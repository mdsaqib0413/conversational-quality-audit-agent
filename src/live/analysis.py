"""Fast local analysis for rolling window and cumulative tracking in Live Assist.

Pure Python, deterministic, uses BM25 retrieval without forcing embedding models.
"""

from __future__ import annotations

import html
import re
from typing import Dict, List, Optional, Tuple

from src.audit.rag import get_kb
from src.audit.topic import TOPICS, _ANGER, _COMPLAINT, _LEX, _count, detect_signals

from .rules import LiveRuleEngine
from .schemas import LiveAlert, LiveClause, LiveSnapshot, LiveTurn, SopStepProgress

_TOPIC_FAMILY_MAP = {
    "refund": ["REF", "PRV", "ESC"],
    "billing": ["BIL", "PRV", "ESC"],
    "shipping": ["SHP", "PRV", "ESC"],
    "warranty": ["WAR", "PRV", "ESC"],
    "complaint": ["ESC", "PRV"],
    "general": ["GEN", "PRV", "ESC"],
}

_TOPIC_KEYWORDS = {
    "refund": "refund return money back replacement",
    "billing": "billing charge payment invoice debit",
    "shipping": "shipping delivery courier tracking transit",
    "warranty": "warranty repair defect service center",
    "complaint": "complaint supervisor escalation grievance",
    "general": "customer support assistance order verification",
}


def _format_clause_snippet(raw_text: str, cid: str, title: str, limit: int = 240) -> str:
    """Remove repeated ID Title prefix, escape HTML, and render **x** as <b>x</b>."""
    lines = [l.strip() for l in raw_text.split("\n") if l.strip()]
    if lines:
        first = lines[0]
        clean_first = re.sub(r"^[#\s\[\]\-]+", "", first)
        if clean_first.startswith(cid) or title.lower() in first.lower() or first.startswith("#"):
            lines = lines[1:]
    body = " ".join(lines)
    body = re.sub(r"^[0-9\.\-\s]+", "", body).strip()
    if len(body) > limit:
        body = body[: limit - 3].rstrip() + "..."
    escaped = html.escape(body)
    return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", escaped)


def compute_cumulative_topic(
    turns: List[LiveTurn],
    alerts: Optional[List[LiveAlert]] = None,
    prev_topic: str = "general",
    hysteresis_margin: float = 2.0,
) -> Tuple[str, float, List[str], Dict[str, float]]:
    """Compute call-level topic from cumulative evidence over whole transcript so far.

    Customer turns in first 60s weigh double. Later evidence decays.
    Hysteresis prevents flickering. Fired alerts add votes.
    """
    scores = {t: 0.0 for t in TOPICS}
    turn_tuples = [(t.speaker, t.text) for t in turns]

    for idx, t in enumerate(turns):
        spk = t.speaker
        txt = t.text
        start_t = t.start

        w_speaker = 1.5 if spk == "customer" else 1.0
        # Customer turns in first 60s (or initial turns) weigh double
        if spk == "customer" and (start_t <= 60.0 or idx <= 3):
            w_speaker *= 2.0
        elif start_t > 60.0:
            w_speaker *= max(0.4, 1.0 - (start_t - 60.0) * 0.003)

        for topic, items in _LEX.items():
            hit = sum(w for rx, w in items if rx.search(txt))
            scores[topic] += hit * w_speaker

        if spk == "customer":
            scores["complaint"] += (1.5 * _count(_ANGER, txt) + 1.0 * _count(_COMPLAINT, txt)) * w_speaker

    # Fired alerts add votes
    if alerts:
        for a in alerts:
            cid = a.clause_id
            if cid.startswith("REF-"):
                scores["refund"] += 3.0
            elif cid.startswith("WAR-"):
                scores["warranty"] += 3.0
            elif cid.startswith("BIL-"):
                scores["billing"] += 3.0
            elif cid.startswith("SHP-"):
                scores["shipping"] += 3.0
            elif cid.startswith("ESC-"):
                scores["complaint"] += 2.0

    signals = detect_signals(turn_tuples) if turn_tuples else []
    if "angry_customer" in signals:
        scores["complaint"] += 2.0

    ranked = sorted(((s, t) for t, s in scores.items() if t != "general"), reverse=True)
    best_score, best_topic = ranked[0]
    second_score = ranked[1][0] if len(ranked) > 1 else 0.0

    if best_score < 1.2:
        topic = "general"
        conf = 0.50
    else:
        if prev_topic == "general":
            topic = best_topic
        else:
            curr_score = scores.get(prev_topic, 0.0)
            if best_topic != prev_topic and best_score > (curr_score + hysteresis_margin):
                topic = best_topic
            else:
                topic = prev_topic

        margin = best_score - second_score
        conf = round(min(0.98, max(0.50, 0.50 + margin / (best_score + 2.0))), 2)

    return topic, conf, signals, scores


def run_live_analysis(
    turns: List[LiveTurn],
    duration_sec: float,
    last_silence_sec: float,
    rule_engine: LiveRuleEngine,
    accumulated_alerts: List[LiveAlert],
    kb=None,
    stereo_exact: bool = True,
    status: str = "running",
    call_id: str = "",
) -> LiveSnapshot:
    kb = kb or get_kb()

    # 1. Talk share computation
    agent_speech_time = sum(max(0.0, t.end - t.start) for t in turns if t.speaker == "agent")
    cust_speech_time = sum(max(0.0, t.end - t.start) for t in turns if t.speaker == "customer")
    total_speech = agent_speech_time + cust_speech_time

    agent_share = agent_speech_time / total_speech if total_speech > 0 else 0.5
    cust_share = cust_speech_time / total_speech if total_speech > 0 else 0.5

    # 2. Cumulative topic detection across whole transcript
    topic, confidence, signals, _scores = compute_cumulative_topic(
        turns=turns,
        alerts=accumulated_alerts,
        prev_topic="general",
    )

    # 3. Evaluate alerts
    new_alerts = rule_engine.evaluate_alerts(turns, duration_sec, agent_share, last_silence_sec)
    for a in new_alerts:
        if not any(x.rule_id == a.rule_id for x in accumulated_alerts):
            accumulated_alerts.append(a)

    # Re-compute topic with any newly fired alerts
    if new_alerts:
        topic, confidence, signals, _scores = compute_cumulative_topic(
            turns=turns,
            alerts=accumulated_alerts,
            prev_topic=topic,
        )

    # 4. Policies panel:
    # Pin clauses cited by fired alerts at the top with a "Triggered" tag and alert time
    top_clauses: List[LiveClause] = []
    seen_clause_ids = set()

    for a in accumulated_alerts:
        cid = a.clause_id
        if cid in seen_clause_ids:
            continue
        seen_clause_ids.add(cid)
        cl = kb.by_id.get(cid)
        if cl:
            t_mm = int(a.time_sec // 60)
            t_ss = int(a.time_sec % 60)
            top_clauses.append(
                LiveClause(
                    id=cl.id,
                    title=cl.title,
                    text=_format_clause_snippet(cl.text, cl.id, cl.title),
                    key_numbers=a.key_numbers,
                    tag="Triggered",
                    alert_time=f"{t_mm}:{t_ss:02d}",
                )
            )

    # Fill the rest from the stable topic's policy families (+ PRV and ESC), max 5 cards
    allowed_prefixes = tuple(_TOPIC_FAMILY_MAP.get(topic, ["GEN", "PRV", "ESC"]))
    last_3_turns_text = " ".join(t.text for t in turns[-3:]) if turns else ""
    topic_kw = _TOPIC_KEYWORDS.get(topic, "")
    query = f"{last_3_turns_text} {topic_kw}".strip()
    if not query:
        query = "customer service general procedure"

    retrieved = kb.retrieve_policies(query, topic=topic if topic != "general" else None, k=8, use_embeddings=False)
    for c in retrieved:
        if len(top_clauses) >= 5:
            break
        if c.id in seen_clause_ids:
            continue
        if not c.id.startswith(allowed_prefixes):
            continue
        seen_clause_ids.add(c.id)
        top_clauses.append(
            LiveClause(
                id=c.id,
                title=c.title,
                text=_format_clause_snippet(c.text, c.id, c.title),
                key_numbers="",
                tag="",
                alert_time="",
            )
        )

    # If still fewer than 5, fill from remaining allowed policies
    if len(top_clauses) < 5:
        for c in retrieved:
            if len(top_clauses) >= 5:
                break
            if c.id in seen_clause_ids:
                continue
            seen_clause_ids.add(c.id)
            top_clauses.append(
                LiveClause(
                    id=c.id,
                    title=c.title,
                    text=_format_clause_snippet(c.text, c.id, c.title),
                    key_numbers="",
                    tag="",
                    alert_time="",
                )
            )

    # 5. SOP progress evaluation
    checklist, next_step = rule_engine.evaluate_sop_progress(topic, turns)

    # Next prescribed action when call is ended
    if status == "ended":
        missed = [s.step_id for s in checklist if s.status != "done"]
        if missed:
            next_action_text = f"Call complete: missed steps {', '.join(missed)}"
        else:
            next_action_text = "Call complete: all steps followed"
        next_step = SopStepProgress(
            step_id="DONE",
            name=next_action_text,
            critical=False,
            status="done",
        )

    # 6. Customer mood
    mood_label, mood_score = rule_engine.evaluate_customer_mood(turns)

    return LiveSnapshot(
        call_id=call_id,
        status=status,
        duration_sec=duration_sec,
        turns=list(turns),
        detected_topic=topic,
        topic_confidence=confidence,
        signals=signals,
        top_clauses=top_clauses,
        sop_checklist=checklist,
        next_step=next_step,
        alerts=list(accumulated_alerts),
        agent_talk_share=agent_share,
        customer_talk_share=cust_share,
        customer_mood=mood_label,
        customer_mood_score=mood_score,
        last_silence_sec=last_silence_sec,
        ai_requests_used=0,
        stereo_exact=stereo_exact,
    )
