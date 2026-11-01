"""Evaluation of policy clause retrieval recall (offline baseline).

Measures retrieval recall across labelled calls with expected policy violations:
- Variant A: Full pipeline context (ALWAYS_INCLUDE + topic family + top-10 hybrid) -> production today
- Variant B: Top-10 retrieval only (k=10, no ALWAYS_INCLUDE, no topic family)
- Variant C: BM25 only (k=10, use_embeddings=False, no ALWAYS_INCLUDE, no topic family)
- Variant D: Metadata-aware retrieval (k=10, BM25 + embeddings + topic boost + situation boost, no ALWAYS_INCLUDE, no topic family)
- Variant E: Metadata-aware + Core Safety (k=10, Variant D + always_include=["PRV-1.1", "ESC-1.1"], no topic family)

Outputs:
- eval/results/retrieval_<timestamp>.csv
- eval/results/heldout_retrieval_baseline.csv
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

from src.audit.policy_check import ALWAYS_INCLUDE, agent_query, call_retrieval_query
from src.audit.rag import KnowledgeBase
from src.audit.topic import detect_call_situations, detect_topic
from src.audit.transcript_io import load_transcript_json

logger = logging.getLogger("eval.retrieval")

# Universal core safety clauses for Variant E (no full family)
CORE_SAFETY_CLAUSES = ["PRV-1.1", "ESC-1.1"]


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
    avg_clean_clauses_sent: float = 0.0
    total_clean_calls: int = 0


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
    retrieved_in_d: bool
    retrieved_in_e: bool
    hits_a: List[str]
    hits_b: List[str]
    hits_c: List[str]
    hits_d: List[str]
    hits_e: List[str]


def evaluate_retrieval(
    expected_data: Dict[str, Any],
    transcripts_dir: Path,
    kb: KnowledgeBase,
) -> Tuple[Dict[str, VariantResult], List[TopicMismatchResult]]:
    """Evaluate retrieval variants on labelled calls with expected violations and clean calls."""
    target_calls: List[Tuple[str, List[str], Optional[str], List[str]]] = []
    clean_calls: List[Tuple[str, Optional[str], List[str]]] = []

    for call_id, call_info in sorted(expected_data.items()):
        viols = call_info.get("violations", [])
        expected_clauses = list(dict.fromkeys(v["clause"] for v in viols if "clause" in v))
        topic_info = call_info.get("topic", {})
        if isinstance(topic_info, dict):
            expected_topic = topic_info.get("label")
            also_ok = topic_info.get("also_ok", [])
        else:
            expected_topic = str(topic_info) if topic_info else None
            also_ok = []

        if not expected_clauses:
            clean_calls.append((call_id, expected_topic, also_ok))
        else:
            target_calls.append((call_id, expected_clauses, expected_topic, also_ok))

    if not target_calls and not clean_calls:
        logger.warning("No labelled calls found in expected data.")
        return {}, []

    results_by_variant: Dict[str, List[CallEvalResult]] = {
        "A": [], "B": [], "C": [], "D": [], "E": []
    }
    clean_counts_by_variant: Dict[str, List[int]] = {
        "A": [], "B": [], "C": [], "D": [], "E": []
    }
    mismatches: List[TopicMismatchResult] = []

    # 1. Evaluate calls with violations
    for call_id, expected_clauses, expected_topic, also_ok in target_calls:
        transcript_path = transcripts_dir / f"{call_id}.json"
        if not transcript_path.exists():
            raise FileNotFoundError(f"Transcript file not found: {transcript_path}")

        call, _ = load_transcript_json(transcript_path)
        topic_res = detect_topic(call.turns)
        detected_topic = topic_res.topic
        query = agent_query(call)
        query_d = call_retrieval_query(call)
        sits = detect_call_situations(call.turns)

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

        # Variant D: Metadata-aware retrieval (customer+agent query, situation boost, no always_include, no family)
        clauses_d = kb.retrieve_policies(query_d, topic=detected_topic, k=10, always_include=[], situations=sits)
        ids_d = [c.id for c in clauses_d]
        hits_d = [c for c in expected_clauses if c in ids_d]
        misses_d = [c for c in expected_clauses if c not in ids_d]
        all_d = len(misses_d) == 0
        results_by_variant["D"].append(
            CallEvalResult(
                call_id=call_id,
                detected_topic=detected_topic,
                expected_topic=expected_topic,
                topic_match=topic_match,
                expected_clauses=expected_clauses,
                retrieved_clauses=ids_d,
                clauses_sent_count=len(ids_d),
                hits=hits_d,
                misses=misses_d,
                all_retrieved=all_d,
            )
        )

        # Variant E: Metadata-aware + Core Safety (Variant D + always_include=["PRV-1.1", "ESC-1.1"], no family)
        clauses_e = kb.retrieve_policies(query_d, topic=detected_topic, k=10, always_include=CORE_SAFETY_CLAUSES, situations=sits)
        ids_e = [c.id for c in clauses_e]
        hits_e = [c for c in expected_clauses if c in ids_e]
        misses_e = [c for c in expected_clauses if c not in ids_e]
        all_e = len(misses_e) == 0
        results_by_variant["E"].append(
            CallEvalResult(
                call_id=call_id,
                detected_topic=detected_topic,
                expected_topic=expected_topic,
                topic_match=topic_match,
                expected_clauses=expected_clauses,
                retrieved_clauses=ids_e,
                clauses_sent_count=len(ids_e),
                hits=hits_e,
                misses=misses_e,
                all_retrieved=all_e,
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
                    retrieved_in_d=all_d,
                    retrieved_in_e=all_e,
                    hits_a=hits_a,
                    hits_b=hits_b,
                    hits_c=hits_c,
                    hits_d=hits_d,
                    hits_e=hits_e,
                )
            )

    # 2. Evaluate clean calls (zero violations) to track average clauses sent
    for call_id, expected_topic, also_ok in clean_calls:
        transcript_path = transcripts_dir / f"{call_id}.json"
        if not transcript_path.exists():
            continue
        call, _ = load_transcript_json(transcript_path)
        topic_res = detect_topic(call.turns)
        detected_topic = topic_res.topic
        query = agent_query(call)
        query_d = call_retrieval_query(call)
        sits = detect_call_situations(call.turns)
        family = [c.id for c in kb.policies_for_topic(detected_topic)]

        cnt_a = len(kb.retrieve_policies(query, topic=detected_topic, k=10, always_include=ALWAYS_INCLUDE + family))
        cnt_b = len(kb.retrieve_policies(query, topic=detected_topic, k=10, always_include=[]))
        cnt_c = len(kb.retrieve_policies(query, topic=detected_topic, k=10, always_include=[], use_embeddings=False))
        cnt_d = len(kb.retrieve_policies(query_d, topic=detected_topic, k=10, always_include=[], situations=sits))
        cnt_e = len(kb.retrieve_policies(query_d, topic=detected_topic, k=10, always_include=CORE_SAFETY_CLAUSES, situations=sits))

        clean_counts_by_variant["A"].append(cnt_a)
        clean_counts_by_variant["B"].append(cnt_b)
        clean_counts_by_variant["C"].append(cnt_c)
        clean_counts_by_variant["D"].append(cnt_d)
        clean_counts_by_variant["E"].append(cnt_e)

    variant_meta = {
        "A": ("Full pipeline context", "always_include + whole family + top-10"),
        "B": ("Top-10 retrieval only", "hybrid BM25 + embeddings, no always_include, no family"),
        "C": ("BM25 only", "BM25 only (use_embeddings=False), no always_include, no family"),
        "D": ("Metadata-aware retrieval", "BM25 + embeddings + topic boost + situation boost, no always_include, no family"),
        "E": ("Metadata-aware + Core Safety", "Variant D + always_include=['PRV-1.1', 'ESC-1.1'] (no full family)"),
    }

    variant_summaries: Dict[str, VariantResult] = {}
    for v_key in ("A", "B", "C", "D", "E"):
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

        clean_counts = clean_counts_by_variant[v_key]
        avg_clean = (sum(clean_counts) / len(clean_counts)) if clean_counts else 0.0

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
            avg_clean_clauses_sent=avg_clean,
            total_clean_calls=len(clean_counts),
        )

    return variant_summaries, mismatches


def format_summary_markdown(
    summaries: Dict[str, VariantResult],
    mismatches: List[TopicMismatchResult],
    timestamp: str,
    split_title: str = "Dev Set",
) -> str:
    lines: List[str] = []
    lines.append(f"# Policy Retrieval Evaluation Summary - {split_title} ({timestamp})")
    lines.append("")
    total_calls = summaries["A"].total_calls if "A" in summaries else 0
    total_expected = summaries["A"].total_expected_clauses if "A" in summaries else 0
    total_clean = summaries["A"].total_clean_calls if "A" in summaries else 0
    lines.append(
        f"Evaluated **{total_calls} calls with violations** ({total_expected} expected clauses) "
        f"and **{total_clean} clean calls**."
    )
    lines.append("")
    lines.append("### 1. Retrieval Performance Comparison")
    lines.append("")
    lines.append(
        "| Variant | Configuration | Clause Recall | Calls with All Retrieved | Avg Clauses Sent | Avg Clean Sent |"
    )
    lines.append("|---|---|---|---|---|---|")
    for key in ("A", "B", "C", "D", "E"):
        if key not in summaries:
            continue
        v = summaries[key]
        clean_str = f"{v.avg_clean_clauses_sent:.1f}" if v.total_clean_calls > 0 else "N/A"
        lines.append(
            f"| **{v.key}** | {v.name} ({v.description}) | "
            f"{v.clause_recall * 100:.1f}% ({v.total_hits}/{v.total_expected_clauses}) | "
            f"{v.calls_all_retrieved_pct * 100:.1f}% ({v.calls_all_retrieved}/{v.total_calls}) | "
            f"{v.avg_clauses_sent:.1f} | {clean_str} |"
        )
    lines.append("")
    lines.append("### 2. Misses by Variant")
    lines.append("")
    for key in ("A", "B", "C", "D", "E"):
        if key not in summaries:
            continue
        v = summaries[key]
        lines.append(f"#### Variant {v.key}: {v.name}")
        if not v.misses_by_call:
            lines.append("No misses. All expected clauses retrieved for all calls.")
        else:
            for call_id, missed, expected in v.misses_by_call:
                lines.append(f"- **{call_id}**: missed `{', '.join(missed)}` (expected: `{', '.join(expected)}`)")
        lines.append("")

    lines.append("### 3. Topic Detection vs Labelled Topic")
    lines.append("")
    if not mismatches:
        lines.append("Detected topic matched labelled topic across all evaluated calls.")
    else:
        lines.append(
            "| Call ID | Detected Topic | Labelled Topic | Expected Clauses | Retrieved in A? | Retrieved in B? | Retrieved in C? | Retrieved in D? | Retrieved in E? |"
        )
        lines.append("|---|---|---|---|---|---|---|---|---|")
        for m in mismatches:
            notes_a = "Yes" if m.retrieved_in_a else (f"Partial ({', '.join(m.hits_a)})" if m.hits_a else "No")
            notes_b = "Yes" if m.retrieved_in_b else (f"Partial ({', '.join(m.hits_b)})" if m.hits_b else "No")
            notes_c = "Yes" if m.retrieved_in_c else (f"Partial ({', '.join(m.hits_c)})" if m.hits_c else "No")
            notes_d = "Yes" if m.retrieved_in_d else (f"Partial ({', '.join(m.hits_d)})" if m.hits_d else "No")
            notes_e = "Yes" if m.retrieved_in_e else (f"Partial ({', '.join(m.hits_e)})" if m.hits_e else "No")
            lines.append(
                f"| `{m.call_id}` | `{m.detected_topic}` | `{m.expected_topic}` | "
                f"`{', '.join(m.expected_clauses)}` | {notes_a} | {notes_b} | {notes_c} | {notes_d} | {notes_e} |"
            )
    lines.append("")
    lines.append("### 4. Per-Call Breakdown (Variant A - Production Baseline)")
    lines.append("")
    lines.append("| Call ID | Detected Topic | Expected Clauses | Retrieved Count | Hits | Misses | All Retrieved? |")
    lines.append("|---|---|---|---|---|---|---|")
    if "A" in summaries:
        for r in summaries["A"].call_results:
            status = "Yes" if r.all_retrieved else "No"
            misses_str = ", ".join(r.misses) if r.misses else "-"
            lines.append(
                f"| `{r.call_id}` | `{r.detected_topic}` | `{', '.join(r.expected_clauses)}` | "
                f"{r.clauses_sent_count} | `{', '.join(r.hits)}` | `{misses_str}` | {status} |"
            )
    lines.append("")

    lines.append("### 5. Per-Call Breakdown (Variant D - Metadata-Aware)")
    lines.append("")
    lines.append("| Call ID | Detected Topic | Expected Clauses | Retrieved Count | Hits | Misses | All Retrieved? |")
    lines.append("|---|---|---|---|---|---|---|")
    if "D" in summaries:
        for r in summaries["D"].call_results:
            status = "Yes" if r.all_retrieved else "No"
            misses_str = ", ".join(r.misses) if r.misses else "-"
            lines.append(
                f"| `{r.call_id}` | `{r.detected_topic}` | `{', '.join(r.expected_clauses)}` | "
                f"{r.clauses_sent_count} | `{', '.join(r.hits)}` | `{misses_str}` | {status} |"
            )
    lines.append("")

    lines.append("### 6. Per-Call Breakdown (Variant E - Metadata-Aware + Core Safety)")
    lines.append("")
    lines.append("| Call ID | Detected Topic | Expected Clauses | Retrieved Count | Hits | Misses | All Retrieved? |")
    lines.append("|---|---|---|---|---|---|---|")
    if "E" in summaries:
        for r in summaries["E"].call_results:
            status = "Yes" if r.all_retrieved else "No"
            misses_str = ", ".join(r.misses) if r.misses else "-"
            lines.append(
                f"| `{r.call_id}` | `{r.detected_topic}` | `{', '.join(r.expected_clauses)}` | "
                f"{r.clauses_sent_count} | `{', '.join(r.hits)}` | `{misses_str}` | {status} |"
            )
    lines.append("")
    return "\n".join(lines)


def write_csv(
    summaries: Dict[str, VariantResult],
    csv_path: Path,
    timestamp: str,
    split_name: str = "dev",
) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "split",
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
        for v_key in ("A", "B", "C", "D", "E"):
            if v_key not in summaries:
                continue
            v = summaries[v_key]
            for r in v.call_results:
                writer.writerow({
                    "split": split_name,
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
    dataset_split: str = "both",
) -> Tuple[Dict[str, VariantResult], List[TopicMismatchResult], Path, Path]:
    results_dir = results_dir or (ROOT / "eval" / "results")
    results_dir.mkdir(parents=True, exist_ok=True)

    if kb is None:
        kb = KnowledgeBase()

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    summary_path = results_dir / "retrieval_summary.md"
    csv_path = results_dir / f"retrieval_{ts}.csv"
    heldout_csv_path = results_dir / "heldout_retrieval_baseline.csv"

    dev_expected_path = ROOT / "data" / "expected" / "expected_results.json"
    dev_transcripts_dir = ROOT / "data" / "transcripts"
    heldout_expected_path = ROOT / "data" / "heldout" / "expected_heldout.json"
    heldout_transcripts_dir = ROOT / "data" / "heldout" / "transcripts"

    all_md_parts: List[str] = [f"# Policy Retrieval Evaluation Summary ({ts})\n"]
    dev_summaries: Dict[str, VariantResult] = {}
    dev_mismatches: List[TopicMismatchResult] = []
    heldout_summaries: Dict[str, VariantResult] = {}
    heldout_mismatches: List[TopicMismatchResult] = []

    # DEV EVALUATION
    if dataset_split in ("dev", "both"):
        exp_p = expected_path or dev_expected_path
        trn_d = transcripts_dir or dev_transcripts_dir
        with open(exp_p, encoding="utf-8") as f:
            dev_expected = json.load(f)
        dev_summaries, dev_mismatches = evaluate_retrieval(dev_expected, trn_d, kb)
        dev_md = format_summary_markdown(dev_summaries, dev_mismatches, ts, split_title="Dev Set")
        all_md_parts.append(dev_md)

    # HELDOUT EVALUATION
    if dataset_split in ("heldout", "both"):
        h_exp_p = expected_path if dataset_split == "heldout" and expected_path else heldout_expected_path
        h_trn_d = transcripts_dir if dataset_split == "heldout" and transcripts_dir else heldout_transcripts_dir
        if h_exp_p.exists() and h_trn_d.exists():
            with open(h_exp_p, encoding="utf-8") as f:
                heldout_expected = json.load(f)
            heldout_summaries, heldout_mismatches = evaluate_retrieval(heldout_expected, h_trn_d, kb)
            heldout_md = format_summary_markdown(heldout_summaries, heldout_mismatches, ts, split_title="Held-Out Set")
            all_md_parts.append(heldout_md)
            # Write dedicated held-out baseline CSV
            write_csv(heldout_summaries, heldout_csv_path, ts, split_name="heldout")

    # Write combined CSV
    with open(csv_path, mode="w", newline="", encoding="utf-8") as f:
        fieldnames = [
            "split",
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
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for split_name, summs in (("dev", dev_summaries), ("heldout", heldout_summaries)):
            for v_key in ("A", "B", "C", "D", "E"):
                if v_key not in summs:
                    continue
                v = summs[v_key]
                for r in v.call_results:
                    writer.writerow({
                        "split": split_name,
                        "timestamp": ts,
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

    # Comparative analysis section in markdown summary
    if dev_summaries and heldout_summaries:
        all_md_parts.append("\n## 7. Dev vs Held-Out Comparative Analysis\n")
        all_md_parts.append("| Variant | Dev Recall | Held-Out Recall | Dev Avg Sent | Held-Out Avg Sent | Generalisation Assessment |")
        all_md_parts.append("|---|---|---|---|---|---|")
        for k in ("A", "B", "C", "D", "E"):
            d_v = dev_summaries.get(k)
            h_v = heldout_summaries.get(k)
            if d_v and h_v:
                assessment = "Baseline production context" if k == "A" else (
                    "Core safety universal backup" if k == "E" else (
                        "Strong lexical/semantic generalization" if h_v.clause_recall >= 0.8 else "Degraded on unseen dialogue"
                    )
                )
                all_md_parts.append(
                    f"| **{k}** | {d_v.clause_recall * 100:.1f}% ({d_v.total_hits}/{d_v.total_expected_clauses}) | "
                    f"{h_v.clause_recall * 100:.1f}% ({h_v.total_hits}/{h_v.total_expected_clauses}) | "
                    f"{d_v.avg_clauses_sent:.1f} | {h_v.avg_clauses_sent:.1f} | {assessment} |"
                )
        all_md_parts.append("")

    full_md = "\n".join(all_md_parts)
    summary_path.write_text(full_md, encoding="utf-8")

    if not quiet:
        print(full_md)

    ret_summaries = heldout_summaries if dataset_split == "heldout" else dev_summaries
    ret_mismatches = heldout_mismatches if dataset_split == "heldout" else dev_mismatches
    return ret_summaries, ret_mismatches, csv_path, summary_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate policy retrieval recall on labelled calls.")
    parser.add_argument(
        "--set",
        dest="dataset_split",
        choices=["dev", "heldout", "both"],
        default="both",
        help="Dataset split to evaluate: dev, heldout, or both (default: both)",
    )
    parser.add_argument("--expected", type=Path, default=None, help="Path to expected_results.json")
    parser.add_argument("--transcripts", type=Path, default=None, help="Path to transcripts directory")
    parser.add_argument("--results-dir", type=Path, default=ROOT / "eval" / "results", help="Directory for output CSV and summary")
    parser.add_argument("--quiet", action="store_true", help="Do not print summary to stdout")
    args = parser.parse_args()

    run_retrieval_eval(
        expected_path=args.expected,
        transcripts_dir=args.transcripts,
        results_dir=args.results_dir,
        quiet=args.quiet,
        dataset_split=args.dataset_split,
    )


if __name__ == "__main__":
    main()
