"""Load labelled transcript JSON files (data/transcripts/*.json) into CallTranscript objects.

The JSON files carry `pause_before_sec` and `interrupts_previous` per turn. We turn them into
timestamps with a speaking-rate model, so timing-based checks (dead air, interruptions, talk ratio)
behave the same on a text transcript as they would on the audio rendering of it.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional, Tuple

from .schemas import CallTranscript, DialogueTurn

WORDS_PER_SECOND = 2.6
OVERLAP_SECONDS = 0.4


def _speech_seconds(text: str) -> float:
    return max(0.8, len(text.split()) / WORDS_PER_SECOND)


def load_transcript_json(path: str | Path) -> Tuple[CallTranscript, dict]:
    path = Path(path)
    raw = json.loads(path.read_text(encoding="utf-8"))
    turns = []
    clock = 0.0
    prev_end = 0.0
    for idx, t in enumerate(raw["turns"], start=1):
        pause = float(t.get("pause_before_sec") or 0.0)
        overlaps = bool(t.get("interrupts_previous"))
        if idx == 1:
            start = 0.0
        elif overlaps:
            start = max(0.0, prev_end - OVERLAP_SECONDS)
        else:
            start = prev_end + pause
        end = start + _speech_seconds(t["text"])
        silence = 0.0 if (idx == 1 or overlaps) else pause
        turns.append(DialogueTurn(
            turn_id=idx, speaker=t["speaker"], start_time=round(start, 2), end_time=round(end, 2),
            text=t["text"], silence_before=round(silence, 2), overlaps_previous=overlaps,
        ))
        prev_end = max(prev_end, end)
    call = CallTranscript(
        call_id=raw.get("id", path.stem), source="transcript", duration_seconds=round(prev_end, 1),
        diarization_method="given", turns=turns,
    )
    return call, raw


def find_transcripts(folder: str | Path, only_verified: bool = False):
    out = []
    for p in sorted(Path(folder).glob("call_*.json")):
        try:
            raw = json.loads(p.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        if only_verified and not raw.get("verified"):
            continue
        out.append(p)
    return out
