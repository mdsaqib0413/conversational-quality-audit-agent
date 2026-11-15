"""Tests for deterministic HLD-02 hold ceiling reconciliation."""

from pathlib import Path
import pytest

from src.audit.schemas import (
    AuditFinding,
    AuditMeta,
    AuditReport,
    ConversationMetrics,
    CallTranscript,
    CoachingItem,
    DialogueTurn,
    HoldSpan,
    ScoreBreakdown,
    SOPResult,
)
from src.audit.reconcile import reconcile_hld02, reconcile_report
from src.audit.rag import get_kb

ROOT = Path(__file__).resolve().parent.parent


def test_hld02_override_fires_when_hold_under_120s():
    """HLD-02 marked missed by LLM is overridden when measured hold is <= 120s."""
    sop_results = [
        SOPResult(
            step_id="HLD-02",
            title="Adhere to Maximum 2-Minute Hold Ceiling",
            sop="hold_and_transfer_sop",
            weight=4,
            critical=True,
            mandatory=True,
            status="missed",
            points_earned=0.0,
            points_possible=4.0,
            reason="The agent kept the customer on hold too long.",
            missing="Did not return within ceiling",
        )
    ]
    metrics = ConversationMetrics(
        holds=[
            HoldSpan(
                start_turn=14,
                end_turn=15,
                start_time=162.41,
                end_time=237.41,
                seconds=75.0,
                exceeded=False,
            )
        ]
    )

    changed = reconcile_hld02(sop_results, metrics)
    assert changed is True
    res = sop_results[0]
    assert res.status == "followed"
    assert res.points_earned == 4.0
    assert res.points_possible == 4.0
    assert res.missing == ""
    assert "Overridden: measured hold 75.0 s is under the 120 s ceiling." in res.reason


def test_hld02_override_does_not_fire_when_hold_exceeds_120s():
    """HLD-02 marked missed must NOT be overridden when a hold actually exceeded 120s."""
    sop_results = [
        SOPResult(
            step_id="HLD-02",
            title="Adhere to Maximum 2-Minute Hold Ceiling",
            sop="hold_and_transfer_sop",
            weight=4,
            critical=True,
            mandatory=True,
            status="missed",
            points_earned=0.0,
            points_possible=4.0,
            reason="Exceeded 2 minutes on hold.",
            missing="Returned after 135 seconds.",
        )
    ]
    metrics = ConversationMetrics(
        holds=[
            HoldSpan(
                start_turn=13,
                end_turn=14,
                start_time=108.87,
                end_time=243.87,
                seconds=135.0,
                exceeded=True,
            )
        ]
    )

    changed = reconcile_hld02(sop_results, metrics)
    assert changed is False
    res = sop_results[0]
    assert res.status == "missed"
    assert res.points_earned == 0.0
    assert "Overridden" not in res.reason


def test_hld02_override_does_not_fire_when_already_followed():
    """If HLD-02 was already marked followed, reconciliation does not modify it."""
    sop_results = [
        SOPResult(
            step_id="HLD-02",
            title="Adhere to Maximum 2-Minute Hold Ceiling",
            sop="hold_and_transfer_sop",
            weight=4,
            critical=True,
            mandatory=True,
            status="followed",
            points_earned=4.0,
            points_possible=4.0,
            reason="Promptly returned within 120 seconds.",
        )
    ]
    metrics = ConversationMetrics(
        holds=[
            HoldSpan(
                start_turn=5,
                end_turn=6,
                start_time=50.0,
                end_time=90.0,
                seconds=40.0,
                exceeded=False,
            )
        ]
    )

    changed = reconcile_hld02(sop_results, metrics)
    assert changed is False
    assert sop_results[0].status == "followed"
    assert "Overridden" not in sop_results[0].reason


def test_hld02_override_does_not_fire_when_step_absent():
    """If HLD-02 is not in the SOP steps, reconcile returns False."""
    sop_results = [
        SOPResult(
            step_id="GEN-01",
            title="Greeting",
            sop="general_sop",
            weight=2,
            status="followed",
            points_earned=2.0,
            points_possible=2.0,
        )
    ]
    metrics = ConversationMetrics(holds=[])
    changed = reconcile_hld02(sop_results, metrics)
    assert changed is False


def test_reconcile_report_call_105_corrects_scores_and_cap():
    """Reconciling call_105 updates score to 100.0, removes critical cap, updates findings/coaching."""
    cpath = ROOT / "data" / "cache" / "audits" / "call_105_d5b32b15966cc6f2.json"
    if not cpath.exists():
        pytest.skip("call_105 cache file not found")

    report = AuditReport.model_validate_json(cpath.read_text(encoding="utf-8"))
    # Reconcile the report
    reconciled = reconcile_report(report, get_kb().rubric)

    # Score and grade verification
    assert reconciled.scores.overall == 100.0
    assert reconciled.scores.grade == "A"
    assert reconciled.scores.critical_failure is False
    assert not any("HLD-02" in r for r in reconciled.scores.cap_reasons)

    # Finding verification
    hld_findings = [f for f in reconciled.findings if f.criterion_id == "HLD-02"]
    if hld_findings:
        assert hld_findings[0].verdict == "followed"
        assert "Overridden: measured hold 75.0 s is under the 120 s ceiling." in hld_findings[0].explanation

    # Coaching tip verification: HLD-02 should be removed
    assert not any("HLD-02" in c.title for c in reconciled.coaching)


def test_reconcile_report_call_106_leaves_critical_failure_intact():
    """Reconciling call_106 (actual hold violation) preserves the missed status and cap."""
    cpath = ROOT / "data" / "cache" / "audits" / "call_106_511787644273c247.json"
    if not cpath.exists():
        pytest.skip("call_106 cache file not found")

    report = AuditReport.model_validate_json(cpath.read_text(encoding="utf-8"))
    reconciled = reconcile_report(report, get_kb().rubric)

    assert reconciled.scores.overall == 16.1
    assert reconciled.scores.grade == "D"
    assert reconciled.scores.critical_failure is True
    hld_step = next((s for s in reconciled.sop_results if s.step_id == "HLD-02"), None)
    assert hld_step is not None
    assert hld_step.status == "missed"
