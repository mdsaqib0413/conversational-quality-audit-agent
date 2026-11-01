"""Offline tests for optional Langfuse exporter (src/audit/langfuse_export.py).

Zero real network calls. Uses mock and fake clients.
Tests:
1. Export skipped when keys are absent.
2. Source isolation: skipped for test/eval unless LANGFUSE_EXPORT_EVAL=1.
3. Errors are swallowed without interrupting audits.
4. Metadata-only export when LANGFUSE_CAPTURE_CONTENT=0 (default).
5. PII masking (emails and phone numbers) when LANGFUSE_CAPTURE_CONTENT=1.
6. Trace score records overall score.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest

from src.audit.langfuse_export import (
    export_audit_to_langfuse,
    is_capture_content_enabled,
    is_export_eval_enabled,
    is_langfuse_enabled,
)
from src.audit.schemas import AuditMeta, AuditReport, CallTranscript, ScoreBreakdown
from src.audit.tracer import AuditTracer, TraceStep


class FakeTrace:
    def __init__(self, id: str, name: str, input: Any = None, output: Any = None, metadata: Any = None, tags: Any = None):
        self.id = id
        self.name = name
        self.input = input
        self.output = output
        self.metadata = metadata or {}
        self.tags = tags or []
        self.spans: List[Dict[str, Any]] = []
        self.generations: List[Dict[str, Any]] = []
        self.scores: List[Dict[str, Any]] = []

    def span(self, name: str, start_time: Any = None, end_time: Any = None, metadata: Any = None, input: Any = None, output: Any = None) -> Dict[str, Any]:
        entry = {
            "name": name,
            "start_time": start_time,
            "end_time": end_time,
            "metadata": metadata or {},
            "input": input,
            "output": output,
        }
        self.spans.append(entry)
        return entry

    def generation(
        self,
        name: str,
        model: Optional[str] = None,
        usage: Optional[Dict[str, Any]] = None,
        start_time: Any = None,
        end_time: Any = None,
        metadata: Any = None,
        input: Any = None,
        output: Any = None,
    ) -> Dict[str, Any]:
        entry = {
            "name": name,
            "model": model,
            "usage": usage,
            "start_time": start_time,
            "end_time": end_time,
            "metadata": metadata or {},
            "input": input,
            "output": output,
        }
        self.generations.append(entry)
        return entry

    def score(self, name: str, value: float, comment: Optional[str] = None) -> None:
        self.scores.append({"name": name, "value": value, "comment": comment})


class FakeLangfuseClient:
    def __init__(self):
        self.traces: List[FakeTrace] = []
        self.flushed = False

    def trace(self, id: str, name: str, input: Any = None, output: Any = None, metadata: Any = None, tags: Any = None) -> FakeTrace:
        t = FakeTrace(id=id, name=name, input=input, output=output, metadata=metadata, tags=tags)
        self.traces.append(t)
        return t

    def flush(self) -> None:
        self.flushed = True


def _make_dummy_report(call_id: str = "call_001", source: str = "prod") -> AuditReport:
    scores = ScoreBreakdown(
        sop_score=26.0,
        policy_score=30.0,
        empathy_score=13.5,
        communication_score=15.5,
        overall=85.0,
        overall_before_cap=85.0,
        grade="A",
        grade_label="Good",
    )
    meta = AuditMeta(
        model="gemini-2.5-flash",
        audit_seconds=4.2,
        llm_requests=2,
        tokens_in=1500,
        tokens_out=450,
        estimated_cost_usd=0.000248,
        trace_id=f"test_trace_{call_id}",
        source=source,
    )
    return AuditReport(
        call_id=call_id,
        generated_at="2026-11-01T12:00:00",
        topic="refund",
        topic_confidence=0.95,
        summary="Customer requested refund for defective electronics item.",
        customer_issue="Customer received non-working earphones and wants a refund.",
        resolved=True,
        scores=scores,
        transcript=CallTranscript(call_id=call_id, turns=[]),
        meta=meta,
    )


def test_is_langfuse_enabled_checks_all_three_keys(monkeypatch):
    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_HOST", raising=False)
    assert not is_langfuse_enabled()

    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-test")
    assert not is_langfuse_enabled()

    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-test")
    assert not is_langfuse_enabled()

    monkeypatch.setenv("LANGFUSE_HOST", "https://cloud.langfuse.com")
    assert is_langfuse_enabled()


def test_export_skipped_when_no_keys(monkeypatch):
    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_HOST", raising=False)

    report = _make_dummy_report()
    result = export_audit_to_langfuse(report)
    assert result is False


def test_source_isolation_skips_test_and_eval_by_default(monkeypatch):
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-test")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-test")
    monkeypatch.setenv("LANGFUSE_HOST", "https://cloud.langfuse.com")
    monkeypatch.delenv("LANGFUSE_EXPORT_EVAL", raising=False)

    fake_client = FakeLangfuseClient()
    report = _make_dummy_report(source="test")
    tracer = AuditTracer(run_id="run_test", source="test")

    # Source is "test" -> skipped
    result = export_audit_to_langfuse(report, tracer, client=fake_client)
    assert result is False
    assert len(fake_client.traces) == 0

    # Source is "eval" -> skipped
    tracer_eval = AuditTracer(run_id="run_eval", source="eval")
    result_eval = export_audit_to_langfuse(report, tracer_eval, client=fake_client)
    assert result_eval is False
    assert len(fake_client.traces) == 0


def test_source_isolation_exports_when_langfuse_export_eval_enabled(monkeypatch):
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-test")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-test")
    monkeypatch.setenv("LANGFUSE_HOST", "https://cloud.langfuse.com")
    monkeypatch.setenv("LANGFUSE_EXPORT_EVAL", "1")

    assert is_export_eval_enabled()

    fake_client = FakeLangfuseClient()
    report = _make_dummy_report(source="eval")
    tracer = AuditTracer(run_id="run_eval_01", source="eval")

    result = export_audit_to_langfuse(report, tracer, client=fake_client)
    assert result is True
    assert len(fake_client.traces) == 1
    assert fake_client.flushed is True


def test_export_swallows_client_exceptions(monkeypatch):
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-test")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-test")
    monkeypatch.setenv("LANGFUSE_HOST", "https://cloud.langfuse.com")

    class ErrorClient:
        def trace(self, *args, **kwargs):
            raise ConnectionError("Network unreachable")

    report = _make_dummy_report()
    tracer = AuditTracer(run_id="run_err", source="prod")

    # Must swallow error and return False without raising
    result = export_audit_to_langfuse(report, tracer, client=ErrorClient())
    assert result is False


def test_export_swallows_flush_exceptions(monkeypatch):
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-test")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-test")
    monkeypatch.setenv("LANGFUSE_HOST", "https://cloud.langfuse.com")

    class FlushErrorClient(FakeLangfuseClient):
        def flush(self):
            raise RuntimeError("Langfuse server timeout on flush")

    report = _make_dummy_report()
    tracer = AuditTracer(run_id="run_flush_err", source="prod")

    result = export_audit_to_langfuse(report, tracer, client=FlushErrorClient())
    assert result is False


def test_export_metadata_only_when_capture_content_zero(monkeypatch, tmp_path):
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-test")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-test")
    monkeypatch.setenv("LANGFUSE_HOST", "https://cloud.langfuse.com")
    monkeypatch.setenv("LANGFUSE_CAPTURE_CONTENT", "0")

    assert not is_capture_content_enabled()

    fake_client = FakeLangfuseClient()
    report = _make_dummy_report()
    tracer = AuditTracer(run_id="run_meta_only", traces_dir=tmp_path, source="prod")

    tracer.record_step(
        step_name="quality_gate",
        decision_type="plain_code",
        status="ok",
        inputs_summary="turns count = 12",
        outputs_summary="gate passed",
        start_t=100.0,
        end_t=100.05,
    )
    tracer.record_step(
        step_name="policy_check",
        decision_type="model",
        status="ok",
        model_name="gemini-2.5-flash",
        tokens_in=800,
        tokens_out=200,
        prompt="Sensitive prompt with customer email user@shopease.com",
        response="Sensitive model answer with phone 9876543210",
        start_t=100.05,
        end_t=101.5,
    )

    result = export_audit_to_langfuse(report, tracer, client=fake_client)
    assert result is True
    assert len(fake_client.traces) == 1

    tr = fake_client.traces[0]
    # In metadata-only mode, trace input and output must be None
    assert tr.input is None
    assert tr.output is None

    # Metadata must carry real numbers
    assert tr.metadata["call_id"] == "call_001"
    assert tr.metadata["overall_score"] == 85.0
    assert tr.metadata["content_captured"] is False

    # Score recorded on trace
    assert len(tr.scores) == 1
    assert tr.scores[0]["name"] == "overall_score"
    assert tr.scores[0]["value"] == 85.0

    # Spans (plain_code step) have None for input and output
    assert len(tr.spans) == 1
    assert tr.spans[0]["name"] == "quality_gate"
    assert tr.spans[0]["input"] is None
    assert tr.spans[0]["output"] is None
    assert tr.spans[0]["metadata"]["decision_type"] == "plain_code"

    # Generations (model step) have None for input/output, but real usage and model
    assert len(tr.generations) == 1
    gen = tr.generations[0]
    assert gen["name"] == "policy_check"
    assert gen["model"] == "gemini-2.5-flash"
    assert gen["usage"] == {"input": 800, "output": 200, "total": 1000}
    assert gen["input"] is None
    assert gen["output"] is None
    assert "user@shopease.com" not in json.dumps(tr.metadata)


def test_export_masks_personal_data_when_capture_content_one(monkeypatch, tmp_path):
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-test")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-test")
    monkeypatch.setenv("LANGFUSE_HOST", "https://cloud.langfuse.com")
    monkeypatch.setenv("LANGFUSE_CAPTURE_CONTENT", "1")

    assert is_capture_content_enabled()

    fake_client = FakeLangfuseClient()
    report = _make_dummy_report()
    report.customer_issue = "My email is deepak.sharma@example.in and phone is 9876543210"
    report.summary = "Resolved inquiry for deepak.sharma@example.in"

    tracer = AuditTracer(run_id="run_masked_content", traces_dir=tmp_path, source="prod")
    tracer.record_step(
        step_name="sop_check",
        decision_type="model",
        status="ok",
        model_name="gemini-2.5-flash",
        tokens_in=600,
        tokens_out=150,
        prompt="Verify identity for deepak.sharma@example.in and 9876543210",
        response="Agent verified phone 9876543210 successfully.",
        start_t=10.0,
        end_t=11.2,
    )

    result = export_audit_to_langfuse(report, tracer, client=fake_client)
    assert result is True

    tr = fake_client.traces[0]
    # Check trace input
    assert "deepak.sharma@example.in" not in tr.input
    assert "9876543210" not in tr.input
    assert "[EMAIL_MASKED]" in tr.input
    assert "[PHONE_MASKED]" in tr.input

    # Check trace output
    assert "deepak.sharma@example.in" not in tr.output
    assert "[EMAIL_MASKED]" in tr.output

    # Check generation input / output
    assert len(tr.generations) == 1
    gen = tr.generations[0]
    assert "deepak.sharma@example.in" not in gen["input"]
    assert "9876543210" not in gen["input"]
    assert "[EMAIL_MASKED]" in gen["input"]
    assert "[PHONE_MASKED]" in gen["input"]

    assert "9876543210" not in gen["output"]
    assert "[PHONE_MASKED]" in gen["output"]
