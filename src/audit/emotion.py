"""Emotion arc and conversation metrics (timing-based gaps). Deterministic; the per-turn emotion labels
themselves come from the single analysis LLM call."""

from __future__ import annotations

import re
from typing import Dict, List, Sequence

from .schemas import (CallTranscript, ConversationMetrics, DialogueTurn, EmotionArc, EmotionPoint, GapResult, HoldSpan)

VALENCE: Dict[str, float] = {
    "angry": -2.0, "frustrated": -1.5, "anxious": -1.0, "confused": -0.5, "neutral": 0.0, "satisfied": 1.0, "happy": 1.5,
}
TONE_VALENCE: Dict[str, float] = {
    "empathetic": 1.5, "warm": 1.0, "calm": 0.5, "neutral": 0.0, "rushed": -0.5, "defensive": -1.5, "dismissive": -1.5,
}
DEAD_AIR_SECONDS = 4.0
HOLD_LIMIT_SECONDS = 120.0   # SOP HLD-02 / policy ESC-2.1: never longer than 2 minutes without a check-in

_HOLD_REQUEST = re.compile(r"\bon (a )?(brief |short |quick |courtesy )?hold\b|\bhold (the|your) line\b|\bplease hold\b|\bplace you on hold\b", re.IGNORECASE)


def _after_hold_request(turns: Sequence[DialogueTurn], idx: int) -> bool:
    """True when turn idx is the agent coming back after having announced a hold in the last few turns."""
    if turns[idx].speaker != "agent":
        return False
    return any(t.speaker == "agent" and _HOLD_REQUEST.search(t.text) for t in turns[max(0, idx - 3):idx])


def compute_metrics(call: CallTranscript, dead_air_seconds: float = DEAD_AIR_SECONDS) -> ConversationMetrics:
    turns = call.turns
    m = ConversationMetrics()
    if not turns:
        return m
    m.duration_sec = round(call.duration_seconds or max(t.end_time for t in turns), 1)
    m.agent_turns = sum(1 for t in turns if t.speaker == "agent")
    m.customer_turns = sum(1 for t in turns if t.speaker == "customer")
    agent_time = sum(max(0.0, t.end_time - t.start_time) for t in turns if t.speaker == "agent")
    cust_time = sum(max(0.0, t.end_time - t.start_time) for t in turns if t.speaker == "customer")
    total = agent_time + cust_time
    m.agent_talk_ratio = round(agent_time / total, 3) if total else 0.0
    m.longest_silence_sec = round(max((t.silence_before for i, t in enumerate(turns) if not _after_hold_request(turns, i)), default=0.0), 1)
    for idx, t in enumerate(turns):
        if t.silence_before >= dead_air_seconds and _after_hold_request(turns, idx):
            # A hold is silence by design: not dead air. Only a hold beyond the 2-minute limit is a problem.
            prev = turns[idx - 1] if idx > 0 else t
            exceeded = t.silence_before > HOLD_LIMIT_SECONDS
            m.holds.append(HoldSpan(start_turn=prev.turn_id, end_turn=t.turn_id, start_time=round(prev.end_time, 2),
                                    end_time=round(t.start_time, 2), seconds=round(t.silence_before, 1), exceeded=exceeded))
            m.longest_hold_sec = max(m.longest_hold_sec, round(t.silence_before, 1))
            if exceeded:
                m.hold_events.append(GapResult(
                    gap_type="hold_too_long", turn=t.turn_id, quote="", source="timing",
                    detail=f"The customer waited about {t.silence_before:.0f}s on hold before turn {t.turn_id} (limit {HOLD_LIMIT_SECONDS:.0f}s).",
                ))
        elif t.silence_before >= dead_air_seconds:
            if t.speaker == "customer":
                m.dead_air_events.append(GapResult(
                    gap_type="dead_air", turn=t.turn_id, quote="", source="timing",
                    detail=f"{t.silence_before:.1f}s of silence before turn {t.turn_id} (customer) (informational, not penalised).",
                ))
            else:
                m.dead_air_events.append(GapResult(
                    gap_type="dead_air", turn=t.turn_id, quote="", source="timing",
                    detail=f"{t.silence_before:.1f}s of silence before turn {t.turn_id} ({t.speaker}).",
                ))
        if t.overlaps_previous:
            if t.speaker == "agent":
                m.agent_interruptions += 1
            m.interruption_events.append(GapResult(
                gap_type="interruption", turn=t.turn_id, quote=t.text[:80], source="timing",
                detail=f"The {t.speaker} started speaking while the other person was still talking (turn {t.turn_id}).",
            ))
    agent_words = sum(len(t.text.split()) for t in turns if t.speaker == "agent")
    m.agent_words_per_minute = round(agent_words / (agent_time / 60), 0) if agent_time > 0 else 0.0
    return m


def build_emotion_arc(turns: Sequence[DialogueTurn], emotions: Dict[int, str]) -> EmotionArc:
    pts: List[EmotionPoint] = []
    for t in turns:
        if t.speaker != "customer":
            continue
        e = emotions.get(t.turn_id, "neutral")
        pts.append(EmotionPoint(turn=t.turn_id, emotion=e, valence=VALENCE.get(e, 0.0)))
    arc = EmotionArc(points=pts)
    if not pts:
        return arc
    arc.start, arc.middle, arc.end = pts[0].emotion, pts[len(pts) // 2].emotion, pts[-1].emotion
    n = max(1, len(pts) // 3)
    first = sum(p.valence for p in pts[:n]) / n
    last = sum(p.valence for p in pts[-n:]) / n
    diff = last - first
    arc.trend = "improved" if diff >= 0.75 else "worsened" if diff <= -0.75 else "flat"
    return arc


def build_tone_arc(turns: Sequence[DialogueTurn], tones: Dict[int, str]) -> EmotionArc:
    """The agent's tone across the call, on the same -2..+1.5 scale as the customer's emotion."""
    pts: List[EmotionPoint] = []
    for t in turns:
        if t.speaker != "agent":
            continue
        tone = tones.get(t.turn_id, "neutral")
        pts.append(EmotionPoint(turn=t.turn_id, emotion=tone, valence=TONE_VALENCE.get(tone, 0.0)))
    arc = EmotionArc(points=pts)
    if pts:
        arc.start, arc.middle, arc.end = pts[0].emotion, pts[len(pts) // 2].emotion, pts[-1].emotion
        n = max(1, len(pts) // 3)
        diff = sum(p.valence for p in pts[-n:]) / n - sum(p.valence for p in pts[:n]) / n
        arc.trend = "improved" if diff >= 0.75 else "worsened" if diff <= -0.75 else "flat"
    return arc
