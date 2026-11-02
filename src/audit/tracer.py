"""Structured step-by-step audit tracing engine.

Emits traces/<run_id>.jsonl containing structured execution records for every
pipeline milestone (transcribe, diarize, quality_gate, topic, sop_check, policy_retrieval, policy_check, scoring, report).
Records model vs plain code decisions, latencies, real token consumption from usage_metadata,
exact costs from eval/pricing.yaml, sanitized prompt/response content, and test/eval isolation.
"""
from __future__ import annotations

import json
import logging
import os
import re
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
TRACES_DIR = REPO_ROOT / "traces"
PRICING_FILE = REPO_ROOT / "eval" / "pricing.yaml"

MAX_CONTENT_CHARS = 10000
TRUNCATION_MARKER = "\n... [TRUNCATED] ..."

_PRICING_CACHE: Optional[Dict[str, Any]] = None
_WARNED_FALLBACK_MODELS: Set[str] = set()


class DefaultRateSource(str):
    """String representing 'default' rate source, backward-compatible with substring checks."""

    def __eq__(self, other: object) -> bool:
        return str(self) == other or other in ("default", "pricing.yaml:default", "eval/pricing.yaml:default")

    def __contains__(self, item: object) -> bool:
        if item in ("default", "pricing.yaml:default", "eval/pricing.yaml:default"):
            return True
        return super().__contains__(str(item))


class ModelRates(tuple):
    """3-tuple (cost_per_million_input, cost_per_million_output, rate_source) with cached_input."""

    def __new__(cls, input_rate: float, output_rate: float, source: str, cached_input: float = 0.0):
        return super().__new__(cls, (input_rate, output_rate, source))

    def __init__(self, input_rate: float, output_rate: float, source: str, cached_input: float = 0.0):
        self.input = input_rate
        self.output = output_rate
        self.source = source
        self.cached_input = cached_input
        self.rate_source = source


def _normalize_model_name(model_name: str) -> str:
    clean = (model_name or "").lower().strip()
    if ":" in clean:
        clean = clean.split(":")[-1]
    if clean.startswith("models/"):
        clean = clean[len("models/"):]
    return clean


# --------------------------------------------------------------------------------------
# Pricing from eval/pricing.yaml
# --------------------------------------------------------------------------------------
def get_pricing_config() -> Dict[str, Any]:
    global _PRICING_CACHE
    if _PRICING_CACHE is None:
        if PRICING_FILE.exists():
            import yaml
            try:
                _PRICING_CACHE = yaml.safe_load(PRICING_FILE.read_text(encoding="utf-8")) or {}
            except Exception as e:
                logger.warning("Failed to load eval/pricing.yaml: %s", e)
                _PRICING_CACHE = {}
        else:
            _PRICING_CACHE = {}
    return _PRICING_CACHE


def get_model_rates(model_name: str) -> ModelRates:
    """Return ModelRates(cost_per_million_input, cost_per_million_output, rate_source, cached_input).

    Looks up the exact model name first in eval/pricing.yaml.
    If there is no exact entry, falls back to default rates, sets rate_source='default',
    and logs a warning once per model.
    """
    cfg = get_pricing_config()
    models = cfg.get("models", {})
    raw_name = (model_name or "").strip()
    clean_name = _normalize_model_name(raw_name)

    # 1. Exact match (clean name or raw name)
    matched_key = None
    if clean_name in models and clean_name != "default":
        matched_key = clean_name
    elif raw_name.lower() in models and raw_name.lower() != "default":
        matched_key = raw_name.lower()

    if matched_key is not None:
        m = models[matched_key]
        cached_rate = float(
            m.get("cost_per_million_cached_input_tokens", m.get("cached_input", 0.0))
        )
        return ModelRates(
            float(m.get("cost_per_million_input_tokens", 0.075)),
            float(m.get("cost_per_million_output_tokens", 0.300)),
            f"eval/pricing.yaml:{matched_key}",
            cached_rate,
        )

    # 2. Fallback to default only if there is no entry (no substring / prefix guessing)
    warn_key = clean_name or raw_name or "unknown"
    if warn_key not in _WARNED_FALLBACK_MODELS:
        _WARNED_FALLBACK_MODELS.add(warn_key)
        logger.warning(
            "Pricing model '%s' has no exact entry in eval/pricing.yaml; falling back to default rates",
            raw_name or model_name,
        )

    def_m = models.get("default", {})
    def_cached = float(
        def_m.get("cost_per_million_cached_input_tokens", def_m.get("cached_input", 0.0))
    )
    return ModelRates(
        float(def_m.get("cost_per_million_input_tokens", 0.075)),
        float(def_m.get("cost_per_million_output_tokens", 0.300)),
        DefaultRateSource("default"),
        def_cached,
    )


def get_rate_source(model_name: str) -> str:
    """Return the rate source string for a model."""
    rates = get_model_rates(model_name)
    return rates.source


def estimate_cost(
    model_name: str,
    tokens_in: Optional[int],
    tokens_out: Optional[int],
    tokens_cached: Optional[int] = None,
    cached_tokens: Optional[int] = None,
) -> Optional[float]:
    """Compute estimated USD cost based on eval/pricing.yaml rates.

    Do not apply cached_input unless the response reports cached tokens.
    """
    if tokens_in is None or tokens_out is None:
        return None

    rates = get_model_rates(model_name)
    rate_in = rates.input
    rate_out = rates.output
    rate_cached = rates.cached_input

    cached = tokens_cached if tokens_cached is not None else cached_tokens
    if cached is not None and cached > 0:
        actual_cached = min(tokens_in, cached)
        uncached_in = max(0, tokens_in - actual_cached)
        cost = (
            (uncached_in * (rate_in / 1_000_000.0))
            + (actual_cached * (rate_cached / 1_000_000.0))
            + (tokens_out * (rate_out / 1_000_000.0))
        )
    else:
        cost = (tokens_in * (rate_in / 1_000_000.0)) + (tokens_out * (rate_out / 1_000_000.0))

    return round(cost, 6)


# --------------------------------------------------------------------------------------
# Content Sanitization (PII Masking & Size Cap)
# --------------------------------------------------------------------------------------
def mask_pii(text: Optional[str]) -> Optional[str]:
    """Mask email addresses and phone numbers before storing in traces."""
    if not text:
        return text
    # Mask email addresses
    masked = re.sub(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", "[EMAIL_MASKED]", text)
    # Mask international / Indian phone numbers (+91...) or standard 10-digit phone numbers
    masked = re.sub(r"(?:\+?91[-.\s]?)?[6-9]\d{9}\b", "[PHONE_MASKED]", masked)
    # Mask toll-free or formatted phones like 1800-XXX-XXXX or (XXX) XXX-XXXX
    masked = re.sub(r"\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{3,4}\)?[-.\s]?\d{3,4}[-.\s]?\d{3,4}\b", "[PHONE_MASKED]", masked)
    return masked


def truncate_content(text: Optional[str], max_chars: int = MAX_CONTENT_CHARS) -> Optional[str]:
    """Enforce size cap with truncation marker."""
    if not text or len(text) <= max_chars:
        return text
    keep = max(0, max_chars - len(TRUNCATION_MARKER))
    return text[:keep] + TRUNCATION_MARKER


def sanitize_content(text: Optional[str], max_chars: int = MAX_CONTENT_CHARS) -> Optional[str]:
    """Mask PII and apply size cap."""
    if not text:
        return text
    return truncate_content(mask_pii(text), max_chars=max_chars)


# --------------------------------------------------------------------------------------
# Trace Source Detection (Test / Eval Isolation)
# --------------------------------------------------------------------------------------
def _detect_source() -> str:
    """Detect whether this execution is from test, eval, or production."""
    env_src = os.environ.get("TRACE_SOURCE", "").strip().lower()
    if env_src in ("test", "eval", "prod", "live"):
        return env_src
    if "PYTEST_CURRENT_TEST" in os.environ or "pytest" in sys.modules:
        return "test"
    main_cmd = " ".join(sys.argv).lower() if sys.argv else ""
    if "eval/" in main_cmd or "eval_" in main_cmd or "eval\\" in main_cmd:
        return "eval"
    return "prod"


@dataclass
class TraceStep:
    step_name: str
    decision_type: str  # "model" or "plain_code"
    status: str = "ok"  # "ok", "degraded", "handoff", "failed", "skipped"
    inputs_summary: str = ""
    outputs_summary: str = ""
    start_time: str = ""
    end_time: str = ""
    latency_seconds: float = 0.0
    duration: float = 0.0
    model_name: str = "none"
    rate_source: str = ""
    tokens_in: Optional[int] = 0
    tokens_out: Optional[int] = 0
    tokens_cached: Optional[int] = 0
    request_count: int = 0
    estimated_cost_usd: Optional[float] = 0.0
    cost_usd: Optional[float] = 0.0
    has_usage: bool = True
    usage_estimated: bool = False  # NEVER True: never guess
    prompt: Optional[str] = None
    response: Optional[str] = None
    source: str = "prod"
    error_text: str = ""
    error: str = ""


class AuditTracer:
    def __init__(self, run_id: Optional[str] = None, traces_dir: Optional[Path] = None, source: Optional[str] = None):
        self.source = source or _detect_source()
        self.run_id = run_id or f"trace_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{int(time.time()*1000)%100000}"
        self.traces_dir = traces_dir or TRACES_DIR
        self.traces_dir.mkdir(parents=True, exist_ok=True)
        self.trace_file = self.traces_dir / f"{self.run_id}.jsonl"
        self.steps: List[TraceStep] = []
        self.llm_calls: List[dict] = []

    def record_step(
        self,
        step_name: str,
        decision_type: str,
        status: str = "ok",
        inputs_summary: str = "",
        outputs_summary: str = "",
        start_t: float = 0.0,
        end_t: float = 0.0,
        model_name: str = "none",
        tokens_in: Optional[int] = None,
        tokens_out: Optional[int] = None,
        tokens_cached: Optional[int] = None,
        request_count: int = 0,
        error_text: str = "",
        prompt: Optional[str] = None,
        response: Optional[str] = None,
        has_usage: Optional[bool] = None,
        max_content_chars: int = MAX_CONTENT_CHARS,
    ) -> TraceStep:
        lat = round(max(0.0, end_t - start_t), 3) if (start_t and end_t) else 0.0

        if decision_type == "model":
            if tokens_in is None or tokens_out is None:
                actual_has_usage = False if has_usage is None else has_usage
                actual_tokens_in = None
                actual_tokens_out = None
                actual_tokens_cached = None
                cost = None
                rate_src = get_rate_source(model_name)
            else:
                actual_has_usage = True if has_usage is None else has_usage
                actual_tokens_in = tokens_in
                actual_tokens_out = tokens_out
                actual_tokens_cached = tokens_cached
                cost = estimate_cost(model_name, tokens_in, tokens_out, tokens_cached=tokens_cached)
                rate_src = get_rate_source(model_name)
        else:
            actual_has_usage = True if has_usage is None else has_usage
            actual_tokens_in = 0 if tokens_in is None else tokens_in
            actual_tokens_out = 0 if tokens_out is None else tokens_out
            actual_tokens_cached = 0 if tokens_cached is None else tokens_cached
            cost = 0.0
            rate_src = "none"

        sanitized_prompt = sanitize_content(prompt, max_chars=max_content_chars)
        sanitized_resp = sanitize_content(response, max_chars=max_content_chars)

        step = TraceStep(
            step_name=step_name,
            decision_type=decision_type,
            status=status,
            inputs_summary=inputs_summary[:200],
            outputs_summary=outputs_summary[:200],
            start_time=datetime.fromtimestamp(start_t or time.time()).isoformat(timespec="milliseconds"),
            end_time=datetime.fromtimestamp(end_t or time.time()).isoformat(timespec="milliseconds"),
            latency_seconds=lat,
            duration=lat,
            model_name=model_name,
            rate_source=rate_src,
            tokens_in=actual_tokens_in,
            tokens_out=actual_tokens_out,
            tokens_cached=actual_tokens_cached,
            request_count=request_count,
            estimated_cost_usd=cost,
            cost_usd=cost,
            has_usage=actual_has_usage,
            usage_estimated=False,  # never guess
            prompt=sanitized_prompt,
            response=sanitized_resp,
            source=self.source,
            error_text=error_text,
            error=error_text,
        )
        self.steps.append(step)
        with open(self.trace_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(step), ensure_ascii=False) + "\n")
        return step

    def record_llm_call(
        self,
        model: str,
        tokens_in: Optional[int],
        tokens_out: Optional[int],
        tokens_cached: Optional[int] = None,
        prompt: Optional[str] = None,
        response: Optional[str] = None,
    ) -> None:
        """Receive LLM usage directly from LLMGateway for every LLM request."""
        cost = estimate_cost(model, tokens_in, tokens_out, tokens_cached=tokens_cached)
        self.llm_calls.append({
            "model": model,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "tokens_cached": tokens_cached,
            "has_usage": tokens_in is not None and tokens_out is not None,
            "cost_usd": cost,
            "rate_source": get_rate_source(model),
            "prompt": sanitize_content(prompt),
            "response": sanitize_content(response),
            "timestamp": datetime.now().isoformat(timespec="milliseconds"),
        })

    def get_summary(self) -> Dict[str, Any]:
        valid_in = [s.tokens_in for s in self.steps if s.tokens_in is not None]
        valid_out = [s.tokens_out for s in self.steps if s.tokens_out is not None]
        valid_cost = [s.estimated_cost_usd for s in self.steps if s.estimated_cost_usd is not None]
        return {
            "run_id": self.run_id,
            "source": self.source,
            "total_steps": len(self.steps),
            "total_latency_seconds": round(sum(s.latency_seconds for s in self.steps), 2),
            "total_tokens_in": sum(valid_in) if valid_in else 0,
            "total_tokens_out": sum(valid_out) if valid_out else 0,
            "total_requests": sum(s.request_count for s in self.steps),
            "total_cost_usd": round(sum(valid_cost), 6) if valid_cost else 0.0,
            "statuses": [s.status for s in self.steps],
            "has_all_usage": all(s.has_usage for s in self.steps if s.decision_type == "model"),
        }


def load_traces(
    traces_dir: Optional[Path] = None,
    include_test: bool = False,
    include_eval: bool = False,
    source: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Load all completed trace logs from disk, isolating test and eval runs by default."""
    tdir = traces_dir or TRACES_DIR
    records = []
    if not tdir.exists():
        return records
    for p in sorted(tdir.glob("*.jsonl"), reverse=True):
        steps = []
        try:
            for line in p.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line:
                    try:
                        steps.append(json.loads(line))
                    except Exception:
                        pass
        except Exception:
            continue
        if not steps:
            continue

        trace_source = steps[0].get("source", "prod")
        if source is not None and source != "all":
            if trace_source != source:
                continue
        elif source != "all":
            if not include_test and trace_source == "test":
                continue
            if not include_eval and trace_source == "eval":
                continue

        valid_in = [s.get("tokens_in") for s in steps if s.get("tokens_in") is not None]
        valid_out = [s.get("tokens_out") for s in steps if s.get("tokens_out") is not None]
        valid_cost = [s.get("estimated_cost_usd") for s in steps if s.get("estimated_cost_usd") is not None]

        records.append({
            "run_id": p.stem,
            "file": str(p),
            "source": trace_source,
            "steps": steps,
            "timestamp": steps[0].get("start_time", ""),
            "status": "failed" if any(s.get("status") == "failed" for s in steps) else ("degraded" if any(s.get("status") == "degraded" for s in steps) else "ok"),
            "total_latency": round(sum(s.get("latency_seconds", 0.0) for s in steps), 2),
            "total_cost": round(sum(valid_cost), 6) if valid_cost else 0.0,
            "total_tokens_in": sum(valid_in) if valid_in else 0,
            "total_tokens_out": sum(valid_out) if valid_out else 0,
            "total_requests": sum(s.get("request_count", 0) for s in steps),
        })
    return records
