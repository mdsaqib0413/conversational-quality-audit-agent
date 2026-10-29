# Conversational Quality Audit Agent - System Artefacts & Architecture (Phase 1)
**Team:** Vibe Check Crew  
**Platform:** ShopEase QA Copilot / Prodloop Capstone

### a) Audio Ingestion & Telephony Specifications
- **Supported Formats:** `.mp3`, `.wav`, `.m4a`, `.flac`
- **Telephony Ingestion:** Handles narrow-band (8 kHz) and broad-band (16 kHz) telephony audio.
- **Telugu Dataset Integration:** Configured for the [Infobay AI Audio Call Center Telugu](https://www.kaggle.com/datasets/infobayai/audio-call-center-telugu) dataset (`data/telugu/`). Download runbook provided in `data/telugu/README.md`.

### b) ASR Benchmarking & Language Adaptation
- **Primary Engine:** `faster-whisper` (`model_size="small"`, `language="te"`).
- **First-Class Setting:** `language` parameter defaults to `"te"` for regional call auditing while maintaining `"en"` compatibility.
- **Turn Enrichment:** Dialogue turns record Telugu script (`text_te`), transliterated Roman script (`text_roman`), word-level timestamps, and token probability proxy (`asr_confidence`).
- **Gating Mechanism:** Deterministic `transcript_quality` evaluator (`src/audit/quality.py`) classifies transcripts into `good`, `degraded`, or `unusable`. Unusable calls halt audit scoring cleanly.

### c) Diarization Strategy & Speaker Separation
- **Dual-Channel Separation:** Separates Channel 0 (Agent / Left) and Channel 1 (Customer / Right) with zero LLM API calls and millisecond boundary detection.
- **Mono Diarization Fallback:** Segment-level LLM speaker labelling via `speaker_id_agent.md` with deterministic acoustic and linguistic cue backup.

### d) Conversational Dynamics & Emotional Trajectory
- **Metrics Tracked:** Talk-to-listen ratios, longest silence duration, agent interruption events, and dead-air breaches (>2.0s).
- **Emotion & Tone Arc:** Customer emotion shifts (angry -> confused -> satisfied) and agent tonal composure (warm, defensive, neutral) mapped across conversation turns.

### e) Policy Knowledge Base & Retrieval Engineering
- **Knowledge Base:** ChromaDB vector index embedded with `BAAI/bge-small-en-v1.5` over authoritative ShopEase policies (`refund_and_returns.md`, `billing_payments.md`, `privacy_identity_verification.md`, `warranty_replacement.md`).
- **Strict Policy Grounding:** Model restricted strictly to retrieved clause IDs. Missing policies yield `"no relevant policy found"` rather than hallucinated rules.

### f) SOP Compliance Engine & Evidence Verification
- **Chunked Analysis & State Preservation:** For calls exceeding 50 turns, `EarlyCallState` (`src/audit/call_state.py`) preserves greeting, verification, and issue context across overlapping windows.
- **Evidence Verification:** Every SOP and policy quote is checked against verbatim turn text. Unverified quotes are downgraded to prevent hallucinated penalties.

### g) Scorecard Architecture & Critical Failure Guardrails
- **Scorecard Definition:** `scorecard/scorecard_v1.yaml` establishes observable vs. inferred criteria categories.
- **Mandatory Failure Cap:** Missed critical identity verification or data privacy disclosure caps total audit score at 70.0% (Grade D/C).
- **Ambiguous Closure Handling:** Phrases such as *"sare, chuddam le"* are flagged as inferred non-committal closures, preventing false claims of customer satisfaction.

### h) Observability Dashboard & Reviewer Calibration
- **User Interface:** Streamlit dashboard (`app/streamlit_app.py`) featuring audio playback, transcript inspection, and QA metrics.
- **Reviewer Persistence:** Human review decisions stored in `data/reviews/<call_id>.json` allowing supervisors to accept or overturn individual AI findings side-by-side.
- **Advanced Centralized Observability & Telemetry:** `TODO (phase 3)`

### i) Live Call Copilot (Phase 2)
- **Real-Time Stream Processing:** Streaming chunk transcription and rolling-window analysis over the last 3 turns. `TODO (phase 2)`
- **Proactive Card Ingestion:** Instantaneous push of verified SOP steps and return policies to live agent screen. `TODO (phase 2)`

### j) Comprehensive System Evaluation & Results
- **Automated Test Suite:** Offline test coverage in `tests/` verifying prompt size caps, request counts, quality gating, and Prodloop scenarios.
- **End-to-End Golden Benchmark:** Multi-call regression test comparing LLM determinations against human-audited ground truth.

