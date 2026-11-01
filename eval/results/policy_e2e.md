# End-to-End Policy Evaluation Report (Turn-Level Matching)

**Date:** 2026-11-01 18:36:25  
**Model:** `gemini:gemini-3.5-flash-lite`  
**Execution Mode:** ONLY `check_policies` (temperature 0.0, no audit cache, no other pipeline steps)  
**Scoring Paradigm:** Turn-Level Matching on `(call, turn)` with acceptable alternates (`REF-3.1` $\iff$ `BIL-2.2`)

> [!IMPORTANT]
> **Evaluation Notes:**
> 1. **Held-Out Label Corrections Applied:** Held-out expected violations were updated to resolve synonymy/granularity discrepancies (e.g. `BIL-2.1`/`BIL-2.3` in `call_204`, removing repeated `ESC-2.1` in `call_205`, `PRV-2.1` in `call_207`, `BIL-3.1`/`ESC-1.1` in `call_208`, `ESC-1.1` in `call_209`).
> 2. **Turn-Level Scoring:** Both clause ID (or acceptable alternate) AND transcript turn must match to qualify as an expected hit.

## 1. Multi-Run Repeatability & Performance Summary

| Run | Variant | Dev Recall | Held-Out Recall | Combined Recall | Full Call Coverage | Extras (Dev / Held / Total) | Avg Latency |
|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| Run 1 | **A** | 8/14 (57.1%) | 12/19 (63.2%) | **20/33 (60.6%)** | 5/16 (31.2%) | 4 / 3 / 7 | 2.72s |
| Run 1 | **G** | 9/14 (64.3%) | 12/19 (63.2%) | **21/33 (63.6%)** | 5/16 (31.2%) | 8 / 2 / 10 | 3.52s |
| Run 2 | **A** | 9/14 (64.3%) | 10/19 (52.6%) | **19/33 (57.6%)** | 5/16 (31.2%) | 4 / 6 / 10 | 3.86s |
| Run 2 | **G** | 9/14 (64.3%) | 13/19 (68.4%) | **22/33 (66.7%)** | 6/16 (37.5%) | 6 / 3 / 9 | 4.23s |
| Run 3 | **A** | 10/14 (71.4%) | 11/19 (57.9%) | **21/33 (63.6%)** | 6/16 (37.5%) | 4 / 4 / 8 | 4.34s |
| Run 3 | **G** | 9/14 (64.3%) | 12/19 (63.2%) | **21/33 (63.6%)** | 5/16 (31.2%) | 8 / 2 / 10 | 4.70s |

## 2. Persistent Misses Analysis (Repeating across All Runs)

An expected violation is **persistent** if the model failed to detect it on that exact turn in **all 3 independent runs**.

### Variant A Persistent Misses

**Persistent Misses (9 total — missed in ALL 3 runs):**

| Split | Call ID | Expected Clause & Turn | Status |
|:---:|:---:|:---|:---:|
| dev | `call_025` | `WAR-2.1 (turn 5)` | Repeated in 3/3 runs |
| dev | `call_041` | `WAR-3.2 (turn 11)` | Repeated in 3/3 runs |
| dev | `call_104` | `PRV-1.1 (turn 5)` | Repeated in 3/3 runs |
| dev | `call_107` | `WAR-1.2 (turn 7)` | Repeated in 3/3 runs |
| heldout | `call_202` | `PRV-1.1 (turn 3)` | Repeated in 3/3 runs |
| heldout | `call_205` | `ESC-3.1 (turn 15)` | Repeated in 3/3 runs |
| heldout | `call_207` | `PRV-2.1 (turn 11)` | Repeated in 3/3 runs |
| heldout | `call_207` | `WAR-2.1 (turn 7)` | Repeated in 3/3 runs |
| heldout | `call_209` | `WAR-2.1 (turn 11)` | Repeated in 3/3 runs |

**Sporadic Misses (9 total — missed in 1 or 2 runs):**

| Split | Call ID | Expected Clause & Turn | Frequency |
|:---:|:---:|:---|:---:|
| dev | `call_102` | `PRV-1.1 (turn 3)` | Missed in 1/3 runs |
| dev | `call_102` | `REF-2.1 (turn 9)` | Missed in 1/3 runs |
| dev | `call_104` | `BIL-2.1 (turn 7)` | Missed in 1/3 runs |
| heldout | `call_204` | `BIL-2.1 (turn 7)` | Missed in 2/3 runs |
| heldout | `call_206` | `PRV-1.1 (turn 3)` | Missed in 2/3 runs |
| heldout | `call_208` | `BIL-3.1 (turn 7)` | Missed in 1/3 runs |
| heldout | `call_208` | `ESC-1.1 (turn 11)` | Missed in 2/3 runs |
| heldout | `call_209` | `ESC-1.1 (turn 7)` | Missed in 1/3 runs |
| heldout | `call_209` | `REF-3.1 (turn 15)` | Missed in 1/3 runs |

### Variant G Persistent Misses

**Persistent Misses (10 total — missed in ALL 3 runs):**

| Split | Call ID | Expected Clause & Turn | Status |
|:---:|:---:|:---|:---:|
| dev | `call_025` | `WAR-2.1 (turn 5)` | Repeated in 3/3 runs |
| dev | `call_041` | `WAR-3.2 (turn 11)` | Repeated in 3/3 runs |
| dev | `call_104` | `PRV-1.1 (turn 5)` | Repeated in 3/3 runs |
| dev | `call_107` | `WAR-1.2 (turn 7)` | Repeated in 3/3 runs |
| heldout | `call_202` | `PRV-1.1 (turn 3)` | Repeated in 3/3 runs |
| heldout | `call_204` | `BIL-2.1 (turn 7)` | Repeated in 3/3 runs |
| heldout | `call_205` | `ESC-3.1 (turn 15)` | Repeated in 3/3 runs |
| heldout | `call_207` | `WAR-2.1 (turn 7)` | Repeated in 3/3 runs |
| heldout | `call_208` | `ESC-1.1 (turn 11)` | Repeated in 3/3 runs |
| heldout | `call_209` | `WAR-2.1 (turn 11)` | Repeated in 3/3 runs |

**Sporadic Misses (3 total — missed in 1 or 2 runs):**

| Split | Call ID | Expected Clause & Turn | Frequency |
|:---:|:---:|:---|:---:|
| dev | `call_104` | `BIL-2.1 (turn 7)` | Missed in 1/3 runs |
| dev | `call_106` | `ESC-1.1 (turn 7)` | Missed in 2/3 runs |
| heldout | `call_209` | `ESC-1.1 (turn 7)` | Missed in 2/3 runs |

## 3. Executive Summary Tables (Overall Averages)

### Dev Set (39 Calls)

| Variant | Expected Violations Found | Full Call Coverage | Extra Findings (False Positives) | Avg Clauses Sent | Avg Input Tokens | Avg Latency |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|
| **Variant A** | 27/42 (64.3%) | 8/21 (38.1%) | 12 | 13.8 | 4,311 | 3.77s |
| **Variant G** | 27/42 (64.3%) | 7/21 (33.3%) | 22 | 21.8 | 5,383 | 3.57s |

### Held-Out Set (36 Calls)

| Variant | Expected Violations Found | Full Call Coverage | Extra Findings (False Positives) | Avg Clauses Sent | Avg Input Tokens | Avg Latency |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|
| **Variant A** | 33/57 (57.9%) | 8/27 (29.6%) | 13 | 13.5 | 4,156 | 3.49s |
| **Variant G** | 37/57 (64.9%) | 9/27 (33.3%) | 7 | 21.1 | 5,182 | 4.78s |

### Combined Sets (75 Calls Total)

| Variant | Expected Violations Found | Full Call Coverage | Extra Findings (False Positives) | Avg Clauses Sent | Avg Input Tokens | Avg Latency |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|
| **Variant A** | 60/99 (60.6%) | 16/48 (33.3%) | 25 | 13.7 | 4,236 | 3.64s |
| **Variant G** | 64/99 (64.6%) | 16/48 (33.3%) | 29 | 21.4 | 5,287 | 4.15s |

## 4. Extra Findings (False-Positive Risk)

Total extra findings recorded across all runs: **54**

| Run | Split | Call ID | Variant | Clause ID | Severity | Turn | Agent Quote | Model Explanation |
|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---|:---|
| Run 1 | dev | `call_025` | **A** | `WAR-2.1` | `minor` | 7 | "the replacement unit will be dispatched within three to four weeks" | WAR-2.1 states that once damage evidence is validated, a replacement consignment is dispatched within 24 to 48 hours, no |
| Run 1 | dev | `call_025` | **G** | `WAR-2.1` | `minor` | 7 | "the replacement unit will be dispatched within three to four weeks." | WAR-2.1 states that a replacement consignment is generated and dispatched within 24 to 48 hours, not three to four weeks |
| Run 1 | dev | `call_041` | **A** | `WAR-3.2` | `minor` | 9 | "refurbished products have zero warranty coverage of any kind from ShopEase" | WAR-3.2 states that certified refurbished electronic devices carry a 6-month ShopEase warranty, whereas the agent incorr |
| Run 1 | dev | `call_041` | **G** | `WAR-3.2` | `major` | 9 | "refurbished products have zero warranty coverage of any kind from ShopEase." | WAR-3.2 states that certified refurbished electronic devices carry a 6-month ShopEase warranty, whereas the agent wrongl |
| Run 1 | dev | `call_102` | **A** | `REF-1.2` | `major` | 9 | "You can keep the watch, no need to send it back." | REF-1.2 requires items to be returned and subjected to a mandatory physical doorstep check by couriers to qualify for a  |
| Run 1 | dev | `call_102` | **G** | `PRV-1.2` | `critical` | 1 | "Hello, ShopEase customer service" | PRV-1.2 mandates reciting the call recording disclosure within the first two conversation turns, which the agent failed  |
| Run 1 | dev | `call_102` | **G** | `REF-1.2` | `major` | 9 | "You can keep the watch, no need to send it back" | REF-1.2 requires items to be returned and pass a mandatory physical doorstep check upon pickup to qualify for a full ref |
| Run 1 | dev | `call_104` | **A** | `PRV-1.1` | `critical` | 3 | "give me your wife's name and I will check" | PRV-1.1 requires two-factor verification (Order ID/Email plus last 4 digits of mobile number) before disclosing any acco |
| Run 1 | dev | `call_104` | **G** | `PRV-1.2` | `critical` | 1 | "Hello, ShopEase support, tell me." | PRV-1.2 requires agents to recite the approved recording disclosure in the initial call greeting within the first two tu |
| Run 1 | dev | `call_104` | **G** | `PRV-1.1` | `critical` | 3 | "give me your wife's name and I will check" | PRV-1.1 requires two-factor verification (Order ID/email and last 4 digits of mobile) before disclosing any account deta |
| Run 1 | dev | `call_104` | **G** | `PRV-2.2` | `major` | 5 | "The order is for a Prestige induction cooktop, Rs 4,750, paid with a debit card " | PRV-2.2 states representatives must use partial masking for shipping details and never recite the complete street addres |
| Run 1 | dev | `call_106` | **G** | `ESC-1.1` | `critical` | 5 | "Sir, managers do not handle delivery issues, I can check it for you." | ESC-1.1 requires an immediate supervisor escalation when the customer requests a manager twice, which the agent refused. |
| Run 1 | heldout | `call_202` | **A** | `ESC-1.2` | `critical` | 11 | "amount of Rs 14,999 will only be credited as ShopEase wallet credits" | ESC-1.2 and REF-3.1 state that any refund exceeding Rs 5,000 strictly requires supervisor review and authorization. The  |
| Run 1 | heldout | `call_202` | **A** | `ESC-1.1` | `critical` | 15 | "another representative would tell you the exact same thing" | ESC-1.1 requires immediate warm escalation when a customer makes an explicit request to speak to a senior lead/someone e |
| Run 1 | heldout | `call_203` | **A** | `ESC-1.1` | `critical` | 15 | "You are free to do so, ma'am." | ESC-1.1 requires frontline agents to initiate an immediate supervisor escalation when the customer mentions consumer cou |
| Run 1 | heldout | `call_203` | **G** | `ESC-1.1` | `critical` | 15 | "You are free to do so, ma'am. Thank you for contacting ShopEase." | ESC-1.1 mandates that when a customer mentions consumer court or legal representation, the agent must initiate an immedi |
| Run 1 | heldout | `call_212` | **G** | `WAR-2.3` | `minor` | 21 | "resolve the repair within a maximum turnaround window of 14 calendar days" | WAR-2.3 applies a 14 business day turnaround time for ShopEase Assured warranty facilitation, not 14 calendar days for s |
| Run 2 | dev | `call_025` | **A** | `WAR-2.1` | `minor` | 7 | "the replacement unit will be dispatched within three to four weeks" | WAR-2.1 states that once evidence is validated, a replacement consignment is dispatched within 24 to 48 hours, not 3 to  |
| Run 2 | dev | `call_025` | **G** | `WAR-2.1` | `minor` | 7 | "replacement unit will be dispatched within three to four weeks" | WAR-2.1 states that a replacement consignment is generated and dispatched within 24 to 48 hours, not three to four weeks |
| Run 2 | dev | `call_041` | **A** | `WAR-3.2` | `minor` | 9 | "refurbished products have zero warranty coverage of any kind from ShopEase." | WAR-3.2 states that certified refurbished and open-box electronic devices carry a 6-month ShopEase warranty. The agent w |
| Run 2 | dev | `call_041` | **G** | `WAR-3.2` | `minor` | 9 | "refurbished products have zero warranty coverage of any kind from ShopEase" | WAR-3.2 clause 1 specifies that certified refurbished and open-box electronic devices carry a 6-month ShopEase warranty. |
| Run 2 | dev | `call_102` | **A** | `REF-1.2` | `major` | 9 | "You can keep the watch, no need to send it back." | REF-1.2 requires items to be physically returned, inspected, and verified via a mandatory doorstep check by couriers to  |
| Run 2 | dev | `call_102` | **G** | `PRV-1.2` | `critical` | 1 | "Hello, ShopEase customer service. How can I help you?" | PRV-1.2 mandates that representatives recite the recording disclosure statement within the first two conversation turns. |
| Run 2 | dev | `call_102` | **G** | `REF-1.2` | `major` | 9 | "You can keep the watch, no need to send it back." | REF-1.2 requires items to be returned and pass a mandatory physical doorstep check to qualify for a full refund. |
| Run 2 | dev | `call_104` | **A** | `PRV-1.1` | `critical` | 3 | "give me your wife's name and I will check" | PRV-1.1 requires two-factor verification (order ID/email and last 4 digits of mobile) before disclosing account details  |
| Run 2 | dev | `call_104` | **G** | `PRV-1.2` | `critical` | 1 | "Hello, ShopEase support, tell me." | PRV-1.2 requires representatives to recite the approved recording disclosure statement within the initial call greeting. |
| Run 2 | dev | `call_104` | **G** | `PRV-2.2` | `major` | 5 | "shipped to Flat 8B, Lotus Residency, Linking Road, Bandra, Mumbai 400050" | PRV-2.2 states representatives must use partial masking and never recite the complete street address or door number unle |
| Run 2 | heldout | `call_202` | **A** | `ESC-1.2` | `critical` | 11 | "the amount of Rs 14,999 will only be credited as ShopEase wallet credits" | ESC-1.2 states that any request involving refunds or concessions exceeding Rs 5,000 must be escalated to a supervisor. |
| Run 2 | heldout | `call_202` | **A** | `ESC-1.1` | `critical` | 15 | "another representative would tell you the exact same thing" | ESC-1.1 requires an immediate transfer to a supervisor when a customer makes an explicit request or has unresolved inqui |
| Run 2 | heldout | `call_203` | **G** | `WAR-1.2` | `major` | 7 | "Electronics can only be returned within 48 hours of transit damage" | REF-1.1 allows a 7-day return window for electronics, whereas WAR-1.2's 48-hour window applies specifically to DOA or tr |
| Run 2 | heldout | `call_205` | **A** | `ESC-2.1` | `major` | 7 | "we do not provide callbacks from managers" | ESC-2.1 requires offering a confirmed Supervisor Callback SLA within 2 to 4 business hours if no supervisor is immediate |
| Run 2 | heldout | `call_205` | **G** | `ESC-2.1` | `major` | 7 | "we do not provide callbacks from managers." | ESC-2.1 explicitly provides for supervisor callbacks within 2 to 4 business hours when a supervisor is not immediately a |
| Run 2 | heldout | `call_206` | **G** | `SHP-2.2` | `major` | 13 | "I have updated the courier dispatch remarks to hold the parcel for Monday delive" | SHP-2.2 states that once an order reaches Shipped or Out for Delivery status, no frontline agent has system permission t |
| Run 2 | heldout | `call_207` | **A** | `PRV-1.1` | `critical` | 11 | "you can pay an expedited handling fee of Rs 350 right now; please read out your " | PRV-1.1 prohibits revealing or collecting sensitive financial details over unverified channels, and collecting CVV over  |
| Run 2 | heldout | `call_209` | **A** | `ESC-1.2` | `critical` | 15 | "approving an immediate goodwill refund of Rs 8,500 directly into your bank accou" | ESC-1.2 limits frontline agent refund authority to a maximum of Rs 5,000. An amount of Rs 8,500 requires supervisor esca |
| Run 2 | heldout | `call_209` | **A** | `REF-3.1` | `major` | 17 | "That is the maximum discretionary allowance I can release to resolve this issue " | REF-3.1 states the agent discretionary limit is Rs 5,000, not Rs 8,500. |
| Run 3 | dev | `call_025` | **A** | `WAR-2.1` | `minor` | 7 | "the replacement unit will be dispatched within three to four weeks." | WAR-2.1 states that a replacement consignment is generated and dispatched within 24 to 48 hours after validation, not th |
| Run 3 | dev | `call_025` | **G** | `WAR-2.1` | `minor` | 7 | "the replacement unit will be dispatched within three to four weeks." | WAR-2.1 states that a replacement consignment is generated and dispatched within 24 to 48 hours, not three to four weeks |
| Run 3 | dev | `call_041` | **A** | `WAR-3.2` | `minor` | 9 | "refurbished products have zero warranty coverage" | WAR-3.2 clause 1 states certified refurbished and open-box electronic devices carry a 6-month ShopEase warranty, not zer |
| Run 3 | dev | `call_041` | **G** | `WAR-3.2` | `minor` | 9 | "refurbished products have zero warranty coverage of any kind from ShopEase. They" | WAR-3.2 clause 1 specifies that certified refurbished electronic devices carry a 6-month ShopEase warranty, whereas the  |
| Run 3 | dev | `call_102` | **A** | `REF-1.2` | `major` | 9 | "You can keep the watch, no need to send it back." | REF-1.2 requires items to be returned in original condition with packaging and accessories, subject to a mandatory physi |
| Run 3 | dev | `call_102` | **G** | `PRV-1.2` | `critical` | 1 | "Hello, ShopEase customer service" | PRV-1.2 mandates that representatives recite the call recording disclosure during their initial greeting within the firs |
| Run 3 | dev | `call_102` | **G** | `REF-1.2` | `major` | 9 | "You can keep the watch, no need to send it back" | REF-1.2 requires items to be returned and verified through a mandatory physical doorstep check by couriers to qualify fo |
| Run 3 | dev | `call_104` | **A** | `PRV-1.1` | `critical` | 3 | "give me your wife's name and I will check" | PRV-1.1 requires two-factor verification (Order ID/Email plus last 4 digits of mobile number) before disclosing account  |
| Run 3 | dev | `call_104` | **G** | `PRV-1.2` | `critical` | 1 | "Hello, ShopEase support, tell me." | PRV-1.2 mandates reciting the call recording disclosure statement within the first two conversation turns. |
| Run 3 | dev | `call_104` | **G** | `PRV-1.1` | `critical` | 3 | "give me your wife's name and I will check" | PRV-1.1 requires two-factor verification (Order ID/Email + last 4 digits of mobile number) before disclosing any account |
| Run 3 | dev | `call_106` | **G** | `ESC-1.1` | `critical` | 5 | "managers do not handle delivery issues, I can check it for you" | ESC-1.1 mandates supervisor escalation when the customer requests a supervisor two times. The customer asked in turn 4 a |
| Run 3 | dev | `call_106` | **G** | `ESC-2.1` | `major` | 14 | "Hello sir, yes, nobody is available." | ESC-2.1 states that if no supervisor is immediately available within 2 minutes, the agent must offer a confirmed Supervi |
| Run 3 | heldout | `call_202` | **A** | `ESC-1.2` | `critical` | 11 | "the amount of Rs 14,999 will only be credited as ShopEase wallet credits" | ESC-1.2 mandates supervisor review and secondary authorization for any refund request exceeding Rs 5,000. |
| Run 3 | heldout | `call_202` | **A** | `ESC-1.1` | `critical` | 15 | "another representative would tell you the exact same thing" | ESC-1.1 requires an immediate supervisor escalation when a customer makes an explicit request two times. |
| Run 3 | heldout | `call_205` | **A** | `ESC-2.1` | `critical` | 7 | "we do not provide callbacks from managers" | ESC-2.1 requires offering a confirmed Supervisor Callback SLA within 2 to 4 business hours if no supervisor is immediate |
| Run 3 | heldout | `call_205` | **G** | `ESC-2.1` | `major` | 7 | "we do not provide callbacks from managers." | ESC-2.1 explicitly states that if no supervisor is immediately available, the agent must offer a confirmed Supervisor Ca |
| Run 3 | heldout | `call_206` | **A** | `SHP-2.2` | `major` | 13 | "I have updated the courier dispatch remarks to hold the parcel for Monday delive" | SHP-2.2 states that once an order reaches Shipped or Out for Delivery status, no frontline agent has system permission t |
| Run 3 | heldout | `call_206` | **G** | `SHP-2.2` | `major` | 13 | "I have updated the courier dispatch remarks to hold the parcel for Monday delive" | SHP-2.2 states that once an order reaches Shipped or Out for Delivery status, no frontline agent has system permission t |
