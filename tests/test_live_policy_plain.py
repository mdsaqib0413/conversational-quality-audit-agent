"""Tests for data/live/policy_plain.json and live policy guidance enrichment."""

import glob
import json
from pathlib import Path
import re
import pytest

from src.audit.rag import KnowledgeBase
from src.audit.live.rules import LiveRules, get_policy_plain_map
from src.audit.live.events import CaptionEvent

ROOT = Path(__file__).resolve().parent.parent


def test_policy_plain_json_exists_and_valid():
    """Verify data/live/policy_plain.json exists, has 42 entries matching KnowledgeBase."""
    plain_file = ROOT / "data" / "live" / "policy_plain.json"
    assert plain_file.exists(), f"File not found: {plain_file}"

    data = json.loads(plain_file.read_text(encoding="utf-8"))
    assert isinstance(data, list), "Expected policy_plain.json to be a list of entries"
    assert len(data) == 42, f"Expected 42 clauses, got {len(data)}"

    kb = KnowledgeBase(use_embeddings=False)
    kb_ids = {c.id for c in kb.policies}
    plain_ids = {item["id"] for item in data}

    assert plain_ids == kb_ids, f"ID mismatch: {kb_ids ^ plain_ids}"

    for item in data:
        assert item.get("id"), "Missing clause id"
        assert item.get("title"), f"Missing title in {item['id']}"
        assert item.get("what_to_do"), f"Missing what_to_do in {item['id']}"
        assert "never" in item, f"Missing never field in {item['id']}"
        assert "limit" in item, f"Missing limit field in {item['id']}"


def test_policy_plain_strict_fidelity_and_integrity():
    """Verify every entry is built strictly from its clause section.

    Fails if:
    1. Any number or duration in what_to_do, never, or limit is missing from its section text.
    2. Severity differs from Default Severity.
    3. A must_not_do clause has no Never line.
    """
    plain_file = ROOT / "data" / "live" / "policy_plain.json"
    data = json.loads(plain_file.read_text(encoding="utf-8"))

    # Parse sections from markdown
    policy_files = sorted(glob.glob(str(ROOT / "data" / "policies" / "*.md")))
    sections = {}
    metadata = {}
    for pf in policy_files:
        content = Path(pf).read_text(encoding="utf-8")
        parts = re.split(r'(?=^###\s+\[[A-Z]+-\d+\.\d+\])', content, flags=re.M)
        for part in parts:
            m = re.match(r'^###\s+\[([A-Z]+-\d+\.\d+)\]\s+(.*)', part.strip())
            if m:
                cid = m.group(1)
                heading = m.group(2).strip()
                kind_m = re.search(r'-\s+\*\*Kind:\*\*\s*(.*)', part)
                sev_m = re.search(r'-\s+\*\*Default Severity:\*\*\s*(.*)', part)
                num_m = re.search(r'-\s+\*\*Numeric Limit:\*\*\s*(.*)', part)

                sections[cid] = part.strip()
                metadata[cid] = {
                    "heading": heading,
                    "kind": kind_m.group(1).strip() if kind_m else "",
                    "severity": sev_m.group(1).strip().lower() if sev_m else "",
                    "numeric_limit": num_m.group(1).strip() if num_m else "",
                }

    assert len(data) == 42
    assert len(sections) == 42

    duration_units = ["day", "days", "hour", "hours", "minute", "minutes", "month", "months", "second", "seconds"]

    for entry in data:
        cid = entry["id"]
        assert cid in sections, f"Unknown clause ID: {cid}"
        sec_text = sections[cid]
        meta = metadata[cid]

        # 1. Heading verbatim
        assert entry["title"] == meta["heading"], (
            f"[{cid}] Title mismatch: '{entry['title']}' != '{meta['heading']}'"
        )

        # 2. Severity matches Default Severity
        assert entry["severity"].lower() == meta["severity"].lower(), (
            f"[{cid}] Severity mismatch: '{entry['severity']}' != '{meta['severity']}'"
        )

        # 3. must_not_do requires a Never line
        if meta["kind"] == "must_not_do":
            assert entry.get("never") and len(entry["never"].strip()) > 0, (
                f"[{cid}] must_not_do clause has empty Never line"
            )
        else:
            assert entry.get("never") == "", (
                f"[{cid}] Non-must_not_do clause should have empty Never line, got: {entry.get('never')}"
            )

        # 4. Limit matches Numeric Limit
        if meta["numeric_limit"].lower() == "none":
            assert entry["limit"] == "", f"[{cid}] Expected empty limit for 'none', got '{entry['limit']}'"
        else:
            assert entry["limit"] == meta["numeric_limit"], (
                f"[{cid}] Limit mismatch: '{entry['limit']}' != '{meta['numeric_limit']}'"
            )

        # 5. All numbers in what_to_do, never, limit must appear in section text
        combined = f"{entry['what_to_do']} {entry['never']} {entry['limit']}"
        numbers = re.findall(r'\b\d+(?:,\d+)*(?:\.\d+)?\b', combined)
        for num in set(numbers):
            assert num in sec_text, (
                f"[{cid}] Number '{num}' in entry was not found in source section text!"
            )

        # 6. All duration words must appear in section text
        for unit in duration_units:
            if re.search(r'\b' + unit + r'\b', combined.lower()):
                assert re.search(r'\b' + unit + r'\b', sec_text.lower()), (
                    f"[{cid}] Duration unit '{unit}' in entry not found in source section text!"
                )

    # Specific assertions for the spot-checked clauses
    # PRV-2.1: Sensitive Personal Data Redaction (must_not_do, critical, OTP/card, no limit)
    prv21 = next(it for it in data if it["id"] == "PRV-2.1")
    assert prv21["title"] == "Sensitive Personal Data Redaction"
    assert prv21["severity"] == "critical"
    assert "Never" in prv21["never"]
    assert "OTP" in prv21["what_to_do"] or "OTP" in prv21["never"]
    assert prv21["limit"] == ""

    # ESC-1.1: Mandatory Supervisor Escalation Triggers (must_say, critical, none)
    esc11 = next(it for it in data if it["id"] == "ESC-1.1")
    assert esc11["title"] == "Mandatory Supervisor Escalation Triggers"
    assert esc11["severity"] == "critical"
    assert esc11["limit"] == ""

    # REF-1.1: Return Eligibility Windows (major, 7 days)
    ref11 = next(it for it in data if it["id"] == "REF-1.1")
    assert ref11["title"] == "Return Eligibility Windows"
    assert ref11["severity"] == "major"
    assert ref11["limit"] == "7 days"

    # REF-2.1: Refund Processing Timelines (minor, 5 to 7 business days)
    ref21 = next(it for it in data if it["id"] == "REF-2.1")
    assert ref21["title"] == "Refund Processing Timelines"
    assert ref21["severity"] == "minor"
    assert ref21["limit"] == "5 to 7 business days"

    # SHP-1.1: Service Tiers and Standard Transit SLAs (minor, 3 to 7 business days)
    shp11 = next(it for it in data if it["id"] == "SHP-1.1")
    assert shp11["title"] == "Service Tiers and Standard Transit SLAs"
    assert shp11["severity"] == "minor"
    assert shp11["limit"] == "3 to 7 business days"


def test_live_rules_populates_enriched_active_clauses():
    """Verify LiveRules surfaces enriched policy clauses with what_to_do and plain limits."""
    rules = LiveRules()
    ev1 = CaptionEvent(
        call_id="test",
        peer_id="agent",
        role="agent",
        text="Hello, thank you for calling ShopEase. This call is recorded.",
        start_ms=0,
        end_ms=2000,
        final=True,
    )
    ev2 = CaptionEvent(
        call_id="test",
        peer_id="cust",
        role="customer",
        text="I want to return an electronic smartphone order ORD-12345.",
        start_ms=2200,
        end_ms=5000,
        final=True,
    )
    rules.process_event(ev1)
    rules.process_event(ev2)

    assert rules.active_clauses, "Expected active clauses to be populated after topic detection"
    cl = rules.active_clauses[0]
    assert "id" in cl
    assert "title" in cl
    assert "what_to_do" in cl and len(cl["what_to_do"]) > 0
    assert "never" in cl
    assert "limit" in cl
    assert "text" in cl and len(cl["text"]) > 0
    assert "topics" in cl
