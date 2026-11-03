#!/usr/bin/env python3
"""Offline verification script for audit cache and demo cache integrity.

Validates that:
1. Every JSON file loads and parses cleanly into Pydantic AuditReport schema
2. Specific target scores match expected values:
   - call_105: 70.0 (Grade C)
   - call_107: 57.8 (Grade D)
   - call_106: 16.1 (Grade D, degraded)
3. Header metadata displays both SOP and Policy models without crashing
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.audit.schemas import AuditReport
from src.audit.ui_html import format_models_header, report_header, audit_mode_badge

DEV_CALLS = [
    "call_001", "call_009", "call_017", "call_025", "call_041",
    "call_101", "call_102", "call_103", "call_104", "call_105",
    "call_106", "call_107", "call_108",
]


def verify_cache() -> None:
    demo_cache_dir = ROOT / "data" / "demo_cache"
    cache_audits_dir = ROOT / "data" / "cache" / "audits"

    print("=== STARTING OFFLINE CACHE VERIFICATION ===\n")

    # 1. Verify demo cache manifest
    manifest_path = demo_cache_dir / "MANIFEST.json"
    assert manifest_path.exists(), f"MANIFEST.json missing at {manifest_path}"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest.get("audit_key_salt") == "audit-v9", "Incorrect audit salt"
    assert manifest.get("sop_model") == "gemini-3.5-flash-lite", "Incorrect SOP model"
    assert manifest.get("policy_model") == "gemini-3.5-flash", "Incorrect policy model"
    assert len(manifest.get("calls", [])) == 13, f"Expected 13 calls in manifest, got {len(manifest.get('calls', []))}"
    print("[PASS] MANIFEST.json structure and metadata valid")

    # 2. Verify each dev call in demo cache and active cache
    checked_calls = {}

    for cid in DEV_CALLS:
        # Check root demo file
        demo_file = demo_cache_dir / f"{cid}.json"
        assert demo_file.exists(), f"Demo file missing: {demo_file}"
        raw_demo = json.loads(demo_file.read_text(encoding="utf-8"))
        rep_demo = AuditReport.model_validate(raw_demo)

        # Check bundle demo file
        bundle_file = demo_cache_dir / cid / "audit.json"
        assert bundle_file.exists(), f"Bundle audit missing: {bundle_file}"
        bundle_trace = demo_cache_dir / cid / "trace.jsonl"
        assert bundle_trace.exists(), f"Bundle trace missing: {bundle_trace}"
        bundle_trans = demo_cache_dir / cid / "transcript.json"
        assert bundle_trans.exists(), f"Bundle transcript missing: {bundle_trans}"

        # Check active cache file
        active_matches = list(cache_audits_dir.glob(f"{cid}_*.json"))
        assert len(active_matches) == 1, f"Expected 1 active cache file for {cid}, found {len(active_matches)}"
        raw_active = json.loads(active_matches[0].read_text(encoding="utf-8"))
        rep_active = AuditReport.model_validate(raw_active)

        # Check models in header
        hdr_demo = format_models_header(rep_demo)
        assert "SOP: gemini-3.5-flash-lite" in hdr_demo, f"[{cid}] SOP model missing in header: {hdr_demo}"
        assert "Policy: gemini-3.5-flash" in hdr_demo, f"[{cid}] Policy model missing in header: {hdr_demo}"

        hdr_html = report_header(rep_demo)
        assert "Transcript audit" in hdr_html, f"[{cid}] Mode badge missing in header HTML"

        checked_calls[cid] = {
            "overall": rep_demo.scores.overall,
            "grade": rep_demo.scores.grade,
            "status": rep_demo.status,
            "header": hdr_demo,
            "mode": audit_mode_badge(rep_demo),
        }
        print(f"[PASS] {cid}: score={rep_demo.scores.overall:.1f}, grade={rep_demo.scores.grade}, status={rep_demo.status}, header='{hdr_demo}'")

    # 3. Verify specific score targets
    # call_105: 70.0
    c105 = checked_calls["call_105"]
    assert abs(c105["overall"] - 70.0) < 0.05, f"call_105 overall expected 70.0, got {c105['overall']}"
    assert c105["grade"] == "C", f"call_105 grade expected C, got {c105['grade']}"
    print("\n[VERIFIED] call_105: overall=70.0, grade=C (capped from raw score)")

    # call_107: 57.8
    c107 = checked_calls["call_107"]
    assert abs(c107["overall"] - 57.8) < 0.05, f"call_107 overall expected 57.8, got {c107['overall']}"
    assert c107["grade"] == "D", f"call_107 grade expected D, got {c107['grade']}"
    print("[VERIFIED] call_107: overall=57.8, grade=D")

    # call_106: 16.1 degraded
    c106 = checked_calls["call_106"]
    assert abs(c106["overall"] - 16.1) < 0.05, f"call_106 overall expected 16.1, got {c106['overall']}"
    assert c106["grade"] == "D", f"call_106 grade expected D, got {c106['grade']}"
    assert c106["status"] == "degraded", f"call_106 status expected degraded, got {c106['status']}"
    print("[VERIFIED] call_106: overall=16.1, grade=D, status=degraded")

    print("\n=== ALL OFFLINE CACHE VERIFICATIONS PASSED SUCCESSFULLY ===")


if __name__ == "__main__":
    verify_cache()
