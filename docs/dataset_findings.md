# Dataset & ASR Technical Findings (Telugu Foundation)

> [!WARNING]
> **DATASET STATUS: UNVERIFIED (dataset not inspected)**  
> The Kaggle Telugu dataset (`infobayai/audio-call-center-telugu`) is not present in local workspace storage (`data/telugu/`). All volume, duration, sample rate, channel layout, licence, and PII statements below are provisional and unverified against physical files.

---

## 1. Step 0 Dataset Inspection

### Availability Status
- **Local status:** Absent in the local workspace directory (`data/telugu/` contains only download instructions).
- **Target source:** [Infobay AI Audio Call Center Telugu](https://www.kaggle.com/datasets/infobayai/audio-call-center-telugu) (`infobayai/audio-call-center-telugu`).
- **Download runbook:** Documented in `data/telugu/README.md`.

### Dataset Specifications & Channel Layout
- **Call volume:** UNVERIFIED (dataset not inspected; assumed ~50–100 calls from external card).
- **Duration range:** UNVERIFIED (dataset not inspected; min/median/max duration unknown until downloaded).
- **Channel layout:** UNVERIFIED (dataset not inspected; telephony layout assumed dual-channel agent-left/customer-right, but not verified on real files).
- **Sampling rate:** UNVERIFIED (dataset not inspected; 8 kHz vs 16 kHz unconfirmed).
- **Transcripts / Ground truth labels:** UNVERIFIED (dataset not inspected; existence of native transcripts or speaker labels unverified).
- **Licence:** UNVERIFIED (dataset not inspected; listed as CC-BY-4.0 on Kaggle page, but physical metadata license file not inspected).
- **PII & Data privacy:** UNVERIFIED (dataset not inspected; presence of customer phone numbers, names, or addresses unverified).

---

## 2. Telugu ASR Engine Selection

> [!NOTE]
> **ASR STATUS: PROVISIONAL (untested on real Telugu audio)**  
> Because real Telugu audio was absent during Phase 1, `faster-whisper` (`model_size="small"`, `language="te"`) is selected **provisionally** based on architectural zero-quota constraints and local processing capability, not empirical WER/CER benchmarks. Real comparative testing against Gemini audio will occur when audio files are downloaded.

### Provisional Selection Rationale:
1. **Zero Quota Footprint:** Preserves the single Gemini API key strictly for compliance & policy reasoning.
2. **Word Timestamps:** Word-level timestamps are required to measure dead air (>2.0s), hold durations (<120s ceiling), and interruption metrics.
3. **Dual-Channel Isolation:** Transcribing left (agent) and right (customer) channels locally provides clean speaker separation without LLM diarization calls.
4. **Observable Quality Proxy:** Token probability log-probs yield an explicit `asr_confidence` metric [0.0–1.0], enabling our deterministic `transcript_quality` evaluator.

---

## 3. Model Requests Per Audit (Short Call vs. Long Call)

The pipeline preserves the single LLM gateway (`src/audit/llm.py`) with zero framework overhead.

| Call Type | Stereo Audio | Mono Audio | Notes |
|---|---|---|---|
| **Pre-Refactor Audit** | 2 requests | 3 requests | Request 1: SOP + Empathy; Request 2: Policy Compliance; Mono adds Request 0: Diarize. |
| **Telugu Short Call (< 60 turns)** | 2 requests | 3 requests | Same request budget. Quality evaluation and call state run locally in deterministic code. |
| **Telugu Long Call (>= 60 turns)** | 3 requests | 4 requests | Early `call_state` extracted locally; Chunk 1 judges early turns; Chunk 2 judges resolution/closure; Request 3: Policy RAG. |
| **Unusable Audio (< 0.40 quality)** | **0 requests** | **0 requests** | Gated before LLM invocation. Returns structured "cannot judge" report with specific failure causes. |
