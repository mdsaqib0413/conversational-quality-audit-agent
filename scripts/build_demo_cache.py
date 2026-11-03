#!/usr/bin/env python3
"""Build the zero-API demo cache from current canonical dev audits in data/cache/audits.

Copies the 13 canonical dev audits into:
1. Root-level data/demo_cache/<call_id>.json (unhashed) for report picker compatibility
2. Per-call folder data/demo_cache/<call_id>/ containing audit.json, trace.jsonl, and transcript.json
3. Standalone trace directory data/demo_cache/traces/<trace_id>.jsonl for the Observability page

Generates data/demo_cache/MANIFEST.json detailing salt, SOP model, policy model, build date,
per-call score, status, and file sizes.

Refuses to execute if data/cache/audits does not hold exactly one current-key audit
per benchmark dev call.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

# Add project root to sys.path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.audit.pipeline import AuditPipeline
from src.audit.rag import KnowledgeBase
from src.audit.transcript_io import load_transcript_json

DEV_CALLS = [
    "call_001", "call_009", "call_017", "call_025", "call_041",
    "call_101", "call_102", "call_103", "call_104", "call_105",
    "call_106", "call_107", "call_108",
]

SALT = "audit-v9"
SOP_MODEL = "gemini-3.5-flash-lite"
POLICY_MODEL = "gemini-3.5-flash"


def sanitize_text(text: str) -> str:
    """Strip local repository absolute paths from text."""
    root_str_win = str(ROOT)
    root_str_unix = str(ROOT).replace("\\", "/")
    t = text.replace(root_str_win, ".").replace(root_str_unix, ".")
    t = re.sub(r'[a-zA-Z]:[\\/][^ \",\n\r\t]*audit-agent', '.', t)
    return t


def build_demo_cache() -> None:
    cache_audits_dir = ROOT / "data" / "cache" / "audits"
    demo_cache_dir = ROOT / "data" / "demo_cache"
    traces_dir = ROOT / "traces"

    if not cache_audits_dir.exists():
        sys.exit(f"Error: cache directory does not exist: {cache_audits_dir}")

    pipe = AuditPipeline(kb=KnowledgeBase(use_embeddings=False))
    
    # Verify exact current-key matches for all 13 dev calls
    src_files = {}
    errors = []

    for cid in DEV_CALLS:
        trans_path = ROOT / "data" / "transcripts" / f"{cid}.json"
        if not trans_path.exists():
            errors.append(f"Transcript missing for {cid}: {trans_path}")
            continue

        call, _ = load_transcript_json(trans_path)
        cur_key = pipe._audit_key(call)
        expected_name = f"{cid}_{cur_key}.json"
        expected_path = cache_audits_dir / expected_name

        # Check all files matching this call_id
        matching = list(cache_audits_dir.glob(f"{cid}_*.json")) + list(cache_audits_dir.glob(f"{cid}.json"))
        if not expected_path.exists():
            errors.append(f"{cid}: Current-key audit file missing (expected {expected_name})")
        elif len(matching) != 1:
            matching_names = [p.name for p in matching]
            errors.append(f"{cid}: Expected exactly 1 file matching current key, but found {len(matching)}: {matching_names}")
        else:
            src_files[cid] = expected_path

    if errors:
        sys.stderr.write("Refusing to build demo cache due to cache anomalies:\n")
        for err in errors:
            sys.stderr.write(f"  - {err}\n")
        sys.exit(1)

    # Ensure demo cache directory structure exists
    demo_cache_dir.mkdir(parents=True, exist_ok=True)
    demo_traces_dir = demo_cache_dir / "traces"
    demo_traces_dir.mkdir(parents=True, exist_ok=True)

    manifest_calls = []
    print(f"Building demo cache in {demo_cache_dir}...")

    for cid in DEV_CALLS:
        src_path = src_files[cid]
        dst_path = demo_cache_dir / f"{cid}.json"
        call_dir = demo_cache_dir / cid
        call_dir.mkdir(parents=True, exist_ok=True)

        # 1. Sanitize and copy root-level audit JSON
        raw_content = src_path.read_text(encoding="utf-8")
        clean_audit = sanitize_text(raw_content).replace("\r\n", "\n").replace("\n", "\r\n")
        dst_path.write_bytes(clean_audit.encode("utf-8"))

        # Also copy to call_dir / audit.json
        (call_dir / "audit.json").write_bytes(clean_audit.encode("utf-8"))

        # 2. Copy transcript
        src_trans = ROOT / "data" / "transcripts" / f"{cid}.json"
        clean_trans = sanitize_text(src_trans.read_text(encoding="utf-8")).replace("\r\n", "\n").replace("\n", "\r\n")
        (call_dir / "transcript.json").write_bytes(clean_trans.encode("utf-8"))

        # 3. Locate, sanitize and copy trace JSONL
        data = json.loads(clean_audit)
        trace_id = data.get("meta", {}).get("trace_id", "")
        trace_src = traces_dir / f"{trace_id}.jsonl" if trace_id else None

        trace_bytes_len = 0
        if trace_src and trace_src.exists():
            clean_trace = sanitize_text(trace_src.read_text(encoding="utf-8")).replace("\r\n", "\n").replace("\n", "\r\n")
            (call_dir / "trace.jsonl").write_bytes(clean_trace.encode("utf-8"))
            (demo_traces_dir / f"{trace_id}.jsonl").write_bytes(clean_trace.encode("utf-8"))
            trace_bytes_len = len(clean_trace.encode("utf-8"))
        else:
            print(f"  Warning: trace file {trace_src} not found for {cid}")

        scores = data.get("scores", {})
        overall = scores.get("overall", 0.0)
        grade = scores.get("grade", "D")
        status = data.get("status", "ok")
        meta = data.get("meta", {})

        call_info = {
            "call_id": cid,
            "overall": round(float(overall), 1),
            "grade": grade,
            "status": status,
            "sop_model": meta.get("sop_model") or SOP_MODEL,
            "policy_model": meta.get("policy_model") or POLICY_MODEL,
            "llm_requests": meta.get("llm_requests", 2),
            "trace_id": trace_id,
            "sizes": {
                "audit_json_bytes": dst_path.stat().st_size,
                "trace_jsonl_bytes": trace_bytes_len,
                "transcript_json_bytes": (call_dir / "transcript.json").stat().st_size,
            },
        }
        manifest_calls.append(call_info)
        print(f"  Copied {cid}: overall={overall}, grade={grade}, status={status}, reqs={meta.get('llm_requests')}")

    manifest = {
        "audit_key_salt": SALT,
        "sop_model": SOP_MODEL,
        "policy_model": POLICY_MODEL,
        "build_date": datetime.now().isoformat(timespec="seconds"),
        "calls": manifest_calls,
    }

    manifest_json_str = json.dumps(manifest, indent=2)
    manifest_json_str = manifest_json_str.replace("\r\n", "\n").replace("\n", "\r\n")
    manifest_path = demo_cache_dir / "MANIFEST.json"
    manifest_path.write_bytes(manifest_json_str.encode("utf-8"))

    # Security check: verify no secrets or local user absolute paths
    drive_path_pattern = re.compile(r'[a-zA-Z]:[\\/](?:Users|audit-agent|home)', re.IGNORECASE)
    for p in demo_cache_dir.rglob("*"):
        if p.is_file():
            text = p.read_text(encoding="utf-8", errors="ignore")
            for secret_prefix in ["AIza", "sk-lf-", "pk-lf-"]:
                if secret_prefix in text:
                    for word in text.split():
                        if word.startswith(secret_prefix) and len(word) > 20 and "..." not in word:
                            sys.exit(f"Security Alert: Secret found in {p}: {word[:8]}***")
            m = drive_path_pattern.search(text)
            if m:
                sys.exit(f"Security Alert: Local absolute path found in {p}: {m.group(0)}")

    print(f"\nWrote manifest with {len(manifest_calls)} calls to {manifest_path.name}")
    print("Demo cache build complete (verified clean of secrets and absolute paths).")


if __name__ == "__main__":
    build_demo_cache()
