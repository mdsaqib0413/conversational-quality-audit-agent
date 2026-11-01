"""Tests for held-out evaluation dataset.

Verifies:
1. Exactly 12 calls load from data/heldout/transcripts/ and data/heldout/expected_heldout.json.
2. Every cited clause ID exists in data/policies/*.md.
3. Policy coverage across all 6 families (REF, SHP, WAR, BIL, ESC, PRV).
4. At least 3 cross-topic calls (violated clause family != call topic).
5. At least 2 calls with 3+ violations.
6. At least 3 clean calls with zero violations.
7. Turn counts within [12, 30] and at least one long call with >3500 chars of agent speech.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parent.parent
HELDOUT_DIR = ROOT / "data" / "heldout" / "transcripts"
EXPECTED_PATH = ROOT / "data" / "heldout" / "expected_heldout.json"
POLICIES_DIR = ROOT / "data" / "policies"


def load_all_policy_clauses() -> set[str]:
    clauses = set()
    clause_re = re.compile(r"###?\s*\[?([A-Z]{3}-\d+\.\d+)\]?")
    for p in POLICIES_DIR.glob("*.md"):
        content = p.read_text(encoding="utf-8")
        clauses.update(clause_re.findall(content))
    return clauses


def test_heldout_files_exist_and_load():
    assert EXPECTED_PATH.exists(), f"Expected labels missing at {EXPECTED_PATH}"
    expected_data = json.loads(EXPECTED_PATH.read_text(encoding="utf-8"))
    assert len(expected_data) == 12, f"Expected 12 heldout calls, found {len(expected_data)}"

    transcript_files = list(HELDOUT_DIR.glob("call_*.json"))
    assert len(transcript_files) == 12, f"Expected 12 transcript files, found {len(transcript_files)}"

    for file_path in transcript_files:
        call_id = file_path.stem
        assert call_id in expected_data, f"Call {call_id} missing from expected_heldout.json"
        data = json.loads(file_path.read_text(encoding="utf-8"))
        assert data["id"] == call_id
        assert "turns" in data and len(data["turns"]) >= 12
        assert "ground_truth" in data


def test_every_cited_clause_exists_in_policies():
    all_clauses = load_all_policy_clauses()
    assert len(all_clauses) >= 42, f"Expected at least 42 policy clauses, found {len(all_clauses)}"

    expected_data = json.loads(EXPECTED_PATH.read_text(encoding="utf-8"))
    for call_id, info in expected_data.items():
        for v in info.get("violations", []):
            clause = v["clause"]
            assert clause in all_clauses, f"Call {call_id} cites unknown clause {clause}"


def test_coverage_rules_across_heldout_dataset():
    expected_data = json.loads(EXPECTED_PATH.read_text(encoding="utf-8"))

    families_seen = set()
    cross_topic_calls = []
    three_plus_violation_calls = []
    clean_calls = []
    has_long_agent_speech_call = False

    topic_to_prefix = {
        "refund": "REF",
        "shipping": "SHP",
        "warranty": "WAR",
        "billing": "BIL",
        "complaint": "ESC",
    }

    for call_id, info in expected_data.items():
        topic = info["topic"]["label"]
        primary_prefix = topic_to_prefix.get(topic)
        violations = info.get("violations", [])

        if not violations:
            clean_calls.append(call_id)
        else:
            if len(violations) >= 3:
                three_plus_violation_calls.append(call_id)

            is_cross = False
            for v in violations:
                clause = v["clause"]
                family = clause.split("-")[0]
                families_seen.add(family)
                if primary_prefix and family != primary_prefix:
                    is_cross = True

            if is_cross:
                cross_topic_calls.append(call_id)

        # Check turn counts and speech length
        t_file = HELDOUT_DIR / f"{call_id}.json"
        t_data = json.loads(t_file.read_text(encoding="utf-8"))
        turns = t_data["turns"]
        assert 12 <= len(turns) <= 30, f"{call_id} has {len(turns)} turns, outside [12, 30]"

        agent_speech_len = sum(len(t["text"]) for t in turns if t["speaker"] == "agent")
        if agent_speech_len > 3500:
            has_long_agent_speech_call = True

    # Rule 1: at least 1 violation in each family (REF, SHP, WAR, BIL, ESC, PRV)
    required_families = {"REF", "SHP", "WAR", "BIL", "ESC", "PRV"}
    missing_families = required_families - families_seen
    assert not missing_families, f"Missing violations in families: {missing_families}"

    # Rule 2: at least 3 cross-topic calls
    assert len(cross_topic_calls) >= 3, f"Expected >= 3 cross-topic calls, got {len(cross_topic_calls)}: {cross_topic_calls}"

    # Rule 3: at least 2 calls with 3+ violations
    assert len(three_plus_violation_calls) >= 2, f"Expected >= 2 calls with 3+ violations, got {len(three_plus_violation_calls)}: {three_plus_violation_calls}"

    # Rule 4: at least 3 clean calls
    assert len(clean_calls) >= 3, f"Expected >= 3 clean calls, got {len(clean_calls)}: {clean_calls}"

    # Rule 5: at least one long call with >3500 chars of agent speech
    assert has_long_agent_speech_call, "Expected at least one call with >3500 chars of agent speech"
