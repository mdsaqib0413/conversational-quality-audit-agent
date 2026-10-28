# Conversational Quality Audit Agent (ShopEase) - Team Vibe Check Crew

Upload a customer-support call (MP3/WAV) and get an evidence-backed audit: transcript with speaker separation,
emotion arc and conversation gaps, SOP adherence, policy compliance via RAG over the company policies/SOPs,
a 0-100 score with grade, and a coaching report (PDF) for the agent.

## Quick start

```powershell
pip install -r requirements.txt
copy .env.example .env         # then put your key + a model from `python scripts/list_models.py`
python -m pytest tests -q      # 60+ offline tests, no API needed
python -m streamlit run app/streamlit_app.py --server.fileWatcherType none --server.runOnSave false --browser.gatherUsageStats false
```

> **Tip:** Use the helper scripts `run_app.bat` (Windows cmd) or `run_app.ps1` (PowerShell) — they run the command above from the project root automatically.


Command line: `python scripts/audit_cli.py data/audio/call_001_stereo.mp3 --pdf`
Free checks (0 API requests): `python eval/run_eval.py --no-llm` and `python scripts/audio_smoke_test.py data/audio/call_001_stereo.mp3`

## How an audit works (2 API requests per call, 3 for mono audio)

```
audio -> faster-whisper -> speaker separation (stereo channels | 1 LLM request for mono)
      -> metrics + topic + situation signals            (deterministic, no LLM; reusable live in Phase 2)
      -> LLM request 1: SOP steps + empathy/communication + customer emotions + gaps
      -> RAG: retrieve policy clauses (BM25 + embeddings) -> LLM request 2: what did the agent promise vs the policy
      -> every quote is verified against the transcript (unverifiable claims are dropped or downgraded)
      -> deterministic scoring from data/rubric.yaml (critical-step cap, policy penalties)
      -> report (UI, PDF, JSON). Audits are cached, so repeating a call costs 0 requests.
```

Design rules: no fake data on failure (errors are raised and shown), every finding cites a transcript turn,
the model may only cite retrieved clause IDs, scoring is code, not LLM.

## LLM configuration (.env)
`GEMINI_MODEL` + optional `GEMINI_FALLBACK_MODELS` (switched automatically when a model's daily free quota is gone), and an
optional OpenAI-compatible fallback (Groq, OpenRouter, local Ollama) via `LLM_FALLBACK_PROVIDER=openai_compat`.
The app sidebar shows the model in use and how many requests were made today.

---

## Real call data

Source: [axondata/call-center-speech-dataset](https://www.kaggle.com/datasets/axondata/call-center-speech-dataset) on Kaggle.

Two English calls are used as `data/audio/real_calls/en_real_001.mp3` and `en_real_002.mp3` (both 8 kHz mono, ~11–14 min).

> ⚠️ **These are financial fraud / scam call recordings**, not ShopEase support calls. Policy compliance is not meaningful; the pipeline correctly reports 0/30 for the policy dimension. They are used as a robustness test for transcription and diarization on real 8 kHz mono telephony audio.

`data/audio/real_calls/` and `call-center-speech-dataset/` are in `.gitignore` (licensed sample, do not commit). Run `python scripts/ingest_real_calls.py` to audit them.

---

# Conversational Quality Audit Agent (ShopEase)
**Team:** Vibe Check Crew  
**Context:** AI-Powered Customer Support Quality Assurance & Compliance Platform for ShopEase India.

---

## 📌 Project Overview
The **Conversational Quality Audit Agent** is an end-to-end QA and compliance platform for audio customer support calls:
1. **Audio Ingestion & Transcription:** Transcribes customer calls using `faster-whisper`, performing speaker diarization (Agent vs. Customer).
2. **Conversational Dynamics:** Analyzes silence/gap intervals, talk-to-listen ratios, interruptions, and turn-level emotion/sentiment trajectories.
3. **Policy & SOP Auditing (RAG):** Uses `sentence-transformers` (`bge-small`) and ChromaDB to match dialogue turns against ShopEase policies and Standard Operating Procedures (SOPs).
4. **LLM Evaluation Gateway:** Executes structured verification through a centralized Gemini wrapper (`src/audit/llm.py`), ensuring every compliance finding links directly to verbatim conversational evidence and specific policy clauses.
5. **Interactive UI & PDF Audit Reports:** Delivers an interactive Streamlit dashboard and exports comprehensive PDF coaching reports via Jinja2.
6. **Phase 2 Readiness:** Standalone sliding-window topic detection and policy retrieval functions designed for real-time live call agent assistance.

---

## 🛠️ Sensible Assumptions
1. **Operating System & Audio Engine:** The system runs on Windows with Python 3.11. Audio files are converted to 16kHz mono WAV internally for uniform processing.
2. **FFmpeg Requirement:** FFmpeg is assumed to be installed and available on the Windows system `PATH` (essential for `pydub`, `librosa`, and `faster-whisper`).
3. **LLM Access & Rate Limits:** Gemini API Free Tier has strict requests-per-minute (RPM) limits. The audit pipeline is designed to minimize LLM calls (e.g., batching turn evaluations into concise prompt payloads) and employs exponential backoff retry logic.
4. **Vector Embeddings:** Uses `BAAI/bge-small-en-v1.5` for RAG chunk embeddings, persisted locally in `data/chroma_db/`.
5. **PDF Engine:** Uses `xhtml2pdf` alongside `Jinja2` to provide native, cross-platform PDF export on Windows without requiring complex GTK/Cairo binaries.
6. **Diarization & Audio Pipeline:** If multi-channel audio is not present, speaker attribution relies on `faster-whisper` timestamps combined with speaker energy clustering or turn heuristics. Synthetic call evaluation scripts use `edge-tts` with distinct Indian English voices.

---

## 🚀 Setup Steps for Windows

### 1. Prerequisites
- **Python 3.11** (64-bit)
- **Git for Windows**
- **FFmpeg**:
  Install via `winget`:
  ```powershell
  winget install Gyan.FFmpeg
  ```
  Or download from [gyan.dev](https://www.gyan.dev/ffmpeg/builds/) and add the `bin` directory to your user `PATH`. Verify with:
  ```powershell
  ffmpeg -version
  ```

### 2. Environment Setup
Clone the repository and create a Python virtual environment:
```powershell
cd c:\Users\mdsaq\OneDrive\Documents\audit-agent
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 3. Install Dependencies
```powershell
pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Configure Environment Variables
Copy `.env.example` to `.env` and supply your Gemini API key:
```powershell
Copy-Item .env.example .env
```
Edit `.env`:
```ini
GEMINI_API_KEY=your_actual_gemini_api_key_here
GEMINI_MODEL=gemini-1.5-flash
WHISPER_MODEL=small
```

---

## 🏃 Running the Application
Launch the Streamlit interactive audit dashboard:
```powershell
streamlit run app/streamlit_app.py
```

---

## 🎙️ Dataset and Audio Generation

The dataset generation pipeline creates ground-truth audited customer support calls across 6 topics with pre-injected compliance adherence, policy violations, and speech gaps.

### 1. Verify Environment & Model Setup
Verify system dependencies, API credentials, model availability, and structured JSON generation using the automated diagnostic checklist:
```powershell
python scripts/check_setup.py
```
To discover all models available for your API key that support `generateContent`:
```powershell
python scripts/list_models.py
```
Set the selected model in your `.env` file (e.g., `GEMINI_MODEL=gemini-2.5-flash` or `GEMINI_MODEL=gemini-flash-latest`).

### 2. Applicable SOP Steps Mapping
Transcripts use granular, context-dependent step mappings rather than monolithic SOP checklists:
- **General Call Flow (`GEN-01` to `GEN-08`):** Universal baseline steps applied across all calls.
  - `GEN-02`: Recording disclosure within the first two turns.
  - `GEN-03`: Caller verification requiring **both** Order ID AND the last 4 digits of registered phone number.
- **Refund Inquiries (`REF-S1` to `REF-S7`):** Applied exclusively when `topic == "refund"`.
- **Customer Complaints (`ANG-01` to `ANG-06`):** Applied exclusively when `topic == "complaint"`.
- **Hold & Transfer Scenarios (~1/3 of all calls include exactly one scenario):**
  - `"hold_only"`: `HLD-01`, `HLD-02`, `HLD-03` (courtesy hold with check-in under 2 min).
  - `"transfer"`: `HLD-04` (warm transfer to supervisor/specialist with briefing).
  - `"callback"`: `HLD-05` (supervisor callback commitment within 2-4 hours).
  - `"none"`: No hold/transfer steps.
- **Ground Truth Isolation:** Each transcript's `ground_truth.sop_steps` contains strictly and exclusively the step IDs enumerated in its `applicable_steps`.

### 3. Generate Call Transcripts
Generate transcripts using Gemini with native structured JSON output, thinking budget minimization, truncation auto-recovery, and rate limiting:
```powershell
# Interleaved generation across all topics and qualities (rate-limited at 8 RPM)
python scripts/generate_transcripts.py --limit 6 --interleave --rpm 8

# Filter by a single topic
python scripts/generate_transcripts.py --topic refund --limit 8

# Override model via CLI
python scripts/generate_transcripts.py --limit 6 --interleave --model gemini-flash-latest
```
Transcripts are output to `data/transcripts/call_XXX.json` alongside `data/transcripts/_manifest.csv`. In case of failed attempts, raw model outputs are saved to `data/transcripts/_failed/<call_id>_attemptN.txt`.

### 4. Validate Transcripts
Run strict Pydantic and rule validation to verify consecutive turn indexing, ground-truth step isolation, topic-matched policy violations, prevention of catalog hint leakage, and verification records:
```powershell
python scripts/validate_transcripts.py
```

### 5. Synthesize Audio (Edge-TTS + Pydub)
Generate realistic Indian English dual-speaker audio without API keys:
```powershell
# Synthesize first 2 calls (mono + channel-separated stereo)
python scripts/make_audio.py --first 2

# Synthesize all available transcripts with light acoustic noise
python scripts/make_audio.py --all --noise

# Synthesize a specific call
python scripts/make_audio.py --id call_001
```
Audio files are saved to `data/audio/<id>.mp3` (mixed mono) and `data/audio/<id>_stereo.mp3` (agent left channel, customer right channel) with tracking in `data/audio/_audio_manifest.csv`.

---

## 📁 Project Architecture
```
audit-agent/
├── app/
│   └── streamlit_app.py              # Streamlit Web UI & Live Call Simulator
├── data/
│   ├── audio/                        # Sample & uploaded audio files (.gitkeep)
│   ├── policies/                     # ShopEase Markdown Policies (stable clause IDs)
│   ├── rubric.yaml                   # Weighted scoring rubric & grading scale
│   ├── sops/                         # ShopEase Standard Operating Procedures
│   └── transcripts/                  # Sample turn-level transcripts
├── src/audit/
│   ├── __init__.py
│   ├── diarize.py                    # Speaker role separation & turns
│   ├── emotion.py                    # Sentiment, emotion & conversation gap analysis
│   ├── llm.py                        # Centralized Gemini LLM client with retries
│   ├── pipeline.py                   # Master end-to-end audit orchestrator
│   ├── policy_check.py               # RAG-grounded policy compliance checker
│   ├── rag.py                        # Sentence-transformers + ChromaDB indexer
│   ├── report.py                     # Jinja2 PDF audit report builder
│   ├── schemas.py                    # Strict Pydantic models for validation
│   ├── scoring.py                    # Rubric penalty calculation & grade calculator
│   ├── sop_check.py                  # Step-by-step SOP checklist verification
│   ├── topic.py                      # Rolling-window topic detector (Phase 2)
│   └── transcribe.py                 # faster-whisper speech-to-text wrapper
├── eval/                             # Evaluation benchmarks & metrics
├── scripts/                          # Synthetic audio generation & helper tools
├── tests/                            # Pytest test suite
├── requirements.txt
├── PROJECT_BRIEF.md
└── GEMINI.md
```
