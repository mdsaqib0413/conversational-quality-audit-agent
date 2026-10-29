"""Speech-to-text with faster-whisper (runs locally, free). The model is loaded lazily and only once."""

from __future__ import annotations

import logging
import math
import os
import re
from dataclasses import dataclass
from typing import List, Optional, Tuple

from .telugu_utils import is_telugu, telugu_to_roman

logger = logging.getLogger(__name__)

INITIAL_PROMPT_EN = (
    "Customer support call for ShopEase. Order ID, refund, replacement, warranty, supervisor, "
    "callback, delivery, courier, OTP, UPI, NEFT, Rs."
)

INITIAL_PROMPT_TE = (
    "ShopEase కస్టమర్ సపోర్ట్ కాల్. ఆర్డర్ ఐడి, రిఫండ్, రీప్లేస్మెంట్, వారంటీ, సూపర్వైజర్, "
    "కాల్బ్యాక్, డెలివరీ, కొరియర్, OTP, UPI, NEFT, రూ."
)

_BRAND = re.compile(
    r"\b(?:shop\s?ease|shoppease|shoppiece|shopiece|shoppies|shoppie|shopeas|shoppeace|shop\s?peace|shop\s?pease|షాపేజ్|షాపీజ్)\b",
    re.IGNORECASE,
)
_ORDER_ID = re.compile(r"\bORD[\s\-]?(\d{4,6})\b", re.IGNORECASE)


def normalize_asr(text: str) -> str:
    text = _BRAND.sub("ShopEase", text)
    text = _ORDER_ID.sub(lambda m: f"ORD-{m.group(1)}", text)
    return text.strip()


@dataclass
class Segment:
    start: float
    end: float
    text: str
    text_roman: str = ""
    asr_confidence: float = 1.0  # Average word confidence [0.0 - 1.0] proxy from ASR engine


class Transcriber:
    def __init__(self, model_size: Optional[str] = None, device: str = "cpu", compute_type: str = "int8", default_language: str = "te"):
        self.model_size = model_size or os.getenv("WHISPER_MODEL", "small")
        self.device = device
        self.compute_type = compute_type
        self.default_language = default_language
        self._model = None

    @property
    def model(self):
        if self._model is None:
            from faster_whisper import WhisperModel

            logger.info("Loading faster-whisper model '%s' (%s, %s)...", self.model_size, self.device, self.compute_type)
            self._model = WhisperModel(self.model_size, device=self.device, compute_type=self.compute_type)
        return self._model

    def transcribe(self, audio_path: str, language: Optional[str] = None) -> Tuple[List[Segment], float]:
        lang = language if language is not None else self.default_language
        initial_prompt = INITIAL_PROMPT_TE if lang == "te" else INITIAL_PROMPT_EN

        segments, info = self.model.transcribe(
            audio_path,
            language=lang,
            beam_size=int(os.getenv("WHISPER_BEAM", "1")),
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 300},
            condition_on_previous_text=False,
            initial_prompt=initial_prompt,
            word_timestamps=True,   # real speech boundaries, so silences / dead air are measured correctly
        )
        out = []
        for s in segments:
            text = normalize_asr(s.text or "")
            if not text:
                continue
            start, end = float(s.start), float(s.end)
            words = getattr(s, "words", None) or []
            if words:  # segment boundaries often swallow the silence; word boundaries do not
                start, end = float(words[0].start), float(words[-1].end)
                conf = sum(getattr(w, "probability", 0.9) for w in words) / len(words)
            else:
                avg_lp = getattr(s, "avg_logprob", -0.1)
                try:
                    conf = math.exp(avg_lp)
                except OverflowError:
                    conf = 0.5
            conf = min(1.0, max(0.0, float(conf)))

            text_roman = telugu_to_roman(text) if is_telugu(text) else ""
            out.append(Segment(start=start, end=end, text=text, text_roman=text_roman, asr_confidence=round(conf, 3)))
        return out, float(getattr(info, "duration", 0.0) or (out[-1].end if out else 0.0))


_default: Optional[Transcriber] = None


def get_transcriber(default_language: str = "te") -> Transcriber:
    global _default
    if _default is None:
        _default = Transcriber(default_language=default_language)
    return _default
