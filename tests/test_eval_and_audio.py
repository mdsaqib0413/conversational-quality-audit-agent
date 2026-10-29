"""Evaluation maths (oracle fake LLM must score ~100%) and the audio path (synthetic audio + fake transcriber)."""
from pathlib import Path

import pytest

from src.audit.evaluation import evaluate_no_llm, evaluate_reports
from src.audit.pipeline import AuditPipeline
from src.audit.rag import KnowledgeBase
from src.audit.schemas import PolicyAnalysis, PolicyClaim, SegmentLabel, SegmentLabels
from src.audit.transcribe import Segment
from src.audit.transcript_io import find_transcripts, load_transcript_json
from tests.fakes import FakeGateway, make_analysis, step_ids_in

ROOT = Path(__file__).resolve().parent.parent
KB = KnowledgeBase(use_embeddings=False)


def oracle_gateway(call, raw):
    gt = raw["ground_truth"]

    def analysis(prompt):
        a = make_analysis(prompt, call, statuses=gt["sop_steps"])
        return a

    claims = [PolicyClaim(turn=v["turn"], quote=" ".join(v["said"].split()[:10]), claim="c", clause_id=v["clause_id"], verdict="violation",
                          severity=v["severity"], explanation="oracle") for v in gt["policy_violations"]]
    return FakeGateway(analysis=analysis, policy=PolicyAnalysis(claims=claims))


def test_oracle_llm_gets_near_perfect_evaluation(tmp_path):
    files = find_transcripts(ROOT / "data" / "transcripts")
    if not files:
        pytest.skip("no transcripts")
    pairs = []
    for p in files:
        call, raw = load_transcript_json(p)
        rep = AuditPipeline(kb=KB, gateway=oracle_gateway(call, raw), cache_dir=tmp_path).audit_call(call)
        pairs.append((rep, raw))
    res = evaluate_reports(pairs)
    assert res["sop"]["exact_match_rate"] == 1.0 and res["sop"]["not_judged"] == 0
    assert res["violations"]["clause_level"]["recall"] == 1.0 and res["violations"]["clause_level"]["precision"] == 1.0
    assert res["violations"]["severity_agreement"] == 1.0
    assert res["gaps"].get("dead_air", {"fn": 0})["fn"] == 0


def test_no_llm_evaluation_runs():
    files = find_transcripts(ROOT / "data" / "transcripts")
    if not files:
        pytest.skip("no transcripts")
    res = evaluate_no_llm(files, KB)
    assert res["candidate_step_coverage"] == 1.0


# ---------------------------------------------------------------- audio path
class FakeTranscriber:
    """Returns canned segments; the stereo path calls it once per channel."""
    def __init__(self, mono=None, left=None, right=None):
        self.mono, self.left, self.right, self.calls = mono, left, right, []

    def transcribe(self, path, language=None):
        self.calls.append(Path(path).name)
        if Path(path).name == "left.wav":
            return self.left, 8.0
        if Path(path).name == "right.wav":
            return self.right, 8.0
        return self.mono, 8.0


def _stereo_wav(tmp_path):
    pydub = pytest.importorskip("pydub")
    from pydub import AudioSegment
    from pydub.generators import Sine

    tone = Sine(440).to_audio_segment(duration=1000).apply_gain(-6)
    sil = AudioSegment.silent(duration=1000)
    left, right = tone + sil + tone + sil, sil + tone + sil + tone
    p = tmp_path / "call_x_stereo.wav"
    AudioSegment.from_mono_audiosegments(left, right).export(p, format="wav")
    return p


def test_stereo_audio_gets_perfect_speaker_separation_without_llm(tmp_path):
    p = _stereo_wav(tmp_path)
    tr = FakeTranscriber(
        left=[Segment(0, 1, "Thank you for calling ShopEase, how may I help you?"), Segment(2, 3, "I understand, may I have your order ID?")],
        right=[Segment(1, 2, "Hello, my order has not arrived."), Segment(3, 4, "It is ORD-1.")])
    gw = FakeGateway()
    from src.audit.diarize import build_call_from_audio

    call, warnings = build_call_from_audio(str(p), "call_x", tr, gw)
    assert [t.speaker for t in call.turns] == ["agent", "customer", "agent", "customer"]
    assert call.diarization_method.startswith("stereo-channels") and gw.request_count == 0 and not warnings
    assert tr.calls == ["left.wav", "right.wav"]


def test_stereo_with_swapped_channels_detects_agent_by_greeting(tmp_path):
    p = _stereo_wav(tmp_path)
    tr = FakeTranscriber(
        right=[Segment(0, 1, "Thank you for calling ShopEase, how may I help you?")],
        left=[Segment(1, 2, "Hello, my order has not arrived.")])
    from src.audit.diarize import build_call_from_audio

    call, _ = build_call_from_audio(str(p), "c", tr, FakeGateway())
    assert call.turns[0].speaker == "agent" and call.turns[1].speaker == "customer"


def test_mono_audio_uses_one_llm_request_for_speakers(tmp_path):
    pydub = pytest.importorskip("pydub")
    from pydub import AudioSegment
    from pydub.generators import Sine

    p = tmp_path / "mono.wav"
    Sine(300).to_audio_segment(duration=4000).export(p, format="wav")
    segs = [Segment(0, 1, "Thank you for calling ShopEase."), Segment(1.5, 2.5, "My order is late."), Segment(3, 4, "I apologise, let me check.")]
    gw = FakeGateway(labels=SegmentLabels(labels=[SegmentLabel(i=0, speaker="agent"), SegmentLabel(i=1, speaker="customer"), SegmentLabel(i=2, speaker="agent")]))
    from src.audit.diarize import build_call_from_audio

    call, warnings = build_call_from_audio(str(p), "m", FakeTranscriber(mono=segs), gw)
    assert gw.request_count == 1 and call.diarization_method == "llm-labelled mono"
    assert [t.speaker for t in call.turns] == ["agent", "customer", "agent"]


def test_mono_falls_back_to_flagged_heuristic_when_llm_fails(tmp_path):
    pytest.importorskip("pydub")
    from pydub.generators import Sine

    p = tmp_path / "mono2.wav"
    Sine(300).to_audio_segment(duration=4000).export(p, format="wav")
    segs = [Segment(0, 1, "Thank you for calling ShopEase, how may I help you?"), Segment(1.5, 2.5, "Hello, my order has not arrived.")]

    class Broken(FakeGateway):
        def generate_structured(self, *a, **k):
            raise RuntimeError("quota")

    from src.audit.diarize import build_call_from_audio

    call, warnings = build_call_from_audio(str(p), "m2", FakeTranscriber(mono=segs), Broken())
    assert "LOW CONFIDENCE" in call.diarization_method and warnings


def test_audit_audio_end_to_end_and_transcript_cache(tmp_path):
    p = _stereo_wav(tmp_path)
    tr = FakeTranscriber(
        left=[Segment(0, 1, "Thank you for calling ShopEase. This call is recorded. How may I help?"), Segment(2, 3, "Please confirm your order ID and last four digits.")],
        right=[Segment(1, 2, "My order has not arrived, I am frustrated."), Segment(3, 4, "ORD-1 and 4321.")])
    holder = {}

    def analysis(prompt):
        return make_analysis(prompt, holder["call"])

    gw = FakeGateway(analysis=analysis, policy=PolicyAnalysis(claims=[]))
    pipe = AuditPipeline(kb=KB, gateway=gw, transcriber=tr, cache_dir=tmp_path / "cache")
    from src.audit.diarize import build_call_from_audio

    holder["call"], _ = build_call_from_audio(str(p), "call_x_stereo", FakeTranscriber(left=tr.left, right=tr.right), FakeGateway())
    rep = pipe.audit_audio(str(p))
    assert rep.transcript.source == "audio" and rep.meta.diarization_method.startswith("stereo")
    n_calls = len(tr.calls)
    rep2 = pipe.audit_audio(str(p))
    assert len(tr.calls) == n_calls and rep2.meta.cache_hit  # neither Whisper nor the LLM ran again


def test_heuristic_transcript_is_never_cached_or_reused(tmp_path):
    pytest.importorskip("pydub")
    from pydub.generators import Sine

    p = tmp_path / "mono3.wav"
    Sine(300).to_audio_segment(duration=4000).export(p, format="wav")
    segs = [Segment(0, 1, "Thank you for calling ShopEase, how may I help you?"), Segment(1.5, 2.5, "Hello, my order has not arrived.")]

    class Broken(FakeGateway):
        def generate_structured(self, *a, **k):
            raise RuntimeError("network down")

    tr = FakeTranscriber(mono=segs)
    pipe = AuditPipeline(kb=KB, gateway=Broken(), transcriber=tr, cache_dir=tmp_path / "cache")
    call, warnings, _ = pipe.transcribe_audio(str(p))
    assert "LOW CONFIDENCE" in call.diarization_method
    assert not list((tmp_path / "cache").rglob("*.json"))  # nothing cached
    good = FakeGateway(labels=SegmentLabels(labels=[SegmentLabel(i=0, speaker="agent"), SegmentLabel(i=1, speaker="customer")]))
    pipe2 = AuditPipeline(kb=KB, gateway=good, transcriber=FakeTranscriber(mono=segs), cache_dir=tmp_path / "cache")
    call2, _, _ = pipe2.transcribe_audio(str(p))
    assert call2.diarization_method == "llm-labelled mono"
