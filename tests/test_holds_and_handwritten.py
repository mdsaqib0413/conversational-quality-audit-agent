"""Hold handling in timing metrics, complaint-vs-anger signals, and the hand-written calls."""
import json
from pathlib import Path

import pytest

from src.audit.emotion import compute_metrics
from src.audit.rag import KnowledgeBase
from src.audit.topic import detect_signals, detect_topic
from src.audit.transcript_io import load_transcript_json

ROOT = Path(__file__).resolve().parent.parent
KB = KnowledgeBase(use_embeddings=False)


def load(cid):
    p = ROOT / "data" / "transcripts" / f"{cid}.json"
    if not p.exists():
        pytest.skip(f"{cid} not present")
    return load_transcript_json(p)


def test_a_normal_hold_is_not_dead_air():
    call, _ = load("call_105")  # 75 s hold, back within the 2-minute limit
    m = compute_metrics(call)
    assert not m.dead_air_events and not m.hold_events


def test_a_hold_beyond_two_minutes_is_flagged_not_called_dead_air():
    call, raw = load("call_106")  # 135 s hold
    m = compute_metrics(call)
    assert not m.dead_air_events
    assert len(m.hold_events) == 1 and m.hold_events[0].gap_type == "hold_too_long" and "135" in m.hold_events[0].detail
    assert "hold_too_long" in raw["ground_truth"]["gaps"]


def test_silence_without_a_hold_is_still_dead_air():
    call, _ = load("call_009")
    assert compute_metrics(call).dead_air_events


def test_the_word_complaint_is_not_an_angry_caller():
    assert "angry_customer" not in detect_signals([("customer", "Please just note my complaint about the double charge.")])
    assert "angry_customer" in detect_signals([("customer", "This is unacceptable, I am fed up.")])


def test_agent_interruption_in_the_bad_complaint_call():
    call, _ = load("call_106")
    m = compute_metrics(call)
    assert m.agent_interruptions == 1


@pytest.mark.parametrize("cid,expected", [("call_101", "refund"), ("call_102", "refund"), ("call_103", "billing"), ("call_104", "billing"),
                                          ("call_107", "warranty"), ("call_108", "shipping")])
def test_topic_on_handwritten_calls(cid, expected):
    call, _ = load(cid)
    assert detect_topic(call.turns).topic == expected


def test_bad_calls_really_are_bad_and_good_calls_clean():
    for cid in ("call_102", "call_104", "call_106", "call_107"):
        _, raw = load(cid)
        gt = raw["ground_truth"]
        crit_missed = [s for s, st in gt["sop_steps"].items() if st == "missed" and KB.by_id[s].critical]
        assert raw["quality"] == "bad_deviation" and crit_missed and gt["policy_violations"], cid
    for cid in ("call_101", "call_103", "call_105", "call_108"):
        _, raw = load(cid)
        assert raw["quality"] == "good" and not raw["ground_truth"]["policy_violations"]
