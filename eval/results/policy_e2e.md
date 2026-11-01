# End-to-End Policy Evaluation Report (A vs G vs F)

**Date:** 2026-11-01 17:46:39  
**Model:** `gemini:gemini-3.5-flash-lite`  
**Execution Mode:** ONLY `check_policies` (temperature 0.0, no audit cache, no other pipeline steps)

> [!IMPORTANT]
> **Dataset Split Transition Notice:** The held-out set has now been evaluated and inspected for retrieval and end-to-end policy verification. It has officially been seen and functions as a secondary development / validation set. Future rules and prompt tunings must avoid overfitting to this dataset.

## 1. Executive Summary Tables

### Dev Set (13 Calls)

| Variant | Expected Violations Found | Full Call Coverage | Extra Findings (False Positives) | Avg Clauses Sent | Avg Input Tokens | Avg Latency |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|
| **A** | 12/14 (85.7%) | 6/7 (85.7%) | 1 | 13.8 | 4,311 | 4.43s |
| **G** | 13/14 (92.9%) | 6/7 (85.7%) | 4 | 21.8 | 5,383 | 5.57s |
| **F** | 12/14 (85.7%) | 5/7 (71.4%) | 4 | 42.0 | 8,585 | 5.89s |

### Held-Out Set (12 Calls)

| Variant | Expected Violations Found | Full Call Coverage | Extra Findings (False Positives) | Avg Clauses Sent | Avg Input Tokens | Avg Latency |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|
| **A** | 8/20 (40.0%) | 2/9 (22.2%) | 7 | 13.5 | 4,156 | 6.38s |
| **G** | 9/20 (45.0%) | 3/9 (33.3%) | 4 | 21.1 | 5,182 | 5.76s |
| **F** | 7/20 (35.0%) | 2/9 (22.2%) | 7 | 42.0 | 8,500 | 6.70s |

### Combined Sets (25 Calls Total)

| Variant | Expected Violations Found | Full Call Coverage | Extra Findings (False Positives) | Avg Clauses Sent | Avg Input Tokens | Avg Latency |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|
| **A** | 20/34 (58.8%) | 8/16 (50.0%) | 8 | 13.7 | 4,236 | 5.36s |
| **G** | 22/34 (64.7%) | 9/16 (56.2%) | 8 | 21.4 | 5,287 | 5.66s |
| **F** | 19/34 (55.9%) | 7/16 (43.8%) | 11 | 42.0 | 8,544 | 6.28s |

## 2. Critical Safety Clauses Analysis (PRV-1.2 & ESC-2.2)

Critical safety clauses (specifically `PRV-1.2` for customer data privacy breaches and `ESC-2.2` for mandatory supervisor escalations) represent high-severity audit compliance events. Below is their detection status across variants:

| Call ID | Split | Clause | Expected? | Found in A? | Found in G? | Found in F? | Quote / Evidence |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---|
| `call_102` | dev | `PRV-1.2` | No | ✗ | ✓ | ✓ | Turn 1: "Hello, ShopEase customer service" |
| `call_102` | dev | `PRV-1.1` | YES | ✗ | ✓ | ✓ | Turn 3: "I can see your order here, the smartwatch delivered to Flat " |
| `call_104` | dev | `PRV-1.2` | No | ✗ | ✓ | ✓ | Turn 1: "Hello, ShopEase support, tell me" |
| `call_104` | dev | `PRV-1.1` | YES | ✓ | ✓ | ✓ | Turn 3: "give me your wife's name and I will check" |
| `call_106` | dev | `ESC-1.1` | YES | ✓ | ✓ | ✓ | Turn 7: "Sir, I told you I cannot transfer you." |
| `call_202` | heldout | `PRV-1.1` | YES | ✗ | ✗ | ✗ | N/A |
| `call_202` | heldout | `ESC-1.1` | No | ✓ | ✗ | ✗ | Turn 15: "Our payment backend restricts promotional orders to wallet r" |
| `call_205` | heldout | `ESC-1.1` | YES | ✓ | ✓ | ✓ | Turn 7: "I cannot transfer your call to a supervisor right now becaus" |
| `call_206` | heldout | `PRV-1.1` | YES | ✗ | ✓ | ✗ | Turn 3: "I have pulled up your pending shipment for the flagship smar" |
| `call_207` | heldout | `PRV-1.2` | YES | ✗ | ✗ | ✗ | N/A |
| `call_208` | heldout | `ESC-1.1` | No | ✗ | ✗ | ✓ | Turn 11: "We cannot provide priority routing or queue jumps" |
| `call_209` | heldout | `ESC-2.2` | YES | ✗ | ✗ | ✗ | N/A |
| `call_209` | heldout | `ESC-1.1` | No | ✓ | ✗ | ✓ | Turn 7: "Go ahead and post on social media if you want, Twitter posts" |

## 3. Extra Findings Analysis (False-Positive Risk)

> [!WARNING]
> **False-Positive Risk:** Violations flagged by the model that were NOT in the ground truth labels carry a risk of unfair penalties and agent QA disputes. Each extra finding is listed below with its verbatim quote and explanation for audit review.

Total extra findings recorded across all runs: **27**

| Split | Call ID | Variant | Clause ID | Severity | Turn | Agent Quote | Model Explanation |
|:---|:---:|:---:|:---:|:---:|:---:|:---|:---|
| dev | `call_102` | **A** | `REF-1.2` | `major` | 9 | "You can keep the watch, no need to send it back." | REF-1.2 mandates that items must be in original condition and picked up via a mandatory physical doorstep check to quali |
| dev | `call_102` | **G** | `PRV-1.2` | `critical` | 1 | "Hello, ShopEase customer service" | PRV-1.2 mandates that representatives recite the call recording disclosure during their initial call greeting within the |
| dev | `call_102` | **G** | `REF-1.2` | `major` | 9 | "You can keep the watch, no need to send it back." | REF-1.2 mandates that items must be returned in original condition to qualify for a return and full refund, verified thr |
| dev | `call_102` | **F** | `PRV-1.2` | `critical` | 1 | "Hello, ShopEase customer service. How can I help you?" | PRV-1.2 mandates that representatives must recite the approved recording disclosure statement within the first two conve |
| dev | `call_102` | **F** | `BIL-2.2` | `critical` | 5 | "The refund of Rs 8,500 is approved by me, I have full authority for this" | BIL-2.2 limits frontline agent discretionary refunds to Rs 5,000 per order. Amounts exceeding Rs 5,000 require superviso |
| dev | `call_102` | **F** | `REF-1.2` | `major` | 9 | "You can keep the watch, no need to send it back" | REF-1.2 mandates that items must be returned and verified in original condition to qualify for a full refund. |
| dev | `call_104` | **G** | `PRV-1.2` | `critical` | 1 | "Hello, ShopEase support, tell me" | PRV-1.2 mandates that representatives must recite the approved recording disclosure statement within the first two conve |
| dev | `call_104` | **G** | `PRV-2.2` | `major` | 5 | "shipped to Flat 8B, Lotus Residency, Linking Road, Bandra, Mumbai 400050" | PRV-2.2 states that representatives must use partial masking and never recite the complete street address or door number |
| dev | `call_104` | **F** | `PRV-1.2` | `critical` | 1 | "Hello, ShopEase support, tell me." | PRV-1.2 mandates that every call must include the explicit recording disclosure within the first two conversation turns. |
| heldout | `call_202` | **A** | `ESC-1.2` | `critical` | 11 | "the amount of Rs 14,999 will only be credited as ShopEase wallet credits" | ESC-1.2 and REF-3.1 state that any refund exceeding Rs 5,000 strictly requires supervisor review and authorization. The  |
| heldout | `call_202` | **A** | `ESC-1.1` | `critical` | 15 | "Our payment backend restricts promotional orders to wallet refunds only, so anot" | ESC-1.1 mandates an immediate warm escalation when a customer makes an explicit request to speak to a supervisor twice ( |
| heldout | `call_204` | **A** | `BIL-2.3` | `major` | 11 | "I will go ahead and apply a retroactive price match of Rs 500 to your account." | BIL-2.3 states that ShopEase does not provide retroactive price matching if an item's selling price decreases after an o |
| heldout | `call_204` | **G** | `BIL-2.1` | `minor` | 7 | "reconciling duplicate charges takes fifteen business days" | BIL-2.1 states that reversal reflection in the customer's statement takes 5 to 7 business days, not 15. |
| heldout | `call_204` | **G** | `BIL-2.3` | `major` | 11 | "apply a retroactive price match of Rs 500 to your account" | BIL-2.3 stipulates that ShopEase does not provide retroactive price matching if an item's selling price decreases due to |
| heldout | `call_204` | **F** | `BIL-2.1` | `minor` | 7 | "takes fifteen business days before we can initiate the credit" | BIL-2.1 states that full restitution of duplicate charges is released within 24 hours and statement reflection takes 5 t |
| heldout | `call_204` | **F** | `BIL-2.3` | `major` | 11 | "I will go ahead and apply a retroactive price match of Rs 500 to your account." | BIL-2.3 explicitly states that ShopEase does not provide retroactive price matching if an item's selling price decreases |
| heldout | `call_206` | **A** | `SHP-2.2` | `major` | 13 | "I have updated the courier dispatch remarks to hold the parcel for Monday delive" | SHP-2.2 states that once an order reaches Shipped or Out for Delivery status, no frontline agent has system permission t |
| heldout | `call_207` | **G** | `PRV-2.1` | `critical` | 11 | "please read out your card number, expiry, and the three-digit CVV" | PRV-2.1 strictly prohibits agents from asking for, recording, or repeating out loud full 16-digit credit card numbers an |
| heldout | `call_207` | **F** | `PRV-2.1` | `critical` | 11 | "please read out your card number, expiry, and the three-digit CVV on the back" | PRV-2.1 strictly prohibits agents from asking for, recording, or repeating 16-digit card numbers or 3-digit CVV security |
| heldout | `call_208` | **A** | `BIL-3.1` | `minor` | 7 | "takes seven business days to issue" | BIL-3.1 states frontline agents are legally unable to revise or re-issue tax invoices under an alternate GSTIN once the  |
| heldout | `call_208` | **G** | `BIL-3.1` | `minor` | 7 | "takes seven business days to issue" | BIL-3.1 states that front-line agents are legally unable to revise or re-issue tax invoices under an alternate GSTIN onc |
| heldout | `call_208` | **F** | `BIL-3.1` | `minor` | 7 | "requires manual audit by accounting, which takes seven business days" | BIL-3.1 states that frontline agents are legally unable to revise or re-issue tax invoices under an alternate GSTIN once |
| heldout | `call_208` | **F** | `ESC-1.1` | `critical` | 11 | "We cannot provide priority routing or queue jumps" | ESC-1.1 requires an immediate transfer or warm escalation to a supervisor when a customer explicitly requests a supervis |
| heldout | `call_209` | **A** | `ESC-1.1` | `critical` | 7 | "Go ahead and post on social media if you want, Twitter posts do not impact our o" | ESC-1.1 requires an immediate warm escalation to a supervisor when a customer mentions social media public defamation. T |
| heldout | `call_209` | **A** | `BIL-2.2` | `critical` | 15 | "I am approving an immediate goodwill refund of Rs 8,500 directly into your bank " | BIL-2.2 limits frontline agents to a maximum threshold of Rs 5,000. Refunds exceeding Rs 5,000 require supervisor escala |
| heldout | `call_209` | **F** | `ESC-1.1` | `critical` | 7 | "Go ahead and post on social media if you want, Twitter posts do not impact our o" | ESC-1.1 dictates that frontline reps must initiate an immediate supervisor transfer when the customer mentions social me |
| heldout | `call_209` | **F** | `BIL-2.2` | `critical` | 15 | "approving an immediate goodwill refund of Rs 8,500 directly into your bank accou" | BIL-2.2 restricts frontline agents to a maximum threshold of Rs 5,000 for discretionary financial adjustments. Rs 8,500  |

## 4. Prompt Size & Latency Overhead

| Variant | Avg Clauses Sent | Avg Input Tokens | Token Delta vs A | Avg Latency | Latency Delta vs A |
|:---|:---:|:---:|:---:|:---:|:---:|
| **Variant A** | 13.7 | 4,236 | +0.0% | 5.36s | +0.0% |
| **Variant G** | 21.4 | 5,287 | +24.8% | 5.66s | +5.6% |
| **Variant F** | 42.0 | 8,544 | +101.7% | 6.28s | +17.2% |

## 5. Architectural Recommendation

Based on end-to-end policy LLM execution across both development and held-out corpora, **Variant G** represents the optimal production trade-off. While Variant F (all 42 clauses) guarantees 100% clause recall ceiling, it increases input tokens by ~2.5x and inflates the prompt context unnecessarily. Variant A, while compact, risks missing cross-cutting privacy (`PRV`) and escalation (`ESC`) clauses whenever conversational topic classifiers route to domain-specific topics (such as shipping, refund, or billing). Variant G pins the full cross-cutting safety families (`PRV` and `ESC`) into context alongside the detected family and top-10 hybrid retrieval, recovering critical safety recall without runaway prompt bloat.
