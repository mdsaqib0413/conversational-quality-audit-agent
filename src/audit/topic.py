"""Call topic + situation signals. Deterministic (no LLM request), so it is free, instant and usable
on a rolling window of a live call (Phase 2)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence, Tuple, Union

from .schemas import DialogueTurn, LiveWindowContext

TurnLike = Union[DialogueTurn, dict, Tuple[str, str]]

TOPICS = ["refund", "billing", "shipping", "warranty", "complaint", "general"]

# (regex, weight)
LEXICON: Dict[str, List[Tuple[str, float]]] = {
    "refund": [
        (r"\brefund", 3), (r"money back", 3), (r"\breturn(ed|ing|s)?\b", 2), (r"\breimburs", 2),
        (r"return (window|request|pickup|policy)", 2), (r"\bcredit(ed)? (back|to)", 1), (r"original payment", 1.5),
    ],
    "billing": [
        (r"\bbill(ed|ing)?\b", 2), (r"\bcharg(e|ed|es)\b", 2), (r"double charge", 3), (r"\bpayment\b", 1.5),
        (r"\binvoice\b", 2), (r"\bdeduct", 2), (r"\bemi\b", 2), (r"\bgst\b", 2), (r"\bcoupon\b", 1.5),
        (r"\bwallet\b", 1), (r"\bupi\b", 1), (r"\bcard\b", 1), (r"\bcod\b", 1), (r"\bstatement\b", 1),
    ],
    "shipping": [
        (r"\bdeliver", 2), (r"\bcourier\b", 2.5), (r"\bshipment\b|\bshipped\b|\bshipping\b", 2), (r"\btracking\b", 2),
        (r"\bdispatch", 2), (r"\bparcel\b|\bpackage\b", 1.5), (r"\bawb\b", 2), (r"out for delivery", 3),
        (r"\bnot received\b", 2), (r"\blogistics\b", 2), (r"\botp\b", 1.5), (r"\bdelay(ed)?\b", 1.5),
        (r"change (the |my )?(delivery )?address", 2),
    ],
    "warranty": [
        (r"\bwarranty\b", 3.5), (r"\brepair", 2.5), (r"\bdefect", 2.5), (r"service cent(er|re)", 2.5),
        (r"stopped working", 2.5), (r"\bmalfunction", 2.5), (r"\breplacement\b", 1.5), (r"\bdamaged\b", 1),
        (r"\bnot working\b", 2), (r"\bfaulty\b", 2),
    ],
}

ANGER = [
    r"unacceptable", r"ridiculous", r"fed up", r"\bworst\b", r"terrible", r"third time",
    r"again and again", r"waste of", r"\bfrustrat", r"\bangry\b", r"disgust", r"\bpathetic", r"\bcheat",
    r"\bfraud", r"\bsick of\b", r"how many times", r"no one (is )?(helping|listening)", r"\bridiculous",
    r"consumer court", r"legal action", r"social media", r"\bnonsense\b", r"useless",
]
COMPLAINT_WORDS = [r"\bcomplain", r"formal complaint", r"\bgrievance"]   # a complaint topic, but not by itself an angry caller
SUPERVISOR = [r"\bsupervisor\b", r"\bmanager\b", r"senior", r"higher authority", r"escalat"]
HOLD = [r"\bon (a )?(brief |short |quick )?hold\b", r"\bhold (the|your) line\b", r"\bplease hold\b", r"\bhold on\b",
        r"\bstay on the line\b", r"\bone moment\b", r"back on the line", r"\bfor (holding|waiting)\b", r"\bholding\b"]
TRANSFER = [r"transfer(ring|red)? (you|your call|this call|the call)", r"transfer (you )?to (a |an |our |the )?(supervisor|manager|specialist|team|department|senior)",
            r"connect you (to|with)", r"warm transfer", r"\bhand(ing)? (you|this) over"]
CALLBACK = [r"call(ing)? you back", r"\bcall ?back\b", r"\bcallback\b", r"return your call", r"get back to you (by|within|in)"]


def _compile(patterns):
    return [re.compile(p, re.IGNORECASE) for p in patterns]


_ANGER, _SUP, _HOLD, _TRANSFER, _CALLBACK, _COMPLAINT = map(_compile, (ANGER, SUPERVISOR, HOLD, TRANSFER, CALLBACK, COMPLAINT_WORDS))
_LEX = {t: [(re.compile(p, re.IGNORECASE), w) for p, w in items] for t, items in LEXICON.items()}


@dataclass
class TopicResult:
    topic: str
    confidence: float
    scores: Dict[str, float] = field(default_factory=dict)
    signals: List[str] = field(default_factory=list)


def _norm_turns(turns: Iterable[TurnLike]) -> List[Tuple[str, str]]:
    out: List[Tuple[str, str]] = []
    for t in turns:
        if isinstance(t, DialogueTurn):
            out.append((t.speaker, t.text))
        elif isinstance(t, dict):
            out.append((str(t.get("speaker", "")), str(t.get("text", ""))))
        else:
            out.append((str(t[0]), str(t[1])))
    return out


def _count(patterns, text: str) -> int:
    return sum(1 for p in patterns if p.search(text))


def detect_signals(turns: Sequence[TurnLike]) -> List[str]:
    tt = _norm_turns(turns)
    cust = [x for s, x in tt if s == "customer"]
    agent = [x for s, x in tt if s == "agent"]
    signals: List[str] = []
    anger_turns = sum(1 for x in cust if _count(_ANGER, x) > 0)
    anger_hits = sum(_count(_ANGER, x) for x in cust) + sum(x.count("!") > 1 for x in cust)
    if anger_turns >= 1 or anger_hits >= 1:
        signals.append("angry_customer")
    if sum(1 for x in cust if _count(_SUP, x)) >= 1:
        signals.append("supervisor_request")
    if sum(1 for x in agent if _count(_HOLD, x)) >= 1:
        signals.append("hold")
    if sum(1 for x in agent if _count(_TRANSFER, x)) >= 1:
        signals.append("transfer")
    if sum(1 for x in agent if _count(_CALLBACK, x)) >= 1:
        signals.append("callback")
    return signals


def detect_topic(turns: Sequence[TurnLike]) -> TopicResult:
    tt = _norm_turns(turns)
    scores = {t: 0.0 for t in TOPICS}
    for idx, (speaker, text) in enumerate(tt):
        w_speaker = 1.5 if speaker == "customer" else 1.0
        w_pos = 1.4 if idx < 6 else 1.0
        for topic, items in _LEX.items():
            hit = sum(w for rx, w in items if rx.search(text))
            scores[topic] += hit * w_speaker * w_pos
        if speaker == "customer":
            scores["complaint"] += 1.5 * _count(_ANGER, text) + 1.0 * _count(_COMPLAINT, text)
    signals = detect_signals(tt)
    if "angry_customer" in signals:
        scores["complaint"] += 2.0
    ranked = sorted(((s, t) for t, s in scores.items() if t != "general"), reverse=True)
    best_score, best = ranked[0]
    second = ranked[1][0] if len(ranked) > 1 else 0.0
    if best_score < 2.0:
        topic, conf = "general", 0.5
    else:
        topic, conf = best, round(best_score / (best_score + second + 1.0), 3)
    scores["general"] = 1.0
    return TopicResult(topic=topic, confidence=conf, scores={k: round(v, 2) for k, v in scores.items()}, signals=signals)


# --------------------------------------------------------------------------------------
# Which SOP steps are candidates for this call
# --------------------------------------------------------------------------------------
def candidate_step_families(topic: str, signals: Sequence[str]) -> List[str]:
    fams = ["GEN"]
    if topic == "refund":
        fams.append("REF-S")
    if topic == "complaint" or "angry_customer" in signals:
        fams.append("ANG")
    if any(s in signals for s in ("hold", "transfer", "callback")):
        fams.append("HLD")
    return fams


def candidate_step_ids(kb, topic: str, signals: Sequence[str]) -> List[str]:
    ids = [s.id for s in kb.sop_steps(candidate_step_families(topic, signals))]
    keep = []
    for sid in ids:
        if sid.startswith("HLD"):
            n = int(sid.split("-")[1])
            if n <= 3 and "hold" not in signals and "transfer" not in signals:
                continue
            if n == 4 and "transfer" not in signals:
                continue
            if n == 5 and "callback" not in signals:
                continue
        keep.append(sid)
    return keep


# --------------------------------------------------------------------------------------
# Phase 2: rolling-window context for a live call
# --------------------------------------------------------------------------------------
def get_live_context(turns: Sequence[TurnLike], window: int = 6, kb=None, k: int = 6) -> LiveWindowContext:
    from .rag import get_kb

    kb = kb or get_kb()
    tt = _norm_turns(turns)[-window:]
    res = detect_topic(tt)
    query = " ".join(x for _, x in tt)
    clauses = kb.retrieve_policies(query, topic=res.topic, k=k)
    return LiveWindowContext(
        window_turn_count=len(tt),
        detected_topic=res.topic,
        confidence=res.confidence,
        signals=res.signals,
        clause_ids=[c.id for c in clauses],
        clauses=[{"id": c.id, "title": c.title, "text": c.short(500)} for c in clauses],
    )



def detect_call_situations(turns: Sequence[TurnLike]) -> List[str]:
    """Detect policy situation tags from conversation signals and text cues.

    Cues:
    - signals from detect_signals(): angry_customer, supervisor_request, hold, transfer, callback
    - customer asks for supervisor: supervisor_request
    - agent gives account/order details or requests auth: identity_verification, data_disclosure
    - OTP mentioned: otp_request
    - refund amount mentioned (e.g. >= Rs 5,000 threshold or authority limit): high_value_refund
    """
    tt = _norm_turns(turns)
    signals = set(detect_signals(turns))
    full_text = " ".join(text for _, text in tt)
    cust_text = " ".join(text for speaker, text in tt if speaker == "customer")
    agent_text = " ".join(text for speaker, text in tt if speaker == "agent")

    situations = set(signals)

    # 1. Customer asks for supervisor
    if re.search(r"\b(supervisor|manager|senior|escalat)", cust_text, re.I):
        situations.add("supervisor_request")

    # 2. Agent gives account details / asks for verification
    if re.search(r"\b(delivered to|shipped to|flat \d|residency|card ending|order (?:is|was) for|bank account|paytm wallet)\b", agent_text, re.I) or \
       re.search(r"\b(order id|last (?:four|4) digits|registered (?:phone|mobile|number)|verif(?:y|ication))\b", full_text, re.I):
        situations.add("identity_verification")
        situations.add("data_disclosure")

    # 3. OTP mentioned
    if re.search(r"\b(otp|one[- ]time password|verification code)\b", full_text, re.I):
        situations.add("otp_request")

    # 4. Refund amount mentioned / high value refund
    amt_match = re.findall(r"(?:rs\.?|inr|rupees)\s*([0-9,]+)", full_text, re.I)
    has_high = False
    for a in amt_match:
        try:
            if float(a.replace(",", "")) >= 5000:
                has_high = True
                break
        except ValueError:
            pass
    if has_high or re.search(r"\b(full authority|approval limit|supervisor is needed|exceeding)\b", agent_text, re.I):
        situations.add("high_value_refund")

    return sorted(situations)
