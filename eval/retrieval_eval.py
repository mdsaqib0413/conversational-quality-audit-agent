"""Evaluation of policy clause retrieval recall (offline baseline).

Measures retrieval recall across labelled calls with expected policy violations:
- Variant A: Full pipeline context (ALWAYS_INCLUDE + topic family + top-10 hybrid) -> production today
- Variant B: Top-10 retrieval only (k=10, no ALWAYS_INCLUDE, no topic family)
- Variant C: BM25 only (k=10, use_embeddings=False, no ALWAYS_INCLUDE, no topic family)

Outputs:
- eval/results/retrieval_<timestamp>.csv
- eval/results/retrieval_summary.md
- Prints summary table and miss details to stdout.
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

# Ensure repository root is on sys.path
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.audit.policy_check import ALWAYS_INCLUDE, agent_query
from src.audit.rag import KnowledgeBase
from src.audit.topic import detect_topic
from src.audit.transcript_io import load_transcript_json

logger = logging.getLogger("eval.retrieval")


@dataclass
class CallEvalResult:
    call_id: str
    detected_topic: str
    expected_topic: Optional[str]
    topic_match: bool
    expected_clauses: List[str]
    retrieved_clauses: List[str]
    clauses_sent_count: int
    hits: List[str]
    misses: List[str]
    all_retrieved: bool


@dataclass
class VariantResult:
    key: str
    name: str
    description: str
    total_calls: int
    total_expected_clauses: int
    total_hits: int
    clause_recall: float
    calls_all_retrieved: int
    calls_all_retrieved_pct: float
    avg_clauses_sent: float
    call_results: List[CallEvalResult] = field(default_factory=list)
    misses_by_call: List[Tuple[str, List[str], List[str]]] = field(default_factory=list)
    # (call_id, misses, expected_clauses)


@dataclass
class TopicMismatchResult:
    call_id: str
    detected_topic: str
    expected_topic: str
    also_ok_topics: List[str]
    expected_clauses: List[str]
    retrieved_in_a: bool
    retrieved_in_b: bool
    retrieved_in_c: bool
    hits_a: List[str]
    hits_b: List[str]
    hits_c: List[str]


def evaluate_retrieval(
    expected_data: Dict[str, Any],
    transcripts_dir: Path,
    kb: KnowledgeBase,
) -> Tuple[Dict[str, VariantResult], List[TopicMismatchResult]]:
    """Evaluate retrieval variants on labelled calls with expected violations."""
    target_calls: List[Tuple[str, List[str], Optional[str], List[str]]] = []
    for call_id, call_info in sorted(expected_data.items()):
        viols = call_info.get("violations", [])
        if not viols:
            continue
        expected_clauses = list(dict.fromkeys(v["clause"] for v in viols if "clause" in v))
        if not expected_clauses:
            continue
        topic_info = call_info.get("topic", {})
        if isinstance(topic_info, dict):
            expected_topic = topic_info.get("label")
            also_ok = topic_info.get("also_ok", [])
        else:
            expected_topic = str(topic_info) if topic_info else None
            also_ok = []
        target_calls.append((call_id, expected_clauses, expected_topic, also_ok))

    if not target_calls:
        logger.warning("No labelled calls with policy violations found.")
        return {}, []

    results_by_variant: Dict[str, List[CallEvalResult]] = {"A": [], "B": [], "C": []}
    mismatches: List[TopicMismatchResult] = []

    for call_id, expected_clauses, expected_topic, also_ok in target_calls:
        transcript_path = transcripts_dir / f"{call_id}.json"
        if not transcript_path.exists():
            raise FileNotFoundError(f"Transcript file not found: {transcript_path}")

        call, _ = load_transcript_json(transcript_path)
        topic_res = detect_topic(call.turns)
        detected_topic = topic_res.topic
        query = agent_query(call)

        topic_match = (detected_topic == expected_topic) or (detected_topic in also_ok)

        # Variant A: Full pipeline context (always_include + family + top-10)
        family = [c.id for c in kb.policies_for_topic(detected_topic)]
        clauses_a = kb.retrieve_policies(query, topic=detected_topic, k=10, always_include=ALWAYS_INCLUDE + family)
        ids_a = [c.id for c in clauses_a]
        hits_a = [c for c in expected_clauses if c in ids_a]
        misses_a = [c for c in expected_clauses if c not in ids_a]
        all_a = len(misses_a) == 0
        results_by_variant["A"].append(
            CallEvalResult(
                call_id=call_id,
                detected_topic=detected_topic,
                expected_topic=expected_topic,
                topic_match=topic_match,
                expected_clauses=expected_clauses,
                retrieved_clauses=ids_a,
                clauses_sent_count=len(ids_a),
                hits=hits_a,
                misses=misses_a,
                all_retrieved=all_a,
            )
        )

        # Variant B: Top-10 retrieval only (no always_include, no family)
        clauses_b = kb.retrieve_policies(query, topic=detected_topic, k=10, always_include=[])
        ids_b = [c.id for c in clauses_b]
        hits_b = [c for c in expected_clauses if c in ids_b]
        misses_b = [c for c in expected_clauses if c not in ids_b]
        all_b = len(misses_b) == 0
        results_by_variant["B"].append(
            CallEvalResult(
                call_id=call_id,
                detected_topic=detected_topic,
                expected_topic=expected_topic,
                topic_match=topic_match,
                expected_clauses=expected_clauses,
                retrieved_clauses=ids_b,
                clauses_sent_count=len(ids_b),
                hits=hits_b,
                misses=misses_b,
                all_retrieved=all_b,
            )
        )

        # Variant C: BM25 only (use_embeddings=False, no always_include, no family)
        clauses_c = kb.retrieve_policies(query, topic=detected_topic, k=10, always_include=[], use_embeddings=False)
        ids_c = [c.id for c in clauses_c]
        hits_c = [c for c in expected_clauses if c in ids_c]
        misses_c = [c for c in expected_clauses if c not in ids_c]
        all_c = len(misses_c) == 0
        results_by_variant["C"].append(
            CallEvalResult(
                call_id=call_id,
                detected_topic=detected_topic,
                expected_topic=expected_topic,
                topic_match=topic_match,
                expected_clauses=expected_clauses,
                retrieved_clauses=ids_c,
                clauses_sent_count=len(ids_c),
                hits=hits_c,
                misses=misses_c,
                all_retrieved=all_c,
            )
        )

        # Topic mismatch tracking
        if detected_topic != expected_topic:
            mismatches.append(
                TopicMismatchResult(
                    call_id=call_id,
                    detected_topic=detected_topic,
                    expected_topic=expected_topic or "unknown",
                    also_ok_topics=also_ok,
                    expected_clauses=expected_clauses,
                    retrieved_in_a=all_a,
                    retrieved_in_b=all_b,
                    retrieved_in_c=all_c,
                    hits_a=hits_a,
                    hits_b=hits_b,
                    hits_c=hits_c,
                )
            )

    variant_meta = {
        "A": ("Full pipeline context", "always_include + whole family + top-10"),
        "B": ("Top-10 retrieval only", "hybrid BM25 + embeddings, no always_include, no family"),
        "C": ("BM25 only", "BM25 only (use_embeddings=False), no always_include, no family"),
    }

    variant_summaries: Dict[str, VariantResult] = {}
    for v_key in ("A", "B", "C"):
        calls = results_by_variant[v_key]
        total_calls = len(calls)
        total_expected = sum(len(c.expected_clauses) for c in calls)
        total_hits = sum(len(c.hits) for c in calls)
        clause_recall = (total_hits / total_expected) if total_expected > 0 else 0.0
        calls_all = sum(1 for c in calls if c.all_retrieved)
        calls_all_pct = (calls_all / total_calls) if total_calls > 0 else 0.0
        avg_sent = (sum(c.clauses_sent_count for c in calls) / total_calls) if total_calls > 0 else 0.0

        misses = [
            (c.call_id, c.misses, c.expected_clauses)
            for c in calls
            if c.misses
        ]

        v_name, v_desc = variant_meta[v_key]
        variant_summaries[v_key] = VariantResult(
            key=v_key,
            name=v_name,
            description=v_desc,
            total_calls=total_calls,
            total_expected_clauses=total_expected,
            total_hits=total_hits,
            clause_recall=clause_recall,
            calls_all_retrieved=calls_all,
            calls_all_retrieved_pct=calls_all_pct,
            avg_clauses_sent=avg_sent,
            call_results=calls,
            misses_by_call=misses,
        )

    return variant_summaries, mismatches


def format_summary_markdown(
    summaries: Dict[str, VariantResult],
    mismatches: List[TopicMismatchResult],
    timestamp: str,
) -> str:
    lines: List[str] = []
    lines.append(f"# Policy Retrieval Evaluation Summary ({timestamp})")
    lines.append("")
    total_calls = summaries["A"].total_calls if "A" in summaries else 0
    total_expected = summaries["A"].total_expected_clauses if "A" in summaries else 0
    lines.append(f"Evaluated **{total_calls} calls** with policy violations (**{total_expected} total expected clauses**).")
    lines.append("")
    lines.append("## 1. Retrieval Performance Comparison")
    lines.append("")
    lines.append("| Variant | Configuration | Clause Recall | Calls with All Retrieved | Avg Clauses Sent |")
    lines.append("|---|---|---|---|---|")
    for key in ("A", "B", "C"):
        v = summaries[key]
        lines.append(
            f"| **{v.key}** | {v.name} ({v.description}) | "
            f"{v.clause_recall * 100:.1f}% ({v.total_hits}/{v.total_expected_clauses}) | "
            f"{v.calls_all_retrieved_pct * 100:.1f}% ({v.calls_all_retrieved}/{v.total_calls}) | "
            f"{v.avg_clauses_sent:.1f} |"
        )
    lines.append("")
    lines.append("## 2. Misses by Variant")
    lines.append("")
    for key in ("A", "B", "C"):
        v = summaries[key]
        lines.append(f"### Variant {v.key}: {v.name}")
        if not v.misses_by_call:
            lines.append("No misses. All expected clauses retrieved for all calls.")
        else:
            for call_id, missed, expected in v.misses_by_call:
                lines.append(f"- **{call_id}**: missed `{', '.join(missed)}` (expected: `{', '.join(expected)}`)")
        lines.append("")

    lines.append("## 3. Topic Detection vs Labelled Topic")
    lines.append("")
    if not mismatches:
        lines.append("Detected topic matched labelled topic across all evaluated calls.")
    else:
        lines.append("| Call ID | Detected Topic | Labelled Topic | Expected Clauses | Retrieved in A? | Retrieved in B? | Retrieved in C? |")
        lines.append("|---|---|---|---|---|---|---|")
        for m in mismatches:
            notes_a = "Yes" if m.retrieved_in_a else f"Partial ({', '.join(m.hits_a)})"
            notes_b = "Yes" if m.retrieved_in_b else (f"Partial ({', '.join(m.hits_b)})" if m.hits_b else "No")
            notes_c = "Yes" if m.retrieved_in_c else (f"Partial ({', '.join(m.hits_c)})" if m.hits_c else "No")
            lines.append(
                f"| `{m.call_id}` | `{m.detected_topic}` | `{m.expected_topic}` | "
                f"`{', '.join(m.expected_clauses)}` | {notes_a} | {notes_b} | {notes_c} |"
            )
    lines.append("")
    lines.append("## 4. Per-Call Breakdown (Variant A - Production)")
    lines.append("")
    lines.append("| Call ID | Detected Topic | Expected Clauses | Retrieved Count | Hits | Misses | All Retrieved? |")
    lines.append("|---|---|---|---|---|---|---|")
    for r in summaries["A"].call_results:
        status = "Yes" if r.all_retrieved else "No"
        misses_str = ", ".join(r.misses) if r.misses else "-"
        lines.append(
            f"| `{r.call_id}` | `{r.detected_topic}` | `{', '.join(r.expected_clauses)}` | "
            f"{r.clauses_sent_count} | `{', '.join(r.hits)}` | `{misses_str}` | {status} |"
        )
    lines.append("")
    return "\n".join(lines)


def write_csv(summaries: Dict[str, VariantResult], csv_path: Path, timestamp: str) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "timestamp",
        "variant",
        "variant_name",
        "call_id",
        "detected_topic",
        "expected_topic",
        "topic_match",
        "expected_clauses",
        "retrieved_clauses",
        "clauses_sent_count",
        "hits",
        "misses",
        "hit_count",
        "expected_count",
        "all_retrieved",
        "clause_recall",
    ]
    with open(csv_path, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for v_key in ("A", "B", "C"):
            v = summaries[v_key]
            for r in v.call_results:
                writer.writerow({
                    "timestamp": timestamp,
                    "variant": v_key,
                    "variant_name": v.name,
                    "call_id": r.call_id,
                    "detected_topic": r.detected_topic,
                    "expected_topic": r.expected_topic or "",
                    "topic_match": r.topic_match,
                    "expected_clauses": "; ".join(r.expected_clauses),
                    "retrieved_clauses": "; ".join(r.retrieved_clauses),
                    "clauses_sent_count": r.clauses_sent_count,
                    "hits": "; ".join(r.hits),
                    "misses": "; ".join(r.misses),
                    "hit_count": len(r.hits),
                    "expected_count": len(r.expected_clauses),
                    "all_retrieved": r.all_retrieved,
                    "clause_recall": round(len(r.hits) / len(r.expected_clauses), 4) if r.expected_clauses else 1.0,
                })


def run_retrieval_eval(
    expected_path: Optional[Path] = None,
    transcripts_dir: Optional[Path] = None,
    results_dir: Optional[Path] = None,
    kb: Optional[KnowledgeBase] = None,
    quiet: bool = False,
) -> Tuple[Dict[str, VariantResult], List[TopicMismatchResult], Path, Path]:
    expected_path = expected_path or (ROOT / "data" / "expected" / "expected_results.json")
    transcripts_dir = transcripts_dir or (ROOT / "data" / "transcripts")
    results_dir = results_dir or (ROOT / "eval" / "results")
    results_dir.mkdir(parents=True, exist_ok=True)

    if kb is None:
        kb = KnowledgeBase()

    with open(expected_path, encoding="utf-8") as f:
        expected_data = json.load(f)

    summaries, mismatches = evaluate_retrieval(expected_data, transcripts_dir, kb)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = results_dir / f"retrieval_{ts}.csv"
    summary_path = results_dir / "retrieval_summary.md"

    write_csv(summaries, csv_path, ts)
    md_content = format_summary_markdown(summaries, mismatches, ts)
    summary_path.write_text(md_content, encoding="utf-8")

    if not quiet:
        print(md_content)

    return summaries, mismatches, csv_path, summary_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate policy retrieval recall on labelled calls.")
    parser.add_argument("--expected", type=Path, default=ROOT / "data" / "expected" / "expected_results.json", help="Path to expected_results.json")
    parser.add_argument("--transcripts", type=Path, default=ROOT / "data" / "transcripts", help="Path to transcripts directory")
    parser.add_argument("--results-dir", type=Path, default=ROOT / "eval" / "results", help="Directory for output CSV and summary")
    parser.add_argument("--quiet", action="store_true", help="Do not print summary to stdout")
    args = parser.parse_args()

    run_retrieval_eval(
        expected_path=args.expected,
        transcripts_dir=args.transcripts,
        results_dir=args.results_dir,
        quiet=args.quiet,
    )


if __name__ == "__main__":
    main()
