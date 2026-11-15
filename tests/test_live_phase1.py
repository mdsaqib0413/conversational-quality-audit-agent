"""Tests for Phase 1 live tracking: CaptionEvent, CallSimulator, and LiveRules."""
from __future__ import annotations

from pathlib import Path
import pytest

from src.audit.live import CallSimulator, CaptionEvent, LiveRules, replay_call

ROOT = Path(__file__).resolve().parent.parent


def test_replaying_call_105_raises_hld02_alert_at_right_time():
    """Verify that replaying call_105 raises the HLD-02 hold alert at the exact ceiling timestamp."""
    transcript_path = ROOT / "data" / "transcripts" / "call_105.json"
    if not transcript_path.exists():
        pytest.skip("call_105 transcript not found")

    sim = CallSimulator(transcript_path)
    events = sim.build_events()
    assert len(events) > 0

    # In call_105, customer agrees to hold at turn 14 (end_time = 162.41s) and agent returns at turn 15 (start_time = 237.41s).
    # Total hold is 75 seconds. Under a 60s hold ceiling, HLD-02 fires at exactly 162.41 + 60.0 = 222.41s.
    rules = LiveRules(config={"max_hold_seconds": 60.0})
    fired_alerts = []
    for ev in events:
        alerts = rules.process_event(ev)
        fired_alerts.extend(alerts)

    hld_alerts = [a for a in fired_alerts if a.rule_id == "HLD-02"]
    assert len(hld_alerts) == 1, f"Expected exactly 1 HLD-02 alert, found {len(hld_alerts)}"
    alert = hld_alerts[0]
    assert alert.severity == "danger"
    assert alert.related_step_or_clause == "HLD-02"
    assert alert.time_sec == pytest.approx(222.41, abs=0.1)
    assert alert.time == pytest.approx(222.41, abs=0.1)
    assert "exceeding maximum" in alert.message

    # Also verify that with default 120s ceiling, call_106 (135s hold) raises HLD-02 at 108.87 + 120 = 228.87s
    call_106_path = ROOT / "data" / "transcripts" / "call_106.json"
    if call_106_path.exists():
        sim_106 = CallSimulator(call_106_path)
        rules_106 = LiveRules()  # default 120s
        alerts_106 = [a for e in sim_106.build_events() for a in rules_106.process_event(e) if a.rule_id == "HLD-02"]
        assert len(alerts_106) == 1
        assert alerts_106[0].time_sec == pytest.approx(228.87, abs=0.1)


def test_compliant_opening_raises_no_gen02_alert():
    """Verify that a call with a compliant recording disclosure in the opening raises no GEN-02 alert."""
    for cid in ("call_001", "call_101", "call_105"):
        transcript_path = ROOT / "data" / "transcripts" / f"{cid}.json"
        if not transcript_path.exists():
            continue

        sim = CallSimulator(transcript_path)
        rules = LiveRules()
        alerts = [a for ev in sim.build_events() for a in rules.process_event(ev)]

        gen02_alerts = [a for a in alerts if a.rule_id == "GEN-02"]
        assert len(gen02_alerts) == 0, f"{cid} has compliant opening but raised GEN-02: {gen02_alerts}"
        assert rules.recording_disclosed is True
        chk = rules.get_checklist_status()
        assert chk["disclosure"]["status"] == "completed"

    # In contrast, call_102 omits disclosure in opening: GEN-02 must be raised
    p102 = ROOT / "data" / "transcripts" / "call_102.json"
    if p102.exists():
        sim_102 = CallSimulator(p102)
        rules_102 = LiveRules()
        alerts_102 = [a for ev in sim_102.build_events() for a in rules_102.process_event(ev)]
        gen02_102 = [a for a in alerts_102 if a.rule_id == "GEN-02"]
        assert len(gen02_102) == 1
        assert gen02_102[0].severity == "danger"
        assert rules_102.get_checklist_status()["disclosure"]["status"] == "missed"


def test_alert_deduplication():
    """Verify that each alert condition fires once with no duplicate alerts."""
    rules = LiveRules(config={"disclosure_max_agent_turns": 1, "empathy_window_turns": 1})

    # Event 1: Agent speaks without recording disclosure
    ev1 = CaptionEvent("c1", "agent_0", "agent", "Hello, how can I help you?", 0, 2000, final=True, turn_id=1)
    a1 = rules.process_event(ev1)
    assert any(a.rule_id == "GEN-02" for a in a1)

    # Event 2: Agent speaks again without disclosure — GEN-02 must not duplicate
    ev2 = CaptionEvent("c1", "agent_0", "agent", "I am still waiting for your question.", 2500, 4500, final=True, turn_id=2)
    a2 = rules.process_event(ev2)
    assert not any(a.rule_id == "GEN-02" for a in a2)

    # Event 3: Agent repeatedly discloses unverified account details
    ev3 = CaptionEvent("c1", "agent_0", "agent", "Your delivery address is Flat 101, residency tower.", 5000, 8000, final=True, turn_id=3)
    a3 = rules.process_event(ev3)
    assert any(a.rule_id == "GEN-03" for a in a3)

    ev4 = CaptionEvent("c1", "agent_0", "agent", "Also the package was delivered to pincode 560001.", 8500, 11000, final=True, turn_id=4)
    a4 = rules.process_event(ev4)
    assert not any(a.rule_id == "GEN-03" for a in a4)

    # Total counts in rules.alerts
    gen02_all = [a for a in rules.alerts if a.rule_id == "GEN-02"]
    gen03_all = [a for a in rules.alerts if a.rule_id == "GEN-03"]
    assert len(gen02_all) == 1
    assert len(gen03_all) == 1


def test_rules_ignore_interim_events():
    """Verify that interim (non-final) events are ignored by LiveRules."""
    rules = LiveRules()

    # Interim event containing breach phrase
    interim_ev = CaptionEvent(
        call_id="c_interim",
        peer_id="agent_0",
        role="agent",
        text="Your order address is flat 102 residency street",
        start_ms=0,
        end_ms=1500,
        final=False,
        turn_id=1,
    )
    alerts = rules.process_event(interim_ev)
    assert alerts == []
    assert len(rules.alerts) == 0
    assert len(rules.events) == 0

    # Another interim event with hold request
    interim_ev2 = CaptionEvent(
        call_id="c_interim",
        peer_id="agent_0",
        role="agent",
        text="Please hold on the line",
        start_ms=1600,
        end_ms=2500,
        final=False,
        turn_id=1,
    )
    alerts2 = rules.process_event(interim_ev2)
    assert alerts2 == []
    assert not rules.on_hold


def test_simulator_interim_events_generation():
    """Verify that CallSimulator generates interim events when emit_interim=True."""
    sim_no_interim = CallSimulator(ROOT / "data" / "transcripts" / "call_001.json", emit_interim=False)
    events_no_interim = sim_no_interim.build_events()
    assert all(e.final is True for e in events_no_interim)

    sim_interim = CallSimulator(ROOT / "data" / "transcripts" / "call_001.json", emit_interim=True)
    events_interim = sim_interim.build_events()
    assert len(events_interim) > len(events_no_interim)
    assert any(e.final is False for e in events_interim)
    assert any(e.final is True for e in events_interim)
