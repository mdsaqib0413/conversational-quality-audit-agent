"""Structured step-by-step audit tracing engine.

Emits traces/<run_id>.jsonl containing structured execution records for every
pipeline milestone (ingestion, quality gate, call_state, judging, policy, scoring).
Records model vs plain code decisions, latencies, token consumption, and cost estimates.
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
TRACES_DIR = REPO_ROOT / "traces"


def estimate_cost(model_name: str, tokens_in: int, tokens_out: int) -> float:
    """Compute estimated USD cost based on eval/pricing.yaml rates."""
    # Standard rates (Gemini 1.5 Flash default: $0.075 / 1M in, $0.300 / 1M out)
    rate_in = 0.075 / 1_000_000.0
    rate_out = 0.300 / 1_000_000.0
    if "pro" in model_name.lower():
        rate_in = 1.250 / 1_000_000.0
        rate_out = 5.000 / 1_000_000.0
    elif "2.0" in model_name.lower():
        rate_in = 0.100 / 1_000_000.0
        rate_out = 0.400 / 1_000_000.0
    return round((tokens_in * rate_in) + (tokens_out * rate_out), 6)


@dataclass
class TraceStep:
    step_name: str
    decision_type: str  # "model" or "plain_code"
    status: str = "ok"  # "ok", "degraded", "handoff", "failed"
    inputs_summary: str = ""
    outputs_summary: str = ""
    start_time: str = ""
    end_time: str = ""
    latency_seconds: float = 0.0
    model_name: str = "none"
    tokens_in: int = 0
    tokens_out: int = 0
    request_count: int = 0
    estimated_cost_usd: float = 0.0
    error_text: str = ""


class AuditTracer:
    def __init__(self, run_id: Optional[str] = None, traces_dir: Optional[Path] = None):
        self.run_id = run_id or f"trace_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{int(time.time()*1000)%100000}"
        self.traces_dir = traces_dir or TRACES_DIR
        self.traces_dir.mkdir(parents=True, exist_ok=True)
        self.trace_file = self.traces_dir / f"{self.run_id}.jsonl"
        self.steps: List[TraceStep] = []

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
        tokens_in: int = 0,
        tokens_out: int = 0,
        request_count: int = 0,
        error_text: str = "",
    ) -> TraceStep:
        lat = round(max(0.0, end_t - start_t), 3) if (start_t and end_t) else 0.0
        cost = estimate_cost(model_name, tokens_in, tokens_out) if decision_type == "model" else 0.0
        step = TraceStep(
            step_name=step_name,
            decision_type=decision_type,
            status=status,
            inputs_summary=inputs_summary[:200],
            outputs_summary=outputs_summary[:200],
            start_time=datetime.fromtimestamp(start_t or time.time()).isoformat(timespec="milliseconds"),
            end_time=datetime.fromtimestamp(end_t or time.time()).isoformat(timespec="milliseconds"),
            latency_seconds=lat,
            model_name=model_name,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            request_count=request_count,
            estimated_cost_usd=cost,
            error_text=error_text,
        )
        self.steps.append(step)
        # Append line directly to jsonl
        with open(self.trace_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(step), ensure_ascii=False) + "\n")
        return step

    def get_summary(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "total_steps": len(self.steps),
            "total_latency_seconds": round(sum(s.latency_seconds for s in self.steps), 2),
            "total_tokens_in": sum(s.tokens_in for s in self.steps),
            "total_tokens_out": sum(s.tokens_out for s in self.steps),
            "total_requests": sum(s.request_count for s in self.steps),
            "total_cost_usd": round(sum(s.estimated_cost_usd for s in self.steps), 6),
            "statuses": [s.status for s in self.steps],
        }


def load_traces(traces_dir: Optional[Path] = None) -> List[Dict[str, Any]]:
    """Load all completed trace logs from disk."""
    tdir = traces_dir or TRACES_DIR
    records = []
    if not tdir.exists():
        return records
    for p in sorted(tdir.glob("*.jsonl"), reverse=True):
        steps = []
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                try:
                    steps.append(json.loads(line))
                except Exception:
                    pass
        if steps:
            records.append({
                "run_id": p.stem,
                "file": str(p),
                "steps": steps,
                "timestamp": steps[0].get("start_time", ""),
                "status": "failed" if any(s.get("status") == "failed" for s in steps) else ("degraded" if any(s.get("status") == "degraded" for s in steps) else "ok"),
                "total_latency": round(sum(s.get("latency_seconds", 0.0) for s in steps), 2),
                "total_cost": round(sum(s.get("estimated_cost_usd", 0.0) for s in steps), 6),
                "total_requests": sum(s.get("request_count", 0) for s in steps),
            })
    return records

