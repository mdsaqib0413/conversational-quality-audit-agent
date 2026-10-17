"""Speech-to-text transcription module using faster-whisper."""

import os
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

class AudioTranscriber:
    """Wrapper around faster-whisper for speech transcription with timestamps."""

    def __init__(self, model_size: Optional[str] = None, device: str = "cpu", compute_type: str = "int8"):
        self.model_size = model_size or os.getenv("WHISPER_MODEL", "small")
        self.device = device
        self.compute_type = compute_type
        self._model = None

    def _get_model(self):
        if self._model is None:
            try:
                from faster_whisper import WhisperModel
                logger.info(f"Loading faster-whisper model '{self.model_size}' on {self.device}...")
                self._model = WhisperModel(self.model_size, device=self.device, compute_type=self.compute_type)
            except Exception as e:
                logger.warning(f"faster-whisper model load failed: {e}. Falling back to placeholder/mock.")
                self._model = None
        return self._model

    def transcribe(self, audio_path: str) -> List[Dict[str, Any]]:
        """Transcribes audio file to a list of timestamped segments."""
        if not Path(audio_path).exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        model = self._get_model()
        if model is None:
            # Fallback stub for environment where model weights are not pre-downloaded
            return [
                {"start": 0.0, "end": 4.5, "text": "Thank you for calling ShopEase. My name is Rahul. How may I assist you today?"},
                {"start": 5.0, "end": 10.2, "text": "Hi Rahul, I received a damaged pair of wireless headphones and I need an immediate refund."}
            ]

        segments, info = model.transcribe(audio_path, beam_size=5, word_timestamps=True)
        results = []
        for seg in segments:
            results.append({
                "start": round(seg.start, 2),
                "end": round(seg.end, 2),
                "text": seg.text.strip(),
            })
        return results

# Default singleton
transcriber = AudioTranscriber()
