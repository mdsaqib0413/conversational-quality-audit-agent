"""Rubric scoring engine calculating category scores, penalties, and overall grades."""

import logging
from typing import List, Dict, Any, Tuple
from .schemas import (
    SOPStepEvaluation,
    PolicyFinding,
    CategoryScoreBreakdown,
    AuditReport
)

logger = logging.getLogger(__name__)

SEVERITY_PENALTIES = {
    "minor": 3.0,
    "major": 8.0,
    "critical": 15.0,
    "none": 0.0
}

class RubricScorer:
    """Computes call audit scores according to the formal rubric."""

    def __init__(self, rubric_data: Dict[str, Any] = None):
        self.rubric = rubric_data or {}
        self.category_weights = self.rubric.get("categories", {
            "sop_adherence": 40.0,
            "policy_compliance": 30.0,
            "empathy": 15.0,
            "communication": 15.0
        })

    def calculate_scores(
        self,
        call_id: str,
        sop_evaluations: List[SOPStepEvaluation],
        policy_findings: List[PolicyFinding],
        empathy_score_raw: float = 14.0,
        communication_score_raw: float = 14.0
    ) -> AuditReport:
        """Calculates final normalized scores, applies violation penalties and critical failure caps."""

        # 1. SOP Adherence Score (Max 40 points)
        total_weight = sum(ev.weight for ev in sop_evaluations)
        earned_weight = sum(ev.points_awarded for ev in sop_evaluations)
        sop_percentage = (earned_weight / total_weight) if total_weight > 0 else 1.0
        sop_score = round(sop_percentage * self.category_weights["sop_adherence"], 2)

        # Check for critical failures in SOP
        has_critical_failure = any(
            ev.is_critical and ev.status == "missed"
            for ev in sop_evaluations
        )

        # 2. Policy Compliance Score (Max 30 points)
        base_policy_score = float(self.category_weights["policy_compliance"])
        total_policy_penalties = 0.0

        for finding in policy_findings:
            if not finding.is_compliant:
                sev = finding.severity.lower()
                pen = SEVERITY_PENALTIES.get(sev, 0.0)
                total_policy_penalties += pen
                finding.penalty_points = pen

        policy_score = max(0.0, round(base_policy_score - total_policy_penalties, 2))

        # 3. Empathy (Max 15 points) and Communication (Max 15 points)
        empathy_score = min(float(self.category_weights["empathy"]), max(0.0, empathy_score_raw))
        comm_score = min(float(self.category_weights["communication"]), max(0.0, communication_score_raw))

        # Overall Raw Score
        raw_overall = round(sop_score + policy_score + empathy_score + comm_score, 1)

        # Cap overall score at 70 if any critical step was missed
        if has_critical_failure:
            overall_score = min(70.0, raw_overall)
        else:
            overall_score = raw_overall

        # Determine Letter Grade (A: 90-100, B: 80-89, C: 70-79, D: <70)
        grade = self._get_grade(overall_score)

        category_breakdown = CategoryScoreBreakdown(
            sop_adherence=sop_score,
            policy_compliance=policy_score,
            empathy=empathy_score,
            communication=comm_score
        )

        # Generate summary coaching tips
        highlights = ["Maintained polite tone throughout conversation."]
        coaching = []
        if has_critical_failure:
            coaching.append("Critical failure observed: Always verify identity or disclosure statement before proceeding.")
        if total_policy_penalties > 0:
            coaching.append(f"Review policy clauses: {total_policy_penalties} points lost due to policy inaccuracy.")

        return AuditReport(
            call_id=call_id,
            overall_score=overall_score,
            grade=grade,
            critical_failure=has_critical_failure,
            category_scores=category_breakdown,
            sop_evaluations=sop_evaluations,
            policy_findings=policy_findings,
            positive_highlights=highlights,
            coaching_recommendations=coaching
        )

    def _get_grade(self, score: float) -> str:
        if score >= 90.0:
            return "A"
        elif score >= 80.0:
            return "B"
        elif score >= 70.0:
            return "C"
        else:
            return "D"

# Singleton
scorer = RubricScorer()
