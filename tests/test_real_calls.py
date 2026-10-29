"""Tests for the real-call integration.

(a) Reference JSON files parse correctly.
(b) run_audit on one real MP3 returns non-empty turns and scores.overall in [0, 100].
    Skipped if no API key or no real_calls folder.
(c) No-policy-match case (all-unverifiable results) yields policy_score == 0 and no violations.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
REAL_CALLS_DIR = ROOT / "data" / "audio" / "real_calls"


# ---------------------------------------------------------------------------
# (a) Reference JSON files parse
# ---------------------------------------------------------------------------
REF_FILES = list(REAL_CALLS_DIR.glob("*.reference.json")) if REAL_CALLS_DIR.exists() else []


@pytest.mark.parametrize("ref_path", REF_FILES, ids=[p.stem for p in REF_FILES])
def test_reference_json_parses(ref_path):
    data = json.loads(ref_path.read_text(encoding="utf-8"))
    assert data.get("call_id"), "call_id missing"
    assert data.get("language") == "en", "expected English"
    assert "summary" in data, "summary section missing"
    assert data.get("dataset_url", "").startswith("https://"), "dataset_url missing or invalid"


# ---------------------------------------------------------------------------
# (b) run_audit on one real MP3 (live; skipped if environment not ready)
# ---------------------------------------------------------------------------
_NEEDS_REAL = pytest.mark.skipif(
    not REAL_CALLS_DIR.exists() or not list(REAL_CALLS_DIR.glob("*.mp3")) or not os.getenv("GEMINI_API_KEY"),
    reason="Requires data/audio/real_calls/*.mp3 and GEMINI_API_KEY",
)


@_NEEDS_REAL
def test_run_audit_real_mp3_returns_valid_report(tmp_path):
    from src.audit.pipeline import AuditPipeline

    mp3 = sorted(REAL_CALLS_DIR.glob("*.mp3"))[0]
    pipe = AuditPipeline(cache_dir=tmp_path)
    report = pipe.audit_audio(str(mp3), call_id=mp3.stem, source_set="real", policy_applicable=False)
    assert report.transcript.turns, "transcript has no turns"
    assert 0 <= report.scores.overall <= 100, f"overall score out of range: {report.scores.overall}"
    assert report.meta.source_set == "real"


# ---------------------------------------------------------------------------
# (c) No-policy-match -> no violations and policy_score == 0
# ---------------------------------------------------------------------------
def test_no_policy_match_yields_zero_policy_score_no_violations():
    """When all policy results are unverifiable/empty, scoring must give policy_score=0."""
    from src.audit.rag import KnowledgeBase
    from src.audit.schemas import PolicyAnalysis, PolicyClaim
    from tests.fakes import FakeGateway, make_analysis
    from src.audit.pipeline import AuditPipeline
    from src.audit.transcript_io import find_transcripts, load_transcript_json

    files = find_transcripts(ROOT / "data" / "transcripts")
    if not files:
        pytest.skip("no transcripts")
    call, _ = load_transcript_json(files[0])
    kb = KnowledgeBase(use_embeddings=False)

    # All policy claims unverifiable — simulates a non-ShopEase call
    all_unverifiable = PolicyAnalysis(claims=[
        PolicyClaim(turn=0, quote="", claim="unrelated", clause_id="none",
                    verdict="unverifiable", severity="none", explanation="off-topic call"),
    ])
    pipe = AuditPipeline(kb=kb,
                         gateway=FakeGateway(analysis=lambda p: make_analysis(p, call),
                                             policy=all_unverifiable),
                         cache_dir=Path("/tmp/test_no_policy"))
    report = pipe.audit_call(call, policy_applicable=False)
    violations = [r for r in report.policy_results if r.verdict == "violation"]
    assert not violations, f"Expected no violations, got: {violations}"
    assert report.scores.policy_score == 0.0, f"Expected policy_score=0, got {report.scores.policy_score}"
    assert any("policy" in reason.lower() for reason in report.scores.cap_reasons), \
        "Expected a cap_reason note about missing policy"


def test_policy_not_applicable_renormalises_to_100():
    import yaml
    from src.audit.schemas import SOPResult
    from src.audit.scoring import score_audit

    rubric = yaml.safe_load((ROOT / "data" / "rubric.yaml").read_text(encoding="utf-8"))
    sop = [
        SOPResult(step_id="SOP-01", title="Greeting", status="followed", weight=10, critical=False),
        SOPResult(step_id="SOP-02", title="Verification", status="followed", weight=10, critical=True),
    ]
    # Perfect SOP (100%), perfect empathy (5.0), perfect communication (5.0), 0 timing penalties
    res = score_audit(
        sop=sop,
        policy=[],
        empathy_0_5=5.0,
        communication_0_5=5.0,
        rubric=rubric,
        policy_applicable=False,
    )
    assert res.overall == 100.0
    assert any("policy" in r.lower() for r in res.cap_reasons)

    # With policy_applicable=True, overall is also 100.0 (synthetic unchanged)
    res_synthetic = score_audit(
        sop=sop,
        policy=[],
        empathy_0_5=5.0,
        communication_0_5=5.0,
        rubric=rubric,
        policy_applicable=True,
    )
    assert res_synthetic.overall == 100.0
    assert not res_synthetic.cap_reasons


def test_general_clause_penalty_cap_yields_nonzero():
    """Perfect non-policy call with a critical general-clause violation scores >0 and <100."""
    import yaml
    from src.audit.schemas import PolicyResult, SOPResult
    from src.audit.scoring import score_audit

    rubric = yaml.safe_load((ROOT / "data" / "rubric.yaml").read_text(encoding="utf-8"))
    sop = [
        SOPResult(step_id="SOP-01", title="Greeting", status="followed", weight=10, critical=False),
        SOPResult(step_id="SOP-02", title="Verification", status="followed", weight=10, critical=True),
    ]
    # Simulate a critical general-clause violation with a large penalty
    critical_violation = PolicyResult(
        clause_id="PRV-1.2", policy_title="Recording Disclosure: critical", verdict="violation",
        severity="critical", quote="n/a", claim="n/a", explanation="did not disclose recording",
        penalty=30.0,
    )
    res = score_audit(
        sop=sop,
        policy=[critical_violation],
        empathy_0_5=5.0,
        communication_0_5=5.0,
        rubric=rubric,
        policy_applicable=False,
    )
    assert res.overall > 0, f"Expected score > 0 after capped penalty, got {res.overall}"
    assert res.overall < 100, f"Expected score < 100 due to penalty, got {res.overall}"


def test_mono_diarization_post_pass_lowercase_continuation():
    from src.audit.diarize import post_process_mono_labels
    from src.audit.transcribe import Segment

    segs = [
        ("agent", Segment(start=0.0, end=2.0, text="I can help with")),
        ("customer", Segment(start=2.3, end=4.0, text="that order right away")),  # starts lowercase, prev no punct, gap 0.3s < 1.0s
        ("customer", Segment(start=5.0, end=7.0, text="Thank you.")),
    ]
    fixed = post_process_mono_labels(segs)
    assert fixed[0][0] == "agent"
    assert fixed[1][0] == "agent", "Expected lowercase continuation to adopt previous speaker"
    assert fixed[2][0] == "customer"


