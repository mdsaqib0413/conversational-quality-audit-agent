"""Export an already-cached audit report and its trace JSONL to Langfuse without LLM API calls.

Usage:
    python scripts/export_cached_to_langfuse.py <call_id>
"""
import glob
import json
import os
import sys
from pathlib import Path

# Load env vars safely without printing any secret
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import requests
from src.audit.langfuse_export import export_audit_to_langfuse, is_langfuse_enabled
from src.audit.schemas import AuditReport


def export_cached(call_id: str) -> bool:
    if not is_langfuse_enabled():
        print("Langfuse is not enabled or keys are not configured.")
        return False

    audit_dir = ROOT / "data" / "cache" / "audits"
    matches = sorted(audit_dir.glob(f"{call_id}_*.json"))
    if not matches:
        matches = sorted(audit_dir.glob(f"{call_id}.json"))

    if not matches:
        print(f"Error: No cached audit report found for '{call_id}' in {audit_dir}")
        return False

    report_path = matches[0]
    print(f"Found cached report: {report_path.name}")
    try:
        report = AuditReport.model_validate_json(report_path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"Error reading report: {e}")
        return False

    trace_id = getattr(report.meta, "trace_id", None)
    trace_path = ROOT / "traces" / f"{trace_id}.jsonl" if trace_id else None
    if trace_path and trace_path.exists():
        print(f"Found trace file: {trace_path.name} ({trace_path.stat().st_size} bytes)")
    else:
        print(f"Note: Trace file for '{trace_id}' not found on disk; exporting report metadata only")

    # Intercept requests.post to capture and print HTTP statuses (no secret headers/payloads printed)
    orig_post = requests.post
    status_records = []

    def logged_post(url, *args, **kwargs):
        resp = orig_post(url, *args, **kwargs)
        # Parse endpoint name
        endpoint = url
        for prefix in ("https://cloud.langfuse.com", "http://cloud.langfuse.com", "https://us.cloud.langfuse.com"):
            if endpoint.startswith(prefix):
                endpoint = endpoint[len(prefix):]
        # Check if score name in json body
        extra = ""
        payload = kwargs.get("json") or {}
        if isinstance(payload, dict):
            if "name" in payload:
                extra = f" ({payload['name']})"
            elif "resourceSpans" in payload:
                extra = " (traces)"
        status_line = f"POST {endpoint}{extra} -> HTTP {resp.status_code}"
        status_records.append(status_line)
        print(f"  {status_line}")
        return resp

    requests.post = logged_post

    # Ensure eval/prod source does not suppress export
    os.environ["LANGFUSE_EXPORT_EVAL"] = "1"

    print(f"Exporting '{call_id}' (status={report.status}, overall={report.scores.overall:.1f}) to Langfuse...")
    success = export_audit_to_langfuse(report, tracer=None)
    requests.post = orig_post

    if success:
        print(f"Successfully exported '{call_id}' to Langfuse.")
    else:
        print(f"Export finished with errors or was skipped.")
    return success


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/export_cached_to_langfuse.py <call_id>")
        sys.exit(1)
    call_id = sys.argv[1].strip()
    ok = export_cached(call_id)
    sys.exit(0 if ok else 1)
