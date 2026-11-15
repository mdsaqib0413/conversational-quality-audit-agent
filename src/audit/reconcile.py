"""Deterministic reconciliation rules for audit findings and scores.

Enforces physical reality constraints over LLM judgments:
- HLD-02 (2-minute hold ceiling): If measured hold duration does not exceed the 120s ceiling
  (i.e. metrics.holds has no hold with exceeded=True), any 'missed' judgment on HLD-02 is
  overridden to 'followed' with an explanation note and full points.
"""

from __future__ import annotations

import logging
from typing import Any, List, Optional

from .schemas import AuditReport, SOPResult
from .scoring import score_audit

logger = logging.getLogger("audit.reconcile")


def reconcile_hld02(sop_results: List[SOPResult], metrics: Any) -> bool:
    """Override HLD-02 to 'followed' if measured holds did not exceed 120 seconds.

    Returns True if an override was applied, False otherwise.
    """
    if not metrics:
        return False

    # Extract holds from metrics (supports ConversationMetrics object or dict)
    if hasattr(metrics, "holds"):
        holds = metrics.holds or []
    elif isinstance(metrics, dict):
        holds = metrics.get("holds") or []
    else:
        holds = []

    # If any hold exceeded 120 seconds, the missed judgment is legitimate
    has_exceeded = any(
        (getattr(h, "exceeded", False) if not isinstance(h, dict) else h.get("exceeded", False))
        for h in holds
    )
    if has_exceeded:
        return False

    overridden = False
    for r in sop_results:
        if r.step_id == "HLD-02" and r.status == "missed":
            r.status = "followed"
            r.points_possible = float(r.weight) if r.weight else 4.0
            r.points_earned = r.points_possible
            r.missing = ""

            if holds:
                max_sec = max(
                    (getattr(h, "seconds", 0.0) if not isinstance(h, dict) else h.get("seconds", 0.0))
                    for h in holds
                )
                note = f"Overridden: measured hold {max_sec:.1f} s is under the 120 s ceiling."
            else:
                note = "Overridden: no hold exceeded the 120 s ceiling."

            if r.reason:
                if note not in r.reason:
                    r.reason = f"{r.reason.strip()} {note}"
            else:
                r.reason = note

            overridden = True
            logger.info("Overrode HLD-02 to 'followed' (measured hold duration compliant)")

    return overridden


def reconcile_report(report: AuditReport, rubric: Optional[dict] = None) -> AuditReport:
    """Apply deterministic reconciliation to an AuditReport (fresh or loaded from cache).

    If HLD-02 is overridden, recalculates scores, updates findings, removes coaching tips,
    and updates strengths accordingly.
    """
    if not report.sop_results:
        return report

    changed = reconcile_hld02(report.sop_results, report.metrics)
    if not changed:
        return report

    # 1. Update structured findings for HLD-02
    if report.findings:
        max_sec = None
        if report.metrics and report.metrics.holds:
            max_sec = max(
                (getattr(h, "seconds", 0.0) if not isinstance(h, dict) else h.get("seconds", 0.0))
                for h in report.metrics.holds
            )
        note = (
            f"Overridden: measured hold {max_sec:.1f} s is under the 120 s ceiling."
            if max_sec is not None
            else "Overridden: no hold exceeded the 120 s ceiling."
        )

        for f in report.findings:
            if f.criterion_id == "HLD-02":
                f.verdict = "followed"
                if f.explanation and note not in f.explanation:
                    f.explanation = f"{f.explanation.strip()} {note}"
                elif not f.explanation:
                    f.explanation = note

    # 2. Remove obsolete HLD-02 coaching tip
    if report.coaching:
        report.coaching = [c for c in report.coaching if "HLD-02" not in c.title]

    # 3. Recompute scores with the rubric
    if rubric is None:
        from .rag import get_kb

        rubric = get_kb().rubric

    comm = ((report.scores.clarity_rating or 5) + (report.scores.professionalism_rating or 5) +
            (report.scores.ownership_rating or 5) + (report.scores.closure_rating or 5)) / 4.0
    agent_dead_air = (
        sum(1 for g in report.metrics.dead_air_events if "not penalised" not in g.detail)
        if report.metrics else 0
    )
    interruptions = report.metrics.agent_interruptions if report.metrics else 0
    policy_app = report.scores.policy_applicable if report.scores.policy_applicable is not None else True

    new_scores = score_audit(
        report.sop_results,
        report.policy_results,
        report.scores.empathy_rating if report.scores.empathy_rating is not None else 5,
        comm,
        rubric,
        dead_air_events=agent_dead_air,
        agent_interruptions=interruptions,
        policy_applicable=policy_app,
    )

    # Preserve rating dimensions
    new_scores.empathy_rating = report.scores.empathy_rating
    new_scores.clarity_rating = report.scores.clarity_rating
    new_scores.professionalism_rating = report.scores.professionalism_rating
    new_scores.ownership_rating = report.scores.ownership_rating
    new_scores.closure_rating = report.scores.closure_rating
    report.scores = new_scores

    # 4. Update strengths if all critical SOP steps are now followed
    if report.strengths is not None:
        crit = [r for r in report.sop_results if r.critical and r.status != "not_applicable"]
        if crit and all(r.status == "followed" for r in crit):
            s_msg = f"Completed all {len(crit)} critical SOP steps that applied to this call."
            if s_msg not in report.strengths:
                report.strengths.append(s_msg)

    return report
