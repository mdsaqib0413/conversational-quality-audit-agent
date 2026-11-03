#!/usr/bin/env python3
"""Build the zero-API demo cache from current canonical dev audits in data/cache/audits.

Copies the 13 canonical dev audits into data/demo_cache/<call_id>.json (without hash)
and generates data/demo_cache/MANIFEST.json detailing salt, policy model, timestamp,
and call score metrics.

Refuses to execute if data/cache/audits does not hold exactly one current-key audit
per benchmark dev call.
"""

from __future__ import annotations

import json
import os
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
POLICY_MODEL = "gemini-3.5-flash"


def build_demo_cache() -> None:
    cache_audits_dir = ROOT / "data" / "cache" / "audits"
    demo_cache_dir = ROOT / "data" / "demo_cache"

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

    # Ensure demo cache directory exists
    demo_cache_dir.mkdir(parents=True, exist_ok=True)

    manifest_calls = []
    print(f"Building demo cache in {demo_cache_dir}...")

    for cid in DEV_CALLS:
        src_path = src_files[cid]
        dst_path = demo_cache_dir / f"{cid}.json"
        
        # Copy file
        shutil.copy2(src_path, dst_path)

        # Parse metrics for manifest
        data = json.loads(dst_path.read_text(encoding="utf-8"))
        scores = data.get("scores", {})
        overall = scores.get("overall", 0.0)
        grade = scores.get("grade", "D")
        status = data.get("status", "ok")

        manifest_calls.append({
            "call_id": cid,
            "overall": round(float(overall), 1),
            "grade": grade,
            "status": status,
        })
        print(f"  Copied {src_path.name} -> {dst_path.name} (overall: {overall}, grade: {grade}, status: {status})")

    manifest = {
        "audit_key_salt": SALT,
        "policy_model": POLICY_MODEL,
        "generation_date": datetime.now().isoformat(timespec="seconds"),
        "calls": manifest_calls,
    }

    manifest_path = demo_cache_dir / "MANIFEST.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Wrote manifest with {len(manifest_calls)} calls to {manifest_path.name}")
    print("Demo cache build complete.")


if __name__ == "__main__":
    build_demo_cache()
