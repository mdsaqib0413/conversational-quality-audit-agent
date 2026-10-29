"""Evidence checking: every finding must be backed by words that really appear in the transcript."""

from __future__ import annotations

import re
from typing import List, Optional, Sequence, Tuple

from .schemas import DialogueTurn

_ELLIPSIS = re.compile(r"\.{3,}|\u2026")


def normalize(text: str) -> str:
    t = (text or "").lower().replace("\u2019", "'")
    t = re.sub(r"[^a-z0-9' ]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def _fragment_score(fragment: str, turn_norm: str) -> float:
    f = normalize(fragment)
    if not f:
        return 0.0
    if f in turn_norm:
        return 1.0
    ftoks = f.split()
    if len(ftoks) < 3:
        return 0.0
    ttoks = set(turn_norm.split())
    return sum(1 for w in ftoks if w in ttoks) / len(ftoks)


def quote_score(quote: str, turn_text: str) -> float:
    """1.0 = verbatim (ignoring case/punctuation); 0.75+ = close paraphrase of the same words; 0 = not there."""
    frags = [f for f in _ELLIPSIS.split(quote or "") if normalize(f)]
    if not frags:
        return 0.0
    tn = normalize(turn_text)
    return sum(_fragment_score(f, tn) for f in frags) / len(frags)


def locate_quote(turns: Sequence[DialogueTurn], quote: str, hint_turn: Optional[int] = None,
                 speaker: Optional[str] = None, threshold: float = 0.75) -> Tuple[Optional[int], float]:
    """Find the turn that contains `quote`. Prefers `hint_turn`. Returns (turn_id or None, score)."""
    if not (quote or "").strip():
        return None, 0.0
    by_id = {t.turn_id: t for t in turns}
    if hint_turn in by_id:
        t = by_id[hint_turn]
        if speaker is None or t.speaker == speaker:
            s = quote_score(quote, t.text)
            if s >= threshold:
                return t.turn_id, s
    best: Tuple[Optional[int], float] = (None, 0.0)
    for t in turns:
        if speaker and t.speaker != speaker:
            continue
        s = quote_score(quote, t.text)
        if s > best[1]:
            best = (t.turn_id, s)
    return (best[0], best[1]) if best[1] >= threshold else (None, best[1])
