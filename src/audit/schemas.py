"""Pydantic schemas for the Conversational Quality Audit Agent.

All structured outputs and data contracts are defined here.
"""

from typing import List, Optional, Literal
from pydantic import BaseModel, Field

class SpeakerRole(str):
    AGENT = "agent"
    CUSTOMER = "customer"
    SUPERVISOR = "supervisor"

class DialogueTurn(BaseModel):
    """Represents a single speech turn in the call transcript."""
    turn_id: int = Field(..., description="1-indexed sequence number of the turn")
    speaker: Literal["agent", "customer", "supervisor"] = Field(..., description="Role of the speaker")
    start_time: float = Field(..., description="Start timestamp in seconds")
    end_time: float = Field(..., description="End timestamp in seconds")
    text: str = Field(..., description="Verbatim transcribed speech")
    emotion: Optional[str] = Field(None, description="Detected emotion (e.g., neutral, frustrated, angry, satisfied)")
    sentiment_score: Optional[float] = Field(None, description="Sentiment polarity from -1.0 to 1.0")
    silence_gap_before: Optional[float] = Field(0.0, description="Silence interval in seconds preceding this turn")

class CallTranscript(BaseModel):
    """Full transcript of an audited customer support call."""
    call_id: str = Field(..., description="Unique call identifier")
    audio_path: Optional[str] = Field(None, description="Path to source audio file")
    duration_seconds: float = Field(0.0, description="Total call duration")
    turns: List[DialogueTurn] = Field(default_factory=list, description="Ordered speech turns")

class SOPStepEvaluation(BaseModel):
    """Evaluation result for an individual SOP checklist step."""
    step_id: str = Field(..., description="Standard SOP Step ID (e.g. GEN-01, REF-S1)")
    description: str = Field(..., description="Short description of the step")
    is_mandatory: bool = Field(True, description="Whether the step is mandatory")
    is_critical: bool = Field(False, description="Whether the step is a critical failure point")
    status: Literal["followed", "partial", "missed"] = Field(..., description="Compliance status")
    weight: int = Field(1, description="Rubric weight (1-5)")
    points_awarded: float = Field(..., description="Calculated points for this step")
    evidence_quote: Optional[str] = Field(None, description="Verbatim quote from the transcript as evidence")
    turn_index: Optional[int] = Field(None, description="Turn ID where the evidence occurs")
    evaluator_notes: Optional[str] = Field(None, description="Reasoning for the assigned score")

class PolicyFinding(BaseModel):
    """Detailed audit finding regarding policy compliance or violation."""
    clause_id: str = Field(..., description="Stable policy clause ID (e.g. REF-1.1, PRV-1.1) or 'no relevant policy found'")
    policy_name: str = Field(..., description="Name of the policy document")
    severity: Literal["none", "minor", "major", "critical"] = Field("none", description="Severity of violation")
    penalty_points: float = Field(0.0, description="Points deducted from policy compliance score")
    is_compliant: bool = Field(True, description="Whether the agent adhered to the policy clause")
    evidence_quote: str = Field(..., description="Verbatim quote from agent speech")
    turn_index: int = Field(..., description="Turn ID containing the quote")
    explanation: str = Field(..., description="Grounded explanation comparing agent statement to retrieved policy clause")

class CategoryScoreBreakdown(BaseModel):
    """Weighted category scores according to rubric."""
    sop_adherence: float = Field(..., description="Score out of 40")
    policy_compliance: float = Field(..., description="Score out of 30")
    empathy: float = Field(..., description="Score out of 15")
    communication: float = Field(..., description="Score out of 15")

class AuditReport(BaseModel):
    """Complete structured audit report for quality assurance and coaching."""
    call_id: str = Field(..., description="Unique call identifier")
    overall_score: float = Field(..., description="Total audit score (0-100)")
    grade: Literal["A", "B", "C", "D"] = Field(..., description="Performance grade based on rubric scale")
    critical_failure: bool = Field(False, description="True if any critical step was missed (caps overall score at 70)")
    category_scores: CategoryScoreBreakdown = Field(..., description="Breakdown across rubric categories")
    sop_evaluations: List[SOPStepEvaluation] = Field(default_factory=list, description="Step-by-step SOP checklist evaluations")
    policy_findings: List[PolicyFinding] = Field(default_factory=list, description="Policy compliance and violation findings")
    positive_highlights: List[str] = Field(default_factory=list, description="Strengths demonstrated by the agent")
    coaching_recommendations: List[str] = Field(default_factory=list, description="Actionable coaching recommendations")

class LiveWindowContext(BaseModel):
    """Data contract for Phase 2: Live call rolling-window analysis."""
    window_turn_count: int = Field(..., description="Number of turns in current sliding window")
    detected_topic: str = Field(..., description="Primary detected customer intent or issue topic")
    confidence: float = Field(..., description="Confidence score of topic detection (0.0 to 1.0)")
    relevant_clause_ids: List[str] = Field(default_factory=list, description="Retrieved policy clause IDs")
    suggested_scripts: List[str] = Field(default_factory=list, description="Recommended standard phrasing for the agent")
