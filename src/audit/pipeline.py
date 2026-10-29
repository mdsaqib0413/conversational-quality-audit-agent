"""End-to-end orchestration.

audio (mp3/wav) --> transcribe + speaker separation --> metrics + topic (no LLM)
   --> LLM request 1: SOP steps + empathy/communication + emotions + gaps
   --> LLM request 2: policy compliance against retrieved clauses (RAG)
   --> deterministic scoring --> AuditReport

A transcript JSON skips the audio stage. Results are cached on disk (keyed by transcript text, model and
knowledge-base version), so re-running or demoing the same call costs zero API requests.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, List, Optional

from .call_state import compute_call_state
from .emotion import build_emotion_arc, build_tone_arc, compute_metrics
from .evidence import locate_quote
from .llm import LLMGateway, gemini_gateway
from .policy_check import check_policies
from .quality import evaluate_transcript_quality
from .rag import KnowledgeBase, get_kb
from .review import apply_reviews_to_report
from .schemas import (AuditFinding, AuditMeta, AuditReport, CallTranscript, CoachingItem,
                      ConversationAnalysis, EvidenceItem, GapResult, PolicyResult, SOPResult,
                      ScoreBreakdown)
from .scoring import score_audit
from .sop_check import analyze_conversation
from .topic import candidate_step_ids, detect_topic
from .transcript_io import load_transcript_json

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CACHE_ROOT = REPO_ROOT / "data" / "cache"
AUDIO_EXT = {".mp3", ".wav", ".m4a", ".flac", ".ogg", ".aac", ".wma"}

Progress = Optional[Callable[[str, float, str], None]]


def _emit(progress: Progress, stage: str, frac: float, msg: str) -> None:
    if progress:
        try:
            progress(stage, frac, msg)
        except Exception:  # noqa: BLE001
            pass


class AuditPipeline:
    def __init__(self, kb: Optional[KnowledgeBase] = None, gateway: Optional[LLMGateway] = None,
                 transcriber=None, cache_dir: Optional[Path] = None):
        self.kb = kb or get_kb()
        self.gateway = gateway or gemini_gateway
        self._transcriber = transcriber
        self.cache_dir = Path(cache_dir) if cache_dir else CACHE_ROOT

    @property
    def transcriber(self):
        if self._transcriber is None:
            from .transcribe import get_transcriber

            self._transcriber = get_transcriber()
        return self._transcriber

    # ------------------------------------------------------------------ caching
    def _audit_key(self, call: CallTranscript) -> str:
        h = hashlib.sha256()
        h.update(call.text_for_hash().encode("utf-8"))
        h.update(self.gateway.model_name.encode("utf-8") if self.gateway.targets else b"")
        h.update(self.kb.version.encode("utf-8"))
        h.update(b"audit-v7")
        return h.hexdigest()[:16]

    def _audit_cache_path(self, call: CallTranscript) -> Path:
        return self.cache_dir / "audits" / f"{call.call_id}_{self._audit_key(call)}.json"

    # ------------------------------------------------------------------ audio -> transcript
    def transcribe_audio(self, audio_path: str, call_id: Optional[str] = None, use_cache: bool = True,
                         progress: Progress = None, language: Optional[str] = None):
        from .diarize import build_call_from_audio

        path = Path(audio_path)
        call_id = call_id or path.stem
        if not language:
            language = "en" if (call_id.startswith("en_") or "en_real" in path.name) else "te"
        file_hash = hashlib.sha256(path.read_bytes()).hexdigest()[:16]
        tcache = self.cache_dir / "transcripts" / f"{call_id}_{file_hash}_{language}_v7.json"
        if not tcache.exists():
            for alt in [
                self.cache_dir / "transcripts" / f"{call_id}_{file_hash}_v6.json",
                CACHE_ROOT / "transcripts" / f"{call_id}_{file_hash}_{language}_v7.json",
                CACHE_ROOT / "transcripts" / f"{call_id}_{file_hash}_v6.json",
            ]:
                if alt.exists():
                    tcache = alt
                    break
        if use_cache and tcache.exists():
            data = json.loads(tcache.read_text(encoding="utf-8"))
            cached_call = CallTranscript.model_validate(data["call"])
            if not cached_call.diarization_method.startswith("heuristic"):  # never reuse low-confidence speaker labels
                _emit(progress, "transcribe", 0.5, "Using cached transcript for this audio file.")
                return cached_call, data.get("warnings", []), 0.0
        t0 = time.time()
        _emit(progress, "transcribe", 0.05, "Loading speech model...")
        call, warnings = build_call_from_audio(str(path), call_id, self.transcriber, self.gateway, progress, language=language)
        elapsed = time.time() - t0
        if not call.diarization_method.startswith("heuristic"):
            tcache.parent.mkdir(parents=True, exist_ok=True)
            tcache.write_text(json.dumps({"call": call.model_dump(), "warnings": warnings}), encoding="utf-8")
        return call, warnings, elapsed

    # ------------------------------------------------------------------ main entry points
    def audit_audio(self, audio_path: str, call_id: Optional[str] = None, use_cache: bool = True,
                    progress: Progress = None, source_set: str = "synthetic",
                    policy_applicable: bool = True, language: Optional[str] = None) -> AuditReport:
        path = Path(audio_path)
        call_id = call_id or path.stem
        if not language:
            language = "en" if (call_id.startswith("en_") or "en_real" in path.name) else "te"
        call, warnings, t_secs = self.transcribe_audio(audio_path, call_id, use_cache, progress, language=language)
        report = self.audit_call(call, use_cache=use_cache, progress=progress, extra_warnings=warnings,
                                 source_set=source_set, policy_applicable=policy_applicable)
        report.meta.transcribe_seconds = round(t_secs, 1)
        return report

    def audit_transcript_file(self, path: str, use_cache: bool = True, progress: Progress = None) -> AuditReport:
        call, _ = load_transcript_json(path)
        return self.audit_call(call, use_cache=use_cache, progress=progress)

    def audit_call(self, call: CallTranscript, use_cache: bool = True, progress: Progress = None,
                   extra_warnings: Optional[List[str]] = None, source_set: str = "synthetic",
                   policy_applicable: bool = True) -> AuditReport:
        if not call.turns:
            raise ValueError("The transcript has no turns.")
        cache_path = self._audit_cache_path(call)
        if use_cache and cache_path.exists():
            try:
                cached = AuditReport.model_validate_json(cache_path.read_text(encoding="utf-8"))
                cached.meta.cache_hit = True
                _emit(progress, "done", 1.0, "Loaded the saved audit for this call (no API requests used).")
                return apply_reviews_to_report(cached)
            except Exception:  # noqa: BLE001
                logger.warning("Ignoring unreadable cache file %s", cache_path)

        t0 = time.time()
        req0 = self.gateway.request_count
        warnings: List[str] = list(extra_warnings or [])
        rubric = self.kb.rubric

        # Step 1 Quality Gating
        quality, q_reason, unreadable = evaluate_transcript_quality(call, target_language=getattr(call, "language", "te"))
        call.transcript_quality = quality
        call.quality_reason = q_reason
        call.unreadable_parts = unreadable

        if quality == "unusable":
            _emit(progress, "done", 1.0, f"Cannot judge audit: transcript quality unusable ({q_reason}).")
            scores = ScoreBreakdown(
                sop_score=0.0, policy_score=0.0, empathy_score=0.0, communication_score=0.0,
                overall_before_cap=0.0, overall=0.0, grade="D", grade_label="Failing / Critical Infraction",
                critical_failure=True, cap_reasons=[f"Unusable audio/transcript quality: {q_reason}"]
            )
            report = AuditReport(
                call_id=call.call_id, generated_at=datetime.now().isoformat(timespec="seconds"),
                topic="unknown", topic_confidence=0.0, summary="Cannot judge: transcript quality is unusable.",
                customer_issue="Audio quality unusable", resolved=False,
                cannot_judge=True, cannot_judge_reason=q_reason, unreadable_parts=unreadable,
                scores=scores, transcript=call,
                meta=AuditMeta(
                    model=self.gateway.describe() if self.gateway.targets else "",
                    llm_requests=0, diarization_method=call.diarization_method,
                    audit_seconds=round(time.time() - t0, 1), warnings=[f"Audit halted: {q_reason}"],
                    source_set=source_set,
                )
            )
            return apply_reviews_to_report(report)

        # Step 5 Running early call state
        call_state = compute_call_state(call.turns)

        _emit(progress, "topic", 0.55, "Detecting call topic and situation...")
        metrics = compute_metrics(call)
        topic = detect_topic(call.turns)
        step_ids = candidate_step_ids(self.kb, topic.topic, topic.signals)

        _emit(progress, "sop", 0.65, f"Judging {len(step_ids)} SOP steps, empathy and emotions...")
        analysis, sop_results, w1 = analyze_conversation(call, topic.topic, topic.signals, step_ids, self.kb, self.gateway, call_state=call_state)
        warnings += w1

        _emit(progress, "policy", 0.82, "Retrieving policies and checking what the agent promised...")
        policy_results, w2, clauses = check_policies(call, topic.topic, self.kb, self.gateway)
        warnings += w2

        _emit(progress, "score", 0.95, "Scoring and building the report...")
        emotions = self._apply_emotions(call, analysis)
        arc = build_emotion_arc(call.turns, emotions)
        tone_arc = build_tone_arc(call.turns, self._apply_tones(call, analysis))
        gaps = self._build_gaps(call, analysis, metrics, sop_results)
        comm = (analysis.clarity_score + analysis.professionalism_score + analysis.ownership_score + analysis.closure_score) / 4
        agent_dead_air = sum(1 for g in metrics.dead_air_events if "not penalised" not in g.detail)
        scores = score_audit(sop_results, policy_results, analysis.empathy_score, comm, rubric,
                             dead_air_events=agent_dead_air, agent_interruptions=metrics.agent_interruptions,
                             policy_applicable=policy_applicable)
        scores.empathy_rating, scores.clarity_rating = analysis.empathy_score, analysis.clarity_score
        scores.professionalism_rating, scores.ownership_rating = analysis.professionalism_score, analysis.ownership_score
        scores.closure_rating = analysis.closure_score

        # Enforce Critical Failure Cap if call_state detected identity breach
        if call_state.identity_breach_detected and not scores.critical_failure:
            scores.critical_failure = True
            scores.cap_reasons.append(
                f"Critical failure: Account details discussed at turn {call_state.first_account_turn} before identity verification completed."
            )
            scores.overall = min(scores.overall, 70.0)

        # Build Step 3 Structured Findings (Observed vs Inferred)
        findings = self._build_structured_findings(call, sop_results, policy_results, analysis, metrics, call_state, quality)

        report = AuditReport(
            call_id=call.call_id, generated_at=datetime.now().isoformat(timespec="seconds"),
            topic=topic.topic, topic_confidence=topic.confidence, signals=topic.signals,
            summary=analysis.summary, customer_issue=analysis.customer_issue, resolved=analysis.resolved,
            scores=scores, sop_results=sop_results, policy_results=policy_results, gaps=gaps,
            findings=findings, emotion=arc, agent_tone=tone_arc,
            metrics=metrics, strengths=[] if analysis.risk_flags else self._strengths(analysis, sop_results),
            coaching=self._coaching(sop_results, policy_results, analysis),
            risk_flags=analysis.risk_flags,
            retrieved_clause_ids=[c.id for c in clauses] if clauses else [],
            transcript=call,
            meta=AuditMeta(
                model=self.gateway.describe() if self.gateway.targets else "", llm_requests=self.gateway.request_count - req0,
                diarization_method=call.diarization_method, audit_seconds=round(time.time() - t0, 1), warnings=warnings,
                source_set=source_set,
            ),
        )

        # Apply human reviews if any
        report = apply_reviews_to_report(report)

        try:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(report.model_dump_json(indent=1), encoding="utf-8")
        except Exception:  # noqa: BLE001
            pass
        _emit(progress, "done", 1.0, "Audit complete.")
        return report

    # ------------------------------------------------------------------ helpers
    @staticmethod
    def _apply_emotions(call: CallTranscript, analysis: ConversationAnalysis) -> Dict[int, str]:
        valid = {t.turn_id for t in call.turns if t.speaker == "customer"}
        emotions = {e.turn: e.emotion for e in analysis.turn_emotions if e.turn in valid}
        for t in call.turns:
            if t.turn_id in emotions:
                t.emotion = emotions[t.turn_id]
        return emotions

    @staticmethod
    def _apply_tones(call: CallTranscript, analysis: ConversationAnalysis) -> Dict[int, str]:
        valid = {t.turn_id for t in call.turns if t.speaker == "agent"}
        tones = {e.turn: e.tone for e in analysis.agent_tones if e.turn in valid}
        for t in call.turns:
            if t.turn_id in tones:
                t.emotion = tones[t.turn_id]
        return tones

    @staticmethod
    def _build_gaps(call: CallTranscript, analysis: ConversationAnalysis, metrics, sop_results=()) -> List[GapResult]:
        gaps: List[GapResult] = list(metrics.dead_air_events) + list(metrics.interruption_events) + list(metrics.hold_events)
        for g in analysis.gaps:
            if g.gap_type in ("dead_air", "interruption"):
                continue
            turn, _ = locate_quote(call.turns, g.quote, hint_turn=g.turn or None)
            gaps.append(GapResult(gap_type=g.gap_type, turn=turn, quote=g.quote if turn else "", detail=g.detail, source="llm"))
        missed = {r.step_id for r in sop_results if r.status == "missed"}
        have = {g.gap_type for g in gaps}
        derived = []
        if ("GEN-05" in missed or "ANG-02" in missed) and "no_empathy" not in have:
            derived.append(("no_empathy", "The agent did not acknowledge how the customer felt (script step missed)."))
        if "GEN-07" in missed and "no_summary" not in have:
            derived.append(("no_summary", "The agent did not recap what was agreed (script step missed)."))
        if "GEN-08" in missed and "no_closing" not in have:
            derived.append(("no_closing", "The call ended without a proper sign-off (script step missed)."))
        for gt, detail in derived:
            gaps.append(GapResult(gap_type=gt, turn=None, quote="", detail=detail, source="script"))
        return gaps

    @staticmethod
    def _strengths(analysis: ConversationAnalysis, sop: List[SOPResult]) -> List[str]:
        out = [s.strip() for s in analysis.strengths if s.strip()][:4]
        crit = [r for r in sop if r.critical and r.status != "not_applicable"]
        if crit and all(r.status == "followed" for r in crit):
            out.append(f"Completed all {len(crit)} critical SOP steps that applied to this call.")
        return out

    @staticmethod
    def _coaching(sop: List[SOPResult], policy: List[PolicyResult], analysis: ConversationAnalysis) -> List[CoachingItem]:
        items: List[CoachingItem] = []
        for r in sorted(sop, key=lambda r: (not r.critical, -r.weight)):
            if r.status in ("missed", "partial") and len(items) < 4:
                advice = r.what_good_looks_like
                if r.example_phrase:
                    advice += f' Example: "{r.example_phrase}"'
                items.append(CoachingItem(title=f"{r.step_id}: {r.title}" + (" (critical)" if r.critical else ""),
                                          advice=advice.strip(), source="sop",
                                          evidence=(f"Missing: {r.missing}. " if r.missing else "") + r.reason))
        for p in policy:
            if p.verdict == "violation":
                items.append(CoachingItem(title=f"Policy {p.clause_id}: say it correctly", advice=p.explanation,
                                          source="policy", evidence=p.quote))
        for tip in analysis.coaching_tips[:3]:
            if tip.strip():
                items.append(CoachingItem(title="Suggestion", advice=tip.strip(), source="llm"))
        return items[:9]

    @staticmethod
    def _build_structured_findings(
        call: CallTranscript,
        sop_results: List[SOPResult],
        policy_results: List[PolicyResult],
        analysis: ConversationAnalysis,
        metrics,
        call_state,
        quality: str,
    ) -> List[AuditFinding]:
        findings: List[AuditFinding] = []
        by_turn = {t.turn_id: t for t in call.turns}

        # 1. SOP findings
        for idx, r in enumerate(sop_results, start=1):
            is_inferred = r.step_id in ("GEN-05", "ANG-01", "ANG-02")
            evidence_items: List[EvidenceItem] = []
            certainty = "high"
            certainty_reason = ""

            if r.turn and r.turn in by_turn:
                t = by_turn[r.turn]
                evidence_items.append(EvidenceItem(
                    turn_id=t.turn_id, speaker=t.speaker, start_s=t.start_time, end_s=t.end_time, quote=r.quote
                ))
            elif r.quote:
                evidence_items.append(EvidenceItem(turn_id=r.turn or 0, quote=r.quote))

            if not r.evidence_verified:
                certainty = "low"
                certainty_reason = "Quoted evidence could not be verified verbatim in cited turn"
            elif quality == "degraded":
                certainty = "medium"
                certainty_reason = f"Degraded transcript: {call.quality_reason}"

            findings.append(AuditFinding(
                finding_id=f"sop_{r.step_id}_{idx}",
                criterion_id=r.step_id,
                name=r.title or r.step_id,
                kind="inferred" if is_inferred else "observed",
                verdict=r.status,
                severity="critical" if r.critical else ("major" if r.mandatory else "minor"),
                evidence=evidence_items,
                certainty=certainty,
                certainty_reason=certainty_reason,
                explanation=r.reason,
            ))

        # 2. Hold Handling multi-hold evidence (Scenario B)
        if metrics and metrics.holds and len(metrics.holds) >= 2:
            hold_evidence = [
                EvidenceItem(
                    turn_id=h.start_turn,
                    speaker="agent",
                    start_s=h.start_time,
                    end_s=h.end_time,
                    quote=f"Hold duration: {h.seconds:.1f}s (turns {h.start_turn}-{h.end_turn})" + (" [EXCEEDED 120s]" if h.exceeded else "")
                )
                for h in metrics.holds
            ]
            findings.append(AuditFinding(
                finding_id="hold_handling_multi",
                criterion_id="hold_handling",
                name="Hold & Transfer Protocol Adherence",
                kind="observed",
                verdict="followed" if not any(h.exceeded for h in metrics.holds) else "missed",
                severity="major",
                evidence=hold_evidence,
                certainty="high",
                explanation=f"{len(metrics.holds)} hold intervals verified from audio timestamps.",
            ))

        # 3. Ambiguous customer closure finding (Scenario B)
        for t in call.turns[-5:]:
            if t.speaker == "customer" and re.search(r"\b(sare,?\s*chuddam\s*le|సరే,?\s*చూద్దాం\s*లే)\b", t.text, re.IGNORECASE):
                findings.append(AuditFinding(
                    finding_id="ambiguous_closure_le",
                    criterion_id="closure_and_next_steps",
                    name="Ambiguous Customer Closure ('sare, chuddam le')",
                    kind="inferred",
                    verdict="partial",
                    severity="minor",
                    evidence=[EvidenceItem(turn_id=t.turn_id, speaker="customer", start_s=t.start_time, end_s=t.end_time, quote=t.text)],
                    certainty="medium",
                    certainty_reason="Colloquial ambiguous closure ('sare, chuddam le') indicates hesitation and unresolved doubt, not confirmed satisfaction",
                    explanation="Customer concluded with 'sare, chuddam le' ('we'll see'); issue cannot be recorded as fully satisfied.",
                ))
                break

        # 4. Policy violations
        for idx, p in enumerate(policy_results, start=1):
            if p.verdict == "violation":
                ev = [EvidenceItem(turn_id=p.turn or 0, quote=p.quote)] if p.quote else []
                findings.append(AuditFinding(
                    finding_id=f"policy_{p.clause_id}_{idx}",
                    criterion_id=p.clause_id,
                    name=p.policy_title or f"Policy {p.clause_id}",
                    kind="observed",
                    verdict="violation",
                    severity=p.severity,
                    evidence=ev,
                    certainty="high" if p.evidence_verified else "low",
                    certainty_reason="" if p.evidence_verified else "Quote unverified",
                    explanation=p.explanation,
                ))

        # 5. Empathy / Tone ratings (strictly inferred)
        findings.append(AuditFinding(
            finding_id="empathy_rating",
            criterion_id="empathy_and_communication",
            name="Empathy & Tone Assessment",
            kind="inferred",
            verdict="followed" if analysis.empathy_score >= 4 else ("partial" if analysis.empathy_score >= 2 else "missed"),
            severity="minor",
            evidence=[EvidenceItem(turn_id=0, quote=analysis.empathy_evidence)] if analysis.empathy_evidence else [],
            certainty="medium",
            certainty_reason="Subjective appraisal of agent warmth and emotional validation",
            explanation=f"Empathy score: {analysis.empathy_score}/5",
        ))

        return findings


def run_audit(source: str, **kw) -> AuditReport:
    """Convenience: path to an audio file or a transcript JSON."""
    pipe = AuditPipeline()
    ext = Path(source).suffix.lower()
    if ext == ".json":
        return pipe.audit_transcript_file(source, **kw)
    if ext in AUDIO_EXT:
        return pipe.audit_audio(source, **kw)
    raise ValueError(f"Unsupported file type: {ext}")
