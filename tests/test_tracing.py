"""Offline tests verifying structured tracing, real token usage, pricing.yaml rates, all pipeline steps, stored prompts, and test isolation."""

from __future__ import annotations

import json
import os
from pathlib import Path
import pytest

from src.audit.pipeline import AuditPipeline
from src.audit.rag import KnowledgeBase
from src.audit.schemas import CallTranscript, DialogueTurn, PolicyAnalysis
from src.audit.tracer import (
    AuditTracer,
    estimate_cost,
    get_model_rates,
    get_rate_source,
    load_traces,
    mask_pii,
    sanitize_content,
    truncate_content,
)
from tests.fakes import FakeGateway, make_analysis


@pytest.fixture(scope="module")
def kb() -> KnowledgeBase:
    return KnowledgeBase(use_embeddings=False)


def test_token_counts_real_and_null_when_missing(tmp_path: Path):
    """Test 1: Real token usage is recorded; if missing, null and has_usage=False are recorded, never a guess."""
    tracer = AuditTracer(run_id="test_token_run", traces_dir=tmp_path, source="test")

    # Step with real usage
    step_real = tracer.record_step(
        step_name="sop_check",
        decision_type="model",
        model_name="gemini-1.5-flash",
        tokens_in=540,
        tokens_out=180,
    )
    assert step_real.tokens_in == 540
    assert step_real.tokens_out == 180
    assert step_real.has_usage is True
    assert step_real.usage_estimated is False
    assert step_real.estimated_cost_usd is not None

    # Step with missing usage (provider gave none)
    step_missing = tracer.record_step(
        step_name="policy_check",
        decision_type="model",
        model_name="gemini-1.5-flash",
        tokens_in=None,
        tokens_out=None,
    )
    assert step_missing.tokens_in is None
    assert step_missing.tokens_out is None
    assert step_missing.has_usage is False
    assert step_missing.usage_estimated is False
    assert step_missing.estimated_cost_usd is None

    # Verify JSONL content on disk
    lines = [json.loads(line) for line in tracer.trace_file.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(lines) == 2

    # Verify real usage line
    assert lines[0]["tokens_in"] == 540
    assert lines[0]["tokens_out"] == 180
    assert lines[0]["has_usage"] is True

    # Verify null usage line has literal nulls and false, never a guess
    assert lines[1]["tokens_in"] is None
    assert lines[1]["tokens_out"] is None
    assert lines[1]["has_usage"] is False
    assert lines[1]["usage_estimated"] is False
    assert lines[1]["estimated_cost_usd"] is None


def test_cost_calculation_from_pricing_yaml():
    """Test 2: Rates are loaded dynamically from eval/pricing.yaml, recording model and rate source."""
    # Gemini 1.5 Flash rates: $0.075 / 1M in, $0.300 / 1M out
    rate_in_flash, rate_out_flash, src_flash = get_model_rates("gemini-1.5-flash")
    assert rate_in_flash == 0.075
    assert rate_out_flash == 0.300
    assert "pricing.yaml" in src_flash
    assert "gemini-1.5-flash" in src_flash

    cost_flash = estimate_cost("gemini-1.5-flash", 1_000_000, 1_000_000)
    assert cost_flash == 0.375

    # Gemini 1.5 Pro rates: $1.250 / 1M in, $5.000 / 1M out
    rate_in_pro, rate_out_pro, src_pro = get_model_rates("gemini-1.5-pro")
    assert rate_in_pro == 1.250
    assert rate_out_pro == 5.000
    assert "gemini-1.5-pro" in src_pro

    cost_pro = estimate_cost("gemini-1.5-pro", 1_000_000, 1_000_000)
    assert cost_pro == 6.250

    # Default fallback rate
    _, _, src_default = get_model_rates("unlisted-custom-model")
    assert "pricing.yaml:default" in src_default

    # Missing tokens return None cost
    assert estimate_cost("gemini-1.5-flash", None, 100) is None
    assert estimate_cost("gemini-1.5-flash", 100, None) is None


def test_all_pipeline_steps_traced(kb: KnowledgeBase, tmp_path: Path):
    """Test 3: Every pipeline step (transcribe, diarize, quality_gate, topic, sop_check, policy_retrieval, policy_check, scoring, report) is traced."""
    turns = [
        DialogueTurn(turn_id=1, speaker="agent", text="ShopEase support, Rahul here. This call is recorded.", start_time=0.0, end_time=4.0),
        DialogueTurn(turn_id=2, speaker="customer", text="My order ORD-99121 was not delivered. Phone last four 4411.", start_time=4.5, end_time=8.5),
        DialogueTurn(turn_id=3, speaker="agent", text="Thank you, I will check your delivery status right now.", start_time=9.0, end_time=13.0),
    ]
    call = CallTranscript(call_id="call_trace_all_steps", language="en", duration_seconds=15.0, turns=turns)

    class GatewayWithUsage(FakeGateway):
        def __init__(self, **kw):
            super().__init__(**kw)
            self.last_usage = {
                "tokens_in": 350,
                "tokens_out": 120,
                "model": "gemini-1.5-flash",
                "prompt": "Evaluate this dialogue for SOP adherence.",
                "response": '{"summary": "ok", "customer_issue": "delivery"}',
                "has_usage": True,
            }

    gw = GatewayWithUsage(analysis=lambda p: make_analysis(p, call), policy=PolicyAnalysis(claims=[]))
    pipe = AuditPipeline(kb=kb, gateway=gw, cache_dir=tmp_path)

    report = pipe.audit_call(call)
    trace_id = report.meta.trace_id
    assert trace_id

    trace_file = Path("traces") / f"{trace_id}.jsonl"
    assert trace_file.exists()

    steps = [json.loads(line) for line in trace_file.read_text(encoding="utf-8").splitlines() if line.strip()]
    step_names = [s["step_name"] for s in steps]

    required_steps = [
        "transcribe",
        "diarize",
        "quality_gate",
        "topic",
        "sop_check",
        "policy_retrieval",
        "policy_check",
        "scoring",
        "report",
    ]

    for req in required_steps:
        assert req in step_names, f"Required step '{req}' missing from trace steps: {step_names}"

    for s in steps:
        assert "start_time" in s and s["start_time"], f"Step {s.get('step_name')} missing start_time"
        assert "duration" in s or "latency_seconds" in s, f"Step {s.get('step_name')} missing duration"
        assert s["status"] in ("ok", "degraded", "handoff", "failed", "skipped"), f"Invalid status in step {s.get('step_name')}"
        assert "error_text" in s, f"Step {s.get('step_name')} missing error_text"


def test_prompt_and_response_content_storage_and_pii_masking(tmp_path: Path):
    """Test 4: Prompts and responses stored with size cap, truncation marker, and PII masked."""
    # 1. PII Masking
    pii_text = (
        "User account rahul.sharma@example.com requested refund. "
        "Phone numbers: +91-9876543210 and 9123456780. "
        "Toll free: 1800-111-2222. Order ORD-99121 for Rs 4500 at turn 5."
    )
    masked = mask_pii(pii_text)
    assert "[EMAIL_MASKED]" in masked
    assert "rahul.sharma@example.com" not in masked
    assert "[PHONE_MASKED]" in masked
    assert "9876543210" not in masked
    assert "9123456780" not in masked
    assert "1800-111-2222" not in masked
    assert "ORD-99121" in masked  # Non-PII business IDs preserved
    assert "4500" in masked  # Amounts preserved

    # 2. Size Cap and Truncation Marker
    long_prompt = "Header\n" + ("A" * 15000) + "\nFooter"
    truncated = truncate_content(long_prompt, max_chars=1000)
    assert len(truncated) <= 1000
    assert "... [TRUNCATED] ..." in truncated

    # 3. Storage in TraceStep
    tracer = AuditTracer(run_id="test_content_storage", traces_dir=tmp_path, source="test")
    step = tracer.record_step(
        step_name="sop_check",
        decision_type="model",
        model_name="gemini-1.5-flash",
        tokens_in=400,
        tokens_out=150,
        prompt="Check order for user@shopease.in with mobile 9876543210",
        response="Agent verified customer user@shopease.in successfully",
    )
    assert step.prompt is not None
    assert "[EMAIL_MASKED]" in step.prompt
    assert "[PHONE_MASKED]" in step.prompt
    assert "user@shopease.in" not in step.prompt
    assert "9876543210" not in step.prompt
    assert "[EMAIL_MASKED]" in step.response


def test_isolation_tagging_and_filtering(tmp_path: Path):
    """Test 5: Traces tagged with source='test' or 'eval' are kept out of default view and totals."""
    # Write a prod trace
    t_prod = AuditTracer(run_id="trace_prod_01", traces_dir=tmp_path, source="prod")
    t_prod.record_step("scoring", "plain_code", tokens_in=0, tokens_out=0)

    # Write a test trace
    t_test = AuditTracer(run_id="trace_test_01", traces_dir=tmp_path, source="test")
    t_test.record_step("scoring", "plain_code", tokens_in=0, tokens_out=0)

    # Write an eval trace
    t_eval = AuditTracer(run_id="trace_eval_01", traces_dir=tmp_path, source="eval")
    t_eval.record_step("scoring", "plain_code", tokens_in=0, tokens_out=0)

    # Default load_traces isolates test and eval
    default_traces = load_traces(traces_dir=tmp_path)
    run_ids = [t["run_id"] for t in default_traces]
    assert "trace_prod_01" in run_ids
    assert "trace_test_01" not in run_ids
    assert "trace_eval_01" not in run_ids

    # Including test traces
    with_test = load_traces(traces_dir=tmp_path, include_test=True)
    with_test_ids = [t["run_id"] for t in with_test]
    assert "trace_prod_01" in with_test_ids
    assert "trace_test_01" in with_test_ids
    assert "trace_eval_01" not in with_test_ids

    # Querying specific source
    eval_only = load_traces(traces_dir=tmp_path, source="eval")
    eval_ids = [t["run_id"] for t in eval_only]
    assert eval_ids == ["trace_eval_01"]

    # All traces
    all_traces = load_traces(traces_dir=tmp_path, source="all")
    assert len(all_traces) == 3
