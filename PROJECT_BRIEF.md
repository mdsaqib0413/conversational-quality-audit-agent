# PROJECT BRIEF: Conversational Quality Audit Agent

## 1. Executive Summary
- **Project Name:** Conversational Quality Audit Agent
- **Team:** Vibe Check Crew
- **Organization / Context:** ShopEase (Fictional Indian E-commerce Enterprise)
- **Target Platform:** Python 3.11 / Streamlit / Modern Quality Management Dashboard

## 2. Core Problem & Workflow
Quality Assurance (QA) in customer support operations is traditionally manual, sampling fewer than 2-5% of total calls. This results in biased feedback, unmonitored compliance risks, and delayed coaching. 

The **Conversational Quality Audit Agent** automates call audit end-to-end:
1. **Audio Ingestion:** Ingest customer support audio recordings (`.mp3` / `.wav`).
2. **Transcription & Diarization:** High-precision speech-to-text using `faster-whisper` and speaker role separation (Agent vs. Customer).
3. **Conversational Metrics & Emotion:** Detect conversational gaps, prolonged silences, talk-to-listen ratios, and turn-level sentiment/emotion shifts.
4. **RAG-Powered Compliance Auditing:** Retrieve authoritative company policies and SOP clauses via ChromaDB (`bge-small` embeddings) and evaluate whether the agent adhered to standard operating procedures and accurately stated policies.
5. **Structured Audit Reporting:** Compute standard rubric scores (SOP Adherence, Policy Compliance, Empathy, Communication) and generate an exportable Jinja2-rendered PDF report with specific turn-level evidence.

## 3. Phase 2 Vision: Live Call Assistance
Designed from day one to support real-time agent co-piloting:
- **Rolling-Window Turn Analysis:** Decoupled topic detection and policy retrieval operating over the last $N$ turns (e.g., sliding window of 3-5 turns).
- **Proactive Policy Surfacing:** Instantly push verified policy clauses and prescribed scripts to the agent's screen during live interactions.

## 4. Technical Stack
- **Language & Runtime:** Python 3.11
- **Speech Processing:** `faster-whisper`, `pydub`, `librosa`, `soundfile`
- **Vector Store & Embeddings:** `sentence-transformers` (`BAAI/bge-small-en-v1.5`), `ChromaDB`
- **Application & Visualization:** `Streamlit`, `Plotly`
- **Report Generation:** `Jinja2`, `xhtml2pdf` / PDF export engine
- **Synthetic Audio & Tooling:** `edge-tts`, `pyyaml`, `pydantic`
- **LLM Gateway:** Google Gemini API (Free tier / `gemini-1.5-flash` or `gemini-2.0-flash`), isolated strictly behind `src/audit/llm.py` with retry backoff and rate-limit handling.

## 5. Non-Negotiable Operational Rules
1. **Single LLM Gateway:** All LLM access MUST go through `src/audit/llm.py`. No direct API calls elsewhere in the codebase.
2. **Structured Outputs:** All LLM analysis MUST return strict JSON conforming to Pydantic schemas at low temperature ($T \le 0.2$).
3. **Evidence-Backed Findings:** Every audit finding, violation, or score deduction must cite exact verbatim quotes and turn numbers / timestamps.
4. **Strict Policy Grounding:** The model is prohibited from hallucinating policy rules. If a topic is not covered in retrieved policy text, it must report `"no relevant policy found"`.
5. **Consistent Business Facts:** Specific facts (such as the 7-day electronics return window, Rs 5,000 refund threshold, 2-minute hold limit, mandatory call-recording disclosure, and order ID + 4-digit phone verification) are immutable across all policies, SOPs, and prompts.
