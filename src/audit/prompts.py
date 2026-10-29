"""Shared prompt helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

from .schemas import DialogueTurn

AGENTS_DIR = Path(__file__).resolve().parent.parent.parent / "agents"


def _load_agent(filename: str) -> str:
    """Load an agent instruction file from the agents/ directory."""
    path = AGENTS_DIR / filename
    return path.read_text(encoding="utf-8").strip()


def format_transcript(turns: Sequence[DialogueTurn]) -> str:
    """Numbered transcript with timing hints the model cannot hear (silences, overlaps)."""
    lines = []
    for t in turns:
        notes = []
        if t.silence_before >= 2.0:
            notes.append(f"after {t.silence_before:.0f}s silence")
        if t.overlaps_previous:
            notes.append("speaks over previous speaker")
        tag = f" ({', '.join(notes)})" if notes else ""
        m, s = divmod(int(t.start_time), 60)
        lines.append(f"[{t.turn_id}] {m:02d}:{s:02d} {t.speaker.upper()}{tag}: {t.text}")
    return "\n".join(lines)
