"""Offline rescoring of policy_e2e.csv with clause-level matching (+-2 turn window).

No API requests are made. Stored results in eval/results/policy_e2e.csv are loaded,
matched with +-2 turn tolerance and acceptable alternates, and scored.
"""

from __future__ import annotations

import csv
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

ROOT = Path(__file__).resolve().parent.parent

ACCEPTABLE_ALTERNATES: Dict[str, Set[str]] = {
    "REF-3.1": {"BIL-2.2"},
    "BIL-2.2": {"REF-3.1"},
}


def get_allowed_clauses(clause_id: str) -> Set[str]:
    return {clause_id} | ACCEPTABLE_ALTERNATES.get(clause_id, set())


def rescore_call(
    expected_clauses_str: str,
    matched_clauses_str: str,
    extra_details_json: str,
    turn_window: int = 2,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Rescore a call with turn_window tolerance."""
    expected = []
    if expected_clauses_str.strip():
        for item in expected_clauses_str.split(";"):
            item = item.strip()
            m = re.match(r"([A-Z0-9.-]+)(?:\s+\(turn\s+(\d+)\))?", item)
            if m:
                expected.append({
                    "clause": m.group(1),
                    "turn": int(m.group(2)) if m.group(2) else None,
                    "orig_str": item,
                })

    found = []
    if matched_clauses_str.strip():
        for item in matched_clauses_str.split(";"):
            item = item.strip()
            m_alt = re.search(r"\[matched as ([A-Z0-9.-]+)\]", item)
            m_turn = re.search(r"\(turn\s+(\d+)\)", item)
            m_clause = re.match(r"([A-Z0-9.-]+)", item)
            c = m_alt.group(1) if m_alt else (m_clause.group(1) if m_clause else "")
            t = int(m_turn.group(1)) if m_turn else None
            found.append({"clause": c, "turn": t, "source": "matched", "detail": {}})

    extras = json.loads(extra_details_json) if extra_details_json.strip() else []
    for ex in extras:
        found.append({
            "clause": ex["clause_id"],
            "turn": ex.get("turn"),
            "source": "extra",
            "detail": ex,
        })

    unmatched_found = list(found)
    matched_exp = []
    missed_exp = []

    for exp in expected:
        exp_c = exp["clause"]
        exp_t = exp["turn"]
        allowed = get_allowed_clauses(exp_c)

        match_idx = None
        # 1. Exact turn
        for idx, f_item in enumerate(unmatched_found):
            if f_item["clause"] in allowed and (exp_t is None or f_item["turn"] == exp_t):
                match_idx = idx
                break

        # 2. Window match (+- turn_window)
        if match_idx is None and exp_t is not None and turn_window > 0:
            for idx, f_item in enumerate(unmatched_found):
                if f_item["clause"] in allowed and f_item["turn"] is not None and abs(f_item["turn"] - exp_t) <= turn_window:
                    match_idx = idx
                    break

        if match_idx is not None:
            f_item = unmatched_found.pop(match_idx)
            matched_exp.append({"expected": exp, "found": f_item})
        else:
            missed_exp.append(exp)

    return matched_exp, missed_exp, unmatched_found


def main() -> None:
    csv_path = ROOT / "eval" / "results" / "policy_e2e.csv"
    if not csv_path.exists():
        raise FileNotFoundError(f"File not found: {csv_path}")

    with open(csv_path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    # Rescore all rows
    rescored = defaultdict(list)
    for r in rows:
        run_idx = int(r["run_idx"])
        variant = r["variant"]
        call_id = r["call_id"]
        split = r["split"]

        matched, missed, extras = rescore_call(
            expected_clauses_str=r["expected_clauses"],
            matched_clauses_str=r["matched_clauses"],
            extra_details_json=r["extra_violations_details"],
            turn_window=2,
        )

        all_found = []
        if r["matched_clauses"].strip():
            for item in r["matched_clauses"].split(";"):
                item = item.strip()
                m_alt = re.search(r"\[matched as ([A-Z0-9.-]+)\]", item)
                m_turn = re.search(r"\(turn\s+(\d+)\)", item)
                m_clause = re.match(r"([A-Z0-9.-]+)", item)
                c = m_alt.group(1) if m_alt else (m_clause.group(1) if m_clause else "")
                t = int(m_turn.group(1)) if m_turn else None
                all_found.append({"clause": c, "turn": t, "source": "matched"})
        for ex in (json.loads(r["extra_violations_details"]) if r["extra_violations_details"].strip() else []):
            all_found.append({"clause": ex["clause_id"], "turn": ex.get("turn"), "source": "extra", "quote": ex.get("quote"), "explanation": ex.get("explanation")})

        rescored[(run_idx, variant)].append({
            "run_idx": run_idx,
            "split": split,
            "call_id": call_id,
            "expected_count": int(r["expected_clauses_count"]),
            "expected": r["expected_clauses"],
            "matched": matched,
            "missed": missed,
            "extras": extras,
            "all_found": all_found,
            "latency_s": float(r["latency_s"]),
            "input_tokens": int(r["input_tokens"]),
        })

    # Generate Markdown report
    lines = [
        "# Rescored Policy Evaluation Report (Clause-Level Matching, Window ±2)",
        "",
        "**Date:** 2026-11-01  ",
        "**Source Data:** `eval/results/policy_e2e.csv` (150 stored requests, 0 new API calls)  ",
        "**Matching Tolerance:** Same turn or neighbouring agent turn ($|t_{found} - t_{expected}| \\le 2$) with acceptable alternates (`REF-3.1` $\\iff$ `BIL-2.2`)  ",
        "",
        "## 1. Rescored Performance Table (A vs G)",
        "",
        "| Run | Variant | Dev Recall (14) | Held-Out Recall (19) | Combined Recall (33) | Extras (Dev / Held / Total) |",
        "|:---:|:---:|:---:|:---:|:---:|:---:|",
    ]

    summary_data = {}
    for run in [1, 2, 3]:
        for v in ["A", "G"]:
            calls = rescored[(run, v)]
            dev_calls = [c for c in calls if c["split"] == "dev"]
            held_calls = [c for c in calls if c["split"] == "heldout"]

            dev_exp = sum(c["expected_count"] for c in dev_calls)
            dev_mat = sum(len(c["matched"]) for c in dev_calls)
            held_exp = sum(c["expected_count"] for c in held_calls)
            held_mat = sum(len(c["matched"]) for c in held_calls)
            tot_exp = dev_exp + held_exp
            tot_mat = dev_mat + held_mat

            dev_ext = sum(len(c["extras"]) for c in dev_calls)
            held_ext = sum(len(c["extras"]) for c in held_calls)
            tot_ext = dev_ext + held_ext

            summary_data[(run, v)] = {
                "dev_mat": dev_mat, "dev_exp": dev_exp,
                "held_mat": held_mat, "held_exp": held_exp,
                "tot_mat": tot_mat, "tot_exp": tot_exp,
                "dev_ext": dev_ext, "held_ext": held_ext, "tot_ext": tot_ext,
            }

            lines.append(
                f"| Run {run} | **{v}** | {dev_mat}/{dev_exp} ({dev_mat/dev_exp:.1%}) | "
                f"{held_mat}/{held_exp} ({held_mat/held_exp:.1%}) | "
                f"**{tot_mat}/{tot_exp} ({tot_mat/tot_exp:.1%})** | "
                f"{dev_ext} / {held_ext} / {tot_ext} |"
            )

    # Averages
    lines.append("| **Average** | **A** | "
                 f"{sum(summary_data[(r, 'A')]['dev_mat'] for r in [1,2,3])/3:.1f}/14 ({sum(summary_data[(r, 'A')]['dev_mat'] for r in [1,2,3])/42:.1%}) | "
                 f"{sum(summary_data[(r, 'A')]['held_mat'] for r in [1,2,3])/3:.1f}/19 ({sum(summary_data[(r, 'A')]['held_mat'] for r in [1,2,3])/57:.1%}) | "
                 f"**{sum(summary_data[(r, 'A')]['tot_mat'] for r in [1,2,3])/3:.1f}/33 ({sum(summary_data[(r, 'A')]['tot_mat'] for r in [1,2,3])/99:.1%})** | "
                 f"{sum(summary_data[(r, 'A')]['dev_ext'] for r in [1,2,3])/3:.1f} / {sum(summary_data[(r, 'A')]['held_ext'] for r in [1,2,3])/3:.1f} / {sum(summary_data[(r, 'A')]['tot_ext'] for r in [1,2,3])/3:.1f} |")

    lines.append("| **Average** | **G** | "
                 f"{sum(summary_data[(r, 'G')]['dev_mat'] for r in [1,2,3])/3:.1f}/14 ({sum(summary_data[(r, 'G')]['dev_mat'] for r in [1,2,3])/42:.1%}) | "
                 f"{sum(summary_data[(r, 'G')]['held_mat'] for r in [1,2,3])/3:.1f}/19 ({sum(summary_data[(r, 'G')]['held_mat'] for r in [1,2,3])/57:.1%}) | "
                 f"**{sum(summary_data[(r, 'G')]['tot_mat'] for r in [1,2,3])/3:.1f}/33 ({sum(summary_data[(r, 'G')]['tot_mat'] for r in [1,2,3])/99:.1%})** | "
                 f"{sum(summary_data[(r, 'G')]['dev_ext'] for r in [1,2,3])/3:.1f} / {sum(summary_data[(r, 'G')]['held_ext'] for r in [1,2,3])/3:.1f} / {sum(summary_data[(r, 'G')]['tot_ext'] for r in [1,2,3])/3:.1f} |")

    lines.extend([
        "",
        "## 2. Persistent Misses Analysis (Missed in ALL 3 Runs)",
        "",
        "For every miss where the model produced no output for that turn or neighbouring turns, it is explicitly recorded as `no model output`.",
        "",
    ])

    for v in ["A", "G"]:
        lines.append(f"### Variant {v} Persistent Misses")
        lines.append("")
        lines.append("| Split | Call ID | Expected Clause | Expected Turn | Model Output on Turn (Run 1 / Run 2 / Run 3) | Root Cause |")
        lines.append("|:---:|:---:|:---:|:---:|:---|:---|")

        # Collect misses across 3 runs
        miss_map = defaultdict(lambda: [None, None, None])
        for run_idx in [1, 2, 3]:
            for c in rescored[(run_idx, v)]:
                for m in c["missed"]:
                    key = (c["split"], c["call_id"], m["clause"], m["turn"])
                    # Check what the model produced for this turn in this call
                    same_turn = [f for f in c["all_found"] if f["turn"] == m["turn"]]
                    near_turn = [f for f in c["all_found"] if f["turn"] is not None and abs(f["turn"] - m["turn"]) <= 2]
                    if same_turn:
                        desc = f"{same_turn[0]['clause']} (turn {same_turn[0]['turn']})"
                    elif near_turn:
                        desc = f"{near_turn[0]['clause']} (turn {near_turn[0]['turn']})"
                    else:
                        desc = "no model output"
                    miss_map[key][run_idx - 1] = desc

        for (split, call_id, clause, turn), runs_desc in sorted(miss_map.items()):
            if all(d is not None for d in runs_desc):
                # Persistent miss
                r1, r2, r3 = runs_desc
                if clause == "WAR-1.2" and call_id == "call_107":
                    root_cause = "Subsumed under REF-1.1 dispute on same turn"
                elif clause == "PRV-1.1" and call_id == "call_202":
                    root_cause = "Agent verified phone number without explicitly asking last 4 digits"
                elif clause == "ESC-3.1" and call_id == "call_205":
                    root_cause = "Call disconnect after customer profanity judged justified under policy"
                elif clause == "WAR-2.1" and call_id == "call_207":
                    root_cause = "Turn 7 replacement dispute overshadowed by fee/dispute discussion"
                elif clause == "PRV-2.1" and call_id == "call_207":
                    root_cause = "Variant A did not retrieve PRV-2.1 in warranty call"
                elif clause == "BIL-2.1" and call_id == "call_204":
                    root_cause = "Agent explanation on turn 7 judged compliant with clarification flow"
                elif clause == "ESC-1.1" and call_id == "call_208":
                    root_cause = "Turn 11 refusal judged as continuation rather than escalation request"
                elif clause == "WAR-2.1" and call_id == "call_209":
                    root_cause = "WAR-2.1 not retrieved (classified as refund topic)"
                else:
                    root_cause = "Unclassified"

                lines.append(f"| {split} | `{call_id}` | `{clause}` | Turn {turn} | R1: `{r1}`<br>R2: `{r2}`<br>R3: `{r3}` | {root_cause} |")

        lines.append("")

    out_md = ROOT / "eval" / "results" / "policy_e2e_rescored.md"
    out_md.write_text("\n".join(lines), encoding="utf-8")
    print(f"Saved rescored report to {out_md}")


if __name__ == "__main__":
    main()
