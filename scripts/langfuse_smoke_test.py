"""Langfuse smoke test script.

Verifies Langfuse connectivity by creating a dummy trace and span via OpenTelemetry OTLP
(POST /api/public/otel/v1/traces) and recording a score via REST (POST /api/public/scores).

Usage:
    python scripts/langfuse_smoke_test.py

Behavior:
- If keys are not configured: prints "Langfuse not configured" and exits (0).
- If keys are set: sends OTLP trace + score, prints the HTTP status of each request,
  and exits non-zero if any response is not 2xx.
- Never prints API key values.
"""
from __future__ import annotations

import base64
import hashlib
import os
import sys
import time
from pathlib import Path
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

# Load .env if present
env_path = REPO_ROOT / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)


def run_smoke_test(timeout: float = 10.0) -> int:
    pk = os.environ.get("LANGFUSE_PUBLIC_KEY", "").strip()
    sk = os.environ.get("LANGFUSE_SECRET_KEY", "").strip()
    host = (os.environ.get("LANGFUSE_HOST") or os.environ.get("LANGFUSE_BASE_URL") or "").strip().rstrip("/")

    if not (pk and sk and host):
        print("Langfuse not configured")
        return 0

    try:
        import requests

        auth_str = f"{pk}:{sk}"
        b64_auth = base64.b64encode(auth_str.encode()).decode()

        fake_call_id = "call_smoke_000"
        hex_trace_id = hashlib.md5(f"{fake_call_id}_trace".encode()).hexdigest()
        root_span_id = hashlib.md5(f"{fake_call_id}_root".encode()).hexdigest()[:16]
        child_span_id = hashlib.md5(f"{fake_call_id}_span".encode()).hexdigest()[:16]
        now_ns = int(time.time() * 1e9)

        otlp_payload = {
            "resourceSpans": [{
                "resource": {
                    "attributes": [
                        {"key": "service.name", "value": {"stringValue": "audit-agent"}},
                        {"key": "session.id", "value": {"stringValue": fake_call_id}},
                        {"key": "user.id", "value": {"stringValue": f"agent_{fake_call_id}"}},
                    ]
                },
                "scopeSpans": [{
                    "scope": {"name": "smoke_test"},
                    "spans": [
                        {
                            "traceId": hex_trace_id,
                            "spanId": root_span_id,
                            "name": "smoke_test",
                            "kind": 1,
                            "startTimeUnixNano": str(now_ns - 1000000000),
                            "endTimeUnixNano": str(now_ns),
                            "attributes": [
                                {"key": "call_id", "value": {"stringValue": fake_call_id}},
                                {"key": "status", "value": {"stringValue": "ok"}},
                            ],
                            "status": {"code": 1},
                        },
                        {
                            "traceId": hex_trace_id,
                            "spanId": child_span_id,
                            "parentSpanId": root_span_id,
                            "name": "smoke_span",
                            "kind": 1,
                            "startTimeUnixNano": str(now_ns - 500000000),
                            "endTimeUnixNano": str(now_ns),
                            "attributes": [
                                {"key": "step_name", "value": {"stringValue": "smoke_span"}},
                                {"key": "status", "value": {"stringValue": "ok"}},
                            ],
                            "status": {"code": 1},
                        },
                    ],
                }],
            }]
        }

        trace_headers = {
            "Authorization": f"Basic {b64_auth}",
            "Content-Type": "application/json",
            "x-langfuse-ingestion-version": "4",
        }

        resp_trace = requests.post(
            f"{host}/api/public/otel/v1/traces",
            headers=trace_headers,
            json=otlp_payload,
            timeout=timeout,
        )
        print(f"OTLP traces: HTTP {resp_trace.status_code}")

        score_headers = {
            "Authorization": f"Basic {b64_auth}",
            "Content-Type": "application/json",
        }
        score_payload = {
            "traceId": hex_trace_id,
            "name": "smoke_score",
            "value": 1.0,
        }
        resp_score = requests.post(
            f"{host}/api/public/scores",
            headers=score_headers,
            json=score_payload,
            timeout=timeout,
        )
        print(f"Score: HTTP {resp_score.status_code}")

        if not (200 <= resp_trace.status_code < 300 and 200 <= resp_score.status_code < 300):
            print("Error: One or more requests returned non-2xx status")
            return 1

        print("sent")
        return 0

    except Exception as exc:
        err = str(exc)
        if pk and pk in err:
            err = err.replace(pk, "[REDACTED]")
        if sk and sk in err:
            err = err.replace(sk, "[REDACTED]")
        print(f"Error: {err}")
        return 1


if __name__ == "__main__":
    sys.exit(run_smoke_test())
