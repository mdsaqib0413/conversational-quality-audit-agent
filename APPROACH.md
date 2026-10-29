# Conversational Quality Audit Agent - Technical Approach (Phase 1)
**Team:** Vibe Check Crew  
**Context:** ShopEase India / Prodloop Capstone

## Section A: Problem Definition & Operational Scope
- **Current State:** Traditional call center quality assurance samples under 3% of total interactions, leading to unmonitored compliance risks, data privacy breaches, and delayed coaching.
- **Phase 1 Scope:** Establishing the foundational multi-stage audit pipeline for customer support calls with first-class support for Telugu (`te`) and English (`en`). Covers dual-channel and mono telephony audio ingestion, deterministic quality evaluation, strict evidence-backed SOP adherence, RAG-grounded policy verification, and human calibration.
- **Out of Scope (Phase 1):** Real-time streaming assistant, deployment infrastructure, multi-tenant databases. `TODO (phase 2)`

## Section B: System Architecture & Workflow Pipeline
- **Orchestration:** Pure Python sequential pipeline (`src/audit/pipeline.py`) without external agent frameworks.
- **LLM Gateway:** Strict single-gateway pattern (`src/audit/llm.py`) interfacing with Google Gemini API with automatic exponential backoff, rate limit handling, and fallbacks.
- **Language & Diarization:**
  - Dual-channel telephony: Left channel (Agent) and Right channel (Customer) transcribed independently using `faster-whisper` (`language="te"` default).
  - Mono audio: Diarization via single LLM speaker labelling (`speaker_id_agent.md`) with deterministic acoustic cue fallback.
- **Deterministic Quality Gating:** Transcripts pre-screened into `good`, `degraded`, or `unusable`. `unusable` calls bypass LLM processing and return structured "cannot judge" reports.
- **Running Call State:** Early call state (identity verification, recording disclosure, issue statement, holds) is tracked deterministically and passed to chunked prompt windows.

## Section C: Grounding, RAG & Compliance Rubric Design
- **Knowledge Base:** ChromaDB vector store backed by `BAAI/bge-small-en-v1.5` embeddings combined with deterministic keyword matching.
- **Authoritative Policies:** Fixed business facts (7-day electronics return window, ₹5,000 refund threshold, 2-minute hold ceiling) immutable across policies and prompts.
- **Grounded Verification:** Every compliance finding must cite verbatim quotes and exact turn numbers verified against transcript audio. Unverifiable claims are automatically dropped or downgraded.
- **Scorecard v1.0:** Explicit separation of `observed` factual breaches (identity verification, greeting, hold handling, policy contradictions) vs. `inferred` qualitative interpretations (empathy, tone, ambiguous closures).

## Section D: Observability, Evaluation & Error Analysis
- **Reviewer Calibration:** Human-in-the-loop review storage (`data/reviews/<call_id>.json`) allowing QA managers to accept or overturn findings side-by-side without deleting AI evidence.
- **Observability Dashboard:** Basic Streamlit application (`app/streamlit_app.py`) for audio playback, synchronized transcript navigation, and review decision management. Advanced distributed tracing and live telemetry metrics are `TODO (phase 3)`.
- **Offline Evaluation Suite:** Suite of deterministic tests and golden call expectations evaluating SOP accuracy, policy violation detection, and score stability.

## Section E: Phase 2 Vision & Production Readiness
- **Live Call Copilot:** Real-time sliding window analysis over the last 3-5 turns, proactive policy recommendation cards, and turn-by-turn hold timers. `TODO (phase 2)`
- **Enterprise Scale & Hindi Expansion:** Multi-language expansion to Hindi (`hi`) and regional Indian dialects. `TODO (phase 2)`
- **Cloud Deployment:** Containerization and production deployment architecture. `TODO (phase 3)`

