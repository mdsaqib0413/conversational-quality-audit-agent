"""Langfuse smoke test script.

Verifies Langfuse connectivity by creating a dummy trace named "smoke_test",
adding one span, recording a score of 1.0 with a fake call id, and flushing.

Usage:
    python scripts/langfuse_smoke_test.py

Behavior:
- If keys are not configured: prints "Langfuse not configured" and exits (0).
- If keys are set: sends the dummy trace, flushes, and prints "sent" or the error.
- Never prints API key values.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

# Load .env if present
env_path = REPO_ROOT / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)


def run_smoke_test() -> int:
    pk = os.environ.get("LANGFUSE_PUBLIC_KEY", "").strip()
    sk = os.environ.get("LANGFUSE_SECRET_KEY", "").strip()
    host = (os.environ.get("LANGFUSE_HOST") or os.environ.get("LANGFUSE_BASE_URL") or "").strip().rstrip("/")

    if not (pk and sk and host):
        print("Langfuse not configured")
        return 0

    try:
        from langfuse import Langfuse
    except ImportError:
        print("Error: langfuse package is not installed (run `pip install -r requirements.txt`)")
        return 1

    try:
        try:
            client = Langfuse(public_key=pk, secret_key=sk, host=host, timeout=5.0)
        except TypeError:
            client = Langfuse(public_key=pk, secret_key=sk, host=host)

        fake_call_id = "call_smoke_000"
        trace = client.trace(
            name="smoke_test",
            metadata={"call_id": fake_call_id, "test": True},
        )
        trace.span(
            name="smoke_span",
            metadata={"status": "ok"},
        )
        if hasattr(trace, "score"):
            trace.score(name="smoke_score", value=1.0)
        elif hasattr(client, "score"):
            client.score(trace_id=getattr(trace, "id", "smoke_trace"), name="smoke_score", value=1.0)

        # Flush with timeout
        from src.audit.langfuse_export import _safe_flush

        _safe_flush(client, timeout=5.0)

        print("sent")
        return 0
    except Exception as exc:
        err = str(exc)
        if pk and pk in err:
            err = err.replace(pk, "[REDACTED]")
        if sk and sk in err:
            err = err.replace(sk, "[REDACTED]")
        print(err)
        return 1


if __name__ == "__main__":
    sys.exit(run_smoke_test())
