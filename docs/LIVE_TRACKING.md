# Phase 1 Live Call Tracking Specification

This document details the architecture, data models, rule engine, and integration protocols for **Phase 1 Live Call Tracking** in AuditIQ. Phase 1 provides deterministic, zero-AI, sub-millisecond compliance monitoring and policy surfacing designed to consume streaming caption events.

---

## 1. Overview & Architecture

Quality Assurance traditionally occurs post-call, discovering compliance infractions hours or days after the interaction ended. The goal of live call tracking is to provide active agent co-piloting:
1. **Zero-AI Request Overhead:** Evaluates compliance milestones and timing gaps entirely in deterministic code, consuming zero Gemini API quota.
2. **Sub-Millisecond Evaluation:** Ingests turn events with latency under 1ms, ensuring zero impact on host telephony or client dashboards.
3. **Pluggable Event Contract:** Uses a decoupled `CaptionEvent` model so real-time WebRTC or WebSocket transcription feeds (e.g. 100ms interim speech chunks) plug in seamlessly without rewriting business logic.

```
┌─────────────────────────────────────────────────────────────┐
│ Telephony / WebRTC Live Audio Stream (Stereo / Multichannel)│
└──────────────────────────────┬──────────────────────────────┘
                               │ 100ms audio slices
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ Streaming ASR / Caption Service (Whisper / Deepgram / Google)│
└──────────────────────────────┬──────────────────────────────┘
                               │ Streaming text chunks
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ CaptionEvent Adapter (peer_id -> role, final flag, start_ms)│
└──────────────────────────────┬──────────────────────────────┘
                               │ CaptionEvent(final=True/False)
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ LiveRules Engine (Deterministic State & Thresholds)         │
│  - GEN-02 Disclosure Monitor   - HLD-02 Hold Ceiling Timer   │
│  - GEN-03 2FA Breach Guard     - Dead Air & Interruption    │
│  - ANG-02 Empathy Tracker      - BM25 Policy Clause Cards   │
└──────────────────────────────┬──────────────────────────────┘
                               │ De-duplicated LiveAlerts
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ Live Assist Co-Pilot Dashboard (Checklist, Alerts, Clauses) │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. The `CaptionEvent` Schema

The event contract is defined in `src/audit/live/events.py`:

```python
@dataclass
class CaptionEvent:
    call_id: str             # Unique identifier for the active call
    peer_id: str             # Identifier for the audio channel/peer (e.g. 'agent_0', 'customer_0')
    role: str                # Conversational role: 'agent' | 'customer'
    text: str                # Transcribed speech caption text
    start_ms: int            # Milliseconds from call start to caption onset
    end_ms: int              # Milliseconds from call start to caption offset
    final: bool = True       # True if committed/final, False if partial interim hypothesis
    turn_id: Optional[int]   # Sequential turn index (if assigned)
```

### Key Properties:
- `start_sec -> float`: Start timestamp in seconds (`start_ms / 1000.0`).
- `end_sec -> float`: End timestamp in seconds (`end_ms / 1000.0`).
- `duration_ms -> int`: Total speech duration of the slice in milliseconds.
- `to_dict() -> dict` / `from_dict(d) -> CaptionEvent`: Standard serialization helpers.

---

## 3. Mapping a 100ms Live Caption Feed to `CaptionEvent`

In a live production telephony environment (e.g. Twilio Media Streams, Asterisk ARI, FreeSWITCH, or WebRTC), audio packets arrive every 20-100ms. An ASR engine (such as Google Speech-to-Text Live, Deepgram Nova-2, or local streaming Whisper) emits partial and finalized transcripts.

### 3.1 Mapping Rules:
1. **Peer ID to Conversational Role (`peer_id -> role`):**
   - **Stereo Ingestion:** Left channel (channel 0) maps to `peer_id="agent_0"`, `role="agent"`. Right channel (channel 1) maps to `peer_id="customer_0"`, `role="customer"`.
   - **Dual WebRTC Tracks:** The agent's microphone track maps to `role="agent"`; the inbound caller RTP stream maps to `role="customer"`.
   - **Mono Audio Fallback:** If channel separation is absent, the opening speaker greeting containing company brand keywords (`ShopEase`) is identified as `role="agent"`, and subsequent alternating turns map accordingly.
2. **Interim vs. Final Flag (`final`):**
   - While the speaker is actively talking, ASR engines emit partial hypotheses every 100-200ms (`is_final=False`). These map to `CaptionEvent(..., final=False)`.
   - When Voice Activity Detection (VAD) detects end-of-speech or punctuation closure, the ASR engine emits `is_final=True`. This maps to `CaptionEvent(..., final=True)`.
3. **Timestamp Alignment (`start_ms`, `end_ms`):**
   - Telephony streams track monotonic timestamps from call connection ($T_0$).
   - `start_ms = int((packet_start - call_start_time) * 1000)`.
   - `end_ms = int((packet_end - call_start_time) * 1000)`.

---

## 4. Deterministic Rules & Thresholds

All thresholds are centralized in a single configuration dictionary in `src/audit/live/rules.py`:

```python
DEFAULT_LIVE_CONFIG = {
    "disclosure_max_agent_turns": 2,    # GEN-02: Recording disclosure required within first 2 agent turns
    "require_order_id": True,           # GEN-03: Order ID required before account data disclosure
    "require_phone_last4": True,        # GEN-03: Registered phone last-4 required before account disclosure
    "max_hold_seconds": 120.0,          # HLD-02: Maximum hold ceiling without check-in (2 minutes)
    "dead_air_threshold_sec": 4.0,      # COM-01: Silence gap between turns flagged as dead air
    "overlap_threshold_sec": 0.2,       # ANG-01: Agent interrupting/talking over customer threshold
    "empathy_window_turns": 2,          # ANG-02: Agent turns allowed to acknowledge customer distress
    "topic_window_turns": 6,            # RAG: Rolling window turns used for topic & clause retrieval
    "clause_top_k": 4,                  # RAG: Number of authoritative policy clauses surfaced
}
```

### 4.1 Rule Definitions:
1. **Mandatory Recording Disclosure (`GEN-02`):**
   - Evaluates whether the agent articulated statutory call recording notification (`recorded`, `recording`, `monitored`, `quality assurance`) within their first 2 conversation turns.
   - Severity: `danger`.
2. **Caller 2FA Verification & Data Protection (`GEN-03`):**
   - Tracks verification state: Order ID (`ORD-XXXXX`) and last 4 phone digits (`\b\d{4}\b`).
   - If the agent discloses sensitive account details (delivery address, pincode, bank account, wallet, refund amount) before both factors are confirmed, an immediate breach alert fires.
   - Severity: `danger`.
3. **Maximum 2-Minute Hold Ceiling (`HLD-02`):**
   - Detects hold initiation phrases (`brief hold`, `hold the line`, `please hold`).
   - Monitors elapsed silence from customer agreement until the agent returns. If elapsed time exceeds 120.0s (or custom threshold), a ceiling violation alert fires at the exact limit timestamp.
   - Returning from a valid hold is recognized as expected silence, preventing false dead-air alerts.
   - Severity: `danger`.
4. **Dead Air Detection (`COM-01`):**
   - Unannounced silence between turns $\ge 4.0\text{s}$ fires a timing warning. Holds are excluded.
   - Severity: `warning`.
5. **Agent Interruption (`ANG-01` / `COM-02`):**
   - Agent speech beginning $> 0.2\text{s}$ before customer speech ends is flagged as talking over the caller.
   - Severity: `warning`.
6. **Customer Distress & Empathy (`ANG-02` / `GEN-05`):**
   - Identifies customer anger cues (lexicon matching `unacceptable`, `worst`, `fed up`, `cheated`, multiple exclamation marks).
   - If the agent does not articulate sincere empathy (`sorry`, `apologize`, `understand your frustration`, `make this right`) within 2 agent turns, a de-escalation warning fires.
   - Severity: `warning`.
7. **Live Policy Clause Surfacing (RAG):**
   - Computes rolling topic classification over the last 6 turns and queries the offline Knowledge Base via BM25. Top 4 relevant clause cards are continuously refreshed.
   - Severity: `info`.

### 4.2 De-duplication & Interim Isolation:
- **Interim Isolation:** `rules.process_event(ev)` returns `[]` immediately if `ev.final is False`. No compliance alerts or milestone counters advance on uncommitted speech.
- **De-duplication Keys:** Fired alerts are stored in `fired_keys` (e.g. `GEN-02:disclosure_missing`, `GEN-03:unverified_disclosure`, `HLD-02:hold_<turn_id>`, `ANG-02:turn_<turn_id>`). Each condition fires at most once per incident.

---

## 5. Live Assist UI Integration

The upgraded Live Assist page in `app/streamlit_app.py` features:
1. **Interactive Replay Controls:**
   - Sample call selector (`call_001` through `call_108`).
   - Replay speed dropdown: `1x`, `2x`, `5x`, `10x`, and `Instant`.
   - Control buttons: `▶ Play`, `⏸ Pause`, `⏭ Step (+1)`, and `↺ Reset`.
2. **Real-Time Visual Indicators:**
   - **Metrics Bar:** Active status badge (`STREAMING`, `PAUSED`, `CALL ENDED`), call elapsed timer, processed events counter, active topic badge, and alert tallies.
   - **Live Transcript Stream:** Colored chat bubbles with speaker role, turn number, timestamp, and speech text.
   - **Compliance Checklist:** Color-coded status cards for `GEN-02` Disclosure, `GEN-03` 2FA Verification, `ANG-02` Empathy, and `HLD-02` Hold Ceiling.
   - **Real-Time Alert Feed:** Reverse-chronological cards with severity badges, timestamps, triggering quotes, and violation descriptions.
   - **Policy Guidance Cards:** Surfaced clauses dynamically relevant to the active discussion.
3. **Zero API Key Requirement:** Works completely offline without configuring `GEMINI_API_KEY`.

---

## 6. Limits of the Deterministic Rule Engine

While Phase 1 provides instant, cost-free compliance monitoring, it has clear structural boundaries:
1. **No Deep Semantic Verification:** Fast regexes cannot verify whether an agent's technical advice is factually accurate or whether an exception to policy was validly applied.
2. **Subtle Policy Calculations:** Verifying complex return eligibility windows (e.g. 7-calendar-day electronics limit vs. 14-day general return window calculated against delivery dates) requires semantic reasoning best handled by post-call LLM auditing.
3. **Nuanced Tone & Sarcasm:** Customer sentiment is evaluated by explicit lexical markers; subtle irony or passive-aggressive frustration without anger keywords is undetected until post-call evaluation.
4. **Holistic Turn Synthesis:** End-of-call resolution, comprehensive call summary quality (`GEN-07`), and overall communication scores require full transcript synthesis.

---

## 7. What Phase 2 Needs

Phase 2 will build upon this foundation to introduce hybrid real-time intelligence:
1. **Direct WebRTC/Audio WebSocket Ingestion:** Stream PCM audio directly from browser microphones or telephony SIP trunks into the live pipeline.
2. **Low-Latency Edge Model / SLM:** Integrate a compact local model (e.g. 2B/4B parameters on CPU/GPU) to evaluate semantic policy claims during pauses between turns without exhausting Gemini rate limits.
3. **Proactive Agent Scripting:** Push prescribed response scripts to the agent's screen when customer anger or policy objections are detected.
4. **Real-Time Supervisor Alerts:** Trigger webhook notifications to team leads when critical infractions (`GEN-03` breach or `HLD-02` exceeding 3 minutes) occur on active calls.
