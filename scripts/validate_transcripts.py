"""Validate all generated customer call transcripts against rubric, policy rules, and verification contracts."""

import re
import sys
import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Literal
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
    pause_before_sec: float = Field(0.0, description="Pause duration before turn in seconds")
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
    applicable_steps: List[str] = Field(..., description="List of step IDs applicable to this call")
    hold_scenario: Optional[str] = "none"
    customer_name: Optional[str] = None
    agent_name: Optional[str] = None
    order_id: Optional[str] = None
    customer_persona: str
    verification_notes: Optional[str] = None
    turns: List[TranscriptTurnSchema]
    ground_truth: GroundTruthSchema


def load_rubric_data() -> Dict[str, Any]:
    rubric_path = REPO_ROOT / "data" / "rubric.yaml"
    with open(rubric_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_violation_catalog() -> List[Dict[str, Any]]:
    cat_path = REPO_ROOT / "scripts" / "violation_catalog.yaml"
    with open(cat_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data.get("violations", [])


def load_all_policy_clauses() -> set:
    clauses = set()
    policies_dir = REPO_ROOT / "data" / "policies"
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
    catalog_violations = load_violation_catalog()
    catalog_by_clause = {}
    for v in catalog_violations:
        catalog_by_clause.setdefault(v["clause_id"], []).append(v)

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

        # 3. Ground-truth steps MUST match applicable_steps exactly
        gt_steps_set = set(transcript.ground_truth.sop_steps.keys())
        app_steps_set = set(transcript.applicable_steps)

        outside_steps = gt_steps_set - app_steps_set
        if outside_steps:
            errors.append(f"[{call_id}] ground_truth.sop_steps contains steps outside applicable_steps: {outside_steps}")

        missing_app_steps = app_steps_set - gt_steps_set
        if missing_app_steps:
            errors.append(f"[{call_id}] ground_truth.sop_steps is missing steps from applicable_steps: {missing_app_steps}")

        for step_id in gt_steps_set:
            if step_id not in all_rubric_steps:
                errors.append(f"[{call_id}] Step ID '{step_id}' does not exist in data/rubric.yaml")

        # 4. Check for catalog hint text leakage into dialogue
        all_agent_text = " ".join([t.text.lower() for t in transcript.turns if t.speaker == "agent"])
        for cat_v in catalog_violations:
            hint_clean = cat_v["wrong_statement_hint"].lower().strip()
            if hint_clean in all_agent_text:
                errors.append(f"[{call_id}] Hint leakage detected! Verbatim catalog hint found in dialogue: '{cat_v['wrong_statement_hint']}'")

        # Check for meta-phrases
        for bad_prefix in ["agent states that", "agent promises to", "agent tells customer", "agent approves an", "agent assures the"]:
            if bad_prefix in all_agent_text:
                errors.append(f"[{call_id}] Hint leakage detected! Meta-prompt phrase '{bad_prefix}' found in dialogue.")

        # 5. Check policy violations:
        # - clause_id must exist in policy files
        # - violation turn must be an AGENT turn
        # - topic of call must match catalog entry topics (violation/topic mismatch)
        turn_speaker_map = {t.i: t.speaker for t in transcript.turns}
        for viol in transcript.ground_truth.policy_violations:
            if viol.clause_id not in all_policy_clauses:
                errors.append(f"[{call_id}] Clause ID '{viol.clause_id}' does not exist in data/policies/*.md")

            speaker = turn_speaker_map.get(viol.turn)
            if speaker != "agent":
                errors.append(f"[{call_id}] Violation assigned to turn {viol.turn} which is '{speaker}' (must be 'agent')")

            # Check topic mismatch
            matching_cat_entries = catalog_by_clause.get(viol.clause_id, [])
            valid_for_topic = any(topic in entry.get("topics", []) for entry in matching_cat_entries)
            if not valid_for_topic:
                errors.append(
                    f"[{call_id}] Violation topic mismatch! Clause '{viol.clause_id}' is not mapped to topic '{topic}' in violation catalog."
                )

        # 6. Check verified=True without verification record
        if transcript.verified:
            notes = (transcript.verification_notes or "").strip()
            if not notes:
                errors.append(f"[{call_id}] verified=True without a verification record / verification_notes!")
            elif "failed" in notes.lower() and "passed" not in notes.lower():
                errors.append(f"[{call_id}] verified=True but verification_notes indicate failure: '{notes}'")

        # 7. Quality bucket compliance checks
        gt = transcript.ground_truth
        if quality == "good":
            non_followed = [s for s, st in gt.sop_steps.items() if st != "followed"]
            if non_followed:
                errors.append(f"[{call_id}] Good call has non-followed steps: {non_followed}")
            if len(gt.policy_violations) > 0:
                errors.append(f"[{call_id}] Good call must have 0 policy violations, found {len(gt.policy_violations)}")

        elif quality == "mild_deviation":
            missed_critical = [s for s, st in gt.sop_steps.items() if s in critical_steps and st == "missed"]
            if missed_critical:
                errors.append(f"[{call_id}] Mild deviation call has missed critical step(s): {missed_critical}")
            bad_viols = [v for v in gt.policy_violations if v.severity in ["major", "critical"]]
            if bad_viols:
                errors.append(f"[{call_id}] Mild deviation call cannot have major/critical violations: {[v.clause_id for v in bad_viols]}")

        elif quality == "bad_deviation":
            missed_critical = [s for s, st in gt.sop_steps.items() if s in critical_steps and st == "missed"]
            if not missed_critical:
                errors.append(f"[{call_id}] Bad deviation call must have at least 1 missed critical step")
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

    print("\n✅ All transcripts passed strict validation against rubric, policy, and verification schemas!")
    return 0


if __name__ == "__main__":
    exit_code = validate_all_transcripts()
    sys.exit(exit_code)
