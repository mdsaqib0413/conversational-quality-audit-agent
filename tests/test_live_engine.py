"""Unit tests for Live Assist real-time engine, rules, deduplication, and streaming."""

import json
from pathlib import Path

import numpy as np
import pytest

from src.live.engine import LiveSession, dedupe_word_overlap
from src.live.rules import LiveRuleEngine
from src.live.schemas import LiveTurn

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def _make_turns_from_transcript(call_id: str) -> list[LiveTurn]:
    path = DATA_DIR / "transcripts" / f"{call_id}.json"
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    turns = []
    t = 0.0
    for idx, raw in enumerate(data.get("turns", [])):
        spk = raw["speaker"]
        txt = raw["text"]
        dur = max(2.0, len(txt.split()) * 0.35)
        turns.append(LiveTurn(speaker=spk, start=t, end=t + dur, text=txt, partial=False, turn_id=idx + 1))
        t += dur + raw.get("pause_before_sec", 0.5)
    return turns


# -------------------------------------------------------------------------
# A. Rule Alert Unit Tests
# -------------------------------------------------------------------------

def test_each_alert_fires_on_crafted_turn_list():
    eng = LiveRuleEngine()

    # 1. Recording disclosure missing
    t1 = [
        LiveTurn("agent", 0.0, 3.0, "Hello welcome to customer service.", False, 1),
        LiveTurn("customer", 3.5, 6.0, "Hi I need some help.", False, 2),
        LiveTurn("agent", 6.5, 9.0, "Sure what can I do for you?", False, 3),
    ]
    alerts = eng.evaluate_alerts(t1, 10.0, 0.5, 0.0)
    assert any(a.rule_id == "recording_disclosure_missing" for a in alerts)

    # 2. Address revealed before verification
    eng.reset()
    t2 = [
        LiveTurn("agent", 0.0, 3.0, "Thanks for calling ShopEase call is recorded. How can I help?", False, 1),
        LiveTurn("customer", 3.5, 6.0, "I want to check my order status.", False, 2),
        LiveTurn("agent", 6.5, 10.0, "I see your parcel delivered to Flat 104, Green Glen Residency, Pune.", False, 3),
    ]
    alerts = eng.evaluate_alerts(t2, 12.0, 0.5, 0.0)
    assert any(a.rule_id == "address_before_verification" for a in alerts)

    # 3. Refund limit self approval > Rs 5,000
    eng.reset()
    t3 = [
        LiveTurn("customer", 0.0, 3.0, "My watch was Rs 8,500.", False, 1),
        LiveTurn("agent", 3.5, 7.0, "The refund of Rs 8,500 is approved by me, no supervisor is needed.", False, 2),
    ]
    alerts = eng.evaluate_alerts(t3, 10.0, 0.5, 0.0)
    assert any(a.rule_id == "refund_limit_self_approval" for a in alerts)

    # 4. Refund to wallet
    eng.reset()
    t4 = [
        LiveTurn("customer", 0.0, 3.0, "How will I receive the refund?", False, 1),
        LiveTurn("agent", 3.5, 7.0, "I will send the refund to your Paytm wallet right now.", False, 2),
    ]
    alerts = eng.evaluate_alerts(t4, 10.0, 0.5, 0.0)
    assert any(a.rule_id == "refund_wallet_destination" for a in alerts)

    # 5. Refund timeline 24 hours
    eng.reset()
    t5 = [
        LiveTurn("customer", 0.0, 3.0, "When will the money arrive?", False, 1),
        LiveTurn("agent", 3.5, 7.0, "The refund will be credited within 24 hours.", False, 2),
    ]
    alerts = eng.evaluate_alerts(t5, 10.0, 0.5, 0.0)
    assert any(a.rule_id == "refund_timeline_24h" for a in alerts)

    # 6. Keep item without return
    eng.reset()
    t6 = [
        LiveTurn("agent", 0.0, 4.0, "You can keep the watch, no need to send it back.", False, 1),
    ]
    alerts = eng.evaluate_alerts(t6, 5.0, 0.5, 0.0)
    assert any(a.rule_id == "keep_item_no_return" for a in alerts)

    # 7. Scam cue (AnyDesk / OTP)
    eng.reset()
    t7 = [
        LiveTurn("agent", 0.0, 4.0, "Please install AnyDesk and read me the OTP.", False, 1),
    ]
    alerts = eng.evaluate_alerts(t7, 5.0, 0.5, 0.0)
    assert any(a.rule_id == "scam_cue_detected" for a in alerts)

    # 8. Customer frustration
    eng.reset()
    t8 = [
        LiveTurn("customer", 0.0, 4.0, "This service is completely unacceptable and ridiculous!", False, 1),
    ]
    alerts = eng.evaluate_alerts(t8, 5.0, 0.5, 0.0)
    assert any(a.rule_id == "customer_frustration" for a in alerts)

    # 9. Prolonged silence > 8s
    eng.reset()
    t9 = [
        LiveTurn("customer", 0.0, 2.0, "Hello?", False, 1),
    ]
    alerts = eng.evaluate_alerts(t9, 15.0, 0.5, 9.2)
    assert any(a.rule_id == "prolonged_silence" for a in alerts)

    # 10. Agent talk share > 75%
    eng.reset()
    alerts = eng.evaluate_alerts(t9, 40.0, 0.82, 0.0)
    assert any(a.rule_id == "agent_talk_dominance" for a in alerts)


def test_call_101_clean_case_no_alerts():
    """Call 101 is the clean compliant interaction: zero alerts must fire."""
    eng = LiveRuleEngine()
    turns = _make_turns_from_transcript("call_101")
    agent_sec = sum(t.end - t.start for t in turns if t.speaker == "agent")
    cust_sec = sum(t.end - t.start for t in turns if t.speaker == "customer")
    share = agent_sec / (agent_sec + cust_sec)
    dur = turns[-1].end if turns else 100.0

    alerts = eng.evaluate_alerts(turns, dur, share, 0.0)
    assert len(alerts) == 0, f"Expected 0 alerts for clean call_101, got: {[a.rule_id for a in alerts]}"


def test_call_102_expected_alerts():
    """Call 102 exhibits severe compliance violations across authorization, verification, and SLAs."""
    eng = LiveRuleEngine()
    turns = _make_turns_from_transcript("call_102")
    agent_sec = sum(t.end - t.start for t in turns if t.speaker == "agent")
    cust_sec = sum(t.end - t.start for t in turns if t.speaker == "customer")
    share = agent_sec / (agent_sec + cust_sec)
    dur = turns[-1].end if turns else 100.0

    alerts = eng.evaluate_alerts(turns, dur, share, 0.0)
    fired_ids = {a.rule_id for a in alerts}

    expected_rules = {
        "address_before_verification",
        "refund_limit_self_approval",
        "refund_wallet_destination",
        "refund_timeline_24h",
        "keep_item_no_return",
    }
    for r in expected_rules:
        assert r in fired_ids, f"Expected alert '{r}' to fire for call_102, but fired: {fired_ids}"


# -------------------------------------------------------------------------
# B. SOP Progress on Call 101
# -------------------------------------------------------------------------

def test_sop_progress_on_call_101():
    eng = LiveRuleEngine()
    turns = _make_turns_from_transcript("call_101")
    checklist, next_step = eng.evaluate_sop_progress("refund", turns)

    assert len(checklist) > 0
    done_ids = {s.step_id for s in checklist if s.status == "done"}

    # Greeting, disclosure, verification, and refund steps must be marked done
    assert "GEN-01" in done_ids
    assert "GEN-02" in done_ids
    assert "GEN-03" in done_ids
    assert any(sid.startswith("REF-") for sid in done_ids)


# -------------------------------------------------------------------------
# C. Chunk Merge & Overlap Deduplication
# -------------------------------------------------------------------------

def test_dedupe_word_overlap():
    prev = "Thank you for calling ShopEase customer support"
    next_chunk = "customer support my name is Sneha"
    deduped = dedupe_word_overlap(prev, next_chunk)
    assert deduped == "my name is Sneha"

    # No overlap
    assert dedupe_word_overlap("Hello how are you", "I need help with my order") == "I need help with my order"

    # Empty inputs
    assert dedupe_word_overlap("", "some text") == "some text"
    assert dedupe_word_overlap("some text", "") == ""


def test_session_chunk_merge():
    session = LiveSession()
    # First chunk
    session._merge_turn("agent", "Thank you for calling ShopEase", 0.0, 2.0)
    assert len(session.turns) == 1
    assert session.turns[0].partial is True

    # Overlapping second chunk from same speaker shortly after
    session._merge_turn("agent", "calling ShopEase my name is Rahul", 1.8, 3.8)
    assert len(session.turns) == 1
    assert "Rahul" in session.turns[0].text
    assert session.turns[0].end == 3.8

    # Turn from customer starts new turn and closes agent turn
    session._merge_turn("customer", "Hi Rahul I have an issue", 4.2, 6.0)
    assert len(session.turns) == 2
    assert session.turns[0].partial is False
    assert session.turns[1].speaker == "customer"


# -------------------------------------------------------------------------
# D. LiveSession with Fake PCM and Stub Transcriber
# -------------------------------------------------------------------------

def test_session_with_fake_pcm_and_stub_transcriber():
    call_count = [0]

    def mock_transcriber(samples: np.ndarray) -> str:
        call_count[0] += 1
        return f"Turn chunk number {call_count[0]}"

    session = LiveSession(
        chunk_duration_sec=0.2,
        overlap_sec=0.05,
        transcriber_fn=mock_transcriber,
    )
    session.start()

    # Feed 1 second of fake 16kHz 16-bit PCM (32,000 bytes)
    fake_pcm = b"\x00" * 32000
    session.push_audio("agent", fake_pcm, 0.0)

    import time
    time.sleep(0.4)

    snap = session.get_snapshot()
    assert snap.status == "running"
    assert len(snap.turns) > 0
    assert "Turn chunk" in snap.turns[0].text

    session.stop()
    final_snap = session.get_snapshot()
    assert final_snap.status == "stopped"
