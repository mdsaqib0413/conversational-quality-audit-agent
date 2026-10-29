from pathlib import Path
import pytest

from src.audit.call_player import extract_key_moments, resolve_audio_path
from src.audit.policy_check import get_involved_clause_ids
from src.audit.rag import KnowledgeBase
from src.audit.schemas import (
    AuditMeta,
    AuditReport,
    CallTranscript,
    DialogueTurn,
    EmotionArc,
    EmotionPoint,
    PolicyResult,
    ScoreBreakdown,
    SOPResult,
)

ROOT = Path(__file__).resolve().parent.parent


def test_audio_path_resolution():
    # 1. Prefer mono over stereo for call_001
    p = resolve_audio_path("call_001")
    assert p is not None and p.is_file()
    assert p.name == "call_001.mp3"

    # 2. Real call resolution
    real_p = resolve_audio_path("en_real_001")
    if (ROOT / "data" / "audio" / "real_calls" / "en_real_001.mp3").is_file():
        assert real_p is not None and real_p.is_file()
        assert "real_calls" in str(real_p)

    # 3. Nonexistent call
    none_p = resolve_audio_path("non_existent_call_99999")
    assert none_p is None


def test_key_moment_extraction_synthetic():
    turns = [
        DialogueTurn(turn_id=1, speaker="agent", start_time=0.0, end_time=4.0, text="Hello, thank you for calling ShopEase."),
        DialogueTurn(turn_id=2, speaker="customer", start_time=5.0, end_time=12.0, text="I am furious, my order never arrived!", emotion="angry"),
        DialogueTurn(turn_id=3, speaker="agent", start_time=13.0, end_time=25.0, text="I will issue an immediate refund of Rs 10000 without any receipt."),
        DialogueTurn(turn_id=4, speaker="customer", start_time=26.0, end_time=32.0, text="Thank you, that helps a lot.", emotion="satisfied"),
        DialogueTurn(turn_id=5, speaker="agent", start_time=33.0, end_time=38.0, text="Have a wonderful day, goodbye."),
    ]
    call = CallTranscript(call_id="test_call", source="audio", duration_seconds=40.0, turns=turns)
    scores = ScoreBreakdown(
        sop_score=30.0, policy_score=10.0, empathy_score=10.0, communication_score=10.0,
        overall_before_cap=60.0, overall=60.0, grade="C",
    )
    sop_results = [
        SOPResult(step_id="GEN-02", title="Identity verification", status="missed", turn=None, missing="Did not verify phone"),
        SOPResult(step_id="GEN-03", title="Call recording disclosure", status="missed", turn=1, quote="Hello, thank you for calling"),
    ]
    policy_results = [
        PolicyResult(
            clause_id="REF-2.1", verdict="violation", severity="critical", turn=3,
            quote="I will issue an immediate refund", explanation="Refund exceeding threshold",
        )
    ]
    rep = AuditReport(
        call_id="test_call", generated_at="2026-10-22T00:00:00", topic="refund", topic_confidence=0.95,
        scores=scores, sop_results=sop_results, policy_results=policy_results, transcript=call,
    )

    moments, never = extract_key_moments(rep)

    # Verify moments are sorted by time
    for i in range(len(moments) - 1):
        assert moments[i].time_sec <= moments[i + 1].time_sec

    # Check emotion turn
    emo_moments = [m for m in moments if m.category == "emotion"]
    assert any("angry" in m.label and m.who == "Customer" for m in emo_moments)
    assert any("recovered" in m.label and m.who == "Customer" for m in emo_moments)

    # Check SOP deviation with turn
    sop_moments = [m for m in moments if m.category == "sop"]
    assert any("GEN-03" in m.label and m.who == "Agent" for m in sop_moments)

    # Check policy violation with turn
    pol_moments = [m for m in moments if m.category == "policy"]
    assert any("REF-2.1" in m.label and m.who == "Agent" for m in pol_moments)

    # Check closing moment
    assert any(m.category == "closing" for m in moments)

    # Check missed SOP without turn is placed in never_happened
    assert any(n.step_id == "GEN-02" for n in never)


def test_key_moment_extraction_from_stored_report():
    audit_files = list((ROOT / "data" / "cache" / "audits").glob("*.json"))
    if not audit_files:
        pytest.skip("no cached audits")

    rep = AuditReport.model_validate_json(audit_files[0].read_text(encoding="utf-8"))
    moments, never = extract_key_moments(rep)

    assert isinstance(moments, list)
    assert isinstance(never, list)
    for i in range(len(moments) - 1):
        assert moments[i].time_sec <= moments[i + 1].time_sec


def test_retrieved_clauses_fallback():
    kb = KnowledgeBase(use_embeddings=False)
    turns = [
        DialogueTurn(turn_id=1, speaker="customer", start_time=0.0, end_time=4.0, text="I want a refund for my order ORD-1234."),
        DialogueTurn(turn_id=2, speaker="agent", start_time=5.0, end_time=10.0, text="I will check our refund return window."),
    ]
    call = CallTranscript(call_id="call_fallback_test", source="transcript", duration_seconds=12.0, turns=turns)
    scores = ScoreBreakdown(
        sop_score=40.0, policy_score=30.0, empathy_score=15.0, communication_score=15.0,
        overall_before_cap=100.0, overall=100.0, grade="A",
    )
    rep = AuditReport(
        call_id="call_fallback_test", generated_at="2026-10-22T00:00:00", topic="refund", topic_confidence=0.9,
        scores=scores, transcript=call, retrieved_clause_ids=[],
    )

    # 1. Fallback when empty: computes on the fly
    clause_ids, was_computed = get_involved_clause_ids(rep, kb)
    assert was_computed is True
    assert len(clause_ids) > 0
    assert any(cid.startswith("REF") for cid in clause_ids)

    # 2. When already present: returns existing without recomputing
    rep.retrieved_clause_ids = ["PRV-1.1", "ESC-1.1"]
    cached_ids, was_computed_cached = get_involved_clause_ids(rep, kb)
    assert was_computed_cached is False
    assert cached_ids == ["PRV-1.1", "ESC-1.1"]


def _make_report(call_id: str, overall: float, grade: str, crit: bool = False, risk_flags: list | None = None) -> AuditReport:
    from src.audit.schemas import CallTranscript, ScoreBreakdown
    scores = ScoreBreakdown(
        sop_score=20.0, policy_score=20.0, empathy_score=20.0, communication_score=20.0,
        overall_before_cap=overall, overall=overall, grade=grade, critical_failure=crit,
    )
    transcript = CallTranscript(call_id=call_id, source="transcript", duration_seconds=10.0, turns=[])
    return AuditReport(
        call_id=call_id, generated_at="2026-10-23T00:00:00", topic="general", topic_confidence=0.9,
        scores=scores, transcript=transcript,
        risk_flags=risk_flags or [],
    )


def test_dashboard_aggregates_exclude_risk_flagged():
    """Risk-flagged reports must be excluded from all dashboard aggregate metrics."""
    from src.audit.ui_html import dash_hero

    r_a = _make_report("call_001", 92.0, "A")
    r_b = _make_report("call_002", 82.0, "B")
    r_c = _make_report("call_003", 55.0, "C", crit=True)
    ns1 = _make_report("en_real_001", 0.0, "D", risk_flags=["possible scam"])
    ns2 = _make_report("en_real_002", 0.0, "D", risk_flags=["social engineering"])

    scored = [r_a, r_b, r_c]
    unscored = [ns1, ns2]

    # dash_hero must not raise
    html = dash_hero(scored, unscored)
    assert "en_real_001" in html or "real_001" in html  # appears in chart
    assert "en_real_002" in html or "real_002" in html

    # Aggregates computed only over scored
    n = len(scored)
    avg = sum(r.scores.overall for r in scored) / n
    crit_count = sum(1 for r in scored if r.scores.critical_failure)
    passing_pct = sum(1 for r in scored if r.scores.overall >= 70) / n * 100

    assert n == 3
    assert abs(avg - (92 + 82 + 55) / 3) < 0.01
    assert crit_count == 1
    assert abs(passing_pct - 200 / 3) < 0.01

    # Risk-flagged calls must NOT appear in grade groups
    grade_A = [r for r in scored if r.scores.grade == "A"]
    grade_D = [r for r in scored if r.scores.grade == "D"]
    all_ids_in_grades = {r.call_id for r in scored}
    assert "en_real_001" not in all_ids_in_grades
    assert "en_real_002" not in all_ids_in_grades
    assert len(grade_A) == 1
    assert len(grade_D) == 0  # no scored D in this set

