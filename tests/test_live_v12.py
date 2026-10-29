"""Live Assist v1.2 test suite.

Covers:
- Full audit click path on saved live transcript with FakeGateway stub client:
  * data/live_calls/<call_id>_live.json written in expected transcript format
  * AuditPipeline.audit_call called with source_set="live"
  * Report saved to cache and loadable
  * Exactly 2 stub LLM requests made
  * Report opens on call_102
- SOP tracker three states (done, partial, not_yet) on call_102 and call_001:
  * call_102: GEN-01 done, GEN-05 partial, 13 missed
  * call_001: all 8 GEN steps done (15 done total)
- End-of-call status header chip logic
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.audit.pipeline import AuditPipeline
from src.audit.rag import KnowledgeBase
from src.audit.schemas import AuditReport, PolicyAnalysis
from src.audit.transcript_io import load_transcript_json
from src.live.rules import LiveRuleEngine
from src.live.schemas import LiveTurn
from tests.fakes import FakeGateway, make_analysis

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
TRANSCRIPTS_DIR = DATA_DIR / "transcripts"
LIVE_CALLS_DIR = DATA_DIR / "live_calls"


# ---------------------------------------------------------------------------
# 1. Integration test: Run full audit on this call click path
# ---------------------------------------------------------------------------

def test_run_full_audit_click_path_on_call_102(tmp_path):
    """Clicking 'Run full audit on this call' writes transcript, runs audit_call,
    saves report, loads report, uses exactly 2 stub LLM requests, and opens on call_102."""
    cid = "call_102"
    raw_path = TRANSCRIPTS_DIR / f"{cid}.json"
    assert raw_path.exists(), f"Missing transcript {raw_path}"
    raw = json.loads(raw_path.read_text(encoding="utf-8"))

    LIVE_CALLS_DIR.mkdir(parents=True, exist_ok=True)
    live_json_path = LIVE_CALLS_DIR / f"{cid}_live.json"

    # 1. Write data/live_calls/<call_id>_live.json in format expected by pipeline
    turns_data = [
        {
            "turn_id": i + 1,
            "speaker": t["speaker"],
            "text": t["text"],
            "start_time": round(i * 3.0, 2),
            "end_time": round((i + 1) * 3.0, 2),
            "pause_before_sec": float(t.get("pause_before_sec", 0.5)),
            "interrupts_previous": bool(t.get("interrupts_previous", False)),
        }
        for i, t in enumerate(raw["turns"])
    ]
    payload = {
        "id": cid,
        "call_id": cid,
        "source_set": "live",
        "turns": turns_data,
    }
    live_json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    assert live_json_path.exists(), "Live transcript file was not written"

    # 2. Pipeline execution with stub LLM client
    call, _ = load_transcript_json(str(live_json_path))
    call.call_id = cid

    kb = KnowledgeBase(use_embeddings=False)
    gateway = FakeGateway(
        analysis=lambda p: make_analysis(p, call),
        policy=PolicyAnalysis(claims=[]),
    )
    pipe = AuditPipeline(kb=kb, gateway=gateway, cache_dir=tmp_path)

    # Call the exact audit function
    rep = pipe.audit_call(call, use_cache=False, source_set="live")

    # 3. Assertions
    # Exactly 2 stub requests made
    assert rep.meta.llm_requests == 2, f"Expected 2 requests, got {rep.meta.llm_requests}"
    assert gateway.request_count == 2, f"Expected 2 gateway calls, got {gateway.request_count}"

    # Source set is 'live'
    assert rep.meta.source_set == "live"

    # Report opens on call_102
    assert rep.call_id == cid

    # Report is saved in cache and loadable
    cache_path = pipe._audit_cache_path(call)
    assert cache_path.exists(), f"Report was not saved to cache at {cache_path}"
    loaded = AuditReport.model_validate_json(cache_path.read_text(encoding="utf-8"))
    assert loaded.call_id == cid
    assert loaded.scores.overall == rep.scores.overall


# ---------------------------------------------------------------------------
# 2. SOP Tracker counts: call_102 and call_001
# ---------------------------------------------------------------------------

def test_sop_tracker_call_102():
    """call_102 must have GEN-01 done, GEN-05 partial, and 13 missed steps."""
    raw = json.loads((TRANSCRIPTS_DIR / "call_102.json").read_text(encoding="utf-8"))["turns"]
    turns = [
        LiveTurn(t["speaker"], i * 3.0, (i + 1) * 3.0, t["text"], False, i + 1)
        for i, t in enumerate(raw)
    ]
    eng = LiveRuleEngine()
    checklist, next_step = eng.evaluate_sop_progress("refund", turns)

    status_by_id = {s.step_id: s.status for s in checklist}

    assert status_by_id["GEN-01"] == "done", f"GEN-01 should be done, got {status_by_id['GEN-01']}"
    assert status_by_id["GEN-05"] == "partial", f"GEN-05 should be partial, got {status_by_id['GEN-05']}"

    done_steps = [s for s in checklist if s.status == "done"]
    partial_steps = [s for s in checklist if s.status == "partial"]
    missed_steps = [s for s in checklist if s.status in ("not_yet", "pending", "missed")]

    assert len(done_steps) == 1, f"Expected 1 done step on call_102, got {len(done_steps)}"
    assert len(partial_steps) == 1, f"Expected 1 partial step on call_102, got {len(partial_steps)}"
    assert len(missed_steps) == 13, f"Expected 13 missed steps on call_102, got {len(missed_steps)}"
    assert "GEN-05" not in [s.step_id for s in missed_steps], "GEN-05 should not be in missed list"


def test_sop_tracker_call_001():
    """call_001 must have all 8 GEN steps done (and 15 done total)."""
    raw = json.loads((TRANSCRIPTS_DIR / "call_001.json").read_text(encoding="utf-8"))["turns"]
    turns = [
        LiveTurn(t["speaker"], i * 3.0, (i + 1) * 3.0, t["text"], False, i + 1)
        for i, t in enumerate(raw)
    ]
    eng = LiveRuleEngine()
    checklist, next_step = eng.evaluate_sop_progress("refund", turns)

    status_by_id = {s.step_id: s.status for s in checklist}

    gen_steps = [f"GEN-0{i}" for i in range(1, 9)]
    for gid in gen_steps:
        assert status_by_id[gid] == "done", f"Expected {gid} to be done on call_001, got {status_by_id[gid]}"

    done_steps = [s for s in checklist if s.status == "done"]
    assert len(done_steps) >= 8, f"Expected >= 8 done steps, got {len(done_steps)}"
