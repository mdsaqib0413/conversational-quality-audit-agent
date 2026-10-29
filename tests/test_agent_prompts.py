"""Tests for per-agent instruction files in agents/.

Guards:
1. Character-count cap: each .md file must stay under AGENT_FILE_CHAR_CAP.
   Fails loudly in CI if someone lets a prompt file bloat over time.
2. Request-count stability: total Gemini requests per audit (stereo and mono
   cases) is unchanged from the pre-refactor baseline (2 requests for a
   transcript-based audit; 3 for a mono audio audit that needs LLM speaker
   labelling).
"""
from __future__ import annotations

from pathlib import Path
from typing import List

import pytest

from src.audit.diarize import llm_label_segments
from src.audit.pipeline import AuditPipeline
from src.audit.rag import KnowledgeBase
from src.audit.schemas import PolicyAnalysis, SegmentLabel, SegmentLabels
from src.audit.transcribe import Segment
from src.audit.transcript_io import find_transcripts, load_transcript_json
from tests.fakes import FakeGateway, make_analysis

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parent.parent
AGENTS_DIR = REPO_ROOT / "agents"

# Adjust this constant to change the cap for all files at once.
AGENT_FILE_CHAR_CAP = 3000

EXPECTED_AGENT_FILES = [
    "compliance_agent.md",
    "policy_agent.md",
    "speaker_id_agent.md",
    "coach_agent.md",
]

# Requests per audit type:
# - transcript/stereo audit: 1 (sop_check) + 1 (policy_check) = 2
# - mono audio audit adds 1 (diarize llm_label_segments) = 3
EXPECTED_TRANSCRIPT_AUDIT_REQUESTS = 2
EXPECTED_MONO_AUDIT_REQUESTS = 3


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _agent_files() -> List[Path]:
    return [AGENTS_DIR / name for name in EXPECTED_AGENT_FILES]


# ---------------------------------------------------------------------------
# Guard 1: all expected files exist
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("filename", EXPECTED_AGENT_FILES)
def test_agent_file_exists(filename: str) -> None:
    path = AGENTS_DIR / filename
    assert path.exists(), f"agents/{filename} does not exist"


# ---------------------------------------------------------------------------
# Guard 2: character count cap
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("filename", EXPECTED_AGENT_FILES)
def test_agent_file_under_char_cap(filename: str) -> None:
    path = AGENTS_DIR / filename
    if not path.exists():
        pytest.skip(f"agents/{filename} missing — covered by existence test")
    char_count = len(path.read_text(encoding="utf-8"))
    assert char_count <= AGENT_FILE_CHAR_CAP, (
        f"agents/{filename} is {char_count} chars, exceeds cap of {AGENT_FILE_CHAR_CAP}. "
        "Trim the few-shot examples first."
    )


# ---------------------------------------------------------------------------
# Guard 3: request count unchanged (transcript-based / stereo equivalent)
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def kb() -> KnowledgeBase:
    return KnowledgeBase(use_embeddings=False)


def test_transcript_audit_request_count_unchanged(kb: KnowledgeBase, tmp_path: Path) -> None:
    """Full pipeline with a fake LLM must still make exactly 2 requests."""
    files = find_transcripts(REPO_ROOT / "data" / "transcripts")
    if not files:
        pytest.skip("no transcripts available")
    call, _ = load_transcript_json(files[0])
    gw = FakeGateway(
        analysis=lambda p: make_analysis(p, call),
        policy=PolicyAnalysis(claims=[]),
    )
    pipe = AuditPipeline(kb=kb, gateway=gw, cache_dir=tmp_path)
    pipe.audit_call(call)
    assert gw.request_count == EXPECTED_TRANSCRIPT_AUDIT_REQUESTS, (
        f"Expected {EXPECTED_TRANSCRIPT_AUDIT_REQUESTS} LLM requests for a transcript audit, "
        f"got {gw.request_count}. This refactor must not add or remove AI calls."
    )



# ---------------------------------------------------------------------------
# Guard 4: mono audio path makes exactly 3 requests (diarize + SOP + policy)
# ---------------------------------------------------------------------------
def test_mono_audio_audit_request_count_is_three(kb: KnowledgeBase, tmp_path: Path) -> None:
    """Simulates the mono diarization path: the first gateway call is the
    speaker-labelling request from llm_label_segments, followed by the normal
    SOP and policy requests.  Total must be exactly 3 — unchanged from before
    this refactor.
    """
    files = find_transcripts(REPO_ROOT / "data" / "transcripts")
    if not files:
        pytest.skip("no transcripts available")
    call, _ = load_transcript_json(files[0])

    # Build a minimal SegmentLabels response matching the transcript turns.
    # Each turn becomes one labelled segment so llm_label_segments is satisfied.
    segments = [
        Segment(start=t.start_time, end=t.end_time, text=t.text)
        for t in call.turns
    ]
    fake_labels = SegmentLabels(
        labels=[SegmentLabel(i=i, speaker=t.speaker) for i, t in enumerate(call.turns)]
    )

    gw = FakeGateway(
        analysis=lambda p: make_analysis(p, call),
        policy=PolicyAnalysis(claims=[]),
        labels=fake_labels,
    )

    # Request 1: diarize (speaker labelling for mono audio)
    returned_labels = llm_label_segments(segments, gw)
    assert len(returned_labels) == len(segments)
    assert gw.request_count == 1, "diarize should consume exactly 1 request"

    # Requests 2 + 3: normal transcript audit (SOP + policy)
    pipe = AuditPipeline(kb=kb, gateway=gw, cache_dir=tmp_path)
    pipe.audit_call(call)

    assert gw.request_count == EXPECTED_MONO_AUDIT_REQUESTS, (
        f"Expected {EXPECTED_MONO_AUDIT_REQUESTS} total LLM requests for a mono audio audit "
        f"(diarize + SOP + policy), got {gw.request_count}."
    )
