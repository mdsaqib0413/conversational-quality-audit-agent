"""Emotion, sentiment, and conversation dynamics (gaps/silences) analysis module."""

import logging
from typing import List, Dict, Any
from .schemas import CallTranscript, DialogueTurn

logger = logging.getLogger(__name__)

class EmotionAnalyzer:
    """Analyzes sentiment, emotion shift, talk-to-listen ratio, and dead air."""

    def analyze_turns(self, transcript: CallTranscript) -> Dict[str, Any]:
        """Calculates emotional progression and silence anomalies."""
        total_agent_time = 0.0
        total_customer_time = 0.0
        long_silence_gaps = []

        for turn in transcript.turns:
            duration = turn.end_time - turn.start_time
            if turn.speaker == "agent":
                total_agent_time += duration
            else:
                total_customer_time += duration

            # Flag dead air > 4.0 seconds
            if (turn.silence_gap_before or 0.0) >= 4.0:
                long_silence_gaps.append({
                    "turn_id": turn.turn_id,
                    "gap_duration": turn.silence_gap_before,
                    "speaker_after": turn.speaker
                })

            # Heuristic sentiment & emotion labeling
            text_lower = turn.text.lower()
            if any(w in text_lower for w in ["angry", "ridiculous", "horrible", "cheat", "scam", "worst", "unacceptable"]):
                turn.emotion = "angry"
                turn.sentiment_score = -0.8
            elif any(w in text_lower for w in ["frustrated", "delay", "waiting", "disappointed", "problem", "broken"]):
                turn.emotion = "frustrated"
                turn.sentiment_score = -0.4
            elif any(w in text_lower for w in ["thank you", "great", "helpful", "appreciate", "perfect"]):
                turn.emotion = "satisfied"
                turn.sentiment_score = 0.7
            else:
                turn.emotion = "neutral"
                turn.sentiment_score = 0.0

        total_speech_time = total_agent_time + total_customer_time
        talk_ratio = round((total_agent_time / total_speech_time) * 100, 1) if total_speech_time > 0 else 50.0

        return {
            "agent_talk_percent": talk_ratio,
            "customer_talk_percent": round(100.0 - talk_ratio, 1),
            "dead_air_occurrences": len(long_silence_gaps),
            "long_silences": long_silence_gaps,
            "customer_start_emotion": transcript.turns[1].emotion if len(transcript.turns) > 1 else "neutral",
            "customer_end_emotion": transcript.turns[-1].emotion if transcript.turns else "neutral"
        }

# Default singleton
emotion_analyzer = EmotionAnalyzer()
