"""Generate synthetic customer support call transcripts using Gemini API.

Enforces:
- Full definitions and required elements of applicable SOP steps in prompt
- Exact topic-grounded policy clauses in prompt
- No fake/template data; fails loudly on API errors or quota limits
- Natural pause variation (0.3-1.2s normal, >=4.0s for dead air)
- Detailed deterministic and LLM verification (temperature 0)
- Support for --interleave (round-robin topics & qualities), --topic filter, and --rpm rate limiting
"""

import os
import re
import sys
import csv
import json
import time
import random
import argparse
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Literal
from dotenv import load_dotenv
from pydantic import BaseModel, Field

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

# Load environment with override=True to ensure .env values take precedence
load_dotenv(dotenv_path=REPO_ROOT / ".env", override=True)

import yaml
from src.audit.llm import gemini_gateway

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("generate_transcripts")

TOPICS = ["refund", "billing", "shipping", "warranty", "complaint", "general"]

GENERAL_STEPS = ["GEN-01", "GEN-02", "GEN-03", "GEN-04", "GEN-05", "GEN-06", "GEN-07", "GEN-08"]
REFUND_STEPS = ["REF-S1", "REF-S2", "REF-S3", "REF-S4", "REF-S5", "REF-S6", "REF-S7"]
COMPLAINT_STEPS = ["ANG-01", "ANG-02", "ANG-03", "ANG-04", "ANG-05", "ANG-06"]

HOLD_SCENARIO_STEPS = {
    "hold_only": ["HLD-01", "HLD-02", "HLD-03"],
    "transfer": ["HLD-04"],
    "callback": ["HLD-05"],
    "none": []
}

CRITICAL_STEPS = {
    "GEN-02", "GEN-03", "GEN-06",
    "REF-S1", "REF-S2", "REF-S4", "REF-S5",
    "ANG-05", "HLD-02", "HLD-04"
}

# Detailed required elements for critical SOP steps
STEP_REQUIRED_ELEMENTS = {
    "GEN-02": "Must deliver the mandatory call recording disclosure within the FIRST TWO conversation turns.",
    "GEN-03": "Must ask for and verify BOTH: (1) Order ID, AND (2) Last 4 digits of the registered mobile phone number before revealing account/order info. Asking only for name or order ID without phone digits is partial/missed.",
    "GEN-06": "Must accurately state policies and timelines without making unauthorized or out-of-policy promises.",
    "REF-S1": "Must authenticate caller identity with Order ID AND last 4 digits of registered phone before discussing refund details.",
    "REF-S2": "Must accurately state the return window: 7 calendar days for electronics, 14 calendar days for non-electronics.",
    "REF-S4": "Must enforce the Rs 5,000 frontline agent approval threshold limit (requests exceeding Rs 5,000 require supervisor sign-off).",
    "REF-S5": "Must state that refunds return to the original payment method, or via NEFT bank transfer for COD orders (never cash at doorstep).",
    "ANG-05": "Must execute supervisor escalation when customer asks twice or issue remains unresolved after 2 frontline attempts.",
    "HLD-02": "Must check back in with the customer before the 2-minute hold ceiling expires.",
    "HLD-04": "Must execute warm transfer by briefing the receiving supervisor with customer name, verified Order ID, and issue summary before bridging."
}

INDIAN_AGENT_NAMES = ["Rahul Sharma", "Priya Nair", "Ananya Sen", "Rohan Verma", "Sneha Kulkarni", "Amit Patel", "Neha Gupta", "Vikram Malhotra"]
INDIAN_CUSTOMER_NAMES = ["Rajesh Kumar", "Sunita Sharma", "Deepak Verma", "Meera Iyer", "Karan Patel", "Anjali Mehta", "Suresh Reddy", "Kavita Singh"]

SAMPLE_PRODUCTS = [
    ("Boat Rockerz 450 Bluetooth Headphones", 1499, "electronics"),
    ("Noise ColorFit Pulse Smartwatch", 2499, "electronics"),
    ("OnePlus Nord CE 3 Lite 5G", 19999, "electronics"),
    ("Puma Men Running Shoes", 2199, "non-electronics"),
    ("Levi's Slim Fit Cotton Jeans", 1899, "non-electronics"),
    ("Prestige Electric Kettle 1.5L", 899, "electronics"),
    ("Philips Multi-Grooming Trimmer", 1099, "electronics"),
    ("Wildcraft 35L Water Resistant Backpack", 1299, "non-electronics")
]


class LLMTurn(BaseModel):
    i: int = Field(..., description="1-indexed sequence number")
    speaker: Literal["agent", "customer"] = Field(..., description="Speaker role")
    text: str = Field(..., description="Spoken dialogue text")
    pause_before_sec: float = Field(0.5, description="Pause duration preceding this turn in seconds (0.3-1.2s normal, >=4.0s for dead air)")
    interrupts_previous: bool = Field(False, description="True ONLY if this turn cuts off the previous speaker")

class LLMTranscriptPayload(BaseModel):
    customer_persona: str = Field(..., description="Short summary of customer personality and state of mind")
    customer_emotion_arc: List[str] = Field(..., description="3 emotion descriptors: [start, mid, end]")
    turns: List[LLMTurn] = Field(..., description="List of dialogue turns between 16 and 36 turns")

class StepVerificationItem(BaseModel):
    step_id: str
    is_followed: bool

class ViolationVerificationItem(BaseModel):
    clause_id: str
    is_stated_by_agent: bool

class LLMVerificationPayload(BaseModel):
    violations_confirmed: List[ViolationVerificationItem] = Field(default_factory=list, description="Verification of each expected policy violation")
    critical_steps_observed: List[StepVerificationItem] = Field(default_factory=list, description="Verification of each expected critical SOP step")
    unintended_deviations: List[str] = Field(default_factory=list, description="Any unintended violations or unlisted critical step omissions")
    all_passed: bool = Field(..., description="True if transcript strictly satisfies the ground truth contract")
    notes: str = Field(..., description="Verification reasoning summary")


def load_violation_catalog() -> List[Dict[str, Any]]:
    cat_path = REPO_ROOT / "scripts" / "violation_catalog.yaml"
    with open(cat_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data.get("violations", [])


def load_all_sop_step_definitions() -> Dict[str, Dict[str, Any]]:
    """Parses full step definitions (description, what good looks like, examples) from data/sops/*.md."""
    step_defs = {}
    sops_dir = REPO_ROOT / "data" / "sops"
    step_header_re = re.compile(r"^###?\s*\[?([A-Z]{3}-S?\d+)\]?\s*(.*)$")

    for sop_file in sops_dir.glob("*.md"):
        lines = sop_file.read_text(encoding="utf-8").splitlines()
        current_step_id = None
        current_title = ""
        current_desc = ""
        current_good = ""
        current_examples = []
        is_crit = False

        for line in lines:
            header_match = step_header_re.match(line.strip())
            if header_match:
                if current_step_id:
                    step_defs[current_step_id] = {
                        "step_id": current_step_id,
                        "title": current_title,
                        "description": current_desc.strip(),
                        "what_good_looks_like": current_good.strip(),
                        "examples": current_examples,
                        "is_critical": is_crit or (current_step_id in CRITICAL_STEPS)
                    }
                current_step_id = header_match.group(1)
                current_title = header_match.group(2)
                current_desc = ""
                current_good = ""
                current_examples = []
                is_crit = current_step_id in CRITICAL_STEPS
                continue

            if current_step_id:
                if line.strip().startswith("- **Description:**"):
                    current_desc = line.strip().replace("- **Description:**", "").strip()
                elif line.strip().startswith("- **What Good Looks Like:**"):
                    current_good = line.strip().replace("- **What Good Looks Like:**", "").strip()
                elif line.strip().startswith("- *\"") or line.strip().startswith("*\""):
                    current_examples.append(line.strip().replace("-", "").strip().strip('"').strip('*'))
                elif "Critical: Yes" in line:
                    is_crit = True

        if current_step_id:
            step_defs[current_step_id] = {
                "step_id": current_step_id,
                "title": current_title,
                "description": current_desc.strip(),
                "what_good_looks_like": current_good.strip(),
                "examples": current_examples,
                "is_critical": is_crit or (current_step_id in CRITICAL_STEPS)
            }

    return step_defs


def load_policy_context_for_topic(topic: str) -> str:
    """Loads authoritative policy clauses for the specified topic from data/policies/*.md."""
    policies_dir = REPO_ROOT / "data" / "policies"
    relevant_files = ["privacy_identity_verification.md"]

    if topic == "refund":
        relevant_files.extend(["refund_and_returns.md", "billing_payments.md"])
    elif topic == "billing":
        relevant_files.extend(["billing_payments.md", "refund_and_returns.md"])
    elif topic == "shipping":
        relevant_files.extend(["shipping_delivery.md"])
    elif topic == "warranty":
        relevant_files.extend(["warranty_replacement.md", "refund_and_returns.md"])
    elif topic == "complaint":
        relevant_files.extend(["escalation.md", "refund_and_returns.md"])
    elif topic == "general":
        relevant_files.extend(["refund_and_returns.md", "shipping_delivery.md"])

    policy_texts = []
    for fname in relevant_files:
        fpath = policies_dir / fname
        if fpath.exists():
            policy_texts.append(fpath.read_text(encoding="utf-8"))

    return "\n\n".join(policy_texts)


def extract_key_figures(text: str) -> List[str]:
    """Extracts numbers from hints to verify agent turns."""
    return re.findall(r"\b\d+(?:,\d+)?\b", text)


def build_scenario_matrix(seed: int = 42) -> List[Dict[str, Any]]:
    """Builds the 48-call scenario specifications."""
    random.seed(seed)
    violations_catalog = load_violation_catalog()

    matrix = []
    call_idx = 1

    test_allocations = {
        "good": set(random.sample(range(18), 4)),
        "mild_deviation": set(random.sample(range(18), 4)),
        "bad_deviation": set(random.sample(range(12), 4)),
    }
    counters = {"good": 0, "mild_deviation": 0, "bad_deviation": 0}

    # Assign hold scenarios to 16 calls (1/3 of 48)
    hold_assignments = {}
    hold_call_ids = set(random.sample(range(1, 49), 16))
    scenario_pool = ["hold_only"] * 6 + ["transfer"] * 5 + ["callback"] * 5
    random.shuffle(scenario_pool)
    for c_id, sc in zip(sorted(list(hold_call_ids)), scenario_pool):
        hold_assignments[c_id] = sc

    for topic in TOPICS:
        qualities = ["good"] * 3 + ["mild_deviation"] * 3 + ["bad_deviation"] * 2
        random.shuffle(qualities)

        for quality in qualities:
            call_id = f"call_{call_idx:03d}"
            
            curr_count = counters[quality]
            counters[quality] += 1
            split = "test" if curr_count in test_allocations[quality] else "train"

            # Determine Applicable Steps
            applicable_steps = list(GENERAL_STEPS)
            applicable_sops = ["general_call_flow"]

            if topic == "refund":
                applicable_steps.extend(REFUND_STEPS)
                applicable_sops.append("refund_call_sop")
            elif topic == "complaint":
                applicable_steps.extend(COMPLAINT_STEPS)
                applicable_sops.append("angry_customer_sop")

            # Hold scenario
            hold_sc = hold_assignments.get(call_idx, "none")
            if hold_sc != "none":
                applicable_steps.extend(HOLD_SCENARIO_STEPS[hold_sc])
                applicable_sops.append("hold_and_transfer_sop")

            # Ground truth construction
            sop_ground_truth = {}
            policy_violations = []
            gaps = []

            # Filter catalog STRICTLY by topic
            topic_viol_pool = [v for v in violations_catalog if topic in v.get("topics", [])]
            if not topic_viol_pool:
                raise ValueError(f"No catalog violations found for topic '{topic}'!")

            if quality == "good":
                for step in applicable_steps:
                    sop_ground_truth[step] = "followed"
                emotion_arc = [random.choice(["frustrated", "neutral"]), "neutral", "satisfied"]
                if random.random() < 0.25:
                    gaps.append(random.choice(["interruption", "customer_repeats"]))

            elif quality == "mild_deviation":
                # 1-2 non-critical steps missed or partial
                non_crit = [s for s in applicable_steps if s not in CRITICAL_STEPS]
                deviated = random.sample(non_crit, min(len(non_crit), random.choice([1, 2])))
                for step in applicable_steps:
                    if step in deviated:
                        sop_ground_truth[step] = random.choice(["partial", "missed"])
                    else:
                        sop_ground_truth[step] = "followed"

                # 0-1 minor policy slip from topic-matched pool
                if random.random() < 0.7:
                    minor_pool = [v for v in topic_viol_pool if v["severity"] == "minor"]
                    if minor_pool:
                        v = random.choice(minor_pool)
                        policy_violations.append({
                            "clause_id": v["clause_id"],
                            "severity": v["severity"],
                            "correct_fact": v["correct_fact"],
                            "hint": v["wrong_statement_hint"],
                            "figures": extract_key_figures(v["wrong_statement_hint"])
                        })

                emotion_arc = [random.choice(["frustrated", "neutral"]), "neutral", random.choice(["neutral", "satisfied"])]
                if random.random() < 0.4:
                    gaps.append(random.choice(["dead_air", "interruption", "no_summary"]))

            else:  # bad_deviation
                # At least 1 critical step missed
                crit = [s for s in applicable_steps if s in CRITICAL_STEPS]
                missed_crit = random.choice(crit) if crit else "GEN-02"
                
                for step in applicable_steps:
                    if step == missed_crit:
                        sop_ground_truth[step] = "missed"
                    else:
                        sop_ground_truth[step] = "followed" if random.random() < 0.75 else "partial"

                # 1-2 major/critical policy violations from topic-matched pool
                major_pool = [v for v in topic_viol_pool if v["severity"] in ["major", "critical"]]
                if not major_pool:
                    major_pool = topic_viol_pool
                
                n_viols = min(len(major_pool), random.choice([1, 2]))
                chosen_viols = random.sample(major_pool, n_viols)
                for v in chosen_viols:
                    policy_violations.append({
                        "clause_id": v["clause_id"],
                        "severity": v["severity"],
                        "correct_fact": v["correct_fact"],
                        "hint": v["wrong_statement_hint"],
                        "figures": extract_key_figures(v["wrong_statement_hint"])
                    })

                emotion_arc = [random.choice(["angry", "frustrated"]), "angry", random.choice(["angry", "escalated", "unhappy"])]
                gaps.append(random.choice(["dead_air", "interruption", "no_summary", "customer_repeats"]))

            prod = random.choice(SAMPLE_PRODUCTS)
            matrix.append({
                "id": call_id,
                "topic": topic,
                "quality": quality,
                "split": split,
                "applicable_sops": applicable_sops,
                "applicable_steps": applicable_steps,
                "hold_scenario": hold_sc,
                "product_name": prod[0],
                "product_price": prod[1],
                "product_category": prod[2],
                "order_id": f"ORD-{random.randint(10000, 99999)}",
                "registered_phone_last4": f"{random.randint(1000, 9999)}",
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


def create_generation_prompt(spec: Dict[str, Any], step_definitions: Dict[str, Dict[str, Any]]) -> str:
    """Builds the comprehensive prompt containing full step definitions and policy facts."""
    gt = spec["ground_truth_spec"]
    
    # 1. Step Instructions with FULL definitions
    step_instructions = []
    for step_id in spec["applicable_steps"]:
        s_def = step_definitions.get(step_id, {})
        status = gt["sop_steps"].get(step_id, "followed")
        req_el = STEP_REQUIRED_ELEMENTS.get(step_id, "")
        ex_str = f" Examples: {s_def.get('examples', [])[:2]}" if s_def.get("examples") else ""

        if status == "followed":
            desc = (
                f"- [{step_id}] MUST BE FOLLOWED FULLY AND EXACTLY:\n"
                f"  Title: {s_def.get('title', '')}\n"
                f"  Standard Definition: {s_def.get('description', '')}\n"
                f"  What Good Looks Like: {s_def.get('what_good_looks_like', '')}\n"
                f"  Required Elements: {req_el if req_el else 'Complete all standard requirements.'}\n"
                f" {ex_str}"
            )
        elif status == "partial":
            desc = (
                f"- [{step_id}] MUST BE PARTIALLY PERFORMED (Leave out one required element):\n"
                f"  Title: {s_def.get('title', '')}\n"
                f"  Instruction: Attempt this step but leave out a key element (e.g. for GEN-03, ask for name and Order ID, but omit the last 4 phone digits; for GEN-01, greet without introducing your name)."
            )
        else:  # missed
            desc = (
                f"- [{step_id}] MUST BE COMPLETELY MISSED / ABSENT FROM DIALOGUE:\n"
                f"  Title: {s_def.get('title', '')}\n"
                f"  Instruction: Completely skip and omit this step. (e.g. if GEN-02 is missed, do NOT provide recording disclosure; if GEN-03 is missed, do NOT perform any verification)."
            )
        step_instructions.append(desc)

    steps_text = "\n\n".join(step_instructions)

    # 2. Policy Violations
    viol_instructions = []
    if gt["policy_violations"]:
        for v in gt["policy_violations"]:
            viol_instructions.append(
                f"- [POLICY VIOLATION on clause {v['clause_id']} ({v['severity']})]:\n"
                f"  MISTAKE TO MAKE (CONCEPTUAL HINT): {v['hint']}\n"
                f"  CORRECT POLICY FACT: {v['correct_fact']}\n"
                f"  CRITICAL INSTRUCTION: The text in 'MISTAKE TO MAKE' explains what the agent gets wrong. NEVER copy or quote that hint text into dialogue!\n"
                f"  Instead, have the agent speak naturally, stating the contradictory figure (e.g. '{', '.join(v['figures'])}') in their own natural words."
            )
        viol_text = "\n".join(viol_instructions)
    else:
        viol_text = "- NO POLICY VIOLATIONS: The agent must state all ShopEase policies, timelines, return windows, and refund rules with 100% factual accuracy."

    # 3. Policy Facts Context
    policy_context = load_policy_context_for_topic(spec["topic"])

    # 4. Gaps & Dynamics
    gaps_text = ""
    if "dead_air" in gt["gaps"]:
        gaps_text += "\n- INJECTED GAP (dead_air): Set 'pause_before_sec' to >= 4.0 (e.g. 4.5 or 5.0) on exactly ONE agent turn to simulate dead air."
    if "interruption" in gt["gaps"]:
        gaps_text += "\n- INJECTED GAP (interruption): Set 'interrupts_previous' to true on exactly ONE customer or agent turn that cuts off the other mid-sentence."
    if "no_summary" in gt["gaps"]:
        gaps_text += "\n- INJECTED GAP (no_summary): The agent MUST NOT summarize agreed next steps, ticket IDs, or resolution at the end."
    if "customer_repeats" in gt["gaps"]:
        gaps_text += "\n- INJECTED GAP (customer_repeats): The customer repeats their issue or Order ID twice due to agitation or mishearing."

    prompt = f"""You are a professional dialogue writer creating a realistic customer support call recording transcript for ShopEase (an Indian e-commerce company).

CALL METADATA (MUST BE 100% CONSISTENT):
- Agent Name: {spec['agent_name']}
- Customer Name: {spec['customer_name']} (Customer must state their name and/or agent address them by name)
- Order ID: {spec['order_id']} (Must be cited when verifying)
- Registered Phone Last 4 Digits: {spec['registered_phone_last4']} (Must be cited when verifying)
- Product: {spec['product_name']} (Category: {spec['product_category']}, Price: Rs {spec['product_price']})
- Topic: {spec['topic'].upper()}
- Target Quality: {spec['quality'].upper()}
- Hold Scenario: {spec['hold_scenario'].upper()}
- Customer Emotion Arc: Start={gt['customer_emotion_arc'][0]}, Mid={gt['customer_emotion_arc'][1]}, End={gt['customer_emotion_arc'][2]}

MANDATORY SCRIPT REQUIREMENTS:
- Customer must introduce themselves with their name '{spec['customer_name']}' or agent must address them by name (e.g. 'Mr. {spec['customer_name'].split()[-1]}').
- If identity verification is followed (GEN-03 / REF-S1), the agent must request BOTH the Order ID ('{spec['order_id']}') AND the last 4 digits of the phone ('{spec['registered_phone_last4']}'), and the customer must supply both.

APPLICABLE SOP STEPS SPECIFICATIONS (READ CAREFULLY):
{steps_text}

POLICY ADHERENCE OR VIOLATIONS:
{viol_text}

CONVERSATIONAL DYNAMICS & REALISM:{gaps_text}
- Natural pause pacing: 'pause_before_sec' must vary naturally between 0.3 and 1.2 seconds on standard turns.
- 'interrupts_previous' must be FALSE on all turns unless an interruption was explicitly requested above.
- Dialogue length: Generate between 16 and 32 turns (alternating agent and customer).
- Language: Natural Indian English with authentic phrasing, natural hesitations, and realistic pacing.

AUTHORITATIVE POLICY REFERENCE FACTS:
{policy_context}
"""
    return prompt


def verify_transcript_deterministic(call_data: Dict[str, Any], spec: Dict[str, Any]) -> List[str]:
    """Runs strict deterministic checks on the generated transcript."""
    errors = []
    turns = call_data.get("turns", [])
    gt = spec["ground_truth_spec"]

    if len(turns) < 14 or len(turns) > 42:
        errors.append(f"Turn count {len(turns)} is outside expected range 16-36.")

    # 1. Check for hint text leakage (verbatim copying from catalog)
    all_agent_text = " ".join([t["text"].lower() for t in turns if t["speaker"] == "agent"])
    for v in gt["policy_violations"]:
        hint_clean = v["hint"].lower().strip()
        if hint_clean in all_agent_text:
            errors.append(f"Catalog hint leaked verbatim into agent dialogue: '{v['hint']}'")
        for bad_prefix in ["agent states that", "agent promises to", "agent tells customer", "agent approves an", "agent assures the"]:
            if bad_prefix in all_agent_text:
                errors.append(f"Catalog meta-phrase leaked into dialogue: '{bad_prefix}'")

    # 2. Check injected gaps
    gaps = gt["gaps"]
    if "dead_air" in gaps:
        has_dead_air = any(t.get("pause_before_sec", 0.0) >= 4.0 for t in turns)
        if not has_dead_air:
            errors.append("Injected gap 'dead_air' not realized: no turn with pause_before_sec >= 4.0.")

    if "interruption" in gaps:
        has_interruption = any(t.get("interrupts_previous", False) is True for t in turns)
        if not has_interruption:
            errors.append("Injected gap 'interruption' not realized: no turn with interrupts_previous=True.")

    if "no_summary" in gaps:
        last_agent_turns = [t["text"].lower() for t in turns[-6:] if t["speaker"] == "agent"]
        summary_words = ["to summarize", "to recap", "in summary", "let me summarize", "recap of our call"]
        if any(any(sw in txt for sw in summary_words) for txt in last_agent_turns):
            errors.append("Injected gap 'no_summary' violated: agent summarized at call conclusion.")

    # 3. Check customer name and Order ID consistency
    cust_first = spec["customer_name"].split()[0].lower()
    all_call_text = " ".join([t["text"].lower() for t in turns])
    if cust_first not in all_call_text:
        errors.append(f"Customer name '{spec['customer_name']}' not used in dialogue.")
    if spec["order_id"].lower() not in all_call_text:
        errors.append(f"Order ID '{spec['order_id']}' not present in dialogue.")

    # 4. Check policy violation figures appear in an agent turn
    for v in gt["policy_violations"]:
        figs = v.get("figures", [])
        if figs:
            fig_found = any(f in all_agent_text for f in figs)
            if not fig_found:
                errors.append(f"Contradicting figure(s) {figs} for clause {v['clause_id']} not stated by agent.")

    # 5. Check critical identity verification elements if GEN-03 / REF-S1 is expected followed
    if gt["sop_steps"].get("GEN-03") == "followed" or gt["sop_steps"].get("REF-S1") == "followed":
        phone_digits = spec["registered_phone_last4"]
        if phone_digits not in all_call_text:
            errors.append(f"Identity verification failed: last 4 digits '{phone_digits}' not requested/verified.")

    # 6. Check GEN-02 recording disclosure within first 2 turns
    if gt["sop_steps"].get("GEN-02") == "followed":
        first_turns_text = " ".join([t["text"].lower() for t in turns[:2]])
        disc_words = ["record", "monitor", "training", "quality"]
        if not any(w in first_turns_text for w in disc_words):
            errors.append("GEN-02 followed check failed: recording disclosure not found in first two turns.")
    elif gt["sop_steps"].get("GEN-02") == "missed":
        first_turns_text = " ".join([t["text"].lower() for t in turns[:2]])
        if any(w in first_turns_text for w in ["recorded", "recording"]):
            errors.append("GEN-02 missed check failed: recording disclosure was present in dialogue.")

    return errors


def run_llm_verification(call_data: Dict[str, Any], spec: Dict[str, Any]) -> LLMVerificationPayload:
    """Runs a single temperature-0 verification call with Gemini checking required elements of critical steps."""
    gt = spec["ground_truth_spec"]
    turns_snippet = [
        {"i": t["i"], "speaker": t["speaker"], "text": t["text"]}
        for t in call_data["turns"]
    ]

    expected_critical_followed = [
        s for s in spec["applicable_steps"]
        if s in CRITICAL_STEPS and gt["sop_steps"].get(s) == "followed"
    ]
    expected_critical_missed = [
        s for s in spec["applicable_steps"]
        if s in CRITICAL_STEPS and gt["sop_steps"].get(s) == "missed"
    ]

    prompt = f"""You are a strict QA Compliance Verification Auditor reviewing a generated call transcript.

TARGET SPECIFICATION:
- Topic: {spec['topic']}
- Quality Target: {spec['quality']}
- Expected Policy Violations (Clause IDs): {[v['clause_id'] for v in gt['policy_violations']]}
- Critical Steps Expected FOLLOWED: {expected_critical_followed}
- Critical Steps Expected MISSED/ABSENT: {expected_critical_missed}

REQUIRED CRITICAL STEP CRITERIA:
- GEN-02: Must deliver recording disclosure in the first two conversation turns.
- GEN-03 / REF-S1: Must ask for and verify BOTH Order ID AND the last 4 digits of the registered phone number before sharing order/account details. If the agent asks only for name or order ID without phone digits, mark critical_steps_observed as false.
- GEN-06: Must not make out-of-policy refund promises.
- REF-S2: Must check correct category window (7 days electronics / 14 days other).
- REF-S4: Must enforce Rs 5,000 threshold limit.
- REF-S5: Must specify original payment method or NEFT for COD.
- ANG-05: Must execute supervisor escalation.
- HLD-02: Must keep hold under 2 minutes.
- HLD-04: Must brief the supervisor before transfer.

TRANSCRIPT TURNS:
{json.dumps(turns_snippet, indent=2)}

TASK:
1. For each expected violation, confirm if the agent stated the policy incorrectly.
2. For each critical step expected FOLLOWED, verify that all its REQUIRED elements are satisfied.
3. For each critical step expected MISSED, confirm that the agent truly omitted it.
4. Set all_passed to true ONLY if the transcript strictly satisfies this contract with zero unlisted critical omissions.
"""

    return gemini_gateway.generate_structured(
        prompt=prompt,
        schema=LLMVerificationPayload,
        system_instruction="Strictly audit whether dialogue satisfies the ground truth contract.",
        temperature=0.0,
        max_output_tokens=1500,
        thinking_budget=100
    )


def generate_single_call_with_verification(spec: Dict[str, Any], step_definitions: Dict[str, Any]) -> Dict[str, Any]:
    """Generates a call transcript using Gemini and verifies it, regenerating up to 2 times on failure."""
    prompt = create_generation_prompt(spec, step_definitions)
    gt = spec["ground_truth_spec"]

    max_attempts = 3
    last_failure_notes = []

    for attempt in range(1, max_attempts + 1):
        logger.info(f"Generating {spec['id']} (attempt {attempt}/{max_attempts})...")
        
        try:
            payload: LLMTranscriptPayload = gemini_gateway.generate_structured(
                prompt=prompt,
                schema=LLMTranscriptPayload,
                system_instruction="You are a professional dialogue writer generating realistic customer service transcripts adhering strictly to compliance benchmarks.",
                temperature=0.8,
                max_output_tokens=8192,
                thinking_budget=0,
                call_id=spec["id"]
            )
        except Exception as e:
            logger.error(f"Unrecoverable error during generation of {spec['id']}: {e}")
            raise e

        turns = [t.model_dump() for t in payload.turns]
        for idx, t in enumerate(turns, start=1):
            t["i"] = idx

        call_data = {
            "id": spec["id"],
            "topic": spec["topic"],
            "quality": spec["quality"],
            "split": spec["split"],
            "applicable_sops": spec["applicable_sops"],
            "applicable_steps": spec["applicable_steps"],
            "hold_scenario": spec["hold_scenario"],
            "product_name": spec["product_name"],
            "product_price": spec["product_price"],
            "product_category": spec["product_category"],
            "order_id": spec["order_id"],
            "registered_phone_last4": spec["registered_phone_last4"],
            "agent_name": spec["agent_name"],
            "customer_name": spec["customer_name"],
            "customer_persona": payload.customer_persona,
            "turns": turns,
            "ground_truth": {
                "sop_steps": gt["sop_steps"],
                "policy_violations": [],
                "customer_emotion_arc": payload.customer_emotion_arc or gt["customer_emotion_arc"],
                "gaps": gt["gaps"]
            }
        }

        # Step A: Deterministic Checks
        det_errors = verify_transcript_deterministic(call_data, spec)
        if det_errors:
            logger.warning(f"Deterministic verification failed (attempt {attempt}): {det_errors}")
            last_failure_notes = det_errors
            continue

        # Step B: Associate violation turn numbers to specific agent turns
        resolved_viols = []
        for v in gt["policy_violations"]:
            matched_turn = None
            figs = v.get("figures", [])
            for t in turns:
                if t["speaker"] == "agent":
                    if any(f in t["text"] for f in figs):
                        matched_turn = t["i"]
                        break
            if not matched_turn:
                agent_turn_ids = [t["i"] for t in turns if t["speaker"] == "agent"]
                matched_turn = agent_turn_ids[len(agent_turn_ids) // 2] if agent_turn_ids else 3

            resolved_viols.append({
                "turn": matched_turn,
                "said": turns[matched_turn - 1]["text"],
                "clause_id": v["clause_id"],
                "severity": v["severity"],
                "correct_fact": v["correct_fact"]
            })
        call_data["ground_truth"]["policy_violations"] = resolved_viols

        # Step C: LLM Verification Pass (temperature 0)
        try:
            ver_res = run_llm_verification(call_data, spec)
            if ver_res.all_passed:
                call_data["verified"] = True
                call_data["verification_notes"] = f"Passed: {ver_res.notes}"
                return call_data
            else:
                logger.warning(f"LLM verification failed (attempt {attempt}): {ver_res.notes}")
                last_failure_notes = [ver_res.notes] + ver_res.unintended_deviations
        except Exception as e:
            logger.warning(f"Verification LLM call encountered error: {e}")
            last_failure_notes = [f"Verification LLM error: {e}"]

    # If retries exhausted without passing verification, save with verified=False
    logger.warning(f"Verification failed after {max_attempts} attempts. Saving {spec['id']} with verified=False.")
    call_data["verified"] = False
    call_data["verification_notes"] = f"Failed verification: {'; '.join(last_failure_notes)}"
    return call_data


def reorder_interleaved(matrix: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Reorders matrix in a round-robin fashion across topics and qualities."""
    by_topic = {}
    for item in matrix:
        by_topic.setdefault(item["topic"], []).append(item)

    interleaved = []
    max_len = max(len(v) for v in by_topic.values())
    
    # In each round, take from each topic while alternating qualities
    topic_order = list(by_topic.keys())
    for idx in range(max_len):
        for t_idx, topic in enumerate(topic_order):
            items = by_topic[topic]
            if idx < len(items):
                interleaved.append(items[idx])

    return interleaved


def main():
    parser = argparse.ArgumentParser(description="Generate synthetic call transcripts for ShopEase QA Agent.")
    parser.add_argument("--limit", type=int, default=None, help="Maximum number of calls to generate")
    parser.add_argument("--sleep", type=float, default=2.0, help="Minimum delay in seconds between LLM calls")
    parser.add_argument("--rpm", type=float, default=8.0, help="Rate limit target in requests per minute (default: 8)")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility")
    parser.add_argument("--interleave", action="store_true", help="Round-robin across topics and qualities")
    parser.add_argument("--topic", type=str, default=None, help="Filter to only generate calls for a specific topic")
    parser.add_argument("--model", type=str, default=None, help="Override Gemini model identifier")
    args = parser.parse_args()

    if args.model:
        gemini_gateway.model_name = args.model.strip()
        gemini_gateway._init_client()
        logger.info(f"Model overridden via CLI: {gemini_gateway.model_name}")

    out_dir = REPO_ROOT / "data" / "transcripts"
    out_dir.mkdir(parents=True, exist_ok=True)

    step_definitions = load_all_sop_step_definitions()
    matrix = build_scenario_matrix(seed=args.seed)

    if args.topic:
        target_t = args.topic.lower().strip()
        matrix = [c for c in matrix if c["topic"].lower() == target_t]
        logger.info(f"Filtered matrix to topic '{target_t}': {len(matrix)} calls.")

    if args.interleave:
        matrix = reorder_interleaved(matrix)
        logger.info("Reordered scenario matrix in interleaved round-robin mode.")

    if args.limit:
        matrix = matrix[:args.limit]

    logger.info(f"Target run set: {len(matrix)} calls.")

    # Compute sleep based on target RPM
    effective_sleep = max(args.sleep, 60.0 / args.rpm)
    logger.info(f"Rate limiting configured: {args.rpm} RPM (effective delay: {effective_sleep:.1f}s)")

    manifest_rows = []
    manifest_path = out_dir / "_manifest.csv"

    # Resumability: read existing manifest
    existing_manifest = {}
    if manifest_path.exists():
        with open(manifest_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                existing_manifest[row["id"]] = row

    for idx, spec in enumerate(matrix, start=1):
        call_id = spec["id"]
        call_file = out_dir / f"{call_id}.json"

        # Resumable: skip existing file
        if call_file.exists():
            logger.info(f"[{idx}/{len(matrix)}] Skipping existing file: {call_file.name}")
            with open(call_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            manifest_rows.append({
                "id": data["id"],
                "topic": data["topic"],
                "quality": data["quality"],
                "split": data["split"],
                "verified": data.get("verified", False),
                "n_turns": len(data["turns"]),
                "n_violations": len(data["ground_truth"]["policy_violations"])
            })
            continue

        logger.info(f"[{idx}/{len(matrix)}] Processing {call_id} (topic: {spec['topic']}, quality: {spec['quality']}, split: {spec['split']})...")

        try:
            call_data = generate_single_call_with_verification(spec, step_definitions)
        except Exception as e:
            logger.error(f"Generation stopped due to unrecoverable error on {call_id}: {e}")
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

        # Rate-limiting delay between generation runs
        if idx < len(matrix):
            time.sleep(effective_sleep)

    # Write manifest CSV
    with open(manifest_path, "w", newline="", encoding="utf-8") as f:
        fieldnames = ["id", "topic", "quality", "split", "verified", "n_turns", "n_violations"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(manifest_rows)

    verified_total = sum(1 for r in manifest_rows if str(r["verified"]).lower() == "true")
    logger.info(f"✅ Generated/Updated {len(manifest_rows)} transcripts ({verified_total} verified). Manifest saved to {manifest_path}")


if __name__ == "__main__":
    main()
