# End-to-End Policy Evaluation Report (Turn-Level Matching)

**Date:** 2026-11-01 19:34:00  
**Model:** `gemini:gemini-2.5-flash`  
**Execution Mode:** ONLY `check_policies` (temperature 0.0, no audit cache, no other pipeline steps)  
**Scoring Paradigm:** Turn-Level Matching on `(call, turn)` with acceptable alternates (`REF-3.1` $\iff$ `BIL-2.2`)

> [!IMPORTANT]
> **Evaluation Notes:**
> 1. **Held-Out Label Corrections Applied:** Held-out expected violations were updated to resolve synonymy/granularity discrepancies (e.g. `BIL-2.1`/`BIL-2.3` in `call_204`, removing repeated `ESC-2.1` in `call_205`, `PRV-2.1` in `call_207`, `BIL-3.1`/`ESC-1.1` in `call_208`, `ESC-1.1` in `call_209`).
> 2. **Turn-Level Scoring:** Both clause ID (or acceptable alternate) AND transcript turn must match to qualify as an expected hit.

## 3. Executive Summary Tables (Overall Averages)

### Dev Set (12 Calls)

| Variant | Expected Violations Found | Full Call Coverage | Extra Findings (False Positives) | Avg Clauses Sent | Avg Input Tokens | Avg Latency |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|
| **Variant G** | 14/14 (100.0%) | 7/7 (100.0%) | 3 | 21.8 | 5,401 | 6.74s |

### Held-Out Set (0 Calls)

| Variant | Expected Violations Found | Full Call Coverage | Extra Findings (False Positives) | Avg Clauses Sent | Avg Input Tokens | Avg Latency |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|
| **Variant G** | 0/0 (0.0%) | N/A | 0 | 0.0 | 0 | 0.00s |

### Combined Sets (12 Calls Total)

| Variant | Expected Violations Found | Full Call Coverage | Extra Findings (False Positives) | Avg Clauses Sent | Avg Input Tokens | Avg Latency |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|
| **Variant G** | 14/14 (100.0%) | 7/7 (100.0%) | 3 | 21.8 | 5,401 | 6.74s |

## 4. Extra Findings (False-Positive Risk)

Total extra findings recorded across all runs: **3**

| Run | Split | Call ID | Variant | Clause ID | Severity | Turn | Agent Quote | Model Explanation |
|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---|:---|
| Run 1 | dev | `call_102` | **G** | `PRV-1.2` | `critical` | 1 | "Hello, ShopEase customer service. How can I help you?" | PRV-1.2 mandates an explicit call recording disclosure at the start of the interaction. The agent failed to deliver this |
| Run 1 | dev | `call_105` | **G** | `ESC-2.1` | `major` | 15 | "Thank you for holding, Ms. Krishnan, and I apologise for the wait. Our superviso" | ESC-2.1 states that if no supervisor is available within 2 minutes, the agent must retrieve the call from hold, apologiz |
| Run 1 | dev | `call_106` | **G** | `ESC-2.1` | `critical` | 14 | "Hello sir, yes, nobody is available. Anything else?" | ESC-2.1 states an agent may not keep a customer on hold for more than 2 minutes (120 seconds) without an active check-in |
