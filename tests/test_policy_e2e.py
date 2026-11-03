"""Offline unit tests for eval/policy_e2e.py."""

from __future__ import annotations

import json
from pathlib import Path
from typing import List

import pytest

from eval.policy_e2e import (
    ExpectedViolation,
    SingleRunResult,
    compute_aggregates,
    generate_markdown_report,
    get_allowed_clauses,
    get_variant_clauses,
    match_violations_turn_level,
    write_csv_report,
)
from src.audit.rag import KnowledgeBase
from src.audit.schemas import CallTranscript, DialogueTurn, PolicyResult


@pytest.fixture
def mock_call() -> CallTranscript:
    turns = [
        DialogueTurn(turn_id=1, speaker="customer", text="I want to return my phone, order 1234."),
        DialogueTurn(turn_id=2, speaker="agent", text="Sure, returns for electronics are accepted within 30 days."),
    ]
    return CallTranscript(call_id="call_mock_01", turns=turns, audio_file="")


@pytest.fixture
def kb() -> KnowledgeBase:
    return KnowledgeBase()


def test_get_variant_clauses_a(mock_call, kb):
    clauses = get_variant_clauses("A", mock_call, "returns", kb)
    clause_ids = {c.id for c in clauses}
    # Should include ALWAYS_INCLUDE
    assert "PRV-1.1" in clause_ids
    assert "ESC-1.1" in clause_ids
    assert len(clauses) <= len(kb.policies)


def test_get_variant_clauses_g(mock_call, kb):
    clauses = get_variant_clauses("G", mock_call, "returns", kb)
    clause_ids = {c.id for c in clauses}
    # G must include all PRV and ESC clauses
    for p in kb.policies:
        if p.family in ("PRV", "ESC"):
            assert p.id in clause_ids, f"{p.id} missing from Variant G"


def test_get_variant_clauses_f(mock_call, kb):
    clauses = get_variant_clauses("F", mock_call, "returns", kb)
    assert len(clauses) == len(kb.policies)


def test_compute_aggregates_and_reports(tmp_path):
    mock_run = SingleRunResult(
        split="dev",
        call_id="call_017",
        variant="A",
        detected_topic="shipping",
        clauses_sent_count=15,
        clauses_sent_ids=["SHP-2.1", "PRV-1.1"],
        expected_clauses=["SHP-2.1"],
        found_violations=[
            PolicyResult(
                clause_id="SHP-2.1",
                policy_title="Shipping",
                verdict="violation",
                severity="minor",
                turn=9,
                quote="Delivery takes 10 days",
                claim="Claim",
                explanation="Explanation",
            )
        ],
        found_clause_ids=["SHP-2.1"],
        matched_clauses=["SHP-2.1"],
        missed_clauses=[],
        all_expected_found=True,
        extra_violations=[],
        input_tokens=2500,
        output_tokens=150,
        total_tokens=2650,
        latency_s=1.5,
    )

    aggs = compute_aggregates([mock_run], "A", "dev")
    assert aggs.total_calls == 1
    assert aggs.recall == 1.0
    assert aggs.fully_covered_calls == 1
    assert aggs.total_extra_findings == 0
    assert aggs.avg_input_tokens == 2500.0

    # Test CSV export
    csv_file = tmp_path / "test_out.csv"
    write_csv_report([mock_run], csv_file)
    assert csv_file.exists()
    content = csv_file.read_text(encoding="utf-8")
    assert "call_017" in content
    assert "SHP-2.1" in content

    # Test Markdown export
    md_file = tmp_path / "test_out.md"
    report_text = generate_markdown_report([mock_run], "gemini-test", md_file)
    assert md_file.exists()
    assert "Executive Summary Tables" in report_text
    assert "Variant A" in report_text


def test_matcher_war_alternate_pair():
    # call_207 turn 7 allows WAR-2.1 <-> WAR-2.3
    assert "WAR-2.3" in get_allowed_clauses("WAR-2.1", call_id="call_207", turn=7)
    assert "WAR-2.1" in get_allowed_clauses("WAR-2.3", call_id="call_207", turn=7)

    # call_209 turn 11 allows WAR-2.1 <-> WAR-2.3
    assert "WAR-2.3" in get_allowed_clauses("WAR-2.1", call_id="call_209", turn=11)
    assert "WAR-2.1" in get_allowed_clauses("WAR-2.3", call_id="call_209", turn=11)

    # Restricted by call_id or turn
    assert "WAR-2.3" not in get_allowed_clauses("WAR-2.1", call_id="call_207", turn=8)
    assert "WAR-2.3" not in get_allowed_clauses("WAR-2.1", call_id="call_208", turn=7)
    assert "WAR-2.3" not in get_allowed_clauses("WAR-2.1", call_id="call_209", turn=10)

    # Turn-level matching test
    expected = [ExpectedViolation(clause="WAR-2.1", turn=7)]
    found = [
        PolicyResult(
            clause_id="WAR-2.3",
            policy_title="Warranty",
            verdict="violation",
            severity="minor",
            turn=7,
            quote="turn 7 quote",
            claim="Claim",
            explanation="Explanation",
        )
    ]
    matched, missed, extra = match_violations_turn_level(expected, found, turn_window=2, call_id="call_207")
    assert len(matched) == 1
    assert len(missed) == 0
    assert len(extra) == 0
    assert "matched as WAR-2.3" in matched[0]

