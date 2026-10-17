"""Convert call transcripts to realistic synthetic audio using edge-tts and pydub.

Features:
- Indian English Neural voices for Agent (en-IN-NeerjaNeural) and Customer (en-IN-PrabhatNeural)
- Stitches dialogue turns with pauses, honoring pause_before_sec and turn interruptions
- Inflects angry customer turns with faster rate (+15%) and higher pitch (+5Hz)
- Dual export: mono mixed audio (<id>.mp3) and channel-separated stereo (<id>_stereo.mp3)
- Optional subtle background acoustic noise (--noise)
- Manifest tracking via data/audio/_audio_manifest.csv
- Clean error messaging if FFmpeg is missing
"""

import os
import io
import sys
import csv
import json
import random
import asyncio
import logging
import argparse
from pathlib import Path
from typing import Dict, Any, List, Optional

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from pydub import AudioSegment
from pydub.generators import WhiteNoise
from pydub.utils import which
import edge_tts

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("make_audio")

ANGRY_KEYWORDS = [
    "angry", "ridiculous", "horrible", "cheat", "scam", "worst", "unacceptable",
    "manager", "supervisor", "fraud", "court", "complaint", "refuse", "disgusted"
]


def check_ffmpeg() -> bool:
    """Verifies ffmpeg is accessible on system PATH."""
    ffmpeg_bin = which("ffmpeg")
    if not ffmpeg_bin:
        print("\n" + "!" * 70)
        print("❌ CRITICAL ERROR: FFmpeg is not installed or not found on PATH.")
        print("FFmpeg is required by pydub to encode and export MP3 audio.")
        print("Installation instructions for Windows:")
        print("  1. Run in PowerShell: winget install Gyan.FFmpeg")
        print("  2. Or download from: https://www.gyan.dev/ffmpeg/builds/")
        print("     and add the 'bin' folder to your system PATH.")
        print("!" * 70 + "\n")
        return False
    return True


async def synthesize_turn_audio(
    text: str,
    voice: str,
    rate: str = "+0%",
    pitch: str = "+0Hz"
) -> AudioSegment:
    """Synthesizes text turn via edge-tts into an in-memory AudioSegment."""
    comm = edge_tts.Communicate(text=text, voice=voice, rate=rate, pitch=pitch)
    mp3_bytes = b""
    async for chunk in comm.stream():
        if chunk["type"] == "audio":
            mp3_bytes += chunk["data"]

    if not mp3_bytes:
        # Fallback 1 second silence if empty
        return AudioSegment.silent(duration=1000)

    return AudioSegment.from_file(io.BytesIO(mp3_bytes), format="mp3")


async def render_transcript_audio(
    transcript_path: Path,
    output_dir: Path,
    agent_voice: str = "en-IN-NeerjaNeural",
    customer_voice: str = "en-IN-PrabhatNeural",
    add_noise: bool = False
) -> Dict[str, Any]:
    """Renders both mono and stereo audio files for a single transcript JSON."""
    with open(transcript_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    call_id = data["id"]
    turns = data.get("turns", [])
    if not turns:
        logger.warning(f"No turns found in {transcript_path}")
        return {}

    mono_path = output_dir / f"{call_id}.mp3"
    stereo_path = output_dir / f"{call_id}_stereo.mp3"

    combined_mono = AudioSegment.empty()
    agent_track = AudioSegment.empty()
    customer_track = AudioSegment.empty()

    for idx, turn in enumerate(turns):
        speaker = turn["speaker"].lower()
        text = turn["text"].strip()
        pause_before = turn.get("pause_before_sec", 0.0)
        interrupts = turn.get("interrupts_previous", False)

        # Determine voice & emotion inflections
        voice = agent_voice if speaker == "agent" else customer_voice
        rate = "+0%"
        pitch = "+0Hz"

        if speaker == "customer":
            text_lower = text.lower()
            is_angry = any(kw in text_lower for kw in ANGRY_KEYWORDS) or (
                data.get("quality") == "bad_deviation" and idx < 4
            )
            if is_angry:
                rate = "+15%"
                pitch = "+5Hz"

        turn_audio = await synthesize_turn_audio(text, voice, rate=rate, pitch=pitch)

        # Handle pause before turn
        if pause_before > 0.0:
            pause_ms = int(pause_before * 1000)
        elif idx > 0:
            pause_ms = random.randint(300, 700)
        else:
            pause_ms = 0

        silence_segment = AudioSegment.silent(duration=pause_ms)

        # Stitch Mono
        if interrupts and len(combined_mono) > 400:
            # Overlap turn ~400ms onto previous turn
            overlap_ms = 400
            base_len = len(combined_mono)
            needed_len = (base_len - overlap_ms) + len(turn_audio)
            if needed_len > base_len:
                combined_mono = combined_mono + AudioSegment.silent(duration=needed_len - base_len)
            combined_mono = combined_mono.overlay(turn_audio, position=base_len - overlap_ms)
        else:
            if pause_ms > 0:
                combined_mono += silence_segment
            combined_mono += turn_audio

        # Stitch Stereo (Agent: Left channel, Customer: Right channel)
        if pause_ms > 0:
            agent_track += silence_segment
            customer_track += silence_segment

        if speaker == "agent":
            agent_track += turn_audio
            customer_track += AudioSegment.silent(duration=len(turn_audio))
        else:
            customer_track += turn_audio
            agent_track += AudioSegment.silent(duration=len(turn_audio))

    # Equalize stereo channel lengths to exact sample frame boundaries
    max_stereo_len = max(len(agent_track), len(customer_track))
    if len(agent_track) < max_stereo_len:
        agent_track += AudioSegment.silent(duration=max_stereo_len - len(agent_track))
    if len(customer_track) < max_stereo_len:
        customer_track += AudioSegment.silent(duration=max_stereo_len - len(customer_track))

    # Match raw byte frames exactly to prevent slice mismatch
    sw = agent_track.sample_width
    min_frames = min(len(agent_track.raw_data) // sw, len(customer_track.raw_data) // sw)
    exact_bytes = min_frames * sw
    agent_aligned = agent_track._spawn(agent_track.raw_data[:exact_bytes])
    customer_aligned = customer_track._spawn(customer_track.raw_data[:exact_bytes])

    combined_stereo = AudioSegment.from_mono_audiosegments(agent_aligned, customer_aligned)

    # Optional light acoustic background noise (-36 dBFS)
    if add_noise:
        noise = WhiteNoise().to_audio_segment(duration=len(combined_mono)).apply_gain(-36)
        combined_mono = combined_mono.overlay(noise)
        noise_stereo = WhiteNoise().to_audio_segment(duration=len(combined_stereo)).apply_gain(-36)
        combined_stereo = combined_stereo.overlay(noise_stereo)

    # Export MP3s
    combined_mono.export(mono_path, format="mp3", bitrate="128k")
    combined_stereo.export(stereo_path, format="mp3", bitrate="128k")

    duration_sec = round(len(combined_mono) / 1000.0, 2)
    logger.info(f"Exported {call_id}.mp3 & {call_id}_stereo.mp3 ({duration_sec}s)")

    return {
        "id": call_id,
        "file_mono": mono_path.name,
        "file_stereo": stereo_path.name,
        "duration_sec": duration_sec,
        "has_noise": add_noise,
        "agent_voice": agent_voice,
        "customer_voice": customer_voice
    }


def main():
    parser = argparse.ArgumentParser(description="Generate synthetic MP3 audio calls from transcripts.")
    parser.add_argument("--id", type=str, default=None, help="Specific transcript ID to process (e.g. call_001)")
    parser.add_argument("--first", type=int, default=None, help="Process first N transcripts")
    parser.add_argument("--all", action="store_true", help="Process all available transcripts")
    parser.add_argument("--noise", action="store_true", help="Add light background white noise")
    parser.add_argument("--agent-voice", type=str, default="en-IN-NeerjaNeural", help="Edge-TTS voice for agent")
    parser.add_argument("--customer-voice", type=str, default="en-IN-PrabhatNeural", help="Edge-TTS voice for customer")
    args = parser.parse_args()

    if not check_ffmpeg():
        sys.exit(1)

    transcripts_dir = REPO_ROOT / "data" / "transcripts"
    audio_dir = REPO_ROOT / "data" / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)

    # Gather target files
    if args.id:
        target_files = [transcripts_dir / f"{args.id}.json"]
    else:
        target_files = sorted(list(transcripts_dir.glob("call_*.json")))
        if args.first:
            target_files = target_files[:args.first]

    if not target_files:
        print("⚠️ No transcripts found to synthesize.")
        sys.exit(0)

    manifest_path = audio_dir / "_audio_manifest.csv"
    existing_manifest = {}
    if manifest_path.exists():
        with open(manifest_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                existing_manifest[row["id"]] = row

    audio_rows = list(existing_manifest.values())

    print(f"🎙️ Starting audio synthesis for {len(target_files)} calls using Edge-TTS...")
    for idx, t_file in enumerate(target_files, start=1):
        call_id = t_file.stem
        mono_out = audio_dir / f"{call_id}.mp3"
        stereo_out = audio_dir / f"{call_id}_stereo.mp3"

        if mono_out.exists() and stereo_out.exists():
            print(f"[{idx}/{len(target_files)}] Skipping existing audio: {call_id}")
            continue

        print(f"[{idx}/{len(target_files)}] Synthesizing audio for {call_id}...")
        try:
            row = asyncio.run(
                render_transcript_audio(
                    transcript_path=t_file,
                    output_dir=audio_dir,
                    agent_voice=args.agent_voice,
                    customer_voice=args.customer_voice,
                    add_noise=args.noise
                )
            )
            if row:
                audio_rows.append(row)
        except Exception as e:
            logger.error(f"Failed to synthesize audio for {call_id}: {e}")

    # Write audio manifest
    with open(manifest_path, "w", newline="", encoding="utf-8") as f:
        fieldnames = ["id", "file_mono", "file_stereo", "duration_sec", "has_noise", "agent_voice", "customer_voice"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(audio_rows)

    print(f"\n✅ Audio generation completed. Manifest saved to {manifest_path}")


if __name__ == "__main__":
    main()
