"""Helpers for locating which agent turn contains a deliberately injected policy mistake."""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Sequence, Tuple

from .rag import STOPWORDS

_NUM_WORDS = {"one": "1", "two": "2", "three": "3", "four": "4", "five": "5", "six": "6", "seven": "7", "eight": "8", "nine": "9", "ten": "10"}


def _tokens(text: str) -> set:
    toks = re.findall(r"[a-z0-9]+", (text or "").lower())
    return {_NUM_WORDS.get(t, t) for t in toks if t not in STOPWORDS and len(t) > 1}


def best_overlap_agent_turn(turns: Sequence[dict], description: str, min_overlap: int = 3) -> Optional[int]:
    """Pick the AGENT turn whose words overlap most with `description` (what the agent wrongly says).

    `turns` are dicts with keys i, speaker, text (the transcript JSON format). Returns the turn id, or None when
    no agent turn overlaps enough: callers must treat None as a failure and never guess a turn.
    """
    want = _tokens(description)
    best: Tuple[int, Optional[int]] = (0, None)
    for t in turns:
        if t["speaker"] != "agent":
            continue
        score = len(want & _tokens(t["text"]))
        if score > best[0]:
            best = (score, t["i"])
    return best[1] if best[0] >= min_overlap else None
