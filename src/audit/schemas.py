"""Data contracts for the Conversational Quality Audit Agent.

Two families of models:

* LLM-facing models (`StepJudgement`, `ConversationAnalysis`, `PolicyAnalysis`, `SegmentLabels`).
  They deliberately have NO default values and no numeric constraints, because Gemini's
  response_schema support is strictest about those. Values are clamped/validated in code.
* Report models (`AuditReport`, `AuditFinding`, `EvidenceItem` and friends) that the app,
  the PDF and the evaluation use.
"""

from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field

# --------------------------------------------------------------------------------------
# Transcript
# --------------------------------------------------------------------------------------
SpeakerName = Literal["agent", "customer"]


class DialogueTurn(BaseModel):
    turn_id: int = Field(..., description="1-indexed turn number")
    speaker: SpeakerName
    start_time: float = 0.0
    end_time: float = 0.0
    text: str
    text_te: Optional[str] = None
    text_roman: Optional[str] = None
    asr_confidence: float = 1.0          # Average word probability [0.0 - 1.0] proxy from ASR engine
    silence_before: float = 0.0          # seconds of silence before this turn started
    overlaps_previous: bool = False      # started while the previous speaker was still talking
    emotion: Optional[str] = None        # filled by the analysis


class CallTranscript(BaseModel):
    call_id: str
    source: Literal["audio", "transcript"] = "transcript"
    language: str = "te"                 # 'te' (Telugu default) or 'en' (English)
    audio_path: Optional[str] = None
    duration_seconds: float = 0.0
    diarization_method: str = "given"
    transcript_quality: Literal["good", "degraded", "unusable"] = "good"
    quality_reason: str = ""
    unreadable_parts: List[str] = Field(default_factory=list)
    turns: List[DialogueTurn] = Field(default_factory=list)

    def text_for_hash(self) -> str:
        return "\n".join(f"{t.turn_id}|{t.speaker}|{t.text}|{t.silence_before:.1f}|{int(t.overlaps_previous)}" for t in self.turns)


# --------------------------------------------------------------------------------------
# LLM-facing schemas (no defaults, no constraints)
# --------------------------------------------------------------------------------------
class SegmentLabel(BaseModel):
    i: int
    speaker: Literal["agent", "customer"]


class SegmentLabels(BaseModel):
    labels: List[SegmentLabel]


class StepJudgement(BaseModel):
    step_id: str
    status: Literal["followed", "partial", "missed", "not_applicable"]
    turn: int            # turn number where the evidence is; 0 when the step is missed / not applicable
    quote: str           # verbatim words from that turn; empty when missed / not applicable
    reason: str          # one short sentence
    missing: str         # required elements NOT found in the transcript (short phrase); "" only if nothing is missing


class TurnEmotion(BaseModel):
    turn: int
    emotion: Literal["angry", "frustrated", "anxious", "confused", "neutral", "satisfied", "happy"]


class TurnTone(BaseModel):
    turn: int
    tone: Literal["warm", "empathetic", "calm", "neutral", "rushed", "defensive", "dismissive"]


class GapFinding(BaseModel):
    gap_type: Literal[
        "no_empathy", "interruption", "dead_air", "unresolved_issue",
        "customer_repeating", "no_summary", "no_closing", "ambiguous_closure", "other",
    ]
    turn: int
    quote: str
    detail: str


class ConversationAnalysis(BaseModel):
    summary: str                  # 2-3 sentences: what the customer wanted and how the call went
    customer_issue: str           # short phrase
    resolved: bool
    steps: List[StepJudgement]
    empathy_score: int            # 0-5
    empathy_evidence: str
    clarity_score: int            # 0-5
    professionalism_score: int    # 0-5
    ownership_score: int          # 0-5
    closure_score: int            # 0-5
    turn_emotions: List[TurnEmotion]      # one per CUSTOMER turn
    agent_tones: List[TurnTone]           # one per AGENT turn
    gaps: List[GapFinding]
    strengths: List[str]
    coaching_tips: List[str]
    risk_flags: List[str] = Field(default_factory=list)


class PolicyClaim(BaseModel):
    turn: int
    quote: str
    claim: str
    clause_id: str                # must be one of the retrieved clause ids, or "none"
    verdict: Literal["compliant", "violation", "unverifiable"]
    severity: Literal["none", "minor", "major", "critical"]
    explanation: str


class PolicyAnalysis(BaseModel):
    claims: List[PolicyClaim]


# --------------------------------------------------------------------------------------
# Report models & Structured Findings (Observed vs Inferred)
# --------------------------------------------------------------------------------------
class EvidenceItem(BaseModel):
    turn_id: int
    speaker: str = "agent"
    start_s: float = 0.0
    end_s: float = 0.0
    quote: str = ""


class AuditFinding(BaseModel):
    finding_id: str
    criterion_id: str
    name: str = ""
    kind: Literal["observed", "inferred"]
    verdict: Literal["followed", "partial", "missed", "not_applicable", "violation", "compliant", "unverifiable"]
    severity: Literal["critical", "major", "minor", "none"] = "none"
    evidence: List[EvidenceItem] = Field(default_factory=list)
    certainty: Literal["high", "medium", "low"] = "high"
    certainty_reason: str = ""
    reviewer_status: Literal["pending", "accepted", "overturned"] = "pending"
    reviewer_note: str = ""
    explanation: str = ""


class SOPResult(BaseModel):
    step_id: str
    title: str = ""
    sop: str = ""
    weight: int = 1
    critical: bool = False
    mandatory: bool = True
    status: Literal["followed", "partial", "missed", "not_applicable"]
    points_earned: float = 0.0
    points_possible: float = 0.0
    turn: Optional[int] = None
    quote: str = ""
    reason: str = ""
    missing: str = ""
    evidence_verified: bool = True
    what_good_looks_like: str = ""
    example_phrase: str = ""


class PolicyResult(BaseModel):
    clause_id: str
    policy_title: str = ""
    verdict: Literal["compliant", "violation", "unverifiable"]
    severity: Literal["none", "minor", "major", "critical"] = "none"
    penalty: float = 0.0
    turn: Optional[int] = None
    quote: str = ""
    claim: str = ""
    explanation: str = ""
    policy_text: str = ""
    evidence_verified: bool = True
    repeat_turns: List[int] = Field(default_factory=list)   # the same mistake repeated later in the call (penalised once)


class GapResult(BaseModel):
    gap_type: str
    turn: Optional[int] = None
    quote: str = ""
    detail: str = ""
    source: Literal["timing", "llm", "script"] = "llm"


class ScoreBreakdown(BaseModel):
    sop_score: float
    policy_score: float
    empathy_score: float
    communication_score: float
    overall_before_cap: float
    overall: float
    grade: Literal["A", "B", "C", "D"]
    grade_label: str = ""
    critical_failure: bool = False
    cap_reasons: List[str] = Field(default_factory=list)
    sop_points_earned: float = 0.0
    sop_points_possible: float = 0.0
    policy_penalty_total: float = 0.0
    policy_applicable: bool = True
    timing_penalty: float = 0.0                       # points taken off communication for dead air / agent interruptions
    timing_notes: List[str] = Field(default_factory=list)
    # the AI's 0-5 ratings behind the empathy and communication points (kept so the score can be explained)
    empathy_rating: int = 0
    clarity_rating: int = 0
    professionalism_rating: int = 0
    ownership_rating: int = 0
    closure_rating: int = 0


class HoldSpan(BaseModel):
    start_turn: int
    end_turn: int
    start_time: float
    end_time: float
    seconds: float
    exceeded: bool = False


class ConversationMetrics(BaseModel):
    duration_sec: float = 0.0
    agent_turns: int = 0
    customer_turns: int = 0
    agent_talk_ratio: float = 0.0       # share of speaking time, 0-1
    longest_silence_sec: float = 0.0
    dead_air_events: List[GapResult] = Field(default_factory=list)
    interruption_events: List[GapResult] = Field(default_factory=list)
    hold_events: List[GapResult] = Field(default_factory=list)       # holds longer than the 2-minute limit
    holds: List[HoldSpan] = Field(default_factory=list)              # every hold in the call
    longest_hold_sec: float = 0.0
    agent_words_per_minute: float = 0.0
    agent_interruptions: int = 0


class EmotionPoint(BaseModel):
    turn: int
    emotion: str
    valence: float


class EmotionArc(BaseModel):
    points: List[EmotionPoint] = Field(default_factory=list)
    start: str = "neutral"
    middle: str = "neutral"
    end: str = "neutral"
    trend: Literal["improved", "worsened", "flat"] = "flat"


class CoachingItem(BaseModel):
    title: str
    advice: str
    source: Literal["sop", "policy", "llm"] = "llm"
    evidence: str = ""


class AuditMeta(BaseModel):
    model: str = ""
    llm_requests: int = 0
    diarization_method: str = ""
    transcribe_seconds: float = 0.0
    audit_seconds: float = 0.0
    cache_hit: bool = False
    warnings: List[str] = Field(default_factory=list)
    source_set: str = "synthetic"   # "synthetic" | "real"
    trace_id: str = ""
    status: Literal["ok", "degraded", "handoff", "failed"] = "ok"
    failed_step: Optional[str] = None
    completed_steps: List[str] = Field(default_factory=list)
    estimated_cost_usd: Optional[float] = 0.0
    tokens_in: Optional[int] = 0
    tokens_out: Optional[int] = 0


class AuditReport(BaseModel):
    call_id: str
    generated_at: str
    topic: str
    topic_confidence: float
    signals: List[str] = Field(default_factory=list)
    summary: str = ""
    customer_issue: str = ""
    resolved: bool = False
    scores: ScoreBreakdown
    sop_results: List[SOPResult] = Field(default_factory=list)
    policy_results: List[PolicyResult] = Field(default_factory=list)
    gaps: List[GapResult] = Field(default_factory=list)
    findings: List[AuditFinding] = Field(default_factory=list)
    cannot_judge: bool = False
    cannot_judge_reason: str = ""
    unreadable_parts: List[str] = Field(default_factory=list)
    status: Literal["ok", "degraded", "handoff", "failed"] = "ok"
    failed_step: Optional[str] = None
    completed_steps: List[str] = Field(default_factory=list)
    emotion: EmotionArc = Field(default_factory=EmotionArc)          # the customer
    agent_tone: EmotionArc = Field(default_factory=EmotionArc)       # the agent
    metrics: ConversationMetrics = Field(default_factory=ConversationMetrics)
    strengths: List[str] = Field(default_factory=list)
    coaching: List[CoachingItem] = Field(default_factory=list)
    risk_flags: List[str] = Field(default_factory=list)
    retrieved_clause_ids: List[str] = Field(default_factory=list)
    transcript: CallTranscript
    meta: AuditMeta = Field(default_factory=AuditMeta)

    @property
    def observed_gaps(self) -> List[AuditFinding]:
        """Strictly observed factual breaches/gaps."""
        return [
            f for f in self.findings
            if f.kind == "observed" and f.verdict in ("missed", "partial", "violation")
        ]

    @property
    def uncertain_interpretations(self) -> List[AuditFinding]:
        """Tonal, empathetic, or inferred interpretations, or low-certainty items."""
        return [
            f for f in self.findings
            if f.kind == "inferred" or f.certainty in ("low", "medium")
        ]

    @property
    def failure_reason(self) -> str:
        return extract_failure_reason(self)


def extract_failure_reason(report: Any) -> str:
    """Extract a concise failure reason from a failed AuditReport or report dict."""
    if not report:
        return "Pipeline execution failure"
    if isinstance(report, dict):
        cannot_judge = report.get("cannot_judge_reason")
        if cannot_judge and str(cannot_judge).strip():
            return str(cannot_judge).strip()
        cap_reasons = report.get("scores", {}).get("cap_reasons", [])
        for cr in cap_reasons:
            if "failed:" in str(cr).lower():
                parts = str(cr).split("failed:", 1)
                if len(parts) == 2 and parts[1].strip():
                    return parts[1].strip()
                return str(cr)
        if cap_reasons:
            return str(cap_reasons[0])
        warnings = report.get("meta", {}).get("warnings", [])
        for w in warnings:
            if "failed" in str(w).lower():
                parts = str(w).split("failed:", 1) if "failed:" in str(w) else str(w).split("failed at", 1)
                if len(parts) == 2 and parts[1].strip():
                    return parts[1].strip()
                return str(w)
        summary = report.get("summary", "")
        if summary and "failed" in str(summary).lower():
            parts = str(summary).split("failed at", 1) if "failed at" in str(summary) else str(summary).split("failed:", 1)
            if len(parts) == 2 and parts[1].strip():
                sub = parts[1].strip()
                if ":" in sub:
                    sub = sub.split(":", 1)[1].strip()
                return sub
            return str(summary)
        failed_step = report.get("failed_step")
        if failed_step:
            return f"Step '{failed_step}' failed"
        return "Pipeline execution failure"

    if getattr(report, "cannot_judge_reason", None) and str(report.cannot_judge_reason).strip():
        return str(report.cannot_judge_reason).strip()
    if hasattr(report, "scores") and getattr(report.scores, "cap_reasons", None):
        for cr in report.scores.cap_reasons:
            if "failed:" in str(cr).lower():
                parts = str(cr).split("failed:", 1)
                if len(parts) == 2 and parts[1].strip():
                    return parts[1].strip()
                return str(cr)
        if report.scores.cap_reasons:
            return str(report.scores.cap_reasons[0])
    if hasattr(report, "meta") and getattr(report.meta, "warnings", None):
        for w in report.meta.warnings:
            if "failed" in str(w).lower():
                parts = str(w).split("failed:", 1) if "failed:" in str(w) else str(w).split("failed at", 1)
                if len(parts) == 2 and parts[1].strip():
                    return parts[1].strip()
                return str(w)
    if getattr(report, "summary", None) and "failed" in str(report.summary).lower():
        parts = str(report.summary).split("failed at", 1) if "failed at" in str(report.summary) else str(report.summary).split("failed:", 1)
        if len(parts) == 2 and parts[1].strip():
            sub = parts[1].strip()
            if ":" in sub:
                sub = sub.split(":", 1)[1].strip()
            return sub
        return str(report.summary)
    failed_step = getattr(report, "failed_step", None)
    if failed_step:
        return f"Step '{failed_step}' failed"
    return "Pipeline execution failure"


def extract_degraded_reason(report: Any) -> str:
    """Extract a concise reason for a degraded AuditReport or report dict."""
    if not report:
        return "audio/transcript quality degraded"
    if isinstance(report, dict):
        t = report.get("transcript", {})
        if isinstance(t, dict):
            qr = str(t.get("quality_reason") or "").strip()
            if qr and not qr.lower().startswith("transcript quality is reliable"):
                return qr
        if report.get("quality_reason"):
            return str(report["quality_reason"]).strip()
        if report.get("cannot_judge_reason"):
            return str(report["cannot_judge_reason"]).strip()
        warnings = report.get("meta", {}).get("warnings", [])
        if warnings:
            return str(warnings[0]).strip()
        return "audio/transcript quality degraded"

    t = getattr(report, "transcript", None)
    if t and getattr(t, "quality_reason", None):
        qr = str(t.quality_reason).strip()
        if qr and not qr.lower().startswith("transcript quality is reliable"):
            return qr
    if getattr(report, "quality_reason", None) and str(report.quality_reason).strip():
        return str(report.quality_reason).strip()
    if getattr(report, "cannot_judge_reason", None) and str(report.cannot_judge_reason).strip():
        return str(report.cannot_judge_reason).strip()
    if hasattr(report, "meta") and getattr(report.meta, "warnings", None) and report.meta.warnings:
        return str(report.meta.warnings[0]).strip()
    return "audio/transcript quality degraded"


class LiveWindowContext(BaseModel):
    """Phase 2: what the agent's screen should show for the last few turns."""
    window_turn_count: int
    detected_topic: str
    confidence: float
    signals: List[str] = Field(default_factory=list)
    clause_ids: List[str] = Field(default_factory=list)
    clauses: List[dict] = Field(default_factory=list)
