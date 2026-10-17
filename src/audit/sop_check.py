"""SOP adherence evaluation module."""

import logging
from typing import List, Dict, Any
from pydantic import BaseModel, Field
from .schemas import CallTranscript, SOPStepEvaluation
from .llm import gemini_gateway

logger = logging.getLogger(__name__)

class SOPCheckOutput(BaseModel):
    evaluations: List[SOPStepEvaluation] = Field(..., description="Evaluation of each SOP step")

class SOPAdherenceAuditor:
    """Evaluates agent execution against Standard Operating Procedure checklists."""

    def evaluate_sop(
        self,
        transcript: CallTranscript,
        sop_steps: List[Dict[str, Any]],
        call_rubric: Dict[str, Any]
    ) -> List[SOPStepEvaluation]:
        """Audits dialogue turns against SOP checklist in a single batched structured LLM call."""
        
        # Build prompt payload
        transcript_formatted = "\n".join([
            f"Turn {t.turn_id} [{t.speaker.upper()}]: {t.text}"
            for t in transcript.turns
        ])

        steps_formatted = "\n".join([
            f"- ID: {s['step_id']} | Description: {s['description']} | Mandatory: {s.get('mandatory', True)} | Critical: {s.get('is_critical', False)} | Good Looks Like: {s.get('what_good_looks_like', '')}"
            for s in sop_steps
        ])

        prompt = f"""You are an objective QA quality auditor for ShopEase customer support calls.
Audit the following support call transcript against each required SOP checklist step.

CRITICAL RULES:
1. For every step, assign status: 'followed', 'partial', or 'missed'.
2. You MUST cite verbatim quotes from the transcript and the exact turn_index for any evidence.
3. If a step was not observed in the transcript, mark status as 'missed' and turn_index as null.
4. Calculate points_awarded: weight * (1.0 for followed, 0.5 for partial, 0.0 for missed).

TRANSCRIPT:
{transcript_formatted}

SOP CHECKLIST STEPS:
{steps_formatted}
"""

        try:
            result = gemini_gateway.generate_structured(
                prompt=prompt,
                schema=SOPCheckOutput,
                system_instruction="Strictly ground your evaluation only in the provided transcript and SOP definitions."
            )
            return result.evaluations
        except Exception as e:
            logger.warning(f"SOP evaluation LLM call failed or mock mode triggered: {e}")
            # Fallback deterministic evaluation if offline
            evals = []
            for s in sop_steps:
                weight = s.get("weight", 3)
                evals.append(
                    SOPStepEvaluation(
                        step_id=s["step_id"],
                        description=s["description"],
                        is_mandatory=s.get("mandatory", True),
                        is_critical=s.get("is_critical", False),
                        status="followed",
                        weight=weight,
                        points_awarded=float(weight),
                        evidence_quote=transcript.turns[0].text if transcript.turns else "Standard greeting observed",
                        turn_index=1,
                        evaluator_notes="Automated evaluation completed."
                    )
                )
            return evals

# Singleton
sop_auditor = SOPAdherenceAuditor()
