# End-to-End Policy Evaluation Report (Turn-Level Matching)

**Date:** 2026-11-03 01:02:06  
**Model:** `gemini:gemini-2.5-flash`  
**Execution Mode:** ONLY `check_policies` (temperature 0.0, no audit cache, no other pipeline steps)  
**Scoring Paradigm:** Turn-Level Matching on `(call, turn)` with acceptable alternates (`REF-3.1` $\iff$ `BIL-2.2`)

> [!IMPORTANT]
> **Evaluation Notes:**
> 1. **Held-Out Label Corrections Applied:** Held-out expected violations were updated to resolve synonymy/granularity discrepancies (e.g. `BIL-2.1`/`BIL-2.3` in `call_204`, removing repeated `ESC-2.1` in `call_205`, `PRV-2.1` in `call_207`, `BIL-3.1`/`ESC-1.1` in `call_208`, `ESC-1.1` in `call_209`).
> 2. **Turn-Level Scoring:** Both clause ID (or acceptable alternate) AND transcript turn must match to qualify as an expected hit.

## 3. Executive Summary Tables (Overall Averages)

### Dev Set (13 Calls)

| Variant | Expected Violations Found | Full Call Coverage | Extra Findings (False Positives) | Avg Clauses Sent | Avg Input Tokens | Avg Latency | Avg Cost / Call |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **Variant G** | 14/14 (100.0%) | 7/7 (100.0%) | 3 | 21.8 | 5,383 | 6.58s | $0.003506 |

### Held-Out Set (12 Calls)

| Variant | Expected Violations Found | Full Call Coverage | Extra Findings (False Positives) | Avg Clauses Sent | Avg Input Tokens | Avg Latency | Avg Cost / Call |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **Variant G** | 14/19 (73.7%) | 4/9 (44.4%) | 6 | 21.1 | 5,182 | 17.26s | $0.003272 |

### Combined Sets (25 Calls Total)

| Variant | Expected Violations Found | Full Call Coverage | Extra Findings (False Positives) | Avg Clauses Sent | Avg Input Tokens | Avg Latency | Avg Cost / Call |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **Variant G** | 28/33 (84.9%) | 11/16 (68.8%) | 9 | 21.4 | 5,287 | 11.71s | $0.003394 |

## 4. Extra Findings (False-Positive Risk)

Total extra findings recorded across all runs: **9**

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
