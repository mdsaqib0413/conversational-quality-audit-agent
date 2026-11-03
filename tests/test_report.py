import json
import time
from pathlib import Path

import pytest

from src.audit.pipeline import AuditPipeline
from src.audit.rag import KnowledgeBase
from src.audit.report import render_html, render_pdf, render_pdf_html
from src.audit.schemas import PolicyAnalysis, PolicyClaim, ScoreBreakdown
from src.audit.transcript_io import find_transcripts, load_transcript_json
from tests.fakes import FakeGateway, make_analysis

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def report(tmp_path_factory):
    files = find_transcripts(ROOT / "data" / "transcripts")
    if not files:
        pytest.skip("no transcripts")
    call, _ = load_transcript_json(files[0])
    agent = next(t for t in call.turns if t.speaker == "agent" and len(t.text.split()) > 8)
    claims = PolicyAnalysis(claims=[PolicyClaim(turn=agent.turn_id, quote=" ".join(agent.text.split()[:8]), claim="c",
                                                clause_id="REF-1.1", verdict="violation", severity="major", explanation="<b>Wrong</b> window & more")])
    gw = FakeGateway(analysis=lambda p: make_analysis(p, call, statuses={"GEN-03": "missed"}), policy=claims)
    return AuditPipeline(kb=KnowledgeBase(use_embeddings=False), gateway=gw, cache_dir=tmp_path_factory.mktemp("c")).audit_call(call)


def test_html_contains_key_sections_and_escapes(report):
    html = render_html(report)
    for needle in ("What happened", "Company rules", "Coaching", "Emotion timeline", "GEN-03", "REF-1.1", "Transcript"):
        assert needle in html
    assert "&lt;b&gt;Wrong&lt;/b&gt;" in html  # model text is escaped
    assert "<svg" in html and "aq-timeline" in html


def test_pdf_is_generated(report):
    pdf = render_pdf(report)
    assert pdf[:4] == b"%PDF" and len(pdf) > 5000


def test_failed_report_rendering_banner_no_zero_score(report):
    from src.audit import ui_html as U

    reason = "503 UNAVAILABLE"
    failed_rep = report.model_copy(update={
        "status": "failed",
        "failed_step": "policy_check",
        "summary": f"Audit failed at policy_check: {reason}",
        "cannot_judge_reason": reason,
        "scores": ScoreBreakdown(
            sop_score=0.0, policy_score=0.0, empathy_score=0.0, communication_score=0.0,
            overall_before_cap=0.0, overall=0.0, grade="D", grade_label="Pipeline Execution Failure",
            critical_failure=True, cap_reasons=[f"Step 'policy_check' failed: {reason}"]
        ),
        "meta": report.meta.model_copy(update={
            "status": "failed",
            "failed_step": "policy_check",
            "warnings": [f"Failed at policy_check: {reason}"]
        }),
    })

    # 1. PDF HTML and PDF rendering
    pdf_html = render_pdf_html(failed_rep)
    assert "Audit failed: 503 UNAVAILABLE; no score" in pdf_html
    assert "0 / 40" not in pdf_html
    assert "0/40" not in pdf_html
    assert "Audit failed" in pdf_html
    assert "No score" in pdf_html

    pdf_bytes = render_pdf(failed_rep)
    assert pdf_bytes[:4] == b"%PDF" and len(pdf_bytes) > 2000

    # 2. Standalone HTML report
    html_out = render_html(failed_rep)
    assert "Audit failed: 503 UNAVAILABLE; no score" in html_out
    assert "0 / 40" not in html_out
    assert "0/40" not in html_out

    # 3. Streamlit UI HTML components
    v_banner = U.verdict_banner(failed_rep)
    assert "Audit failed: 503 UNAVAILABLE; no score" in v_banner

    cards = U.score_cards(failed_rep)
    assert "Audit failed: 503 UNAVAILABLE; no score" in cards
    assert "0/40" not in cards
    assert "0 / 40" not in cards

    hdr = U.report_header(failed_rep)
    assert "Audit failed: 503 UNAVAILABLE; no score" in hdr

    walk = U.walkthrough_section(failed_rep)
    assert "Audit failed: 503 UNAVAILABLE; no score" in walk


def test_degraded_report_rendering_shows_scores_with_degraded_note(report):
    from src.audit import ui_html as U

    deg_rep = report.model_copy(update={
        "status": "degraded",
        "scores": ScoreBreakdown(
            sop_score=10.0, policy_score=0.0, empathy_score=3.1, communication_score=3.0,
            overall_before_cap=16.1, overall=16.1, grade="D", grade_label="Needs Improvement",
            critical_failure=False, cap_reasons=[]
        ),
        "meta": report.meta.model_copy(update={
            "status": "degraded",
            "warnings": ["Substantial dead air/silence (57.1%)"]
        }),
    })

    # 1. PDF HTML rendering
    pdf_html = render_pdf_html(deg_rep)
    assert "Audit failed" not in pdf_html
    assert "degraded input quality (Substantial dead air/silence (57.1%))" in pdf_html
    assert "16.1" in pdf_html

    # 2. Standalone HTML report
    html_out = render_html(deg_rep)
    assert "Audit failed" not in html_out
    assert "degraded input quality (Substantial dead air/silence (57.1%))" in html_out
    assert "16.1" in html_out

    # 3. Streamlit UI HTML components
    v_banner = U.verdict_banner(deg_rep)
    assert "Audit failed" not in v_banner
    assert "degraded input quality" in v_banner
    assert "Grade D" in v_banner

    cards = U.score_cards(deg_rep)
    assert "Audit failed" not in cards
    assert "degraded input quality" in cards
    assert "Call script" in cards
    assert "10" in cards

    hdr = U.report_header(deg_rep)
    assert "Audit failed" not in hdr
    assert "degraded input quality" in hdr

    walk = U.walkthrough_section(deg_rep)
    assert "Audit failed" not in walk


def test_audit_index_excludes_unhashed_and_stale_cache(monkeypatch, tmp_path):
    from app import streamlit_app as app
    from src.audit.schemas import CallTranscript

    # Create dummy audit directory with current, stale, and unhashed files
    call_id = "call_001"
    # Get current key for call_001
    call, _ = load_transcript_json(ROOT / "data" / "transcripts" / f"{call_id}.json")
    pipe = app.get_pipeline()
    curr_key = pipe._audit_key(call)

    # Mock AUDIT_DIR
    mock_audit_dir = tmp_path / "audits"
    mock_audit_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(app, "AUDIT_DIR", mock_audit_dir)

    # 1. Unhashed legacy file with newer timestamp
    (mock_audit_dir / f"{call_id}.json").write_text(
        json.dumps({"call_id": call_id, "generated_at": "2099-01-01T00:00:00", "scores": {"overall": 50.0}}),
        encoding="utf-8"
    )

    # 2. Stale hashed file with newer timestamp
    (mock_audit_dir / f"{call_id}_0123456789abcdef.json").write_text(
        json.dumps({"call_id": call_id, "generated_at": "2099-01-02T00:00:00", "scores": {"overall": 60.0}}),
        encoding="utf-8"
    )

    # 3. Current-key file
    (mock_audit_dir / f"{call_id}_{curr_key}.json").write_text(
        json.dumps({"call_id": call_id, "generated_at": "2026-11-03T12:00:00", "scores": {"overall": 100.0}}),
        encoding="utf-8"
    )

    # Clear streamlit cache and call get_audit_index
    app.get_audit_index.clear()
    idx = app.get_audit_index(int(time.time() * 1e9))

    assert len(idx) == 1
    assert idx[0]["call_id"] == call_id
    assert idx[0]["overall"] == 100.0
    assert idx[0]["path"].endswith(f"{call_id}_{curr_key}.json")

