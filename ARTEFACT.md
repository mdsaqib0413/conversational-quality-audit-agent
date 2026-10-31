# Conversational Quality Audit Agent - Repository Artefacts (`v0.2-eval-obs`)
**Team:** Vibe Check Crew  
**Context:** ShopEase India / Prodloop Capstone Assessment

This document provides a factual, verified inventory of all technical components, datasets, evaluation suites, and configurations existing in this repository at tag `v0.2-eval-obs`.

---

### a) Dataset Status: Verified vs. Unverified
- **Kaggle Telugu Dataset Status:** Directly inspected on disk under `data/telugu/` (Samples 01, 02, 03).
- **Verified Facts (Measured Directly):**
  - `Sample - 01`: 2 mono WAV files (`SPEAKER_00.wav`, `SPEAKER_01.wav`), 8000 Hz, 349.6s each.
  - `Sample - 02`: 3 mono WAV files (`SPEAKER_00/01/02.wav`), 8000 Hz, 448.6s each.
  - `Sample - 03`: 3 mono WAV files (`SPEAKER_00/01/02.wav`), 8000 Hz, 379.4s each.
  - Format is time-aligned mono tracks on a shared timeline, NOT dual-channel stereo.
- **Unverified Items:** License, Telugu language acoustic confirmation, domain/call-center content, acoustic bleed-through between tracks, and PII presence.
- **Data Used in Current Evaluation Benchmark:**
  - 14 Golden English reference calls (`data/transcripts/`, e.g., `call_001` through `call_108`).
  - 8 Controlled Synthetic Telugu call fixtures (`eval_data/synthetic_fixtures.py`, clearly marked `[SYNTHETIC]`).

---

### b) ASR Engine Status & Evidence
- **Implementation:** `faster-whisper` (`model_size="small"`, `language="te"`).
- **Status:** **PROVISIONAL (untested on real Telugu audio)**.
- **Evidence:** The `small` Whisper model is selected as a provisional default based on container memory limits (~1.0 GB RAM footprint). Empirical benchmarking against Gemini audio on the Telugu dataset tracks remains to be conducted.

---

### c) Scorecard Architecture: `scorecard/scorecard_v1.yaml`
- **Location:** `scorecard/scorecard_v1.yaml` (cleanly supersedes `data/rubric.yaml` while preserving backwards compatibility).
- **Criteria Defined:**
  1. `identity_verification` (Mandatory, Critical, Observable): Verification of Order ID + last 4 phone digits before account disclosure. Failure caps score $\le 70.0$.
  2. `greeting_and_recording_disclosure` (Mandatory, Major, Observable): ShopEase brand greeting + call recording disclosure.
  3. `hold_handling` (Mandatory when hold occurs, Major, Observable): Permission requested, duration stated, return acknowledged. Holds $>120$s penalized.
  4. `issue_understood_and_resolved` (Graded, Major, Observable): End-to-end resolution assessment across entire dialogue.
  5. `closure_and_next_steps` (Graded, Minor, Inferred/Observed): Recap and commitment; colloquial hesitation (*"sare, chuddam le"*) flagged as non-committal.
  6. `empathy_and_communication` (Graded, Minor, Inferred): Evaluated strictly as qualitative interpretation; cannot fail a call independently.

---

### d) Evaluation Harness & Formal Results (`eval/`)
- **Split Configuration:** `eval_data/split.json` isolates calls into `dev` (17 calls) and `heldout` (7 calls). Enforced by `tests/test_eval_separation.py`.
- **Pricing Table:** `eval/pricing.yaml` documents Gemini 1.5 Flash ($0.075 / 1M input tokens, $0.300 / 1M output tokens).
- **Pass Rules:** `eval/PASS_RULE.md` defines pre-declared acceptance gates.
- **Evaluation Runner:** `eval/run_eval.py` generates metrics CSV and Markdown reports in `eval/results/v0.2-eval-obs/`.
- **Verified Benchmark Results:**
  - Identity Verification Recall: **100.0%** (2/2) [PASS]
  - Hold Handling Recall: **100.0%** (1/1) [PASS]
  - Separation Violations: **0** [PASS]
  - Evidence Validity: **100.0%** (135/135) [PASS]
  - Handoff Correctness: **100.0%** (2/2) [PASS]
  - False Rejection Rate: **0.0%** (0/15) [PASS]
  - Graded Exact Agreement: **100.0%** (94/94) [PASS]
  - Model Requests / Audit: **1.82** (Target $\le 3.0$) [PASS]
  - Estimated Cost / Audit: **$0.000245 USD** (Target $\le \$0.005$) [PASS]
  - Overall Pass Rule Outcome: **PASS**

---

### e) Blank Human Label Templates
Per project guidelines, ground-truth labels for real calls must be human-annotated. The following template files remain blank and have been explicitly moved to `eval_data/labels/templates/`:
1. `eval_data/labels/templates/te_real_001.template.yaml` (Awaiting human annotation)
2. `eval_data/labels/templates/te_real_002.template.yaml` (Awaiting human annotation)
3. `eval_data/labels/templates/te_heldout_001.template.yaml` (Awaiting human annotation)
4. `eval_data/labels/templates/te_heldout_002.template.yaml` (Awaiting human annotation)
- **Annotation Guidelines:** Documented in `eval_data/LABELLING_GUIDE.md` (multi-annotator rubric and tie-breaking workflow).

---

### f) Observability & Forensic Tracing
- **Tracing Module:** `src/audit/tracer.py` writes step-by-step logs to `traces/<run_id>.jsonl`.
- **Step Telemetry Logged:** `step_name`, `kind` (`model`/`tool`/`plain_code`), `status` (`ok`/`degraded`/`handoff`/`failed`), `latency_sec`, `tokens_in`, `tokens_out`, `cost_usd`, `inputs_summary`, `outputs_summary`, `error_text`.
- **UI Integrations:**
  - **Trace Tab:** Added to `app/streamlit_app.py` in the Report view.
  - **Observability Hub:** Added as dedicated page `app/observability.py` displaying system KPIs, benchmark history, and trace inspection.

---

### g) Deployment Readiness & Containerization
- **`Dockerfile`:** Python 3.11-slim container with FFmpeg, libsndfile1, non-root paths, Streamlit port 8501, and native HTTP healthcheck.
- **`.dockerignore`:** Excludes raw audio, test caches, local traces, credentials, and venvs.
- **`DEPLOY.md`:** Step-by-step runbook for Streamlit Community Cloud, Hugging Face Spaces (Docker), and Render.
- **Memory Rationale:** Explains why `faster-whisper` `small` (~1.0 GB RAM) is chosen over `medium`/`large` to prevent container OOM crashes on free 2 GB cloud tiers.

---

### h) Scenario Tests (Prodloop Assessment)
- `tests/test_telugu_foundation.py`:
  - `test_scenario_a_identity_verification_breach_caps_score`: Validates Turn 3 address disclosure before verification, enforces critical failure cap $\le 70.0$. Clearly labelled `[SYNTHETIC TELUGU FIXTURE]`.
  - `test_scenario_b_holds_and_ambiguous_closure`: Validates extraction of 2 hold intervals and flags colloquial closure *"sare, chuddam le"* as unresolved. Clearly labelled `[SYNTHETIC TELUGU FIXTURE]`.

---

### i) System Architecture & Workflow Diagrams
- **Architecture Diagram:** [docs/diagrams/architecture.mmd](docs/diagrams/architecture.mmd) (Mermaid representation of all 5 system subgraphs).
- **Workflow Diagram:** [docs/diagrams/workflow.mmd](docs/diagrams/workflow.mmd) (Decision flow showing quality gate, scope gate, call state, model calls, and reviewer loop).

---

### j) Phase 2 Team Ownership Table (Blank for Team Allocation)

| Component / Subsystem | Primary Owner | Secondary Reviewer | Target Milestone | Status / Notes |
|---|---|---|---|---|
| **Real Telugu Audio Ingestion & Kaggle Ingestion** | *[Unassigned]* | *[Unassigned]* | Sprint 1 | Awaiting dataset download |
| **Human Ground-Truth Labeling (`eval_data/labels/`)**| *[Unassigned]* | *[Unassigned]* | Sprint 1 | Follow `LABELLING_GUIDE.md` |
| **Real Telugu ASR Benchmarking (Whisper vs Gemini)** | *[Unassigned]* | *[Unassigned]* | Sprint 1 | Run on 3 real calls |
| **Streaming Audio / WebSocket Live Copilot** | *[Unassigned]* | *[Unassigned]* | Sprint 2 | Sliding window of 3-5 turns |
| **Hindi (`hi`) Expansion & Multilingual SOPs** | *[Unassigned]* | *[Unassigned]* | Sprint 3 | Add Hindi lexicon & prompts |
| **Production Cloud Deployment & Monitoring** | *[Unassigned]* | *[Unassigned]* | Sprint 3 | Deploy via `Dockerfile` |
