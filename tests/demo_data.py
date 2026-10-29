"""TEST/PREVIEW ONLY: builds realistic AuditReports from the labelled calls with an 'oracle' fake LLM
(statuses and violations from the ground truth, emotions interpolated from the labelled arc).
Used to look at charts/UI and to test the expected-vs-actual machinery. The product never uses this."""
from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Dict, List

from src.audit.pipeline import AuditPipeline
from src.audit.rag import KnowledgeBase
from src.audit.schemas import (ConversationAnalysis, GapFinding, PolicyAnalysis, PolicyClaim, StepJudgement, TurnEmotion, TurnTone)
from src.audit.transcript_io import find_transcripts, load_transcript_json
from tests.fakes import FakeGateway, step_ids_in

ROOT = Path(__file__).resolve().parent.parent

NEG = {"angry", "frustrated", "anxious"}


def _interp_arc(arc: List[str], n: int, quality: str) -> List[str]:
    if n == 0:
        return []
    start, mid, end = (arc + ["neutral"] * 3)[:3]
    out = []
    for i in range(n):
        f = i / max(1, n - 1)
        out.append(start if f < 0.34 else (mid if f < 0.67 else end))
    # make the opening of an angry call really angry and the first reaction sharper
    if out and out[0] == "frustrated" and quality == "bad_deviation":
        out[0] = "angry"
    return out


def oracle_analysis(prompt: str, call, raw) -> ConversationAnalysis:
    gt = raw["ground_truth"]
    q = raw["quality"]
    agent_turns = [t for t in call.turns if t.speaker == "agent"]
    cust_turns = [t for t in call.turns if t.speaker == "customer"]
    steps = []
    for sid in step_ids_in(prompt):
        st = gt["sop_steps"].get(sid, "followed")
        if sid not in gt["sop_steps"] and sid.startswith(("ANG-06",)):
            st = "not_applicable"
        if st in ("missed", "not_applicable"):
            steps.append(StepJudgement(step_id=sid, status=st, turn=0, quote="", reason="Judged from the transcript.", missing="the required action" if st == "missed" else ""))
        else:
            t = agent_turns[min(1, len(agent_turns) - 1)]
            steps.append(StepJudgement(step_id=sid, status=st, turn=t.turn_id, quote=" ".join(t.text.split()[:9]), reason="Done as required." if st == "followed" else "Only partly done.",
                                       missing="" if st == "followed" else "one required element"))
    emos = _interp_arc(gt["customer_emotion_arc"], len(cust_turns), q)
    neg_agent = any(gt["sop_steps"].get(s) == "missed" for s in ("ANG-01", "ANG-02", "GEN-05"))
    cycle_pos = ["calm", "warm", "empathetic", "calm", "warm"]
    cycle_neg = ["neutral", "dismissive", "defensive", "rushed", "dismissive"]
    tones = []
    for i, t in enumerate(agent_turns):
        tones.append(TurnTone(turn=t.turn_id, tone=(cycle_neg if neg_agent else cycle_pos)[i % 5]))
    emp = {"good": 5, "mild_deviation": 3, "bad_deviation": 1}[q]
    comm = {"good": 5, "mild_deviation": 4, "bad_deviation": 2}[q]
    return ConversationAnalysis(
        summary={"good": "The agent handled the call well and solved the customer's problem.",
                 "mild_deviation": "The agent solved the problem but skipped a couple of expected steps.",
                 "bad_deviation": "The agent broke important rules and the customer left without a proper solution."}[q],
        customer_issue=raw.get("customer_persona", "customer issue")[:60], resolved=q != "bad_deviation", steps=steps,
        empathy_score=emp, empathy_evidence="", clarity_score=comm, professionalism_score=comm, ownership_score=comm, closure_score=comm,
        turn_emotions=[TurnEmotion(turn=t.turn_id, emotion=e) for t, e in zip(cust_turns, emos)], agent_tones=tones,
        gaps=[], strengths=["Polite greeting"] if q != "bad_deviation" else [], coaching_tips=[] if q == "good" else ["Review the steps marked as missed."],
    )


def oracle_policy(raw) -> PolicyAnalysis:
    claims = [PolicyClaim(turn=v["turn"], quote=" ".join(v["said"].split()[:10]), claim="claim", clause_id=v["clause_id"], verdict="violation",
                          severity=v["severity"], explanation=f"The agent's statement conflicts with the policy. Correct rule: {v['correct_fact']}") for v in raw["ground_truth"]["policy_violations"]]
    return PolicyAnalysis(claims=claims)


def build_reports(only: List[str] | None = None, cache_dir=None) -> Dict[str, object]:
    kb = KnowledgeBase(use_embeddings=False)
    cache_dir = cache_dir or tempfile.mkdtemp()
    out = {}
    for p in find_transcripts(ROOT / "data" / "transcripts"):
        if only and p.stem not in only:
            continue
        call, raw = load_transcript_json(p)
        gw = FakeGateway(analysis=lambda pr, c=call, r=raw: oracle_analysis(pr, c, r), policy=oracle_policy(raw))
        out[p.stem] = AuditPipeline(kb=kb, gateway=gw, cache_dir=cache_dir).audit_call(call)
    return out
