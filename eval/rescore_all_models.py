"""Offline comparative rescoring of all policy compliance model evaluation CSVs.

Evaluates Gemini Flash-Lite (runs 1, 2, 3 and 3-run avg), Gemini-2.5-Flash (run 1), and
Gemini-3.5-Flash (run 1) on Variant G across 25 calls (13 dev, 12 held-out)
using turn-level matching (+-2 turn window) and acceptable alternates.
Compares old baseline ground truth (14 dev / 19 held-out / 33 combined) against
the updated ground truth incorporating the 6 human-reviewed labels (18 dev / 21 held-out / 39 combined).
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

# Ensure repository root is on sys.path
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from eval.policy_e2e import ExpectedViolation, get_allowed_clauses, match_violations_turn_level
from src.audit.schemas import PolicyResult


def load_updated_ground_truth() -> Dict[str, List[ExpectedViolation]]:
    """Load latest ground-truth violations from data/expected and data/heldout."""
    dev_path = ROOT / "data" / "expected" / "expected_results.json"
    held_path = ROOT / "data" / "heldout" / "expected_heldout.json"

    gt: Dict[str, List[ExpectedViolation]] = {}
    if dev_path.exists():
        with open(dev_path, encoding="utf-8") as f:
            dev_data = json.load(f)
        for cid, info in dev_data.items():
            gt[cid] = [
                ExpectedViolation(clause=v["clause"], turn=v.get("turn"))
                for v in info.get("violations", [])
                if "clause" in v
            ]

    if held_path.exists():
        with open(held_path, encoding="utf-8") as f:
            held_data = json.load(f)
        for cid, info in held_data.items():
            gt[cid] = [
                ExpectedViolation(clause=v["clause"], turn=v.get("turn"))
                for v in info.get("violations", [])
                if "clause" in v
            ]

    return gt


def rescore_dataframe(
    df_path: Path | str,
    variant: str = "G",
    run_idx: Optional[int] = 1,
    allow_war_alternate: bool = True,
    use_new_gt: bool = False,
    updated_gt: Optional[Dict[str, List[ExpectedViolation]]] = None,
) -> Dict[str, Any]:
    """Rescore an evaluation CSV file for a given variant and run index."""
    df = pd.read_csv(df_path)
    if "variant" in df.columns:
        df = df[df["variant"] == variant]
    if "run_idx" in df.columns and run_idx is not None:
        df = df[df["run_idx"] == run_idx]

    records: List[Dict[str, Any]] = []
    for _, r in df.iterrows():
        call_id = r["call_id"]
        split = r["split"]

        if use_new_gt:
            if updated_gt is None:
                updated_gt = load_updated_ground_truth()
            expected = updated_gt.get(call_id, [])
        else:
            # Parse expected violations from CSV column
            expected_clauses_str = str(r["expected_clauses"]) if pd.notna(r["expected_clauses"]) else ""
            expected = []
            if expected_clauses_str.strip() and expected_clauses_str != "nan":
                for item in expected_clauses_str.split(";"):
                    item = item.strip()
                    m = re.match(r"([A-Z0-9.-]+)(?:\s+\(turn\s+(\d+)\))?", item)
                    if m:
                        expected.append(
                            ExpectedViolation(
                                clause=m.group(1),
                                turn=int(m.group(2)) if m.group(2) else None,
                            )
                        )

        # Reconstruct found violations as PolicyResult objects
        found_violations: List[PolicyResult] = []
        matched_str = str(r["matched_clauses"]) if pd.notna(r["matched_clauses"]) else ""
        if matched_str.strip() and matched_str != "nan":
            for item in matched_str.split(";"):
                item = item.strip()
                m_alt = re.search(r"\[matched as ([A-Z0-9.-]+)\]", item)
                m_turn = re.search(r"\(turn\s+(\d+)\)", item)
                m_flagged = re.search(r"\[flagged on turn\s+(\d+)\]", item)
                m_clause = re.match(r"([A-Z0-9.-]+)", item)

                clause = m_alt.group(1) if m_alt else (m_clause.group(1) if m_clause else "")
                turn = int(m_flagged.group(1)) if m_flagged else (int(m_turn.group(1)) if m_turn else None)
                found_violations.append(
                    PolicyResult(
                        clause_id=clause,
                        policy_title="",
                        verdict="violation",
                        severity="minor",
                        turn=turn,
                        quote="",
                        claim="",
                        explanation="",
                    )
                )

        extras_str = str(r["extra_violations_details"]) if pd.notna(r["extra_violations_details"]) else ""
        if extras_str.strip() and extras_str != "nan":
            try:
                extras = json.loads(extras_str)
                for ex in extras:
                    found_violations.append(
                        PolicyResult(
                            clause_id=ex["clause_id"],
                            policy_title="",
                            verdict="violation",
                            severity=ex.get("severity", "minor"),
                            turn=ex.get("turn"),
                            quote=ex.get("quote", ""),
                            claim=ex.get("claim", ""),
                            explanation=ex.get("explanation", ""),
                        )
                    )
            except Exception:
                pass

        target_call_id = call_id if allow_war_alternate else f"no_alt_{call_id}"
        matched, missed, extra = match_violations_turn_level(
            expected, found_violations, turn_window=2, call_id=target_call_id
        )

        records.append(
            {
                "call_id": call_id,
                "split": split,
                "expected_count": len(expected),
                "matched_count": len(matched),
                "missed_count": len(missed),
                "extra_count": len(extra),
                "matched": matched,
                "missed": missed,
                "extra": [e.clause_id for e in extra],
            }
        )

    res_df = pd.DataFrame(records)
    dev_sub = res_df[res_df["split"] == "dev"]
    held_sub = res_df[res_df["split"] == "heldout"]

    dev_exp = dev_sub["expected_count"].sum()
    dev_mat = dev_sub["matched_count"].sum()
    dev_ext = dev_sub["extra_count"].sum()

    held_exp = held_sub["expected_count"].sum()
    held_mat = held_sub["matched_count"].sum()
    held_ext = held_sub["extra_count"].sum()

    tot_exp = dev_exp + held_exp
    tot_mat = dev_mat + held_mat
    tot_ext = dev_ext + held_ext

    return {
        "dev_matched": int(dev_mat),
        "dev_expected": int(dev_exp),
        "dev_recall": dev_mat / dev_exp if dev_exp else 0.0,
        "dev_extras": int(dev_ext),
        "held_matched": int(held_mat),
        "held_expected": int(held_exp),
        "held_recall": held_mat / held_exp if held_exp else 0.0,
        "held_extras": int(held_ext),
        "tot_matched": int(tot_mat),
        "tot_expected": int(tot_exp),
        "tot_recall": tot_mat / tot_exp if tot_exp else 0.0,
        "tot_extras": int(tot_ext),
    }


def compute_average(stats_list: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Compute average metrics across multiple runs."""
    n = len(stats_list)
    if n == 0:
        return {}
    dev_exp = stats_list[0]["dev_expected"]
    held_exp = stats_list[0]["held_expected"]
    tot_exp = stats_list[0]["tot_expected"]
    avg_dev_mat = sum(s["dev_matched"] for s in stats_list) / n
    avg_held_mat = sum(s["held_matched"] for s in stats_list) / n
    avg_tot_mat = sum(s["tot_matched"] for s in stats_list) / n
    avg_dev_ext = sum(s["dev_extras"] for s in stats_list) / n
    avg_held_ext = sum(s["held_extras"] for s in stats_list) / n
    avg_tot_ext = sum(s["tot_extras"] for s in stats_list) / n

    return {
        "dev_matched": avg_dev_mat,
        "dev_expected": dev_exp,
        "dev_recall": avg_dev_mat / dev_exp if dev_exp else 0.0,
        "dev_extras": avg_dev_ext,
        "held_matched": avg_held_mat,
        "held_expected": held_exp,
        "held_recall": avg_held_mat / held_exp if held_exp else 0.0,
        "held_extras": avg_held_ext,
        "tot_matched": avg_tot_mat,
        "tot_expected": tot_exp,
        "tot_recall": avg_tot_mat / tot_exp if tot_exp else 0.0,
        "tot_extras": avg_tot_ext,
    }


def main() -> None:
    updated_gt = load_updated_ground_truth()
    models = [
        ("Gemini Flash-Lite (Run 1)", ROOT / "eval" / "results" / "policy_e2e.csv", 1),
        ("Gemini Flash-Lite (Run 2)", ROOT / "eval" / "results" / "policy_e2e.csv", 2),
        ("Gemini Flash-Lite (Run 3)", ROOT / "eval" / "results" / "policy_e2e.csv", 3),
        ("Gemini-2.5-Flash (Run 1)", ROOT / "eval" / "results" / "policy_model_comparison_25flash.csv", 1),
        ("Gemini-3.5-Flash (Run 1)", ROOT / "eval" / "results" / "policy_model_comparison.csv", 1),
    ]

    print("=" * 115)
    print("COMPARATIVE RESCORING: OLD DENOMINATORS vs NEW REVIEWED DENOMINATORS")
    print("=" * 115)
    print(
        f"{'Model':<25} | {'Ground Truth':<12} | {'Dev Recall':<17} | {'Held-Out Recall':<18} | {'Combined Recall':<18} | {'Extras (D/H/T)':<16}"
    )
    print("-" * 115)

    flash_lite_old = []
    flash_lite_new = []

    for name, path, r_idx in models:
        stats_old = rescore_dataframe(
            path, variant="G", run_idx=r_idx, allow_war_alternate=True, use_new_gt=False
        )
        stats_new = rescore_dataframe(
            path, variant="G", run_idx=r_idx, allow_war_alternate=True, use_new_gt=True, updated_gt=updated_gt
        )

        if "Flash-Lite" in name:
            flash_lite_old.append(stats_old)
            flash_lite_new.append(stats_new)

        d_old = f"{stats_old['dev_matched']}/{stats_old['dev_expected']} ({stats_old['dev_recall']:.1%})"
        h_old = f"{stats_old['held_matched']}/{stats_old['held_expected']} ({stats_old['held_recall']:.1%})"
        c_old = f"{stats_old['tot_matched']}/{stats_old['tot_expected']} ({stats_old['tot_recall']:.1%})"
        e_old = f"{stats_old['dev_extras']} / {stats_old['held_extras']} / {stats_old['tot_extras']}"

        d_new = f"{stats_new['dev_matched']}/{stats_new['dev_expected']} ({stats_new['dev_recall']:.1%})"
        h_new = f"{stats_new['held_matched']}/{stats_new['held_expected']} ({stats_new['held_recall']:.1%})"
        c_new = f"{stats_new['tot_matched']}/{stats_new['tot_expected']} ({stats_new['tot_recall']:.1%})"
        e_new = f"{stats_new['dev_extras']} / {stats_new['held_extras']} / {stats_new['tot_extras']}"

        print(f"{name:<25} | {'OLD (33)':<12} | {d_old:<17} | {h_old:<18} | {c_old:<18} | {e_old:<16}")
        print(f"{name:<25} | {'NEW (39)':<12} | {d_new:<17} | {h_new:<18} | {c_new:<18} | {e_new:<16}")
        print("-" * 115)

    # Compute and display 3-run averages for Flash-Lite
    avg_old = compute_average(flash_lite_old)
    avg_new = compute_average(flash_lite_new)

    d_avg_old = f"{avg_old['dev_matched']:.1f}/{avg_old['dev_expected']} ({avg_old['dev_recall']:.1%})"
    h_avg_old = f"{avg_old['held_matched']:.1f}/{avg_old['held_expected']} ({avg_old['held_recall']:.1%})"
    c_avg_old = f"{avg_old['tot_matched']:.1f}/{avg_old['tot_expected']} ({avg_old['tot_recall']:.1%})"
    e_avg_old = f"{avg_old['dev_extras']:.1f} / {avg_old['held_extras']:.1f} / {avg_old['tot_extras']:.1f}"

    d_avg_new = f"{avg_new['dev_matched']:.1f}/{avg_new['dev_expected']} ({avg_new['dev_recall']:.1%})"
    h_avg_new = f"{avg_new['held_matched']:.1f}/{avg_new['held_expected']} ({avg_new['held_recall']:.1%})"
    c_avg_new = f"{avg_new['tot_matched']:.1f}/{avg_new['tot_expected']} ({avg_new['tot_recall']:.1%})"
    e_avg_new = f"{avg_new['dev_extras']:.1f} / {avg_new['held_extras']:.1f} / {avg_new['tot_extras']:.1f}"

    print(f"{'Flash-Lite (3-Run Avg)':<25} | {'OLD (33)':<12} | {d_avg_old:<17} | {h_avg_old:<18} | {c_avg_old:<18} | {e_avg_old:<16}")
    print(f"{'Flash-Lite (3-Run Avg)':<25} | {'NEW (39)':<12} | {d_avg_new:<17} | {h_avg_new:<18} | {c_avg_new:<18} | {e_avg_new:<16}")
    print("=" * 115)


if __name__ == "__main__":
    main()
