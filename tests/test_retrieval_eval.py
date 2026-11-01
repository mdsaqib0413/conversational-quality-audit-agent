"""Tests for policy retrieval evaluation baseline harness (offline)."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from eval.retrieval_eval import (
    evaluate_retrieval,
    format_summary_markdown,
    run_retrieval_eval,
    write_csv,
)
from src.audit.rag import KnowledgeBase


@pytest.fixture
def synthetic_retrieval_env(tmp_path: Path):
    """Create a minimal synthetic knowledge base and transcripts environment."""
    data_dir = tmp_path / "data"
    pol_dir = data_dir / "policies"
    sop_dir = data_dir / "sops"
    trans_dir = tmp_path / "transcripts"
    results_dir = tmp_path / "results"

    pol_dir.mkdir(parents=True)
    sop_dir.mkdir(parents=True)
    trans_dir.mkdir(parents=True)
    results_dir.mkdir(parents=True)

    (data_dir / "rubric.yaml").write_text("version: 1\nsop_steps: []\n", encoding="utf-8")
    (pol_dir / "refund.md").write_text(
        "---\ntype: policy\ncategory: general\n---\n"
        "### [REF-1.1] Standard Refund Window\nRefunds within 7 days of delivery.\n\n"
        "### [REF-2.1] Refund Mode\nRefund to original payment method.\n\n"
        "### [PRV-1.1] Data Privacy\nNever disclose customer details.\n\n"
        "### [ESC-1.1] Mandatory Escalation\nEscalate upon supervisor request.\n",
        encoding="utf-8",
    )
    (sop_dir / "sop.md").write_text(
        "---\ntype: sop\n---\n### [GEN-01] Greeting\nGreet customer politely.\n",
        encoding="utf-8",
    )

    # Call 1: Discusses refunds and has expected violation REF-1.1
    call_1 = {
        "id": "call_synth_001",
        "turns": [
            {"speaker": "customer", "text": "I want a refund for my order please."},
            {"speaker": "agent", "text": "I can process an immediate refund of money back for you."},
        ],
    }
    (trans_dir / "call_synth_001.json").write_text(json.dumps(call_1), encoding="utf-8")

    # Call 2: Discusses refunds, expects non-existent policy UNK-9.9 (guaranteed miss)
    call_2 = {
        "id": "call_synth_002",
        "turns": [
            {"speaker": "customer", "text": "Can I return this item for a full refund?"},
            {"speaker": "agent", "text": "Returns and refunds are subject to review."},
        ],
    }
    (trans_dir / "call_synth_002.json").write_text(json.dumps(call_2), encoding="utf-8")

    expected_data = {
        "call_synth_001": {
            "topic": {"label": "refund", "also_ok": []},
            "violations": [{"clause": "REF-1.1", "severity": "major", "turn": 2}],
        },
        "call_synth_002": {
            "topic": {"label": "refund", "also_ok": []},
            "violations": [{"clause": "UNK-9.9", "severity": "minor", "turn": 2}],
        },
        "call_synth_unviolated": {
            "topic": {"label": "refund", "also_ok": []},
            "violations": [],
        },
    }

    expected_file = data_dir / "expected_results.json"
    expected_file.write_text(json.dumps(expected_data), encoding="utf-8")

    kb = KnowledgeBase(data_dir=data_dir, use_embeddings=False)

    return {
        "data_dir": data_dir,
        "trans_dir": trans_dir,
        "results_dir": results_dir,
        "expected_file": expected_file,
        "expected_data": expected_data,
        "kb": kb,
    }


def test_evaluate_retrieval_synthetic_metrics(synthetic_retrieval_env):
    """Verify metrics calculation on synthetic fixture with hits and misses."""
    env = synthetic_retrieval_env
    summaries, mismatches = evaluate_retrieval(
        expected_data=env["expected_data"],
        transcripts_dir=env["trans_dir"],
        kb=env["kb"],
    )

    # 1. Calls with zero violations should be excluded (only 2 calls evaluated)
    assert "A" in summaries
    assert "B" in summaries
    assert "C" in summaries

    summary_a = summaries["A"]
    assert summary_a.total_calls == 2
    assert summary_a.total_expected_clauses == 2
    assert summary_a.total_hits == 1  # REF-1.1 hit, UNK-9.9 missed
    assert summary_a.clause_recall == 0.5
    assert summary_a.calls_all_retrieved == 1
    assert summary_a.calls_all_retrieved_pct == 0.5
    assert len(summary_a.misses_by_call) == 1

    call_id, misses, expected = summary_a.misses_by_call[0]
    assert call_id == "call_synth_002"
    assert misses == ["UNK-9.9"]
    assert expected == ["UNK-9.9"]

    # First call had full recall
    res_1 = [r for r in summary_a.call_results if r.call_id == "call_synth_001"][0]
    assert res_1.all_retrieved is True
    assert res_1.hits == ["REF-1.1"]
    assert res_1.misses == []


def test_topic_mismatch_tracking(synthetic_retrieval_env):
    """Verify that topic differences between detected and labelled topics are flagged."""
    env = synthetic_retrieval_env
    # Mismatch topic: transcript talks about refund, but label is "shipping"
    expected_mismatch = {
        "call_synth_001": {
            "topic": {"label": "shipping", "also_ok": []},
            "violations": [{"clause": "REF-1.1", "severity": "major", "turn": 2}],
        },
    }

    summaries, mismatches = evaluate_retrieval(
        expected_data=expected_mismatch,
        transcripts_dir=env["trans_dir"],
        kb=env["kb"],
    )

    assert len(mismatches) == 1
    m = mismatches[0]
    assert m.call_id == "call_synth_001"
    assert m.detected_topic == "refund"
    assert m.expected_topic == "shipping"
    assert m.expected_clauses == ["REF-1.1"]
    assert m.retrieved_in_a is True  # retrieved via query or family


def test_format_markdown_and_write_csv(synthetic_retrieval_env, tmp_path: Path):
    """Verify markdown report generation and CSV output structure."""
    env = synthetic_retrieval_env
    summaries, mismatches = evaluate_retrieval(
        expected_data=env["expected_data"],
        transcripts_dir=env["trans_dir"],
        kb=env["kb"],
    )

    ts = "20261101_120000"
    md = format_summary_markdown(summaries, mismatches, ts)
    assert "# Policy Retrieval Evaluation Summary" in md
    assert "| Variant | Configuration | Clause Recall | Calls with All Retrieved | Avg Clauses Sent |" in md
    assert "**A**" in md
    assert "**B**" in md
    assert "**C**" in md
    assert "call_synth_002" in md

    csv_path = tmp_path / "test_out.csv"
    write_csv(summaries, csv_path, ts)
    assert csv_path.exists()

    with open(csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    assert len(rows) == 6  # 2 calls * 3 variants
    variants_in_csv = {r["variant"] for r in rows}
    assert variants_in_csv == {"A", "B", "C"}
    assert "expected_clauses" in reader.fieldnames
    assert "retrieved_clauses" in reader.fieldnames
    assert "clause_recall" in reader.fieldnames


def test_run_retrieval_eval_end_to_end(synthetic_retrieval_env):
    """Verify run_retrieval_eval writes summary.md and timestamped csv."""
    env = synthetic_retrieval_env
    summaries, mismatches, csv_path, summary_path = run_retrieval_eval(
        expected_path=env["expected_file"],
        transcripts_dir=env["trans_dir"],
        results_dir=env["results_dir"],
        kb=env["kb"],
        quiet=True,
    )

    assert csv_path.exists()
    assert summary_path.exists()
    assert "Policy Retrieval Evaluation Summary" in summary_path.read_text(encoding="utf-8")
    assert summaries["A"].total_calls == 2
