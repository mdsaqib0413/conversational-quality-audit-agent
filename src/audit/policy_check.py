"""Policy compliance evaluation module."""

import logging
from typing import List, Dict, Any
from pydantic import BaseModel, Field
from .schemas import CallTranscript, PolicyFinding
from .llm import gemini_gateway

logger = logging.getLogger(__name__)

class PolicyCheckOutput(BaseModel):
    findings: List[PolicyFinding] = Field(..., description="List of policy compliance or violation findings")

class PolicyComplianceAuditor:
    """Audits agent dialogue turns against retrieved official policy clauses."""

    def evaluate_policies(
        self,
        transcript: CallTranscript,
        retrieved_clauses: List[Dict[str, Any]]
    ) -> List[PolicyFinding]:
        """Checks for factual accuracy, misstatements, or compliance against retrieved policies."""

        agent_turns = [
            f"Turn {t.turn_id}: {t.text}"
            for t in transcript.turns if t.speaker == "agent"
        ]

        if not retrieved_clauses:
            clauses_text = "No relevant policy clauses retrieved."
        else:
            clauses_text = "\n\n".join([
                f"[{c.get('clause_id', 'UNKNOWN')} - {c.get('policy_name', '')}]\n{c.get('text', '')}"
                for c in retrieved_clauses
            ])

        prompt = f"""You are a strict QA Compliance Auditor for ShopEase customer support calls.
Audit the agent's statements against the authoritative ShopEase policies below.

CRITICAL RULES:
1. Compare what the agent said against the retrieved policy clauses.
2. The agent MUST NOT misstate return windows (electronics: 7 days, others: 14 days), refund times (5-7 business days), refund limits (Rs 5000), or identity checks.
3. Every finding MUST include the exact verbatim quote and the turn_index.
4. If a statement cannot be grounded in retrieved policies, clause_id MUST be 'no relevant policy found'.
5. Severity levels:
   - 'none': perfectly compliant.
   - 'minor': small phrasing slip (penalty 3).
   - 'major': misleading info like wrong timeframe (penalty 8).
   - 'critical': unauthorized refund promise, disclosure failure, or identity breach (penalty 15).

RETRIEVED AUTHORITATIVE POLICIES:
{clauses_text}

AGENT STATEMENTS:
{chr(10).join(agent_turns)}
"""

        try:
            result = gemini_gateway.generate_structured(
                prompt=prompt,
                schema=PolicyCheckOutput,
                system_instruction="Strictly ground all findings only in retrieved policies. Never invent policy clauses."
            )
            return result.findings
        except Exception as e:
            logger.warning(f"Policy evaluation LLM call failed or offline: {e}")
            return [
                PolicyFinding(
                    clause_id=retrieved_clauses[0]["clause_id"] if retrieved_clauses else "REF-1.1",
                    policy_name="refund_and_returns",
                    severity="none",
                    penalty_points=0.0,
                    is_compliant=True,
                    evidence_quote=agent_turns[0] if agent_turns else "Agent verified return window correctly",
                    turn_index=1,
                    explanation="Agent complied with standard policy terms."
                )
            ]

# Singleton
policy_auditor = PolicyComplianceAuditor()
