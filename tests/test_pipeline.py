"""Pipeline mechanics with a fake LLM: evidence verification, downgrades, caching, scoring integration."""
from pathlib import Path

import pytest

from src.audit.pipeline import AuditPipeline
from src.audit.rag import KnowledgeBase
from src.audit.schemas import PolicyAnalysis, PolicyClaim
from src.audit.transcript_io import find_transcripts, load_transcript_json
from tests.fakes import FakeGateway, make_analysis

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def kb():
    return KnowledgeBase(use_embeddings=False)


@pytest.fixture()
def sample():
    files = find_transcripts(ROOT / "data" / "transcripts")
    if not files:
        pytest.skip("no transcripts")
    return load_transcript_json(files[0])


def make_pipe(kb, tmp_path, analysis, policy):
    return AuditPipeline(kb=kb, gateway=FakeGateway(analysis=analysis, policy=policy), cache_dir=tmp_path)


def test_full_pipeline_uses_two_requests_and_scores(kb, tmp_path, sample):
    call, _ = sample
    pipe = make_pipe(kb, tmp_path, lambda p: make_analysis(p, call), PolicyAnalysis(claims=[]))
    rep = pipe.audit_call(call)
    assert rep.meta.llm_requests == 2
    assert 0 < rep.scores.overall <= 100 and rep.scores.sop_points_possible > 0
    assert rep.topic and rep.emotion.start == "angry" and rep.emotion.trend == "improved"
    assert rep.coaching and rep.strengths
    assert all(r.evidence_verified for r in rep.sop_results if r.status in ("followed", "partial"))


def test_fabricated_quote_is_downgraded_and_flagged(kb, tmp_path, sample):
    call, _ = sample
    sid = "GEN-03"
    pipe = make_pipe(kb, tmp_path, lambda p: make_analysis(p, call, quote_for={sid: "this sentence was never spoken by anyone"}), PolicyAnalysis(claims=[]))
    rep = pipe.audit_call(call)
    r = next(x for x in rep.sop_results if x.step_id == sid)
    assert r.status == "partial" and not r.evidence_verified
    assert any(sid in w for w in rep.meta.warnings)


def test_missed_critical_step_caps_score(kb, tmp_path, sample):
    call, _ = sample
    pipe = make_pipe(kb, tmp_path, lambda p: make_analysis(p, call, statuses={"GEN-03": "missed"}), PolicyAnalysis(claims=[]))
    rep = pipe.audit_call(call)
    assert rep.scores.overall <= 70 and rep.scores.critical_failure and any("GEN-03" in r for r in rep.scores.cap_reasons)


def test_policy_violation_needs_real_clause_and_real_quote(kb, tmp_path, sample):
    call, _ = sample
    agent_turn = next(t for t in call.turns if t.speaker == "agent" and len(t.text.split()) > 8)
    quote = " ".join(agent_turn.text.split()[:8])
    claims = PolicyAnalysis(claims=[
        PolicyClaim(turn=agent_turn.turn_id, quote=quote, claim="c", clause_id="REF-1.1", verdict="violation", severity="major", explanation="wrong window"),
        PolicyClaim(turn=agent_turn.turn_id, quote=quote, claim="c", clause_id="ZZZ-9.9", verdict="violation", severity="critical", explanation="invented clause"),
        PolicyClaim(turn=1, quote="words that nobody said at all in this call", claim="c", clause_id="REF-1.1", verdict="violation", severity="major", explanation="fake quote"),
    ])
    pipe = make_pipe(kb, tmp_path, lambda p: make_analysis(p, call), claims)
    rep = pipe.audit_call(call)
    violations = [p for p in rep.policy_results if p.verdict == "violation"]
    assert len(violations) == 1 and violations[0].clause_id == "REF-1.1" and violations[0].turn == agent_turn.turn_id
    assert rep.scores.policy_penalty_total == 8
    assert len(rep.meta.warnings) >= 2


def test_not_returned_steps_are_excluded_not_penalised(kb, tmp_path, sample):
    call, _ = sample

    def partial_answer(p):
        a = make_analysis(p, call)
        a.steps = a.steps[:3]
        return a

    rep = make_pipe(kb, tmp_path, partial_answer, PolicyAnalysis(claims=[])).audit_call(call)
    assert sum(1 for r in rep.sop_results if r.status == "not_applicable") == len(rep.sop_results) - 3
    assert any("returned nothing" in w for w in rep.meta.warnings)


def test_second_run_hits_cache_and_uses_zero_requests(kb, tmp_path, sample):
    call, _ = sample
    gw = FakeGateway(analysis=lambda p: make_analysis(p, call), policy=PolicyAnalysis(claims=[]))
    pipe = AuditPipeline(kb=kb, gateway=gw, cache_dir=tmp_path)
    first = pipe.audit_call(call)
    n = gw.request_count
    second = pipe.audit_call(call)
    assert gw.request_count == n and second.meta.cache_hit and second.scores.overall == first.scores.overall


def test_timing_gaps_come_from_metrics_not_the_llm(kb, tmp_path):
    files = find_transcripts(ROOT / "data" / "transcripts")
    for p in files:
        call, raw = load_transcript_json(p)
        if "dead_air" in raw["ground_truth"].get("gaps", []):
            rep = make_pipe(kb, tmp_path, lambda pr: make_analysis(pr, call), PolicyAnalysis(claims=[])).audit_call(call)
            assert any(g.gap_type == "dead_air" and g.source == "timing" for g in rep.gaps)
            return
    pytest.skip("no dead-air transcript available")


def test_empty_transcript_is_rejected(kb, tmp_path, sample):
    call, _ = sample
    call = call.model_copy(update={"turns": []})
    with pytest.raises(ValueError):
        make_pipe(kb, tmp_path, None, None).audit_call(call)
