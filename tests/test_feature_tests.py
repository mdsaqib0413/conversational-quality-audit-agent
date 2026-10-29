"""The feature-test machinery itself: expectations are in sync, a perfect system passes everything,
and a sabotaged system FAILS the right checks (test the tests)."""
import copy
from pathlib import Path

import pytest

from src.audit.expectations import build_all, load_expected, load_spec
from src.audit.featuretests import aggregate, audit_rows, evaluate_spec, offline_rows, output_rows, run_all, to_markdown
from src.audit.rag import KnowledgeBase
from src.audit.transcript_io import find_transcripts, load_transcript_json
from tests.demo_data import build_reports

ROOT = Path(__file__).resolve().parent.parent
KB = KnowledgeBase(use_embeddings=False)
FILES = find_transcripts(ROOT / "data" / "transcripts", only_verified=True)


@pytest.fixture(scope="module")
def reports():
    return build_reports()


@pytest.fixture(scope="module")
def expected():
    return load_expected()


def test_expected_results_file_is_in_sync_with_the_transcripts(expected):
    fresh = build_all(ROOT / "data" / "transcripts", KB)
    import json

    assert json.loads(json.dumps(fresh, sort_keys=True)) == json.loads(json.dumps(expected, sort_keys=True)), \
        "data/expected/expected_results.json is out of date: run python scripts/build_expectations.py"


def test_every_verified_call_has_expectations(expected):
    assert {p.stem for p in FILES} == set(expected)


def test_spec_metrics_are_all_produced_by_the_engine(reports, expected):
    """Every metric named in the spec must actually be computed, otherwise a check could silently never run."""
    produced = set()
    for p in FILES:
        call, raw = load_transcript_json(p)
        for r in offline_rows(call, raw, expected[p.stem], KB) + audit_rows(reports[p.stem], expected[p.stem]):
            produced |= set(r["metrics"])
    for r in output_rows(next(iter(reports.values()))):
        produced |= set(r["metrics"])
    named = {c["metric"] for f in load_spec()["features"] for c in f["checks"]}
    assert named <= produced, f"metrics never computed: {sorted(named - produced)}"


def test_offline_features_pass_on_the_real_code(expected):
    res = run_all(FILES, KB, expected, load_spec(), reports=None)
    bad = [f for f in res["features"] if not f["needs_ai"] and f["id"] != "report_outputs" and f["status"] in ("FAIL", "WARN")]
    assert not bad, [(f["title"], [c for c in f["checks"] if c["status"] != "PASS"]) for f in bad]


def test_a_perfect_system_passes_every_feature(reports, expected):
    res = run_all(FILES, KB, expected, load_spec(), reports)
    assert res["summary"].get("FAIL", 0) == 0 and res["summary"].get("WARN", 0) == 0, to_markdown(res)


def test_markdown_report_lists_every_feature(reports, expected):
    md = to_markdown(run_all(FILES, KB, expected, load_spec(), reports))
    for f in load_spec()["features"]:
        assert f["title"] in md


# ------------------------------------------------------------------ sabotage: the tests must be able to fail
def _rates(reports, expected, mutate):
    rows = []
    for p in FILES:
        rep = copy.deepcopy(reports[p.stem])
        mutate(rep)
        rows += audit_rows(rep, expected[p.stem])
    return aggregate(rows)


def _status(spec_id, rates):
    f = next(x for x in evaluate_spec(load_spec(), rates) if x["id"] == spec_id)
    return f["status"]


def test_flipping_step_results_fails_sop_judging(reports, expected):
    def sab(rep):
        for r in rep.sop_results:
            if r.status == "missed":
                r.status = "followed"      # a lenient judge that misses every real problem

    assert _status("sop_steps", _rates(reports, expected, sab)) == "FAIL"


def test_inventing_violations_fails_policy_precision(reports, expected):
    from src.audit.schemas import PolicyResult

    def sab(rep):
        rep.policy_results.append(PolicyResult(clause_id="REF-1.1", verdict="violation", severity="major", turn=1, quote="x", evidence_verified=True))

    rates = _rates(reports, expected, sab)
    assert _status("policy", rates) == "FAIL"


def test_missing_violations_fails_policy_recall(reports, expected):
    def sab(rep):
        rep.policy_results = [p for p in rep.policy_results if p.verdict != "violation"]

    assert _status("policy", _rates(reports, expected, sab)) == "FAIL"


def test_removing_the_critical_cap_fails_scoring_outcome(reports, expected):
    def sab(rep):
        rep.scores.critical_failure = False
        rep.scores.overall = rep.scores.overall_before_cap + 40

    assert _status("scoring_outcome", _rates(reports, expected, sab)) == "FAIL"


def test_unverified_quotes_fail_evidence_integrity(reports, expected):
    def sab(rep):
        for r in rep.sop_results:
            if r.status == "followed":
                r.evidence_verified = False

    assert _status("evidence", _rates(reports, expected, sab)) == "FAIL"


def test_overspending_ai_requests_fails_efficiency(reports, expected):
    def sab(rep):
        rep.meta.llm_requests = 9

    assert _status("efficiency", _rates(reports, expected, sab)) == "FAIL"


def test_hallucinated_timing_gap_fails_gap_feature(reports, expected):
    from src.audit.schemas import GapResult

    def sab(rep):
        rep.gaps.append(GapResult(gap_type="dead_air", turn=3, detail="invented", source="llm"))

    assert _status("gaps", _rates(reports, expected, sab)) in ("FAIL",)


def test_wrong_topic_and_signals_fail_offline_checks(expected, monkeypatch):
    import src.audit.featuretests as F
    from src.audit.topic import TopicResult

    monkeypatch.setattr(F, "detect_topic", lambda turns: TopicResult(topic="general", confidence=0.5, scores={}, signals=[]))
    rows = []
    for p in FILES:
        call, raw = load_transcript_json(p)
        rows += offline_rows(call, raw, expected[p.stem], KB)
    rates = aggregate(rows)
    assert _status("topic", rates) == "FAIL" and _status("signals", rates) == "FAIL"


def test_the_output_checks_catch_html_injection(reports, monkeypatch):
    import src.audit.report as R

    monkeypatch.setattr(R, "esc", lambda s: str(s))   # simulate a regression that stops escaping
    import src.audit.ui_html as U

    monkeypatch.setattr(U, "esc", lambda s: str(s))
    rows = output_rows(next(iter(reports.values())))
    assert not next(r for r in rows if r["item"] == "Hostile text is escaped")["ok"]
