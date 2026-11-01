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
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
TRACES_DIR = REPO_ROOT / "traces"
PRICING_FILE = REPO_ROOT / "eval" / "pricing.yaml"

MAX_CONTENT_CHARS = 10000
TRUNCATION_MARKER = "\n... [TRUNCATED] ..."

_PRICING_CACHE: Optional[Dict[str, Any]] = None


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


def get_model_rates(model_name: str) -> Tuple[float, float, str]:
    """Return (cost_per_million_input, cost_per_million_output, rate_source)."""
    cfg = get_pricing_config()
    models = cfg.get("models", {})
    clean_name = (model_name or "").lower().strip()
    if ":" in clean_name:
        clean_name = clean_name.split(":")[-1]
    if clean_name.startswith("models/"):
        clean_name = clean_name[len("models/"):]

    # 1. Exact match in models dict
    if clean_name in models:
        m = models[clean_name]
        return (
            float(m.get("cost_per_million_input_tokens", 0.075)),
            float(m.get("cost_per_million_output_tokens", 0.300)),
            f"eval/pricing.yaml:{clean_name}",
        )

    # 2. Substring / prefix match in models dict
    for k, m in models.items():
        if k != "default" and (k in clean_name or clean_name in k):
            return (
                float(m.get("cost_per_million_input_tokens", 0.075)),
                float(m.get("cost_per_million_output_tokens", 0.300)),
                f"eval/pricing.yaml:{k}",
            )

    # 3. Fallback to default in pricing.yaml
    if "default" in models:
        m = models["default"]
        return (
            float(m.get("cost_per_million_input_tokens", 0.075)),
            float(m.get("cost_per_million_output_tokens", 0.300)),
            "eval/pricing.yaml:default",
        )

    return (0.075, 0.300, "fallback:default")


def get_rate_source(model_name: str) -> str:
    """Return the rate source string for a model."""
    _, _, source = get_model_rates(model_name)
    return source


def estimate_cost(model_name: str, tokens_in: Optional[int], tokens_out: Optional[int]) -> Optional[float]:
    """Compute estimated USD cost based on eval/pricing.yaml rates."""
    if tokens_in is None or tokens_out is None:
        return None
    rate_in, rate_out, _ = get_model_rates(model_name)
    return round((tokens_in * (rate_in / 1_000_000.0)) + (tokens_out * (rate_out / 1_000_000.0)), 6)


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
                cost = None
                rate_src = get_rate_source(model_name)
            else:
                actual_has_usage = True if has_usage is None else has_usage
                actual_tokens_in = tokens_in
                actual_tokens_out = tokens_out
                cost = estimate_cost(model_name, tokens_in, tokens_out)
                rate_src = get_rate_source(model_name)
        else:
            actual_has_usage = True if has_usage is None else has_usage
            actual_tokens_in = 0 if tokens_in is None else tokens_in
            actual_tokens_out = 0 if tokens_out is None else tokens_out
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
        prompt: Optional[str] = None,
        response: Optional[str] = None,
    ) -> None:
        """Receive LLM usage directly from LLMGateway for every LLM request."""
        cost = estimate_cost(model, tokens_in, tokens_out)
        self.llm_calls.append({
            "model": model,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
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
