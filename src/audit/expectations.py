"""Expected results: what every feature SHOULD produce for every labelled call, written down before any audit runs.

`build_expected()` derives the expectations from each transcript's hand-written ground truth using simple,
independent arithmetic (it does NOT call the code under test). The result is stored in
data/expected/expected_results.json so a human can read it, edit it and review it in a diff.

    python scripts/build_expectations.py        # regenerate after changing or adding transcripts
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, List

import yaml

ROOT = Path(__file__).resolve().parent.parent.parent
EXPECTED_PATH = ROOT / "data" / "expected" / "expected_results.json"
SPEC_PATH = ROOT / "data" / "expected" / "feature_spec.yaml"

MULT = {"followed": 1.0, "partial": 0.5, "missed": 0.0}
PENALTY = {"minor": 3, "major": 8, "critical": 15}
NEGATIVE = {"angry", "frustrated", "anxious"}
POSITIVE = {"satisfied", "happy"}
SPEAKING_WORDS_PER_SECOND = 2.6   # same speaking-rate model the transcript loader uses

# bands by call quality (the "predefined expected result" a reader can check at a glance)
OVERALL_BAND = {"good": [88, 100], "mild_deviation": [60, 100], "bad_deviation": [0, 70]}
GRADE_IN = {"good": ["A", "B"], "mild_deviation": ["A", "B", "C"], "bad_deviation": ["C", "D"]}


def emotion_class(label: str) -> str:
    return "negative" if label in NEGATIVE else "positive" if label in POSITIVE else "neutral"


def _valence(label: str) -> float:
    return {"angry": -2, "frustrated": -1.5, "anxious": -1, "confused": -0.5, "neutral": 0, "satisfied": 1, "happy": 1.5}.get(label, 0)


def _trend(arc: List[str]) -> str:
    if len(arc) < 2:
        return "flat"
    diff = _valence(arc[-1]) - _valence(arc[0])
    return "improved" if diff >= 0.75 else "worsened" if diff <= -0.75 else "flat"


def _signals_required(gt: dict) -> List[str]:
    steps = gt["sop_steps"]
    sig = set()
    if any(s.startswith("ANG-") for s in steps):
        sig.add("angry_customer")
    if any(s in steps for s in ("HLD-01", "HLD-02", "HLD-03")):
        sig.add("hold")
    if "HLD-04" in steps:
        sig.add("transfer")
    if "HLD-05" in steps:
        sig.add("callback")
    if "ANG-05" in steps or any(v["clause_id"] == "ESC-1.1" for v in gt["policy_violations"]):
        sig.add("supervisor_request")
    return sorted(sig)


def _implied_gaps(steps: Dict[str, str]) -> List[str]:
    out = set()
    if steps.get("GEN-05") == "missed" or steps.get("ANG-02") == "missed":
        out.add("no_empathy")
    if steps.get("GEN-07") == "missed":
        out.add("no_summary")
    if steps.get("GEN-08") == "missed":
        out.add("no_closing")
    return sorted(out)


def _timing_from_raw(raw: dict) -> dict:
    """Independent count of silences / holds / interruptions straight from the JSON (pause_before_sec, interrupts_previous)."""
    turns = raw["turns"]
    dead_air = hold_over = holds = agent_int = 0
    longest_hold = 0.0
    for i, t in enumerate(turns):
        if t.get("interrupts_previous") and t["speaker"] == "agent":
            agent_int += 1
        pause = float(t.get("pause_before_sec") or 0)
        if pause >= 4.0 and i > 0:
            prev_agent = " ".join(x["text"].lower() for x in turns[max(0, i - 3):i] if x["speaker"] == "agent")
            if t["speaker"] == "agent" and re.search(r"\bhold\b", prev_agent):
                holds += 1
                longest_hold = max(longest_hold, pause)
                if pause > 120:
                    hold_over += 1
            else:
                dead_air += 1
    words_agent = sum(len(t["text"].split()) for t in turns if t["speaker"] == "agent")
    words_all = sum(len(t["text"].split()) for t in turns)
    return {"dead_air_events": dead_air, "agent_interruptions": agent_int, "holds": holds, "holds_over_limit": hold_over,
            "longest_hold_sec": longest_hold, "agent_talk_ratio": round(words_agent / max(1, words_all), 3),
            "agent_turns": sum(1 for t in turns if t["speaker"] == "agent"), "customer_turns": sum(1 for t in turns if t["speaker"] == "customer")}


def build_expected(raw: dict, kb) -> dict:
    gt = raw["ground_truth"]
    quality = raw["quality"]
    steps = dict(gt["sop_steps"])
    rubric = {s["step_id"]: s for s in kb.rubric["sop_steps"]}

    earned = sum(rubric[s]["weight"] * MULT[st] for s, st in steps.items())
    possible = sum(rubric[s]["weight"] for s in steps)
    sop_exp = round(earned / possible * 40, 1) if possible else 0.0
    seen, penalty = set(), 0
    for v in gt["policy_violations"]:
        if v["clause_id"] in seen:
            continue
        seen.add(v["clause_id"])
        penalty += PENALTY[v["severity"]]
    policy_exp = max(0, 30 - penalty)
    crit_missed = [s for s, st in steps.items() if st == "missed" and rubric[s].get("critical")]
    empathy_est = 6.0 if (steps.get("GEN-05") == "missed" or steps.get("ANG-02") == "missed") else 12.0
    comm_est = 13.0 if quality == "good" else 11.0 if quality == "mild_deviation" else 7.0
    estimate = sop_exp + policy_exp + empathy_est + comm_est
    if crit_missed:
        estimate = min(estimate, 70.0)

    timing = _timing_from_raw(raw)
    arc = gt["customer_emotion_arc"]
    if any(steps.get(s) == "missed" for s in ("ANG-01", "ANG-02")):
        agent_expect = "has_negative"
    elif quality == "good":
        agent_expect = "mostly_positive"
    else:
        agent_expect = "any"
    gaps_gt = sorted(set(gt.get("gaps", [])) | set(_implied_gaps(steps)))
    forbidden = [g for g in ("dead_air", "interruption", "hold_too_long") if g not in gaps_gt]

    return {
        "quality": quality,
        "topic": {"label": raw["topic"], "also_ok_if_angry": raw["topic"] == "complaint", "also_ok": []},
        "signals_required": _signals_required(gt),
        "candidate_steps_must_include": sorted(steps),
        "steps": steps,
        "violations": [{"clause": v["clause_id"], "turn": v["turn"], "severity": v["severity"]} for v in gt["policy_violations"]],
        "gaps_required": gaps_gt,
        "gaps_forbidden": forbidden,
        "metrics": timing,
        "score": {
            "sop_score_expected": sop_exp, "sop_score_tolerance": 8.0, "policy_score_expected": policy_exp,
            "overall_band": OVERALL_BAND[quality], "overall_estimate": round(estimate, 1), "overall_estimate_tolerance": 14.0,
            "grade_in": GRADE_IN[quality], "critical_step_missed": crit_missed, "critical_failure_expected": bool(crit_missed),
            "max_overall_if_critical": 70.0,
        },
        "emotion": {"customer_start": emotion_class(arc[0]), "customer_end": emotion_class(arc[-1]), "customer_trend": _trend(arc), "agent": agent_expect},
        "requests_max": 3,
    }


OVERRIDES_PATH = ROOT / "data" / "expected" / "overrides.yaml"


def _merge(base: dict, extra: dict) -> dict:
    for k, v in extra.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _merge(base[k], v)
        else:
            base[k] = v
    return base


def load_overrides(path: Path = OVERRIDES_PATH) -> dict:
    """Human corrections on top of the derived expectations (for example a call that is genuinely about two topics)."""
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def build_all(folder: Path, kb, overrides: Dict[str, dict] | None = None) -> Dict[str, dict]:
    overrides = load_overrides() if overrides is None else overrides
    out: Dict[str, dict] = {}
    for p in sorted(Path(folder).glob("call_*.json")):
        raw = json.loads(p.read_text(encoding="utf-8"))
        if not raw.get("verified"):
            continue
        out[p.stem] = _merge(build_expected(raw, kb), overrides.get(p.stem, {}))
    return out


def save_expected(expected: Dict[str, dict], path: Path = EXPECTED_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(expected, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def load_expected(path: Path = EXPECTED_PATH) -> Dict[str, dict]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_spec(path: Path = SPEC_PATH) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))
