# Deployment Runbook: Conversational Quality Audit Agent

This document provides deployment guidelines for hosting the **Conversational Quality Audit Agent** on free or low-cost cloud container services.

---

## 1. Resource Sizing & Hardware Constraints

| Component | In-Memory (RAM) | Storage (Disk) | Recommended Platform Tier |
|---|---|---|---|
| **Streamlit UI + Python Runtime** | ~350 MB | ~500 MB base container | 1 vCPU / 1 GB RAM minimum |
| **`faster-whisper` (`small` model)** | ~1.0 GB RAM | ~480 MB model weights | 2 vCPU / 2-4 GB RAM recommended |
| **`bge-small-en-v1.5` (Embeddings)** | ~300 MB RAM | ~130 MB weights | Shared with Python runtime |
| **Qdrant Vector Store (embedded local)** | ~150 MB RAM | ~1 MB index | Local ephemeral storage |
| **Total Operational Sizing** | **~2.0 – 2.5 GB RAM** | **~1.5 GB free disk** | Free/Starter Tier (Hugging Face Spaces, Streamlit Cloud, Render) |

> [!IMPORTANT]
> **Why `faster-whisper` `small` is the Deployment Default:**  
> The `medium` (1.5 GB weights, ~3.0 GB RAM) and `large-v3` (3.1 GB weights, ~6.0 GB RAM) Whisper models frequently trigger Out-Of-Memory (OOM) eviction on free container tiers (capped at 2 GB or 3 GB limits). The `small` model fits comfortably within 2 GB memory footprints while sustaining accurate speech recognition and timestamp alignment.

---

## 2. Platform 1: Streamlit Community Cloud (Free)

Streamlit Community Cloud connects directly to your GitHub repository and serves the application with native secret management.

### Deployment Steps:
1. Push this repository to GitHub (ensure `.env`, raw audio, and `data/telugu/*.wav` remain ignored).
2. Navigate to [share.streamlit.io](https://share.streamlit.io) and sign in with GitHub.
3. Click **"New app"** and specify:
   - **Repository:** `your-username/audit-agent`
   - **Branch:** `main`
   - **Main file path:** `app/streamlit_app.py`
4. Expand **"Advanced settings..."** -> **"Secrets"** and enter your API configuration in TOML format:
   ```toml
   GEMINI_API_KEY = "AIzaSy..."
   GEMINI_MODEL = "gemini-2.5-flash" # or any model printed by `python scripts/list_models.py`
   ```
5. Click **"Deploy!"**. The build will automatically install `packages.txt` (`ffmpeg`) and `requirements.txt`.

---

## 3. Platform 2: Hugging Face Spaces (Docker / Free)

Hugging Face Spaces provides 2 vCPU and 16 GB RAM free on CPU Basic tier, running your native Dockerfile.

### Deployment Steps:
1. Sign in to [Hugging Face](https://huggingface.co) and create a **New Space**.
2. Space Configuration:
   - **Space Name:** `conversational-quality-audit-agent`
   - **License:** `apache-2.0` (or `mit`)
   - **Space SDK:** Choose **Docker** -> **Blank Dockerfile**.
3. Push your repository to the Hugging Face Space Git remote or connect via GitHub integration.
4. Add Secrets:
   - Go to **Settings** -> **Variables and secrets**.
   - Click **"New secret"**:
     - Key: `GEMINI_API_KEY`
     - Value: `AIzaSy...`
   - Click **"New variable"**:
     - Key: `GEMINI_MODEL`
     - Value: `gemini-2.5-flash` (or a model printed by `python scripts/list_models.py`)
5. The container builds from `Dockerfile` and listens on port `8501`.

---

## 4. Platform 3: Render (Web Service / Docker)

1. Create a **New Web Service** on [render.com](https://render.com).
2. Connect your GitHub repository.
3. Select **Environment:** `Docker`.
4. Plan: `Free` or `Starter` ($7/mo for persistent RAM).
5. Under **Environment Variables**, add:
   - `GEMINI_API_KEY`: `AIzaSy...`
   - `GEMINI_MODEL`: `gemini-2.5-flash` (or a model printed by `python scripts/list_models.py`)
   - `STREAMLIT_SERVER_PORT`: `8501`
   - `STREAMLIT_SERVER_ADDRESS`: `0.0.0.0`

---

## 5. Post-Deploy Health Check & Verification

Once deployed, verify the installation with these smoke checks:

1. **HTTP Healthcheck:**
   ```bash
   curl -f http://<your-deployed-domain>/_stcore/health
   # Expected response: 200 OK
   ```

2. **Offline UI Navigation Smoke Test:**
   - Open the web application URL.
   - Verify that the **Privacy Notice banner** appears in the sidebar.
   - Navigate to the **"Observability"** page: verify that formal benchmarks (`v0.2-eval-obs`), metrics, and prototype comparisons render without errors.
   - Open **"Report"** tab: verify that the audio player and the **"Trace"** tab load.

3. **Live Audit Test:**
   - In **"Audit a call"**, select a bundled sample call (e.g., `call_001_stereo`).
   - Run the audit. Verify that findings populate with high certainty, evidence quotes are verbatim, and a structured trace is recorded.

