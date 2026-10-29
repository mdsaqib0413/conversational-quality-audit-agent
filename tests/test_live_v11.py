"""Live Assist v1.1 test suite.

Covers:
- Topic stability on call_102 and call_001
- EOF finalization (no partial turns left)
- Pinned alert clauses with Triggered tag
- Number-form dedupe
- Speaker-restricted rules (agent vs customer)
- Regression table harness (slow marker)
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import List

import numpy as np
import pytest

from src.live.analysis import compute_cumulative_topic, run_live_analysis
from src.live.engine import (
    LiveSession,
    collapse_immediate_repeats,
    dedupe_word_overlap,
    normalize_spoken_numbers,
)
from src.live.rules import LiveRuleEngine
from src.live.schemas import LiveAlert, LiveTurn

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
TRANSCRIPTS_DIR = DATA_DIR / "transcripts"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_turns(call_id: str) -> List[LiveTurn]:
    path = TRANSCRIPTS_DIR / f"{call_id}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    turns: List[LiveTurn] = []
    t = 0.0
    for idx, raw in enumerate(data.get("turns", [])):
        spk = raw["speaker"]
        txt = raw["text"]
        dur = max(2.0, len(txt.split()) * 0.35)
        turns.append(LiveTurn(speaker=spk, start=t, end=t + dur, text=txt, partial=False, turn_id=idx + 1))
        t += dur + raw.get("pause_before_sec", 0.5)
    return turns


def _run_alerts(call_id: str):
    eng = LiveRuleEngine()
    turns = _load_turns(call_id)
    agent_sec = sum(t.end - t.start for t in turns if t.speaker == "agent")
    cust_sec = sum(t.end - t.start for t in turns if t.speaker == "customer")
    share = agent_sec / (agent_sec + cust_sec) if (agent_sec + cust_sec) > 0 else 0.5
    dur = turns[-1].end if turns else 0.0
    alerts = eng.evaluate_alerts(turns, dur, share, 0.0)
    return turns, alerts


# ---------------------------------------------------------------------------
# 1. Topic stability: call_102 and call_001
# ---------------------------------------------------------------------------

def test_topic_call_102_refund_early_and_stable():
    """call_102 must show refund within first 3 turns and keep it to the end."""
    turns = _load_turns("call_102")
    assert turns, "call_102 has no turns"

    first_3 = turns[:3]
    topic_early, _, _, _ = compute_cumulative_topic(first_3, alerts=None, prev_topic="general")
    assert topic_early == "refund", (
        f"Expected refund from first 3 turns of call_102, got {topic_early!r}"
    )

    topic_all, conf_all, _, _ = compute_cumulative_topic(turns, alerts=None, prev_topic="refund")
    assert topic_all == "refund", f"Topic drifted from refund at end of call_102: {topic_all!r}"
    assert conf_all >= 0.55, f"Confidence too low: {conf_all}"


def test_topic_call_001_refund_early_and_stable():
    """call_001 must show refund within first 3 turns and keep it to the end."""
    turns = _load_turns("call_001")
    assert turns, "call_001 has no turns"

    first_3 = turns[:3]
    topic_early, _, _, _ = compute_cumulative_topic(first_3, alerts=None, prev_topic="general")
    assert topic_early == "refund", (
        f"Expected refund from first 3 turns of call_001, got {topic_early!r}"
    )

    topic_all, conf_all, _, _ = compute_cumulative_topic(turns, alerts=None, prev_topic="refund")
    assert topic_all == "refund", f"Topic drifted from refund at end of call_001: {topic_all!r}"
    assert conf_all >= 0.55


# ---------------------------------------------------------------------------
# 2. EOF finalization: no partial turns remain
# ---------------------------------------------------------------------------

def test_eof_finalization_no_partial_turns():
    """flush_and_end must clear all partial flags."""
    transcribed = ["Hello welcome to ShopEase.", "I need to return my item please."]
    idx = [0]

    def mock_transcriber(samples):
        result = transcribed[idx[0] % len(transcribed)]
        idx[0] += 1
        return result

    session = LiveSession(
        chunk_duration_sec=0.2,
        overlap_sec=0.05,
        transcriber_fn=mock_transcriber,
    )
    session.start()

    fake_pcm = b"\x00" * 32000
    session.push_audio("agent", fake_pcm, 0.0)
    session.push_audio("customer", fake_pcm, 0.0)

    time.sleep(0.5)
    session.flush_and_end()

    snap = session.get_snapshot()
    assert snap.status == "ended"
    for turn in snap.turns:
        assert not turn.partial, f"Turn #{turn.turn_id} still partial after flush_and_end"


# ---------------------------------------------------------------------------
# 3. Pinned alert clauses with Triggered tag
# ---------------------------------------------------------------------------

def test_pinned_alert_clauses_have_triggered_tag():
    """Fired alerts must appear as pinned LiveClause entries with tag=Triggered."""
    eng = LiveRuleEngine()
    turns = [
        LiveTurn("agent", 0.0, 3.0,
                 "Thanks for calling ShopEase, this call is recorded for quality purposes.", False, 1),
        LiveTurn("customer", 3.5, 6.0, "I need a refund on my order.", False, 2),
        LiveTurn("agent", 6.5, 10.0, "I will send the refund to your Paytm wallet.", False, 3),
        LiveTurn("agent", 11.0, 14.0, "Please install AnyDesk and share your OTP.", False, 4),
    ]
    accumulated: List[LiveAlert] = []
    snap = run_live_analysis(
        turns=turns,
        duration_sec=15.0,
        last_silence_sec=0.0,
        rule_engine=eng,
        accumulated_alerts=accumulated,
        stereo_exact=True,
        status="running",
    )
    triggered = [c for c in snap.top_clauses if c.tag == "Triggered"]
    assert len(triggered) >= 1, "Expected at least 1 Triggered clause"
    for tc in triggered:
        assert tc.alert_time, f"Triggered clause {tc.id} missing alert_time"


# ---------------------------------------------------------------------------
# 4. Number-form dedupe
# ---------------------------------------------------------------------------

def test_normalize_spoken_numbers():
    assert normalize_spoken_numbers("eight thousand five hundred") == "8500"
    assert normalize_spoken_numbers("two thousand") == "2000"
    assert normalize_spoken_numbers("five") == "5"
    assert "ShopEase" in normalize_spoken_numbers("Welcome to ShopEase")


def test_collapse_immediate_repeats_number():
    result = collapse_immediate_repeats("eight thousand 8500")
    assert "8500" in result
    assert result.count("8500") == 1


def test_dedupe_word_overlap_spoken_numbers():
    prev = "refund of eight thousand five hundred rupees"
    nxt = "five hundred rupees will be credited"
    deduped = dedupe_word_overlap(prev, nxt)
    assert deduped.startswith("will"), f"Unexpected dedup result: {deduped!r}"


# ---------------------------------------------------------------------------
# 5. Speaker-restricted rules
# ---------------------------------------------------------------------------

def test_speaker_restriction_frustration_only_customer():
    """customer_frustration must NOT fire when frustration words are in agent speech."""
    eng = LiveRuleEngine()
    turns = [
        LiveTurn("agent", 0.0, 3.0,
                 "Thanks for calling ShopEase, this call is recorded for quality.", False, 1),
        LiveTurn("agent", 3.5, 7.0,
                 "I understand this is completely unacceptable and ridiculous.", False, 2),
    ]
    alerts = eng.evaluate_alerts(turns, 10.0, 0.8, 0.0)
    fired = {a.rule_id for a in alerts}
    assert "customer_frustration" not in fired, (
        "customer_frustration should not fire for agent speech"
    )


def test_speaker_restriction_frustration_fires_for_customer():
    """customer_frustration MUST fire when frustration is in customer speech."""
    eng = LiveRuleEngine()
    turns = [
        LiveTurn("agent", 0.0, 3.0,
                 "Thanks for calling ShopEase, this call is recorded for quality.", False, 1),
        LiveTurn("customer", 3.5, 7.0,
                 "This is completely unacceptable and ridiculous!", False, 2),
    ]
    alerts = eng.evaluate_alerts(turns, 10.0, 0.5, 0.0)
    fired = {a.rule_id for a in alerts}
    assert "customer_frustration" in fired


def test_speaker_restriction_refund_timeline_only_agent():
    """refund_timeline_24h must NOT fire from customer speech."""
    eng = LiveRuleEngine()
    turns = [
        LiveTurn("agent", 0.0, 3.0,
                 "Thanks for calling ShopEase, this call is recorded.", False, 1),
        LiveTurn("customer", 3.5, 7.0,
                 "The refund will be credited within 24 hours right?", False, 2),
    ]
    alerts = eng.evaluate_alerts(turns, 10.0, 0.4, 0.0)
    fired = {a.rule_id for a in alerts}
    assert "refund_timeline_24h" not in fired, (
        "refund_timeline_24h should not fire from customer speech"
    )


def test_speaker_restriction_keep_item_only_agent():
    """keep_item_no_return must NOT fire from customer speech."""
    eng = LiveRuleEngine()
    turns = [
        LiveTurn("agent", 0.0, 3.0,
                 "Thanks for calling ShopEase, this call is recorded.", False, 1),
        LiveTurn("customer", 3.5, 7.0,
                 "Can I keep the item and still get a refund?", False, 2),
    ]
    alerts = eng.evaluate_alerts(turns, 10.0, 0.4, 0.0)
    fired = {a.rule_id for a in alerts}
    assert "keep_item_no_return" not in fired, (
        "keep_item_no_return should not fire from customer speech"
    )


# ---------------------------------------------------------------------------
# 6. Regression table harness
# ---------------------------------------------------------------------------

@pytest.mark.slow
def test_regression_table():
    """Text-only regression over all labelled transcripts from data/expected; prints TP/FP/FN table."""
    expected_path = DATA_DIR / "expected" / "expected_results.json"
    assert expected_path.exists(), f"Missing {expected_path}"
    expected_data = json.loads(expected_path.read_text(encoding="utf-8"))

    results = []
    total_tp = total_fp = total_fn = 0

    for call_id, info in expected_data.items():
        transcript_path = TRANSCRIPTS_DIR / f"{call_id}.json"
        if not transcript_path.exists():
            continue

        turns, alerts = _run_alerts(call_id)
        fired_clauses = {a.clause_id for a in alerts if a.clause_id and a.severity in ("danger", "warning")}
        expected_clauses = {v["clause"] for v in info.get("violations", [])}

        tp = len(fired_clauses & expected_clauses)
        fp = len(fired_clauses - expected_clauses)
        fn = len(expected_clauses - fired_clauses)
        total_tp += tp
        total_fp += fp
        total_fn += fn
        results.append((call_id, fired_clauses, expected_clauses, tp, fp, fn, alerts))

    print("\n\nLive Rule Regression Table (All Labelled Calls)")
    print(f"{'Call':<10} {'Fired Clauses':<40} {'Expected Clauses':<40} {'TP':>3} {'FP':>3} {'FN':>3}")
    print("-" * 105)
    for call_id, fired, expected, tp, fp, fn, _ in results:
        fired_str = ", ".join(sorted(fired)) or "(none)"
        exp_str = ", ".join(sorted(expected)) or "(none)"
        print(f"{call_id:<10} {fired_str:<40} {exp_str:<40} {tp:>3} {fp:>3} {fn:>3}")

    precision = total_tp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else 1.0
    recall = total_tp / (total_tp + total_fn) if (total_tp + total_fn) > 0 else 1.0
    print(f"\nOverall  TP={total_tp}  FP={total_fp}  FN={total_fn}  "
          f"Precision={precision:.1%}  Recall={recall:.1%}")

    # Clean calls (call_001, call_009, call_101, call_103, call_105, call_108) must raise no serious alerts
    for call_id, fired, expected, tp, fp, fn, alerts in results:
        if not expected:
            serious_alerts = [a for a in alerts if a.severity == "danger"]
            assert len(serious_alerts) == 0, f"Clean call {call_id} raised serious alerts: {serious_alerts}"
