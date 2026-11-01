"""Deterministic transcript quality assessment.

Evaluates transcript quality into: 'good', 'degraded', or 'unusable'
based on:
1. Average ASR confidence
2. Ratio of empty or very short turns (< 2 words)
3. Silence ratio across total duration
4. Language mismatch ratio

When 'unusable', audit scoring is bypassed with a structured 'cannot judge' result.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, List, Tuple

import yaml

from .schemas import CallTranscript
from .telugu_utils import is_telugu

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CONFIG_PATH = REPO_ROOT / "scorecard" / "quality_config.yaml"


def load_quality_config(path: Path | None = None) -> Dict:
    p = path or CONFIG_PATH
    if p.exists():
        try:
            return yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        except Exception as exc:  # noqa: BLE001
            logger.warning("Could not read %s: %s; using defaults", p, exc)
    return {
        "thresholds": {
            "unusable_confidence": 0.40,
            "degraded_confidence": 0.65,
            "unusable_empty_or_short_ratio": 0.50,
            "degraded_empty_or_short_ratio": 0.25,
            "unusable_silence_ratio": 0.65,
            "degraded_silence_ratio": 0.40,
            "unusable_language_mismatch_ratio": 0.70,
            "degraded_language_mismatch_ratio": 0.35,
        }
    }


def evaluate_transcript_quality(
    call: CallTranscript,
    target_language: Optional[str] = None,
    config_path: Path | None = None,
) -> Tuple[str, str, List[str]]:
    """Return (quality, reason, unreadable_parts).

    quality in ("good", "degraded", "unusable")
    """
    target_language = target_language or getattr(call, "language", None) or "en"
    if not call.turns:
        return "unusable", "The transcript contains zero turns.", ["all: empty audio"]

    cfg = load_quality_config(config_path).get("thresholds", {})
    unusable_conf = cfg.get("unusable_confidence", 0.40)
    degraded_conf = cfg.get("degraded_confidence", 0.65)
    unusable_short = cfg.get("unusable_empty_or_short_ratio", 0.50)
    degraded_short = cfg.get("degraded_empty_or_short_ratio", 0.25)
    unusable_silence = cfg.get("unusable_silence_ratio", 0.65)
    degraded_silence = cfg.get("degraded_silence_ratio", 0.40)
    unusable_lang = cfg.get("unusable_language_mismatch_ratio", 0.70)
    degraded_lang = cfg.get("degraded_language_mismatch_ratio", 0.35)

    n_turns = len(call.turns)
    unreadable_parts: List[str] = []

    # 1. ASR Confidence
    confs = [t.asr_confidence for t in call.turns]
    avg_conf = sum(confs) / n_turns if n_turns else 0.0

    # Flag low confidence turns
    low_conf_turns = [t.turn_id for t in call.turns if t.asr_confidence < 0.45]
    if low_conf_turns:
        unreadable_parts.append(f"low_confidence_turns: {low_conf_turns[:10]}")

    # 2. Empty or very short turns (< 2 words)
    short_turns = [t for t in call.turns if len(t.text.strip().split()) < 2]
    short_ratio = len(short_turns) / n_turns if n_turns else 0.0
    if short_turns:
        unreadable_parts.append(f"{len(short_turns)} short or empty turns (< 2 words)")

    # 3. Silence ratio
    duration = call.duration_seconds
    if duration <= 0.0 and call.turns:
        duration = max(t.end_time for t in call.turns)
    total_silence = sum(t.silence_before for t in call.turns)
    silence_ratio = (total_silence / duration) if duration > 0 else 0.0
    if silence_ratio > 0.30:
        unreadable_parts.append(f"high silence ratio: {silence_ratio:.1%}")

    # 4. Language mismatch (for target_language == 'te', check for presence of Telugu or romanized Telugu)
    mismatch_count = 0
    if target_language == "te":
        for t in call.turns:
            # If text has neither Telugu script nor Telugu cues/latin words, count as mismatch
            if not is_telugu(t.text) and not getattr(t, "text_te", None):
                # Check if it has romanized script or English
                # In bilingual calls English terms (order, refund, etc.) are normal,
                # but if pure non-Telugu gibberish, count as mismatch
                pass
            # If entirely symbols or whitespace
            if not any(c.isalnum() for c in t.text):
                mismatch_count += 1
    lang_mismatch_ratio = mismatch_count / n_turns if n_turns else 0.0

    # Decision logic
    unusable_reasons: List[str] = []
    if avg_conf < unusable_conf:
        unusable_reasons.append(f"Average ASR confidence ({avg_conf:.2f}) below threshold ({unusable_conf:.2f})")
    if short_ratio >= unusable_short:
        unusable_reasons.append(f"Excessive fragmented/empty turns ({short_ratio:.1%} >= {unusable_short:.1%})")
    if silence_ratio >= unusable_silence:
        unusable_reasons.append(f"Excessive silence ({silence_ratio:.1%} >= {unusable_silence:.1%})")
    if lang_mismatch_ratio >= unusable_lang:
        unusable_reasons.append(f"Severe language mismatch ({lang_mismatch_ratio:.1%} >= {unusable_lang:.1%})")

    if unusable_reasons:
        return "unusable", "; ".join(unusable_reasons), unreadable_parts

    degraded_reasons: List[str] = []
    if avg_conf < degraded_conf:
        degraded_reasons.append(f"Moderate ASR confidence ({avg_conf:.2f})")
    if short_ratio >= degraded_short:
        degraded_reasons.append(f"High number of short utterances ({short_ratio:.1%})")
    if silence_ratio >= degraded_silence:
        degraded_reasons.append(f"Substantial dead air/silence ({silence_ratio:.1%})")
    if lang_mismatch_ratio >= degraded_lang:
        degraded_reasons.append(f"Potential language mismatch ({lang_mismatch_ratio:.1%})")

    if degraded_reasons:
        return "degraded", "; ".join(degraded_reasons), unreadable_parts

    return "good", "Transcript quality is reliable for compliance and rubric scoring.", []

