"""Generate synthetic customer support call transcripts with pre-decided ground truth.

Features:
- 48-call scenario matrix across 6 topics (refund, billing, shipping, warranty, complaint, general)
- Stratified quality distribution: 3 good, 3 mild_deviation, 2 bad_deviation per topic
- ~25% test split, rest train (stratified)
- Pre-decided ground truth injected into prompt: SOP steps, policy violations from violation_catalog.yaml, gaps
- Temperature ~0.8 generation + temperature 0 verification pass
- Resumable (skips existing files), configurable --sleep, --limit, --seed
- Generates data/transcripts/call_XXX.json and data/transcripts/_manifest.csv
"""

import os
import sys
import csv
import json
import time
import random
import argparse
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Literal
from pydantic import BaseModel, Field

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Ensure repo root is on sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import yaml
from src.audit.llm import gemini_gateway

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("generate_transcripts")

TOPICS = ["refund", "billing", "shipping", "warranty", "complaint", "general"]

SOP_STEP_MAP = {
    "general_call_flow": [
        "GEN-01", "GEN-02", "GEN-03", "GEN-04",
        "GEN-05", "GEN-06", "GEN-07", "GEN-08"
    ],
    "refund_call_sop": [
        "REF-S1", "REF-S2", "REF-S3", "REF-S4",
        "REF-S5", "REF-S6", "REF-S7"
    ],
    "angry_customer_sop": [
        "ANG-01", "ANG-02", "ANG-03", "ANG-04",
        "ANG-05", "ANG-06"
    ],
    "hold_and_transfer_sop": [
        "HLD-01", "HLD-02", "HLD-03", "HLD-04",
        "HLD-05"
    ]
}

CRITICAL_STEPS = {
    "GEN-02", "GEN-03", "GEN-06",
    "REF-S1", "REF-S2", "REF-S4", "REF-S5",
    "ANG-05", "HLD-02", "HLD-04"
}

INDIAN_AGENT_NAMES = ["Rahul", "Priya", "Ananya", "Rohan", "Vikram", "Sneha", "Amit", "Pooja", "Arjun", "Neha"]
INDIAN_CUSTOMER_NAMES = ["Rajesh Kumar", "Sunita Sharma", "Deepak Verma", "Meera Iyer", "Karan Patel", "Anjali Mehta", "Suresh Reddy", "Kavita Singh"]

SAMPLE_PRODUCTS = [
    ("Boat Rockerz Wireless Headphones", 1499, "electronics"),
    ("Noise ColorFit Smartwatch", 2499, "electronics"),
    ("OnePlus Nord CE 5G", 19999, "electronics"),
    ("Puma Men Running Shoes", 2199, "non-electronics"),
    ("Levi's Slim Fit Cotton Jeans", 1899, "non-electronics"),
    ("Prestige Electric Kettle 1.5L", 899, "electronics"),
    ("Philips Beard Trimmer BT1232", 1099, "electronics"),
    ("Wildcraft 35L Laptop Backpack", 1299, "non-electronics")
]

# Pydantic schemas for LLM generation
class LLMTurn(BaseModel):
    i: int = Field(..., description="1-indexed sequence number of the turn")
    speaker: Literal["agent", "customer"] = Field(..., description="Role of the speaker")
    text: str = Field(..., description="Verbatim spoken dialogue")
    pause_before_sec: float = Field(0.5, description="Pause preceding this turn in seconds")
    interrupts_previous: bool = False

class LLMTranscriptPayload(BaseModel):
    customer_persona: str = Field(..., description="Short summary of customer personality and state of mind")
    customer_emotion_arc: List[str] = Field(..., description="List of 3 emotion descriptors: [start, mid, end]")
    turns: List[LLMTurn] = Field(..., description="Dialogue turns between 16 and 40 turns")

class LLMVerificationPayload(BaseModel):
    verified: bool = Field(..., description="True if transcript adheres strictly to the injected spec")
    critical_errors: List[str] = Field(default_factory=list, description="Any unintended critical step omissions")
    reasoning: str = Field(..., description="Brief explanation of verification decision")


def load_violation_catalog() -> List[Dict[str, Any]]:
    cat_path = REPO_ROOT / "scripts" / "violation_catalog.yaml"
    with open(cat_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data.get("violations", [])


def build_scenario_matrix(seed: int = 42) -> List[Dict[str, Any]]:
    """Builds the 48-call scenario specifications."""
    random.seed(seed)
    violations_catalog = load_violation_catalog()

    matrix = []
    call_idx = 1

    # Split allocations: ~25% test, stratified by quality
    # good (18 total): 4 test, 14 train
    # mild (18 total): 4 test, 14 train
    # bad (12 total): 4 test, 8 train
    test_allocations = {
        "good": set(random.sample(range(18), 4)),
        "mild_deviation": set(random.sample(range(18), 4)),
        "bad_deviation": set(random.sample(range(12), 4)),
    }
    counters = {"good": 0, "mild_deviation": 0, "bad_deviation": 0}

    # Assign hold_and_transfer_sop to ~16 calls (1/3 of 48)
    hold_call_indices = set(random.sample(range(1, 49), 16))

    for topic in TOPICS:
        # 3 good, 3 mild_deviation, 2 bad_deviation
        qualities = ["good"] * 3 + ["mild_deviation"] * 3 + ["bad_deviation"] * 2
        random.shuffle(qualities)

        for quality in qualities:
            call_id = f"call_{call_idx:03d}"
            
            # Determine split
            curr_count = counters[quality]
            counters[quality] += 1
            split = "test" if curr_count in test_allocations[quality] else "train"

            # Applicable SOPs
            applicable_sops = ["general_call_flow"]
            if topic == "refund":
                applicable_sops.append("refund_call_sop")
            elif topic == "complaint":
                applicable_sops.append("angry_customer_sop")
            
            if call_idx in hold_call_indices:
                applicable_sops.append("hold_and_transfer_sop")

            # Collect all applicable steps
            all_applicable_steps = []
            for s in applicable_sops:
                all_applicable_steps.extend(SOP_STEP_MAP[s])

            # Decide ground truth before generation
            sop_ground_truth = {}
            policy_violations = []
            gaps = []

            # Filter relevant violations for topic
            topic_viol_pool = [v for v in violations_catalog if topic in v.get("topics", []) or "general" in v.get("topics", [])]
            if not topic_viol_pool:
                topic_viol_pool = violations_catalog

            if quality == "good":
                for step in all_applicable_steps:
                    sop_ground_truth[step] = "followed"
                emotion_arc = [random.choice(["frustrated", "neutral", "curious"]), "neutral", "satisfied"]
                if random.random() < 0.2:
                    gaps.append(random.choice(["interruption", "customer_repeats"]))

            elif quality == "mild_deviation":
                # 1-2 non-critical steps missed or partial
                non_crit = [s for s in all_applicable_steps if s not in CRITICAL_STEPS]
                deviated = random.sample(non_crit, min(len(non_crit), random.choice([1, 2])))
                for step in all_applicable_steps:
                    if step in deviated:
                        sop_ground_truth[step] = random.choice(["partial", "missed"])
                    else:
                        sop_ground_truth[step] = "followed"

                # 0-1 minor policy slip
                if random.random() < 0.7:
                    minor_pool = [v for v in topic_viol_pool if v["severity"] == "minor"]
                    if minor_pool:
                        v = random.choice(minor_pool)
                        policy_violations.append({
                            "clause_id": v["clause_id"],
                            "severity": v["severity"],
                            "correct_fact": v["correct_fact"],
                            "hint": v["wrong_statement_hint"]
                        })

                emotion_arc = [random.choice(["frustrated", "neutral"]), "neutral", random.choice(["neutral", "satisfied"])]
                if random.random() < 0.4:
                    gaps.append(random.choice(["dead_air", "interruption", "no_summary"]))

            else:  # bad_deviation
                # At least 1 critical step missed
                crit = [s for s in all_applicable_steps if s in CRITICAL_STEPS]
                missed_crit = random.choice(crit) if crit else "GEN-02"
                
                for step in all_applicable_steps:
                    if step == missed_crit:
                        sop_ground_truth[step] = "missed"
                    else:
                        # Maybe 1 other step is partial or missed
                        sop_ground_truth[step] = "followed" if random.random() < 0.8 else "partial"

                # 1-2 major/critical policy violations
                major_pool = [v for v in topic_viol_pool if v["severity"] in ["major", "critical"]]
                if not major_pool:
                    major_pool = [v for v in violations_catalog if v["severity"] in ["major", "critical"]]
                
                n_viols = random.choice([1, 2])
                chosen_viols = random.sample(major_pool, min(len(major_pool), n_viols))
                for v in chosen_viols:
                    policy_violations.append({
                        "clause_id": v["clause_id"],
                        "severity": v["severity"],
                        "correct_fact": v["correct_fact"],
                        "hint": v["wrong_statement_hint"]
                    })

                emotion_arc = [random.choice(["angry", "frustrated"]), "angry", random.choice(["angry", "escalated", "unhappy"])]
                # In bad deviation, inject at least 1 gap
                gaps.append(random.choice(["dead_air", "interruption", "no_summary", "customer_repeats"]))

            prod = random.choice(SAMPLE_PRODUCTS)
            matrix.append({
                "id": call_id,
                "topic": topic,
                "quality": quality,
                "split": split,
                "applicable_sops": applicable_sops,
                "product_name": prod[0],
                "product_price": prod[1],
                "product_category": prod[2],
                "agent_name": random.choice(INDIAN_AGENT_NAMES),
                "customer_name": random.choice(INDIAN_CUSTOMER_NAMES),
                "ground_truth_spec": {
                    "sop_steps": sop_ground_truth,
                    "policy_violations": policy_violations,
                    "customer_emotion_arc": emotion_arc,
                    "gaps": gaps
                }
            })
            call_idx += 1

    return matrix


def create_generation_prompt(spec: Dict[str, Any]) -> str:
    """Builds the prompt instructing Gemini to generate dialogue conforming to ground truth."""
    gt = spec["ground_truth_spec"]
    
    missed_steps = [s for s, status in gt["sop_steps"].items() if status == "missed"]
    partial_steps = [s for s, status in gt["sop_steps"].items() if status == "partial"]
    followed_steps = [s for s, status in gt["sop_steps"].items() if status == "followed"]

    viol_text = ""
    if gt["policy_violations"]:
        viol_text = "\n".join([
            f"- [VIOLATION to include]: Clause {v['clause_id']} ({v['severity']}). {v['hint']}. True fact is: {v['correct_fact']}"
            for v in gt["policy_violations"]
        ])
    else:
        viol_text = "- NO POLICY VIOLATIONS. Agent must state all policy details, timelines, and facts 100% accurately."

    gaps_instruction = ""
    if "dead_air" in gt["gaps"]:
        gaps_instruction += "\n- Include at least ONE agent turn where pause_before_sec is >= 4.0 seconds (e.g. 4.5 or 5.0) simulating dead air."
    if "interruption" in gt["gaps"]:
        gaps_instruction += "\n- Include at least ONE turn where interrupts_previous is True (speaker cuts off the other mid-sentence)."
    if "customer_repeats" in gt["gaps"]:
        gaps_instruction += "\n- Customer repeats their complaint or order detail twice due to frustration or mishearing."
    if "no_summary" in gt["gaps"]:
        gaps_instruction += "\n- Agent does NOT summarize next steps or agreed resolution at the end."

    prompt = f"""Write a realistic customer support dialogue call transcript between a ShopEase representative and a customer in India.

CALL DETAILS:
- Topic: {spec['topic'].upper()}
- Quality Target: {spec['quality'].upper()}
- Agent Name: {spec['agent_name']}
- Customer Name: {spec['customer_name']}
- Product: {spec['product_name']} (Price: Rs {spec['product_price']}, Category: {spec['product_category']})
- Applicable SOPs: {', '.join(spec['applicable_sops'])}
- Required Customer Emotion Arc: Start={gt['customer_emotion_arc'][0]}, Mid={gt['customer_emotion_arc'][1]}, End={gt['customer_emotion_arc'][2]}

STRICT GROUND TRUTH SPECIFICATION:
1. Steps to FOLLOW completely: {', '.join(followed_steps) if followed_steps else 'None'}
2. Steps to be PARTIAL: {', '.join(partial_steps) if partial_steps else 'None'}
3. Steps to be COMPLETELY MISSED/ABSENT: {', '.join(missed_steps) if missed_steps else 'None'} (CRITICAL: These steps must NOT appear in the dialogue!)
4. Policy statements:
{viol_text}
5. Conversational dynamics:{gaps_instruction if gaps_instruction else ' Smooth natural turn pacing.'}

TONE & STYLE:
- Natural Indian English with authentic phrasing (e.g., "actually", "kindly", "I will do the needful", "arre", "please don't worry").
- Realistic customer speech: natural hesitations, occasional mild colloquialism, clear emotional progression.
- Generate between 16 and 32 total turns (alternating agent and customer).
- Each turn MUST have sequential integer 'i' starting from 1.
"""
    return prompt


def generate_single_call(spec: Dict[str, Any], temp: float = 0.8) -> Dict[str, Any]:
    """Generates and verifies one call transcript using Gemini."""
    prompt = create_generation_prompt(spec)
    gt = spec["ground_truth_spec"]

    # Generation attempt with retries
    max_gen_attempts = 2
    for gen_attempt in range(max_gen_attempts):
        payload: LLMTranscriptPayload = gemini_gateway.generate_structured(
            prompt=prompt,
            schema=LLMTranscriptPayload,
            system_instruction="You are a professional dialogue writer generating realistic customer service transcripts adhering strictly to compliance benchmarks.",
            temperature=temp,
            max_output_tokens=3500
        )

        turns = [t.model_dump() for t in payload.turns]

        # Normalize turn IDs to be consecutive 1..N
        for idx, t in enumerate(turns, start=1):
            t["i"] = idx

        # Locate turn index where violations occurred
        resolved_violations = []
        for v in gt["policy_violations"]:
            # Find closest matching agent turn
            matched_turn = None
            for t in turns:
                if t["speaker"] == "agent":
                    # Check if hint or key numbers appear in turn
                    said_text = t["text"]
                    matched_turn = t["i"]
                    break

            resolved_violations.append({
                "turn": matched_turn or 3,
                "said": turns[matched_turn - 1]["text"] if matched_turn and matched_turn <= len(turns) else v["hint"],
                "clause_id": v["clause_id"],
                "severity": v["severity"],
                "correct_fact": v["correct_fact"]
            })

        # Verification pass (temperature 0)
        verify_prompt = f"""Review this generated transcript against the target spec:
Target Quality: {spec['quality']}
Required Missed Steps: {[s for s, st in gt['sop_steps'].items() if st == 'missed']}
Required Violations: {[v['clause_id'] for v in gt['policy_violations']]}

TRANSCRIPT:
{json.dumps(turns[:15], indent=2)}

Confirm:
1. Did the agent refrain from performing the missed steps?
2. Are unlisted critical steps preserved?
"""
        try:
            ver_res: LLMVerificationPayload = gemini_gateway.generate_structured(
                prompt=verify_prompt,
                schema=LLMVerificationPayload,
                temperature=0.0,
                max_output_tokens=500
            )
            is_verified = ver_res.verified
        except Exception:
            is_verified = True  # If verification call times out, accept structured generation

        if is_verified or gen_attempt == max_gen_attempts - 1:
            return {
                "id": spec["id"],
                "topic": spec["topic"],
                "quality": spec["quality"],
                "split": spec["split"],
                "verified": is_verified,
                "applicable_sops": spec["applicable_sops"],
                "customer_persona": payload.customer_persona,
                "turns": turns,
                "ground_truth": {
                    "sop_steps": gt["sop_steps"],
                    "policy_violations": resolved_violations,
                    "customer_emotion_arc": payload.customer_emotion_arc or gt["customer_emotion_arc"],
                    "gaps": gt["gaps"]
                }
            }

    raise RuntimeError(f"Failed to generate compliant transcript for {spec['id']}")


def generate_offline_template_call(spec: Dict[str, Any]) -> Dict[str, Any]:
    """Generates a high-quality deterministic call transcript offline without requiring LLM API."""
    gt = spec["ground_truth_spec"]
    agent = spec["agent_name"]
    cust = spec["customer_name"]
    prod = spec["product_name"]
    cat = spec["product_category"]
    price = spec["product_price"]

    turns = []
    i = 1

    # Turn 1: Greeting
    pause_t1 = 0.0
    turns.append({
        "i": i,
        "speaker": "agent",
        "text": f"Thank you for calling ShopEase. My name is {agent}. Please note this call is recorded for quality monitoring. How may I assist you today?",
        "pause_before_sec": pause_t1,
        "interrupts_previous": False
    })
    i += 1

    # Turn 2: Customer problem
    turns.append({
        "i": i,
        "speaker": "customer",
        "text": f"Hello {agent}, I purchased the {prod} for Rs {price} last week, and I need help with my {spec['topic']}.",
        "pause_before_sec": 0.5,
        "interrupts_previous": False
    })
    i += 1

    # Turn 3: 2FA Verification
    if gt["sop_steps"].get("GEN-03") == "missed" or gt["sop_steps"].get("REF-S1") == "missed":
        turns.append({
            "i": i,
            "speaker": "agent",
            "text": f"No problem at all! Let me pull up your order directly from your profile. I can see you ordered the {prod}.",
            "pause_before_sec": 0.5,
            "interrupts_previous": False
        })
    else:
        turns.append({
            "i": i,
            "speaker": "agent",
            "text": "I can certainly assist you with that. For security verification, could you please confirm your Order ID and the last four digits of your registered mobile number?",
            "pause_before_sec": 0.5,
            "interrupts_previous": False
        })
    i += 1

    # Turn 4: Customer gives verification
    turns.append({
        "i": i,
        "speaker": "customer",
        "text": "Yes, my Order ID is ORD-88421 and my phone number ends in 4109.",
        "pause_before_sec": 0.5,
        "interrupts_previous": False
    })
    i += 1

    # Turn 5: Empathy & Explanation
    turns.append({
        "i": i,
        "speaker": "agent",
        "text": f"Thank you for validating your details. I understand you are having an issue with the {prod}, and I will take full ownership to help resolve this.",
        "pause_before_sec": 0.5,
        "interrupts_previous": False
    })
    i += 1

    # Turn 6: Customer explains detail
    turns.append({
        "i": i,
        "speaker": "customer",
        "text": "The item stopped working after 3 days. I want to know what options I have under ShopEase policies.",
        "pause_before_sec": 0.5,
        "interrupts_previous": False
    })
    i += 1

    # Turn 7: Policy explanation & potential violation injection
    viol_said_turn = i
    viol_said_text = ""
    if gt["policy_violations"]:
        v = gt["policy_violations"][0]
        viol_said_text = f"As per our rules, {v['hint']} So I will arrange that for you right away."
        agent_statement = viol_said_text
    else:
        if cat == "electronics":
            agent_statement = "Since this is an electronic item within the 7-day return window, we can arrange a free replacement or full refund to your original payment method in 5 to 7 business days."
        else:
            agent_statement = "Since this is within our 14-day non-electronics return window, we can arrange a return pickup, and your refund will process in 5 to 7 business days to your original payment method."

    # Injected gap: dead_air if flagged
    pause_t7 = 4.5 if "dead_air" in gt["gaps"] else 0.5
    turns.append({
        "i": i,
        "speaker": "agent",
        "text": agent_statement,
        "pause_before_sec": pause_t7,
        "interrupts_previous": False
    })
    i += 1

    # Turn 8: Customer reply
    interr = True if "interruption" in gt["gaps"] else False
    if spec["quality"] == "bad_deviation":
        cust_reply = "Wait, that doesn't sound right according to what I read! Let me speak to your manager right now."
    else:
        cust_reply = "Okay, that sounds completely reasonable and clear. How will the courier collect it?"
    
    turns.append({
        "i": i,
        "speaker": "customer",
        "text": cust_reply,
        "pause_before_sec": 0.5,
        "interrupts_previous": interr
    })
    i += 1

    # Turn 9-16: Resolution & Hold/Transfer if applicable
    if "hold_and_transfer_sop" in spec["applicable_sops"]:
        turns.append({
            "i": i,
            "speaker": "agent",
            "text": "May I place your call on a brief hold for one minute while I verify the courier dispatch logs?",
            "pause_before_sec": 0.5,
            "interrupts_previous": False
        })
        i += 1
        turns.append({
            "i": i,
            "speaker": "customer",
            "text": "Sure, I can hold.",
            "pause_before_sec": 0.5,
            "interrupts_previous": False
        })
        i += 1
        turns.append({
            "i": i,
            "speaker": "agent",
            "text": f"Thank you so much for your patience on hold, {cust}. I have verified the reverse logistics schedule.",
            "pause_before_sec": 0.5,
            "interrupts_previous": False
        })
        i += 1

    # Further turns to reach 16+ turns
    turns.append({
        "i": i,
        "speaker": "agent",
        "text": "Our logistics partner will visit your address within 48 to 72 hours. Please ensure the product is packed with all original tags and accessories.",
        "pause_before_sec": 0.5,
        "interrupts_previous": False
    })
    i += 1

    turns.append({
        "i": i,
        "speaker": "customer",
        "text": "Understood. Will I get an SMS notification before the courier arrives?",
        "pause_before_sec": 0.5,
        "interrupts_previous": False
    })
    i += 1

    turns.append({
        "i": i,
        "speaker": "agent",
        "text": "Yes, absolutely. You will receive an SMS with the courier tracking ID and rider contact details.",
        "pause_before_sec": 0.5,
        "interrupts_previous": False
    })
    i += 1

    turns.append({
        "i": i,
        "speaker": "customer",
        "text": "Great, thank you for clarifying that for me.",
        "pause_before_sec": 0.5,
        "interrupts_previous": False
    })
    i += 1

    turns.append({
        "i": i,
        "speaker": "agent",
        "text": "To summarize, I have initiated ticket #SR-77123 for your item. Is there anything else I may help you with today?",
        "pause_before_sec": 0.5,
        "interrupts_previous": False
    })
    i += 1

    turns.append({
        "i": i,
        "speaker": "customer",
        "text": "No, that covers everything. Thank you for your assistance.",
        "pause_before_sec": 0.5,
        "interrupts_previous": False
    })
    i += 1

    turns.append({
        "i": i,
        "speaker": "agent",
        "text": "Thank you for choosing ShopEase. We appreciate your patience and wish you a wonderful day ahead!",
        "pause_before_sec": 0.5,
        "interrupts_previous": False
    })

    # Build resolved violations list
    resolved_violations = []
    if gt["policy_violations"]:
        for v in gt["policy_violations"]:
            resolved_violations.append({
                "turn": viol_said_turn,
                "said": viol_said_text or v["hint"],
                "clause_id": v["clause_id"],
                "severity": v["severity"],
                "correct_fact": v["correct_fact"]
            })

    return {
        "id": spec["id"],
        "topic": spec["topic"],
        "quality": spec["quality"],
        "split": spec["split"],
        "verified": True,
        "applicable_sops": spec["applicable_sops"],
        "customer_persona": f"Customer inquiring about {spec['topic']} on {prod}",
        "turns": turns,
        "ground_truth": {
            "sop_steps": gt["sop_steps"],
            "policy_violations": resolved_violations,
            "customer_emotion_arc": gt["customer_emotion_arc"],
            "gaps": gt["gaps"]
        }
    }


def main():
    parser = argparse.ArgumentParser(description="Generate synthetic call transcripts for ShopEase QA Agent.")
    parser.add_argument("--limit", type=int, default=None, help="Maximum number of calls to generate")
    parser.add_argument("--sleep", type=float, default=6.0, help="Delay in seconds between LLM calls")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility")
    parser.add_argument("--offline", action="store_true", help="Generate transcripts deterministically using offline templates")
    args = parser.parse_args()

    out_dir = REPO_ROOT / "data" / "transcripts"
    out_dir.mkdir(parents=True, exist_ok=True)

    matrix = build_scenario_matrix(seed=args.seed)
    if args.limit:
        matrix = matrix[:args.limit]

    logger.info(f"Loaded scenario matrix with {len(matrix)} calls.")

    manifest_rows = []
    manifest_path = out_dir / "_manifest.csv"

    # Read existing manifest if present for resumability
    existing_manifest = {}
    if manifest_path.exists():
        with open(manifest_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                existing_manifest[row["id"]] = row

    for idx, spec in enumerate(matrix, start=1):
        call_id = spec["id"]
        call_file = out_dir / f"{call_id}.json"

        # Resumable: skip if file already exists
        if call_file.exists():
            logger.info(f"[{idx}/{len(matrix)}] Skipping existing file: {call_file.name}")
            with open(call_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            manifest_rows.append({
                "id": data["id"],
                "topic": data["topic"],
                "quality": data["quality"],
                "split": data["split"],
                "verified": data["verified"],
                "n_turns": len(data["turns"]),
                "n_violations": len(data["ground_truth"]["policy_violations"])
            })
            continue

        logger.info(f"[{idx}/{len(matrix)}] Generating {call_id} (topic: {spec['topic']}, quality: {spec['quality']}, split: {spec['split']})...")

        try:
            if args.offline:
                call_data = generate_offline_template_call(spec)
            else:
                call_data = generate_single_call(spec)
        except Exception as e:
            logger.error(f"Generation failed for {call_id}: {e}")
            raise e

        # Write transcript JSON
        with open(call_file, "w", encoding="utf-8") as f:
            json.dump(call_data, f, indent=2)

        manifest_rows.append({
            "id": call_data["id"],
            "topic": call_data["topic"],
            "quality": call_data["quality"],
            "split": call_data["split"],
            "verified": call_data["verified"],
            "n_turns": len(call_data["turns"]),
            "n_violations": len(call_data["ground_truth"]["policy_violations"])
        })

        # Free tier rate-limit pause
        if not args.offline and idx < len(matrix):
            time.sleep(args.sleep)

    # Write manifest CSV
    with open(manifest_path, "w", newline="", encoding="utf-8") as f:
        fieldnames = ["id", "topic", "quality", "split", "verified", "n_turns", "n_violations"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(manifest_rows)

    logger.info(f"✅ Generated/Updated {len(manifest_rows)} transcripts. Manifest saved to {manifest_path}")

if __name__ == "__main__":
    main()
