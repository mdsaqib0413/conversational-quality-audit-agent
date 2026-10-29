# Prodloop QA Scorecard (v1.0) & Grading System

## Overview
`scorecard/scorecard_v1.yaml` defines the structured QA criteria for auditing customer-support voice interactions. It integrates directly with the existing `data/rubric.yaml` mathematical weights (40% SOP Adherence, 30% Policy Compliance, 15% Empathy, 15% Communication) while adding strict operational boundaries tailored for Telugu and bilingual enterprise auditing.

## Criterion Design Principles

### 1. Observable vs. Inferred Separation
- **Observable Criteria:** Factual determinations grounded purely in explicit transcript speech (e.g., whether the agent asked for the last 4 digits of the phone number before disclosing the address, or whether permission was requested before placing on hold).
- **Inferred Criteria:** Interpretations of conversational tone, emotional warmth, and empathy. These are explicitly tagged with `kind: inferred` and isolated into their own dedicated section in the audit report so reviewers can distinguish between hard procedural facts and subjective quality judgements.

### 2. Core Mandatory Criteria
- **`identity_verification` (Critical):**
  - **Rule:** Agent must verify customer identity (Order ID + last 4 digits of registered phone number) BEFORE discussing account status, order items, addresses, or monetary refunds.
  - **Failure:** Disclosing account details without prior verification results in an immediate `critical` finding and caps the entire call score at **70.0%** (Grade D/C ceiling), even if the issue was resolved politely.
- **`greeting_and_recording_disclosure` (Major):**
  - **Rule:** Telephony compliance requires informing the caller that the call is recorded.
- **`hold_handling` (Major):**
  - **Rule:** Any hold requires permission, reason, and gratitude on return. Hold durations exceeding the 2-minute (120-second) ceiling trigger penalty.
- **`policy_compliance` (Critical/Major/Minor):**
  - Matches agent statements against retrieved RAG clauses (refund windows, ₹5,000 supervisor limit).

### 3. Graded Holistic Criteria
- **`issue_understood_and_resolved` (Graded 0-5):**
  - Evaluated across the entire call flow, ensuring proper root-cause diagnosis.
- **`closure_and_next_steps` (Graded 0-5):**
  - Evaluates action recap and customer closure. Non-committal responses (e.g., Telugu *"sare, chuddam le"*) are classified as ambiguous closures and prevented from registering as confirmed customer satisfaction.
- **`empathy_and_communication` (Graded 0-5, Inferred):**
  - Measures warmth, active listening, and composure.

## Critical Failure Score Cap
When any critical mandatory criterion is missed:
- `critical_failure = True`
- `overall_score = min(calculated_score, 70.0)`
- The report highlights the breach under **Observed Gaps (Critical Failure)** with turn timestamps.

