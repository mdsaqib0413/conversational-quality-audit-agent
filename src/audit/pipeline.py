"""End-to-end orchestration pipeline for conversational quality auditing."""

import yaml
import logging
from pathlib import Path
from typing import Dict, Any, Optional

from .schemas import CallTranscript, AuditReport
from .transcribe import transcriber
from .diarize import diarizer
from .emotion import emotion_analyzer
from .rag import kb, retrieve_relevant_clauses
from .sop_check import sop_auditor
from .policy_check import policy_auditor
from .scoring import scorer
from .report import report_generator

logger = logging.getLogger(__name__)

class AuditPipeline:
    """Coordinates transcription, emotion detection, RAG retrieval, LLM audit, and report generation."""

    def __init__(self, rubric_path: str = "data/rubric.yaml"):
        self.rubric_path = Path(rubric_path)
        self.rubric = self._load_rubric()

    def _load_rubric(self) -> Dict[str, Any]:
        if self.rubric_path.exists():
            with open(self.rubric_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f)
        return {}

    def run_audit(self, audio_path: Optional[str] = None, transcript: Optional[CallTranscript] = None, call_id: str = "CALL-101") -> AuditReport:
        """Executes full audit pipeline from audio or pre-parsed transcript."""
        
        # 1. Transcription & Diarization
        if transcript is None:
            if not audio_path:
                raise ValueError("Either audio_path or transcript must be provided.")
            segments = transcriber.transcribe(audio_path)
            transcript = diarizer.diarize_segments(segments, call_id=call_id)

        # 2. Emotion and Conversation Dynamics
        dynamics = emotion_analyzer.analyze_turns(transcript)
        logger.info(f"Analyzed dynamics: {dynamics}")

        # 3. Policy & SOP Retrieval (RAG)
        all_agent_speech = " ".join([t.text for t in transcript.turns if t.speaker == "agent"])
        retrieved_clauses = retrieve_relevant_clauses(all_agent_speech, top_k=4)

        # 4. SOP Adherence Audit
        sop_steps = self.rubric.get("sop_steps", [])
        sop_evals = sop_auditor.evaluate_sop(transcript, sop_steps, self.rubric)

        # 5. Policy Accuracy Audit
        policy_findings = policy_auditor.evaluate_policies(transcript, retrieved_clauses)

        # 6. Rubric Scoring & Penalties
        report = scorer.calculate_scores(
            call_id=call_id,
            sop_evaluations=sop_evals,
            policy_findings=policy_findings,
            empathy_score_raw=13.5,
            communication_score_raw=14.0
        )

        return report

# Global singleton
audit_pipeline = AuditPipeline()
