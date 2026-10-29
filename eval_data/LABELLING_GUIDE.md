# Human Ground-Truth Labelling Guide (Prodloop QA Scorecard v1.0)

This guide governs manual human annotation of customer support audio interactions for model calibration and evaluation.

## 1. Ethical Guidelines & Ground-Truth Principle
- **Human Authorship Only:** Ground-truth labels must be produced solely by human reviewers listening to the real audio recording and inspecting the transcript. **Never use AI to generate ground truth.**
- **Privacy:** Reviewers must never write personal identifying information (full phone numbers, bank accounts, passwords) into labels. Use turn IDs and relative quotes.

## 2. Reviewer Workflow & Double Annotation
1. **Primary Annotation:** Reviewer 1 listens to the call audio and populates `eval_data/labels/<call_id>.yaml`.
2. **Independent Secondary Annotation:** For heldout evaluation calls, Reviewer 2 independently audits the call.
3. **Disagreement Resolution:**
   - If Reviewer 1 and Reviewer 2 disagree on a **mandatory** criterion verdict (`followed` vs `missed`), a third Lead QA Auditor adjudicates the tie-breaker based on verbatim transcript quotes.
   - For **graded** criteria (0–5 scale), disagreements within $\pm 1$ level are averaged; differences $\ge 2$ require joint review of the cited turn timestamps.

## 3. Scorecard Fields Reference
For each criterion in `scorecard/scorecard_v1.yaml`, annotate:
- `verdict`:
  - Mandatory: `followed` | `partial` | `missed` | `not_applicable`
  - Graded: `excellent` (5) | `proficient` (4) | `adequate` (3) | `deficient` (1) | `failed` (0)
- `kind`: `observed` (strictly factual quotes from transcript) vs `inferred` (qualitative appraisal of tone, intent, or warmth).
- `evidence`:
  - `turn_ids`: List of authoritative turn numbers `[e.g. 1, 3]`.
  - `quote`: Verbatim quote (max 25 words).
  - `timestamp_range`: `[start_seconds, end_seconds]`.
- `cannot_judge`: Set `true` only if audio was distorted/silent/unusable or out-of-scope non-support interaction.

## 4. Specific Criteria Rules
1. `identity_verification`: Critical failure (`missed`) if the agent discusses customer order or address details BEFORE asking for Order ID + phone digits, even if the issue was subsequently resolved.
2. `greeting_and_recording_disclosure`: Must include brand greeting ("ShopEase"), agent name, and call recording disclosure in opening agent turns.
3. `hold_handling`: Mandatory when a hold occurs. Agent must ask permission, state expected duration (<120s), and thank customer on return.
4. `issue_understood_and_resolved`: Graded holistically across the entirety of the conversation.
5. `closure_and_next_steps`: Check for clear next steps. Phrases like *"sare, chuddam le"* indicate ambiguous hesitation and cannot be graded as full satisfaction.
6. `empathy_and_communication`: Inferred evaluation of courtesy, active listening, and professionalism.

