# Agent Setup & Pair Programming Guidelines

This document outlines the coding-agent operational conventions, rules, and prompt specifications for the Conversational Quality Audit Agent.

## Core Rules & System Prompt
The primary instructions for AI development agents operating on this codebase are:
1. **`GEMINI.md`**: Directs the agent to read `PROJECT_BRIEF.md` prior to executing tasks and abide strictly by its rules.
2. **`PROJECT_BRIEF.md`**: Contains the enterprise executive summary, domain context (ShopEase India), technical stack, and non-negotiable operational rules (single LLM gateway, structured Pydantic outputs, evidence-backed findings, consistent business facts).

## Prompts & Agent Specifications
Dedicated agent prompt definitions are organized under:
- **`agents/`**: Core prompt instruction files:
  - `compliance_agent.md`: SOP procedural checks and empathy/communication scoring (capped <= 3000 chars).
  - `policy_agent.md`: Factual policy verification against RAG excerpts (capped <= 3000 chars).
  - `speaker_id_agent.md`: Mono audio speaker labelling (capped <= 3000 chars).
  - `coach_agent.md`: Managerial summary and agent coaching guidance.
- **`prompts/`**: Versioned prompt templates and Telugu colloquial guidelines (`telugu_guidelines_v1.md`).

## Verification & Guardrail Tests
All agents modifying this codebase must ensure:
- `python -m pytest tests/test_agent_prompts.py -q`: Verifies that prompt files remain strictly under the 3,000-character cap and request count baseline is unchanged (2 requests for stereo, 3 requests for mono).
- `python -m pytest tests/test_telugu_foundation.py -q`: Verifies quality gating, observed/inferred findings, and Prodloop scenarios.

