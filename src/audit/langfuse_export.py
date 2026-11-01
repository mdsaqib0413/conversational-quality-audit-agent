"""Optional Langfuse observability exporter for conversational quality audits.

Exports structured execution traces to Langfuse when explicitly configured via
LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, and LANGFUSE_HOST.
The local disk tracer (traces/<run_id>.jsonl) remains the primary source of truth.

SDK Version Target:
- Targets Langfuse SDK v2 (langfuse>=2.0.0,<3.0.0) stateful tracing methods:
  Langfuse(public_key, secret_key, host), client.trace(), trace.span(),
  trace.generation(), trace.score(), and client.flush().

Safety & Privacy:
- Never interrupts audits: all exceptions are caught, logged, and swallowed.
- LANGFUSE_CAPTURE_CONTENT=0 (default, blank string means 0): exports only metadata
  (step names, durations, token counts, costs, models, scores, and call id). Prompts,
  responses, and transcript text are completely excluded.
- LANGFUSE_CAPTURE_CONTENT=1: exports prompt/response text with PII masking (email and phone).
  NOTE: Strictly intended for synthetic sample data only, as masking covers email and phone only.
- Test/eval isolation: traces with source in ('test', 'eval') are skipped unless
  LANGFUSE_EXPORT_EVAL=1 is explicitly set (blank string means 0).
- Flush timeout: client.flush() is wrapped in a bounded background thread with a short timeout
  so slow or unreachable Langfuse endpoints never block audits for more than a few seconds.
"""
from __future__ import annotations

import logging
import os
import sys
import threading
from datetime import datetime
from typing import Any, Dict, List, Optional

from src.audit.schemas import AuditReport
from src.audit.tracer import TRACES_DIR, AuditTracer, mask_pii

logger = logging.getLogger(__name__)

DEFAULT_FLUSH_TIMEOUT_SECONDS = 3.0


def is_langfuse_enabled() -> bool:
    """Return True if all required Langfuse credentials are set and non-empty."""
    pk = os.environ.get("LANGFUSE_PUBLIC_KEY", "").strip()
    sk = os.environ.get("LANGFUSE_SECRET_KEY", "").strip()
    host = os.environ.get("LANGFUSE_HOST", "").strip()
    return bool(pk and sk and host)


def is_capture_content_enabled() -> bool:
    """Return True if content capture (prompts/responses) is enabled (default 0 = False).

    A blank string (e.g. LANGFUSE_CAPTURE_CONTENT= in .env.example) or unset value means 0.
    """
    raw = os.environ.get("LANGFUSE_CAPTURE_CONTENT")
    if raw is None or not raw.strip():
        return False
    val = raw.strip().lower()
    return val in ("1", "true", "yes", "on")


def is_export_eval_enabled() -> bool:
    """Return True if test/eval runs should be exported to Langfuse (default 0 = False).

    A blank string (e.g. LANGFUSE_EXPORT_EVAL= in .env.example) or unset value means 0.
    """
    raw = os.environ.get("LANGFUSE_EXPORT_EVAL")
    if raw is None or not raw.strip():
        return False
    val = raw.strip().lower()
    return val in ("1", "true", "yes", "on")


def get_langfuse_client(timeout: float = DEFAULT_FLUSH_TIMEOUT_SECONDS) -> Optional[Any]:
    """Instantiate and return the Langfuse client if configured and available."""
    if not is_langfuse_enabled():
        return None
    try:
        from langfuse import Langfuse

        pk = os.environ.get("LANGFUSE_PUBLIC_KEY", "").strip()
        sk = os.environ.get("LANGFUSE_SECRET_KEY", "").strip()
        host = os.environ.get("LANGFUSE_HOST", "").strip()
        try:
            return Langfuse(public_key=pk, secret_key=sk, host=host, timeout=timeout)
        except TypeError:
            return Langfuse(public_key=pk, secret_key=sk, host=host)
    except Exception as exc:
        logger.warning("Could not initialize Langfuse client: %s", exc)
        return None


def _parse_time(t: Any) -> Optional[datetime]:
    if isinstance(t, datetime):
        return t
    if isinstance(t, str) and t.strip():
        try:
            return datetime.fromisoformat(t.strip())
        except Exception:
            return None
    return None


def _safe_flush(client: Any, timeout: float = DEFAULT_FLUSH_TIMEOUT_SECONDS) -> None:
    """Flush the Langfuse client with a strict timeout.

    Ensures a slow, hanging, or unreachable Langfuse endpoint never delays
    an audit by more than a few seconds.
    """
    if not hasattr(client, "flush"):
        return

    exc_holder: List[Exception] = []

    def _do_flush() -> None:
        try:
            import inspect

            sig = inspect.signature(client.flush)
            if "timeout" in sig.parameters:
                client.flush(timeout=timeout)
            else:
                client.flush()
        except TypeError:
            try:
                client.flush()
            except Exception as e:
                exc_holder.append(e)
        except Exception as e:
            exc_holder.append(e)

    flush_thread = threading.Thread(target=_do_flush, daemon=True)
    flush_thread.start()
    flush_thread.join(timeout=timeout)

    if flush_thread.is_alive():
        logger.warning(
            "Langfuse client.flush() timed out after %.1fs; continuing audit without waiting",
            timeout,
        )
    elif exc_holder:
        logger.warning("Langfuse client.flush() failed: %s", exc_holder[0])


def _determine_source(report: AuditReport, tracer: Optional[AuditTracer]) -> str:
    if tracer and hasattr(tracer, "source") and tracer.source:
        return str(tracer.source).lower()
    if hasattr(report, "meta"):
        if hasattr(report.meta, "source") and getattr(report.meta, "source"):
            return str(report.meta.source).lower()
        if hasattr(report.meta, "source_set") and getattr(report.meta, "source_set"):
            src = str(report.meta.source_set).lower()
            if src in ("test", "eval"):
                return src
    env_src = os.environ.get("TRACE_SOURCE", "").strip().lower()
    if env_src in ("test", "eval", "prod", "live"):
        return env_src
    if "PYTEST_CURRENT_TEST" in os.environ or "pytest" in sys.modules:
        return "test"
    main_cmd = " ".join(sys.argv).lower() if sys.argv else ""
    if "eval/" in main_cmd or "eval_" in main_cmd or "eval\\" in main_cmd:
        return "eval"
    return "prod"


def _load_steps_from_disk(trace_id: str) -> List[Dict[str, Any]]:
    path = TRACES_DIR / f"{trace_id}.jsonl"
    if not path.exists():
        return []
    steps = []
    try:
        import json

        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                try:
                    steps.append(json.loads(line))
                except Exception:
                    pass
    except Exception as e:
        logger.debug("Failed reading trace file %s: %s", path, e)
    return steps


def export_audit_to_langfuse(
    report: AuditReport,
    tracer: Optional[AuditTracer] = None,
    client: Optional[Any] = None,
    flush_timeout: float = DEFAULT_FLUSH_TIMEOUT_SECONDS,
) -> bool:
    """Export an AuditReport and its step traces to Langfuse.

    Returns True if export succeeded, False if skipped or failed.
    Never raises an exception; all errors are logged and swallowed.
    A short flush timeout guarantees slow/unreachable endpoints do not delay audits.
    """
    try:
        if client is None:
            if not is_langfuse_enabled():
                return False
            client = get_langfuse_client(timeout=flush_timeout)
            if client is None:
                return False

        source = _determine_source(report, tracer)
        if source in ("test", "eval") and not is_export_eval_enabled():
            logger.debug(
                "Skipping Langfuse export for call %s (source=%s, LANGFUSE_EXPORT_EVAL=0)",
                report.call_id,
                source,
            )
            return False

        capture_content = is_capture_content_enabled()

        # Build trace metadata
        trace_id = getattr(report.meta, "trace_id", None) or (tracer.run_id if tracer else f"audit_{report.call_id}")
        trace_name = f"audit_{report.call_id}"

        overall_score = float(getattr(report.scores, "overall", 0.0)) if hasattr(report, "scores") else 0.0
        grade = str(getattr(report.scores, "grade", "")) if hasattr(report, "scores") else ""
        topic = str(getattr(report, "topic", ""))
        status = str(getattr(report, "status", "ok"))

        meta_dict: Dict[str, Any] = {
            "call_id": report.call_id,
            "topic": topic,
            "grade": grade,
            "overall_score": overall_score,
            "sop_score": float(getattr(report.scores, "sop_score", 0.0)) if hasattr(report, "scores") else 0.0,
            "policy_score": float(getattr(report.scores, "policy_score", 0.0)) if hasattr(report, "scores") else 0.0,
            "status": status,
            "source": source,
            "content_captured": capture_content,
        }
        if hasattr(report, "meta"):
            if getattr(report.meta, "model", None):
                meta_dict["model"] = report.meta.model
            if getattr(report.meta, "tokens_in", None) is not None:
                meta_dict["tokens_in"] = report.meta.tokens_in
            if getattr(report.meta, "tokens_out", None) is not None:
                meta_dict["tokens_out"] = report.meta.tokens_out
            if getattr(report.meta, "estimated_cost_usd", None) is not None:
                meta_dict["estimated_cost_usd"] = report.meta.estimated_cost_usd
            if getattr(report.meta, "audit_seconds", None) is not None:
                meta_dict["audit_seconds"] = report.meta.audit_seconds

        trace_input = None
        trace_output = None
        if capture_content:
            raw_input = getattr(report, "customer_issue", "") or f"Audit of call {report.call_id}"
            raw_output = getattr(report, "summary", "") or f"Grade: {grade}, Overall: {overall_score:.1f}"
            trace_input = mask_pii(raw_input)
            trace_output = mask_pii(raw_output)

        # Create trace on Langfuse
        trace = client.trace(
            id=trace_id,
            name=trace_name,
            input=trace_input,
            output=trace_output,
            metadata=meta_dict,
            tags=[source, f"grade_{grade}" if grade else "grade_none", topic or "general"],
        )

        # Record final score as a trace score
        if hasattr(trace, "score"):
            trace.score(
                name="overall_score",
                value=overall_score,
                comment=f"Grade: {grade}" if grade else None,
            )
        elif hasattr(client, "score"):
            client.score(
                trace_id=trace_id,
                name="overall_score",
                value=overall_score,
                comment=f"Grade: {grade}" if grade else None,
            )

        # Gather steps from tracer or disk
        raw_steps: List[Any] = []
        if tracer and getattr(tracer, "steps", None):
            raw_steps = list(tracer.steps)
        elif trace_id:
            raw_steps = _load_steps_from_disk(trace_id)

        for s in raw_steps:
            s_name = getattr(s, "step_name", None) or (s.get("step_name") if isinstance(s, dict) else "unknown_step")
            s_type = getattr(s, "decision_type", None) or (s.get("decision_type", "plain_code") if isinstance(s, dict) else "plain_code")
            s_status = getattr(s, "status", None) or (s.get("status", "ok") if isinstance(s, dict) else "ok")
            s_model = getattr(s, "model_name", None) or (s.get("model_name", "none") if isinstance(s, dict) else "none")
            s_rate_src = getattr(s, "rate_source", None) or (s.get("rate_source", "") if isinstance(s, dict) else "")
            s_tokens_in = getattr(s, "tokens_in", None) if not isinstance(s, dict) else s.get("tokens_in")
            s_tokens_out = getattr(s, "tokens_out", None) if not isinstance(s, dict) else s.get("tokens_out")
            s_cost = getattr(s, "estimated_cost_usd", None) if not isinstance(s, dict) else s.get("estimated_cost_usd")
            s_lat = getattr(s, "latency_seconds", None) if not isinstance(s, dict) else s.get("latency_seconds", 0.0)
            s_start = getattr(s, "start_time", None) or (s.get("start_time", "") if isinstance(s, dict) else "")
            s_end = getattr(s, "end_time", None) or (s.get("end_time", "") if isinstance(s, dict) else "")
            s_prompt = getattr(s, "prompt", None) or (s.get("prompt") if isinstance(s, dict) else None)
            s_resp = getattr(s, "response", None) or (s.get("response") if isinstance(s, dict) else None)
            s_in_sum = getattr(s, "inputs_summary", None) or (s.get("inputs_summary", "") if isinstance(s, dict) else "")
            s_out_sum = getattr(s, "outputs_summary", None) or (s.get("outputs_summary", "") if isinstance(s, dict) else "")

            step_meta: Dict[str, Any] = {
                "status": s_status,
                "latency_seconds": s_lat or 0.0,
                "decision_type": s_type,
            }
            if s_cost is not None:
                step_meta["cost_usd"] = s_cost
            if s_rate_src:
                step_meta["rate_source"] = s_rate_src

            step_in = None
            step_out = None
            if capture_content:
                if s_prompt:
                    step_in = mask_pii(s_prompt)
                elif s_in_sum:
                    step_in = mask_pii(s_in_sum)

                if s_resp:
                    step_out = mask_pii(s_resp)
                elif s_out_sum:
                    step_out = mask_pii(s_out_sum)

            if s_type == "model" and hasattr(trace, "generation"):
                usage_val = None
                if s_tokens_in is not None or s_tokens_out is not None:
                    usage_val = {
                        "input": s_tokens_in or 0,
                        "output": s_tokens_out or 0,
                        "total": (s_tokens_in or 0) + (s_tokens_out or 0),
                    }
                trace.generation(
                    name=s_name,
                    model=s_model if s_model and s_model != "none" else None,
                    usage=usage_val,
                    start_time=_parse_time(s_start),
                    end_time=_parse_time(s_end),
                    metadata=step_meta,
                    input=step_in,
                    output=step_out,
                )
            elif hasattr(trace, "span"):
                trace.span(
                    name=s_name,
                    start_time=_parse_time(s_start),
                    end_time=_parse_time(s_end),
                    metadata=step_meta,
                    input=step_in,
                    output=step_out,
                )

        _safe_flush(client, timeout=flush_timeout)

        logger.info("Successfully exported audit trace %s to Langfuse", trace_id)
        return True
    except Exception as exc:
        logger.warning("Langfuse export failed (continuing audit): %s", exc)
        return False
