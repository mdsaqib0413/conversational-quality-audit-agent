"""Re-locate the turn of every labelled policy violation in data/transcripts/*.json.

Older generator versions guessed the turn (middle agent turn) when the wrong claim had no digits. This script
finds the agent turn that really states the wrong claim (using violation_catalog.yaml) and rewrites `turn` and `said`.
Run it once after generating transcripts:  python scripts/repair_violation_turns.py [--dry-run]
"""
import argparse
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from src.audit.labels import best_overlap_agent_turn  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    cat = yaml.safe_load((ROOT / "scripts" / "violation_catalog.yaml").read_text(encoding="utf-8"))
    items = cat if isinstance(cat, list) else next(iter(cat.values()))
    changed = problems = 0
    for p in sorted((ROOT / "data" / "transcripts").glob("call_*.json")):
        d = json.loads(p.read_text(encoding="utf-8"))
        dirty = False
        for v in d["ground_truth"]["policy_violations"]:
            entry = next((i for i in items if i["clause_id"] == v["clause_id"] and i.get("correct_fact", "").strip() == v.get("correct_fact", "").strip()), None)
            if entry is None:
                print(f"{p.name}: no catalog entry for {v['clause_id']}; left unchanged")
                problems += 1
                continue
            turn = best_overlap_agent_turn(d["turns"], f"{entry['wrong_statement_hint']} {entry['correct_fact']}")
            if turn is None:
                print(f"{p.name}: could not locate the violation {v['clause_id']} in the dialogue; marking unverified")
                d["verified"] = False
                d["verification_notes"] = (d.get("verification_notes", "") + " | violation turn could not be located").strip(" |")
                dirty = True
                problems += 1
                continue
            text = next(t["text"] for t in d["turns"] if t["i"] == turn)
            if v["turn"] != turn or v["said"] != text:
                print(f"{p.name}: {v['clause_id']} turn {v['turn']} -> {turn}")
                v["turn"], v["said"] = turn, text
                dirty = True
                changed += 1
        if dirty and not args.dry_run:
            p.write_text(json.dumps(d, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"done: {changed} violation labels corrected, {problems} problems" + (" (dry run)" if args.dry_run else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
