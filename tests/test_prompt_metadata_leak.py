"""Offline tests verifying that internal policy metadata keys do not leak into LLM prompts."""

from __future__ import annotations

from pathlib import Path
import pytest

from src.audit.diarize import llm_label_segments
from src.audit.policy_check import check_policies
from src.audit.rag import KnowledgeBase
from src.audit.schemas import (
    ConversationAnalysis,
    PolicyAnalysis,
    SegmentLabel,
    SegmentLabels,
)
from src.audit.sop_check import analyze_conversation
from src.audit.topic import candidate_step_ids
from src.audit.transcribe import Segment
from src.audit.transcript_io import load_transcript_json

METADATA_KEYS = ["Topics:", "Situations:", "Numeric Limit:", "Default Severity:", "Kind:"]


class CapturingGateway:
    def __init__(self):
        self.captured_prompts: list[str] = []

    def generate_structured(self, prompt, schema, system_instruction=None, **kwargs):
        self.captured_prompts.append(prompt)
        if schema == PolicyAnalysis:
            return PolicyAnalysis(claims=[])
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


def test_policy_prompt_has_no_metadata(kb: KnowledgeBase) -> None:
    """Fails if policy metadata keys appear in the policy compliance prompt."""
    dev_call, _ = load_transcript_json(Path("data/transcripts/call_017.json"))
    gw = CapturingGateway()
    check_policies(dev_call, topic="shipping", kb=kb, gateway=gw)
    prompt = gw.captured_prompts[-1]
    leaked = [key for key in METADATA_KEYS if key in prompt]
    assert not leaked, f"Policy metadata keys leaked into policy prompt: {leaked}"
