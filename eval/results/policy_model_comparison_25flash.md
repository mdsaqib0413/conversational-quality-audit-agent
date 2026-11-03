# End-to-End Policy Evaluation Report (Turn-Level Matching)

**Date:** 2026-11-03 14:59:08  
**Model:** `gemini:gemini-2.5-flash`  
**Execution Mode:** ONLY `check_policies` (temperature 0.0, no audit cache, no other pipeline steps)  
**Scoring Paradigm:** Turn-Level Matching on `(call, turn)` with acceptable alternates (`REF-3.1` $\iff$ `BIL-2.2`)

> [!IMPORTANT]
> **Evaluation Notes:**
> 1. **Held-Out Label Corrections Applied:** Held-out expected violations were updated to resolve synonymy/granularity discrepancies (e.g. `BIL-2.1`/`BIL-2.3` in `call_204`, removing repeated `ESC-2.1` in `call_205`, `PRV-2.1` in `call_207`, `BIL-3.1`/`ESC-1.1` in `call_208`, `ESC-1.1` in `call_209`).
> 2. **Turn-Level Scoring:** Both clause ID (or acceptable alternate) AND transcript turn must match to qualify as an expected hit.

## 1. Multi-Run Repeatability & Performance Summary

| Run | Variant | Dev Recall | Held-Out Recall | Combined Recall | Full Call Coverage | Extras (Dev / Held / Total) | Avg Latency |
|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| Run 1 | **G** | 14/14 (100.0%) | 14/19 (73.7%) | **28/33 (84.9%)** | 11/16 (68.8%) | 3 / 6 / 9 | 11.71s |
| Run 2 | **G** | 14/14 (100.0%) | 8/10 (80.0%) | **22/24 (91.7%)** | 10/12 (83.3%) | 2 / 4 / 6 | 17.51s |

## 2. Persistent Misses Analysis (Repeating across All Runs)

An expected violation is **persistent** if the model failed to detect it on that exact turn in **all 3 independent runs**.

### Variant G Persistent Misses

**Persistent Misses (2 total — missed in ALL 2 runs):**

| Split | Call ID | Expected Clause & Turn | Status |
|:---:|:---:|:---|:---:|
| heldout | `call_202` | `PRV-1.1 (turn 3)` | Repeated in 2/2 runs |
| heldout | `call_205` | `ESC-3.1 (turn 15)` | Repeated in 2/2 runs |

**Sporadic Misses (3 total — missed in 1 or 2 runs):**

| Split | Call ID | Expected Clause & Turn | Frequency |
|:---:|:---:|:---|:---:|
| heldout | `call_206` | `PRV-1.1 (turn 3)` | Missed in 1/2 runs |
| heldout | `call_207` | `WAR-2.1 (turn 7)` | Missed in 1/2 runs |
| heldout | `call_209` | `WAR-2.1 (turn 11)` | Missed in 1/2 runs |

## 3. Executive Summary Tables (Overall Averages)

### Dev Set (26 Calls)

| Variant | Expected Violations Found | Full Call Coverage | Extra Findings (False Positives) | Avg Clauses Sent | Avg Input Tokens | Avg Latency | Avg Cost / Call |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **Variant G** | 28/28 (100.0%) | 14/14 (100.0%) | 5 | 21.8 | 5,383 | 11.25s | $0.003439 |

### Held-Out Set (17 Calls)

| Variant | Expected Violations Found | Full Call Coverage | Extra Findings (False Positives) | Avg Clauses Sent | Avg Input Tokens | Avg Latency | Avg Cost / Call |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **Variant G** | 22/29 (75.9%) | 7/14 (50.0%) | 10 | 20.9 | 5,120 | 18.55s | $0.003297 |

### Combined Sets (43 Calls Total)

| Variant | Expected Violations Found | Full Call Coverage | Extra Findings (False Positives) | Avg Clauses Sent | Avg Input Tokens | Avg Latency | Avg Cost / Call |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **Variant G** | 50/57 (87.7%) | 21/28 (75.0%) | 15 | 21.4 | 5,279 | 14.13s | $0.003383 |

## 4. Extra Findings (False-Positive Risk)

Total extra findings recorded across all runs: **15**

| Run | Split | Call ID | Variant | Clause ID | Severity | Turn | Agent Quote | Model Explanation |
|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---|:---|
| Run 1 | dev | `call_102` | **G** | `PRV-1.2` | `critical` | 1 | "Hello, ShopEase customer service. How can I help you?" | PRV-1.2 mandates an explicit call recording disclosure at the start of the interaction. The agent failed to deliver this |
| Run 1 | dev | `call_105` | **G** | `ESC-2.1` | `major` | 15 | "Thank you for holding, Ms. Krishnan, and I apologise for the wait. Our superviso" | ESC-2.1 states that if no supervisor is available within 2 minutes, the agent must retrieve the call from hold, apologiz |
| Run 1 | dev | `call_106` | **G** | `ESC-2.1` | `critical` | 14 | "Hello sir, yes, nobody is available. Anything else?" | ESC-2.1 states an agent may not keep a customer on hold for more than 2 minutes (120 seconds) without an active check-in |
| Run 1 | heldout | `call_202` | **G** | `PRV-2.2` | `major` | 3 | "I see your order for the tablet was delivered to flat 402, Palm Heights in Pune " | PRV-2.2 states that agents must use partial masking and never recite the complete street address or door number out loud |
| Run 1 | heldout | `call_202` | **G** | `REF-3.1` | `critical` | 11 | "the amount of Rs 14,999 will only be credited as ShopEase wallet credits" | REF-3.1 states that frontline agents have discretionary authority to approve refunds up to a maximum limit of Rs 5,000.  |
| Run 1 | heldout | `call_202` | **G** | `ESC-1.1` | `critical` | 15 | "Our payment backend restricts promotional orders to wallet refunds only, so anot" | ESC-1.1 mandates escalation when a customer explicitly asks to speak to a supervisor. The agent refused this mandatory e |
| Run 1 | heldout | `call_203` | **G** | `WAR-1.2` | `major` | 9 | "Our portal only handles damage claims reported within two days of arrival. Beyon" | WAR-1.2 states that transit damage or defective condition must be reported within 48 hours for a free replacement. Howev |
| Run 1 | heldout | `call_207` | **G** | `WAR-2.3` | `minor` | 7 | "standard repair turnaround time is forty-five days" | WAR-2.3 states that for 'ShopEase Assured' items, the maximum turnaround time for repair or replacement is 14 business d |
| Run 1 | heldout | `call_212` | **G** | `WAR-2.3` | `minor` | 21 | "authorized service centers must resolve the repair within a maximum turnaround w" | WAR-2.3 specifies a maximum turnaround time of '14 business days' for repair or replacement, not '14 calendar days'. The |
| Run 2 | dev | `call_105` | **G** | `ESC-2.1` | `major` | 15 | "Thank you for holding, Ms. Krishnan, and I apologise for the wait. Our superviso" | ESC-2.1 states that if no supervisor is available within 2 minutes, the agent must retrieve the call from hold, apologiz |
| Run 2 | dev | `call_106` | **G** | `ESC-2.1` | `critical` | 14 | "Hello sir, yes, nobody is available. Anything else?" | ESC-2.1 states an agent may not keep a customer on hold for more than 2 minutes (120 seconds) without an active check-in |
| Run 2 | heldout | `call_202` | **G** | `PRV-2.2` | `major` | 3 | "I see your order for the tablet was delivered to flat 402, Palm Heights in Pune " | PRV-2.2 states that agents must use partial masking and never recite the complete street address or door number out loud |
| Run 2 | heldout | `call_202` | **G** | `REF-3.1` | `critical` | 11 | "the amount of Rs 14,999 will only be credited as ShopEase wallet credits" | REF-3.1 states that frontline agents have discretionary authority to approve refunds up to a maximum limit of Rs 5,000.  |
| Run 2 | heldout | `call_202` | **G** | `ESC-1.1` | `critical` | 15 | "Our payment backend restricts promotional orders to wallet refunds only, so anot" | ESC-1.1 mandates escalation when a customer explicitly asks to speak to a supervisor. The agent refused this mandatory e |
| Run 2 | heldout | `call_203` | **G** | `WAR-1.2` | `major` | 9 | "Our portal only handles damage claims reported within two days of arrival. Beyon" | WAR-1.2 states that transit damage or defective condition must be reported within 48 hours for a free replacement. Howev |
