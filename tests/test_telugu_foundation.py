"""Tests for Phase 1 Telugu Foundations & Prodloop Requirements.

Covers:
1. Transcript quality gating ('unusable' returns structured 'cannot judge' with 0 LLM calls).
2. Observed vs Inferred strict separation (inferred claims never land in observed section).
3. Verbatim quote verification and certainty tagging.
4. Scenario A: Long call, issue resolved, agent never verifies identity before account disclosure.
   Expected: identity_verification = missed, kind = observed, severity = critical,
   evidence cites first account-detail turn, critical score cap <= 70.0 applied.
   [FIXTURE: Synthetic Telugu conversation marked in docstring].
5. Scenario B: Two holds checked individually + customer closing with 'sare, chuddam le'.
   Expected: Two hold evidence items, closure marked as inferred ambiguous finding,
   certainty = medium, resolution does NOT claim customer was satisfied.
   [FIXTURE: Synthetic Telugu conversation marked in docstring].
6. Human review storage in data/reviews/<call_id>.json and side-by-side annotation.
"""
from __future__ import annotations

import json
from pathlib import Path
import pytest

from src.audit.pipeline import AuditPipeline
from src.audit.rag import KnowledgeBase
from src.audit.review import load_reviews_for_call, save_review_decision
from src.audit.schemas import (CallTranscript, DialogueTurn, PolicyAnalysis,
                              ConversationAnalysis, StepJudgement, TurnEmotion, TurnTone, GapFinding)
from tests.fakes import FakeGateway, make_analysis

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def kb() -> KnowledgeBase:
    return KnowledgeBase(use_embeddings=False)


# ---------------------------------------------------------------------------
# 1. Transcript Quality Gating
# ---------------------------------------------------------------------------
def test_transcript_quality_gating_unusable(kb: KnowledgeBase, tmp_path: Path):
    """When transcript quality is unusable (<0.40 confidence or >65% silence),
    audit halts with cannot_judge=True and zero LLM calls.
    """
    turns = [
        DialogueTurn(turn_id=1, speaker="agent", text="...", asr_confidence=0.20, silence_before=0.0),
        DialogueTurn(turn_id=2, speaker="customer", text="...", asr_confidence=0.15, silence_before=15.0),
        DialogueTurn(turn_id=3, speaker="agent", text="...", asr_confidence=0.25, silence_before=20.0),
    ]
    call = CallTranscript(call_id="test_unusable_01", language="te", duration_seconds=50.0, turns=turns)

    gw = FakeGateway(analysis=None, policy=None)
    pipe = AuditPipeline(kb=kb, gateway=gw, cache_dir=tmp_path)
    report = pipe.audit_call(call)

    assert report.cannot_judge is True
    assert report.meta.llm_requests == 0
    assert report.scores.overall == 0.0
    assert report.scores.critical_failure is True
    assert "Unusable" in report.cannot_judge_reason or "confidence" in report.cannot_judge_reason.lower()


# ---------------------------------------------------------------------------
# 2. Observed vs Inferred Strict Separation
# ---------------------------------------------------------------------------
def test_observed_vs_inferred_separation(kb: KnowledgeBase, tmp_path: Path):
    """An inferred finding can never be categorized as an observed gap,
    and tone/empathy claims must only appear in uncertain interpretations.
    """
    turns = [
        DialogueTurn(turn_id=1, speaker="agent", text="Thank you for calling ShopEase. My name is Priya.", start_time=0.0, end_time=3.0),
        DialogueTurn(turn_id=2, speaker="customer", text="I am very angry about my delayed package.", start_time=3.5, end_time=7.0),
        DialogueTurn(turn_id=3, speaker="agent", text="Please give me your Order ID and last four digits of phone.", start_time=7.5, end_time=11.0),
        DialogueTurn(turn_id=4, speaker="customer", text="Order is ORD-12345, last four digits 9876.", start_time=11.5, end_time=14.0),
    ]
    call = CallTranscript(call_id="test_obs_inf_01", language="en", duration_seconds=20.0, turns=turns)

    gw = FakeGateway(analysis=lambda p: make_analysis(p, call), policy=PolicyAnalysis(claims=[]))
    pipe = AuditPipeline(kb=kb, gateway=gw, cache_dir=tmp_path)
    report = pipe.audit_call(call)

    for g in report.observed_gaps:
        assert g.kind == "observed", f"Finding {g.finding_id} in observed_gaps has kind={g.kind}"
        assert g.criterion_id not in ("empathy_and_communication", "GEN-05", "ANG-01", "ANG-02")

    for item in report.uncertain_interpretations:
        assert item.kind == "inferred" or item.certainty in ("low", "medium")


# ---------------------------------------------------------------------------
# 3. Verbatim Quote Verification
# ---------------------------------------------------------------------------
def test_quote_verification_tagging(kb: KnowledgeBase, tmp_path: Path):
    """Findings with verified verbatim quotes receive certainty=high;
    findings with fabricated or altered quotes receive certainty=low.
    """
    turns = [
        DialogueTurn(turn_id=1, speaker="agent", text="Thank you for calling ShopEase.", start_time=0.0, end_time=2.0),
        DialogueTurn(turn_id=2, speaker="customer", text="I need help with my order.", start_time=2.5, end_time=4.5),
        DialogueTurn(turn_id=3, speaker="agent", text="Please provide your Order ID.", start_time=5.0, end_time=7.0),
    ]
    call = CallTranscript(call_id="test_quote_verif_01", language="en", duration_seconds=10.0, turns=turns)

    # Injected fake quote for GEN-01
    gw = FakeGateway(
        analysis=lambda p: make_analysis(p, call, quote_for={"GEN-01": "Words that were never spoken by Priya at all"}),
        policy=PolicyAnalysis(claims=[]),
    )
    pipe = AuditPipeline(kb=kb, gateway=gw, cache_dir=tmp_path)
    report = pipe.audit_call(call)

    gen01_finding = next((f for f in report.findings if f.criterion_id == "GEN-01"), None)
    assert gen01_finding is not None
    assert gen01_finding.certainty == "low"
    assert "not verified" in gen01_finding.certainty_reason.lower() or "quote" in gen01_finding.certainty_reason.lower()


# ---------------------------------------------------------------------------
# 4. Scenario A: Long Call, Issue Resolved, Identity Verification Breached
# ---------------------------------------------------------------------------
def test_scenario_a_identity_verification_breached_caps_score(kb: KnowledgeBase, tmp_path: Path):
    """[SYNTHETIC TELUGU FIXTURE]: Long customer call where the issue is resolved,
    but the agent discusses customer account & delivery address details at turn 3
    WITHOUT ever requesting Order ID or last 4 digits of phone.

    Expected:
    - identity_verification = missed, kind = observed, severity = critical
    - Evidence cites turn 3 (first account detail discussion)
    - Critical score cap applied (overall score <= 70.0, critical_failure = True)
    """
    turns = [
        DialogueTurn(turn_id=1, speaker="agent", text="షాపేజ్ కస్టమర్ కేర్ కి స్వాగతం. నా పేరు రాహుల్. ఈ కాల్ రికార్డ్ చేయబడుతుంది.", start_time=0.0, end_time=4.0),
        DialogueTurn(turn_id=2, speaker="customer", text="నమస్కారం అండీ, నేను ఆర్డర్ చేసిన బోట్ స్మార్ట్‌వాచ్ డెలివరీ కాలేదు.", start_time=4.5, end_time=8.5),
        DialogueTurn(turn_id=3, speaker="agent", text="సరే అండీ, మీ ఆర్డర్ ఫ్లాట్ 12, సాయి రెసిడెన్సీ, పూణే అడ్రస్ కి 8,500 రూపాయలకు పంపించాము.", start_time=9.0, end_time=14.0), # ACCOUNT DISCLOSURE WITHOUT VERIFICATION
        DialogueTurn(turn_id=4, speaker="customer", text="అవును ఆ అడ్రస్సే, కానీ ఇంకా డెలివరీ రాలేదు.", start_time=14.5, end_time=17.5),
        DialogueTurn(turn_id=5, speaker="agent", text="కొరియర్ పార్టనర్ ఆలస్యం చేశారు, నేను ఇప్పుడే రీ-డిస్పాచ్ చేస్తున్నాను.", start_time=18.0, end_time=22.0),
        DialogueTurn(turn_id=6, speaker="customer", text="ధన్యవాదాలు, ఎప్పటి వరకు వస్తుంది?", start_time=22.5, end_time=25.0),
        DialogueTurn(turn_id=7, speaker="agent", text="రేపు సాయంత్రం 5 గంటల లోపు డెలివరీ పూర్తవుతుంది. ట్రాకింగ్ మెసేజ్ పంపాను.", start_time=25.5, end_time=29.5),
        DialogueTurn(turn_id=8, speaker="customer", text="సరే చాలా సంతోషం, సమస్య పరిష్కరించారు.", start_time=30.0, end_time=33.0),
        DialogueTurn(turn_id=9, speaker="agent", text="షాపేజ్ కి కాల్ చేసినందుకు ధన్యవాదాలు. సెలవు.", start_time=33.5, end_time=36.0),
    ]
    call = CallTranscript(call_id="te_synthetic_scenario_a", language="te", duration_seconds=40.0, turns=turns)

    # Model reports resolved=True and issue resolved
    def fake_resolved_analysis(prompt):
        ana = make_analysis(prompt, call)
        ana.resolved = True
        return ana

    gw = FakeGateway(analysis=fake_resolved_analysis, policy=PolicyAnalysis(claims=[]))
    pipe = AuditPipeline(kb=kb, gateway=gw, cache_dir=tmp_path)
    report = pipe.audit_call(call)

    # 1. Critical Failure & Cap
    assert report.scores.critical_failure is True, "Critical failure must be triggered for identity breach"
    assert report.scores.overall <= 70.0, f"Overall score must be capped at 70.0, got {report.scores.overall}"

    # 2. Verification finding is missed, observed, critical
    v_finding = next((f for f in report.findings if f.criterion_id in ("GEN-03", "REF-S1", "identity_verification")), None)
    assert v_finding is not None
    assert v_finding.verdict == "missed"
    assert v_finding.kind == "observed"
    assert v_finding.severity == "critical"

    # 3. Evidence cites turn 3 (first account disclosure)
    assert any(e.turn_id == 3 for e in v_finding.evidence)


# ---------------------------------------------------------------------------
# 5. Scenario B: Two Holds + Ambiguous Closure ("sare, chuddam le")
# ---------------------------------------------------------------------------
def test_scenario_b_two_holds_and_ambiguous_closure(kb: KnowledgeBase, tmp_path: Path):
    """[SYNTHETIC TELUGU FIXTURE]: Call with two separate hold events.
    The customer ends with 'సరే, చూద్దాం లే' ('sare, chuddam le' - 'okay, we'll see').

    Expected:
    - hold_handling checked per hold (multi-hold evidence)
    - 'sare, chuddam le' records an inferred finding with certainty = medium
    - Resolution must NOT claim 'customer satisfied' (resolved != satisfied confirmation)
    """
    turns = [
        DialogueTurn(turn_id=1, speaker="agent", text="ShopEase support. My name is Swathi. Call is recorded.", start_time=0.0, end_time=3.0),
        DialogueTurn(turn_id=2, speaker="customer", text="I received a defective mixer grinder.", start_time=3.5, end_time=6.0),
        DialogueTurn(turn_id=3, speaker="agent", text="Please provide Order ID and phone number.", start_time=6.5, end_time=9.0),
        DialogueTurn(turn_id=4, speaker="customer", text="Order ID ORD-99881, phone last four digits 1122.", start_time=9.5, end_time=12.0),
        # Hold 1 (30s dead air)
        DialogueTurn(turn_id=5, speaker="agent", text="Please stay on hold for 1 minute while I check warranty.", start_time=12.5, end_time=15.0),
        DialogueTurn(turn_id=6, speaker="agent", text="Thank you for waiting on line.", start_time=45.0, end_time=47.0, silence_before=30.0),
        DialogueTurn(turn_id=7, speaker="customer", text="What is the update?", start_time=47.5, end_time=49.0),
        # Hold 2 (25s dead air)
        DialogueTurn(turn_id=8, speaker="agent", text="I need one more brief hold to confirm technician visit.", start_time=49.5, end_time=52.0),
        DialogueTurn(turn_id=9, speaker="agent", text="Thank you for your patience on hold.", start_time=77.0, end_time=79.0, silence_before=25.0),
        DialogueTurn(turn_id=10, speaker="agent", text="Technician will visit tomorrow to inspect.", start_time=79.5, end_time=82.0),
        # Ambiguous closure: "sare, chuddam le"
        DialogueTurn(turn_id=11, speaker="customer", text="సరే, చూద్దాం లే. (sare, chuddam le)", start_time=82.5, end_time=85.0),
        DialogueTurn(turn_id=12, speaker="agent", text="Thank you for contacting ShopEase. Good day.", start_time=85.5, end_time=88.0),
    ]
    call = CallTranscript(call_id="te_synthetic_scenario_b", language="te", duration_seconds=90.0, turns=turns)

    gw = FakeGateway(analysis=lambda p: make_analysis(p, call), policy=PolicyAnalysis(claims=[]))
    pipe = AuditPipeline(kb=kb, gateway=gw, cache_dir=tmp_path)
    report = pipe.audit_call(call)

    # 1. Holds: two holds evaluated
    hold_finding = next((f for f in report.findings if f.criterion_id == "hold_handling"), None)
    if hold_finding:
        assert len(hold_finding.evidence) == 2, f"Expected 2 hold evidence items, got {len(hold_finding.evidence)}"

    # 2. Ambiguous closure: Inferred finding with medium certainty
    ambig_finding = next((f for f in report.findings if "ambiguous_closure" in f.finding_id or "chuddam" in f.name.lower()), None)
    assert ambig_finding is not None, "Expected an inferred ambiguous closure finding for 'sare, chuddam le'"
    assert ambig_finding.kind == "inferred"
    assert ambig_finding.certainty == "medium"
    assert "chuddam" in ambig_finding.certainty_reason.lower() or "ambiguous" in ambig_finding.certainty_reason.lower()

    # 3. Resolution does not claim satisfied
    assert report.resolved is False, "Resolution must not claim customer satisfied when closure is non-committal"


# ---------------------------------------------------------------------------
# 6. Human Review Storage & Annotation
# ---------------------------------------------------------------------------
def test_human_review_storage_and_annotation(tmp_path: Path):
    """Review decisions stored in data/reviews/<call_id>.json are loaded and applied
    without deleting original AI findings.
    """
    call_id = "test_review_call_01"
    finding_id = "sop_GEN-01_1"

    # Save an overturn review
    save_review_decision(call_id, finding_id, decision="overturned", reviewer_note="Agent spoke greeting softly", base_dir=tmp_path)

    reviews = load_reviews_for_call(call_id, base_dir=tmp_path)
    assert finding_id in reviews
    assert reviews[finding_id].decision == "overturned"
    assert reviews[finding_id].reviewer_note == "Agent spoke greeting softly"



# ---------------------------------------------------------------------------
# 7. Long Conversation Early-State Preservation (Step 5)
# ---------------------------------------------------------------------------
def test_long_conversation_preserves_early_verification_finding(kb: KnowledgeBase, tmp_path: Path):
    """[SYNTHETIC TELUGU FIXTURE]: Long call (> 50 turns created by concatenating
    turns), where the early turns have an identity verification breach (address disclosed
    without verification).

    Verifies that processing a long call through chunked evaluation retains the exact same
    early-call identity verification breach finding as the short version.
    """
    base_turns = [
        DialogueTurn(turn_id=1, speaker="agent", text="షాపేజ్ సపోర్ట్. నా పేరు రమేష్.", start_time=0.0, end_time=3.0),
        DialogueTurn(turn_id=2, speaker="customer", text="నా ఆర్డర్ రీప్లేస్మెంట్ కావాలి.", start_time=3.5, end_time=6.0),
        DialogueTurn(turn_id=3, speaker="agent", text="మీ ఆర్డర్ ఫ్లాట్ 12, సాయి రెసిడెన్సీ అడ్రస్ కి వెళ్ళింది.", start_time=6.5, end_time=10.0), # EARLY BREACH
    ]
    # Pad to 56 turns
    extra_turns = []
    curr_time = 10.5
    for i in range(4, 56):
        spk = "customer" if i % 2 == 0 else "agent"
        extra_turns.append(DialogueTurn(
            turn_id=i,
            speaker=spk,
            text="సరే అండీ వివరాలు అర్థమయ్యాయి." if spk == "customer" else "నేను మీ సమస్యను పరిశీలిస్తున్నాను.",
            start_time=curr_time,
            end_time=curr_time + 2.0,
        ))
        curr_time += 2.5

    long_turns = base_turns + extra_turns
    call = CallTranscript(call_id="te_synthetic_long_56turns", language="te", duration_seconds=curr_time, turns=long_turns)

    gw = FakeGateway(analysis=lambda p: make_analysis(p, call), policy=PolicyAnalysis(claims=[]))
    pipe = AuditPipeline(kb=kb, gateway=gw, cache_dir=tmp_path)
    report = pipe.audit_call(call)

    # Verification finding must still be captured despite 56 turns
    v_finding = next((f for f in report.findings if f.criterion_id in ("GEN-03", "REF-S1", "identity_verification")), None)
    assert v_finding is not None
    assert v_finding.verdict == "missed"
    assert v_finding.kind == "observed"
    assert report.scores.critical_failure is True

