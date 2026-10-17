"""Speaker diarization and turn segmentation module."""

import logging
from typing import List, Dict, Any
from .schemas import DialogueTurn, CallTranscript

logger = logging.getLogger(__name__)

class SpeakerDiarizer:
    """Attributes transcribed segments to Agent and Customer dialogue turns."""

    def __init__(self, hf_token: str = None):
        self.hf_token = hf_token

    def diarize_segments(self, segments: List[Dict[str, Any]], call_id: str = "CALL-001") -> CallTranscript:
        """Assigns speakers and calculates silence gaps between turns."""
        turns: List[DialogueTurn] = []
        last_end_time = 0.0

        # Alternating heuristic if speaker labels are not provided by hardware channels
        current_speaker = "agent"
        for idx, seg in enumerate(segments, start=1):
            start = seg.get("start", 0.0)
            end = seg.get("end", start + 2.0)
            text = seg.get("text", "")
            speaker = seg.get("speaker")

            if not speaker:
                # Heuristic: First speaker is usually agent greeting
                speaker = "agent" if idx % 2 != 0 else "customer"

            silence_gap = max(0.0, round(start - last_end_time, 2)) if idx > 1 else 0.0

            turns.append(
                DialogueTurn(
                    turn_id=idx,
                    speaker=speaker,
                    start_time=start,
                    end_time=end,
                    text=text,
                    silence_gap_before=silence_gap
                )
            )
            last_end_time = end

        duration = last_end_time if turns else 0.0
        return CallTranscript(call_id=call_id, duration_seconds=duration, turns=turns)

# Default singleton
diarizer = SpeakerDiarizer()
