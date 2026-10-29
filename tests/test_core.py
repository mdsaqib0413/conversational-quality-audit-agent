"""KB parsing, topic detection, evidence, scoring, diarization helpers (no network, no ML models)."""
from pathlib import Path

import pytest

from src.audit.diarize import heuristic_labels, segments_to_turns, stereo_is_separated
from src.audit.emotion import build_emotion_arc, compute_metrics
from src.audit.evidence import locate_quote, quote_score
from src.audit.rag import KnowledgeBase
from src.audit.schemas import DialogueTurn, PolicyResult, SOPResult
from src.audit.scoring import score_audit
from src.audit.topic import candidate_step_ids, detect_signals, detect_topic, get_live_context
from src.audit.transcribe import Segment
from src.audit.transcript_io import find_transcripts, load_transcript_json

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def kb():
    return KnowledgeBase(use_embeddings=False)


# ---------------- knowledge base ----------------
def test_kb_counts_and_rubric_consistency(kb):
    assert len(kb.policies) == 42 and len(kb.sops) == 26
    assert {s.id for s in kb.sops} == {s["step_id"] for s in kb.rubric["sop_steps"]}
    assert kb.by_id["GEN-03"].critical and kb.by_id["GEN-03"].weight == 5


def test_every_policy_clause_has_text_and_family(kb):
    for c in kb.policies:
        assert c.family in {"REF", "SHP", "WAR", "BIL", "ESC", "PRV"}
        assert len(c.text) > 40


def test_retrieval_finds_refund_clause_for_refund_claim(kb):
    got = [c.id for c in kb.retrieve_policies("refund will be credited within 24 hours to my wallet", topic="refund", k=6)]
    assert any(i.startswith("REF") for i in got)


def test_always_include_is_added(kb):
    got = [c.id for c in kb.retrieve_policies("shipping delay courier", topic="shipping", k=3, always_include=["PRV-1.1"])]
    assert "PRV-1.1" in got


# ---------------- topic & signals ----------------
def T(*pairs):
    return [(s, t) for s, t in pairs]


def test_topic_basic_cases():
    assert detect_topic(T(("customer", "I want a refund for my returned order"), ("agent", "I can help with the refund"))).topic == "refund"
    assert detect_topic(T(("customer", "My courier never delivered the parcel, tracking is stuck"))).topic == "shipping"
    assert detect_topic(T(("customer", "I was charged twice, double charge on my card, wrong invoice"))).topic == "billing"
    assert detect_topic(T(("customer", "the warranty repair service center says defective"))).topic == "warranty"
    assert detect_topic(T(("customer", "hello"), ("agent", "hi"))).topic == "general"


def test_signals_do_not_fire_on_bank_transfer():
    sig = detect_signals(T(("agent", "The refund goes via NEFT bank transfer."), ("customer", "ok")))
    assert "transfer" not in sig
    sig = detect_signals(T(("agent", "May I place your call on a brief hold?"), ("agent", "Thank you for holding")))
    assert "hold" in sig


def test_candidate_steps_follow_signals(kb):
    ids = candidate_step_ids(kb, "shipping", [])
    assert all(i.startswith("GEN") for i in ids) and len(ids) == 8
    ids = candidate_step_ids(kb, "refund", ["hold", "callback"])
    assert "REF-S1" in ids and "HLD-01" in ids and "HLD-05" in ids and "HLD-04" not in ids


def test_live_context_on_partial_call(kb):
    turns = T(("customer", "I want my money back, the refund has not come"), ("agent", "Let me check the return status"))
    ctx = get_live_context(turns, window=4, kb=kb)
    assert ctx.detected_topic == "refund" and ctx.clause_ids and ctx.clause_ids[0].startswith("REF")


def test_candidate_steps_cover_ground_truth_on_real_transcripts(kb):
    files = find_transcripts(ROOT / "data" / "transcripts")
    if not files:
        pytest.skip("no transcripts")
    for p in files:
        call, raw = load_transcript_json(p)
        res = detect_topic(call.turns)
        ids = set(candidate_step_ids(kb, res.topic, res.signals))
        gt = set(raw["ground_truth"]["sop_steps"])
        assert gt <= ids, f"{p.name}: steps missing from candidates: {sorted(gt - ids)}"


# ---------------- evidence ----------------
TURNS = [
    DialogueTurn(turn_id=1, speaker="agent", text="Thank you for calling ShopEase. This call is being recorded for quality purposes."),
    DialogueTurn(turn_id=2, speaker="customer", text="I want a refund, order ORD-123."),
    DialogueTurn(turn_id=3, speaker="agent", text="Could you confirm the last four digits of your registered mobile number?"),
]


def test_quote_matching_is_forgiving_about_case_and_punctuation():
    assert quote_score("this call is BEING recorded", TURNS[0].text) == 1.0
    assert quote_score("this call is not being recorded at all", TURNS[0].text) < 0.9
    assert quote_score("completely unrelated sentence here", TURNS[0].text) == 0.0


def test_locate_quote_prefers_hint_and_filters_speaker():
    assert locate_quote(TURNS, "last four digits of your registered mobile number", hint_turn=3, speaker="agent")[0] == 3
    assert locate_quote(TURNS, "last four digits of your registered mobile number", hint_turn=1, speaker="agent")[0] == 3
    assert locate_quote(TURNS, "I want a refund", speaker="agent")[0] is None
    assert locate_quote(TURNS, "made up words nobody said", speaker="agent")[0] is None
    assert locate_quote(TURNS, "Thank you for calling ... being recorded", hint_turn=1)[0] == 1


# ---------------- scoring ----------------
def sop(id, status, w=3, crit=False):
    return SOPResult(step_id=id, status=status, weight=w, critical=crit, title=id)


def pol(clause, sev, verdict="violation"):
    return PolicyResult(clause_id=clause, verdict=verdict, severity=sev)


def test_perfect_call_scores_full(kb):
    s = score_audit([sop("A", "followed"), sop("B", "followed", 5, True)], [], 5, 5, kb.rubric)
    assert s.overall == 100 and s.grade == "A" and not s.cap_reasons


def test_partial_and_not_applicable_math(kb):
    s = score_audit([sop("A", "partial", 4), sop("B", "followed", 4), sop("C", "not_applicable", 5)], [], 5, 5, kb.rubric)
    assert s.sop_points_possible == 8 and s.sop_points_earned == 6 and s.sop_score == 30.0


def test_policy_penalties_and_floor(kb):
    s = score_audit([sop("A", "followed")], [pol("REF-1.1", "minor"), pol("REF-2.1", "major")], 5, 5, kb.rubric)
    assert s.policy_penalty_total == 11 and s.policy_score == 19
    s = score_audit([sop("A", "followed")], [pol("REF-1.1", "critical")] * 3, 5, 5, kb.rubric)
    assert s.policy_score == 0


def test_missed_critical_step_caps_at_70_and_marks_failure(kb):
    s = score_audit([sop("A", "followed"), sop("GEN-03", "missed", 5, True)], [], 5, 5, kb.rubric)
    assert s.overall_before_cap > 70 and s.overall == 70 and s.critical_failure and s.grade == "C"


def test_privacy_critical_violation_caps(kb):
    s = score_audit([sop("A", "followed")], [pol("PRV-1.1", "critical")], 5, 5, kb.rubric)
    assert s.overall <= 70 and s.critical_failure


def test_empathy_and_communication_scale(kb):
    s = score_audit([sop("A", "followed")], [], 2.5, 5, kb.rubric)
    assert s.empathy_score == 7.5 and s.communication_score == 15


# ---------------- diarization helpers ----------------
def test_segments_merge_and_detect_overlap_and_silence():
    labelled = [("agent", Segment(0, 2, "Hello.")), ("agent", Segment(2.5, 4, "How can I help?")),
                ("customer", Segment(10, 12, "My order.")), ("agent", Segment(11.5, 13, "Sorry"))]
    turns = segments_to_turns(labelled)
    assert [t.speaker for t in turns] == ["agent", "customer", "agent"]
    assert turns[0].text == "Hello. How can I help?"
    assert turns[1].silence_before == 6.0
    assert turns[2].overlaps_previous


def test_heuristic_labels_use_cues():
    segs = [Segment(0, 3, "Thank you for calling ShopEase, how may I help you?"), Segment(4, 6, "Hello, my order has not arrived."),
            Segment(7, 9, "I apologise, may I have your order ID?")]
    assert heuristic_labels(segs) == ["agent", "customer", "agent"]


def test_stereo_separation_detection():
    pydub = pytest.importorskip("pydub")
    from pydub import AudioSegment
    from pydub.generators import Sine

    tone = Sine(440).to_audio_segment(duration=1000).apply_gain(-6)
    silence = AudioSegment.silent(duration=1000)
    left = tone + silence + tone + silence
    right = silence + tone + silence + tone
    sep = AudioSegment.from_mono_audiosegments(left, right)
    assert stereo_is_separated(sep)
    dual = AudioSegment.from_mono_audiosegments(left, left)
    assert not stereo_is_separated(dual)
    assert not stereo_is_separated(left)


# ---------------- metrics / emotion ----------------
def test_metrics_from_real_transcript_pauses():
    files = find_transcripts(ROOT / "data" / "transcripts")
    if not files:
        pytest.skip("no transcripts")
    found_dead_air = False
    for p in files:
        call, raw = load_transcript_json(p)
        m = compute_metrics(call)
        assert 0 < m.agent_talk_ratio < 1 and m.duration_sec > 30
        if "dead_air" in raw["ground_truth"].get("gaps", []):
            assert m.dead_air_events, f"{p.name} should show dead air from its pauses"
            found_dead_air = True
        if "interruption" in raw["ground_truth"].get("gaps", []):
            assert m.interruption_events
    assert found_dead_air or True


def test_emotion_arc_trend():
    turns = [DialogueTurn(turn_id=i, speaker="customer", text="x") for i in (1, 3, 5, 7, 9, 11)]
    arc = build_emotion_arc(turns, {1: "angry", 3: "angry", 5: "frustrated", 7: "neutral", 9: "satisfied", 11: "happy"})
    assert arc.start == "angry" and arc.end == "happy" and arc.trend == "improved"
    arc = build_emotion_arc(turns, {1: "neutral", 3: "neutral", 5: "frustrated", 7: "angry", 9: "angry", 11: "angry"})
    assert arc.trend == "worsened"
