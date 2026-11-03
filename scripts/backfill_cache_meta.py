#!/usr/bin/env python3
"""Backfill meta (sop_model, policy_model, llm_requests) in canonical cache files.

Backs up existing cache files into data/cache/audits_backup/ before modifying.
Extracts models and request counts from execution trace JSONL files.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.audit.schemas import AuditReport
from src.audit.ui_html import format_models_header

CACHE_DIR = ROOT / "data" / "cache" / "audits"
BACKUP_DIR = ROOT / "data" / "cache" / "audits_backup"
TRACES_DIR = ROOT / "traces"

DEV_CALLS = [
    "call_001", "call_009", "call_017", "call_025", "call_041",
    "call_101", "call_102", "call_103", "call_104", "call_105",
    "call_106", "call_107", "call_108",
]


def clean_model_str(name: str | None) -> str:
    if not name:
        return ""
    n = str(name).strip()
    if n.startswith("gemini:"):
        n = n[len("gemini:"):]
    return n


def backfill_cache():
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    
    before_headers = {}
    after_headers = {}

    for cid in DEV_CALLS:
        matches = list(CACHE_DIR.glob(f"{cid}_*.json"))
        if not matches:
            print(f"[{cid}] No cache file found in {CACHE_DIR}")
            continue
        if len(matches) > 1:
            print(f"[{cid}] Multiple cache files found: {[m.name for m in matches]}, skipping")
            continue
        
        cache_file = matches[0]
        backup_file = BACKUP_DIR / cache_file.name

        # 1. Back up original
        shutil.copy2(cache_file, backup_file)

        # 2. Read existing
        raw = json.loads(cache_file.read_text(encoding="utf-8"))
        old_rep = AuditReport.model_validate(raw)
        before_headers[cid] = format_models_header(old_rep)

        # 3. Find trace file
        trace_id = raw.get("meta", {}).get("trace_id", "")
        trace_path = TRACES_DIR / f"{trace_id}.jsonl" if trace_id else None

        if not trace_path or not trace_path.exists():
            # Search for latest trace for this call
            cand_traces = sorted(TRACES_DIR.glob(f"run_{cid}_*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
            if cand_traces:
                trace_path = cand_traces[0]
            else:
                print(f"[{cid}] Trace missing; leaving file unchanged.")
                after_headers[cid] = before_headers[cid]
                continue

        # 4. Parse trace steps
        steps = []
        for line in trace_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                try:
                    steps.append(json.loads(line))
                except Exception:
                    pass

        found_sop = None
        found_pol = None
        total_reqs = 0

        for st in steps:
            s_name = st.get("step_name", "")
            m_name = st.get("model_name", "")
            cnt = st.get("request_count", 0)
            total_reqs += cnt
            if s_name in ("sop_check", "scorecard_judgment") and m_name and m_name != "none":
                found_sop = clean_model_str(m_name)
            elif s_name == "policy_check" and m_name and m_name != "none":
                found_pol = clean_model_str(m_name)

        if not found_sop and not found_pol and total_reqs == 0:
            print(f"[{cid}] Trace contained no model calls; leaving file unchanged.")
            after_headers[cid] = before_headers[cid]
            continue

        sop_model = found_sop or clean_model_str(raw.get("meta", {}).get("sop_model")) or "gemini-3.5-flash-lite"
        policy_model = found_pol or clean_model_str(raw.get("meta", {}).get("policy_model")) or "gemini-3.5-flash"
        req_count = total_reqs if total_reqs > 0 else raw.get("meta", {}).get("llm_requests", 1)

        combined_model = (
            f"SOP: {sop_model} · Policy: {policy_model}"
            if (sop_model and policy_model and sop_model != policy_model)
            else (sop_model or policy_model or raw.get("meta", {}).get("model", ""))
        )

        # Update meta dictionary
        if "meta" not in raw:
            raw["meta"] = {}
        raw["meta"]["sop_model"] = sop_model
        raw["meta"]["policy_model"] = policy_model
        raw["meta"]["llm_requests"] = req_count
        raw["meta"]["model"] = combined_model

        # Write back with CRLF
        content_str = json.dumps(raw, indent=1)
        content_str = content_str.replace("\r\n", "\n").replace("\n", "\r\n")
        cache_file.write_bytes(content_str.encode("utf-8"))

        new_rep = AuditReport.model_validate(raw)
        after_headers[cid] = format_models_header(new_rep)
        print(f"[{cid}] Backfilled successfully: sop={sop_model}, pol={policy_model}, reqs={req_count}")

    print("\n=== BEFORE AND AFTER HEADERS FOR CALL_107 & CALL_108 ===")
    for c in ["call_107", "call_108"]:
        print(f"\n{c}:")
        print(f"  BEFORE: {before_headers.get(c)}")
        print(f"  AFTER:  {after_headers.get(c)}")


if __name__ == "__main__":
    backfill_cache()
