"""Tests for data/live/policy_plain.json and live policy guidance enrichment."""

import json
from pathlib import Path
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


def test_policy_plain_prohibitions_and_limits():
    """Verify prohibitions and limits for representative high-risk clauses."""
    plain_map = get_policy_plain_map()
    assert len(plain_map) == 42

    # Prohibitions
    assert "PRV-1.1" in plain_map
    assert "Never" in plain_map["PRV-1.1"]["never"]

    assert "PRV-2.1" in plain_map
    assert "Never" in plain_map["PRV-2.1"]["never"]

    assert "BIL-2.2" in plain_map
    assert "Never" in plain_map["BIL-2.2"]["never"]
    assert "5,000" in plain_map["BIL-2.2"]["limit"]

    assert "ESC-2.2" in plain_map
    assert "Never" in plain_map["ESC-2.2"]["never"]

    assert "SHP-3.1" in plain_map
    assert "Never" in plain_map["SHP-3.1"]["never"]
    assert "2,500" in plain_map["SHP-3.1"]["limit"]

    # Limits
    assert "REF-1.1" in plain_map
    assert "7" in plain_map["REF-1.1"]["limit"]

    assert "ESC-2.1" in plain_map
    assert "2" in plain_map["ESC-2.1"]["limit"]

    assert "WAR-1.2" in plain_map
    assert "48" in plain_map["WAR-1.2"]["limit"]


def test_live_rules_populates_enriched_active_clauses():
    """Verify LiveRules surfaces enriched policy clauses with what_to_do and plain limits."""
    rules = LiveRules()
    # Feed events to detect topic and trigger clause retrieval
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
