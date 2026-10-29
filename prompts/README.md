# Versioned Prompt Pack (Prodloop Capstone / Telugu-Ready)
# version: 1.0

This directory holds the versioned prompt templates and linguistic guidelines used across the Conversational Quality Audit Agent pipeline.

## Files
- `compliance_prompt_v1.md`: SOP verification, holistic resolution, and communication quality prompt template.
- `policy_prompt_v1.md`: Grounded RAG policy compliance prompt template.
- `speaker_id_prompt_v1.md`: Telephony mono-audio speaker separation template.
- `telugu_guidelines_v1.md`: Telugu domain phrases, verification scripts, hold markers, and ambiguous closures (*"sare, chuddam le"*).

All model prompts are routed strictly through the single gateway at `src/audit/llm.py`.

