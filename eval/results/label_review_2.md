# Label Review Report 2 (Round 2)

**Date:** 2026-11-03  
**File:** `eval/results/label_review_2.md`  
**Audit Scope:** Ground-truth and model finding verification across JSON transcripts and policy Markdown definitions. All clause texts and transcript quotes below are extracted directly from repository files by script.

## 1. Policy Clause Definitions (Direct Source File Extraction)

### Clause `PRV-2.2`: Delivery Address Masking and Privacy
- **File Path:** `data/policies/privacy_identity_verification.md`
- **Clause ID:** `PRV-2.2`
- **Exact Text:**
```text
PRV-2.2 Delivery Address Masking and Privacy
- **Topics:** shipping, general
- **Situations:** data_disclosure
- **Numeric Limit:** none
- **Default Severity:** major
- **Kind:** must_not_do

1. When confirming shipping details with an authenticated caller, representatives must use partial masking:
   - Quote only the recipient's first name, city, and pin code.
   - Never recite the complete street address or door number out loud unless the customer recites it first for confirmation.
```

### Clause `REF-1.2`: Item Condition and Verification
- **File Path:** `data/policies/refund_and_returns.md`
- **Clause ID:** `REF-1.2`
- **Exact Text:**
```text
REF-1.2 Item Condition and Verification
- **Topics:** refund
- **Situations:** none
- **Numeric Limit:** none
- **Default Severity:** major
- **Kind:** informational

1. To qualify for a return and full refund, items must be in original condition, unused, unwashed, and accompanied by:
   - Original brand packaging, tags, warranty cards, manuals, and bundled accessories.
   - Intact serial numbers / IMEI numbers matching the invoice record.
2. Couriers perform a mandatory physical doorstep check upon pickup. Pickup will be rejected if serial numbers do not match or if physical abuse is detected.
```

### Clause `PRV-1.2`: Mandatory Call Recording Disclosure
- **File Path:** `data/policies/privacy_identity_verification.md`
- **Clause ID:** `PRV-1.2`
- **Exact Text:**
```text
PRV-1.2 Mandatory Call Recording Disclosure
- **Topics:** general
- **Situations:** none
- **Numeric Limit:** none
- **Default Severity:** critical
- **Kind:** must_say

1. Indian telecom and privacy compliance mandates that every incoming and outbound call must include an explicit recording notification at the very start of the interaction.
2. Representatives must recite the approved disclosure statement during their initial call greeting:
   - *"Please note this call is recorded for quality assurance and training purposes."*
3. Failure to deliver the recording disclosure within the first two conversation turns is a **Critical Compliance Infraction**.
```

### Clause `ESC-1.1`: Mandatory Supervisor Escalation Triggers
- **File Path:** `data/policies/escalation.md`
- **Clause ID:** `ESC-1.1`
- **Exact Text:**
```text
ESC-1.1 Mandatory Supervisor Escalation Triggers
- **Topics:** complaint, general
- **Situations:** supervisor_request, angry_customer, transfer
- **Numeric Limit:** none
- **Default Severity:** critical
- **Kind:** must_say

1. Frontline customer service representatives are required to initiate an immediate transfer or warm escalation to a supervisor under the following circumstances:
   - **Customer Explicit Request:** The customer explicitly asks to speak to a supervisor, manager, or senior lead **two (2) times** within the conversation.
   - **Unresolved Inquiries:** The customer's issue remains unresolved after **two (2) distinct frontline attempts** to clarify or execute a solution.
   - **Legal or Regulatory Mention:** The customer mentions consumer court, legal representation, cyber cell, or social media public defamation.
   - **Profanity or Threat of Harm:** Repeated abusive profanity or personal verbal threats directed at the representative after warning.
```

### Clause `ESC-1.2`: Monetary Escalation and Approval Limits
- **File Path:** `data/policies/escalation.md`
- **Clause ID:** `ESC-1.2`
- **Exact Text:**
```text
ESC-1.2 Monetary Escalation and Approval Limits
- **Topics:** complaint, refund, billing
- **Situations:** high_value_refund, supervisor_request, transfer
- **Numeric Limit:** Rs 5,000
- **Default Severity:** critical
- **Kind:** must_not_do

1. Frontline representatives possess monetary approval discretion up to **Rs 5,000**.
2. Any request involving concessions, replacements, goodwill vouchers, or refunds exceeding **Rs 5,000** must be escalated to a Level-1 Supervisor (authorized up to Rs 25,000) or Level-2 Operations Manager (authorized above Rs 25,000).
3. Agents must summarize the customer's issue and policy basis to the supervisor prior to warm call handover.
```

### Clause `ESC-2.1`: Warm Transfer Protocol and Hold Regulations
- **File Path:** `data/policies/escalation.md`
- **Clause ID:** `ESC-2.1`
- **Exact Text:**
```text
ESC-2.1 Warm Transfer Protocol and Hold Regulations
- **Topics:** complaint, general
- **Situations:** hold, transfer, callback, supervisor_request
- **Numeric Limit:** 2 minutes
- **Default Severity:** major
- **Kind:** must_say

1. Before initiating an escalation transfer to a supervisor, the agent must inform the customer and place them on a courtesy hold.
2. Under no circumstance may an agent keep a customer on hold for more than **2 minutes without performing an active check-in** (`[HLD-03]`).
3. If no supervisor is immediately available within 2 minutes:
   - The agent must retrieve the call from hold.
   - Apologize for the extended wait.
   - Offer a confirmed **Supervisor Callback SLA within 2 to 4 business hours**.
```

### Clause `WAR-2.3`: ShopEase Assured Warranty Facilitation
- **File Path:** `data/policies/warranty_replacement.md`
- **Clause ID:** `WAR-2.3`
- **Exact Text:**
```text
WAR-2.3 ShopEase Assured Warranty Facilitation
- **Topics:** warranty, refund
- **Situations:** none
- **Numeric Limit:** 14 business days
- **Default Severity:** minor
- **Kind:** informational

1. For items marketed under the "ShopEase Assured" badge where the manufacturer does not have a physical service center within 30 km of the customer's residential pin code:
   - ShopEase provides doorstep pickup and complimentary courier transit to the regional service hub.
   - Maximum turnaround time (TAT) for repair or replacement is 14 business days.
   - If repair cannot be completed within 14 business days, a full refund will be credited under clause `[REF-2.1]`.
```

## 2. Transcript Turns (Direct Source File Extraction)

### `call_102` (Turn 9)
- **File Path:** `data/transcripts/call_102.json`
- **Turn Index:** 9
- **Speaker:** `agent`
- **Exact Text:** "It will be credited within 24 hours. You can keep the watch, no need to send it back."

### `call_104` (Turn 5)
- **File Path:** `data/transcripts/call_104.json`
- **Turn Index:** 5
- **Speaker:** `agent`
- **Exact Text:** "No problem, I found it. The order is for a Prestige induction cooktop, Rs 4,750, paid with a debit card ending 4412, and it is shipped to Flat 8B, Lotus Residency, Linking Road, Bandra, Mumbai 400050."

### `call_106` (Turns 12-14)
- **File Path:** `data/transcripts/call_106.json`
- **Turn Index:** 12
- **Speaker:** `customer`
- **Exact Text:** "I am done listening. I am filing a complaint in consumer court."
- **Turn Index:** 13
- **Speaker:** `agent`
- **Exact Text:** "Okay sir, wait, I am putting you on hold, I will check with someone."
- **Turn Index:** 14
- **Speaker:** `agent`
- **Exact Text:** "Hello sir, yes, nobody is available. Anything else?"

### `call_202` (Turns 9-16)
- **File Path:** `data/heldout/transcripts/call_202.json`
- **Turn Index:** 9
- **Speaker:** `agent`
- **Exact Text:** "Yes, I can arrange a return pickup within 48 hours. The courier will inspect the unit and collect the box."
- **Turn Index:** 10
- **Speaker:** `customer`
- **Exact Text:** "Great. I paid Rs 14,999 on my Visa credit card, so please credit it back to that card."
- **Turn Index:** 11
- **Speaker:** `agent`
- **Exact Text:** "Since you purchased this during the weekend clearance sale, refunds cannot be returned to your Visa card; the amount of Rs 14,999 will only be credited as ShopEase wallet credits for future purchases."
- **Turn Index:** 12
- **Speaker:** `customer`
- **Exact Text:** "What? Why would I want wallet credits? I paid with real money from my card and the device is defective!"
- **Turn Index:** 13
- **Speaker:** `agent`
- **Exact Text:** "Clearance items are strictly non-refundable to card accounts under our system policies; only store credits can be offered."
- **Turn Index:** 14
- **Speaker:** `customer`
- **Exact Text:** "This is very disappointing. Let me speak to someone who can process a proper bank refund."
- **Turn Index:** 15
- **Speaker:** `agent`
- **Exact Text:** "Our payment backend restricts promotional orders to wallet refunds only, so another representative would tell you the exact same thing."
- **Turn Index:** 16
- **Speaker:** `customer`
- **Exact Text:** "I will take this up separately then. Good day."

### `call_203` (Turns 13-15)
- **File Path:** `data/heldout/transcripts/call_203.json`
- **Turn Index:** 13
- **Speaker:** `agent`
- **Exact Text:** "Our platform partner agreements provide six months coverage unless an extended warranty pack was separately purchased."
- **Turn Index:** 14
- **Speaker:** `customer`
- **Exact Text:** "I will be contacting consumer affairs regarding this policy. Goodbye."
- **Turn Index:** 15
- **Speaker:** `agent`
- **Exact Text:** "You are free to do so, ma'am. Thank you for contacting ShopEase."

### `call_205` (Turns 5-8)
- **File Path:** `data/heldout/transcripts/call_205.json`
- **Turn Index:** 5
- **Speaker:** `agent`
- **Exact Text:** "Thank you, Ms. Nair, your details match the account. Let me review the case history."
- **Turn Index:** 6
- **Speaker:** `customer`
- **Exact Text:** "Do not review anything, just transfer the call. I have spent hours explaining this."
- **Turn Index:** 7
- **Speaker:** `agent`
- **Exact Text:** "I cannot transfer your call to a supervisor right now because our managerial queue is closed for the day, and we do not provide callbacks from managers."
- **Turn Index:** 8
- **Speaker:** `customer`
- **Exact Text:** "What do you mean you don't provide callbacks? Your frontline staff has failed to resolve a damaged product for over a week!"

### `call_206` (Turns 2-3)
- **File Path:** `data/heldout/transcripts/call_206.json`
- **Turn Index:** 2
- **Speaker:** `customer`
- **Exact Text:** "Hi Manoj, I am Siddharth Mehta. I placed an order for a new smartphone, but I will be out of town tomorrow when it is supposed to arrive."
- **Turn Index:** 3
- **Speaker:** `agent`
- **Exact Text:** "Good morning, I have pulled up your pending shipment for the flagship smartphone heading to your residency at Green Glen Layout."

## 3. Gemini 3.5 Flash Extra Findings Review and Final Decisions

**Source File:** `eval/results/policy_model_comparison.csv` (Model: `gemini:gemini-3.5-flash`, Run 1, Variant G)

| # | Split | Call ID | Clause ID | Turn Index | Model-Cited Quote | Final Decision | Justification |
|:---:|:---:|:---:|:---:|:---:|:---|:---:|:---|
| 1 | `dev` | `call_102` | `PRV-1.2` | 1 | "Hello, ShopEase customer service. How can I help you?" | **add** | Clause PRV-1.2 mandates delivering the approved recording disclosure within the first two conversation turns, which this opening greeting fails to include. |
| 2 | `dev` | `call_102` | `REF-1.2` | 9 | "You can keep the watch, no need to send it back." | **skip** | Clause REF-1.2 specifies item condition requirements upon return, but the agent's action on turn 9 reflects a concession under frontline discretion rather than an item condition infraction; skipped per user decision. |
| 3 | `dev` | `call_104` | `PRV-1.2` | 1 | "Hello, ShopEase support, tell me." | **add** | Clause PRV-1.2 requires representatives to recite the recording disclosure during their initial greeting within the first two turns, which is entirely missing from this greeting. |
| 4 | `dev` | `call_104` | `PRV-2.2` | 5 | "and it is shipped to Flat 8B, Lotus Residency, Linking Road, Bandra, Mumbai 400050." | **add** | Clause PRV-2.2 explicitly forbids reciting complete street addresses or door numbers out loud unless the customer recites it first for confirmation. |
| 5 | `dev` | `call_106` | `ESC-2.1` | 14 | "Hello sir, yes, nobody is available. Anything else?" | **add** | Clause ESC-2.1 requires that if no supervisor is immediately available, the agent must apologize and offer a confirmed Supervisor Callback SLA within 2 to 4 business hours. |
| 6 | `heldout` | `call_202` | `PRV-2.2` | 3 | "delivered to flat 402, Palm Heights in Pune yesterday" | **add** | Clause PRV-2.2 requires partial masking of delivery addresses and strictly prohibits reciting complete door numbers or street addresses out loud. |
| 7 | `heldout` | `call_202` | `ESC-1.2` | 11 | "the amount of Rs 14,999 will only be credited as ShopEase wallet credits" | **skip** | Clause ESC-1.2 caps frontline authority at Rs 5,000, but call_202 ground truth already captures the core refund refusal violations; skipped per user decision. |
| 8 | `heldout` | `call_202` | `ESC-1.1` | 15 | "Our payment backend restricts promotional orders to wallet refunds only, so another representative would tell you the exact same thing." | **skip** | Clause ESC-1.1 mandates supervisor escalation upon explicit request, but call_202 ground truth already focuses on refund policy infractions; skipped per user decision. |
| 9 | `heldout` | `call_203` | `ESC-1.1` | 15 | "You are free to do so, ma'am. Thank you for contacting ShopEase." | **skip** | Clause ESC-1.1 lists mention of consumer court as an escalation trigger, but call_203 ground truth intentionally isolates warranty duration and condition rules; skipped per user decision. |
| 10 | `heldout` | `call_205` | `ESC-2.1` | 7 | "we do not provide callbacks from managers." | **add** | Clause ESC-2.1 mandates offering a confirmed Supervisor Callback SLA within 2 to 4 business hours when a supervisor is not immediately available, which claiming that callbacks are not provided directly breaches. |
| 11 | `heldout` | `call_206` | `PRV-2.2` | 3 | "heading to your residency at Green Glen Layout." | **borderline** | Clause PRV-2.2 instructs representatives to quote only first name, city, and pin code and never recite street address or door number out loud, though here only the residential layout name was stated without a door number. |
| 12 | `heldout` | `call_207` | `WAR-2.3` | 7 | "standard repair turnaround time is forty-five days, and we cannot offer any replacement unit or refund" | **skip** | Clause WAR-2.3 sets a maximum repair or replacement turnaround time of 14 business days, but this finding on turn 7 is already evaluated under ground truth WAR-2.1 as an alternate pair. |
| 13 | `heldout` | `call_209` | `WAR-2.3` | 11 | "During festival months, panel replacement turnaround times are indefinite; it could take several months and we cannot commit to any timeline." | **skip** | Clause WAR-2.3 establishes a maximum turnaround time of 14 business days and prohibits quoting indefinite timelines, but this finding on turn 11 is already evaluated under ground truth WAR-2.1 as an alternate pair. |
| 14 | `heldout` | `call_212` | `WAR-2.3` | 21 | "authorized service centers must resolve the repair within a maximum turnaround window of 14 calendar days." | **borderline** | Clause WAR-2.3 specifies a maximum turnaround time of 14 business days, making the agent citation of 14 calendar days a technical discrepancy regarding business versus calendar days. |

### Itemized Detail for the 6 Added Labels

#### Extra 1: `call_102` (dev) — Clause `PRV-1.2`
- **File Path:** `data/transcripts/call_102.json`
- **Clause ID:** `PRV-1.2`
- **Turn Index:** 1
- **Severity:** `critical`
- **Quote:** `"Hello, ShopEase customer service. How can I help you?"`
- **Final Decision:** `add`
- **Ground Truth Target:** `data/expected/expected_results.json`

#### Extra 3: `call_104` (dev) — Clause `PRV-1.2`
- **File Path:** `data/transcripts/call_104.json`
- **Clause ID:** `PRV-1.2`
- **Turn Index:** 1
- **Severity:** `critical`
- **Quote:** `"Hello, ShopEase support, tell me."`
- **Final Decision:** `add`
- **Ground Truth Target:** `data/expected/expected_results.json`

#### Extra 4: `call_104` (dev) — Clause `PRV-2.2`
- **File Path:** `data/transcripts/call_104.json`
- **Clause ID:** `PRV-2.2`
- **Turn Index:** 5
- **Severity:** `major`
- **Quote:** `"No problem, I found it. The order is for a Prestige induction cooktop, Rs 4,750, paid with a debit card ending 4412, and it is shipped to Flat 8B, Lotus Residency, Linking Road, Bandra, Mumbai 400050."`
- **Final Decision:** `add`
- **Ground Truth Target:** `data/expected/expected_results.json`

#### Extra 5: `call_106` (dev) — Clause `ESC-2.1`
- **File Path:** `data/transcripts/call_106.json`
- **Clause ID:** `ESC-2.1`
- **Turn Index:** 14
- **Severity:** `major`
- **Quote:** `"Hello sir, yes, nobody is available. Anything else?"`
- **Final Decision:** `add`
- **Ground Truth Target:** `data/expected/expected_results.json`

#### Extra 6: `call_202` (heldout) — Clause `PRV-2.2`
- **File Path:** `data/heldout/transcripts/call_202.json`
- **Clause ID:** `PRV-2.2`
- **Turn Index:** 3
- **Severity:** `major`
- **Quote:** `"Yes, Mr. Joshi. I see the order was placed on Sunday, delivered to flat 402, Palm Heights in Pune yesterday."`
- **Final Decision:** `add`
- **Ground Truth Target:** `data/heldout/expected_heldout.json`

#### Extra 10: `call_205` (heldout) — Clause `ESC-2.1`
- **File Path:** `data/heldout/transcripts/call_205.json`
- **Clause ID:** `ESC-2.1`
- **Turn Index:** 7
- **Severity:** `major`
- **Quote:** `"I cannot transfer your call to a supervisor right now because our managerial queue is closed for the day, and we do not provide callbacks from managers."`
- **Final Decision:** `add`
- **Ground Truth Target:** `data/heldout/expected_heldout.json`

## 4. Final Disposition and Rescoring Results (Old vs New)

### Ground Truth Denominators
- **Old Baseline Denominators:** Dev = 14, Held-Out = 19, Combined = 33
- **New Reviewed Denominators:** Dev = 18 (+4), Held-Out = 21 (+2), Combined = 39 (+6)

### Comparative Rescoring Table

| Model | Ground Truth | Dev Recall | Held-Out Recall | Combined Recall | Extras (Dev / Held / Total) |
|:---|:---:|:---:|:---:|:---:|:---:|
| **Flash-Lite (3-Run Avg)** | OLD (33) | 12.3 / 14 (88.1%) | 12.3 / 19 (64.9%) | 24.7 / 33 (74.7%) | 4.0 / 2.3 / 6.3 |
| **Flash-Lite (3-Run Avg)** | NEW (39) | 15.3 / 18 (85.2%) | 13.0 / 21 (61.9%) | 28.3 / 39 (72.6%) | 1.0 / 1.7 / 2.7 |
| **Gemini-2.5-Flash (Run 1)** | OLD (33) | 14 / 14 (100.0%) | 15 / 19 (78.9%) | 29 / 33 (87.9%) | 3 / 5 / 8 |
| **Gemini-2.5-Flash (Run 1)** | NEW (39) | 16 / 18 (88.9%) | 16 / 21 (76.2%) | 32 / 39 (82.1%) | 1 / 4 / 5 |
| **Gemini-3.5-Flash (Run 1)** | OLD (33) | 14 / 14 (100.0%) | 18 / 19 (94.7%) | 32 / 33 (97.0%) | 5 / 7 / 12 |
| **Gemini-3.5-Flash (Run 1)** | NEW (39) | 18 / 18 (100.0%) | 20 / 21 (95.2%) | 38 / 39 (97.4%) | 1 / 5 / 6 |

### Per-Run Breakdown for Flash-Lite
- **Run 1:**
  - OLD: Dev 13/14 (92.9%), Held 12/19 (63.2%), Combined 25/33 (75.8%), Extras 4 / 2 / 6
  - NEW: Dev 16/18 (88.9%), Held 12/21 (57.1%), Combined 28/39 (71.8%), Extras 1 / 2 / 3
- **Run 2:**
  - OLD: Dev 11/14 (78.6%), Held 13/19 (68.4%), Combined 24/33 (72.7%), Extras 4 / 3 / 7
  - NEW: Dev 14/18 (77.8%), Held 14/21 (66.7%), Combined 28/39 (71.8%), Extras 1 / 2 / 3
- **Run 3:**
  - OLD: Dev 13/14 (92.9%), Held 12/19 (63.2%), Combined 25/33 (75.8%), Extras 4 / 2 / 6
  - NEW: Dev 16/18 (88.9%), Held 13/21 (61.9%), Combined 29/39 (74.4%), Extras 1 / 1 / 2
