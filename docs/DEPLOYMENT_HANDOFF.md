# Deployment Handoff: Conversational Quality Audit Agent (AuditIQ)

**Target Platform:** Hugging Face Spaces (Docker SDK)  
**Application Server:** Streamlit on Port `7860`  
**Base Runtime:** Python 3.11 (64-bit)  

This document serves as the implementation specification for deploying AuditIQ to a production containerized environment on Hugging Face Spaces.

---

## 1. Runtime Architecture & Startup Assets

During cold start, the application initializes heavy machine learning and retrieval assets locally before serving HTTP requests:

1. **`faster-whisper` (Speech-to-Text):**
   - Transcribes customer support audio (`.mp3` / `.wav`) into timestamped turn segments.
   - Defaults to model `small` with language auto-detection (`auto`, supporting English, Telugu, Hindi).
2. **`BAAI/bge-small-en-v1.5` (`sentence-transformers`):**
   - Dense vector embedding model (384-dimensional) used for semantic policy and SOP clause retrieval.
   - Must be baked into the container image cache at build time to prevent runtime downloads.
3. **Embedded `Qdrant` Local Vector Database:**
   - Runs in embedded local disk mode (`qdrant-client`, storage located under `data/qdrant_db/`).
   - Pairs dense vector embeddings with BM25 keyword matching for hybrid RAG over authoritative clauses in `data/policies/`.

---

## 2. Environment Variable Configuration

> **CRITICAL SECURITY NOTE:**  
> Provide variable **NAMES ONLY**. Never bake secret values into the Dockerfile, image layers, or git repository. Configure sensitive secrets strictly in the Hugging Face Space Settings under **Repository Secrets**.

### Required Production Secrets & Configuration
- `GEMINI_API_KEY`: API credential for Google Gemini (LLM gateway).
- `POLICY_MODEL`: Dedicated model strictly used for policy compliance evaluation (default: `gemini-3.5-flash`).
- `GEMINI_MODEL`: Model used for general conversational analysis, SOP step tracking, diarization, and emotion classification (default: `gemini-2.5-flash`).
- `LANGFUSE_PUBLIC_KEY`: Langfuse Cloud public API key (observability).
- `LANGFUSE_SECRET_KEY`: Langfuse Cloud secret API key.
- `LANGFUSE_HOST`: Langfuse base URL / host endpoint (e.g. `https://cloud.langfuse.com`).
- `HF_HUB_OFFLINE`: Set to `1` in the container environment once models are baked into image cache.

### Proposed Deployment Security & Feature Flags
- `APP_PASSWORD`: Shared passcode for password-gating sensitive public actions (e.g. running live audits or accessing live assist).
- `DEMO_MODE`: Set to `1` for public deployments. Disables live file uploads and defaults to pre-rendered demo audits.
- `DEMO_LIVE`: Set to `1` to selectively allow authenticated users to execute live audits against the Gemini API.

---

## 3. Containerization Requirements (Hugging Face Spaces Docker)

### A. Dockerfile Specification
- **Base Image:** `python:3.11-slim`
- **System Dependencies:**
  - Install `ffmpeg`, `git`, and `curl` via `apt-get`:
    ```dockerfile
    RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
        git \
        curl \
        && rm -rf /var/lib/apt/lists/*
    ```
- **PyTorch Installation:**
  - Install CPU-only PyTorch wheels to avoid CUDA dependencies and minimize image footprint:
    ```dockerfile
    RUN pip install --no-cache-dir torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
    ```
- **Pre-download Models at Build Time:**
  - Run build-time Python commands to cache model weights into `/home/user/.cache/huggingface/hub`:
    ```dockerfile
    RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('BAAI/bge-small-en-v1.5')"
    RUN python -c "from faster_whisper import WhisperModel; WhisperModel('small', device='cpu', compute_type='int8')"
    ```
- **Hugging Face Hub Offline Enactment:**
  - Set container environment: `ENV HF_HUB_OFFLINE=1`
- **Non-Root User (Hugging Face Requirement):**
  - HF Spaces run containers under UID 1000. Create and switch to a non-root user:
    ```dockerfile
    RUN useradd -m -u 1000 user
    USER user
    ENV HOME=/home/user \
        PATH=/home/user/.local/bin:$PATH
    WORKDIR /home/user/app
    ```
- **Exposed Port & Start Command:**
  - Expose port `7860`.
  - Start Streamlit listening on all interfaces:
    ```dockerfile
    EXPOSE 7860
    CMD ["streamlit", "run", "app/streamlit_app.py", "--server.port", "7860", "--server.address", "0.0.0.0", "--server.fileWatcherType", "none", "--server.runOnSave", "false", "--browser.gatherUsageStats", "false"]
    ```

### B. `.dockerignore` Specification
Ensure the following directories and files are excluded from the Docker build context:
```gitignore
.env
.env.*
.git
.agents
.cadra
tests
data/cache/audits_old
eval
eval_data
traces/*.jsonl
scratch
__pycache__
*.py[cod]
.pytest_cache
```

---

## 4. Public Demo Hardening & Security Controls

When deployed to a public Hugging Face Space, the application must be protected against abuse, quota exhaustion, and credential leakage:

1. **`DEMO_MODE` Operation:**
   - When `DEMO_MODE=1` is set:
     - The audio file uploader on the "Audit a call" page is hidden or disabled.
     - Live model evaluations against the external Gemini API are blocked unless `DEMO_LIVE=1` is explicitly set and `GEMINI_API_KEY` is present.
     - The audit report picker loads pre-audited calls from a shipped `data/demo_cache/` directory by `call_id` regardless of cache key hash, clearly displaying the model used and generation timestamp.
2. **`APP_PASSWORD` Authentication Gate:**
   - Implement a simple password gate in Streamlit session state (`st.session_state["authenticated"]`).
   - If `APP_PASSWORD` is configured, visitors can explore cached reports freely, but must enter the passcode to access "Audit a call" or trigger live processing.
3. **Per-Session Rate Limiting:**
   - In `st.session_state`, maintain a counter of live audits executed (e.g. limit to 2 live audits per browser session) to prevent single-user quota draining.
4. **Offline Container Health Check:**
   - Hugging Face Spaces probes port `7860`. Ensure the health check relies strictly on Streamlit's native endpoint (`http://localhost:7860/_stcore/health`) or a local script that verifies knowledge base initialization without pinging external network hosts.

---

## 5. Cache Key Sensitivity in Normal Mode vs. Demo Mode

### Normal Mode Behavior
- The pipeline determines audit cache filenames using:
  $$\text{cache\_filename} = \text{call\_id} + \text{"\_"} + \text{\_audit\_key(call)} + \text{".json"}$$
- The 16-hex `_audit_key` is a deterministic SHA-256 hash incorporating:
  - Transcript text content
  - `POLICY_MODEL` string
  - `GEMINI_MODEL` string
  - Knowledge Base version (`kb.version`)
  - Policy Context (`POLICY_CONTEXT`)
  - Pipeline revision identifier (`audit-v9`)
- **Important Gotcha:** If the deployment teammate changes `POLICY_MODEL` (e.g. from `gemini-3.5-flash` to another model) or alters prompts, the computed `_audit_key` changes. In normal mode, the Streamlit report picker filters strictly by the active `_audit_key`, causing previously cached files to disappear from the selector.

### Demo Mode Solution
- In `DEMO_MODE=1`, the audit loader should bypass strict hash matching and index audits from `data/demo_cache/` (or shipped cache) by `call_id`, annotating each report in the UI with its recorded `meta.model` and `generated_at` timestamp.

---

## 6. Free-Tier Quota Notes & Strategy

- **Gemini Free-Tier Constraints:**
  - `gemini-3.5-flash` has strict Requests-Per-Minute (RPM) and Daily Requests (RPD) limits on free-tier keys.
  - Hitting the daily limit raises `429 RESOURCE_EXHAUSTED` / `Daily quota exhausted`.
- **Zero-API Demo Architecture:**
  - Pre-audit all 13 dev benchmark calls (`call_001` through `call_108`) and real call samples, and commit them into `data/demo_cache/`.
  - Shipped cache files satisfy 100% of standard visitor page views, PDF downloads, and dashboard explorations with **0 API requests and 0 cost**.

---

## 7. Implementation Checklist for the Deployment Teammate

### Required Tests to Add
- [ ] `test_demo_mode_blocks_upload_and_live_eval`: Verifies file uploader and API triggers are disabled when `DEMO_MODE=1` without `DEMO_LIVE=1`.
- [ ] `test_demo_mode_loads_shipped_cache_by_call_id`: Verifies audit reports load from demo cache regardless of `_audit_key` divergence.
- [ ] `test_app_password_gate`: Verifies session state protects live pages when `APP_PASSWORD` is set.
- [ ] `test_per_session_audit_limit`: Verifies the per-session execution counter stops abuse after $N$ runs.
- [ ] `test_offline_health_endpoint`: Verifies local health check executes with zero external network requests.

### Untested Items Requiring Verification in Container Environment
- [ ] **UID 1000 Filesystem Permissions:** Verify non-root user `user` can read/write embedded Qdrant files in `data/qdrant_db/` and write transient files to `/tmp`.
- [ ] **Container RAM Headroom:** Confirm memory usage during simultaneous Whisper transcription and Qdrant search remains within the standard 16 GB Space allocation.
- [ ] **Audio Streaming Over Space Proxy:** Confirm HTML5 audio player controls in Streamlit stream `.mp3` and `.wav` recordings smoothly through the HF Spaces reverse proxy.
