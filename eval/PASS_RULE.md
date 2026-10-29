# System Evaluation Pass Rules (Pre-Declared Thresholds)

> [!IMPORTANT]
> **Pre-Commitment Notice:** All thresholds in this document were established and frozen prior to inspecting or evaluating heldout dataset calls, ensuring zero test contamination.

A prototype pipeline version is declared **PASSED** on the development benchmark (`dev`) if and only if every condition below is satisfied:

## 1. Compliance & Safety Thresholds

| Metric | Target | Rationale |
|---|---|---|
| **Mandatory Recall (`identity_verification`)** | $\ge 90.0\%$ | A missed security breach exposes customer PII and carries critical regulatory liability. |
| **Mandatory Recall (`hold_handling`)** | $\ge 85.0\%$ | Customer dead-air and hold abandonment directly impact caller churn and compliance. |
| **Observed / Inferred Separation Violations** | **0** (Strict Zero) | Speculative model interpretations must never contaminate factual, audit-grade findings. |
| **Evidence Verbatim Validity** | $\ge 85.0\%$ | Every penalty deduction must cite a verifiable, timestamped quote from the cited turn. |
| **Handoff Correctness (Unusable / Out-of-Scope)** | $\ge 90.0\%$ | Unusable or non-support inputs must halt before LLM execution without wasting API quota. |
| **False Rejection Rate (Good Calls Refused)** | $\le 5.0\%$ | Valid customer support interactions must never be wrongly abandoned as unusable. |

## 2. Operational & Latency Thresholds

| Metric | Target | Rationale |
|---|---|---|
| **SOP Exact Verdict Agreement (Graded)** | $\ge 80.0\%$ | Audit scoring consistency against human gold standard. |
| **SOP Within-1-Level Agreement (Graded)** | $\ge 95.0\%$ | Avoids severe grading variance across supervisor reviews. |
| **Max LLM Requests Per Short Call ($\le 50$ turns)** | $\le 2$ (Stereo), $\le 3$ (Mono) | Controls API consumption and prevents unbounded agentic loops. |
| **p95 Total Audit Pipeline Latency** | $\le 8.0$ seconds | Ensures conversational audit throughput in operational queue workers. |
| **Estimated Model Cost Per Call** | $\le \$0.005$ USD | Keeps production cost well below manual human audit overhead. |

## 3. Decision Matrix
- **PASS:** Meets all mandatory compliance thresholds and operational latency limits.
- **CONDITIONAL PASS:** Meets all safety thresholds, but graded agreement falls between 70% and 80% (acceptable for dev prototype tuning).
- **FAIL:** Any breach of the Zero-Separation rule, mandatory recall $< 90\%$, or false rejection of valid calls.

