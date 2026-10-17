"""Validate all generated customer call transcripts against rubric and policy rules."""

import sys
import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Literal
from pydantic import BaseModel, Field, ValidationError

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import yaml

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("validate_transcripts")

# Pydantic Schemas for Strict Validation
class TranscriptTurnSchema(BaseModel):
    i: int
    speaker: Literal["agent", "customer"]
    text: str
    pause_before_sec: float = 0.0
    interrupts_previous: bool = False

class PolicyViolationSchema(BaseModel):
    turn: int
    said: str
    clause_id: str
    severity: Literal["minor", "major", "critical"]
    correct_fact: str

class GroundTruthSchema(BaseModel):
    sop_steps: Dict[str, Literal["followed", "partial", "missed"]]
    policy_violations: List[PolicyViolationSchema] = Field(default_factory=list)
    customer_emotion_arc: List[str]
    gaps: List[str] = Field(default_factory=list)

class FullTranscriptSchema(BaseModel):
    id: str
    topic: str
    quality: Literal["good", "mild_deviation", "bad_deviation"]
    split: Literal["train", "test"]
    verified: bool
    applicable_sops: List[str]
    customer_persona: str
    turns: List[TranscriptTurnSchema]
    ground_truth: GroundTruthSchema


def load_rubric_data() -> Dict[str, Any]:
    rubric_path = REPO_ROOT / "data" / "rubric.yaml"
    with open(rubric_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_all_policy_clauses() -> set:
    clauses = set()
    policies_dir = REPO_ROOT / "data" / "policies"
    import re
    clause_pattern = re.compile(r"###?\s*\[?([A-Z]{3}-\d+\.\d+)\]?")
    for p in policies_dir.glob("*.md"):
        content = p.read_text(encoding="utf-8")
        matches = clause_pattern.findall(content)
        clauses.update(matches)
    return clauses


def validate_all_transcripts():
    transcripts_dir = REPO_ROOT / "data" / "transcripts"
    transcript_files = sorted(list(transcripts_dir.glob("call_*.json")))

    if not transcript_files:
        print("⚠️ No transcript files found in data/transcripts/ to validate.")
        return 0

    rubric = load_rubric_data()
    all_rubric_steps = {s["step_id"]: s for s in rubric.get("sop_steps", [])}
    critical_steps = {s["step_id"] for s in rubric.get("sop_steps", []) if s.get("critical", False)}
    all_policy_clauses = load_all_policy_clauses()

    # SOP to Step ID mappings from rubric
    sop_to_steps = {}
    for s in rubric.get("sop_steps", []):
        sop_file_stem = Path(s["sop_file"]).stem
        sop_to_steps.setdefault(sop_file_stem, set()).add(s["step_id"])

    errors = []
    topic_quality_counts = {}
    verified_count = 0

    for file_path in transcript_files:
        call_id = file_path.stem
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            errors.append(f"[{call_id}] Invalid JSON format: {e}")
            continue

        # 1. Pydantic validation
        try:
            transcript = FullTranscriptSchema.model_validate(data)
        except ValidationError as e:
            errors.append(f"[{call_id}] Pydantic schema validation error:\n{e}")
            continue

        # Tally stats
        topic = transcript.topic
        quality = transcript.quality
        topic_quality_counts.setdefault(topic, {}).setdefault(quality, 0)
        topic_quality_counts[topic][quality] += 1
        if transcript.verified:
            verified_count += 1

        # 2. Consecutive turn index check
        turn_indices = [t.i for t in transcript.turns]
        expected_indices = list(range(1, len(transcript.turns) + 1))
        if turn_indices != expected_indices:
            errors.append(f"[{call_id}] Turns are not indexed consecutively 1..N. Got {turn_indices[:5]}...")

        # 3. Check SOP steps belong to applicable SOPs and exist in rubric
        allowed_steps_for_call = set()
        for sop in transcript.applicable_sops:
            allowed_steps_for_call.update(sop_to_steps.get(sop, set()))

        for step_id, status in transcript.ground_truth.sop_steps.items():
            if step_id not in all_rubric_steps:
                errors.append(f"[{call_id}] Step ID '{step_id}' does not exist in data/rubric.yaml")
            if step_id not in allowed_steps_for_call:
                errors.append(f"[{call_id}] Step ID '{step_id}' does not belong to applicable SOPs {transcript.applicable_sops}")

        # 4. Check policy violation clauses exist in policy markdown files
        # and that violation turn numbers are agent turns
        turn_speaker_map = {t.i: t.speaker for t in transcript.turns}
        for viol in transcript.ground_truth.policy_violations:
            if viol.clause_id not in all_policy_clauses:
                errors.append(f"[{call_id}] Clause ID '{viol.clause_id}' does not exist in data/policies/*.md")
            
            speaker = turn_speaker_map.get(viol.turn)
            if speaker != "agent":
                errors.append(f"[{call_id}] Violation assigned to turn {viol.turn} which is speaker '{speaker}' (must be 'agent')")

        # 5. Quality bucket compliance checks
        gt = transcript.ground_truth
        if quality == "good":
            # All steps must be followed
            non_followed = [s for s, st in gt.sop_steps.items() if st != "followed"]
            if non_followed:
                errors.append(f"[{call_id}] Good call has non-followed steps: {non_followed}")
            if len(gt.policy_violations) > 0:
                errors.append(f"[{call_id}] Good call must have 0 policy violations, found {len(gt.policy_violations)}")

        elif quality == "mild_deviation":
            # No critical step may be missed
            missed_critical = [s for s, st in gt.sop_steps.items() if s in critical_steps and st == "missed"]
            if missed_critical:
                errors.append(f"[{call_id}] Mild deviation call has missed critical step(s): {missed_critical}")
            # Policy violations must only be minor (at most 1)
            bad_viols = [v for v in gt.policy_violations if v.severity in ["major", "critical"]]
            if bad_viols:
                errors.append(f"[{call_id}] Mild deviation call cannot have major/critical violations: {[v.clause_id for v in bad_viols]}")

        elif quality == "bad_deviation":
            # At least 1 critical step missed
            missed_critical = [s for s, st in gt.sop_steps.items() if s in critical_steps and st == "missed"]
            if not missed_critical:
                errors.append(f"[{call_id}] Bad deviation call must have at least 1 missed critical step")
            # And at least 1 major or critical policy violation
            major_crit_viols = [v for v in gt.policy_violations if v.severity in ["major", "critical"]]
            if not major_crit_viols:
                errors.append(f"[{call_id}] Bad deviation call must have at least 1 major/critical policy violation")

    # Output Summary Table
    print("\n" + "=" * 65)
    print(f"📊 TRANSCRIPT VALIDATION SUMMARY ({len(transcript_files)} calls evaluated)")
    print("=" * 65)
    print(f"{'Topic':<15} | {'Good':<8} | {'Mild':<8} | {'Bad':<8} | {'Total':<6}")
    print("-" * 65)

    all_topics = sorted(topic_quality_counts.keys())
    for t in all_topics:
        c_good = topic_quality_counts[t].get("good", 0)
        c_mild = topic_quality_counts[t].get("mild_deviation", 0)
        c_bad = topic_quality_counts[t].get("bad_deviation", 0)
        total = c_good + c_mild + c_bad
        print(f"{t:<15} | {c_good:<8} | {c_mild:<8} | {c_bad:<8} | {total:<6}")

    print("-" * 65)
    print(f"Verified Transcripts: {verified_count} / {len(transcript_files)}")
    print("=" * 65)

    if errors:
        print(f"\n❌ Validation FAILED with {len(errors)} error(s):")
        for err in errors[:25]:
            print(f"  • {err}")
        if len(errors) > 25:
            print(f"  ... and {len(errors) - 25} more errors.")
        return 1

    print("\n✅ All transcripts passed strict validation against rubric and policy schemas!")
    return 0


if __name__ == "__main__":
    exit_code = validate_all_transcripts()
    sys.exit(exit_code)
