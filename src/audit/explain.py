"""Plain-language layer: turns the audit's numbers into sentences a team lead or a new agent understands.

Nothing here changes a score. It only explains, labels and groups what the audit already measured.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from .schemas import AuditReport

# ---------------------------------------------------------------------------------- vocabulary
STATUS_LABEL = {"followed": "Done", "partial": "Partly done", "missed": "Missed", "not_applicable": "Did not apply"}
STATUS_HELP = {
    "followed": "The agent did everything this step asks for.",
    "partial": "The agent did part of it but left something out.",
    "missed": "The agent did not do this when they should have.",
    "not_applicable": "The situation never came up in this call, so it is not scored.",
}
SEVERITY_LABEL = {"minor": "Small slip", "major": "Serious", "critical": "Critical", "none": "None"}
SEVERITY_HELP = {
    "minor": "A wrong detail such as a timeline or a count. Costs 3 points.",
    "major": "A wrong promise or decision about money or eligibility. Costs 8 points.",
    "critical": "A security or authority breach. Costs 15 points.",
}
GAP_INFO: Dict[str, Tuple[str, str]] = {
    "dead_air": ("Long silence", "A silence of 4 seconds or more with nobody speaking and no hold announced."),
    "interruption": ("Talked over someone", "One person started speaking while the other was still talking."),
    "hold_too_long": ("Hold over 2 minutes", "The customer waited more than the 2-minute limit without a check-in."),
    "no_empathy": ("No empathy shown", "The customer described a difficulty and the agent did not acknowledge it."),
    "unresolved_issue": ("Problem not solved", "The call ended without the customer's problem being resolved."),
    "customer_repeating": ("Customer had to repeat themselves", "The customer had to say the same thing more than once."),
    "no_summary": ("No recap at the end", "The agent did not summarise what was agreed."),
    "no_closing": ("No proper closing", "The call ended without a courteous sign-off."),
    "other": ("Other issue", "Something else the reviewer flagged."),
}
CATEGORIES = [
    ("sop_score", "Call script", 40, "SOP adherence", "Did the agent follow the steps expected on every call?",
     "Did the agent follow the steps the company expects on every call (greeting, verifying the caller, explaining, summarising)? "
     "Each step has a weight; points = weight × (done 1, partly done 0.5, missed 0)."),
    ("policy_score", "Company rules", 30, "Policy compliance", "Did the agent say things that match company policy?",
     "Did the agent say things that match company policy (refund windows, limits, timelines)? Starts at 30 and loses points for every wrong statement."),
    ("empathy_score", "Empathy", 15, "Empathy", "Did the agent acknowledge how the customer felt?",
     "Did the agent acknowledge how the customer felt? The reviewer gives 0 to 5, scaled to 15 points."),
    ("communication_score", "Communication", 15, "Communication", "Was the agent clear, professional and well organised?",
     "Clarity, professionalism, ownership and closure (each 0 to 5, averaged and scaled to 15), minus small deductions for long silences and talking over the customer."),
]
EMOTION_WORDS = {"angry": "angry", "frustrated": "frustrated", "anxious": "worried", "confused": "confused", "neutral": "calm",
                 "satisfied": "satisfied", "happy": "happy"}
TONE_WORDS = {"empathetic": "empathetic", "warm": "warm", "calm": "calm", "neutral": "neutral", "rushed": "rushed", "defensive": "defensive", "dismissive": "dismissive"}
EMOTION_CLASS = {"angry": "negative", "frustrated": "negative", "anxious": "negative", "confused": "neutral", "neutral": "neutral",
                 "satisfied": "positive", "happy": "positive"}
TOPIC_LABEL = {"refund": "Refund or return", "billing": "Billing and payments", "shipping": "Shipping and delivery", "warranty": "Warranty and repair",
               "complaint": "Complaint", "general": "General enquiry"}
GRADE_HEADLINE = {"A": "Excellent call", "B": "Good call", "C": "Needs improvement", "D": "Failing call"}


def topic_label(topic: str) -> str:
    return TOPIC_LABEL.get(topic, topic.title())


# ---------------------------------------------------------------------------------- verdict
def _short(text: str, n: int = 150) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= n else text[: n - 1].rstrip() + "…"


def verdict(rep: AuditReport) -> dict:
    sc = rep.scores
    crit_missed = [r for r in rep.sop_results if r.critical and r.status == "missed"]
    violations = [p for p in rep.policy_results if p.verdict == "violation"]
    capped = (bool(sc.cap_reasons) and sc.overall < sc.overall_before_cap) or getattr(sc, "critical_failure", False)
    tone = "good" if sc.grade == "A" else "ok" if sc.grade == "B" else "warn" if sc.grade == "C" else "bad"
    headline = GRADE_HEADLINE.get(sc.grade, sc.grade_label)
    if sc.critical_failure or capped:
        headline = "Critical rule broken" if (sc.critical_failure or sc.overall < 70) else "Score capped"
        tone = "bad" if sc.overall < 70 else "warn"
    sub = {"A": "Everything that mattered was done well.",
           "B": "Solid call. A few things could be polished.",
           "C": "The call solved some things but important parts were missing.",
           "D": "The call fell well below the standard."}.get(sc.grade, "")
    if sc.critical_failure or capped:
        sub = "A step or rule the company treats as non-negotiable was not followed, so the score is held back."

    reasons: List[Tuple[str, str]] = []
    for r in sorted(crit_missed, key=lambda r: -r.weight)[:3]:
        reasons.append(("bad", f"Critical step missed: {r.title} ({r.step_id})."))
    for p in sorted(violations, key=lambda p: {"critical": 0, "major": 1, "minor": 2}.get(p.severity, 3))[:3]:
        reasons.append(("bad" if p.severity == "critical" else "warn", f"Broke a company rule ({SEVERITY_LABEL[p.severity].lower()}): {_short(p.explanation, 140)}"))
    for g in rep.metrics.hold_events[:1]:
        reasons.append(("bad", "The customer was left on hold for more than 2 minutes."))
    if rep.metrics.dead_air_events:
        reasons.append(("warn", f"{len(rep.metrics.dead_air_events)} long silence(s) with nobody speaking."))
    if rep.metrics.agent_interruptions:
        reasons.append(("warn", f"The agent talked over the customer {rep.metrics.agent_interruptions} time(s)."))
    partial_or_missed = [r for r in rep.sop_results if r.status in ("missed", "partial") and not r.critical]
    if partial_or_missed and len(reasons) < 5:
        reasons.append(("warn", f"{len(partial_or_missed)} other script step(s) were missed or only partly done."))
    if rep.emotion.trend == "worsened" or (rep.emotion.points and rep.emotion.end in ("angry", "frustrated")):
        reasons.append(("warn", f"The customer ended the call {EMOTION_WORDS.get(rep.emotion.end, rep.emotion.end)}."))
    if not reasons:
        reasons.append(("good", "No rule was broken and no required step was missed."))
        if rep.emotion.trend == "improved":
            reasons.append(("good", f"The customer's mood improved from {EMOTION_WORDS.get(rep.emotion.start, rep.emotion.start)} to {EMOTION_WORDS.get(rep.emotion.end, rep.emotion.end)}."))
    nxt = rep.coaching[0] if rep.coaching else None
    return {"tone": tone, "headline": headline, "sub": sub, "reasons": reasons[:6], "capped": capped,
            "next_step": (f"{nxt.title}: {_short(nxt.advice, 200)}" if nxt else "Keep doing what you are doing.")}


# ---------------------------------------------------------------------------------- score walkthrough
def score_walkthrough(rep: AuditReport) -> List[dict]:
    sc = rep.scores
    rows: List[dict] = []
    done = sum(1 for r in rep.sop_results if r.status == "followed")
    part = sum(1 for r in rep.sop_results if r.status == "partial")
    miss = sum(1 for r in rep.sop_results if r.status == "missed")
    na = sum(1 for r in rep.sop_results if r.status == "not_applicable")
    rows.append({
        "title": "Call script", "points": sc.sop_score, "max": 40,
        "formula": f"{sc.sop_points_earned:g} of {sc.sop_points_possible:g} step points × 40 = {sc.sop_score:g}" if sc.sop_points_possible else "No steps could be scored",
        "plain": f"{done} step(s) done, {part} partly done, {miss} missed; {na} did not apply and are not counted. "
                 "A step's points equal its weight (1 to 5): done = full, partly done = half, missed = none.",
    })
    viol = [p for p in rep.policy_results if p.verdict == "violation"]
    pen = " + ".join(f"{p.penalty:g}" for p in viol) or "0"
    rows.append({
        "title": "Company rules", "points": sc.policy_score, "max": 30,
        "formula": f"30 − ({pen}) = {sc.policy_score:g}",
        "plain": ("No rule was broken, so nothing is taken off." if not viol else
                  f"{len(viol)} wrong statement(s): each small slip costs 3 points, a serious one 8, a critical one 15 (a mistake repeated later counts once)."),
    })
    emp = sc.empathy_rating
    rows.append({"title": "Empathy", "points": sc.empathy_score, "max": 15,
                 "formula": f"{emp} out of 5 × 3 = {sc.empathy_score:g}",
                 "plain": "How well the agent acknowledged the customer's situation: 0 = ignored it, 3 = named the specific problem, 5 = named it, showed they understood the impact and took ownership."})
    avg = (sc.clarity_rating + sc.professionalism_rating + sc.ownership_rating + sc.closure_rating) / 4
    base = round(avg / 5 * 15, 1)
    adj = f" − {sc.timing_penalty:g} for {'; '.join(sc.timing_notes)}" if sc.timing_penalty else ""
    rows.append({"title": "Communication", "points": sc.communication_score, "max": 15,
                 "formula": f"average of clarity {sc.clarity_rating}, professionalism {sc.professionalism_rating}, ownership {sc.ownership_rating}, closure {sc.closure_rating} = {avg:.1f} out of 5 → {base:g}{adj} = {sc.communication_score:g}",
                 "plain": "Clear explanations, courteous tone, taking responsibility and a proper wrap-up. Long silences and talking over the customer take off small amounts."})
    total = {"title": "Total", "points": sc.overall_before_cap, "max": 100,
             "formula": f"{sc.sop_score:g} + {sc.policy_score:g} + {sc.empathy_score:g} + {sc.communication_score:g} = {sc.overall_before_cap:g}",
             "plain": "The four parts add up to the score."}
    rows.append(total)
    if sc.overall != sc.overall_before_cap:
        rows.append({"title": "Critical-failure cap", "points": sc.overall, "max": 100,
                     "formula": f"capped at 70, so {sc.overall_before_cap:g} becomes {sc.overall:g}",
                     "plain": "; ".join(sc.cap_reasons) + ". A critical failure can never score above 70, however well the rest went."})
    elif sc.cap_reasons:
        rows.append({"title": "Critical-failure flag", "points": sc.overall, "max": 100, "formula": "; ".join(sc.cap_reasons),
                     "plain": "A critical problem was found; the score was already below the 70 cap."})
    return rows


# ---------------------------------------------------------------------------------- metrics
def metric_cards(rep: AuditReport) -> List[dict]:
    m = rep.metrics
    cards: List[dict] = []
    cards.append({"label": "Call length", "value": f"{m.duration_sec / 60:.1f}", "unit": "min", "state": "info",
                  "hint": "Total time from the first word to the last.", "range": ""})
    share = m.agent_talk_ratio
    st = "good" if 0.40 <= share <= 0.65 else ("watch" if 0.30 <= share <= 0.75 else "bad")
    cards.append({"label": "Agent talk share", "value": f"{share * 100:.0f}", "unit": "%", "state": st,
                  "hint": "Share of the speaking time used by the agent. Very high can mean the customer was not given room to speak.",
                  "range": "Balanced calls are usually 40 to 65% (rule of thumb)."})
    ls = m.longest_silence_sec
    cards.append({"label": "Longest silence", "value": f"{ls:.0f}", "unit": "s", "state": "good" if ls < 4 else "bad",
                  "hint": "The longest stretch where nobody spoke (holds are counted separately).", "range": "4 seconds or more counts as a long silence."})
    wpm = m.agent_words_per_minute
    st = "info" if not wpm else ("good" if 110 <= wpm <= 170 else "watch")
    cards.append({"label": "Agent speaking pace", "value": f"{wpm:.0f}", "unit": "words/min", "state": st,
                  "hint": "How fast the agent speaks. Too fast is hard to follow, too slow can sound disengaged.",
                  "range": "Typical conversation is about 120 to 160 words per minute."})
    ai = m.agent_interruptions
    cards.append({"label": "Agent talked over customer", "value": str(ai), "unit": "time(s)", "state": "good" if ai == 0 else "bad",
                  "hint": "How often the agent started speaking while the customer was still talking.", "range": "Aim for zero."})
    if m.holds:
        lh = m.longest_hold_sec
        cards.append({"label": "Longest hold", "value": f"{int(lh) // 60}:{int(lh) % 60:02d}", "unit": "min:sec", "state": "good" if lh <= 120 else "bad",
                      "hint": "How long the customer waited on hold.", "range": "Company limit is 2 minutes without a check-in."})
    else:
        cards.append({"label": "Hold", "value": "None", "unit": "", "state": "info", "hint": "The customer was not put on hold.", "range": ""})
    cards.append({"label": "Turns", "value": f"{m.agent_turns} / {m.customer_turns}", "unit": "agent / customer", "state": "info",
                  "hint": "How many times each person spoke.", "range": ""})
    return cards


# ---------------------------------------------------------------------------------- emotion summary
def emotion_summary(rep: AuditReport) -> Tuple[str, str]:
    e, a = rep.emotion, rep.agent_tone
    if e.points:
        s, en = EMOTION_WORDS.get(e.start, e.start), EMOTION_WORDS.get(e.end, e.end)
        trend = {"improved": "Their mood improved during the call.", "worsened": "Their mood got worse during the call.", "flat": "Their mood stayed about the same."}[e.trend]
        cust = f"The customer started {s} and ended {en}. {trend}"
    else:
        cust = "No customer emotion was recorded."
    if a.points:
        counts: Dict[str, int] = {}
        for p in a.points:
            counts[p.emotion] = counts.get(p.emotion, 0) + 1
        top = max(counts, key=counts.get)
        neg = sum(c for k, c in counts.items() if k in ("defensive", "dismissive", "rushed"))
        pos = sum(c for k, c in counts.items() if k in ("empathetic", "warm"))
        agent = (f"The agent mostly sounded {TONE_WORDS.get(top, top)}. "
                 + (f"{neg} of {len(a.points)} turns came across as rushed, defensive or dismissive." if neg else "")
                 + (f" {pos} turn(s) were warm or empathetic." if pos else "")).strip()
    else:
        agent = "No agent tone was recorded."
    return cust, agent


# ---------------------------------------------------------------------------------- helpers used by the UI
def step_columns(rep: AuditReport) -> Dict[str, list]:
    cols = {"missed": [], "partial": [], "followed": [], "not_applicable": []}
    for r in rep.sop_results:
        cols[r.status].append(r)
    for k in cols:
        cols[k].sort(key=lambda r: (not r.critical, -r.weight, r.step_id))
    return cols


def gap_title(gap_type: str) -> str:
    return GAP_INFO.get(gap_type, (gap_type.replace("_", " ").title(), ""))[0]


def gap_help(gap_type: str) -> str:
    return GAP_INFO.get(gap_type, ("", ""))[1]
