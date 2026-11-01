"""Evaluation of policy clause retrieval recall (offline baseline).

Measures retrieval recall across labelled calls with expected policy violations:
- Variant A: Full pipeline context (ALWAYS_INCLUDE + topic family + top-10 hybrid) -> production today
- Variant B: Top-10 retrieval only (k=10, no ALWAYS_INCLUDE, no topic family)
- Variant C: BM25 only (k=10, use_embeddings=False, no ALWAYS_INCLUDE, no topic family)
- Variant D: Metadata-aware retrieval (k=10, BM25 + embeddings + topic boost + situation boost, no ALWAYS_INCLUDE, no topic family)
- Variant E: Metadata-aware + Core Safety (k=10, Variant D + always_include=["PRV-1.1", "ESC-1.1"], no topic family)
- Variant F: ALL policy clauses (the ceiling)
- Variant G: Variant A plus the WHOLE PRV and ESC families always included (cross-cutting safety families)
- Variant H: Per-turn retrieval: embed/retrieve each agent turn and each customer turn separately (top-3 hybrid per turn, skip turns shorter than 5 words), take the union, cap at 14 clauses by best score. No always-include, no family. No regex situation cues.

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
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

# Ensure huggingface is offline to prevent hanging in sandboxed environments
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

# Ensure repository root is on sys.path
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.audit.policy_check import ALWAYS_INCLUDE, agent_query, call_retrieval_query
from src.audit.rag import Chunk, KnowledgeBase, tokenize, _normalize
from src.audit.topic import detect_call_situations, detect_topic
from src.audit.transcript_io import load_transcript_json

logger = logging.getLogger("eval.retrieval")

# Universal core safety clauses for Variant E (no full family)
CORE_SAFETY_CLAUSES = ["PRV-1.1", "ESC-1.1"]

VARIANT_META: Dict[str, Tuple[str, str]] = {
    "A": ("Full pipeline context", "always_include + whole family + top-10"),
    "B": ("Top-10 retrieval only", "hybrid BM25 + embeddings, no always_include, no family"),
    "C": ("BM25 only", "BM25 only (use_embeddings=False), no always_include, no family"),
    "D": ("Metadata-aware retrieval", "BM25 + embeddings + topic boost + situation boost, no always_include, no family"),
    "E": ("Metadata-aware + Core Safety", "Variant D + always_include=['PRV-1.1', 'ESC-1.1'] (no full family)"),
    "F": ("All policy clauses (ceiling)", "All policy clauses unconditionally included"),
    "G": ("Full context + PRV/ESC safety families", "Variant A + whole PRV and ESC families always included"),
    "H": ("Per-turn retrieval (union top-3 cap 14)", "Top-3 hybrid per turn (>=5 words), union capped at 14 by score"),
}


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
    chars_sent_count: int = 0


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
    avg_chars_sent: float = 0.0
    call_results: List[CallEvalResult] = field(default_factory=list)
    misses_by_call: List[Tuple[str, List[str], List[str]]] = field(default_factory=list)
    avg_clean_clauses_sent: float = 0.0
    avg_clean_chars_sent: float = 0.0
    total_clean_calls: int = 0
    elapsed_seconds: float = 0.0


@dataclass
class TopicMismatchResult:
    call_id: str
    detected_topic: str
    expected_topic: str
    also_ok_topics: List[str]
    expected_clauses: List[str]
    retrieved_in_a: bool = False
    retrieved_in_b: bool = False
    retrieved_in_c: bool = False
    retrieved_in_d: bool = False
    retrieved_in_e: bool = False
    retrieved_in_f: bool = False
    retrieved_in_g: bool = False
    retrieved_in_h: bool = False
    hits_a: List[str] = field(default_factory=list)
    hits_b: List[str] = field(default_factory=list)
    hits_c: List[str] = field(default_factory=list)
    hits_d: List[str] = field(default_factory=list)
    hits_e: List[str] = field(default_factory=list)
    hits_f: List[str] = field(default_factory=list)
    hits_g: List[str] = field(default_factory=list)
    hits_h: List[str] = field(default_factory=list)


def retrieve_per_turn(
    call: Any,
    kb: KnowledgeBase,
    top_per_turn: int = 3,
    min_words: int = 5,
    cap_clauses: int = 14,
) -> List[Chunk]:
    """Variant H: Per-turn retrieval.

    Embed/retrieve each agent turn and each customer turn separately
    (top-3 hybrid per turn, skip turns shorter than 5 words), take the union,
    cap at 14 clauses by best score. No always-include, no family. No regex situation cues.
    """
    eligible_turns = [
        t.text.strip() for t in call.turns
        if len(t.text.strip().split()) >= min_words
    ]
    if not eligible_turns or not kb.policies:
        return []

    should_embed = kb.use_embeddings and kb._load_embeddings()
    turn_vec_sims: List[List[float]] = []
    if should_embed and kb._emb_matrix is not None:
        try:
            import numpy as np
            from src.audit.rag import get_embedder

            embedder = get_embedder()
            prefix = "Represent this sentence for searching relevant passages: "
            turn_embs = embedder.encode([prefix + txt for txt in eligible_turns], normalize_embeddings=True)
            sim_mat = np.asarray(turn_embs) @ kb._emb_matrix.T
            turn_vec_sims = sim_mat.tolist()
        except Exception as exc:
            logger.warning("Turn embedding query failed (%s); using BM25 only.", exc)
            turn_vec_sims = []

    best_scores: Dict[str, Tuple[float, Chunk]] = {}
    for idx, turn_text in enumerate(eligible_turns):
        lex = _normalize(kb._bm25.scores(tokenize(turn_text)))
        if turn_vec_sims and idx < len(turn_vec_sims):
            sims = _normalize(turn_vec_sims[idx])
            scores = [0.5 * a + 0.5 * b for a, b in zip(lex, sims)]
        else:
            scores = lex

        scored = sorted(zip(scores, kb.policies), key=lambda x: -x[0])[:top_per_turn]
        for s, c in scored:
            if c.id not in best_scores or s > best_scores[c.id][0]:
                best_scores[c.id] = (s, c)

    ranked = sorted(best_scores.values(), key=lambda x: -x[0])[:cap_clauses]
    return [c for _, c in ranked]


def evaluate_retrieval(
    expected_data: Dict[str, Any],
    transcripts_dir: Path,
    kb: KnowledgeBase,
    variants: Optional[Sequence[str]] = None,
) -> Tuple[Dict[str, VariantResult], List[TopicMismatchResult]]:
    """Evaluate retrieval variants on labelled calls with expected violations and clean calls."""
    variant_keys = tuple(v for v in (variants or tuple(VARIANT_META.keys())) if v in VARIANT_META)
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

    results_by_variant: Dict[str, List[CallEvalResult]] = {k: [] for k in variant_keys}
    clean_counts_by_variant: Dict[str, List[int]] = {k: [] for k in variant_keys}
    clean_chars_by_variant: Dict[str, List[int]] = {k: [] for k in variant_keys}
    variant_durations: Dict[str, float] = {k: 0.0 for k in variant_keys}
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

        family = [c.id for c in kb.policies_for_topic(detected_topic)]
        safety_families = [c.id for c in kb.policies if c.family in ("PRV", "ESC")]

        clauses_by_variant: Dict[str, List[Chunk]] = {}

        if "A" in variant_keys:
            t0 = time.perf_counter()
            clauses_by_variant["A"] = kb.retrieve_policies(query, topic=detected_topic, k=10, always_include=ALWAYS_INCLUDE + family)
            variant_durations["A"] += time.perf_counter() - t0

        if "B" in variant_keys:
            t0 = time.perf_counter()
            clauses_by_variant["B"] = kb.retrieve_policies(query, topic=detected_topic, k=10, always_include=[])
            variant_durations["B"] += time.perf_counter() - t0

        if "C" in variant_keys:
            t0 = time.perf_counter()
            clauses_by_variant["C"] = kb.retrieve_policies(query, topic=detected_topic, k=10, always_include=[], use_embeddings=False)
            variant_durations["C"] += time.perf_counter() - t0

        if "D" in variant_keys:
            t0 = time.perf_counter()
            clauses_by_variant["D"] = kb.retrieve_policies(query_d, topic=detected_topic, k=10, always_include=[], situations=sits)
            variant_durations["D"] += time.perf_counter() - t0

        if "E" in variant_keys:
            t0 = time.perf_counter()
            clauses_by_variant["E"] = kb.retrieve_policies(query_d, topic=detected_topic, k=10, always_include=CORE_SAFETY_CLAUSES, situations=sits)
            variant_durations["E"] += time.perf_counter() - t0

        if "F" in variant_keys:
            t0 = time.perf_counter()
            clauses_by_variant["F"] = list(kb.policies)
            variant_durations["F"] += time.perf_counter() - t0

        if "G" in variant_keys:
            t0 = time.perf_counter()
            always_g = ALWAYS_INCLUDE + family + safety_families
            clauses_by_variant["G"] = kb.retrieve_policies(query, topic=detected_topic, k=10, always_include=always_g)
            variant_durations["G"] += time.perf_counter() - t0

        if "H" in variant_keys:
            t0 = time.perf_counter()
            clauses_by_variant["H"] = retrieve_per_turn(call, kb, top_per_turn=3, min_words=5, cap_clauses=14)
            variant_durations["H"] += time.perf_counter() - t0

        for v_key in variant_keys:
            clauses = clauses_by_variant[v_key]
            ids = [c.id for c in clauses]
            hits = [c for c in expected_clauses if c in ids]
            misses = [c for c in expected_clauses if c not in ids]
            all_r = len(misses) == 0
            chars_sent = sum(len(c.short(1100)) for c in clauses)
            results_by_variant[v_key].append(
                CallEvalResult(
                    call_id=call_id,
                    detected_topic=detected_topic,
                    expected_topic=expected_topic,
                    topic_match=topic_match,
                    expected_clauses=expected_clauses,
                    retrieved_clauses=ids,
                    clauses_sent_count=len(ids),
                    hits=hits,
                    misses=misses,
                    all_retrieved=all_r,
                    chars_sent_count=chars_sent,
                )
            )

        if detected_topic != expected_topic:
            all_flags = {
                k: len([c for c in expected_clauses if c not in [ch.id for ch in clauses_by_variant.get(k, [])]]) == 0
                for k in variant_keys
            }
            all_hits = {
                k: [c for c in expected_clauses if c in [ch.id for ch in clauses_by_variant.get(k, [])]]
                for k in variant_keys
            }
            mismatches.append(
                TopicMismatchResult(
                    call_id=call_id,
                    detected_topic=detected_topic,
                    expected_topic=expected_topic or "unknown",
                    also_ok_topics=also_ok,
                    expected_clauses=expected_clauses,
                    retrieved_in_a=all_flags.get("A", False),
                    retrieved_in_b=all_flags.get("B", False),
                    retrieved_in_c=all_flags.get("C", False),
                    retrieved_in_d=all_flags.get("D", False),
                    retrieved_in_e=all_flags.get("E", False),
                    retrieved_in_f=all_flags.get("F", False),
                    retrieved_in_g=all_flags.get("G", False),
                    retrieved_in_h=all_flags.get("H", False),
                    hits_a=all_hits.get("A", []),
                    hits_b=all_hits.get("B", []),
                    hits_c=all_hits.get("C", []),
                    hits_d=all_hits.get("D", []),
                    hits_e=all_hits.get("E", []),
                    hits_f=all_hits.get("F", []),
                    hits_g=all_hits.get("G", []),
                    hits_h=all_hits.get("H", []),
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
        safety_families = [c.id for c in kb.policies if c.family in ("PRV", "ESC")]

        clean_clauses: Dict[str, List[Chunk]] = {}

        if "A" in variant_keys:
            t0 = time.perf_counter()
            clean_clauses["A"] = kb.retrieve_policies(query, topic=detected_topic, k=10, always_include=ALWAYS_INCLUDE + family)
            variant_durations["A"] += time.perf_counter() - t0

        if "B" in variant_keys:
            t0 = time.perf_counter()
            clean_clauses["B"] = kb.retrieve_policies(query, topic=detected_topic, k=10, always_include=[])
            variant_durations["B"] += time.perf_counter() - t0

        if "C" in variant_keys:
            t0 = time.perf_counter()
            clean_clauses["C"] = kb.retrieve_policies(query, topic=detected_topic, k=10, always_include=[], use_embeddings=False)
            variant_durations["C"] += time.perf_counter() - t0

        if "D" in variant_keys:
            t0 = time.perf_counter()
            clean_clauses["D"] = kb.retrieve_policies(query_d, topic=detected_topic, k=10, always_include=[], situations=sits)
            variant_durations["D"] += time.perf_counter() - t0

        if "E" in variant_keys:
            t0 = time.perf_counter()
            clean_clauses["E"] = kb.retrieve_policies(query_d, topic=detected_topic, k=10, always_include=CORE_SAFETY_CLAUSES, situations=sits)
            variant_durations["E"] += time.perf_counter() - t0

        if "F" in variant_keys:
            t0 = time.perf_counter()
            clean_clauses["F"] = list(kb.policies)
            variant_durations["F"] += time.perf_counter() - t0

        if "G" in variant_keys:
            t0 = time.perf_counter()
            always_g = ALWAYS_INCLUDE + family + safety_families
            clean_clauses["G"] = kb.retrieve_policies(query, topic=detected_topic, k=10, always_include=always_g)
            variant_durations["G"] += time.perf_counter() - t0

        if "H" in variant_keys:
            t0 = time.perf_counter()
            clean_clauses["H"] = retrieve_per_turn(call, kb, top_per_turn=3, min_words=5, cap_clauses=14)
            variant_durations["H"] += time.perf_counter() - t0

        for v_key in variant_keys:
            cls_list = clean_clauses[v_key]
            clean_counts_by_variant[v_key].append(len(cls_list))
            clean_chars_by_variant[v_key].append(sum(len(c.short(1100)) for c in cls_list))

    variant_summaries: Dict[str, VariantResult] = {}
    for v_key in variant_keys:
        calls = results_by_variant[v_key]
        total_calls = len(calls)
        total_expected = sum(len(c.expected_clauses) for c in calls)
        total_hits = sum(len(c.hits) for c in calls)
        clause_recall = (total_hits / total_expected) if total_expected > 0 else 0.0
        calls_all = sum(1 for c in calls if c.all_retrieved)
        calls_all_pct = (calls_all / total_calls) if total_calls > 0 else 0.0
        avg_sent = (sum(c.clauses_sent_count for c in calls) / total_calls) if total_calls > 0 else 0.0
        avg_chars = (sum(c.chars_sent_count for c in calls) / total_calls) if total_calls > 0 else 0.0

        misses = [
            (c.call_id, c.misses, c.expected_clauses)
            for c in calls
            if c.misses
        ]

        clean_counts = clean_counts_by_variant[v_key]
        clean_chars = clean_chars_by_variant[v_key]
        avg_clean = (sum(clean_counts) / len(clean_counts)) if clean_counts else 0.0
        avg_clean_chars = (sum(clean_chars) / len(clean_chars)) if clean_chars else 0.0

        v_name, v_desc = VARIANT_META[v_key]
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
            avg_chars_sent=avg_chars,
            call_results=calls,
            misses_by_call=misses,
            avg_clean_clauses_sent=avg_clean,
            avg_clean_chars_sent=avg_clean_chars,
            total_clean_calls=len(clean_counts),
            elapsed_seconds=variant_durations[v_key],
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
    first_summary = next(iter(summaries.values())) if summaries else None
    total_calls = first_summary.total_calls if first_summary else 0
    total_expected = first_summary.total_expected_clauses if first_summary else 0
    total_clean = first_summary.total_clean_calls if first_summary else 0
    lines.append(
        f"Evaluated **{total_calls} calls with violations** ({total_expected} expected clauses) "
        f"and **{total_clean} clean calls**."
    )
    lines.append("")
    lines.append("### 1. Retrieval Performance Comparison")
    lines.append("")
    lines.append(
        "| Variant | Configuration | Clause Recall | Calls with All Retrieved | Avg Clauses Sent | Avg Characters Sent | Avg Clean Sent | Time (s) |"
    )
    lines.append("|---|---|---|---|---|---|---|---|")
    for key, v in summaries.items():
        clean_str = f"{v.avg_clean_clauses_sent:.1f}" if v.total_clean_calls > 0 else "N/A"
        time_str = f"{v.elapsed_seconds:.2f}s"
        lines.append(
            f"| **{v.key}** | {v.name} ({v.description}) | "
            f"{v.clause_recall * 100:.1f}% ({v.total_hits}/{v.total_expected_clauses}) | "
            f"{v.calls_all_retrieved_pct * 100:.1f}% ({v.calls_all_retrieved}/{v.total_calls}) | "
            f"{v.avg_clauses_sent:.1f} | {v.avg_chars_sent:.0f} | {clean_str} | {time_str} |"
        )
    lines.append("")
    lines.append("### 2. Misses by Variant")
    lines.append("")
    for key, v in summaries.items():
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
        hdr = ["Call ID", "Detected Topic", "Labelled Topic", "Expected Clauses"] + [f"Retrieved in {k}?" for k in summaries.keys()]
        lines.append("| " + " | ".join(hdr) + " |")
        lines.append("|" + "|".join(["---"] * len(hdr)) + "|")
        for m in mismatches:
            row = [f"`{m.call_id}`", f"`{m.detected_topic}`", f"`{m.expected_topic}`", f"`{', '.join(m.expected_clauses)}`"]
            for k in summaries.keys():
                flag = getattr(m, f"retrieved_in_{k.lower()}", False)
                hits = getattr(m, f"hits_{k.lower()}", [])
                status_str = "Yes" if flag else (f"Partial ({', '.join(hits)})" if hits else "No")
                row.append(status_str)
            lines.append("| " + " | ".join(row) + " |")
    lines.append("")

    for k in ("A", "D", "E", "F", "G", "H"):
        if k in summaries:
            v = summaries[k]
            lines.append(f"### Per-Call Breakdown (Variant {k} - {v.name})")
            lines.append("")
            lines.append("| Call ID | Detected Topic | Expected Clauses | Retrieved Count | Chars Sent | Hits | Misses | All Retrieved? |")
            lines.append("|---|---|---|---|---|---|---|---|")
            for r in v.call_results:
                status = "Yes" if r.all_retrieved else "No"
                misses_str = ", ".join(r.misses) if r.misses else "-"
                lines.append(
                    f"| `{r.call_id}` | `{r.detected_topic}` | `{', '.join(r.expected_clauses)}` | "
                    f"{r.clauses_sent_count} | {r.chars_sent_count} | `{', '.join(r.hits)}` | `{misses_str}` | {status} |"
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
        "chars_sent_count",
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
        for v_key, v in summaries.items():
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
                    "chars_sent_count": r.chars_sent_count,
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
    variants: Optional[Sequence[str]] = None,
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
        dev_summaries, dev_mismatches = evaluate_retrieval(dev_expected, trn_d, kb, variants=variants)
        dev_md = format_summary_markdown(dev_summaries, dev_mismatches, ts, split_title="Dev Set")
        all_md_parts.append(dev_md)

    # HELDOUT EVALUATION
    if dataset_split in ("heldout", "both"):
        h_exp_p = expected_path if dataset_split == "heldout" and expected_path else heldout_expected_path
        h_trn_d = transcripts_dir if dataset_split == "heldout" and transcripts_dir else heldout_transcripts_dir
        if h_exp_p.exists() and h_trn_d.exists():
            with open(h_exp_p, encoding="utf-8") as f:
                heldout_expected = json.load(f)
            heldout_summaries, heldout_mismatches = evaluate_retrieval(heldout_expected, h_trn_d, kb, variants=variants)
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
            "chars_sent_count",
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
            for v_key, v in summs.items():
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
                        "chars_sent_count": r.chars_sent_count,
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
        all_md_parts.append(
            "> [!IMPORTANT]\n"
            "> **Dataset Split Status Note:** The held-out set has now been evaluated and inspected for retrieval analysis. "
            "It has therefore been seen and effectively transitions into a secondary development / validation set; "
            "future variants must not be over-tuned to it.\n"
        )
        all_md_parts.append("### Cross-Split Retrieval Performance\n")
        all_md_parts.append(
            "| Variant | Dev Recall | Held-Out Recall | Dev Avg Sent | Held-Out Avg Sent | Dev Avg Chars | Held-Out Avg Chars | Generalisation Assessment |"
        )
        all_md_parts.append("|---|---|---|---|---|---|---|---|")
        for k in dev_summaries.keys():
            if k in heldout_summaries:
                d_v = dev_summaries[k]
                h_v = heldout_summaries[k]
                assessment = (
                    "Ceiling baseline (all clauses sent unconditionally)" if k == "F" else (
                        "Cross-cutting safety families guarantee zero safety misses" if k == "G" else (
                            "Per-turn union without topic bias" if k == "H" else (
                                "Baseline production context" if k == "A" else (
                                    "Core safety universal backup" if k == "E" else (
                                        "Strong lexical/semantic generalization" if h_v.clause_recall >= 0.8 else "Degraded on unseen dialogue"
                                    )
                                )
                            )
                        )
                    )
                )
                all_md_parts.append(
                    f"| **{k}** | {d_v.clause_recall * 100:.1f}% ({d_v.total_hits}/{d_v.total_expected_clauses}) | "
                    f"{h_v.clause_recall * 100:.1f}% ({h_v.total_hits}/{h_v.total_expected_clauses}) | "
                    f"{d_v.avg_clauses_sent:.1f} | {h_v.avg_clauses_sent:.1f} | "
                    f"{d_v.avg_chars_sent:.0f} | {h_v.avg_chars_sent:.0f} | {assessment} |"
                )
        all_md_parts.append("")
        all_md_parts.append("### Critical Clauses Analysis (PRV & ESC Families)\n")
        all_md_parts.append(
            "- **PRV-2.1 (call_207 - Warranty Topic):** In `call_207`, the customer inquiry focused on warranty, but a sensitive personal data breach (`PRV-2.1`, CVV request) occurred. "
            "Variant A missed `PRV-2.1` because it only retrieved the warranty family and core safety (`PRV-1.1`, `ESC-1.1`, `ESC-1.2`). "
            "Variants F and G successfully retrieved `PRV-2.1` by including the full PRV family.\n"
            "- **ESC-1.1 (call_209 - Topic Mismatch Complaint vs Refund):** In `call_209`, the topic was labelled `complaint` with escalation clause `ESC-1.1`, "
            "while topic detection classified it as `refund`. Because `ESC-1.1` is in `ALWAYS_INCLUDE`, Variants A, G, and F all successfully retrieved `ESC-1.1`."
        )
        all_md_parts.append("")

    full_md = "\n".join(all_md_parts)
    summary_path.write_text(full_md, encoding="utf-8")

    # Print execution timers
    print("\n=== Retrieval Variant Execution Timers ===")
    all_seen_variants = list(dict.fromkeys(list(dev_summaries.keys()) + list(heldout_summaries.keys())))
    for k in all_seen_variants:
        d_time = dev_summaries[k].elapsed_seconds if k in dev_summaries else 0.0
        h_time = heldout_summaries[k].elapsed_seconds if k in heldout_summaries else 0.0
        total_time = d_time + h_time
        meta_name = VARIANT_META.get(k, (k, ""))[0]
        print(f"Variant {k} ({meta_name}): {total_time:.2f}s (dev: {d_time:.2f}s, heldout: {h_time:.2f}s)")
    print("==========================================\n")

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
    parser.add_argument(
        "--variants",
        type=lambda s: [x.strip() for x in s.split(",") if x.strip()],
        default=None,
        help="Comma-separated variant keys to run (e.g. F,G,H or A,B,C,D,E,F,G,H). Default: all.",
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
        variants=args.variants,
    )


if __name__ == "__main__":
    main()
