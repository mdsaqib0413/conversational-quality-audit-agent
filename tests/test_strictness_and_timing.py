"""Strict judging (missing elements), timing penalties, implied gaps."""
from pathlib import Path

from src.audit.evaluation import implied_gaps
from src.audit.pipeline import AuditPipeline
from src.audit.rag import KnowledgeBase
from src.audit.schemas import PolicyAnalysis, SOPResult
from src.audit.scoring import score_audit, timing_penalty
from src.audit.transcript_io import load_transcript_json
from tests.fakes import FakeGateway, make_analysis

KB = KnowledgeBase(use_embeddings=False)
ROOT = Path(__file__).resolve().parent.parent


def run(call, tmp_path, **kw):
    gw = FakeGateway(analysis=lambda p: make_analysis(p, call, **kw), policy=PolicyAnalysis(claims=[]))
    return AuditPipeline(kb=KB, gateway=gw, cache_dir=tmp_path).audit_call(call)


def test_followed_with_a_missing_element_is_downgraded_to_partial(tmp_path):
    call, _ = load_transcript_json(ROOT / "data" / "transcripts" / "call_009.json")
    rep = run(call, tmp_path, missing={"GEN-01": "the agent's own name"})
    r = next(x for x in rep.sop_results if x.step_id == "GEN-01")
    assert r.status == "partial" and r.missing == "the agent's own name" and "Downgraded" in r.reason
    assert any("the agent's own name" in c.evidence for c in rep.coaching)


def test_none_like_missing_values_do_not_downgrade(tmp_path):
    call, _ = load_transcript_json(ROOT / "data" / "transcripts" / "call_009.json")
    for word in ("none", "None.", "N/A", "nothing", "-"):
        rep = run(call, tmp_path / word.strip(".-/").replace("/", "_") or "dash", missing={"GEN-01": word})
        assert next(x for x in rep.sop_results if x.step_id == "GEN-01").status == "followed"


def test_timing_penalty_math_and_cap():
    rubric = KB.rubric
    assert timing_penalty(0, 0, rubric) == (0.0, [])
    pts, notes = timing_penalty(1, 1, rubric)
    assert pts == 2.0 and len(notes) == 2
    assert timing_penalty(5, 5, rubric)[0] == 3.0


def test_timing_penalty_reduces_communication_only():
    base = score_audit([SOPResult(step_id="A", status="followed", weight=3)], [], 5, 5, KB.rubric)
    pen = score_audit([SOPResult(step_id="A", status="followed", weight=3)], [], 5, 5, KB.rubric, dead_air_events=2, agent_interruptions=1)
    assert base.communication_score == 15 and pen.communication_score == 12
    assert pen.sop_score == base.sop_score and pen.timing_penalty == 3 and pen.timing_notes


def test_pipeline_applies_timing_penalty_from_the_dead_air_call(tmp_path):
    call, raw = load_transcript_json(ROOT / "data" / "transcripts" / "call_009.json")
    assert "dead_air" in raw["ground_truth"]["gaps"]
    rep = run(call, tmp_path)
    assert rep.scores.timing_penalty >= 1 and rep.scores.communication_score < 15


def test_agent_interruption_counted_only_for_the_agent(tmp_path):
    call, raw = load_transcript_json(ROOT / "data" / "transcripts" / "call_041.json")
    rep = run(call, tmp_path)
    assert rep.metrics.agent_interruptions == 1 and any("interruption" in n for n in rep.scores.timing_notes)


def test_implied_gaps_from_missed_steps():
    assert implied_gaps({"GEN-05": "missed"}) == {"no_empathy"}
    assert implied_gaps({"GEN-05": "partial", "GEN-07": "missed", "GEN-08": "missed"}) == {"no_summary", "no_closing"}
    assert implied_gaps({}) == set()
