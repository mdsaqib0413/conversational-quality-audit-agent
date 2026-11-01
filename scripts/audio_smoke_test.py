"""Check the audio half WITHOUT any API request (speech recognition + stereo speaker separation).

  python scripts/audio_smoke_test.py data/audio/call_001_stereo.mp3     # perfect separation expected
  python scripts/audio_smoke_test.py data/audio/call_001.mp3            # mono: heuristic labels (no LLM here)
  python scripts/audio_smoke_test.py data/audio/call_001_stereo.mp3 --language en
Prints how long transcription took and the first turns, so you can judge speech-to-text quality. If a transcript
JSON with the same id exists, it also prints the word error rate (lower is better).
"""
import argparse
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.audit.diarize import build_call_from_audio  # noqa: E402
from src.audit.transcribe import get_transcriber  # noqa: E402


def wer(ref: str, hyp: str) -> float:
    r, h = re.findall(r"[a-z0-9']+", ref.lower()), re.findall(r"[a-z0-9']+", hyp.lower())
    d = list(range(len(h) + 1))
    for i in range(1, len(r) + 1):
        prev, d[0] = d[0], i
        for j in range(1, len(h) + 1):
            cur = min(d[j] + 1, d[j - 1] + 1, prev + (r[i - 1] != h[j - 1]))
            prev, d[j] = d[j], cur
    return d[len(h)] / max(1, len(r))


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Check audio speech recognition and speaker separation.")
    parser.add_argument("audio_path", help="Path to audio file (.mp3 / .wav)")
    parser.add_argument("--language", default="auto", choices=["auto", "en", "te", "hi"],
                        help="Transcription language (default: auto)")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    path = Path(args.audio_path)
    if not path.exists():
        print(f"Error: audio file not found: {path}")
        return 1
    t0 = time.time()
    call, warnings = build_call_from_audio(
        str(path), path.stem, get_transcriber(), gateway=None,
        progress=lambda s, f, m: print(f"  {m}"),
        language=args.language,
    )
    print(f"\nLanguage used: {call.language}")
    print(f"Transcribed {call.duration_seconds:.0f}s of audio in {time.time() - t0:.0f}s | method: {call.diarization_method} | turns: {len(call.turns)}")
    for w in warnings:
        print("  warning:", w)
    for t in call.turns[:8]:
        print(f"  [{t.turn_id}] {t.speaker:<8} {t.text[:110]}")
    ref_file = ROOT / "data" / "transcripts" / f"{path.stem.replace('_stereo', '')}.json"
    if ref_file.exists():
        ref = " ".join(t["text"] for t in json.loads(ref_file.read_text(encoding="utf-8"))["turns"])
        hyp = " ".join(t.text for t in call.turns)
        print(f"\nWord error rate vs original script: {wer(ref, hyp):.1%}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
