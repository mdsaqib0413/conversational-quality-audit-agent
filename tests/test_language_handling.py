"""Tests for speech-to-text language resolution and explicit handling (offline, no model download)."""

from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts.audio_smoke_test import parse_args
from src.audit.pipeline import AuditPipeline
from src.audit.quality import evaluate_transcript_quality
from src.audit.rag import KnowledgeBase
from src.audit.schemas import CallTranscript, DialogueTurn, SegmentLabel, SegmentLabels
from src.audit.transcribe import (
    INITIAL_PROMPT_EN,
    INITIAL_PROMPT_TE,
    Segment,
    Transcriber,
    resolve_language,
)
from tests.fakes import FakeGateway

KB = KnowledgeBase(use_embeddings=False)


def test_resolve_language_precedence(monkeypatch):
    # 1. Explicit argument overrides WHISPER_LANGUAGE env var
    monkeypatch.setenv("WHISPER_LANGUAGE", "te")
    assert resolve_language("en") == "en"
    assert resolve_language("te") == "te"
    assert resolve_language("hi") == "hi"

    # 2. WHISPER_LANGUAGE env var is used when explicit is None or empty
    assert resolve_language(None) == "te"
    assert resolve_language("") == "te"

    monkeypatch.setenv("WHISPER_LANGUAGE", "en")
    assert resolve_language() == "en"

    monkeypatch.setenv("WHISPER_LANGUAGE", "hi")
    assert resolve_language() == "hi"

    # 3. Default is "auto" when neither is provided
    monkeypatch.delenv("WHISPER_LANGUAGE", raising=False)
    assert resolve_language(None) == "auto"
    assert resolve_language("") == "auto"

    # 4. Normalization and aliases
    assert resolve_language("English") == "en"
    assert resolve_language("Telugu") == "te"
    assert resolve_language("Hindi") == "hi"
    assert resolve_language("Auto") == "auto"

    # 5. Invalid/unsupported language raises ValueError
    with pytest.raises(ValueError, match="Unsupported transcription language"):
        resolve_language("french")


class FakeDiarizeTranscriber:
    def __init__(self, detected="en"):
        self.detected = detected
        self.calls = []

    def detect_language(self, audio_path):
        return self.detected, 0.99

    def transcribe(self, audio_path, language=None):
        self.calls.append({"path": Path(audio_path).name, "language": language})
        seg = Segment(start=0.0, end=2.0, text="Hello thank you for calling ShopEase")
        return [seg], 2.0


def test_no_filename_guessing_in_pipeline(tmp_path, monkeypatch):
    pydub = pytest.importorskip("pydub")
    from pydub.generators import Sine

    # Create dummy audio files with names that used to trigger filename guessing
    en_file = tmp_path / "en_real_001.wav"
    Sine(300).to_audio_segment(duration=1000).export(en_file, format="wav")

    te_file = tmp_path / "call_001.wav"
    Sine(300).to_audio_segment(duration=1000).export(te_file, format="wav")

    tr = FakeDiarizeTranscriber()
    pipe = AuditPipeline(kb=KB, gateway=FakeGateway(), transcriber=tr, cache_dir=tmp_path / "cache")

    # en_real_001 with explicit "te" must be "te", NOT "en"
    call_te, _, _ = pipe.transcribe_audio(str(en_file), language="te")
    assert call_te.language == "te"

    # call_001 with explicit "en" must be "en", NOT "te"
    call_en, _, _ = pipe.transcribe_audio(str(te_file), language="en")
    assert call_en.language == "en"

    # en_real_001 with WHISPER_LANGUAGE="hi" and no explicit argument must be "hi", NOT "en"
    monkeypatch.setenv("WHISPER_LANGUAGE", "hi")
    call_hi, _, _ = pipe.transcribe_audio(str(en_file), language=None)
    assert call_hi.language == "hi"


def test_transcript_cache_key_changes_with_language(tmp_path):
    pytest.importorskip("pydub")
    from pydub.generators import Sine

    audio_file = tmp_path / "sample_call.wav"
    Sine(440).to_audio_segment(duration=1000).export(audio_file, format="wav")

    cache_dir = tmp_path / "cache"
    tr = FakeDiarizeTranscriber()
    gw = FakeGateway(labels=SegmentLabels(labels=[SegmentLabel(i=0, speaker="agent")]))
    pipe = AuditPipeline(kb=KB, gateway=gw, transcriber=tr, cache_dir=cache_dir)

    call_en, _, _ = pipe.transcribe_audio(str(audio_file), language="en", use_cache=True)
    assert call_en.language == "en"

    call_te, _, _ = pipe.transcribe_audio(str(audio_file), language="te", use_cache=True)
    assert call_te.language == "te"

    cached_files = [p.name for p in (cache_dir / "transcripts").glob("*.json")]
    assert any("_en_v7.json" in name for name in cached_files)
    assert any("_te_v7.json" in name for name in cached_files)
    assert len(cached_files) == 2


def test_smoke_test_cli_argument_parsing():
    args_default = parse_args(["audio.mp3"])
    assert args_default.audio_path == "audio.mp3"
    assert args_default.language == "auto"

    args_en = parse_args(["audio.mp3", "--language", "en"])
    assert args_en.language == "en"

    args_te = parse_args(["audio.mp3", "--language", "te"])
    assert args_te.language == "te"

    args_hi = parse_args(["audio.mp3", "--language", "hi"])
    assert args_hi.language == "hi"


def test_quality_eval_uses_chosen_call_language():
    turn = DialogueTurn(
        turn_id=1, speaker="agent", start_time=0.0, end_time=2.0,
        text="Thank you for calling ShopEase support, how may I help you?",
        asr_confidence=0.95, silence_before=0.0, overlaps_previous=False,
    )
    # English call
    call_en = CallTranscript(call_id="call_en", source="audio", language="en", duration_seconds=2.0, turns=[turn])
    quality_en, reason_en, _ = evaluate_transcript_quality(call_en)
    assert quality_en == "good"

    # Telugu call with no Telugu content: should flag language mismatch
    call_te = CallTranscript(call_id="call_te", source="audio", language="te", duration_seconds=2.0, turns=[
        DialogueTurn(turn_id=1, speaker="agent", start_time=0.0, end_time=2.0, text="...", asr_confidence=0.95, silence_before=0.0, overlaps_previous=False)
    ])
    quality_te, reason_te, _ = evaluate_transcript_quality(call_te)
    assert quality_te in ("unusable", "degraded")


def test_transcriber_auto_detect_and_prompt_selection():
    seg = SimpleNamespace(start=0.0, end=2.0, text="Hello world", words=[])
    recorded_kwargs = []

    class FakeModel:
        def detect_language(self, audio):
            return "te", 0.94, []

        def transcribe(self, path, **kw):
            recorded_kwargs.append(kw)
            return iter([seg]), SimpleNamespace(duration=2.0, language=kw.get("language"), language_probability=0.94)

    t = Transcriber()
    t._model = FakeModel()

    # Transcribe with "te": uses INITIAL_PROMPT_TE
    t.transcribe("fake.wav", language="te")
    assert recorded_kwargs[-1]["language"] == "te"
    assert recorded_kwargs[-1]["initial_prompt"] == INITIAL_PROMPT_TE

    # Transcribe with "en": uses INITIAL_PROMPT_EN
    t.transcribe("fake.wav", language="en")
    assert recorded_kwargs[-1]["language"] == "en"
    assert recorded_kwargs[-1]["initial_prompt"] == INITIAL_PROMPT_EN
