"""Offline unit tests for per-model pricing, exact match, fallback, warning, and shared lookup."""

from __future__ import annotations

import logging
import pytest

from eval.policy_e2e import (
    estimate_cost as e2e_estimate,
    get_model_rates as e2e_rates,
    get_rate_source as e2e_rate_source,
)
from src.audit.langfuse_export import (
    estimate_cost as lf_estimate,
    get_model_rates as lf_rates,
    get_rate_source as lf_rate_source,
)
from src.audit.tracer import (
    _WARNED_FALLBACK_MODELS,
    estimate_cost,
    get_model_rates,
    get_rate_source,
)


def test_exact_match_pricing():
    """Exact model entries match rates in eval/pricing.yaml."""
    # gemini-2.5-flash: input 0.30, output 2.50, cached_input 0.03
    r25 = get_model_rates("gemini-2.5-flash")
    assert r25.input == 0.30
    assert r25.output == 2.50
    assert r25.cached_input == 0.03
    assert "pricing.yaml:gemini-2.5-flash" in r25.source

    # gemini-3.5-flash-lite: input 0.30, output 2.50, cached_input 0.03
    r35_lite = get_model_rates("gemini-3.5-flash-lite")
    assert r35_lite.input == 0.30
    assert r35_lite.output == 2.50
    assert r35_lite.cached_input == 0.03
    assert "pricing.yaml:gemini-3.5-flash-lite" in r35_lite.source

    # gemini-3.5-flash: input 1.50, output 9.00, cached_input 0.15
    r35 = get_model_rates("gemini-3.5-flash")
    assert r35.input == 1.50
    assert r35.output == 9.00
    assert r35.cached_input == 0.15
    assert "pricing.yaml:gemini-3.5-flash" in r35.source

    # Clean prefixes (models/ or provider: prefix)
    r_pref1 = get_model_rates("gemini:gemini-3.5-flash")
    assert r_pref1.input == 1.50
    assert r_pref1.output == 9.00
    assert r_pref1.cached_input == 0.15

    r_pref2 = get_model_rates("models/gemini-2.5-flash")
    assert r_pref2.input == 0.30
    assert r_pref2.output == 2.50
    assert r_pref2.cached_input == 0.03


def test_cost_calculation_exact_models():
    """Cost estimates match exact model pricing."""
    # gemini-3.5-flash-lite: 1,000,000 in ($0.30) + 1,000,000 out ($2.50) = $2.80
    cost_lite = estimate_cost("gemini-3.5-flash-lite", 1_000_000, 1_000_000)
    assert cost_lite == 2.80

    # gemini-3.5-flash: 1,000,000 in ($1.50) + 1,000,000 out ($9.00) = $10.50
    cost_flash = estimate_cost("gemini-3.5-flash", 1_000_000, 1_000_000)
    assert cost_flash == 10.50

    # gemini-2.5-flash: 100,000 in ($0.03) + 20,000 out ($0.05) = $0.08
    cost_25 = estimate_cost("gemini-2.5-flash", 100_000, 20_000)
    assert cost_25 == 0.08


def test_fallback_pricing_and_rate_source():
    """Unlisted model falls back to default rates with rate_source='default'."""
    unlisted_model = "unlisted-arbitrary-model-xyz-123"
    rates = get_model_rates(unlisted_model)
    assert rates.input == 0.075
    assert rates.output == 0.300
    assert rates.source == "default"
    assert rates.rate_source == "default"
    assert get_rate_source(unlisted_model) == "default"

    # Default cost: 1,000,000 in ($0.075) + 1,000,000 out ($0.300) = $0.375
    cost_def = estimate_cost(unlisted_model, 1_000_000, 1_000_000)
    assert cost_def == 0.375


def test_substring_models_do_not_match_exact():
    """A model name containing an existing model as substring must NOT match."""
    # 'gemini-3.5-flash-preview' contains 'gemini-3.5-flash' but is not an exact match
    rates = get_model_rates("gemini-3.5-flash-preview")
    assert rates.source == "default"
    assert rates.input == 0.075
    assert rates.output == 0.300

    rates_25 = get_model_rates("gemini-2.5-flash-extra")
    assert rates_25.source == "default"


def test_fallback_warning_logged_once(caplog):
    """Tracer logs a warning on fallback exactly once per model."""
    unique_model = "model-for-warning-test-999"
    _WARNED_FALLBACK_MODELS.discard(unique_model)

    with caplog.at_level(logging.WARNING, logger="src.audit.tracer"):
        # First lookup: warning logged
        r1 = get_model_rates(unique_model)
        assert r1.source == "default"
        matching_logs = [rec for rec in caplog.records if unique_model in rec.message]
        assert len(matching_logs) == 1
        assert "falling back to default rates" in matching_logs[0].message

        # Second lookup: warning is NOT logged again
        r2 = get_model_rates(unique_model)
        assert r2.source == "default"
        matching_logs_after = [rec for rec in caplog.records if unique_model in rec.message]
        assert len(matching_logs_after) == 1


def test_cached_tokens_applied_only_if_reported():
    """cached_input rate applies only when the response reports cached tokens > 0."""
    # When tokens_cached is None: regular input rate ($0.30 / 1M)
    cost_none = estimate_cost("gemini-3.5-flash-lite", 1_000_000, 1_000_000, tokens_cached=None)
    assert cost_none == 2.80

    # When tokens_cached is 0: regular input rate ($0.30 / 1M)
    cost_zero = estimate_cost("gemini-3.5-flash-lite", 1_000_000, 1_000_000, tokens_cached=0)
    assert cost_zero == 2.80

    # When tokens_cached > 0 (500k cached @ $0.03/1M, 500k uncached @ $0.30/1M, 1M out @ $2.50/1M):
    # uncached in: $0.15, cached in: $0.015, out: $2.50 => total: $2.665
    cost_cached = estimate_cost("gemini-3.5-flash-lite", 1_000_000, 1_000_000, tokens_cached=500_000)
    assert cost_cached == 2.665

    # Gemini 3.5 Flash: 1M in (all cached @ $0.15/1M), 500k out ($9.00 * 0.5 = $4.50)
    # total: $4.65
    cost_flash_cached = estimate_cost("gemini-3.5-flash", 1_000_000, 500_000, tokens_cached=1_000_000)
    assert cost_flash_cached == 4.65


def test_shared_pricing_lookup_across_modules():
    """eval/policy_e2e.py and src/audit/langfuse_export.py use the exact same lookup."""
    # 1. Exact function identities
    assert e2e_estimate is estimate_cost
    assert lf_estimate is estimate_cost
    assert e2e_rates is get_model_rates
    assert lf_rates is get_model_rates
    assert e2e_rate_source is get_rate_source
    assert lf_rate_source is get_rate_source

    # 2. Consistent outputs for exact match
    c_tracer = estimate_cost("gemini-3.5-flash-lite", 10_000, 2_000)
    c_e2e = e2e_estimate("gemini-3.5-flash-lite", 10_000, 2_000)
    c_lf = lf_estimate("gemini-3.5-flash-lite", 10_000, 2_000)
    assert c_tracer == c_e2e == c_lf

    # 3. Consistent outputs for fallback
    c_tracer_fb = estimate_cost("unlisted-shared-model", 10_000, 2_000)
    c_e2e_fb = e2e_estimate("unlisted-shared-model", 10_000, 2_000)
    c_lf_fb = lf_estimate("unlisted-shared-model", 10_000, 2_000)
    assert c_tracer_fb == c_e2e_fb == c_lf_fb
