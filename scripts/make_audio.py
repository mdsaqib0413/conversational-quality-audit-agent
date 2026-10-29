"""Turn transcripts into varied call recordings (free, uses edge-tts).

Every call gets its own caller and agent voices (accent, gender, speaking speed), emotion-driven delivery per turn,
optional phone-line filtering and background noise. Both a mono and a stereo (agent left / customer right) file are written.

  python scripts/make_audio.py --all            # new calls only
  python scripts/make_audio.py --all --force    # redo every call with the new voice variety
  python scripts/make_audio.py --id call_106 --noise 2
"""
import argparse
import asyncio
import json
import random
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.audit.voices import agent_tone, customer_emotions, guess_gender, pick_voices, prosody_args  # noqa: E402

TRANS, AUDIO = ROOT / "data" / "transcripts", ROOT / "data" / "audio"


def assemble(raw: dict, synth, rng: random.Random, phone: bool = True, noise_db: float | None = None):
    """synth(turn, speaker, emotion) -> AudioSegment. Returns (mono, stereo)."""
    from pydub import AudioSegment
    from pydub.effects import normalize

    placed, prev_end = [], 0
    emos = customer_emotions(raw)
    for i, t in enumerate(raw["turns"]):
        emo = emos.get(t["i"]) if t["speaker"] == "customer" else agent_tone(raw, t)
        seg = synth(t, t["speaker"], emo or "neutral")
        pause = t.get("pause_before_sec")
        gap = int((pause if pause is not None else rng.uniform(0.3, 0.7)) * 1000)
        start = 0 if i == 0 else (max(0, prev_end - 400) if t.get("interrupts_previous") else prev_end + gap)
        placed.append((start, t["speaker"], seg))
        prev_end = start + len(seg)
    total = prev_end + 500
    tracks = {s: AudioSegment.silent(total) for s in ("agent", "customer")}
    for start, spk, seg in placed:
        tracks[spk] = tracks[spk].overlay(seg, position=start)
    if phone:
        tracks = {k: v.high_pass_filter(300).low_pass_filter(3400) for k, v in tracks.items()}
    if noise_db is not None:
        from pydub.generators import WhiteNoise

        for k in tracks:
            tracks[k] = tracks[k].overlay(WhiteNoise().to_audio_segment(duration=total, volume=noise_db))
    mono = tracks["agent"].overlay(tracks["customer"])
    stereo = AudioSegment.from_mono_audiosegments(tracks["agent"], tracks["customer"])
    return normalize(mono), stereo


async def _edge(text, voice, rate, pitch, volume, path):
    import edge_tts

    await edge_tts.Communicate(text, voice, rate=rate, pitch=pitch, volume=volume).save(path)


def make_one(raw: dict, voices, args):
    from pydub import AudioSegment

    rng = random.Random(f"{raw['id']}-{args.seed}")
    ag_g, cu_g = guess_gender(raw.get("agent_name", ""), rng), guess_gender(raw.get("customer_name", ""), rng)
    ag_v = pick_voices(voices, ag_g, rng) if voices else None
    cu_v = pick_voices(voices, cu_g, rng, avoid=ag_v or "") if voices else None
    from src.audit.voices import FALLBACK

    ag_v, cu_v = ag_v or FALLBACK[ag_g], cu_v or FALLBACK[cu_g]
    base = {"agent": rng.choice([-6, -3, 0, 3]), "customer": rng.choice([-8, -4, 0, 4, 8])}
    phone = not args.no_phone and rng.random() < 0.7
    noise = {"auto": rng.choice([None, None, -48.0, -42.0]), "0": None, "1": -48.0, "2": -42.0, "3": -36.0}[args.noise]
    tmp = Path(tempfile.mkdtemp())

    def synth(turn, speaker, emotion):
        voice = ag_v if speaker == "agent" else cu_v
        kw = prosody_args(emotion, base[speaker])
        p = str(tmp / f"{turn['i']}.mp3")
        asyncio.run(_edge(turn["text"], voice, kw["rate"], kw["pitch"], kw["volume"], p))
        return AudioSegment.from_file(p)

    mono, stereo = assemble(raw, synth, rng, phone, noise)
    AUDIO.mkdir(parents=True, exist_ok=True)
    mono.export(AUDIO / f"{raw['id']}.mp3", format="mp3")
    stereo.export(AUDIO / f"{raw['id']}_stereo.mp3", format="mp3")
    return {"agent": {"name": raw.get("agent_name"), "voice": ag_v, "speed_offset_pct": base["agent"]},
            "customer": {"name": raw.get("customer_name"), "voice": cu_v, "speed_offset_pct": base["customer"]},
            "phone_filter": phone, "noise_db": noise, "seconds": round(len(mono) / 1000, 1)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--id")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--first", type=int, default=0)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--no-phone", action="store_true")
    ap.add_argument("--noise", choices=["auto", "0", "1", "2", "3"], default="auto")
    ap.add_argument("--seed", default="1")
    ap.add_argument("--list-voices", action="store_true")
    args = ap.parse_args()
    import shutil

    if not shutil.which("ffmpeg"):
        print("ffmpeg is missing. Install it with: winget install ffmpeg")
        return 1
    try:
        import edge_tts

        voices = asyncio.run(edge_tts.list_voices())
        voices = [v for v in voices if v.get("Locale", "").startswith("en-")]
    except Exception as exc:  # noqa: BLE001
        print(f"Could not load the voice list ({str(exc)[:80]}); using the default voices.")
        voices = []
    if args.list_voices:
        for v in sorted(voices, key=lambda v: (v["Locale"], v["Gender"])):
            print(v["Locale"], v["Gender"], v["ShortName"])
        return 0
    files = sorted(TRANS.glob("call_*.json"))
    if args.id:
        files = [TRANS / f"{args.id}.json"]
    elif args.first:
        files = files[: args.first]
    elif not args.all:
        print("Use --id, --first N or --all")
        return 1
    prof_path = AUDIO / "_voice_profiles.json"
    profiles = json.loads(prof_path.read_text(encoding="utf-8")) if prof_path.exists() else {}
    for n, p in enumerate(files, 1):
        raw = json.loads(p.read_text(encoding="utf-8"))
        if (AUDIO / f"{raw['id']}.mp3").exists() and not args.force and raw["id"] in profiles:
            print(f"[{n}/{len(files)}] skipping {raw['id']} (already has varied voices; use --force to redo)")
            continue
        profiles[raw["id"]] = make_one(raw, voices, args)
        pr = profiles[raw["id"]]
        print(f"[{n}/{len(files)}] {raw['id']}: agent {pr['agent']['voice']}, customer {pr['customer']['voice']}, {pr['seconds']}s, phone={pr['phone_filter']}, noise={pr['noise_db']}")
        AUDIO.mkdir(parents=True, exist_ok=True)
        prof_path.write_text(json.dumps(profiles, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
