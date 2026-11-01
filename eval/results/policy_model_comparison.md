# End-to-End Policy Evaluation Report (Turn-Level Matching)

**Date:** 2026-11-01 19:21:42  
**Model:** `gemini:gemini-3.5-flash-lite`  
**Execution Mode:** ONLY `check_policies` (temperature 0.0, no audit cache, no other pipeline steps)  
**Scoring Paradigm:** Turn-Level Matching on `(call, turn)` with acceptable alternates (`REF-3.1` $\iff$ `BIL-2.2`)

> [!IMPORTANT]
> **Evaluation Notes:**
> 1. **Held-Out Label Corrections Applied:** Held-out expected violations were updated to resolve synonymy/granularity discrepancies (e.g. `BIL-2.1`/`BIL-2.3` in `call_204`, removing repeated `ESC-2.1` in `call_205`, `PRV-2.1` in `call_207`, `BIL-3.1`/`ESC-1.1` in `call_208`, `ESC-1.1` in `call_209`).
> 2. **Turn-Level Scoring:** Both clause ID (or acceptable alternate) AND transcript turn must match to qualify as an expected hit.

## 3. Executive Summary Tables (Overall Averages)

### Dev Set (5 Calls)

| Variant | Expected Violations Found | Full Call Coverage | Extra Findings (False Positives) | Avg Clauses Sent | Avg Input Tokens | Avg Latency |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|
| **Variant G** | 3/3 (100.0%) | 3/3 (100.0%) | 0 | 21.6 | 5,545 | 12.45s |

### Held-Out Set (0 Calls)

| Variant | Expected Violations Found | Full Call Coverage | Extra Findings (False Positives) | Avg Clauses Sent | Avg Input Tokens | Avg Latency |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|
| **Variant G** | 0/0 (0.0%) | N/A | 0 | 0.0 | 0 | 0.00s |

### Combined Sets (5 Calls Total)

| Variant | Expected Violations Found | Full Call Coverage | Extra Findings (False Positives) | Avg Clauses Sent | Avg Input Tokens | Avg Latency |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|
| **Variant G** | 3/3 (100.0%) | 3/3 (100.0%) | 0 | 21.6 | 5,545 | 12.45s |

## 4. Extra Findings (False-Positive Risk)

*No extra findings detected across all runs.*
