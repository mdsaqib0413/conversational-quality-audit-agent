"""Deterministic scoring from data/rubric.yaml. No LLM involved, so the same findings always give the same score."""

from __future__ import annotations

from typing import Dict, List

from .schemas import PolicyResult, ScoreBreakdown, SOPResult

MULTIPLIER = {"followed": 1.0, "partial": 0.5, "missed": 0.0}


def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def apply_sop_points(results: List[SOPResult]) -> None:
    for r in results:
        if r.status == "not_applicable":
            r.points_possible, r.points_earned = 0.0, 0.0
        else:
            r.points_possible = float(r.weight)
            r.points_earned = r.weight * MULTIPLIER[r.status]


def apply_policy_penalties(results: List[PolicyResult], rubric: dict) -> None:
    pen = rubric["scoring_formula"]["policy_compliance_penalties"]
    for r in results:
        r.penalty = float(pen.get(r.severity, 0)) if r.verdict == "violation" else 0.0


def grade_for(score: float, rubric: dict):
    scale = rubric["grade_scale"]
    for g in sorted(scale, key=lambda k: -float(scale[k]["min_score"])):
        if score >= float(scale[g]["min_score"]):
            return g, scale[g].get("label", "")
    return "D", scale.get("D", {}).get("label", "")


DEFAULT_TIMING = {"dead_air": 1.0, "agent_interruption": 1.0, "max_total": 3.0}


def timing_penalty(dead_air_events: int, agent_interruptions: int, rubric: dict):
    cfg = {**DEFAULT_TIMING, **(rubric.get("scoring_formula", {}).get("timing_penalties") or {})}
    notes: List[str] = []
    total = 0.0
    if dead_air_events:
        pts = min(dead_air_events * float(cfg["dead_air"]), 5.0)
        total += pts
        notes.append(f"{dead_air_events} dead-air gap(s) of 4s or more: -{pts:g}")
    if agent_interruptions:
        pts = agent_interruptions * float(cfg["agent_interruption"])
        total += pts
        notes.append(f"{agent_interruptions} agent interruption(s): -{pts:g}")
    total = min(total, float(cfg["max_total"]))
    return total, notes


def score_audit(sop: List[SOPResult], policy: List[PolicyResult], empathy_0_5: float, communication_0_5: float,
                rubric: dict, dead_air_events: int = 0, agent_interruptions: int = 0,
                policy_applicable: bool = True) -> ScoreBreakdown:
    cats = rubric["categories"]
    apply_sop_points(sop)
    apply_policy_penalties(policy, rubric)

    possible = sum(r.points_possible for r in sop)
    earned = sum(r.points_earned for r in sop)
    sop_score = (earned / possible) * cats["sop_adherence"] if possible else 0.0

    penalty_total = sum(r.penalty for r in policy)
    if policy_applicable:
        policy_score = max(0.0, cats["policy_compliance"] - penalty_total)
    else:
        policy_score = 0.0   # no topic-specific policy applies; category excluded

    empathy = clamp(empathy_0_5, 0, 5) / 5 * cats["empathy"]
    comm = clamp(communication_0_5, 0, 5) / 5 * cats["communication"]
    t_pen, t_notes = timing_penalty(dead_air_events, agent_interruptions, rubric)
    comm = max(0.0, comm - t_pen)

    before = sop_score + policy_score + empathy + comm
    if not policy_applicable:
        rem_weight = cats.get("sop_adherence", 0) + cats.get("empathy", 0) + cats.get("communication", 0)
        if rem_weight > 0:
            before = before * (100.0 / rem_weight)
        # Cap general-clause penalty at the policy category's renormalised share (~42.86 pts)
        policy_renorm_share = cats.get("policy_compliance", 30) * (100.0 / rem_weight) if rem_weight > 0 else 0.0
        capped_penalty = min(penalty_total, policy_renorm_share)
        before = max(0.0, before - capped_penalty)
    cap = float(rubric["scoring_formula"]["critical_failure_cap"]["max_overall_score"])
    cap_reasons: List[str] = []
    for r in sop:
        if r.critical and r.status == "missed":
            cap_reasons.append(f"Critical step {r.step_id} ({r.title}) was missed")
    for p in policy:
        if p.verdict == "violation" and p.severity == "critical" and p.clause_id.startswith("PRV"):
            cap_reasons.append(f"Critical privacy violation ({p.clause_id})")
    overall = min(before, cap) if cap_reasons else before
    reasons: List[str] = list(cap_reasons)
    if not policy_applicable:
        reasons.append("No topic-specific policy applies; general clauses (recording disclosure, identity verification) were checked.")
    if not possible:
        reasons.append("No applicable SOP steps were judged; SOP score is 0")
    grade, label = grade_for(overall, rubric)
    return ScoreBreakdown(
        sop_score=round(sop_score, 1), policy_score=round(policy_score, 1), empathy_score=round(empathy, 1),
        communication_score=round(comm, 1), overall_before_cap=round(before, 1), overall=round(overall, 1),
        grade=grade, grade_label=label, critical_failure=bool(cap_reasons),
        cap_reasons=reasons, sop_points_earned=round(earned, 1), sop_points_possible=round(possible, 1),
        policy_penalty_total=round(penalty_total, 1), timing_penalty=round(t_pen, 1), timing_notes=t_notes,
        policy_applicable=policy_applicable,
    )
