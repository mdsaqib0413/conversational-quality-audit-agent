from pathlib import Path

import pytest

from src.audit.pipeline import AuditPipeline
from src.audit.rag import KnowledgeBase
from src.audit.report import render_html, render_pdf
from src.audit.schemas import PolicyAnalysis, PolicyClaim
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
