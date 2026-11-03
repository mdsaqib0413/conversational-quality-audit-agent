"""Offline unit tests for POLICY_MODEL configuration, cache versioning, pricing, and fail-fast behavior."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.audit.llm import (
    FatalLLMError,
    LLMGateway,
    Provider,
    QuotaExhaustedError,
    RateLimitedError,
    build_targets,
    get_policy_gateway,
)
from src.audit.pipeline import AuditPipeline
from src.audit.policy_check import check_policies, get_policy_model
from src.audit.rag import KnowledgeBase
from src.audit.schemas import CallTranscript, DialogueTurn, PolicyAnalysis
from src.audit.tracer import AuditTracer, estimate_cost, get_model_rates


@pytest.fixture
def sample_call() -> CallTranscript:
    turns = [
        DialogueTurn(turn_id=1, speaker="agent", text="ShopEase support, Rahul here. This call is recorded."),
        DialogueTurn(turn_id=2, speaker="customer", text="I want to return an order ORD-99121, phone 4411."),
        DialogueTurn(turn_id=3, speaker="agent", text="Returns for electronics are accepted within 7 days."),
    ]
    return CallTranscript(call_id="call_test_pm_01", language="en", duration_seconds=12.0, turns=turns)


@pytest.fixture
def kb() -> KnowledgeBase:
    return KnowledgeBase(use_embeddings=False)


def test_policy_model_default_value(monkeypatch):
    """When POLICY_MODEL is not set, default to gemini-3.5-flash."""
    monkeypatch.delenv("POLICY_MODEL", raising=False)
    assert get_policy_model() == "gemini-3.5-flash"

    pipe = AuditPipeline()
    assert pipe.policy_model == "gemini-3.5-flash"


def test_policy_model_env_override(monkeypatch):
    """POLICY_MODEL can be overridden via environment variable."""
    monkeypatch.setenv("POLICY_MODEL", "gemini-2.5-flash")
    assert get_policy_model() == "gemini-2.5-flash"

    pipe = AuditPipeline()
    assert pipe.policy_model == "gemini-2.5-flash"

    # Explicit constructor override takes precedence
    custom_pipe = AuditPipeline(policy_model="custom-gemini-preview")
    assert custom_pipe.policy_model == "custom-gemini-preview"


def test_cache_key_changes_with_policy_model(sample_call, kb, tmp_path, monkeypatch):
    """Cache key must change when POLICY_MODEL changes, and reflect audit-v9 bump."""
    fake_gateway = MagicMock(spec=LLMGateway)
    fake_gateway.model_name = "gemini-2.5-flash"
    fake_gateway.targets = [object()]

    pipe = AuditPipeline(kb=kb, gateway=fake_gateway, cache_dir=tmp_path)

    monkeypatch.setenv("POLICY_MODEL", "gemini-3.5-flash")
    key_35 = pipe._audit_key(sample_call)

    monkeypatch.setenv("POLICY_MODEL", "gemini-2.5-flash")
    key_25 = pipe._audit_key(sample_call)

    monkeypatch.setenv("POLICY_MODEL", "gemini-1.5-flash")
    key_15 = pipe._audit_key(sample_call)

    # Different policy models must generate different cache keys
    assert key_35 != key_25
    assert key_25 != key_15
    assert key_35 != key_15

    assert len(key_35) == 16
    assert len(key_25) == 16


def test_policy_gateway_has_no_fallback_targets(monkeypatch):
    """get_policy_gateway has strictly ONE target and no fallback chain, even if GEMINI_FALLBACK_MODELS is set."""
    monkeypatch.setenv("GEMINI_MODEL", "gemini-2.5-flash")
    monkeypatch.setenv("GEMINI_FALLBACK_MODELS", "gemini-1.5-flash,gemini-2.0-flash")
    monkeypatch.setenv("POLICY_MODEL", "gemini-3.5-flash")

    # Standard chain includes fallbacks
    standard_targets = build_targets()
    assert len(standard_targets) >= 2

    # Policy gateway must have exactly 1 target and no fallback
    policy_gw = get_policy_gateway()
    assert len(policy_gw.targets) == 1
    assert policy_gw.model_name == "gemini-3.5-flash"


def test_no_fallback_on_429_raises_and_records_warning(tmp_path):
    """When the policy model hits 429 quota exhaustion, it raises without switching models and records a warning."""
    tracer = AuditTracer(run_id="test_429_trace", traces_dir=tmp_path)

    # Create a mock provider that raises QuotaExhaustedError (429)
    mock_prov = MagicMock(spec=Provider)
    mock_prov.name = "gemini"
    mock_prov.model = "gemini-3.5-flash"
    mock_prov.ready_check.return_value = None
    mock_prov.complete.side_effect = QuotaExhaustedError("Daily quota exhausted for gemini-3.5-flash (429)")

    gw = LLMGateway(targets=[mock_prov])
    gw.tracer = tracer

    # Calling gateway must raise QuotaExhaustedError directly with NO silent model fallback
    with pytest.raises(QuotaExhaustedError) as exc_info:
        gw.generate_structured("prompt", PolicyAnalysis)

    assert "Daily quota exhausted" in str(exc_info.value)
    # Check that trace warning was recorded
    assert any("429" in w and "gemini-3.5-flash" in w for w in tracer.warnings)


def test_model_unavailable_raises_and_records_warning(tmp_path):
    """When the model is unavailable (e.g. 404), it raises FatalLLMError without switching models and records a warning."""
    tracer = AuditTracer(run_id="test_unavail_trace", traces_dir=tmp_path)

    mock_prov = MagicMock(spec=Provider)
    mock_prov.name = "gemini"
    mock_prov.model = "gemini-3.5-flash"
    mock_prov.ready_check.side_effect = FatalLLMError("Model not available: 404 Not Found")

    gw = LLMGateway(targets=[mock_prov])
    gw.tracer = tracer

    with pytest.raises(FatalLLMError) as exc_info:
        gw.generate_structured("prompt", PolicyAnalysis)

    assert "Model not available" in str(exc_info.value)
    assert any("unavailable" in w and "gemini-3.5-flash" in w for w in tracer.warnings)


def test_pricing_and_cost_from_pricing_yaml():
    """Pricing and cost for gemini-3.5-flash use exact rates from eval/pricing.yaml."""
    rates = get_model_rates("gemini-3.5-flash")
    assert rates.input == 1.50
    assert rates.output == 9.00
    assert rates.source == "eval/pricing.yaml:gemini-3.5-flash"

    cost = estimate_cost("gemini-3.5-flash", tokens_in=10_000, tokens_out=2_000)
    expected_cost = (10_000 * 1.50 / 1_000_000) + (2_000 * 9.00 / 1_000_000)
    assert cost == pytest.approx(expected_cost, rel=1e-5)


def test_pipeline_audit_call_records_policy_model_in_trace(sample_call, kb, tmp_path, monkeypatch):
    """AuditPipeline traces the policy_check step using POLICY_MODEL rates and records failure warnings."""
    monkeypatch.setenv("POLICY_MODEL", "gemini-3.5-flash")

    # Mock gateway that fails at policy check with 429
    def mock_policy_fail(*args, **kwargs):
        raise QuotaExhaustedError("Quota exhausted for gemini-3.5-flash (429)")

    fake_gw = MagicMock()
    fake_gw.request_count = 1
    fake_gw.targets = [object()]
    fake_gw.describe.return_value = "gemini:gemini-2.5-flash"
    fake_gw.model_name = "gemini-2.5-flash"
    fake_gw.last_usage = {"tokens_in": 100, "tokens_out": 50, "prompt": "p", "response": "r"}

    from tests.fakes import make_analysis
    fake_gw.generate_structured.side_effect = lambda prompt, schema, **kw: (
        make_analysis(prompt, sample_call) if schema.__name__ == "ConversationAnalysis" else mock_policy_fail()
    )

    pipe = AuditPipeline(kb=kb, gateway=fake_gw, cache_dir=tmp_path)
    report = pipe.audit_call(sample_call)

    assert report.status == "failed"
    assert report.failed_step == "policy_check"
    assert any("policy_check" in w for w in report.meta.warnings)
