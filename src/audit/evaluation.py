"""Compare audit results with the ground truth stored in data/transcripts/*.json."""

from __future__ import annotations

import csv
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from .emotion import compute_metrics
from .topic import candidate_step_ids, detect_topic
from .transcript_io import load_transcript_json

DEVIATION = {"partial", "missed"}
TURN_TOLERANCE = 2


def _prf(tp: int, fp: int, fn: int) -> Dict[str, float]:
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    f = 2 * p * r / (p + r) if p + r else 0.0
    return {"precision": round(p, 3), "recall": round(r, 3), "f1": round(f, 3), "tp": tp, "fp": fp, "fn": fn}


def implied_gaps(sop_steps: Dict[str, str]) -> set:
    """Gap labels that follow from labelled SOP steps (a missed empathy step IS a no_empathy gap)."""
    out = set()
    if sop_steps.get("GEN-05") == "missed" or sop_steps.get("ANG-02") == "missed":
        out.add("no_empathy")
    if sop_steps.get("GEN-07") == "missed":
        out.add("no_summary")
    if sop_steps.get("GEN-08") == "missed":
        out.add("no_closing")
    return out


def evaluate_no_llm(files: Sequence[Path], kb) -> dict:
    """Zero-request checks: topic accuracy, candidate-step coverage, timing-gap detection."""
    rows, topic_ok, covered, total_gt_steps = [], 0, 0, 0
    gap_tp = {"dead_air": 0, "interruption": 0}
    gap_fn = {"dead_air": 0, "interruption": 0}
    gap_fp = {"dead_air": 0, "interruption": 0}
    for p in files:
        call, raw = load_transcript_json(p)
        res = detect_topic(call.turns)
        gt_steps = set(raw["ground_truth"]["sop_steps"])
        cand = set(candidate_step_ids(kb, res.topic, res.signals))
        topic_ok += res.topic == raw["topic"] or (raw["topic"] == "complaint" and "angry_customer" in res.signals)
        covered += len(gt_steps & cand)
        total_gt_steps += len(gt_steps)
        m = compute_metrics(call)
        gt_gaps = set(raw["ground_truth"].get("gaps", []))
        for g, events in (("dead_air", m.dead_air_events), ("interruption", m.interruption_events)):
            if g in gt_gaps and events:
                gap_tp[g] += 1
            elif g in gt_gaps:
                gap_fn[g] += 1
            elif events:
                gap_fp[g] += 1
        rows.append({"id": call.call_id, "label_topic": raw["topic"], "pred_topic": res.topic, "signals": ",".join(res.signals),
                     "gt_steps_covered": f"{len(gt_steps & cand)}/{len(gt_steps)}"})
    n = max(1, len(files))
    return {
        "calls": len(files), "topic_accuracy": round(topic_ok / n, 3),
        "candidate_step_coverage": round(covered / total_gt_steps, 3) if total_gt_steps else None,
        "timing_gaps": {g: _prf(gap_tp[g], gap_fp[g], gap_fn[g]) for g in gap_tp}, "rows": rows,
    }


def evaluate_reports(pairs: Sequence[tuple]) -> dict:
    """pairs = [(AuditReport, raw_transcript_json), ...]"""
    step_exact = step_total = not_judged = 0
    dev = {"tp": 0, "fp": 0, "fn": 0}
    viol = {"tp": 0, "fp": 0, "fn": 0}
    sev_ok = sev_total = 0
    call_viol = {"tp": 0, "fp": 0, "fn": 0, "tn": 0}
    crit = {"tp": 0, "fp": 0, "fn": 0, "tn": 0}
    topic_ok = 0
    by_quality: Dict[str, List[float]] = defaultdict(list)
    gap_stats = defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0})
    per_call, per_step = [], []

    for rep, raw in pairs:
        gt = raw["ground_truth"]
        by_quality[raw["quality"]].append(rep.scores.overall)
        topic_ok += rep.topic == raw["topic"] or (raw["topic"] == "complaint" and "angry_customer" in rep.signals)
        results = {r.step_id: r for r in rep.sop_results}
        crit_gt_missed = False
        for sid, gt_status in gt["sop_steps"].items():
            r = results.get(sid)
            step_total += 1
            if r is None or r.status == "not_applicable":
                not_judged += 1
                pred = None
            else:
                pred = r.status
                step_exact += pred == gt_status
            gt_dev, pred_dev = gt_status in DEVIATION, pred in DEVIATION
            if pred is not None:
                dev["tp"] += gt_dev and pred_dev
                dev["fp"] += (not gt_dev) and pred_dev
                dev["fn"] += gt_dev and not pred_dev
            else:
                dev["fn"] += gt_dev
            per_step.append({"call": rep.call_id, "step": sid, "gt": gt_status, "pred": pred or "n/a", "match": pred == gt_status})
            if gt_status == "missed" and r is not None and r.critical:
                crit_gt_missed = True
        # any critical step in GT that the system knows as critical and missed
        pred_crit = rep.scores.critical_failure
        crit["tp"] += crit_gt_missed and pred_crit
        crit["fp"] += (not crit_gt_missed) and pred_crit
        crit["fn"] += crit_gt_missed and not pred_crit
        crit["tn"] += (not crit_gt_missed) and not pred_crit

        gt_v = [(v["clause_id"], v["turn"], v.get("severity")) for v in gt["policy_violations"]]
        pred_v = [(p.clause_id, p.turn or 0, p.severity) for p in rep.policy_results if p.verdict == "violation"]
        used = set()
        tp_here = 0
        for cid, turn, sev in gt_v:
            hit = next((i for i, (pc, pt, ps) in enumerate(pred_v) if i not in used and pc == cid and abs(pt - turn) <= TURN_TOLERANCE), None)
            if hit is None:
                viol["fn"] += 1
            else:
                used.add(hit)
                viol["tp"] += 1
                tp_here += 1
                sev_total += 1
                sev_ok += pred_v[hit][2] == sev
        viol["fp"] += len(pred_v) - len(used)
        has_gt, has_pred = bool(gt_v), bool(pred_v)
        call_viol["tp"] += has_gt and has_pred
        call_viol["fp"] += (not has_gt) and has_pred
        call_viol["fn"] += has_gt and not has_pred
        call_viol["tn"] += (not has_gt) and not has_pred

        gt_gaps = set(gt.get("gaps", [])) | implied_gaps(gt["sop_steps"])
        pred_gaps = {g.gap_type for g in rep.gaps}
        for g in gt_gaps | pred_gaps:
            if g in gt_gaps and g in pred_gaps:
                gap_stats[g]["tp"] += 1
            elif g in gt_gaps:
                gap_stats[g]["fn"] += 1
            else:
                gap_stats[g]["fp"] += 1
        per_call.append({"id": rep.call_id, "quality": raw["quality"], "topic_label": raw["topic"], "topic_pred": rep.topic,
                         "overall": rep.scores.overall, "grade": rep.scores.grade, "gt_violations": len(gt_v), "pred_violations": len(pred_v),
                         "violations_matched": tp_here, "critical_failure": rep.scores.critical_failure, "requests": rep.meta.llm_requests})

    means = {q: round(statistics.mean(v), 1) for q, v in by_quality.items()}
    ordered = None
    if all(k in means for k in ("good", "mild_deviation", "bad_deviation")):
        ordered = means["good"] > means["mild_deviation"] > means["bad_deviation"]
    n = max(1, len(pairs))
    return {
        "calls": len(pairs), "topic_accuracy": round(topic_ok / n, 3),
        "sop": {"steps_compared": step_total, "exact_match_rate": round(step_exact / max(1, step_total - not_judged), 3),
                "not_judged": not_judged, "deviation_detection": _prf(dev["tp"], dev["fp"], dev["fn"])},
        "violations": {"clause_level": _prf(viol["tp"], viol["fp"], viol["fn"]), "call_level": call_viol,
                       "severity_agreement": round(sev_ok / sev_total, 3) if sev_total else None},
        "critical_failure": crit,
        "score_by_quality": means, "scores_ordered_good_gt_mild_gt_bad": ordered,
        "gaps": {g: _prf(v["tp"], v["fp"], v["fn"]) for g, v in sorted(gap_stats.items())},
        "per_call": per_call, "per_step": per_step,
    }


def write_csv(path: Path, rows: List[dict]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def summary_markdown(res: dict, title: str = "Evaluation summary") -> str:
    L = [f"# {title}", "", f"Calls evaluated: **{res['calls']}**", ""]
    if "sop" in res:
        s, v = res["sop"], res["violations"]
        d = s["deviation_detection"]
        L += [
            "| Metric | Result |", "|---|---|",
            f"| Topic accuracy | {res['topic_accuracy']:.0%} |",
            f"| SOP step exact-match (judged steps) | {s['exact_match_rate']:.0%} over {s['steps_compared'] - s['not_judged']} steps |",
            f"| SOP deviation detection (missed/partial) | precision {d['precision']:.0%}, recall {d['recall']:.0%}, F1 {d['f1']:.2f} |",
            f"| Policy violation detection (clause level) | precision {v['clause_level']['precision']:.0%}, recall {v['clause_level']['recall']:.0%}, F1 {v['clause_level']['f1']:.2f} |",
            f"| Severity agreement on matched violations | {v['severity_agreement'] if v['severity_agreement'] is None else format(v['severity_agreement'], '.0%')} |",
            f"| Average score by call quality | {res['score_by_quality']} |",
            f"| Scores ordered good > mild > bad | {res['scores_ordered_good_gt_mild_gt_bad']} |",
            f"| Critical-failure detection | {res['critical_failure']} |", "",
            "## Gap detection", "", "| Gap | precision | recall | tp/fp/fn |", "|---|---|---|---|",
        ]
        for g, m in res["gaps"].items():
            L.append(f"| {g} | {m['precision']:.0%} | {m['recall']:.0%} | {m['tp']}/{m['fp']}/{m['fn']} |")
    else:
        L += ["| Metric | Result |", "|---|---|", f"| Topic accuracy | {res['topic_accuracy']:.0%} |",
              f"| Candidate SOP steps cover ground truth | {res['candidate_step_coverage']:.0%} |"]
        for g, m in res["timing_gaps"].items():
            L.append(f"| Timing-based {g} detection | precision {m['precision']:.0%}, recall {m['recall']:.0%} |")
    return "\n".join(L) + "\n"
