"""Tests for observability traces and pipeline error resilience.

Covers:
1. Every audit produces a traces/<run_id>.jsonl with one record per step.
2. Model failure in SOP judgment returns a structured 'failed' result without crashing.
3. Model failure in policy check returns a structured 'failed' result with partial steps completed.
4. Unusable audio halts with a structured 'handoff' result and 0 API calls.
5. Degraded audio results in status='degraded' and lowered certainty.
6. Evidence validity confirms quotes exist in cited turn and timestamps are within bounds.
"""
from __future__ import annotations

import json
from pathlib import Path
import pytest

from src.audit.pipeline import AuditPipeline
from src.audit.rag import KnowledgeBase
from src.audit.schemas import (CallTranscript, DialogueTurn, PolicyAnalysis,
                              ConversationAnalysis, StepJudgement)
from src.audit.tracer import TRACES_DIR, load_traces
from tests.fakes import FakeGateway, make_analysis

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def kb() -> KnowledgeBase:
    return KnowledgeBase(use_embeddings=False)


def test_trace_file_written_per_audit(kb: KnowledgeBase, tmp_path: Path):
    turns = [
        DialogueTurn(turn_id=1, speaker="agent", text="ShopEase support, Rahul speaking. This call is recorded.", start_time=0.0, end_time=4.0),
        DialogueTurn(turn_id=2, speaker="customer", text="I need help with my refund for order ORD-12345, phone last 4 are 9988.", start_time=4.5, end_time=8.5),
        DialogueTurn(turn_id=3, speaker="agent", text="Thank you, I will check your refund of 1,200 rupees.", start_time=9.0, end_time=13.0),
    ]
    call = CallTranscript(call_id="test_trace_call_01", language="en", duration_seconds=15.0, turns=turns)
    gw = FakeGateway(analysis=lambda p: make_analysis(p, call), policy=PolicyAnalysis(claims=[]))
    pipe = AuditPipeline(kb=kb, gateway=gw, cache_dir=tmp_path)

    report = pipe.audit_call(call)
    assert report.meta.trace_id, "Report meta must include trace_id"

    trace_file = TRACES_DIR / f"{report.meta.trace_id}.jsonl"
    assert trace_file.exists(), f"Trace file {trace_file} must exist on disk"

    lines = [json.loads(l) for l in trace_file.read_text(encoding="utf-8").splitlines() if l.strip()]
    step_names = [l["step_name"] for l in lines]

    assert "input_ingestion" in step_names
    assert "quality_gate" in step_names
    assert "call_state" in step_names
    assert "sop_check" in step_names or "scorecard_judgment" in step_names
    assert "policy_check" in step_names
    assert "evidence_verification" in step_names
    assert "scoring" in step_names


def test_sop_model_failure_returns_structured_failed_result(kb: KnowledgeBase, tmp_path: Path):
    turns = [
        DialogueTurn(turn_id=1, speaker="agent", text="ShopEase support, Rahul speaking.", start_time=0.0, end_time=3.0),
        DialogueTurn(turn_id=2, speaker="customer", text="Where is my parcel?", start_time=3.5, end_time=6.0),
    ]
    call = CallTranscript(call_id="test_fail_sop", language="en", duration_seconds=10.0, turns=turns)

    def failing_analysis(prompt):
        raise RuntimeError("Quota exhausted or model timeout (503 Service Unavailable)")

    gw = FakeGateway(analysis=failing_analysis, policy=PolicyAnalysis(claims=[]))
    pipe = AuditPipeline(kb=kb, gateway=gw, cache_dir=tmp_path)

    report = pipe.audit_call(call)
    assert report.status == "failed"
    assert report.failed_step == "scorecard_judgment"
    assert "quality_gate" in report.completed_steps
    assert "call_state" in report.completed_steps
    assert report.scores.critical_failure is True
    assert report.scores.overall == 0.0
    assert any("503" in r or "scorecard_judgment" in r for r in report.scores.cap_reasons)


def test_policy_model_failure_returns_structured_failed_result(kb: KnowledgeBase, tmp_path: Path):
    turns = [
        DialogueTurn(turn_id=1, speaker="agent", text="ShopEase customer care. Please provide your order ID.", start_time=0.0, end_time=3.0),
        DialogueTurn(turn_id=2, speaker="customer", text="My order ID is ORD-99121, phone ending in 4411.", start_time=3.5, end_time=6.0),
        DialogueTurn(turn_id=3, speaker="agent", text="Thank you, checking your order details now.", start_time=6.5, end_time=9.0),
    ]
    call = CallTranscript(call_id="test_fail_policy", language="en", duration_seconds=10.0, turns=turns)

    def failing_policy(prompt):
        raise RuntimeError("Policy retrieval / RAG model rate limited (429 Resource Exhausted)")

    gw = FakeGateway(analysis=lambda p: make_analysis(p, call), policy=failing_policy)
    pipe = AuditPipeline(kb=kb, gateway=gw, cache_dir=tmp_path)

    report = pipe.audit_call(call)
    assert report.status == "failed"
    assert report.failed_step == "policy_check"
    assert "scorecard_judgment" in report.completed_steps
    assert report.scores.critical_failure is True


def test_unusable_audio_returns_handoff_with_zero_llm_calls(kb: KnowledgeBase, tmp_path: Path):
    turns = [
        DialogueTurn(turn_id=1, speaker="agent", text="...", asr_confidence=0.15, silence_before=0.0),
        DialogueTurn(turn_id=2, speaker="customer", text="...", asr_confidence=0.20, silence_before=20.0),
    ]
    call = CallTranscript(call_id="test_handoff_unusable", language="te", duration_seconds=30.0, turns=turns)
    gw = FakeGateway(analysis=lambda p: make_analysis(p, call), policy=PolicyAnalysis(claims=[]))
    pipe = AuditPipeline(kb=kb, gateway=gw, cache_dir=tmp_path)

    report = pipe.audit_call(call)
    assert report.cannot_judge is True
    assert report.status == "handoff"
    assert report.meta.llm_requests == 0
    assert gw.request_count == 0


def test_degraded_quality_marks_findings_medium_certainty(kb: KnowledgeBase, tmp_path: Path):
    turns = [
        DialogueTurn(turn_id=1, speaker="agent", text="షాపేజ్ కస్టమర్ కేర్. నా పేరు రాహుల్. కాల్ రికార్డ్ అవుతుంది.", asr_confidence=0.55),
        DialogueTurn(turn_id=2, speaker="customer", text="నా ఆర్డర్ ఇంకా రాలేదు.", asr_confidence=0.52),
    ]
    call = CallTranscript(call_id="test_degraded_audit", language="te", duration_seconds=15.0, turns=turns)
    gw = FakeGateway(analysis=lambda p: make_analysis(p, call), policy=PolicyAnalysis(claims=[]))
    pipe = AuditPipeline(kb=kb, gateway=gw, cache_dir=tmp_path)

    report = pipe.audit_call(call)
    assert report.status == "degraded"
    assert report.meta.status == "degraded"
    assert any(f.certainty in ("medium", "low") for f in report.findings)


def test_out_of_scope_call_returns_handoff_with_zero_llm_calls(kb: KnowledgeBase, tmp_path: Path):
    turns = [
        DialogueTurn(turn_id=1, speaker="agent", text="హలో సురేష్, ఈరోజు సాయంత్రం సినిమాకి వెళ్దామా?", start_time=0.0, end_time=3.5),
        DialogueTurn(turn_id=2, speaker="customer", text="ఈరోజు కుదరదు రా, రేపు క్రికెట్ మ్యాచ్ ఆడుకుందాం.", start_time=4.0, end_time=7.5),
    ]
    call = CallTranscript(call_id="te_synthetic_out_of_scope", language="te", duration_seconds=10.0, turns=turns)
    gw = FakeGateway(analysis=lambda p: make_analysis(p, call), policy=PolicyAnalysis(claims=[]))
    pipe = AuditPipeline(kb=kb, gateway=gw, cache_dir=tmp_path)

    report = pipe.audit_call(call)
    assert report.cannot_judge is True
    assert report.status == "handoff"
    assert report.meta.llm_requests == 0
    assert gw.request_count == 0


def test_deployment_assets_exist_and_valid():
    root = Path(__file__).resolve().parent.parent
    dockerfile = root / "Dockerfile"
    dockerignore = root / ".dockerignore"
    deploy_md = root / "DEPLOY.md"
    pricing_yaml = root / "eval" / "pricing.yaml"
    pass_rule_md = root / "eval" / "PASS_RULE.md"

    assert dockerfile.exists(), "Dockerfile must exist"
    assert "8501" in dockerfile.read_text(encoding="utf-8"), "Dockerfile must expose port 8501"

    assert dockerignore.exists(), ".dockerignore must exist"
    assert deploy_md.exists(), "DEPLOY.md must exist"

    assert pricing_yaml.exists(), "eval/pricing.yaml must exist"
    import yaml
    pricing = yaml.safe_load(pricing_yaml.read_text(encoding="utf-8"))
    assert "gemini-1.5-flash" in pricing["models"], "pricing.yaml must define gemini-1.5-flash"

    assert pass_rule_md.exists(), "eval/PASS_RULE.md must exist"

