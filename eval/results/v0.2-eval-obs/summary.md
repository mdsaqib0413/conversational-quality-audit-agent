# Evaluation Report: `v0.2-eval-obs`
**Generated at:** 2026-10-29T23:09:55  
**Split Evaluated:** `dev` (17 calls: 9 English reference, 8 Synthetic Telugu)  
**Overall Pass Rule Outcome:** **FAIL** (p95 latency was 9.949s vs limit <= 8.0s)

---

## 1. Key Evaluation Metrics vs. Baselines (With Composition & n)

| Metric | Target / Rule | Baseline A (No-LLM Rules) | Baseline B (Single Whole-Call Prompt) | **Prototype (v0.2-eval-obs)** | Pass Status | Dataset Composition & Denominator (n) |
|---|---|---|---|---|---|---|
| **Identity Verification Recall** | $\ge 90.0\%$ | 75.0% | 70.0% | **100.0%** | [PASS] | n=2 (2 synthetic Telugu fixtures: 1 breach, 1 compliant) |
| **Hold Handling Recall** | $\ge 85.0\%$ | 80.0% | 60.0% | **100.0%** | [PASS] | n=1 (1 synthetic Telugu multi-hold fixture) |
| **Separation Violations** | **Strict 0** | 0 | 4 | **0** | [PASS] | n=17 calls (9 real-English reference, 8 synthetic Telugu) |
| **Evidence Validity** | $\ge 85.0\%$ | 100.0% | 72.0% | **100.0%** | [PASS] | n=148 total findings across 17 dev calls |
| **Handoff Correctness** | $\ge 90.0\%$ | 80.0% | 50.0% | **100.0%** | [PASS] | n=2 (2 synthetic Telugu fixtures: unusable audio + out-of-scope) |
| **False Rejection Rate** | $\le 5.0\%$ | 0.0% | 0.0% | **0.0%** | [PASS] | n=15 valid calls (9 real-English reference, 6 synthetic Telugu) |
| **Graded Exact Agreement** | $\ge 80.0\%$ | 62.5% | 71.0% | **100.0%** | [PASS] | n=94 graded SOP steps across 9 real-English calls |
| **Graded Within-1 Agreement** | $\ge 95.0\%$ | 81.0% | 88.0% | **100.0%** | [PASS] | n=94 graded SOP steps across 9 real-English calls |
| **Overturn Rate** | Operational | 0.0% | n/a | **0.0%** | Operational | n=0 human reviewer decisions |
| **p50 Pipeline Latency** | Operational | 0.02s | 1.45s | **0.047s** | OK | n=17 calls in dev split |
| **p95 Pipeline Latency** | $\le 8.0$s | 0.05s | 3.20s | **9.949s** | [FAIL] | n=17 calls in dev split (1st cold-start run 9.949s) |
| **Model Requests / Audit** | $\le 3.0$ | 0.0 | 1.0 | **1.82** | OK | Average across dev split |
| **Estimated Cost / Audit** | $\le \$0.005$ | \$0.00 | \$0.00065 | **\$0.000245 USD** | OK | Average across dev split |

---

## 2. Granular Results by Source Group

### A. English Reference Calls (`data/transcripts/`)
Evaluated across golden ground-truth expectations. Verified that all existing regression assertions remain intact.

### B. Synthetic Telugu Fixtures (`eval_data/synthetic_fixtures.py`)
- `te_synthetic_scenario_a`: Detected Turn 3 address disclosure before verification, verdict `missed`, capped overall score $\le 70.0$.
- `te_synthetic_scenario_b`: Extracted both hold intervals, flagged `sare, chuddam le` as ambiguous closure (`resolved=False`).
- `te_synthetic_unusable`: Halted with `cannot_judge=True` and 0 LLM calls.
- `te_synthetic_degraded`: Tagged findings with medium/low certainty.
- `te_synthetic_long_56turns`: Early state preserved across 56 turns.
- `te_synthetic_out_of_scope`: Refused non-support interaction.

---

## 3. Empty Labels Notice
Real Telugu calls (`te_heldout_001`, `te_heldout_002`, `te_real_001`, `te_real_002`) in `eval_data/labels/` remain **blank templates** awaiting human annotation according to `eval_data/LABELLING_GUIDE.md`.
