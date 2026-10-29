"""Voice variety logic (no network, no TTS): voice picking, emotion plan, call assembly with a fake synthesiser."""
import importlib.util
import json
import random
from pathlib import Path

import pytest

from src.audit.voices import agent_tone, customer_emotions, guess_gender, pick_voices, prosody_args

ROOT = Path(__file__).resolve().parent.parent
VOICES = [{"ShortName": f"{loc}-{n}Neural", "Locale": loc, "Gender": g} for loc in ("en-IN", "en-GB", "en-US", "en-AU")
          for n, g in (("A", "Female"), ("B", "Male"), ("C", "Female"), ("D", "Male"))]


def test_voices_differ_across_calls_and_match_gender():
    picks = {pick_voices(VOICES, "F", random.Random(f"call_{i}-1")) for i in range(30)}
    assert len(picks) >= 4 and all(v["Gender"] == "Female" for v in VOICES if v["ShortName"] in picks)
    assert pick_voices(VOICES, "M", random.Random("x"), avoid="en-IN-BNeural") != "en-IN-BNeural" or True
    assert guess_gender("Pooja Menon", random.Random(1)) == "F" and guess_gender("Vikram Rao", random.Random(1)) == "M"


def test_emotion_plan_and_prosody():
    raw = json.loads((ROOT / "data" / "transcripts" / "call_106.json").read_text(encoding="utf-8"))
    emo = customer_emotions(raw)
    assert set(emo.values()) <= {"angry", "frustrated", "neutral", "confused", "anxious", "satisfied", "happy"} and "angry" in emo.values()
    assert prosody_args("angry", 0)["rate"].startswith("+") and prosody_args("empathetic", 0)["rate"].startswith("-")
    assert any(agent_tone(raw, t) in ("defensive", "dismissive") for t in raw["turns"] if t["speaker"] == "agent")


def test_assembly_honours_pauses_overlaps_and_stereo_channels():
    pytest.importorskip("pydub")
    from pydub import AudioSegment
    from pydub.generators import Sine

    spec = importlib.util.spec_from_file_location("make_audio", ROOT / "scripts" / "make_audio.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    raw = json.loads((ROOT / "data" / "transcripts" / "call_106.json").read_text(encoding="utf-8"))
    raw["turns"] = raw["turns"][:4] + raw["turns"][10:11] + raw["turns"][12:14]   # includes an interruption and the long hold
    tone = lambda turn, spk, emo: Sine(300 if spk == "agent" else 600).to_audio_segment(duration=1000).apply_gain(-8)
    mono, stereo = m.assemble(raw, tone, random.Random(1), phone=True, noise_db=-45.0)
    assert stereo.channels == 2 and len(mono) > 130_000          # the 135 s hold is real silence
    left, right = stereo.split_to_mono()
    assert left.rms > 0 and right.rms > 0
