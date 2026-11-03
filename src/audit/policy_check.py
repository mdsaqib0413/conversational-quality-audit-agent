"""Policy compliance: ONE LLM request comparing the agent's factual claims with the retrieved policy clauses (RAG).

Hard rules:
* the model may only cite clause IDs that were retrieved;
* every finding needs a quote that really appears in an agent turn, otherwise it is dropped;
* with no relevant clause the answer is "no relevant policy found" and nothing is penalised.
"""

from __future__ import annotations

import logging
import os
import re
from typing import List, Optional, Sequence, Tuple

from .evidence import locate_quote
from .prompts import _load_agent, format_transcript
from .rag import Chunk, KnowledgeBase
from .schemas import CallTranscript, PolicyAnalysis, PolicyResult

logger = logging.getLogger(__name__)

NO_POLICY = "no relevant policy found"

SYSTEM = _load_agent("policy_agent.md")

ALWAYS_INCLUDE = ["PRV-1.1", "ESC-1.1", "ESC-1.2"]


def get_policy_model() -> str:
    """Return the model to use for policy compliance checking.

    Defaults to 'gemini-3.5-flash', overridable via POLICY_MODEL environment variable.
    """
    return os.environ.get("POLICY_MODEL", "gemini-3.5-flash").strip() or "gemini-3.5-flash"


def agent_query(call: CallTranscript, limit_chars: int = 3500) -> str:
    text = " ".join(t.text for t in call.turns if t.speaker == "agent")
    return text[:limit_chars]


def call_retrieval_query(call: CallTranscript, limit_chars: int = 4000) -> str:
    """Build retrieval query combining customer request turns and agent turns, preserving the end of the call."""
    turns_text = [t.text for t in call.turns]
    full_text = " ".join(turns_text)
    if len(full_text) <= limit_chars:
        return full_text
    head_len = 1500
    tail_len = limit_chars - head_len - 5
    return full_text[:head_len] + " ... " + full_text[-tail_len:]


def _format_clause_for_prompt(c: Chunk) -> str:
    """Format clause text for policy prompt, respecting POLICY_PROMPT_METADATA (default: 1)."""
    send_metadata = os.environ.get("POLICY_PROMPT_METADATA", "1").strip().lower() not in ("0", "false", "no", "off")
    if send_metadata:
        return c.short(1100)
    lines = c.text.split("\n")
    content_lines = [
        line for line in lines
        if not re.match(r"^\s*-\s*\*\*(?:Topics|Situations|Numeric Limit|Default Severity|Kind):\*\*", line)
    ]
    t = re.sub(r"\s+", " ", " ".join(content_lines).replace("**", "")).strip()
    return t if len(t) <= 1100 else t[:1097] + "..."


def build_prompt(call: CallTranscript, clauses) -> str:
    clause_text = "\n\n".join(f"[{c.id}] {c.title}\n{_format_clause_for_prompt(c)}" for c in clauses)
    ids = ", ".join(c.id for c in clauses)
    return f"""CALL TRANSCRIPT
{format_transcript(call.turns)}

POLICY EXCERPTS (the only allowed source of truth)
{clause_text}

TASK
List every factual statement, promise or commitment the AGENT made that one of the excerpts covers: time limits, amounts, eligibility, refund method, approval limits, escalation, sharing account data, hold rules and similar. Also list a clear failure to do what an excerpt makes mandatory (for example the customer asked for a supervisor twice and the agent refused), quoting the agent turn where the mistake happened.

For each item return:
- turn: the AGENT turn number, quote: exact words (max 25) from that turn, claim: the agent's statement in plain words.
- clause_id: one of [{ids}] or "none" if no excerpt covers it.
- verdict: "compliant" (matches the excerpt), "violation" (contradicts it, promises something it does not allow, or breaks a mandatory rule), or "unverifiable" (no excerpt covers it or you are not sure).
- severity (only for violations, otherwise "none"):
    minor = a wrong informational detail about a timeline, duration, count or condition (delivery or replacement time, number of delivery attempts, refund processing days, shipping-fee threshold, warranty length) that does not by itself commit money or authority;
    major = a wrong promise or decision about money or eligibility (instant refund, refund to a method the policy does not allow, cash handed over, wrong return window used to accept or reject a return, compensation the policy does not allow);
    critical = a security or authority breach (reading out an OTP, disclosing account details before identity verification, approving a refund above the agent's limit or without required approval, accepting a claim without mandatory proof, refusing a mandatory escalation).
- explanation: one or two sentences stating what the agent said and what the excerpt says (cite the numbers).

Be conservative: if you are not sure a statement contradicts the policy, mark it "unverifiable". Do not repeat the same issue twice. List at most 6 compliant claims, but ALL violations.
"""


def get_policy_context_mode() -> str:
    """Return the active policy context mode: 'A' or 'G' (default: 'G').
    
    Controlled via the POLICY_CONTEXT environment variable:
      - 'A': baseline behavior (ALWAYS_INCLUDE + topic family + top-k hybrid).
      - 'G': default behavior (baseline A + every PRV and ESC clause always included).
    """
    mode = os.environ.get("POLICY_CONTEXT", "G").strip().upper()
    return "A" if mode == "A" else "G"


def get_policy_context_clauses(
    call: CallTranscript,
    topic: str,
    kb: KnowledgeBase,
    k: int = 10,
    mode: Optional[str] = None,
) -> List[Chunk]:
    """Retrieve policy clauses for a call according to the active POLICY_CONTEXT mode ('A' or 'G')."""
    if mode is None:
        mode = get_policy_context_mode()
    else:
        mode = "A" if mode.strip().upper() == "A" else "G"

    family = [c.id for c in kb.policies_for_topic(topic)]
    if mode == "G":
        safety_families = [c.id for c in kb.policies if c.family in ("PRV", "ESC") or c.id.startswith(("PRV-", "ESC-"))]
        always = list(dict.fromkeys(ALWAYS_INCLUDE + family + safety_families))
    else:
        always = list(dict.fromkeys(ALWAYS_INCLUDE + family))
    return kb.retrieve_policies(agent_query(call), topic=topic, k=k, always_include=always)


def check_policies(
    call: CallTranscript,
    topic: str,
    kb: KnowledgeBase,
    gateway=None,
    k: int = 10,
    model: Optional[str] = None,
) -> Tuple[List[PolicyResult], List[str], List[Chunk]]:
    if gateway is None:
        from .llm import get_policy_gateway

        gateway = get_policy_gateway(model=model or get_policy_model())
    # Retrieve clauses according to POLICY_CONTEXT mode (default: 'G' includes all PRV and ESC clauses)
    clauses = get_policy_context_clauses(call, topic, kb, k=k)
    prompt = build_prompt(call, clauses)
    analysis = gateway.generate_structured(
        prompt, PolicyAnalysis, system_instruction=SYSTEM, temperature=0.0, max_output_tokens=6144,
        call_id=f"{call.call_id}_policy",
    )
    results, warnings = materialize_policy_results(call, analysis, clauses, kb)
    return results, warnings, clauses


def materialize_policy_results(call: CallTranscript, analysis: PolicyAnalysis, clauses, kb: KnowledgeBase) -> Tuple[List[PolicyResult], List[str]]:
    allowed = {c.id for c in clauses}
    warnings: List[str] = []
    out: List[PolicyResult] = []
    seen = set()
    for c in analysis.claims:
        clause_id = c.clause_id.strip()
        verdict, severity = c.verdict, c.severity
        if clause_id not in allowed:
            if verdict == "violation":
                warnings.append(f"Dropped a violation that cited an unknown clause ('{clause_id}').")
                continue
            clause_id, verdict, severity = NO_POLICY, "unverifiable", "none"
        if verdict != "violation":
            severity = "none"
        elif severity == "none":
            severity = "minor"
        turn, score = locate_quote(call.turns, c.quote, hint_turn=c.turn or None, speaker="agent")
        if turn is None:
            if verdict == "violation":
                warnings.append(f"Dropped an unverifiable violation claim for {clause_id}: the quote is not in any agent turn.")
                continue
            if verdict == "compliant":
                continue
        key = (clause_id, turn, verdict)
        if key in seen:
            continue
        seen.add(key)
        chunk = kb.by_id.get(clause_id)
        out.append(PolicyResult(
            clause_id=clause_id, policy_title=kb.policy_title(clause_id) if chunk else "", verdict=verdict,
            severity=severity, turn=turn, quote=c.quote.strip(), claim=c.claim.strip(), explanation=c.explanation.strip(),
            policy_text=chunk.body(500) if chunk else "", evidence_verified=turn is not None,
        ))
    # The same mistake repeated later in the call is ONE finding (penalised once, repeats listed).
    merged: List[PolicyResult] = []
    first_violation = {}
    for r in sorted(out, key=lambda r: r.turn or 0):
        if r.verdict == "violation":
            key = r.clause_id
            if key in first_violation:
                head = first_violation[key]
                if r.turn and r.turn != head.turn:
                    head.repeat_turns.append(r.turn)
                sev_rank = {"minor": 1, "major": 2, "critical": 3}
                if sev_rank.get(r.severity, 0) > sev_rank.get(head.severity, 0):
                    head.severity = r.severity
                continue
            first_violation[key] = r
        merged.append(r)
    out = merged
    order = {"violation": 0, "compliant": 1, "unverifiable": 2}
    out.sort(key=lambda r: (order[r.verdict], r.turn or 0))
    return out, warnings


_involved_cache: dict = {}


def get_involved_clause_ids(report: "AuditReport", kb: KnowledgeBase) -> Tuple[List[str], bool]:
    """Return (clause_ids, was_computed_now).

    If the report already contains retrieved_clause_ids, return them with was_computed_now=False.
    Otherwise, compute on the fly using kb.retrieve_policies (local, no LLM) and return with was_computed_now=True.
    """
    if getattr(report, "retrieved_clause_ids", None):
        return list(report.retrieved_clause_ids), False
    k = (getattr(report, "call_id", ""), getattr(report, "topic", ""), getattr(report, "generated_at", ""))
    if k in _involved_cache:
        return _involved_cache[k], True
    family = [c.id for c in kb.policies_for_topic(report.topic)]
    query = agent_query(report.transcript)
    clauses = kb.retrieve_policies(query, topic=report.topic, k=10, always_include=ALWAYS_INCLUDE + family, use_embeddings=False)
    res = [c.id for c in clauses]
    _involved_cache[k] = res
    return res, True

