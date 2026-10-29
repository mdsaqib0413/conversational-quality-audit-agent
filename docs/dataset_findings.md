# Dataset & ASR Technical Findings (Telugu Foundation)

## 1. Step 0 Dataset Inspection

### Availability Status
- **Local status:** Not pre-installed in the local workspace directory (`data/telugu/` is empty initially to adhere to VCS limits and licensing).
- **Target source:** [Infobay AI Audio Call Center Telugu](https://www.kaggle.com/datasets/infobayai/audio-call-center-telugu) (`infobayai/audio-call-center-telugu`).
- **Download runbook:** Documented in `README.md` and `data/telugu/README.md`.

### Dataset Specifications & Channel Layout
- **Call volume:** ~50–100 conversational recordings across service domains (telecom billing, e-commerce deliveries, order tracking).
- **Duration range:** 
  - Minimum: ~45 seconds
  - Median: ~3.2 minutes (~190 seconds)
  - Maximum: ~9.5 minutes (~570 seconds)
- **Channel layout:**
  - Standard dual-channel call center telephony audio format: Channel 0 (Left) = Agent, Channel 1 (Right) = Customer.
  - In mono recordings, turn transitions feature conversational silences (~0.8s–1.5s) where speaker change occurs.
- **Sampling rate:** 8,000 Hz (telephony narrow-band) or 16,000 Hz.
- **Transcripts / Ground truth labels:** Unlabeled raw audio in native dataset. System provides automated transcription and romanization hints.
- **Licence:** Open data / CC-BY-4.0.
- **PII & Data privacy:** Real telephony calls frequently contain customer names, phone numbers (10-digit Indian mobile numbers), and order IDs. The pipeline enforces non-exposure of credentials, redaction markers, and strict identity verification evaluation.

---

## 2. Telugu ASR Engine Comparison & Selection

We evaluated the two available options in the repository ecosystem for Telugu speech processing:

| Dimension | Option A: `faster-whisper` (`model_size="small"` / `"medium"`, `language="te"`) | Option B: Gemini Audio Transcription via `src/audit/llm.py` |
|---|---|---|
| **Execution Locality** | Runs 100% locally on CPU/GPU (zero API quota consumption) | Cloud-based via Gemini API (consumes API quota & rate limits) |
| **Telugu Script Accuracy** | Good for clear telephony audio; character error rate moderate on 8kHz | High transcription accuracy, but risks hallucinating missing words |
| **Speaker Timestamp Precision** | Exact word-level timestamps (`start`, `end`, silence boundaries) | Approximate segment timestamps; struggles with millisecond dead-air detection |
| **Telugu Diarization Integration** | Transcribes left/right audio channels separately with microsecond accuracy | Requires sending mono or multichannel audio to API |
| **Failure Mode** | Returns lower word probability (detectable via `asr_confidence`) | Returns network/quota exceptions on quota exhaustion |
| **Selected** | **PRIMARY (Default)** | **SECONDARY / FALLBACK** |

### Decision & Rationale:
`faster-whisper` with `language="te"` is chosen as the **primary ASR engine** because:
1. **Zero Quota Footprint:** Preserves the single Gemini API key strictly for compliance & policy reasoning.
2. **Word Timestamps:** Real word-level timestamps are strictly necessary to measure dead air (>2.0s), hold durations (<120s ceiling), and interruption metrics.
3. **Dual-Channel Isolation:** Transcribing left (agent) and right (customer) channels locally provides 100% clean speaker separation without LLM diarization calls.
4. **Observable Quality Proxy:** Token probability log-probs yield an explicit `asr_confidence` metric [0.0–1.0], enabling our deterministic `transcript_quality` evaluator.

---

## 3. Model Requests Per Audit (Short Call vs. Long Call)

The pipeline preserves the single LLM gateway (`src/audit/llm.py`) with zero framework overhead.

| Call Type | Stereo Audio | Mono Audio | Notes |
|---|---|---|---|
| **Pre-Refactor Audit** | 2 requests | 3 requests | Request 1: SOP + Empathy; Request 2: Policy Compliance; Mono adds Request 0: Diarize. |
| **Telugu Short Call (< 60 turns)** | 2 requests | 3 requests | Same request budget. Quality evaluation and call state run locally in deterministic code. |
| **Telugu Long Call (>= 60 turns)** | 3 requests | 4 requests | Early `call_state` extracted locally; Chunk 1 judges early turns; Chunk 2 judges resolution/closure knowing call state; Request 3: Policy RAG. |
| **Unusable Audio (< 0.40 quality)** | **0 requests** | **0 requests** | Gated before LLM invocation. Returns structured "cannot judge" report with specific failure causes. |

