"""Feature tests: expected result vs actual result, for every call and every feature.

Flow
  expected_results.json  (written before anything runs, from the hand-written labels)
  + an audit of the call (or, for the offline features, just the deterministic code)
  -> `call_comparison()` rows: item | expected | actual | ok
  -> `aggregate()` rates per metric
  -> `evaluate_spec()` PASS / WARN / FAIL per feature against data/expected/feature_spec.yaml
"""

from __future__ import annotations

import copy
import datetime as dt
import json
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from .emotion import compute_metrics
from .expectations import emotion_class
from .schemas import AuditReport, PolicyResult, SOPResult
from .scoring import score_audit
from .topic import candidate_step_ids, detect_signals, detect_topic

DEVIATION = {"partial", "missed"}
TIMING_GAPS = ("dead_air", "interruption", "hold_too_long")
POS_TONES = {"warm", "empathetic"}
NEG_TONES = {"defensive", "dismissive", "rushed"}
HTML_SECTIONS = ["What happened", "The call in numbers", "Emotion timeline", "Coaching", "Call script", "Company rules", "Conversation gaps",
                 "Transcript", "How the score was worked out", "Technical details"]

OPS = {">=": lambda a, b: a >= b - 1e-9, "<=": lambda a, b: a <= b + 1e-9, "==": lambda a, b: abs(a - b) < 1e-9}


def _row(feature: str, item: str, expected, actual, ok: bool, level: str = "hard", metrics: Optional[Dict[str, bool]] = None) -> dict:
    return {"feature": feature, "item": item, "expected": str(expected), "actual": str(actual), "ok": bool(ok), "level": level, "metrics": metrics or {}}


# ---------------------------------------------------------------------------------- offline rows (no AI)
def offline_rows(call, raw: dict, exp: dict, kb) -> List[dict]:
    rows: List[dict] = []
    res = detect_topic(call.turns)
    accept = (res.topic == exp["topic"]["label"] or res.topic in exp["topic"].get("also_ok", [])
              or (exp["topic"]["also_ok_if_angry"] and "angry_customer" in res.signals))
    rows.append(_row("topic", "Topic", exp["topic"]["label"] + (" (or anything, if the caller is angry)" if exp["topic"]["also_ok_if_angry"] else "")
                     + (" or " + " / ".join(exp["topic"]["also_ok"]) if exp["topic"].get("also_ok") else ""), res.topic, accept,
                     metrics={"topic_accuracy": accept}))
    for s in exp["signals_required"]:
        ok = s in res.signals
        rows.append(_row("signals", f"Signal: {s.replace('_', ' ')}", "detected", "detected" if ok else "missing", ok, metrics={"signals_recall": ok}))
    cand = set(candidate_step_ids(kb, res.topic, res.signals))
    missing = [s for s in exp["candidate_steps_must_include"] if s not in cand]
    rows.append(_row("candidate_steps", "Steps put up for judging", f"all {len(exp['candidate_steps_must_include'])} labelled steps",
                     "all present" if not missing else "missing " + ", ".join(missing), not missing, metrics={"candidate_coverage": not missing}))
    m = compute_metrics(call)
    em = exp["metrics"]
    for label, e, a in (("Long silences (dead air)", em["dead_air_events"], len(m.dead_air_events)),
                        ("Agent talked over the customer", em["agent_interruptions"], m.agent_interruptions),
                        ("Holds over 2 minutes", em["holds_over_limit"], len(m.hold_events)),
                        ("Number of holds", em["holds"], len(m.holds))):
        rows.append(_row("timing", label, e, a, e == a, metrics={"timing_exact": e == a}))
    ok_ratio = abs(m.agent_talk_ratio - em["agent_talk_ratio"]) <= 0.06
    rows.append(_row("timing", "Agent talk share", f"{em['agent_talk_ratio']:.2f} ± 0.06", f"{m.agent_talk_ratio:.2f}", ok_ratio, "soft", {"talk_ratio_ok": ok_ratio}))
    # scoring arithmetic: feed the labelled findings into the real scoring code, compare with independent arithmetic
    rubric = {s["step_id"]: s for s in kb.rubric["sop_steps"]}
    sop = [SOPResult(step_id=s, status=st, weight=rubric[s]["weight"], critical=bool(rubric[s].get("critical")), title=s) for s, st in exp["steps"].items()]
    seen, pol = set(), []
    for v in exp["violations"]:
        if v["clause"] not in seen:
            seen.add(v["clause"])
            pol.append(PolicyResult(clause_id=v["clause"], verdict="violation", severity=v["severity"]))
    sc = score_audit(sop, pol, 5, 5, kb.rubric)
    e_sop, e_pol = exp["score"]["sop_score_expected"], exp["score"]["policy_score_expected"]
    rows.append(_row("scoring_formula", "Script points", e_sop, sc.sop_score, abs(sc.sop_score - e_sop) <= 0.11, metrics={"formula_sop_ok": abs(sc.sop_score - e_sop) <= 0.11}))
    rows.append(_row("scoring_formula", "Company-rules points", e_pol, sc.policy_score, abs(sc.policy_score - e_pol) <= 0.11, metrics={"formula_policy_ok": abs(sc.policy_score - e_pol) <= 0.11}))
    if exp["score"]["critical_failure_expected"]:
        ok = sc.overall <= 70.0 and sc.critical_failure
        rows.append(_row("scoring_formula", "Critical cap on perfect marks elsewhere", "70 or lower, flagged", f"{sc.overall:g}" + (", flagged" if sc.critical_failure else ", not flagged"), ok,
                         metrics={"formula_cap_ok": ok}))
    return rows


# ---------------------------------------------------------------------------------- AI-dependent rows
def audit_rows(rep: AuditReport, exp: dict) -> List[dict]:
    rows: List[dict] = []
    actual = {r.step_id: r for r in rep.sop_results}
    for sid, e_status in exp["steps"].items():
        r = actual.get(sid)
        a_status = "not judged" if (r is None or r.status == "not_applicable") else r.status
        ok = a_status == e_status
        m = {"step_exact": ok} if a_status != "not judged" else {}
        if e_status in DEVIATION and a_status != "not judged":
            m["deviation_recall"] = a_status in DEVIATION
        if a_status in DEVIATION:
            m["deviation_precision"] = e_status in DEVIATION
        rows.append(_row("sop_steps", f"{sid} {(r.title if r else '')}".strip(), e_status, a_status, ok, metrics=m))
    # policy
    found = [p for p in rep.policy_results if p.verdict == "violation"]
    used = set()
    for v in exp["violations"]:
        hit = next((i for i, p in enumerate(found) if i not in used and p.clause_id == v["clause"] and abs((p.turn or 0) - v["turn"]) <= 2), None)
        if hit is None:
            rows.append(_row("policy", f"Violation {v['clause']} (turn {v['turn']})", "found", "not found", False, metrics={"violation_recall": False}))
        else:
            used.add(hit)
            p = found[hit]
            rows.append(_row("policy", f"Violation {v['clause']} (turn {v['turn']})", "found", f"found at turn {p.turn}", True, metrics={"violation_recall": True, "violation_precision": True}))
            sev_ok = p.severity == v["severity"]
            rows.append(_row("policy", f"Severity of {v['clause']}", v["severity"], p.severity, sev_ok, "soft", {"severity_agreement": sev_ok}))
    for i, p in enumerate(found):
        if i not in used:
            rows.append(_row("policy", f"Unexpected violation {p.clause_id} (turn {p.turn})", "none", f"{p.clause_id} ({p.severity})", False, metrics={"violation_precision": False}))
    # evidence
    bad = [r.step_id for r in rep.sop_results if r.status in ("followed", "partial") and not r.evidence_verified]
    bad += [p.clause_id for p in rep.policy_results if p.verdict == "violation" and not p.evidence_verified]
    rows.append(_row("evidence", "Every quote found in the transcript", "no unverifiable quote", "none" if not bad else ", ".join(bad), not bad, metrics={"evidence_ok": not bad}))
    # scoring
    sc, es = rep.scores, exp["score"]
    rows.append(_row("scoring_outcome", "Grade", " or ".join(es["grade_in"]), sc.grade, sc.grade in es["grade_in"], metrics={"grade_ok": sc.grade in es["grade_in"]}))
    lo, hi = es["overall_band"]
    rows.append(_row("scoring_outcome", "Overall score band", f"{lo} to {hi}", f"{sc.overall:g}", lo <= sc.overall <= hi, metrics={"band_ok": lo <= sc.overall <= hi}))
    if es["critical_failure_expected"]:
        ok = sc.critical_failure and sc.overall <= es["max_overall_if_critical"]
        rows.append(_row("scoring_outcome", "Critical failure flagged and capped", "flagged, 70 or lower", f"{'flagged' if sc.critical_failure else 'not flagged'}, {sc.overall:g}", ok, metrics={"critical_ok": ok}))
    else:
        ok = not sc.critical_failure
        rows.append(_row("scoring_outcome", "No critical failure", "none", "none" if ok else "flagged", ok, metrics={"critical_ok": ok}))
    tol = es["sop_score_tolerance"]
    ok = abs(sc.sop_score - es["sop_score_expected"]) <= tol
    rows.append(_row("scoring_outcome", "Script score", f"{es['sop_score_expected']:g} ± {tol:g}", f"{sc.sop_score:g}", ok, "soft", {"sop_score_ok": ok}))
    tol = es["overall_estimate_tolerance"]
    ok = abs(sc.overall - es["overall_estimate"]) <= tol
    rows.append(_row("scoring_outcome", "Overall score vs estimate", f"{es['overall_estimate']:g} ± {tol:g}", f"{sc.overall:g}", ok, "soft", {"overall_estimate_ok": ok}))
    # emotion
    ee = exp["emotion"]
    if rep.emotion.points:
        for label, e, a, key in (("Customer's starting mood", ee["customer_start"], emotion_class(rep.emotion.start), "customer_start_ok"),
                                 ("Customer's ending mood", ee["customer_end"], emotion_class(rep.emotion.end), "customer_end_ok"),
                                 ("Mood trend", ee["customer_trend"], rep.emotion.trend, "customer_trend_ok")):
            rows.append(_row("emotion", label, e, a, e == a, "soft", {key: e == a}))
    tones = [p.emotion for p in rep.agent_tone.points]
    if tones and ee["agent"] != "any":
        pos = sum(t in POS_TONES for t in tones) / len(tones)
        neg = sum(t in NEG_TONES for t in tones)
        ok = (pos >= 0.5 and neg / len(tones) <= 0.2) if ee["agent"] == "mostly_positive" else neg >= 1
        rows.append(_row("emotion", "Agent tone", "mostly warm or calm" if ee["agent"] == "mostly_positive" else "some defensive, dismissive or rushed turns",
                         f"{pos:.0%} warm/empathetic, {neg} negative turn(s)", ok, "soft", {"agent_tone_ok": ok}))
    # gaps
    types = {g.gap_type for g in rep.gaps}
    for g in TIMING_GAPS:
        e = g in exp["gaps_required"]
        rows.append(_row("gaps", f"Gap: {g.replace('_', ' ')}", "reported" if e else "not reported", "reported" if g in types else "not reported", e == (g in types), metrics={"timing_gap_ok": e == (g in types)}))
    for g in exp["gaps_required"]:
        if g not in TIMING_GAPS:
            rows.append(_row("gaps", f"Gap: {g.replace('_', ' ')}", "reported", "reported" if g in types else "not reported", g in types, "soft", {"ai_gap_recall": g in types}))
    rows.append(_row("efficiency", "AI requests for this call", f"{exp['requests_max']} or fewer", rep.meta.llm_requests, rep.meta.llm_requests <= exp["requests_max"], metrics={"requests_ok": rep.meta.llm_requests <= exp["requests_max"]}))
    return rows


def call_comparison(rep: AuditReport, call, raw: dict, exp: dict, kb) -> List[dict]:
    """Everything the Test lab shows for one call: offline rows (deterministic code) + audit rows (AI)."""
    return offline_rows(call, raw, exp, kb) + audit_rows(rep, exp)


# ---------------------------------------------------------------------------------- report-output rows
def output_rows(rep: AuditReport) -> List[dict]:
    from .report import render_html, render_pdf

    rows: List[dict] = []
    html = render_html(rep)
    missing = [s for s in HTML_SECTIONS if s not in html]
    rows.append(_row("report_outputs", "HTML sections", "all 10 present", "all present" if not missing else "missing: " + ", ".join(missing), not missing, metrics={"html_sections_ok": not missing}))
    try:
        pdf = render_pdf(rep)
        ok = pdf[:4] == b"%PDF" and len(pdf) > 3000
        rows.append(_row("report_outputs", "PDF", "valid PDF", f"{len(pdf)} bytes" if ok else "invalid", ok, metrics={"pdf_ok": ok}))
    except Exception as exc:  # noqa: BLE001
        rows.append(_row("report_outputs", "PDF", "valid PDF", f"error: {str(exc)[:80]}", False, metrics={"pdf_ok": False}))
    back = AuditReport.model_validate_json(rep.model_dump_json())
    rows.append(_row("report_outputs", "JSON round trip", "identical", "identical" if back == rep else "different", back == rep, metrics={"json_roundtrip_ok": back == rep}))
    evil = copy.deepcopy(rep)
    evil.transcript.turns[0].text = "<script>alert(1)</script> $x$ `code`"
    evil.summary = "<img src=x onerror=alert(2)>"
    page = render_html(evil)
    safe = "<script>alert(1)" not in page and "<img src=x" not in page and "&lt;script&gt;" in page
    rows.append(_row("report_outputs", "Hostile text is escaped", "no HTML injection", "escaped" if safe else "INJECTED", safe, metrics={"html_safe_ok": safe}))
    return rows


# ---------------------------------------------------------------------------------- aggregation
def aggregate(rows: Iterable[dict]) -> Dict[str, Tuple[int, int]]:
    acc: Dict[str, List[int]] = defaultdict(lambda: [0, 0])
    for r in rows:
        for k, ok in r["metrics"].items():
            acc[k][1] += 1
            acc[k][0] += 1 if ok else 0
    return {k: (v[0], v[1]) for k, v in acc.items()}


def evaluate_spec(spec: dict, rates: Dict[str, Tuple[int, int]], ai_available: bool = True) -> List[dict]:
    out = []
    for f in spec["features"]:
        checks = []
        for c in f["checks"]:
            ok_n, tot = rates.get(c["metric"], (0, 0))
            if tot == 0:
                status, actual = "SKIP", "no data" if (ai_available or not f["needs_ai"]) else "needs AI audits"
            else:
                rate = ok_n / tot
                actual = f"{rate:.0%} ({ok_n}/{tot})"
                passed = OPS[c["op"]](rate, c["value"])
                status = "PASS" if passed else ("FAIL" if c["level"] == "hard" else "WARN")
            checks.append({"metric": c["metric"], "label": c["label"], "expected": f"{c['op']} {c['value']:.0%}", "actual": actual, "status": status, "level": c["level"]})
        statuses = {c["status"] for c in checks}
        status = "FAIL" if "FAIL" in statuses else "WARN" if "WARN" in statuses else "PASS" if "PASS" in statuses else "SKIP"
        out.append({"id": f["id"], "title": f["title"], "plain": f["plain"], "needs_ai": f["needs_ai"], "status": status, "checks": checks})
    return out


def run_all(files: Sequence[Path], kb, expected: Dict[str, dict], spec: dict, reports: Optional[Dict[str, AuditReport]] = None) -> dict:
    """Offline features for every expected call; AI features for the calls that have an audit."""
    from .transcript_io import load_transcript_json

    reports = reports or {}
    rows_by_call: Dict[str, List[dict]] = {}
    for p in files:
        cid = p.stem
        if cid not in expected:
            continue
        call, raw = load_transcript_json(p)
        rows = offline_rows(call, raw, expected[cid], kb)
        if cid in reports:
            rows += audit_rows(reports[cid], expected[cid])
        rows_by_call[cid] = rows
    all_rows = [r for rows in rows_by_call.values() for r in rows]
    sample = next(iter(reports.values()), None)
    out_rows = output_rows(sample) if sample is not None else []
    rates = aggregate(all_rows + out_rows)
    features = evaluate_spec(spec, rates, ai_available=bool(reports))
    counts = defaultdict(int)
    for f in features:
        counts[f["status"]] += 1
    return {"generated_at": dt.datetime.now().isoformat(timespec="seconds"), "calls": sorted(rows_by_call), "audited_calls": sorted(reports),
            "summary": dict(counts), "features": features, "rows": rows_by_call, "output_rows": out_rows}


def to_markdown(result: dict) -> str:
    L = ["# Feature test report", "", f"Generated {result['generated_at']} · {len(result['calls'])} calls, {len(result['audited_calls'])} with AI audits", "",
         "| Result | Count |", "|---|---|"] + [f"| {k} | {v} |" for k, v in sorted(result["summary"].items())] + ["", "| Feature | Check | Expected | Actual | Result |", "|---|---|---|---|---|"]
    for f in result["features"]:
        for c in f["checks"]:
            L.append(f"| {f['title']} | {c['label']} | {c['expected']} | {c['actual']} | {c['status']} |")
    fails = [(cid, r) for cid, rows in result["rows"].items() for r in rows if not r["ok"]]
    if fails:
        L += ["", "## Calls where actual differs from expected", "", "| Call | Feature | Item | Expected | Actual | Level |", "|---|---|---|---|---|---|"]
        for cid, r in fails:
            L.append(f"| {cid} | {r['feature']} | {r['item']} | {r['expected']} | {r['actual']} | {r['level']} |")
    return "\n".join(L) + "\n"
