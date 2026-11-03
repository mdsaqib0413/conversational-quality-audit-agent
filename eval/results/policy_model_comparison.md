# End-to-End Policy Evaluation Report (Turn-Level Matching)

**Date:** 2026-11-03 14:52:18  
**Model:** `gemini:gemini-3.5-flash`  
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
| **Variant G** | 14/14 (100.0%) | 7/7 (100.0%) | 5 | 21.8 | 5,383 | 10.70s | $0.014446 |

### Held-Out Set (12 Calls)

| Variant | Expected Violations Found | Full Call Coverage | Extra Findings (False Positives) | Avg Clauses Sent | Avg Input Tokens | Avg Latency | Avg Cost / Call |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **Variant G** | 16/19 (84.2%) | 6/9 (66.7%) | 9 | 21.1 | 5,182 | 8.62s | $0.013987 |

### Combined Sets (25 Calls Total)

| Variant | Expected Violations Found | Full Call Coverage | Extra Findings (False Positives) | Avg Clauses Sent | Avg Input Tokens | Avg Latency | Avg Cost / Call |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **Variant G** | 30/33 (90.9%) | 13/16 (81.2%) | 14 | 21.4 | 5,287 | 9.70s | $0.014226 |

## 4. Extra Findings (False-Positive Risk)

Total extra findings recorded across all runs: **14**

| Run | Split | Call ID | Variant | Clause ID | Severity | Turn | Agent Quote | Model Explanation |
|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---|:---|
| Run 1 | dev | `call_102` | **G** | `PRV-1.2` | `critical` | 1 | "Hello, ShopEase customer service. How can I help you?" | PRV-1.2 requires an explicit call recording disclosure during the initial call greeting. The agent did not provide this  |
| Run 1 | dev | `call_102` | **G** | `REF-1.2` | `major` | 9 | "You can keep the watch, no need to send it back." | REF-1.2 requires items to be returned in original condition via doorstep pickup to qualify for a refund. Policy does not |
| Run 1 | dev | `call_104` | **G** | `PRV-1.2` | `critical` | 1 | "Hello, ShopEase support, tell me." | PRV-1.2 mandates that representatives recite the approved call recording disclosure during their initial call greeting w |
| Run 1 | dev | `call_104` | **G** | `PRV-2.2` | `major` | 5 | "and it is shipped to Flat 8B, Lotus Residency, Linking Road, Bandra, Mumbai 4000" | PRV-2.2 states representatives must never recite the complete street address or door number out loud unless the customer |
| Run 1 | dev | `call_106` | **G** | `ESC-2.1` | `critical` | 14 | "Hello sir, yes, nobody is available. Anything else?" | ESC-2.1 limits hold duration to 2 minutes (120s) without active check-in (agent held for 135s) and requires offering a c |
| Run 1 | heldout | `call_202` | **G** | `PRV-2.2` | `major` | 3 | "delivered to flat 402, Palm Heights in Pune yesterday" | PRV-2.2 states representatives must partially mask delivery addresses and never recite the full door number/street addre |
| Run 1 | heldout | `call_202` | **G** | `ESC-1.2` | `critical` | 11 | "the amount of Rs 14,999 will only be credited as ShopEase wallet credits" | ESC-1.2 and REF-3.1 state frontline agents have approval/processing authority up to Rs 5,000 only; any request exceeding |
| Run 1 | heldout | `call_202` | **G** | `ESC-1.1` | `critical` | 15 | "Our payment backend restricts promotional orders to wallet refunds only, so anot" | ESC-1.1 mandates escalation upon customer explicit request or unresolved inquiries after frontline attempts. Dismissing  |
| Run 1 | heldout | `call_203` | **G** | `ESC-1.1` | `critical` | 15 | "You are free to do so, ma'am. Thank you for contacting ShopEase." | ESC-1.1 explicitly mandates an immediate supervisor escalation whenever a customer mentions legal or regulatory bodies,  |
| Run 1 | heldout | `call_205` | **G** | `ESC-2.1` | `minor` | 7 | "we do not provide callbacks from managers." | ESC-2.1 mandates offering a confirmed Supervisor Callback SLA within 2 to 4 business hours if a supervisor is not immedi |
| Run 1 | heldout | `call_206` | **G** | `PRV-2.2` | `major` | 3 | "heading to your residency at Green Glen Layout." | PRV-2.2 requires delivery address masking (quoting only first name, city, and pin code) and prohibits reciting street or |
| Run 1 | heldout | `call_207` | **G** | `WAR-2.3` | `minor` | 7 | "standard repair turnaround time is forty-five days, and we cannot offer any repl" | WAR-2.3 specifies that the maximum turnaround time for ShopEase Assured warranty facilitation is 14 business days, after |
| Run 1 | heldout | `call_209` | **G** | `WAR-2.3` | `minor` | 11 | "During festival months, panel replacement turnaround times are indefinite; it co" | WAR-2.3 caps warranty repair/replacement turnaround time at 14 business days, whereas the agent claimed turnaround times |
| Run 1 | heldout | `call_212` | **G** | `WAR-2.3` | `minor` | 21 | "authorized service centers must resolve the repair within a maximum turnaround w" | Agent stated the maximum TAT is 14 calendar days, whereas WAR-2.3 clause 1 specifies maximum turnaround time is 14 busin |
