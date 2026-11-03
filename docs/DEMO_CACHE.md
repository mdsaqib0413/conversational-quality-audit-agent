# Demo Cache Specification & Architecture (`data/demo_cache/`)

## 1. Overview and Purpose
The **Demo Cache** (`data/demo_cache/`) provides a self-contained, pre-computed benchmark suite of all 13 canonical development calls (`call_001` through `call_108`).

### Core Objectives
1. **Zero-API Demo Deployments:** Powers public demonstrations on platforms like Hugging Face Spaces (free tier) with **zero Gemini API calls**, zero token costs, and immunity to rate-limit or quota failures (`429 RESOURCE_EXHAUSTED`).
2. **Offline Resilience:** Enables instant viewing of audit scorecards, coaching guidance, policy compliance findings, PDF exports, and observability traces without network access or active API credentials.
3. **Decoupled Key Matching:** Traditional pipeline caching relies on strict dynamic SHA-256 hash matching (`_audit_key`). In demo mode, audits are indexed directly by `call_id`, preventing missing-report issues if model configurations or prompt revisions change.

---

## 2. Directory Layout & Artifacts

The demo cache is organized to support both legacy single-file loaders and multi-asset page requirements:

```
data/demo_cache/
├── MANIFEST.json                    # Index manifest with salt, models, date, scores & sizes
├── call_001.json                    # Root-level audit report (backward-compatible loader)
├── ...
├── call_108.json                    # Root-level audit report
├── call_001/                        # Per-call multi-asset bundle
│   ├── audit.json                   # Full AuditReport JSON
│   ├── trace.jsonl                  # Execution telemetry trace
│   └── transcript.json              # Canonical source transcript
├── ...
├── call_108/
│   ├── audit.json
│   ├── trace.jsonl
│   └── transcript.json
└── traces/                          # Standalone trace directory for Observability dashboard
    ├── run_call_001_789672.jsonl
    └── ...
```

---

## 3. `MANIFEST.json` Specification

`data/demo_cache/MANIFEST.json` records build provenance, active model versions, and per-call metrics:

```json
{
  "audit_key_salt": "audit-v9",
  "sop_model": "gemini-3.5-flash-lite",
  "policy_model": "gemini-3.5-flash",
  "build_date": "2026-11-04T01:47:25",
  "calls": [
    {
      "call_id": "call_001",
      "overall": 100.0,
      "grade": "A",
      "status": "ok",
      "sop_model": "gemini-3.5-flash-lite",
      "policy_model": "gemini-3.5-flash",
      "llm_requests": 2,
      "trace_id": "run_call_001_789672",
      "sizes": {
        "audit_json_bytes": 56343,
        "trace_jsonl_bytes": 40978,
        "transcript_json_bytes": 10560
      }
    }
  ]
}
```

---

## 4. Runtime File Dependencies by Feature

| Feature / Page | Files Read at Runtime | Purpose |
| :--- | :--- | :--- |
| **Report View** | `data/demo_cache/<call_id>.json` (or `<call_id>/audit.json`) | Displays overall gauge, grade badge, KPI cards, emotion timeline, conversational gaps, coaching tabs, and transcript turns. |
| **Policy / Evidence View** | `data/demo_cache/<call_id>.json`, `data/policies/*.md`, `data/sops/*.yaml` | Evaluates policy results and displays verbatim clause text via `KnowledgeBase.by_id`. |
| **Audio Player** | `data/audio/<call_id>.mp3` *(optional)* | Streams audio in synchronized timeline player. If missing, player displays audio unavailable and cleanly falls back to transcript view. |
| **PDF Export** | `data/demo_cache/<call_id>.json`, `data/policies/*.md` | Generates exportable PDF report with scorecards and policy citations. Does not require audio. |
| **Observability Dashboard** | `data/demo_cache/traces/*.jsonl` (or `<call_id>/trace.jsonl`), `eval/pricing.yaml` | Renders system telemetry, step latencies, token consumption, and model cost estimates. |

> [!NOTE]
> **Transcript Mode Operation:**  
> The report view, policy/evidence explorer, scorecard breakdown, coaching cards, and PDF export operate **100% without audio files**. All dialogue turns, timestamps, and emotion markers are embedded inside the audit report JSON.

---

## 5. How to Rebuild the Demo Cache

The demo cache is generated via `scripts/build_demo_cache.py`:

```bash
python scripts/build_demo_cache.py
```

### Build Workflow & Validation Rules
1. **Cache Integrity Verification:**
   - Scans `data/cache/audits/` to confirm that **all 13 dev calls** (`call_001` through `call_108`) have **exactly one current-key audit file**.
   - If any audit is missing or contains stale/duplicate hashes, the script refuses to run.
2. **Asset Packaging:**
   - Copies each audit file to `data/demo_cache/<call_id>.json` and `data/demo_cache/<call_id>/audit.json`.
   - Copies transcripts from `data/transcripts/<call_id>.json` to `data/demo_cache/<call_id>/transcript.json`.
   - Locates execution traces in `traces/<trace_id>.jsonl` and copies them to `data/demo_cache/<call_id>/trace.jsonl` and `data/demo_cache/traces/<trace_id>.jsonl`.
3. **Path Sanitization & Security Scan:**
   - Replaces local host absolute paths (e.g. `E:\audit-agent`) with relative references (`.`).
   - Scans all output files to confirm zero API keys (`AIza`, `sk-lf-`, `pk-lf-`) and zero host drive paths appear in version-controlled data.
4. **Manifest Generation:**
   - Compiles `MANIFEST.json` with scores, grades, models, request counts, and file byte counts.

---

## 6. Demo Mode Loader Architecture (Implementation Guide)

> **Important:** Do not implement `DEMO_MODE` directly in this phase; follow this specification when wiring demo mode in deployment.

### Audit Discovery Logic in Normal vs. Demo Mode

- **Normal Mode:**
  ```python
  # Matches current dynamic SHA-256 hash
  current_key = pipeline._audit_key(call)
  expected_file = f"data/cache/audits/{call_id}_{current_key}.json"
  ```
- **Demo Mode (`DEMO_MODE=1`):**
  ```python
  # Bypasses hash matching and discovers by call_id
  demo_dir = ROOT / "data" / "demo_cache"
  audit_file = demo_dir / f"{call_id}.json"
  if not audit_file.exists():
      audit_file = demo_dir / call_id / "audit.json"
  ```

### Key Benefits of Call ID Discovery
1. **Resilient to Model Changes:** If `POLICY_MODEL` in production is set to `gemini-3.5-flash` while local development tested `gemini-2.5-flash`, the demo cache remains 100% discoverable.
2. **Metadata Transparency:** The report header reads model provenance directly from `meta.sop_model` and `meta.policy_model` inside the audit JSON, accurately showing which model generated the pre-computed audit.

---

## 7. Git-Ignore Status & Version Control Decision

- **`data/cache/` (Local Scratch):**  
  `data/cache/` and its subdirectories (`audits/`, `audits_old/`, `audits_backup/`) are **git-ignored** to prevent bloated commits and local churn.
- **`data/demo_cache/` (Shipped Production Cache):**  
  `data/demo_cache/` is **explicitly NOT git-ignored** and **MUST be committed to git**.  
  Committing this directory guarantees that Hugging Face Spaces (or containerized deployments) receives the 13 canonical benchmark audits at image build time, allowing the public app to serve reports without requiring Gemini API quotas or runtime network calls.
