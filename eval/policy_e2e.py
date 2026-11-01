"""End-to-End Policy Evaluation (A vs G vs F).

Evaluates the policy compliance LLM step (check_policies) across:
- Variant A: Production retrieval context (ALWAYS_INCLUDE + topic family + top-10 hybrid)
- Variant G: Variant A + whole PRV and ESC families always included
- Variant F: ALL policy clauses (the ceiling)

Settings:
- ONLY policy step (no audio, no transcript generation, no SOP checklist, no audit cache)
- Temperature 0.0, max_output_tokens 6144
- Turn-level matching on (call, turn) with acceptable alternates (REF-3.1 and BIL-2.2 equivalent)
- Tracks exact token usage and latency per request
- Evaluates on both Dev and Held-Out sets

Outputs:
- eval/results/policy_e2e.csv
- eval/results/policy_e2e.md
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import sys
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple, Union

# Prevent HuggingFace Hub network checks from hanging in offline / sandboxed runs
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

# Ensure repository root is on sys.path
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.audit.llm import (
    FatalLLMError,
    GeminiProvider,
    LLMGateway,
    OpenAICompatProvider,
    QuotaExhaustedError,
    RateLimitedError,
    gemini_gateway,
)
from src.audit.policy_check import (
    ALWAYS_INCLUDE,
    SYSTEM,
    agent_query,
    build_prompt,
    materialize_policy_results,
)
from src.audit.rag import Chunk, KnowledgeBase
from src.audit.schemas import CallTranscript, PolicyAnalysis, PolicyResult
from src.audit.topic import detect_topic
from src.audit.transcript_io import load_transcript_json

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("eval.policy_e2e")


# --------------------------------------------------------------------------------------
# Acceptable Alternates & Turn-Level Matching
# --------------------------------------------------------------------------------------
ACCEPTABLE_ALTERNATES: Dict[str, Set[str]] = {
    "REF-3.1": {"BIL-2.2"},
    "BIL-2.2": {"REF-3.1"},
}


def get_allowed_clauses(clause_id: str) -> Set[str]:
    """Return the set of acceptable clause IDs for a given expected clause."""
    return {clause_id} | ACCEPTABLE_ALTERNATES.get(clause_id, set())


@dataclass(frozen=True)
class ExpectedViolation:
    clause: str
    turn: Optional[int] = None
    severity: str = "major"


def match_violations_turn_level(
    expected_list: Sequence[Union[ExpectedViolation, dict, str]],
    found_violations: Sequence[PolicyResult],
) -> Tuple[List[str], List[str], List[PolicyResult]]:
    """Match expected violations against found violations at the turn level.

    An expected violation E matches found violation F if:
      (E.turn is None or F.turn == E.turn) and F.clause_id in get_allowed_clauses(E.clause)

    Each found violation can match at most one expected violation.
    """
    parsed_expected: List[ExpectedViolation] = []
    for item in expected_list:
        if isinstance(item, ExpectedViolation):
            parsed_expected.append(item)
        elif isinstance(item, dict):
            parsed_expected.append(
                ExpectedViolation(
                    clause=item.get("clause") or item.get("clause_id", ""),
                    turn=item.get("turn"),
                    severity=item.get("severity", "major"),
                )
            )
        elif isinstance(item, str):
            parsed_expected.append(ExpectedViolation(clause=item, turn=None))

    matched_expected: List[str] = []
    missed_expected: List[str] = []
    unmatched_found: List[PolicyResult] = list(found_violations)

    for exp in parsed_expected:
        allowed = get_allowed_clauses(exp.clause)
        match_idx = None
        matched_clause_name = None
        for idx, f in enumerate(unmatched_found):
            turn_matches = (exp.turn is None) or (f.turn is not None and f.turn == exp.turn)
            if turn_matches and f.clause_id in allowed:
                match_idx = idx
                matched_clause_name = f.clause_id
                break

        desc = f"{exp.clause} (turn {exp.turn})" if exp.turn is not None else exp.clause
        if match_idx is not None:
            if matched_clause_name != exp.clause:
                desc += f" [matched as {matched_clause_name}]"
            matched_expected.append(desc)
            unmatched_found.pop(match_idx)
        else:
            missed_expected.append(desc)

    extra_violations = unmatched_found
    return matched_expected, missed_expected, extra_violations


# --------------------------------------------------------------------------------------
# Token & Latency Tracker Hook
# --------------------------------------------------------------------------------------
@dataclass
class UsageRecord:
    prompt_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    latency_s: float = 0.0


class GatewayUsageTracker:
    """Intercepts low-level LLM calls on gemini_gateway to track exact token usage."""

    def __init__(self, gateway: LLMGateway):
        self.gateway = gateway
        self.last_record = UsageRecord()
        self._installed = False
        self._orig_genai_generate: Optional[Any] = None

    def install(self) -> None:
        if self._installed:
            return
        for target in self.gateway.targets:
            if isinstance(target, GeminiProvider):
                target.ready_check()
                client = target.client
                if hasattr(client, "models") and hasattr(client.models, "generate_content"):
                    self._orig_genai_generate = client.models.generate_content

                    def make_hook(orig_fn):
                        def hooked_generate(*args, **kwargs):
                            resp = orig_fn(*args, **kwargs)
                            um = getattr(resp, "usage_metadata", None)
                            if um:
                                self.last_record.prompt_tokens = getattr(um, "prompt_token_count", 0) or 0
                                self.last_record.output_tokens = getattr(um, "candidates_token_count", 0) or 0
                                self.last_record.total_tokens = getattr(um, "total_token_count", 0) or 0
                            return resp
                        return hooked_generate

                    client.models.generate_content = make_hook(self._orig_genai_generate)
        self._installed = True

    def reset_record(self) -> None:
        self.last_record = UsageRecord()


# --------------------------------------------------------------------------------------
# Data Structures
# --------------------------------------------------------------------------------------
@dataclass
class SingleRunResult:
    split: str
    call_id: str
    variant: str
    detected_topic: str
    clauses_sent_count: int
    clauses_sent_ids: List[str]
    expected_clauses: List[str]
    found_violations: List[PolicyResult]
    found_clause_ids: List[str]
    matched_clauses: List[str]
    missed_clauses: List[str]
    all_expected_found: bool
    extra_violations: List[PolicyResult]
    input_tokens: int
    output_tokens: int
    total_tokens: int
    latency_s: float
    run_idx: int = 1


@dataclass
class VariantAggregates:
    variant: str
    split: str
    total_calls: int
    total_expected_violations: int
    total_matched_violations: int
    recall: float
    fully_covered_calls: int
    fully_covered_pct: float
    total_extra_findings: int
    clean_calls_total: int
    clean_calls_correct: int
    avg_input_tokens: float
    avg_output_tokens: float
    avg_total_tokens: float
    avg_latency_s: float
    avg_clauses_sent: float


# --------------------------------------------------------------------------------------
# Policy Clauses Selection per Variant
# --------------------------------------------------------------------------------------
def get_variant_clauses(
    variant: str,
    call: CallTranscript,
    detected_topic: str,
    kb: KnowledgeBase,
) -> List[Chunk]:
    """Retrieve or construct the policy clause list for a variant."""
    query = agent_query(call)
    family = [c.id for c in kb.policies_for_topic(detected_topic)]
    safety_families = [c.id for c in kb.policies if c.family in ("PRV", "ESC")]

    if variant == "A":
        return kb.retrieve_policies(
            query,
            topic=detected_topic,
            k=10,
            always_include=ALWAYS_INCLUDE + family,
        )
    elif variant == "G":
        always_g = ALWAYS_INCLUDE + family + safety_families
        return kb.retrieve_policies(
            query,
            topic=detected_topic,
            k=10,
            always_include=always_g,
        )
    elif variant == "F":
        return list(kb.policies)
    else:
        raise ValueError(f"Unknown variant: {variant}")


# --------------------------------------------------------------------------------------
# Run Single LLM Policy Check Step
# --------------------------------------------------------------------------------------
def execute_policy_step(
    split: str,
    call_id: str,
    call: CallTranscript,
    variant: str,
    expected_clauses: Sequence[Union[dict, ExpectedViolation, str]],
    kb: KnowledgeBase,
    gateway: LLMGateway,
    tracker: GatewayUsageTracker,
    run_idx: int = 1,
) -> SingleRunResult:
    """Execute ONLY the check_policies step for a given call and variant."""
    detected_topic = detect_topic(call.turns).topic
    clauses = get_variant_clauses(variant, call, detected_topic, kb)
    clauses_sent_ids = [c.id for c in clauses]

    prompt = build_prompt(call, clauses)

    tracker.reset_record()
    t0 = time.perf_counter()

    call_tag = f"{call_id}_{variant}_run{run_idx}" if run_idx > 1 else f"{call_id}_{variant}"

    analysis = gateway.generate_structured(
        prompt,
        PolicyAnalysis,
        system_instruction=SYSTEM,
        temperature=0.0,
        max_output_tokens=6144,
        call_id=call_tag,
    )
    latency_s = time.perf_counter() - t0

    rec = tracker.last_record
    input_tokens = rec.prompt_tokens or (len(prompt) // 4)
    output_tokens = rec.output_tokens or 0
    total_tokens = rec.total_tokens or (input_tokens + output_tokens)

    print(
        f"[Run {run_idx} | {split.upper()}] {call_id} | Variant {variant}: "
        f"{input_tokens:,} input tokens, {output_tokens:,} output tokens, {total_tokens:,} total | "
        f"Latency: {latency_s:.2f}s | Clauses sent: {len(clauses)}"
    )

    results, warnings = materialize_policy_results(call, analysis, clauses, kb)
    violations = [r for r in results if r.verdict == "violation"]
    found_clause_ids = [r.clause_id for r in violations]

    # Turn-level matching with acceptable alternates
    matched_clauses, missed_clauses, extra_violations = match_violations_turn_level(
        expected_clauses, violations
    )
    all_expected_found = len(missed_clauses) == 0

    expected_str_list = []
    for exp in expected_clauses:
        if isinstance(exp, dict):
            c = exp.get("clause") or exp.get("clause_id", "")
            t = exp.get("turn")
            expected_str_list.append(f"{c} (turn {t})" if t is not None else c)
        elif isinstance(exp, ExpectedViolation):
            expected_str_list.append(f"{exp.clause} (turn {exp.turn})" if exp.turn is not None else exp.clause)
        else:
            expected_str_list.append(str(exp))

    return SingleRunResult(
        split=split,
        call_id=call_id,
        variant=variant,
        detected_topic=detected_topic,
        clauses_sent_count=len(clauses),
        clauses_sent_ids=clauses_sent_ids,
        expected_clauses=expected_str_list,
        found_violations=violations,
        found_clause_ids=found_clause_ids,
        matched_clauses=matched_clauses,
        missed_clauses=missed_clauses,
        all_expected_found=all_expected_found,
        extra_violations=extra_violations,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        latency_s=latency_s,
        run_idx=run_idx,
    )


# --------------------------------------------------------------------------------------
# Aggregation & Scoring
# --------------------------------------------------------------------------------------
def compute_aggregates(runs: List[SingleRunResult], variant: str, split: str) -> VariantAggregates:
    subset = [r for r in runs if r.variant == variant and (split == "both" or r.split == split)]
    total_calls = len(subset)
    if total_calls == 0:
        return VariantAggregates(
            variant=variant, split=split, total_calls=0, total_expected_violations=0,
            total_matched_violations=0, recall=0.0, fully_covered_calls=0, fully_covered_pct=0.0,
            total_extra_findings=0, clean_calls_total=0, clean_calls_correct=0,
            avg_input_tokens=0.0, avg_output_tokens=0.0, avg_total_tokens=0.0,
            avg_latency_s=0.0, avg_clauses_sent=0.0,
        )

    total_expected = sum(len(r.expected_clauses) for r in subset)
    total_matched = sum(len(r.matched_clauses) for r in subset)
    recall = round(total_matched / total_expected, 4) if total_expected > 0 else 1.0

    violation_calls = [r for r in subset if len(r.expected_clauses) > 0]
    fully_covered = sum(1 for r in violation_calls if r.all_expected_found)
    fully_covered_pct = round(fully_covered / len(violation_calls) * 100, 1) if violation_calls else 100.0

    clean_calls = [r for r in subset if len(r.expected_clauses) == 0]
    clean_calls_correct = sum(1 for r in clean_calls if len(r.found_violations) == 0)

    total_extra = sum(len(r.extra_violations) for r in subset)
    avg_input = sum(r.input_tokens for r in subset) / total_calls
    avg_output = sum(r.output_tokens for r in subset) / total_calls
    avg_total = sum(r.total_tokens for r in subset) / total_calls
    avg_lat = sum(r.latency_s for r in subset) / total_calls
    avg_clauses = sum(r.clauses_sent_count for r in subset) / total_calls

    return VariantAggregates(
        variant=variant,
        split=split,
        total_calls=total_calls,
        total_expected_violations=total_expected,
        total_matched_violations=total_matched,
        recall=recall,
        fully_covered_calls=fully_covered,
        fully_covered_pct=fully_covered_pct,
        total_extra_findings=total_extra,
        clean_calls_total=len(clean_calls),
        clean_calls_correct=clean_calls_correct,
        avg_input_tokens=round(avg_input, 1),
        avg_output_tokens=round(avg_output, 1),
        avg_total_tokens=round(avg_total, 1),
        avg_latency_s=round(avg_lat, 2),
        avg_clauses_sent=round(avg_clauses, 1),
    )


# --------------------------------------------------------------------------------------
# Export Results (CSV & Markdown)
# --------------------------------------------------------------------------------------
def write_csv_report(runs: List[SingleRunResult], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "run_idx",
        "split",
        "call_id",
        "variant",
        "detected_topic",
        "clauses_sent_count",
        "expected_clauses_count",
        "expected_clauses",
        "found_violations_count",
        "found_clauses",
        "matched_count",
        "matched_clauses",
        "missed_count",
        "missed_clauses",
        "all_expected_found",
        "extra_count",
        "extra_clauses",
        "extra_violations_details",
        "input_tokens",
        "output_tokens",
        "total_tokens",
        "latency_s",
    ]
    with open(output_path, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in runs:
            extra_details = [
                {
                    "clause_id": ev.clause_id,
                    "turn": ev.turn,
                    "quote": ev.quote,
                    "severity": ev.severity,
                    "explanation": ev.explanation,
                }
                for ev in r.extra_violations
            ]
            extra_clause_strs = [
                f"{ev.clause_id} (turn {ev.turn})" if ev.turn is not None else ev.clause_id
                for ev in r.extra_violations
            ]
            writer.writerow({
                "run_idx": r.run_idx,
                "split": r.split,
                "call_id": r.call_id,
                "variant": r.variant,
                "detected_topic": r.detected_topic,
                "clauses_sent_count": r.clauses_sent_count,
                "expected_clauses_count": len(r.expected_clauses),
                "expected_clauses": "; ".join(r.expected_clauses),
                "found_violations_count": len(r.found_violations),
                "found_clauses": "; ".join(r.found_clause_ids),
                "matched_count": len(r.matched_clauses),
                "matched_clauses": "; ".join(r.matched_clauses),
                "missed_count": len(r.missed_clauses),
                "missed_clauses": "; ".join(r.missed_clauses),
                "all_expected_found": r.all_expected_found,
                "extra_count": len(r.extra_violations),
                "extra_clauses": "; ".join(extra_clause_strs),
                "extra_violations_details": json.dumps(extra_details, ensure_ascii=False),
                "input_tokens": r.input_tokens,
                "output_tokens": r.output_tokens,
                "total_tokens": r.total_tokens,
                "latency_s": round(r.latency_s, 2),
            })
    logger.info("Saved CSV results to %s", output_path)


def generate_markdown_report(
    runs: List[SingleRunResult],
    model_name: str,
    output_path: Path,
) -> str:
    run_indices = sorted(list(dict.fromkeys(r.run_idx for r in runs)))
    variants = sorted(list(dict.fromkeys(r.variant for r in runs)))

    lines: List[str] = []
    lines.append("# End-to-End Policy Evaluation Report (Turn-Level Matching)\n")
    lines.append(f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  ")
    lines.append(f"**Model:** `{model_name}`  ")
    lines.append(f"**Execution Mode:** ONLY `check_policies` (temperature 0.0, no audit cache, no other pipeline steps)  ")
    lines.append(f"**Scoring Paradigm:** Turn-Level Matching on `(call, turn)` with acceptable alternates (`REF-3.1` $\\iff$ `BIL-2.2`)\n")

    lines.append("> [!IMPORTANT]")
    lines.append(
        "> **Evaluation Notes:**\n"
        "> 1. **Held-Out Label Corrections Applied:** Held-out expected violations were updated to resolve synonymy/granularity discrepancies (e.g. `BIL-2.1`/`BIL-2.3` in `call_204`, removing repeated `ESC-2.1` in `call_205`, `PRV-2.1` in `call_207`, `BIL-3.1`/`ESC-1.1` in `call_208`, `ESC-1.1` in `call_209`).\n"
        "> 2. **Turn-Level Scoring:** Both clause ID (or acceptable alternate) AND transcript turn must match to qualify as an expected hit.\n"
    )

    # 1. Multi-Run Repeatability Table
    if len(run_indices) > 1:
        lines.append("## 1. Multi-Run Repeatability & Performance Summary\n")
        lines.append("| Run | Variant | Dev Recall | Held-Out Recall | Combined Recall | Full Call Coverage | Extras (Dev / Held / Total) | Avg Latency |")
        lines.append("|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|")

        for r_i in run_indices:
            r_subset = [r for r in runs if r.run_idx == r_i]
            for v in variants:
                d_agg = compute_aggregates(r_subset, v, "dev")
                h_agg = compute_aggregates(r_subset, v, "heldout")
                b_agg = compute_aggregates(r_subset, v, "both")

                dev_rec = f"{d_agg.total_matched_violations}/{d_agg.total_expected_violations} ({d_agg.recall:.1%})"
                held_rec = f"{h_agg.total_matched_violations}/{h_agg.total_expected_violations} ({h_agg.recall:.1%})"
                comb_rec = f"{b_agg.total_matched_violations}/{b_agg.total_expected_violations} ({b_agg.recall:.1%})"
                cov = f"{b_agg.fully_covered_calls}/{b_agg.total_calls - b_agg.clean_calls_total} ({b_agg.fully_covered_pct:.1f}%)"
                extras_str = f"{d_agg.total_extra_findings} / {h_agg.total_extra_findings} / {b_agg.total_extra_findings}"
                lines.append(
                    f"| Run {r_i} | **{v}** | {dev_rec} | {held_rec} | **{comb_rec}** | {cov} | {extras_str} | {b_agg.avg_latency_s:.2f}s |"
                )
        lines.append("")

        # 2. Persistent Misses Analysis
        lines.append("## 2. Persistent Misses Analysis (Repeating across All Runs)\n")
        lines.append(
            "An expected violation is **persistent** if the model failed to detect it on that exact turn in **all 3 independent runs**.\n"
        )

        for v in variants:
            lines.append(f"### Variant {v} Persistent Misses\n")
            v_runs = [r for r in runs if r.variant == v]
            calls_in_v = sorted(list(dict.fromkeys(r.call_id for r in v_runs)))

            misses_by_run: Dict[str, List[Set[str]]] = defaultdict(list)
            for r_i in run_indices:
                r_calls = {r.call_id: set(r.missed_clauses) for r in v_runs if r.run_idx == r_i}
                for cid in calls_in_v:
                    misses_by_run[cid].append(r_calls.get(cid, set()))

            persistent_misses: List[Tuple[str, str, str]] = []
            sporadic_misses: List[Tuple[str, str, str, int]] = []

            for cid in calls_in_v:
                run_miss_sets = misses_by_run[cid]
                if not run_miss_sets:
                    continue
                all_repeat = set.intersection(*run_miss_sets) if run_miss_sets else set()
                any_miss = set.union(*run_miss_sets) if run_miss_sets else set()
                sample_r = next(r for r in v_runs if r.call_id == cid)

                for m in sorted(all_repeat):
                    persistent_misses.append((sample_r.split, cid, m))
                for m in sorted(any_miss - all_repeat):
                    count = sum(1 for s in run_miss_sets if m in s)
                    sporadic_misses.append((sample_r.split, cid, m, count))

            if persistent_misses:
                lines.append(f"**Persistent Misses ({len(persistent_misses)} total — missed in ALL {len(run_indices)} runs):**\n")
                lines.append("| Split | Call ID | Expected Clause & Turn | Status |")
                lines.append("|:---:|:---:|:---|:---:|")
                for sp, cid, m in persistent_misses:
                    lines.append(f"| {sp} | `{cid}` | `{m}` | Repeated in {len(run_indices)}/{len(run_indices)} runs |")
                lines.append("")
            else:
                lines.append(f"*Zero persistent misses for Variant {v} across all {len(run_indices)} runs!*\n")

            if sporadic_misses:
                lines.append(f"**Sporadic Misses ({len(sporadic_misses)} total — missed in 1 or 2 runs):**\n")
                lines.append("| Split | Call ID | Expected Clause & Turn | Frequency |")
                lines.append("|:---:|:---:|:---|:---:|")
                for sp, cid, m, cnt in sporadic_misses:
                    lines.append(f"| {sp} | `{cid}` | `{m}` | Missed in {cnt}/{len(run_indices)} runs |")
                lines.append("")

    # Executive Summary (Mean / Overall)
    lines.append("## 3. Executive Summary Tables (Overall Averages)\n")

    def render_table(aggs: List[VariantAggregates], title: str) -> None:
        lines.append(f"### {title}\n")
        lines.append("| Variant | Expected Violations Found | Full Call Coverage | Extra Findings (False Positives) | Avg Clauses Sent | Avg Input Tokens | Avg Latency |")
        lines.append("|:---|:---:|:---:|:---:|:---:|:---:|:---:|")
        for a in aggs:
            v_desc = f"Variant {a.variant}"
            recall_str = f"{a.total_matched_violations}/{a.total_expected_violations} ({a.recall:.1%})"
            cov_str = f"{a.fully_covered_calls}/{a.total_calls - a.clean_calls_total} ({a.fully_covered_pct:.1f}%)" if (a.total_calls - a.clean_calls_total) > 0 else "N/A"
            lines.append(
                f"| **{v_desc}** | {recall_str} | {cov_str} | {a.total_extra_findings} | {a.avg_clauses_sent:.1f} | {a.avg_input_tokens:,.0f} | {a.avg_latency_s:.2f}s |"
            )
        lines.append("")

    dev_aggs = [compute_aggregates(runs, v, "dev") for v in variants]
    heldout_aggs = [compute_aggregates(runs, v, "heldout") for v in variants]
    overall_aggs = [compute_aggregates(runs, v, "both") for v in variants]

    dev_calls_count = dev_aggs[0].total_calls if dev_aggs else 0
    heldout_calls_count = heldout_aggs[0].total_calls if heldout_aggs else 0
    overall_calls_count = overall_aggs[0].total_calls if overall_aggs else 0

    render_table(dev_aggs, f"Dev Set ({dev_calls_count} Calls)")
    render_table(heldout_aggs, f"Held-Out Set ({heldout_calls_count} Calls)")
    render_table(overall_aggs, f"Combined Sets ({overall_calls_count} Calls Total)")

    # 4. Extra Findings Table
    lines.append("## 4. Extra Findings (False-Positive Risk)\n")
    all_extras: List[Tuple[int, str, str, str, PolicyResult]] = []
    for r in runs:
        for ev in r.extra_violations:
            all_extras.append((r.run_idx, r.split, r.call_id, r.variant, ev))

    if not all_extras:
        lines.append("*No extra findings detected across all runs.*\n")
    else:
        lines.append(f"Total extra findings recorded across all runs: **{len(all_extras)}**\n")
        lines.append("| Run | Split | Call ID | Variant | Clause ID | Severity | Turn | Agent Quote | Model Explanation |")
        lines.append("|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---|:---|")
        for r_i, split, cid, v_key, ev in all_extras:
            clean_quote = ev.quote.replace("\n", " ").replace("|", "\\|")[:80]
            clean_expl = ev.explanation.replace("\n", " ").replace("|", "\\|")[:120]
            lines.append(
                f"| Run {r_i} | {split} | `{cid}` | **{v_key}** | `{ev.clause_id}` | `{ev.severity}` | {ev.turn or 'N/A'} | "
                f"\"{clean_quote}\" | {clean_expl} |"
            )
        lines.append("")

    report_text = "\n".join(lines)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report_text, encoding="utf-8")
    logger.info("Saved Markdown report to %s", output_path)
    return report_text


# --------------------------------------------------------------------------------------
# Main Runner Loop
# --------------------------------------------------------------------------------------
def load_calls(
    split: str,
    expected_path: Path,
    transcripts_dir: Path,
) -> List[Tuple[str, str, CallTranscript, List[Dict[str, Any]]]]:
    """Load call transcripts and expected violation clause IDs."""
    if not expected_path.exists():
        raise FileNotFoundError(f"Expected file not found: {expected_path}")
    with open(expected_path, encoding="utf-8") as f:
        expected_data = json.load(f)

    calls: List[Tuple[str, str, CallTranscript, List[Dict[str, Any]]]] = []
    for call_id, info in sorted(expected_data.items()):
        trn_path = transcripts_dir / f"{call_id}.json"
        if not trn_path.exists():
            logger.warning("Transcript %s not found in %s, skipping", call_id, transcripts_dir)
            continue
        call, _ = load_transcript_json(trn_path)
        viols = info.get("violations", [])
        expected_violations = [
            {"clause": v["clause"], "turn": v.get("turn"), "severity": v.get("severity", "major")}
            for v in viols if "clause" in v
        ]
        calls.append((split, call_id, call, expected_violations))
    return calls


def main() -> None:
    parser = argparse.ArgumentParser(description="End-to-End Policy Evaluation (A vs G vs F)")
    parser.add_argument("--dry-run", action="store_true", help="Run only 2 calls to verify pipeline and request count")
    parser.add_argument("--split", choices=["dev", "heldout", "both"], default="both", help="Dataset split to evaluate")
    parser.add_argument(
        "--variants",
        type=lambda s: [x.strip() for x in s.split(",") if x.strip()],
        default=["A", "G"],
        help="Variants to evaluate (default: A,G)",
    )
    parser.add_argument("--runs", type=int, default=3, help="Number of evaluation runs (default: 3)")
    parser.add_argument("--delay", type=float, default=1.5, help="Polite delay between requests to stay below RPM limit")
    parser.add_argument("--output-csv", type=str, default="eval/results/policy_e2e.csv", help="CSV output path")
    parser.add_argument("--output-md", type=str, default="eval/results/policy_e2e.md", help="Markdown output path")
    args = parser.parse_args()

    dev_expected = ROOT / "data" / "expected" / "expected_results.json"
    dev_transcripts = ROOT / "data" / "transcripts"
    heldout_expected = ROOT / "data" / "heldout" / "expected_heldout.json"
    heldout_transcripts = ROOT / "data" / "heldout" / "transcripts"

    all_calls: List[Tuple[str, str, CallTranscript, List[Dict[str, Any]]]] = []
    if args.split in ("dev", "both"):
        all_calls.extend(load_calls("dev", dev_expected, dev_transcripts))
    if args.split in ("heldout", "both"):
        all_calls.extend(load_calls("heldout", heldout_expected, heldout_transcripts))

    if args.dry_run:
        dev_pick = next((c for c in all_calls if c[0] == "dev" and c[3]), all_calls[0])
        heldout_pick = next((c for c in all_calls if c[0] == "heldout" and c[3]), all_calls[1])
        all_calls = [dev_pick, heldout_pick]
        print(f"=== DRY RUN MODE: Selected 2 calls: {[c[1] for c in all_calls]} ===")

    variants = args.variants
    num_runs = args.runs
    total_expected_requests = len(all_calls) * len(variants) * num_runs
    print(f"Total calls to evaluate: {len(all_calls)}")
    print(f"Variants: {variants}")
    print(f"Runs: {num_runs}")
    print(f"Total expected LLM requests: {total_expected_requests}")
    print(f"Target model: {gemini_gateway.describe()}")
    print("-" * 70)

    kb = KnowledgeBase()
    tracker = GatewayUsageTracker(gemini_gateway)
    tracker.install()

    runs: List[SingleRunResult] = []
    completed_requests = 0
    csv_out = ROOT / args.output_csv
    md_out = ROOT / args.output_md

    stopped_early = False
    stop_reason = ""

    try:
        for run_i in range(1, num_runs + 1):
            print(f"\n=======================================================")
            print(f"               STARTING RUN {run_i} OF {num_runs}")
            print(f"=======================================================")
            for idx, (split, call_id, call, expected_violations) in enumerate(all_calls, start=1):
                print(f"\n[Run {run_i}/{num_runs}] [{idx}/{len(all_calls)}] Processing {split} call `{call_id}` (expected: {len(expected_violations)})...")
                for v_key in variants:
                    res = execute_policy_step(
                        split=split,
                        call_id=call_id,
                        call=call,
                        variant=v_key,
                        expected_clauses=expected_violations,
                        kb=kb,
                        gateway=gemini_gateway,
                        tracker=tracker,
                        run_idx=run_i,
                    )
                    runs.append(res)
                    completed_requests += 1

                    if args.delay > 0 and completed_requests < total_expected_requests:
                        time.sleep(args.delay)

    except (QuotaExhaustedError, RateLimitedError, FatalLLMError) as err:
        stopped_early = True
        stop_reason = str(err)
        print(f"\n[!] STOPPED EARLY on rate limit or quota error: {stop_reason}")
        print(f"[!] Completed {completed_requests} of {total_expected_requests} requests before stopping.")
    except Exception as exc:
        stopped_early = True
        stop_reason = str(exc)
        print(f"\n[!] STOPPED on unexpected exception: {stop_reason}")
        print(f"[!] Completed {completed_requests} of {total_expected_requests} requests before stopping.")
        raise
    finally:
        if runs:
            write_csv_report(runs, csv_out)
            generate_markdown_report(runs, gemini_gateway.describe(), md_out)
            print("\n" + "=" * 70)
            print(f"Evaluation complete. Completed {completed_requests}/{total_expected_requests} requests.")
            print(f"Results saved to:\n  - {csv_out}\n  - {md_out}")
            print("=" * 70)
        else:
            print("\n[!] No runs were completed.")


if __name__ == "__main__":
    main()
