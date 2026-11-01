"""Offline tests verifying that internal policy metadata keys do not leak into LLM prompts or user-facing reports."""

from __future__ import annotations

from pathlib import Path
import pytest

from src.audit.diarize import llm_label_segments
from src.audit.policy_check import check_policies
from src.audit.rag import KnowledgeBase
from src.audit.report import render_pdf_html
from src.audit.schemas import (
    AuditReport,
    ConversationAnalysis,
    PolicyAnalysis,
    PolicyClaim,
    PolicyResult,
    ScoreBreakdown,
    SegmentLabel,
    SegmentLabels,
)
from src.audit.sop_check import analyze_conversation
from src.audit.topic import candidate_step_ids
from src.audit.transcribe import Segment
from src.audit.transcript_io import load_transcript_json
from src.audit.ui_html import policies_and_sops_involved_section, policy_section

METADATA_KEYS = ["Topics:", "Situations:", "Numeric Limit:", "Default Severity:", "Kind:"]


class CapturingGateway:
    def __init__(self, claims=None):
        self.captured_prompts: list[str] = []
        self.claims = claims if claims is not None else []

    def generate_structured(self, prompt, schema, system_instruction=None, **kwargs):
        self.captured_prompts.append(prompt)
        if schema == PolicyAnalysis:
            return PolicyAnalysis(claims=self.claims)
        elif schema == ConversationAnalysis:
            return ConversationAnalysis(
                summary="Summary",
                customer_issue="Issue",
                resolved=True,
                steps=[],
                empathy_score=4,
                empathy_evidence="Evidence",
                clarity_score=4,
                professionalism_score=4,
                ownership_score=4,
                closure_score=4,
                turn_emotions=[],
                agent_tones=[],
                gaps=[],
                strengths=[],
                coaching_tips=[],
                risk_flags=[],
            )
        elif schema == SegmentLabels:
            return SegmentLabels(
                labels=[
                    SegmentLabel(i=0, speaker="agent"),
                    SegmentLabel(i=1, speaker="customer"),
                ]
            )
        raise ValueError(f"Unknown schema: {schema}")


@pytest.fixture
def kb() -> KnowledgeBase:
    return KnowledgeBase(use_embeddings=False)


def test_sop_prompt_has_no_metadata(kb: KnowledgeBase) -> None:
    """Ensure SOP adherence prompts contain no internal policy metadata lines."""
    dev_call, _ = load_transcript_json(Path("data/transcripts/call_017.json"))
    gw = CapturingGateway()
    step_ids = candidate_step_ids(kb, "shipping", [])
    analyze_conversation(dev_call, topic="shipping", signals=[], step_ids=step_ids, kb=kb, gateway=gw)
    prompt = gw.captured_prompts[-1]
    for key in METADATA_KEYS:
        assert key not in prompt, f"Metadata key '{key}' leaked into SOP prompt"


def test_speaker_id_prompt_has_no_metadata() -> None:
    """Ensure speaker-id diarization prompts contain no internal policy metadata lines."""
    gw = CapturingGateway()
    dummy_segments = [
        Segment(start=0.0, end=2.0, text="Hello, thank you for calling ShopEase."),
        Segment(start=2.5, end=4.5, text="Hi, my order has not arrived."),
    ]
    llm_label_segments(dummy_segments, gw)
    prompt = gw.captured_prompts[-1]
    for key in METADATA_KEYS:
        assert key not in prompt, f"Metadata key '{key}' leaked into Speaker-ID prompt"


def test_policy_prompt_metadata_default_includes_metadata(kb: KnowledgeBase, monkeypatch: pytest.MonkeyPatch) -> None:
    """When POLICY_PROMPT_METADATA is default (or 1), the policy prompt contains the metadata block."""
    monkeypatch.delenv("POLICY_PROMPT_METADATA", raising=False)
    dev_call, _ = load_transcript_json(Path("data/transcripts/call_017.json"))
    gw = CapturingGateway()
    check_policies(dev_call, topic="shipping", kb=kb, gateway=gw)
    prompt = gw.captured_prompts[-1]
    found = [k for k in METADATA_KEYS if k in prompt]
    assert len(found) > 0, "Default policy prompt was expected to include metadata block"


def test_policy_prompt_metadata_disabled_strips_metadata(kb: KnowledgeBase, monkeypatch: pytest.MonkeyPatch) -> None:
    """When POLICY_PROMPT_METADATA=0, the policy prompt strips all internal metadata lines."""
    monkeypatch.setenv("POLICY_PROMPT_METADATA", "0")
    dev_call, _ = load_transcript_json(Path("data/transcripts/call_017.json"))
    gw = CapturingGateway()
    check_policies(dev_call, topic="shipping", kb=kb, gateway=gw)
    prompt = gw.captured_prompts[-1]
    leaked = [key for key in METADATA_KEYS if key in prompt]
    assert not leaked, f"Policy metadata keys leaked into policy prompt when POLICY_PROMPT_METADATA=0: {leaked}"


def test_policy_result_policy_text_has_no_metadata(kb: KnowledgeBase) -> None:
    """PolicyResult.policy_text should contain clean clause body text without metadata lines."""
    dev_call, _ = load_transcript_json(Path("data/transcripts/call_017.json"))
    claim = PolicyClaim(
        turn=9,
        quote="As per our courier guidelines, the delivery agent will make only one single delivery attempt at your door.",
        claim="The delivery agent will make only one delivery attempt.",
        clause_id="SHP-1.2",
        verdict="violation",
        severity="major",
        explanation="Standard shipping policy requires three delivery attempts before returning parcel to origin.",
    )
    gw = CapturingGateway(claims=[claim])
    results, _, _ = check_policies(dev_call, topic="shipping", kb=kb, gateway=gw)
    assert len(results) > 0
    for r in results:
        if r.policy_text:
            for key in METADATA_KEYS:
                assert key not in r.policy_text, f"Metadata key '{key}' in PolicyResult.policy_text: {r.policy_text}"


def test_pdf_and_ui_renders_have_no_metadata(kb: KnowledgeBase) -> None:
    """PDF report and Streamlit HTML renders must never expose metadata lines, even from dirty inputs."""
    dev_call, _ = load_transcript_json(Path("data/transcripts/call_017.json"))
    scores = ScoreBreakdown(
        sop_score=30.0,
        policy_score=10.0,
        empathy_score=10.0,
        communication_score=10.0,
        overall_before_cap=60.0,
        overall=60.0,
        grade="C",
    )
    dirty_text = """Standard shipping takes 3-5 business days.
- **Topics:** shipping, logistics
- **Situations:** delay
- **Numeric Limit:** 5 days
- **Default Severity:** major
- **Kind:** rule
Customer must be informed of delay proactively."""
    policy_results = [
        PolicyResult(
            clause_id="SHP-1.1",
            verdict="violation",
            severity="critical",
            turn=1,
            quote="It takes up to 10 days.",
            explanation="Violated shipping timeline.",
            policy_title="SHP-1.1: Standard Shipping Timelines",
            policy_text=dirty_text,
        )
    ]
    report = AuditReport(
        call_id="call_017",
        generated_at="2026-10-22T00:00:00",
        topic="shipping",
        topic_confidence=0.95,
        scores=scores,
        sop_results=[],
        policy_results=policy_results,
        transcript=dev_call,
    )

    pdf_html = render_pdf_html(report)
    ui_pol = policy_section(report)
    ui_inv = policies_and_sops_involved_section(report, kb)

    for target_name, html_content in [
        ("PDF Report", pdf_html),
        ("Streamlit Policy Section", ui_pol),
        ("Streamlit Involved Section", ui_inv),
    ]:
        for key in METADATA_KEYS:
            assert key not in html_content, f"Metadata key '{key}' leaked in {target_name}"
