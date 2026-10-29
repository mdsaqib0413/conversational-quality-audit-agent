"""SOP adherence + conversation quality: ONE LLM request judging every candidate SOP step, rating
empathy/communication, labelling customer emotions and listing gaps.

All evidence is verified against the transcript afterwards; claims without verifiable evidence are
downgraded instead of trusted.
"""

from __future__ import annotations

import logging
import re
from typing import Dict, List, Optional, Sequence, Tuple

from .call_state import EarlyCallState, compute_call_state
from .evidence import locate_quote
from .prompts import _load_agent, format_transcript
from .rag import KnowledgeBase
from .schemas import CallTranscript, ConversationAnalysis, SOPResult

logger = logging.getLogger(__name__)

SYSTEM = _load_agent("compliance_agent.md")

SCORE_GUIDE = """SCORING GUIDE (integers 0-5)
empathy_score: 0 = dismissive or none; 1 = scripted/token apology at the wrong moment; 2 = generic apology only; 3 = acknowledges the customer's specific problem; 4 = acknowledges the specific problem and reassures; 5 = acknowledges the problem AND its impact on the customer, takes ownership, tone adapts to the customer's emotion.
clarity_score: 0 = confusing or contradictory; 3 = understandable but vague on details; 5 = precise, explains next steps and timelines plainly.
professionalism_score: 0 = rude/unprofessional; 3 = polite but some slips (filler, informal); 5 = consistently courteous, uses the customer's name, proper greeting and closing.
ownership_score: 0 = deflects or passes the customer around; 3 = handles the request but leaves follow-up unclear; 5 = takes clear responsibility and commits to concrete follow-up.
closure_score: 0 = call just ends; 3 = issue addressed but no recap or check; 5 = recaps the outcome, asks if anything else is needed, closes courteously."""

TELUGU_HINTS = """
TELUGU DOMAIN & CONVERSATIONAL GUIDELINES:
- Identity verification requires requesting both Order ID (ఆర్డర్ ఐడి) and registered phone digits (చివరి 4 అంకెలు). Disclosing customer account details or addresses before completing verification is an immediate CRITICAL failure.
- Hold protocol requires permission ("హోల్డ్ లో ఉండండి" / "hold lo undandi") and gratitude on return ("వేచి ఉన్నందుకు ధన్యవాదాలు").
- Ambiguous closure phrase "సరే, చూద్దాం లే" / "sare, chuddam le" ("okay, we'll see") indicates hesitation and unresolved doubt, NOT confirmed satisfaction. Do not treat customer as satisfied when this is spoken.
"""


def _step_block(step) -> str:
    flags = []
    if step.mandatory:
        flags.append("mandatory")
    if step.critical:
        flags.append("CRITICAL")
    desc = step.description or step.title
    return (
        f"- {step.id} | {step.title} | {', '.join(flags) or 'optional'}\n"
        f"  Required: {desc}\n"
        f"  Good looks like: {step.what_good}"
    )


def build_prompt(call: CallTranscript, topic: str, signals: Sequence[str], steps,
                 call_state: Optional[EarlyCallState] = None) -> str:
    step_text = "\n".join(_step_block(s) for s in steps)
    sigs = ", ".join(signals) if signals else "none"
    state_block = f"\nEARLY CALL MILESTONES (computed from transcript start)\n{call_state.format_for_prompt()}\n" if call_state else ""

    return f"""CALL TRANSCRIPT (turn numbers in [brackets] are authoritative; timing hints are measured from the audio)
{format_transcript(call.turns)}

CONTEXT
Detected topic: {topic}. Detected situation signals: {sigs}.
{state_block}
{TELUGU_HINTS}

SOP STEPS TO JUDGE (return exactly one judgement per step id below)
{step_text}

STATUS RULES
- followed: every required element of the step is clearly present in the transcript.
- partial: some but not all required elements (e.g. only the order ID was asked, not the last 4 digits of the phone).
- missed: the step was required in this call but the agent did not do it.
- not_applicable: the situation the step covers never happened in this call (for example a hold, transfer or callback step when none occurred, or an angry-customer step when the customer never showed frustration). Do NOT use not_applicable just because the agent skipped something that was required.
- BE STRICT. For every step, check each element named in "Required" one by one and list the elements you cannot find in `missing` (a short phrase; empty string only when nothing is missing). `followed` is allowed only when `missing` is empty. If the step was done but an element is absent, use `partial`; if it was not done at all, `missed`. An element counts only if the agent clearly said or did it: behaviour that merely resembles it does not count.
- For followed/partial: give the turn number and copy the exact words (max 25 words) from that AGENT turn. For missed/not_applicable: turn = 0 and quote = "".
- "reason" is one short sentence.

ALSO RETURN
- summary: 2-3 sentences (what the customer wanted, what the agent did, outcome). customer_issue: a short phrase. resolved: true/false.
- empathy_score, empathy_evidence (verbatim quote of the agent's best or worst moment), clarity_score, professionalism_score, ownership_score, closure_score.
{SCORE_GUIDE}
- turn_emotions: one entry for EVERY CUSTOMER turn (angry, frustrated, anxious, confused, neutral, satisfied, happy).
- agent_tones: one entry for EVERY AGENT turn describing how the agent comes across from the wording (warm, empathetic, calm, neutral, rushed, defensive, dismissive).
- gaps: only real problems, with the turn number and an exact quote. Allowed gap types: no_empathy, unresolved_issue, customer_repeating, no_summary, no_closing, ambiguous_closure, other. Do NOT report silences or interruptions; those are measured from the audio separately.
- strengths: up to 4 specific things the agent did well (concrete, tied to this call).
- coaching_tips: up to 4 specific, actionable tips addressed to the agent ("Next time, ..."), each tied to a real behaviour in this call.
- risk_flags: check for social-engineering / scam / suspicious support patterns. Flag only clear patterns if present. Return empty list [] if no such pattern is present.
"""


def _clamp_int(x, lo=0, hi=5) -> int:
    try:
        return max(lo, min(hi, int(round(float(x)))))
    except Exception:  # noqa: BLE001
        return lo


def analyze_conversation(call: CallTranscript, topic: str, signals: Sequence[str], step_ids: Sequence[str],
                         kb: KnowledgeBase, gateway, call_state: Optional[EarlyCallState] = None) -> Tuple[ConversationAnalysis, List[SOPResult], List[str]]:
    steps = [kb.by_id[s] for s in step_ids if s in kb.by_id]
    state = call_state or compute_call_state(call.turns)

    # Context window chunking: if call is unusually long (> 50 turns), process in overlapping chunks
    # keeping the early call_state intact for all chunks.
    if len(call.turns) > 50:
        chunk1_turns = call.turns[:35]
        chunk2_turns = call.turns[25:]
        subcall1 = call.model_copy(update={"turns": chunk1_turns})
        subcall2 = call.model_copy(update={"turns": chunk2_turns})

        prompt1 = build_prompt(subcall1, topic, signals, steps[:len(steps)//2 + 2], state)
        analysis1 = gateway.generate_structured(
            prompt1, ConversationAnalysis, system_instruction=SYSTEM, temperature=0.1,
            max_output_tokens=8192, call_id=f"{call.call_id}_chunk1",
        )
        prompt2 = build_prompt(subcall2, topic, signals, steps[len(steps)//2:], state)
        analysis2 = gateway.generate_structured(
            prompt2, ConversationAnalysis, system_instruction=SYSTEM, temperature=0.1,
            max_output_tokens=8192, call_id=f"{call.call_id}_chunk2",
        )
        # Merge analyses
        analysis = analysis2
        analysis.steps = analysis1.steps + analysis2.steps
        analysis.summary = analysis2.summary or analysis1.summary
        analysis.gaps = analysis1.gaps + analysis2.gaps
    else:
        prompt = build_prompt(call, topic, signals, steps, state)
        analysis = gateway.generate_structured(
            prompt, ConversationAnalysis, system_instruction=SYSTEM, temperature=0.1,
            max_output_tokens=8192, call_id=f"{call.call_id}_analysis",
        )

    # Post-process ambiguous closure ("sare, chuddam le")
    has_ambiguous_closure = any(
        re.search(r"\b(sare,?\s*chuddam\s*le|సరే,?\s*చూద్దాం\s*లే)\b", t.text, re.IGNORECASE)
        for t in call.turns[-5:]
        if t.speaker == "customer"
    )
    if has_ambiguous_closure:
        analysis.resolved = False
        analysis.closure_score = min(analysis.closure_score, 3)

    results, warnings = materialize_sop_results(call, analysis, steps, state)
    for name in ("empathy_score", "clarity_score", "professionalism_score", "ownership_score", "closure_score"):
        setattr(analysis, name, _clamp_int(getattr(analysis, name)))
    return analysis, results, warnings


def materialize_sop_results(call: CallTranscript, analysis: ConversationAnalysis, steps,
                            call_state: Optional[EarlyCallState] = None) -> Tuple[List[SOPResult], List[str]]:
    warnings: List[str] = []
    judged: Dict[str, object] = {}
    for j in analysis.steps:
        judged.setdefault(j.step_id.strip(), j)
    results: List[SOPResult] = []
    for step in steps:
        j = judged.get(step.id)
        if j is None:
            warnings.append(f"The judge returned nothing for step {step.id}; it was left out of scoring.")
            res = SOPResult(step_id=step.id, status="not_applicable", reason="Not judged (no answer from the model).")
        else:
            status, turn, quote, reason, verified = j.status, None, (j.quote or "").strip(), (j.reason or "").strip(), True
            missing = (j.missing or "").strip()
            if missing.lower().strip(" .") in ("none", "n/a", "na", "nothing", "-", "no", "nil"):
                missing = ""
            if status == "followed" and missing:
                status = "partial"   # the judge itself listed a missing element, so "followed" is not allowed
                reason = (reason + " ").strip() + f"(Downgraded: missing {missing}.)"
            if status in ("followed", "partial"):
                found, score = locate_quote(call.turns, quote, hint_turn=j.turn or None, speaker="agent")
                if found is None:
                    verified = False
                    if status == "followed":
                        status = "partial"
                        reason = (reason + " ").strip() + "(Downgraded: the quoted evidence was not found in the transcript.)"
                    warnings.append(f"{step.id}: evidence quote could not be verified.")
                else:
                    turn = found
            res = SOPResult(
                step_id=step.id, status=status, turn=turn, quote=quote if verified else quote, reason=reason,
                missing=missing if status in ("partial", "missed") else "", evidence_verified=verified,
            )

        # Enforce deterministic identity verification breach (Scenario A)
        if call_state and call_state.identity_breach_detected and step.id in ("GEN-03", "REF-S1"):
            res.status = "missed"
            res.turn = call_state.first_account_turn
            res.quote = call_state.first_account_quote
            res.reason = f"Critical breach: account details discussed at turn {call_state.first_account_turn} before identity verification completed."
            res.evidence_verified = True

        res.title, res.sop, res.weight = step.title, step.file.replace(".md", ""), step.weight
        res.critical, res.mandatory = step.critical, step.mandatory
        res.what_good_looks_like, res.example_phrase = step.what_good, step.example
        results.append(res)
    return results, warnings
