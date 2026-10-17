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

### 1. Inspect Available Gemini Models
Run the model discovery utility to check which Gemini models are available for your API key:
```powershell
python scripts/list_models.py
```
Set the selected model in your `.env` file (e.g., `GEMINI_MODEL=gemini-2.0-flash`).

### 2. Generate Call Transcripts
Generate the 48-call scenario matrix using the Gemini API (free tier with configurable delay, resumable):
```powershell
# Generate all 48 calls (rate-limit safe sequential processing)
python scripts/generate_transcripts.py --sleep 6.0

# Or generate first 6 calls for testing
python scripts/generate_transcripts.py --limit 6

# Offline deterministic generation (no API key required)
python scripts/generate_transcripts.py --limit 6 --offline
```
Transcripts are output to `data/transcripts/call_XXX.json` alongside `data/transcripts/_manifest.csv`.

### 3. Validate Transcripts
Run strict Pydantic validation across all generated transcripts to ensure consecutive turn indexing, valid rubric step mappings, policy clause verification, and quality bucket integrity:
```powershell
python scripts/validate_transcripts.py
```

### 4. Synthesize Audio (Edge-TTS + Pydub)
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
