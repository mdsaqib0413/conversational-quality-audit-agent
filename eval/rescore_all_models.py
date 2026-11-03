"""Offline comparative rescoring of all policy compliance model evaluation CSVs.

Evaluates Gemini Flash-Lite (runs 1, 2, 3), Gemini-2.5-Flash (run 1), and
Gemini-3.5-Flash (run 1) on Variant G across 25 calls (13 dev, 12 held-out)
using turn-level matching (+-2 turn window) and acceptable alternates.
Compares baseline scoring against rescoring with the WAR-2.1 <-> WAR-2.3 alternate
pair for call_207 turn 7 and call_209 turn 11.
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


def rescore_dataframe(
    df_path: Path | str,
    variant: str = "G",
    run_idx: Optional[int] = 1,
    allow_war_alternate: bool = True,
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

        # Parse expected violations
        expected_clauses_str = str(r["expected_clauses"]) if pd.notna(r["expected_clauses"]) else ""
        expected: List[ExpectedViolation] = []
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


def main() -> None:
    models = [
        ("Gemini Flash-Lite (Run 1)", ROOT / "eval" / "results" / "policy_e2e.csv", 1),
        ("Gemini Flash-Lite (Run 2)", ROOT / "eval" / "results" / "policy_e2e.csv", 2),
        ("Gemini Flash-Lite (Run 3)", ROOT / "eval" / "results" / "policy_e2e.csv", 3),
        ("Gemini-2.5-Flash (Run 1)", ROOT / "eval" / "results" / "policy_model_comparison_25flash.csv", 1),
        ("Gemini-3.5-Flash (Run 1)", ROOT / "eval" / "results" / "policy_model_comparison.csv", 1),
    ]

    print(
        f"{'Model':<28} | {'Dev Recall (14)':<17} | {'Held-Out Recall (19)':<20} | {'Combined Recall (33)':<20} | {'Extras (Dev/Held/Tot)':<22}"
    )
    print("-" * 115)

    for name, path, r_idx in models:
        for alt in [False, True]:
            label = f"{name} [{'WITH alt' if alt else 'BEFORE'}]"
            stats = rescore_dataframe(path, variant="G", run_idx=r_idx, allow_war_alternate=alt)
            d_str = f"{stats['dev_matched']}/{stats['dev_expected']} ({stats['dev_recall']:.1%})"
            h_str = f"{stats['held_matched']}/{stats['held_expected']} ({stats['held_recall']:.1%})"
            c_str = f"{stats['tot_matched']}/{stats['tot_expected']} ({stats['tot_recall']:.1%})"
            e_str = f"{stats['dev_extras']} / {stats['held_extras']} / {stats['tot_extras']}"
            print(f"{label:<28} | {d_str:<17} | {h_str:<20} | {c_str:<20} | {e_str:<22}")


if __name__ == "__main__":
    main()
