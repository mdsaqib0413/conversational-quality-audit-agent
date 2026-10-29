"""Schemas for Live Assist streaming and UI snapshots."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class LiveTurn:
    speaker: str  # "agent" | "customer"
    start: float  # seconds from start
    end: float    # seconds from start
    text: str
    partial: bool = False
    turn_id: int = 1


@dataclass
class LiveAlert:
    rule_id: str
    name: str
    clause_id: str
    severity: str  # "danger" | "warning" | "info"
    message: str
    key_numbers: str
    time_sec: float
    offending_quote: str = ""
    turn_id: Optional[int] = None


@dataclass
class SopStepProgress:
    step_id: str
    name: str
    critical: bool = False
    status: str = "not_yet"  # "done" | "partial" | "not_yet"
    matched_quote: str = ""


@dataclass
class LiveClause:
    id: str
    title: str
    text: str
    key_numbers: str = ""
    tag: str = ""
    alert_time: str = ""


@dataclass
class LiveSnapshot:
    call_id: str = ""
    status: str = "stopped"  # "running" | "ended" | "stopped" | "idle"
    duration_sec: float = 0.0
    turns: List[LiveTurn] = field(default_factory=list)
    detected_topic: str = "general"
    topic_confidence: float = 0.0
    signals: List[str] = field(default_factory=list)
    top_clauses: List[LiveClause] = field(default_factory=list)
    sop_checklist: List[SopStepProgress] = field(default_factory=list)
    next_step: Optional[SopStepProgress] = None
    alerts: List[LiveAlert] = field(default_factory=list)
    agent_talk_share: float = 0.0
    customer_talk_share: float = 0.0
    customer_mood: str = "Neutral"  # "Calm" | "Neutral" | "Frustrated" | "Angry"
    customer_mood_score: float = 0.0  # -1.0 to 1.0
    last_silence_sec: float = 0.0
    latency_ms: float = 0.0
    ai_requests_used: int = 0
    stereo_exact: bool = True
    end_suggested: bool = False
