# Data Safety and Privacy Policy

## 1. Overview and Operational Scope
The **Conversational Quality Audit Agent** processes conversational customer support recordings. Customer support dialogues routinely contain sensitive customer Personally Identifiable Information (PII) and financial transaction details. This policy outlines how data is ingested, processed, protected, and isolated during prototype development and operational audits.

---

## 2. PII Identified in Customer Support Calls
In ShopEase customer support calls (including both English and Telugu audio interactions), the following categories of PII and sensitive data may appear:
- **Full Names & Salutations:** Customer identity and agent identity disclosed in opening/closing exchanges.
- **Order Identifiers:** Reference numbers formatted as `ORD-XXXXX` linked to customer purchase history.
- **Contact Information:** Phone numbers (specifically the mandatory last 4 digits requested during identity verification) and email addresses.
- **Physical Delivery Addresses:** Flat numbers, building names, street names, landmarks, and postal PIN codes.
- **Financial & Transaction Data:** Product invoice amounts, bank account/wallet references, and refund values (e.g., transactions exceeding the ₹5,000 threshold).

---

## 3. Pipeline Data Handling and Security Safeguards
The audit architecture strictly enforces the following controls:
1. **Zero Persistent Raw Audio Storage:** Raw audio recordings (`.mp3`, `.wav`) are loaded ephemerally for transcription/diarization and are never committed to version control. All media and audio working directories under `data/telugu/` and session folders are gitignored.
2. **Local Credential Boundary:** Gemini API keys are retrieved strictly via environment variable (`GEMINI_API_KEY`) and routed exclusively through the single gateway module (`src/audit/llm.py`). Keys are never hardcoded, written to disk, or transmitted to third-party frameworks.
3. **Cache Isolation and Scrubbed Transcripts:** Local caching of audit reports is restricted to ephemeral, gitignored cache paths (`cache/`, `eval/results/*/cache`). Reference transcripts included in regression suites (`data/transcripts/`) and evaluation fixtures (`eval_data/synthetic_fixtures.py`) are strictly synthetic or scrubbed of real customer identities.
4. **Structured Tracing Security:** Operational execution logs emitted to `traces/<run_id>.jsonl` capture only pipeline step names, execution runtimes, token counts, and sanitized step summaries. Raw unredacted customer audio waveforms are never logged.

---

## 4. Approved Data Sources
The project operates exclusively on approved data sources:
- **Synthetic Fixtures:** Controlled, synthetic Telugu dialogues generated in `eval_data/synthetic_fixtures.py` and `tests/fixtures/`, clearly marked `[SYNTHETIC]`.
- **Reference Synthetic English Calls:** Golden transcripts in `data/transcripts/` generated under defined business SOPs.
- **External Dataset (Kaggle Telugu Call Center Audio):** If ingested from Kaggle (`infobayai/audio-call-center-telugu`), it must remain local under `data/telugu/` (gitignored), used strictly under its documented dataset license, and never committed to version control.

---

## 5. Reviewer and Production Notice
> [!CAUTION]
> **Prototype Status:** This system is an evaluation prototype designed for the Prodloop Capstone Assessment. It is **NOT** cleared for unredacted live customer calls in production. Deployment to a live contact center environment requires an enterprise compliance review, automated pre-ingestion PII scrubbing/masking (NER redaction of names, phone numbers, and addresses), and data retention governance conforming to applicable data protection regulations.

