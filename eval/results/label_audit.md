# Conversational Quality Audit Agent — Label & Findings Audit Report

**Date:** 2026-11-01 18:01:12  
**Target File:** `eval/results/label_audit.md`  
**Scope:** Dev Split (13 calls) and Held-Out Split (12 calls)  
**Production Status:** Audit artifact only — zero production changes, zero edits to stored expectations or transcripts.

> [!IMPORTANT]
> **Notice for Human Reviewers:**
> 1. **No Editorial Alterations:** Per strict audit guidelines, no stored labels, expectations, or transcript texts have been judged, modified, or altered. All data is presented verbatim for human review.
> 2. **Split Transition Notice:** The held-out dataset has now been evaluated end-to-end and inspected. It officially functions as a secondary development / validation corpus.
> 3. **Audit Purpose:** This document compiles every ground-truth violation label, every extra finding (false-positive candidate) surfaced during end-to-end policy execution, every ceiling miss by Variant F, and the deterministic scoring delta between Variant A (production) and Variant G.

## 1. Ground Truth Expected (Call, Clause) Violations Audit

Below is the complete registry of all 34 expected policy violation labels across the Development (14 pairs) and Held-Out (20 pairs) evaluation sets. For each pair, the exact clause title, the first 300 characters of the policy clause definition, and the exact transcript turn text are presented for human verification.

### 1.1 Expected Violations Registry Summary

| # | Split | Call ID | Clause ID | Severity | Target Turn | Clause Title |
|:---:|:---:|:---:|:---:|:---:|:---:|:---|
| 1 | `dev` | `call_017` | `SHP-2.1` | `minor` | Turn 9 | Carrier Attempts and Undelivered Consignments |
| 2 | `dev` | `call_025` | `WAR-2.1` | `minor` | Turn 5 | Free Replacement Workflow |
| 3 | `dev` | `call_041` | `WAR-3.2` | `minor` | Turn 11 | Refurbished and Open-Box Warranty Rules |
| 4 | `dev` | `call_102` | `PRV-1.1` | `critical` | Turn 3 | Mandatory Two-Factor Customer Identity Verification |
| 5 | `dev` | `call_102` | `REF-3.1` | `critical` | Turn 5 | Agent Approval Authority Threshold |
| 6 | `dev` | `call_102` | `REF-2.2` | `major` | Turn 7 | Method of Refund Disbursement |
| 7 | `dev` | `call_102` | `REF-2.1` | `major` | Turn 9 | Refund Processing Timelines |
| 8 | `dev` | `call_104` | `PRV-1.1` | `critical` | Turn 5 | Mandatory Two-Factor Customer Identity Verification |
| 9 | `dev` | `call_104` | `BIL-2.1` | `minor` | Turn 7 | Double Deductions and Duplicate Billings |
| 10 | `dev` | `call_106` | `ESC-1.1` | `critical` | Turn 7 | Mandatory Supervisor Escalation Triggers |
| 11 | `dev` | `call_106` | `SHP-2.3` | `major` | Turn 9 | Delayed Shipments and Compensation Protocol |
| 12 | `dev` | `call_107` | `WAR-1.2` | `major` | Turn 7 | Dead on Arrival (DOA) and Transit Damage Reporting |
| 13 | `dev` | `call_107` | `REF-1.1` | `major` | Turn 7 | Return Eligibility Windows |
| 14 | `dev` | `call_107` | `WAR-1.1` | `minor` | Turn 9 | Standard Electronics Warranty Coverage |
| 15 | `heldout` | `call_201` | `SHP-2.1` | `major` | Turn 6 | Carrier Attempts and Undelivered Consignments |
| 16 | `heldout` | `call_202` | `PRV-1.1` | `critical` | Turn 3 | Mandatory Two-Factor Customer Identity Verification |
| 17 | `heldout` | `call_202` | `REF-1.1` | `major` | Turn 7 | Return Eligibility Windows |
| 18 | `heldout` | `call_202` | `REF-2.2` | `major` | Turn 11 | Method of Refund Disbursement |
| 19 | `heldout` | `call_203` | `REF-1.1` | `major` | Turn 7 | Return Eligibility Windows |
| 20 | `heldout` | `call_203` | `WAR-1.1` | `minor` | Turn 11 | Standard Electronics Warranty Coverage |
| 21 | `heldout` | `call_204` | `BIL-1.2` | `major` | Turn 7 | Failed Transactions and Auto-Reversals |
| 22 | `heldout` | `call_204` | `BIL-2.2` | `minor` | Turn 11 | Agent Discretionary Compensation Limit |
| 23 | `heldout` | `call_205` | `ESC-1.1` | `critical` | Turn 7 | Mandatory Supervisor Escalation Triggers |
| 24 | `heldout` | `call_205` | `ESC-2.1` | `critical` | Turn 11 | Warm Transfer Protocol and Hold Regulations |
| 25 | `heldout` | `call_205` | `ESC-3.1` | `major` | Turn 15 | Priority Support Level SLA Commitments |
| 26 | `heldout` | `call_206` | `PRV-1.1` | `critical` | Turn 3 | Mandatory Two-Factor Customer Identity Verification |
| 27 | `heldout` | `call_206` | `SHP-3.1` | `major` | Turn 7 | Secure One-Time Password (OTP) Delivery Protocol |
| 28 | `heldout` | `call_207` | `WAR-2.1` | `major` | Turn 7 | Free Replacement Workflow |
| 29 | `heldout` | `call_207` | `PRV-1.2` | `critical` | Turn 11 | Mandatory Call Recording Disclosure |
| 30 | `heldout` | `call_208` | `BIL-2.1` | `minor` | Turn 7 | Double Deductions and Duplicate Billings |
| 31 | `heldout` | `call_208` | `ESC-1.2` | `major` | Turn 11 | Monetary Escalation and Approval Limits |
| 32 | `heldout` | `call_209` | `ESC-2.2` | `major` | Turn 7 | Cold Drops and Call Abandonment Prohibition |
| 33 | `heldout` | `call_209` | `WAR-2.1` | `major` | Turn 11 | Free Replacement Workflow |
| 34 | `heldout` | `call_209` | `REF-3.1` | `critical` | Turn 15 | Agent Approval Authority Threshold |

### 1.2 Expected Violations Detailed Verbatim Evidence

#### [1] `call_017` (dev) — Clause `SHP-2.1`: Carrier Attempts and Undelivered Consignments

- **Call ID:** `call_017` (dev split)
- **Clause ID & Title:** `SHP-2.1` — Carrier Attempts and Undelivered Consignments
- **Expected Severity:** `minor`
- **Target Transcript Turn:** Turn 9 (agent)
- **Clause Excerpt (First 300 Characters):**
```text
SHP-2.1 Carrier Attempts and Undelivered Consignments
- **Topics:** shipping, refund
- **Situations:** none
- **Numeric Limit:** 3 attempts
- **Default Severity:** minor
- **Kind:** informational

1. Delivery partners will make up to **three (3) independent delivery attempts** at the customer's ship
```
- **Exact Transcript Turn Text:**
> **Turn 9 (agent):** "As per our courier guidelines, the delivery agent will make only one single delivery attempt at your door. If you are not available during that visit, they will immediately cancel the order and return the parcel back to our origin warehouse."

---

#### [2] `call_025` (dev) — Clause `WAR-2.1`: Free Replacement Workflow

- **Call ID:** `call_025` (dev split)
- **Clause ID & Title:** `WAR-2.1` — Free Replacement Workflow
- **Expected Severity:** `minor`
- **Target Transcript Turn:** Turn 5 (agent)
- **Clause Excerpt (First 300 Characters):**
```text
WAR-2.1 Free Replacement Workflow
- **Topics:** warranty, refund
- **Situations:** none
- **Numeric Limit:** 5 to 7 business days
- **Default Severity:** minor
- **Kind:** informational

1. Once damage/defect evidence is validated by our verification team (within 24 hours of ticket submission):
   -
```
- **Exact Transcript Turn Text:**
> **Turn 5 (agent):** "Thank you for validating your account details. If I understand correctly, your Boat Rockerz 450 headphones were delivered yesterday, and the left ear cup is completely silent right out of the box, so you are looking to arrange a free replacement. Is that accurate?"

---

#### [3] `call_041` (dev) — Clause `WAR-3.2`: Refurbished and Open-Box Warranty Rules

- **Call ID:** `call_041` (dev split)
- **Clause ID & Title:** `WAR-3.2` — Refurbished and Open-Box Warranty Rules
- **Expected Severity:** `minor`
- **Target Transcript Turn:** Turn 11 (agent)
- **Clause Excerpt (First 300 Characters):**
```text
WAR-3.2 Refurbished and Open-Box Warranty Rules
- **Topics:** warranty, refund
- **Situations:** none
- **Numeric Limit:** 6 months
- **Default Severity:** minor
- **Kind:** informational

1. Certified refurbished and open-box electronic devices carry a **6-month ShopEase warranty** instead of the s
```
- **Exact Transcript Turn Text:**
> **Turn 11 (agent):** "That is correct, refurbished items carry no warranty coverage whatsoever, whereas brand new units like your OnePlus come with full brand warranty and our return window."

---

#### [4] `call_102` (dev) — Clause `PRV-1.1`: Mandatory Two-Factor Customer Identity Verification

- **Call ID:** `call_102` (dev split)
- **Clause ID & Title:** `PRV-1.1` — Mandatory Two-Factor Customer Identity Verification
- **Expected Severity:** `critical`
- **Target Transcript Turn:** Turn 3 (agent)
- **Clause Excerpt (First 300 Characters):**
```text
PRV-1.1 Mandatory Two-Factor Customer Identity Verification
- **Topics:** general, refund, billing, shipping
- **Situations:** identity_verification, data_disclosure
- **Numeric Limit:** none
- **Default Severity:** critical
- **Kind:** must_not_do

1. To safeguard customer accounts and prevent unau
```
- **Exact Transcript Turn Text:**
> **Turn 3 (agent):** "Okay Mr. Rao, no problem, I can see your order here, the smartwatch delivered to Flat 12, Sai Residency, Pune. I will process the refund right away."

---

#### [5] `call_102` (dev) — Clause `REF-3.1`: Agent Approval Authority Threshold

- **Call ID:** `call_102` (dev split)
- **Clause ID & Title:** `REF-3.1` — Agent Approval Authority Threshold
- **Expected Severity:** `critical`
- **Target Transcript Turn:** Turn 5 (agent)
- **Clause Excerpt (First 300 Characters):**
```text
REF-3.1 Agent Approval Authority Threshold
- **Topics:** refund
- **Situations:** high_value_refund, supervisor_request
- **Numeric Limit:** Rs 5,000
- **Default Severity:** critical
- **Kind:** must_not_do

1. Frontline customer support agents possess discretionary authority to approve instant refu
```
- **Exact Transcript Turn Text:**
> **Turn 5 (agent):** "No, no need. The refund of Rs 8,500 is approved by me, I have full authority for this, so no supervisor is needed."

---

#### [6] `call_102` (dev) — Clause `REF-2.2`: Method of Refund Disbursement

- **Call ID:** `call_102` (dev split)
- **Clause ID & Title:** `REF-2.2` — Method of Refund Disbursement
- **Expected Severity:** `major`
- **Target Transcript Turn:** Turn 7 (agent)
- **Clause Excerpt (First 300 Characters):**
```text
REF-2.2 Method of Refund Disbursement
- **Topics:** refund, billing
- **Situations:** identity_verification, data_disclosure
- **Numeric Limit:** none
- **Default Severity:** major
- **Kind:** must_not_do

1. Refunds must be remitted strictly to the **original payment method** utilized during checko
```
- **Exact Transcript Turn Text:**
> **Turn 7 (agent):** "I will send it to your Paytm wallet, that is the quickest way."

---

#### [7] `call_102` (dev) — Clause `REF-2.1`: Refund Processing Timelines

- **Call ID:** `call_102` (dev split)
- **Clause ID & Title:** `REF-2.1` — Refund Processing Timelines
- **Expected Severity:** `major`
- **Target Transcript Turn:** Turn 9 (agent)
- **Clause Excerpt (First 300 Characters):**
```text
REF-2.1 Refund Processing Timelines
- **Topics:** refund
- **Situations:** none
- **Numeric Limit:** 5 to 7 business days
- **Default Severity:** minor
- **Kind:** informational

1. All approved refunds are processed within **5 to 7 business days** following successful return pickup and warehouse ve
```
- **Exact Transcript Turn Text:**
> **Turn 9 (agent):** "It will be credited within 24 hours. You can keep the watch, no need to send it back."

---

#### [8] `call_104` (dev) — Clause `PRV-1.1`: Mandatory Two-Factor Customer Identity Verification

- **Call ID:** `call_104` (dev split)
- **Clause ID & Title:** `PRV-1.1` — Mandatory Two-Factor Customer Identity Verification
- **Expected Severity:** `critical`
- **Target Transcript Turn:** Turn 5 (agent)
- **Clause Excerpt (First 300 Characters):**
```text
PRV-1.1 Mandatory Two-Factor Customer Identity Verification
- **Topics:** general, refund, billing, shipping
- **Situations:** identity_verification, data_disclosure
- **Numeric Limit:** none
- **Default Severity:** critical
- **Kind:** must_not_do

1. To safeguard customer accounts and prevent unau
```
- **Exact Transcript Turn Text:**
> **Turn 5 (agent):** "No problem, I found it. The order is for a Prestige induction cooktop, Rs 4,750, paid with a debit card ending 4412, and it is shipped to Flat 8B, Lotus Residency, Linking Road, Bandra, Mumbai 400050."

---

#### [9] `call_104` (dev) — Clause `BIL-2.1`: Double Deductions and Duplicate Billings

- **Call ID:** `call_104` (dev split)
- **Clause ID & Title:** `BIL-2.1` — Double Deductions and Duplicate Billings
- **Expected Severity:** `minor`
- **Target Transcript Turn:** Turn 7 (agent)
- **Clause Excerpt (First 300 Characters):**
```text
BIL-2.1 Double Deductions and Duplicate Billings
- **Topics:** billing, refund
- **Situations:** none
- **Numeric Limit:** 5 to 7 business days
- **Default Severity:** minor
- **Kind:** informational

1. In instances where a customer is charged twice for a single order due to gateway re-attempts:
```
- **Exact Transcript Turn Text:**
> **Turn 7 (agent):** "Yes, I can see two charges. The duplicate will be sorted out, it takes around 15 to 20 working days to come back."

---

#### [10] `call_106` (dev) — Clause `ESC-1.1`: Mandatory Supervisor Escalation Triggers

- **Call ID:** `call_106` (dev split)
- **Clause ID & Title:** `ESC-1.1` — Mandatory Supervisor Escalation Triggers
- **Expected Severity:** `critical`
- **Target Transcript Turn:** Turn 7 (agent)
- **Clause Excerpt (First 300 Characters):**
```text
ESC-1.1 Mandatory Supervisor Escalation Triggers
- **Topics:** complaint, general
- **Situations:** supervisor_request, angry_customer, transfer
- **Numeric Limit:** none
- **Default Severity:** critical
- **Kind:** must_say

1. Frontline customer service representatives are required to initiate an
```
- **Exact Transcript Turn Text:**
> **Turn 7 (agent):** "Sir, I told you I cannot transfer you. It is showing in transit, the courier will deliver when it delivers."

---

#### [11] `call_106` (dev) — Clause `SHP-2.3`: Delayed Shipments and Compensation Protocol

- **Call ID:** `call_106` (dev split)
- **Clause ID & Title:** `SHP-2.3` — Delayed Shipments and Compensation Protocol
- **Expected Severity:** `major`
- **Target Transcript Turn:** Turn 9 (agent)
- **Clause Excerpt (First 300 Characters):**
```text
SHP-2.3 Delayed Shipments and Compensation Protocol
- **Topics:** shipping, complaint, refund
- **Situations:** angry_customer
- **Numeric Limit:** 48 hours
- **Default Severity:** major
- **Kind:** informational

1. A shipment is officially categorized as "Delayed in Transit" when transit time exce
```
- **Exact Transcript Turn Text:**
> **Turn 9 (agent):** "Compensation or refund is not possible until thirty days are over, that is our rule. And there is no point creating a ticket, the courier will not respond."

---

#### [12] `call_107` (dev) — Clause `WAR-1.2`: Dead on Arrival (DOA) and Transit Damage Reporting

- **Call ID:** `call_107` (dev split)
- **Clause ID & Title:** `WAR-1.2` — Dead on Arrival (DOA) and Transit Damage Reporting
- **Expected Severity:** `major`
- **Target Transcript Turn:** Turn 7 (agent)
- **Clause Excerpt (First 300 Characters):**
```text
WAR-1.2 Dead on Arrival (DOA) and Transit Damage Reporting
- **Topics:** warranty, shipping, refund
- **Situations:** none
- **Numeric Limit:** 48 hours
- **Default Severity:** major
- **Kind:** must_say

1. Customers are entitled to a **free replacement** without any restocking fee or return shippi
```
- **Exact Transcript Turn Text:**
> **Turn 7 (agent):** "I understand. Unfortunately, any defect has to be reported within 48 hours of delivery with photos, and since you are on day six, there is nothing we can do. No replacement, no return and no warranty claim is possible now."

---

#### [13] `call_107` (dev) — Clause `REF-1.1`: Return Eligibility Windows

- **Call ID:** `call_107` (dev split)
- **Clause ID & Title:** `REF-1.1` — Return Eligibility Windows
- **Expected Severity:** `major`
- **Target Transcript Turn:** Turn 7 (agent)
- **Clause Excerpt (First 300 Characters):**
```text
REF-1.1 Return Eligibility Windows
- **Topics:** refund, warranty
- **Situations:** none
- **Numeric Limit:** 7 days
- **Default Severity:** major
- **Kind:** informational

1. Customers are entitled to initiate a return within the specified category window starting from the recorded delivery timest
```
- **Exact Transcript Turn Text:**
> **Turn 7 (agent):** "I understand. Unfortunately, any defect has to be reported within 48 hours of delivery with photos, and since you are on day six, there is nothing we can do. No replacement, no return and no warranty claim is possible now."

---

#### [14] `call_107` (dev) — Clause `WAR-1.1`: Standard Electronics Warranty Coverage

- **Call ID:** `call_107` (dev split)
- **Clause ID & Title:** `WAR-1.1` — Standard Electronics Warranty Coverage
- **Expected Severity:** `minor`
- **Target Transcript Turn:** Turn 9 (agent)
- **Clause Excerpt (First 300 Characters):**
```text
WAR-1.1 Standard Electronics Warranty Coverage
- **Topics:** warranty
- **Situations:** none
- **Numeric Limit:** 12 months
- **Default Severity:** minor
- **Kind:** informational

1. All consumer electronics, computer peripherals, home appliances, and audio gear sold on ShopEase are backed by a min
```
- **Exact Transcript Turn Text:**
> **Turn 9 (agent):** "Warranty covers only six months for audio products, and it is void if you did not claim in the first two days."

---

#### [15] `call_201` (heldout) — Clause `SHP-2.1`: Carrier Attempts and Undelivered Consignments

- **Call ID:** `call_201` (heldout split)
- **Clause ID & Title:** `SHP-2.1` — Carrier Attempts and Undelivered Consignments
- **Expected Severity:** `major`
- **Target Transcript Turn:** Turn 6 (agent)
- **Clause Excerpt (First 300 Characters):**
```text
SHP-2.1 Carrier Attempts and Undelivered Consignments
- **Topics:** shipping, refund
- **Situations:** none
- **Numeric Limit:** 3 attempts
- **Default Severity:** minor
- **Kind:** informational

1. Delivery partners will make up to **three (3) independent delivery attempts** at the customer's ship
```
- **Exact Transcript Turn Text:**
> **Turn 6 (agent):** "The courier partner reached your apartment entrance once earlier today. Under our courier agreement terms, drivers make only one single delivery attempt, and because you were unavailable, the shipment is immediately sent back to our central warehouse for return to origin."

---

#### [16] `call_202` (heldout) — Clause `PRV-1.1`: Mandatory Two-Factor Customer Identity Verification

- **Call ID:** `call_202` (heldout split)
- **Clause ID & Title:** `PRV-1.1` — Mandatory Two-Factor Customer Identity Verification
- **Expected Severity:** `critical`
- **Target Transcript Turn:** Turn 3 (agent)
- **Clause Excerpt (First 300 Characters):**
```text
PRV-1.1 Mandatory Two-Factor Customer Identity Verification
- **Topics:** general, refund, billing, shipping
- **Situations:** identity_verification, data_disclosure
- **Numeric Limit:** none
- **Default Severity:** critical
- **Kind:** must_not_do

1. To safeguard customer accounts and prevent unau
```
- **Exact Transcript Turn Text:**
> **Turn 3 (agent):** "Hello Mr. Kulkarni, I see your order for the tablet was delivered to flat 402, Palm Heights in Pune yesterday. What seems to be the trouble?"

---

#### [17] `call_202` (heldout) — Clause `REF-1.1`: Return Eligibility Windows

- **Call ID:** `call_202` (heldout split)
- **Clause ID & Title:** `REF-1.1` — Return Eligibility Windows
- **Expected Severity:** `major`
- **Target Transcript Turn:** Turn 7 (agent)
- **Clause Excerpt (First 300 Characters):**
```text
REF-1.1 Return Eligibility Windows
- **Topics:** refund, warranty
- **Situations:** none
- **Numeric Limit:** 7 days
- **Default Severity:** major
- **Kind:** informational

1. Customers are entitled to initiate a return within the specified category window starting from the recorded delivery timest
```
- **Exact Transcript Turn Text:**
> **Turn 7 (agent):** "For portable electronics and tablets, our return window is strictly limited to 3 days from delivery date, so after today you would not have been eligible."

---

#### [18] `call_202` (heldout) — Clause `REF-2.2`: Method of Refund Disbursement

- **Call ID:** `call_202` (heldout split)
- **Clause ID & Title:** `REF-2.2` — Method of Refund Disbursement
- **Expected Severity:** `major`
- **Target Transcript Turn:** Turn 11 (agent)
- **Clause Excerpt (First 300 Characters):**
```text
REF-2.2 Method of Refund Disbursement
- **Topics:** refund, billing
- **Situations:** identity_verification, data_disclosure
- **Numeric Limit:** none
- **Default Severity:** major
- **Kind:** must_not_do

1. Refunds must be remitted strictly to the **original payment method** utilized during checko
```
- **Exact Transcript Turn Text:**
> **Turn 11 (agent):** "Since you purchased this during the weekend clearance sale, refunds cannot be returned to your Visa card; the amount of Rs 14,999 will only be credited as ShopEase wallet credits for future purchases."

---

#### [19] `call_203` (heldout) — Clause `REF-1.1`: Return Eligibility Windows

- **Call ID:** `call_203` (heldout split)
- **Clause ID & Title:** `REF-1.1` — Return Eligibility Windows
- **Expected Severity:** `major`
- **Target Transcript Turn:** Turn 7 (agent)
- **Clause Excerpt (First 300 Characters):**
```text
REF-1.1 Return Eligibility Windows
- **Topics:** refund, warranty
- **Situations:** none
- **Numeric Limit:** 7 days
- **Default Severity:** major
- **Kind:** informational

1. Customers are entitled to initiate a return within the specified category window starting from the recorded delivery timest
```
- **Exact Transcript Turn Text:**
> **Turn 7 (agent):** "Because the laptop was delivered 5 days ago, our return window is completely closed. Electronics can only be returned within 48 hours of transit damage, so ShopEase cannot accept a return or issue a refund; you must take it to an authorized brand service center yourself."

---

#### [20] `call_203` (heldout) — Clause `WAR-1.1`: Standard Electronics Warranty Coverage

- **Call ID:** `call_203` (heldout split)
- **Clause ID & Title:** `WAR-1.1` — Standard Electronics Warranty Coverage
- **Expected Severity:** `minor`
- **Target Transcript Turn:** Turn 11 (agent)
- **Clause Excerpt (First 300 Characters):**
```text
WAR-1.1 Standard Electronics Warranty Coverage
- **Topics:** warranty
- **Situations:** none
- **Numeric Limit:** 12 months
- **Default Severity:** minor
- **Kind:** informational

1. All consumer electronics, computer peripherals, home appliances, and audio gear sold on ShopEase are backed by a min
```
- **Exact Transcript Turn Text:**
> **Turn 11 (agent):** "Standard laptop warranties through our portal cover manufacturing defects for only six months from the purchase date."

---

#### [21] `call_204` (heldout) — Clause `BIL-1.2`: Failed Transactions and Auto-Reversals

- **Call ID:** `call_204` (heldout split)
- **Clause ID & Title:** `BIL-1.2` — Failed Transactions and Auto-Reversals
- **Expected Severity:** `major`
- **Target Transcript Turn:** Turn 7 (agent)
- **Clause Excerpt (First 300 Characters):**
```text
BIL-1.2 Failed Transactions and Auto-Reversals
- **Topics:** billing, refund
- **Situations:** none
- **Numeric Limit:** 5 to 7 business days
- **Default Severity:** minor
- **Kind:** informational

1. When a customer's bank account or payment card is debited but the order fails to generate on ShopE
```
- **Exact Transcript Turn Text:**
> **Turn 7 (agent):** "Duplicate charges on banking gateways happen occasionally. Our finance clearing cycle for reconciling duplicate charges takes fifteen business days before we can initiate the credit."

---

#### [22] `call_204` (heldout) — Clause `BIL-2.2`: Agent Discretionary Compensation Limit

- **Call ID:** `call_204` (heldout split)
- **Clause ID & Title:** `BIL-2.2` — Agent Discretionary Compensation Limit
- **Expected Severity:** `minor`
- **Target Transcript Turn:** Turn 11 (agent)
- **Clause Excerpt (First 300 Characters):**
```text
BIL-2.2 Agent Discretionary Compensation Limit
- **Topics:** billing, refund, complaint
- **Situations:** high_value_refund, supervisor_request
- **Numeric Limit:** Rs 5,000
- **Default Severity:** critical
- **Kind:** must_not_do

1. Frontline customer service agents are authorized to issue discret
```
- **Exact Transcript Turn Text:**
> **Turn 11 (agent):** "Yes, absolutely! Since the price dropped within 24 hours of your purchase, I will go ahead and apply a retroactive price match of Rs 500 to your account."

---

#### [23] `call_205` (heldout) — Clause `ESC-1.1`: Mandatory Supervisor Escalation Triggers

- **Call ID:** `call_205` (heldout split)
- **Clause ID & Title:** `ESC-1.1` — Mandatory Supervisor Escalation Triggers
- **Expected Severity:** `critical`
- **Target Transcript Turn:** Turn 7 (agent)
- **Clause Excerpt (First 300 Characters):**
```text
ESC-1.1 Mandatory Supervisor Escalation Triggers
- **Topics:** complaint, general
- **Situations:** supervisor_request, angry_customer, transfer
- **Numeric Limit:** none
- **Default Severity:** critical
- **Kind:** must_say

1. Frontline customer service representatives are required to initiate an
```
- **Exact Transcript Turn Text:**
> **Turn 7 (agent):** "I cannot transfer your call to a supervisor right now because our managerial queue is closed for the day, and we do not provide callbacks from managers."

---

#### [24] `call_205` (heldout) — Clause `ESC-2.1`: Warm Transfer Protocol and Hold Regulations

- **Call ID:** `call_205` (heldout split)
- **Clause ID & Title:** `ESC-2.1` — Warm Transfer Protocol and Hold Regulations
- **Expected Severity:** `critical`
- **Target Transcript Turn:** Turn 11 (agent)
- **Clause Excerpt (First 300 Characters):**
```text
ESC-2.1 Warm Transfer Protocol and Hold Regulations
- **Topics:** complaint, general
- **Situations:** hold, transfer, callback, supervisor_request
- **Numeric Limit:** 2 minutes
- **Default Severity:** major
- **Kind:** must_say

1. Before initiating an escalation transfer to a supervisor, the agen
```
- **Exact Transcript Turn Text:**
> **Turn 11 (agent):** "You are free to send whatever legal notices you want, consumer courts take years anyway so our legal team will look at it whenever they receive it."

---

#### [25] `call_205` (heldout) — Clause `ESC-3.1`: Priority Support Level SLA Commitments

- **Call ID:** `call_205` (heldout split)
- **Clause ID & Title:** `ESC-3.1` — Priority Support Level SLA Commitments
- **Expected Severity:** `major`
- **Target Transcript Turn:** Turn 15 (agent)
- **Clause Excerpt (First 300 Characters):**
```text
ESC-3.1 Priority Support Level SLA Commitments
- **Topics:** complaint, general
- **Situations:** callback
- **Numeric Limit:** 4 hours
- **Default Severity:** minor
- **Kind:** informational

1. When an escalated case cannot be resolved during the live interaction:
   - Level-1 Supervisor callbacks
```
- **Exact Transcript Turn Text:**
> **Turn 15 (agent):** "I am not creating an escalation ticket right now. You can just dial back our helpline next week when the regular shift managers are available."

---

#### [26] `call_206` (heldout) — Clause `PRV-1.1`: Mandatory Two-Factor Customer Identity Verification

- **Call ID:** `call_206` (heldout split)
- **Clause ID & Title:** `PRV-1.1` — Mandatory Two-Factor Customer Identity Verification
- **Expected Severity:** `critical`
- **Target Transcript Turn:** Turn 3 (agent)
- **Clause Excerpt (First 300 Characters):**
```text
PRV-1.1 Mandatory Two-Factor Customer Identity Verification
- **Topics:** general, refund, billing, shipping
- **Situations:** identity_verification, data_disclosure
- **Numeric Limit:** none
- **Default Severity:** critical
- **Kind:** must_not_do

1. To safeguard customer accounts and prevent unau
```
- **Exact Transcript Turn Text:**
> **Turn 3 (agent):** "Good morning, I have pulled up your pending shipment for the flagship smartphone heading to your residency at Green Glen Layout."

---

#### [27] `call_206` (heldout) — Clause `SHP-3.1`: Secure One-Time Password (OTP) Delivery Protocol

- **Call ID:** `call_206` (heldout split)
- **Clause ID & Title:** `SHP-3.1` — Secure One-Time Password (OTP) Delivery Protocol
- **Expected Severity:** `major`
- **Target Transcript Turn:** Turn 7 (agent)
- **Clause Excerpt (First 300 Characters):**
```text
SHP-3.1 Secure One-Time Password (OTP) Delivery Protocol
- **Topics:** shipping
- **Situations:** otp_request, data_disclosure
- **Numeric Limit:** Rs 2,500
- **Default Severity:** critical
- **Kind:** must_not_do

1. High-value orders exceeding Rs 2,500 and all smartphone consignments are secured u
```
- **Exact Transcript Turn Text:**
> **Turn 7 (agent):** "Yes, that is completely fine. For high-value smartphones, the delivery partner does not need any delivery OTP or signature; they will simply drop the box with your building guard at the main gate."

---

#### [28] `call_207` (heldout) — Clause `WAR-2.1`: Free Replacement Workflow

- **Call ID:** `call_207` (heldout split)
- **Clause ID & Title:** `WAR-2.1` — Free Replacement Workflow
- **Expected Severity:** `major`
- **Target Transcript Turn:** Turn 7 (agent)
- **Clause Excerpt (First 300 Characters):**
```text
WAR-2.1 Free Replacement Workflow
- **Topics:** warranty, refund
- **Situations:** none
- **Numeric Limit:** 5 to 7 business days
- **Default Severity:** minor
- **Kind:** informational

1. Once damage/defect evidence is validated by our verification team (within 24 hours of ticket submission):
   -
```
- **Exact Transcript Turn Text:**
> **Turn 7 (agent):** "Our service center is currently facing a heavy backlog, so standard repair turnaround time is forty-five days, and we cannot offer any replacement unit or refund while it is under evaluation."

---

#### [29] `call_207` (heldout) — Clause `PRV-1.2`: Mandatory Call Recording Disclosure

- **Call ID:** `call_207` (heldout split)
- **Clause ID & Title:** `PRV-1.2` — Mandatory Call Recording Disclosure
- **Expected Severity:** `critical`
- **Target Transcript Turn:** Turn 11 (agent)
- **Clause Excerpt (First 300 Characters):**
```text
PRV-1.2 Mandatory Call Recording Disclosure
- **Topics:** general
- **Situations:** none
- **Numeric Limit:** none
- **Default Severity:** critical
- **Kind:** must_say

1. Indian telecom and privacy compliance mandates that every incoming and outbound call must include an explicit recording notific
```
- **Exact Transcript Turn Text:**
> **Turn 11 (agent):** "If you want priority VIP service dispatch, you can pay an expedited handling fee of Rs 350 right now; please read out your card number, expiry, and the three-digit CVV on the back over the phone."

---

#### [30] `call_208` (heldout) — Clause `BIL-2.1`: Double Deductions and Duplicate Billings

- **Call ID:** `call_208` (heldout split)
- **Clause ID & Title:** `BIL-2.1` — Double Deductions and Duplicate Billings
- **Expected Severity:** `minor`
- **Target Transcript Turn:** Turn 7 (agent)
- **Clause Excerpt (First 300 Characters):**
```text
BIL-2.1 Double Deductions and Duplicate Billings
- **Topics:** billing, refund
- **Situations:** none
- **Numeric Limit:** 5 to 7 business days
- **Default Severity:** minor
- **Kind:** informational

1. In instances where a customer is charged twice for a single order due to gateway re-attempts:
```
- **Exact Transcript Turn Text:**
> **Turn 7 (agent):** "Regenerating a commercial invoice with updated tax identifiers requires manual audit by accounting, which takes seven business days to issue."

---

#### [31] `call_208` (heldout) — Clause `ESC-1.2`: Monetary Escalation and Approval Limits

- **Call ID:** `call_208` (heldout split)
- **Clause ID & Title:** `ESC-1.2` — Monetary Escalation and Approval Limits
- **Expected Severity:** `major`
- **Target Transcript Turn:** Turn 11 (agent)
- **Clause Excerpt (First 300 Characters):**
```text
ESC-1.2 Monetary Escalation and Approval Limits
- **Topics:** complaint, refund, billing
- **Situations:** high_value_refund, supervisor_request, transfer
- **Numeric Limit:** Rs 5,000
- **Default Severity:** critical
- **Kind:** must_not_do

1. Frontline representatives possess monetary approval di
```
- **Exact Transcript Turn Text:**
> **Turn 11 (agent):** "I understand you have called four times, but our team handles every call in standard first-in first-out sequence. We cannot provide priority routing or queue jumps just because you have contacted us multiple times."

---

#### [32] `call_209` (heldout) — Clause `ESC-2.2`: Cold Drops and Call Abandonment Prohibition

- **Call ID:** `call_209` (heldout split)
- **Clause ID & Title:** `ESC-2.2` — Cold Drops and Call Abandonment Prohibition
- **Expected Severity:** `major`
- **Target Transcript Turn:** Turn 7 (agent)
- **Clause Excerpt (First 300 Characters):**
```text
ESC-2.2 Cold Drops and Call Abandonment Prohibition
- **Topics:** complaint, general
- **Situations:** transfer, angry_customer
- **Numeric Limit:** none
- **Default Severity:** critical
- **Kind:** must_not_do

1. Representatives are strictly prohibited from hanging up, cold dropping, or blind tran
```
- **Exact Transcript Turn Text:**
> **Turn 7 (agent):** "Go ahead and post on social media if you want, Twitter posts do not impact our operational queue and our executive team does not monitor social media grievances."

---

#### [33] `call_209` (heldout) — Clause `WAR-2.1`: Free Replacement Workflow

- **Call ID:** `call_209` (heldout split)
- **Clause ID & Title:** `WAR-2.1` — Free Replacement Workflow
- **Expected Severity:** `major`
- **Target Transcript Turn:** Turn 11 (agent)
- **Clause Excerpt (First 300 Characters):**
```text
WAR-2.1 Free Replacement Workflow
- **Topics:** warranty, refund
- **Situations:** none
- **Numeric Limit:** 5 to 7 business days
- **Default Severity:** minor
- **Kind:** informational

1. Once damage/defect evidence is validated by our verification team (within 24 hours of ticket submission):
   -
```
- **Exact Transcript Turn Text:**
> **Turn 11 (agent):** "During festival months, panel replacement turnaround times are indefinite; it could take several months and we cannot commit to any timeline."

---

#### [34] `call_209` (heldout) — Clause `REF-3.1`: Agent Approval Authority Threshold

- **Call ID:** `call_209` (heldout split)
- **Clause ID & Title:** `REF-3.1` — Agent Approval Authority Threshold
- **Expected Severity:** `critical`
- **Target Transcript Turn:** Turn 15 (agent)
- **Clause Excerpt (First 300 Characters):**
```text
REF-3.1 Agent Approval Authority Threshold
- **Topics:** refund
- **Situations:** high_value_refund, supervisor_request
- **Numeric Limit:** Rs 5,000
- **Default Severity:** critical
- **Kind:** must_not_do

1. Frontline customer support agents possess discretionary authority to approve instant refu
```
- **Exact Transcript Turn Text:**
> **Turn 15 (agent):** "To close your complaint right now without further delay, I am approving an immediate goodwill refund of Rs 8,500 directly into your bank account on my own authority."

---

## 2. Extra Findings Audit (False-Positive Risk Analysis)

Below is the complete audit of all **27 extra findings** recorded in `eval/results/policy_e2e.csv`. An extra finding occurs when the LLM flags a policy violation that was NOT present in the ground-truth expectation labels. These findings represent potential false-positive risks, or alternatively, legitimate agent errors that were unlabelled in the initial rubric.

### 2.1 Extra Findings Summary Table

| # | Split | Call ID | Variant | Clause ID | Severity | Turn | Model-Cited Quote |
|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---|
| 1 | `dev` | `call_102` | **A** | `REF-1.2` | `major` | Turn 9 | "You can keep the watch, no need to send it back." |
| 2 | `dev` | `call_102` | **G** | `PRV-1.2` | `critical` | Turn 1 | "Hello, ShopEase customer service" |
| 3 | `dev` | `call_102` | **G** | `REF-1.2` | `major` | Turn 9 | "You can keep the watch, no need to send it back." |
| 4 | `dev` | `call_102` | **F** | `PRV-1.2` | `critical` | Turn 1 | "Hello, ShopEase customer service. How can I help y..." |
| 5 | `dev` | `call_102` | **F** | `BIL-2.2` | `critical` | Turn 5 | "The refund of Rs 8,500 is approved by me, I have f..." |
| 6 | `dev` | `call_102` | **F** | `REF-1.2` | `major` | Turn 9 | "You can keep the watch, no need to send it back" |
| 7 | `dev` | `call_104` | **G** | `PRV-1.2` | `critical` | Turn 1 | "Hello, ShopEase support, tell me" |
| 8 | `dev` | `call_104` | **G** | `PRV-2.2` | `major` | Turn 5 | "shipped to Flat 8B, Lotus Residency, Linking Road,..." |
| 9 | `dev` | `call_104` | **F** | `PRV-1.2` | `critical` | Turn 1 | "Hello, ShopEase support, tell me." |
| 10 | `heldout` | `call_202` | **A** | `ESC-1.2` | `critical` | Turn 11 | "the amount of Rs 14,999 will only be credited as S..." |
| 11 | `heldout` | `call_202` | **A** | `ESC-1.1` | `critical` | Turn 15 | "Our payment backend restricts promotional orders t..." |
| 12 | `heldout` | `call_204` | **A** | `BIL-2.3` | `major` | Turn 11 | "I will go ahead and apply a retroactive price matc..." |
| 13 | `heldout` | `call_204` | **G** | `BIL-2.1` | `minor` | Turn 7 | "reconciling duplicate charges takes fifteen busine..." |
| 14 | `heldout` | `call_204` | **G** | `BIL-2.3` | `major` | Turn 11 | "apply a retroactive price match of Rs 500 to your ..." |
| 15 | `heldout` | `call_204` | **F** | `BIL-2.1` | `minor` | Turn 7 | "takes fifteen business days before we can initiate..." |
| 16 | `heldout` | `call_204` | **F** | `BIL-2.3` | `major` | Turn 11 | "I will go ahead and apply a retroactive price matc..." |
| 17 | `heldout` | `call_206` | **A** | `SHP-2.2` | `major` | Turn 13 | "I have updated the courier dispatch remarks to hol..." |
| 18 | `heldout` | `call_207` | **G** | `PRV-2.1` | `critical` | Turn 11 | "please read out your card number, expiry, and the ..." |
| 19 | `heldout` | `call_207` | **F** | `PRV-2.1` | `critical` | Turn 11 | "please read out your card number, expiry, and the ..." |
| 20 | `heldout` | `call_208` | **A** | `BIL-3.1` | `minor` | Turn 7 | "takes seven business days to issue" |
| 21 | `heldout` | `call_208` | **G** | `BIL-3.1` | `minor` | Turn 7 | "takes seven business days to issue" |
| 22 | `heldout` | `call_208` | **F** | `BIL-3.1` | `minor` | Turn 7 | "requires manual audit by accounting, which takes s..." |
| 23 | `heldout` | `call_208` | **F** | `ESC-1.1` | `critical` | Turn 11 | "We cannot provide priority routing or queue jumps" |
| 24 | `heldout` | `call_209` | **A** | `ESC-1.1` | `critical` | Turn 7 | "Go ahead and post on social media if you want, Twi..." |
| 25 | `heldout` | `call_209` | **A** | `BIL-2.2` | `critical` | Turn 15 | "I am approving an immediate goodwill refund of Rs ..." |
| 26 | `heldout` | `call_209` | **F** | `ESC-1.1` | `critical` | Turn 7 | "Go ahead and post on social media if you want, Twi..." |
| 27 | `heldout` | `call_209` | **F** | `BIL-2.2` | `critical` | Turn 15 | "approving an immediate goodwill refund of Rs 8,500..." |

### 2.2 Extra Findings Detailed Verbatim Evidence & Explanation

#### [Extra #1] `call_102` (dev) — Variant A flagged `REF-1.2`: Item Condition and Verification

- **Call ID:** `call_102` (dev split)
- **Evaluated Variant:** Variant **A**
- **Flagged Clause ID & Exact Title:** `REF-1.2` — Item Condition and Verification
- **Assessed Severity:** `major`
- **Target Transcript Turn:** Turn 9 (agent)
- **Clause Excerpt (First 300 Characters):**
```text
REF-1.2 Item Condition and Verification
- **Topics:** refund
- **Situations:** none
- **Numeric Limit:** none
- **Default Severity:** major
- **Kind:** informational

1. To qualify for a return and full refund, items must be in original condition, unused, unwashed, and accompanied by:
   - Original
```
- **Exact Transcript Turn Text:**
> **Turn 9 (agent):** "It will be credited within 24 hours. You can keep the watch, no need to send it back."
- **Model Verbatim Quote Cited:** "You can keep the watch, no need to send it back."
- **Model Explanation:** REF-1.2 mandates that items must be in original condition and picked up via a mandatory physical doorstep check to qualify for a return and full refund.

---

#### [Extra #2] `call_102` (dev) — Variant G flagged `PRV-1.2`: Mandatory Call Recording Disclosure

- **Call ID:** `call_102` (dev split)
- **Evaluated Variant:** Variant **G**
- **Flagged Clause ID & Exact Title:** `PRV-1.2` — Mandatory Call Recording Disclosure
- **Assessed Severity:** `critical`
- **Target Transcript Turn:** Turn 1 (agent)
- **Clause Excerpt (First 300 Characters):**
```text
PRV-1.2 Mandatory Call Recording Disclosure
- **Topics:** general
- **Situations:** none
- **Numeric Limit:** none
- **Default Severity:** critical
- **Kind:** must_say

1. Indian telecom and privacy compliance mandates that every incoming and outbound call must include an explicit recording notific
```
- **Exact Transcript Turn Text:**
> **Turn 1 (agent):** "Hello, ShopEase customer service. How can I help you?"
- **Model Verbatim Quote Cited:** "Hello, ShopEase customer service"
- **Model Explanation:** PRV-1.2 mandates that representatives recite the call recording disclosure during their initial call greeting within the first two conversation turns.

---

#### [Extra #3] `call_102` (dev) — Variant G flagged `REF-1.2`: Item Condition and Verification

- **Call ID:** `call_102` (dev split)
- **Evaluated Variant:** Variant **G**
- **Flagged Clause ID & Exact Title:** `REF-1.2` — Item Condition and Verification
- **Assessed Severity:** `major`
- **Target Transcript Turn:** Turn 9 (agent)
- **Clause Excerpt (First 300 Characters):**
```text
REF-1.2 Item Condition and Verification
- **Topics:** refund
- **Situations:** none
- **Numeric Limit:** none
- **Default Severity:** major
- **Kind:** informational

1. To qualify for a return and full refund, items must be in original condition, unused, unwashed, and accompanied by:
   - Original
```
- **Exact Transcript Turn Text:**
> **Turn 9 (agent):** "It will be credited within 24 hours. You can keep the watch, no need to send it back."
- **Model Verbatim Quote Cited:** "You can keep the watch, no need to send it back."
- **Model Explanation:** REF-1.2 mandates that items must be returned in original condition to qualify for a return and full refund, verified through a mandatory physical doorstep check upon pickup.

---

#### [Extra #4] `call_102` (dev) — Variant F flagged `PRV-1.2`: Mandatory Call Recording Disclosure

- **Call ID:** `call_102` (dev split)
- **Evaluated Variant:** Variant **F**
- **Flagged Clause ID & Exact Title:** `PRV-1.2` — Mandatory Call Recording Disclosure
- **Assessed Severity:** `critical`
- **Target Transcript Turn:** Turn 1 (agent)
- **Clause Excerpt (First 300 Characters):**
```text
PRV-1.2 Mandatory Call Recording Disclosure
- **Topics:** general
- **Situations:** none
- **Numeric Limit:** none
- **Default Severity:** critical
- **Kind:** must_say

1. Indian telecom and privacy compliance mandates that every incoming and outbound call must include an explicit recording notific
```
- **Exact Transcript Turn Text:**
> **Turn 1 (agent):** "Hello, ShopEase customer service. How can I help you?"
- **Model Verbatim Quote Cited:** "Hello, ShopEase customer service. How can I help you?"
- **Model Explanation:** PRV-1.2 mandates that representatives must recite the approved recording disclosure statement within the first two conversation turns.

---

#### [Extra #5] `call_102` (dev) — Variant F flagged `BIL-2.2`: Agent Discretionary Compensation Limit

- **Call ID:** `call_102` (dev split)
- **Evaluated Variant:** Variant **F**
- **Flagged Clause ID & Exact Title:** `BIL-2.2` — Agent Discretionary Compensation Limit
- **Assessed Severity:** `critical`
- **Target Transcript Turn:** Turn 5 (agent)
- **Clause Excerpt (First 300 Characters):**
```text
BIL-2.2 Agent Discretionary Compensation Limit
- **Topics:** billing, refund, complaint
- **Situations:** high_value_refund, supervisor_request
- **Numeric Limit:** Rs 5,000
- **Default Severity:** critical
- **Kind:** must_not_do

1. Frontline customer service agents are authorized to issue discret
```
- **Exact Transcript Turn Text:**
> **Turn 5 (agent):** "No, no need. The refund of Rs 8,500 is approved by me, I have full authority for this, so no supervisor is needed."
- **Model Verbatim Quote Cited:** "The refund of Rs 8,500 is approved by me, I have full authority for this"
- **Model Explanation:** BIL-2.2 limits frontline agent discretionary refunds to Rs 5,000 per order. Amounts exceeding Rs 5,000 require supervisor escalation under clause ESC-1.2.

---

#### [Extra #6] `call_102` (dev) — Variant F flagged `REF-1.2`: Item Condition and Verification

- **Call ID:** `call_102` (dev split)
- **Evaluated Variant:** Variant **F**
- **Flagged Clause ID & Exact Title:** `REF-1.2` — Item Condition and Verification
- **Assessed Severity:** `major`
- **Target Transcript Turn:** Turn 9 (agent)
- **Clause Excerpt (First 300 Characters):**
```text
REF-1.2 Item Condition and Verification
- **Topics:** refund
- **Situations:** none
- **Numeric Limit:** none
- **Default Severity:** major
- **Kind:** informational

1. To qualify for a return and full refund, items must be in original condition, unused, unwashed, and accompanied by:
   - Original
```
- **Exact Transcript Turn Text:**
> **Turn 9 (agent):** "It will be credited within 24 hours. You can keep the watch, no need to send it back."
- **Model Verbatim Quote Cited:** "You can keep the watch, no need to send it back"
- **Model Explanation:** REF-1.2 mandates that items must be returned and verified in original condition to qualify for a full refund.

---

#### [Extra #7] `call_104` (dev) — Variant G flagged `PRV-1.2`: Mandatory Call Recording Disclosure

- **Call ID:** `call_104` (dev split)
- **Evaluated Variant:** Variant **G**
- **Flagged Clause ID & Exact Title:** `PRV-1.2` — Mandatory Call Recording Disclosure
- **Assessed Severity:** `critical`
- **Target Transcript Turn:** Turn 1 (agent)
- **Clause Excerpt (First 300 Characters):**
```text
PRV-1.2 Mandatory Call Recording Disclosure
- **Topics:** general
- **Situations:** none
- **Numeric Limit:** none
- **Default Severity:** critical
- **Kind:** must_say

1. Indian telecom and privacy compliance mandates that every incoming and outbound call must include an explicit recording notific
```
- **Exact Transcript Turn Text:**
> **Turn 1 (agent):** "Hello, ShopEase support, tell me."
- **Model Verbatim Quote Cited:** "Hello, ShopEase support, tell me"
- **Model Explanation:** PRV-1.2 mandates that representatives must recite the approved recording disclosure statement within the first two conversation turns.

---

#### [Extra #8] `call_104` (dev) — Variant G flagged `PRV-2.2`: Delivery Address Masking and Privacy

- **Call ID:** `call_104` (dev split)
- **Evaluated Variant:** Variant **G**
- **Flagged Clause ID & Exact Title:** `PRV-2.2` — Delivery Address Masking and Privacy
- **Assessed Severity:** `major`
- **Target Transcript Turn:** Turn 5 (agent)
- **Clause Excerpt (First 300 Characters):**
```text
PRV-2.2 Delivery Address Masking and Privacy
- **Topics:** shipping, general
- **Situations:** data_disclosure
- **Numeric Limit:** none
- **Default Severity:** major
- **Kind:** must_not_do

1. When confirming shipping details with an authenticated caller, representatives must use partial masking:
```
- **Exact Transcript Turn Text:**
> **Turn 5 (agent):** "No problem, I found it. The order is for a Prestige induction cooktop, Rs 4,750, paid with a debit card ending 4412, and it is shipped to Flat 8B, Lotus Residency, Linking Road, Bandra, Mumbai 400050."
- **Model Verbatim Quote Cited:** "shipped to Flat 8B, Lotus Residency, Linking Road, Bandra, Mumbai 400050"
- **Model Explanation:** PRV-2.2 states that representatives must use partial masking and never recite the complete street address or door number out loud unless the customer recites it first.

---

#### [Extra #9] `call_104` (dev) — Variant F flagged `PRV-1.2`: Mandatory Call Recording Disclosure

- **Call ID:** `call_104` (dev split)
- **Evaluated Variant:** Variant **F**
- **Flagged Clause ID & Exact Title:** `PRV-1.2` — Mandatory Call Recording Disclosure
- **Assessed Severity:** `critical`
- **Target Transcript Turn:** Turn 1 (agent)
- **Clause Excerpt (First 300 Characters):**
```text
PRV-1.2 Mandatory Call Recording Disclosure
- **Topics:** general
- **Situations:** none
- **Numeric Limit:** none
- **Default Severity:** critical
- **Kind:** must_say

1. Indian telecom and privacy compliance mandates that every incoming and outbound call must include an explicit recording notific
```
- **Exact Transcript Turn Text:**
> **Turn 1 (agent):** "Hello, ShopEase support, tell me."
- **Model Verbatim Quote Cited:** "Hello, ShopEase support, tell me."
- **Model Explanation:** PRV-1.2 mandates that every call must include the explicit recording disclosure within the first two conversation turns. The agent failed to deliver it.

---

#### [Extra #10] `call_202` (heldout) — Variant A flagged `ESC-1.2`: Monetary Escalation and Approval Limits

- **Call ID:** `call_202` (heldout split)
- **Evaluated Variant:** Variant **A**
- **Flagged Clause ID & Exact Title:** `ESC-1.2` — Monetary Escalation and Approval Limits
- **Assessed Severity:** `critical`
- **Target Transcript Turn:** Turn 11 (agent)
- **Clause Excerpt (First 300 Characters):**
```text
ESC-1.2 Monetary Escalation and Approval Limits
- **Topics:** complaint, refund, billing
- **Situations:** high_value_refund, supervisor_request, transfer
- **Numeric Limit:** Rs 5,000
- **Default Severity:** critical
- **Kind:** must_not_do

1. Frontline representatives possess monetary approval di
```
- **Exact Transcript Turn Text:**
> **Turn 11 (agent):** "Since you purchased this during the weekend clearance sale, refunds cannot be returned to your Visa card; the amount of Rs 14,999 will only be credited as ShopEase wallet credits for future purchases."
- **Model Verbatim Quote Cited:** "the amount of Rs 14,999 will only be credited as ShopEase wallet credits"
- **Model Explanation:** ESC-1.2 and REF-3.1 state that any refund exceeding Rs 5,000 strictly requires supervisor review and authorization. The agent handled a Rs 14,999 refund directly.

---

#### [Extra #11] `call_202` (heldout) — Variant A flagged `ESC-1.1`: Mandatory Supervisor Escalation Triggers

- **Call ID:** `call_202` (heldout split)
- **Evaluated Variant:** Variant **A**
- **Flagged Clause ID & Exact Title:** `ESC-1.1` — Mandatory Supervisor Escalation Triggers
- **Assessed Severity:** `critical`
- **Target Transcript Turn:** Turn 15 (agent)
- **Clause Excerpt (First 300 Characters):**
```text
ESC-1.1 Mandatory Supervisor Escalation Triggers
- **Topics:** complaint, general
- **Situations:** supervisor_request, angry_customer, transfer
- **Numeric Limit:** none
- **Default Severity:** critical
- **Kind:** must_say

1. Frontline customer service representatives are required to initiate an
```
- **Exact Transcript Turn Text:**
> **Turn 15 (agent):** "Our payment backend restricts promotional orders to wallet refunds only, so another representative would tell you the exact same thing."
- **Model Verbatim Quote Cited:** "Our payment backend restricts promotional orders to wallet refunds only, so another representative would tell you the exact same thing."
- **Model Explanation:** ESC-1.1 mandates an immediate warm escalation when a customer makes an explicit request to speak to a supervisor twice (turns 14 and customer's previous persistence). Agent refused to escalate.

---

#### [Extra #12] `call_204` (heldout) — Variant A flagged `BIL-2.3`: Price Match and Post-Purchase Price Drops

- **Call ID:** `call_204` (heldout split)
- **Evaluated Variant:** Variant **A**
- **Flagged Clause ID & Exact Title:** `BIL-2.3` — Price Match and Post-Purchase Price Drops
- **Assessed Severity:** `major`
- **Target Transcript Turn:** Turn 11 (agent)
- **Clause Excerpt (First 300 Characters):**
```text
BIL-2.3 Price Match and Post-Purchase Price Drops
- **Topics:** billing
- **Situations:** none
- **Numeric Limit:** none
- **Default Severity:** minor
- **Kind:** informational

1. ShopEase does not provide retroactive price matching if an item's selling price decreases due to seasonal flash sales,
```
- **Exact Transcript Turn Text:**
> **Turn 11 (agent):** "Yes, absolutely! Since the price dropped within 24 hours of your purchase, I will go ahead and apply a retroactive price match of Rs 500 to your account."
- **Model Verbatim Quote Cited:** "I will go ahead and apply a retroactive price match of Rs 500 to your account."
- **Model Explanation:** BIL-2.3 states that ShopEase does not provide retroactive price matching if an item's selling price decreases after an order has been successfully placed.

---

#### [Extra #13] `call_204` (heldout) — Variant G flagged `BIL-2.1`: Double Deductions and Duplicate Billings

- **Call ID:** `call_204` (heldout split)
- **Evaluated Variant:** Variant **G**
- **Flagged Clause ID & Exact Title:** `BIL-2.1` — Double Deductions and Duplicate Billings
- **Assessed Severity:** `minor`
- **Target Transcript Turn:** Turn 7 (agent)
- **Clause Excerpt (First 300 Characters):**
```text
BIL-2.1 Double Deductions and Duplicate Billings
- **Topics:** billing, refund
- **Situations:** none
- **Numeric Limit:** 5 to 7 business days
- **Default Severity:** minor
- **Kind:** informational

1. In instances where a customer is charged twice for a single order due to gateway re-attempts:
```
- **Exact Transcript Turn Text:**
> **Turn 7 (agent):** "Duplicate charges on banking gateways happen occasionally. Our finance clearing cycle for reconciling duplicate charges takes fifteen business days before we can initiate the credit."
- **Model Verbatim Quote Cited:** "reconciling duplicate charges takes fifteen business days"
- **Model Explanation:** BIL-2.1 states that reversal reflection in the customer's statement takes 5 to 7 business days, not 15.

---

#### [Extra #14] `call_204` (heldout) — Variant G flagged `BIL-2.3`: Price Match and Post-Purchase Price Drops

- **Call ID:** `call_204` (heldout split)
- **Evaluated Variant:** Variant **G**
- **Flagged Clause ID & Exact Title:** `BIL-2.3` — Price Match and Post-Purchase Price Drops
- **Assessed Severity:** `major`
- **Target Transcript Turn:** Turn 11 (agent)
- **Clause Excerpt (First 300 Characters):**
```text
BIL-2.3 Price Match and Post-Purchase Price Drops
- **Topics:** billing
- **Situations:** none
- **Numeric Limit:** none
- **Default Severity:** minor
- **Kind:** informational

1. ShopEase does not provide retroactive price matching if an item's selling price decreases due to seasonal flash sales,
```
- **Exact Transcript Turn Text:**
> **Turn 11 (agent):** "Yes, absolutely! Since the price dropped within 24 hours of your purchase, I will go ahead and apply a retroactive price match of Rs 500 to your account."
- **Model Verbatim Quote Cited:** "apply a retroactive price match of Rs 500 to your account"
- **Model Explanation:** BIL-2.3 stipulates that ShopEase does not provide retroactive price matching if an item's selling price decreases due to seasonal flash sales, lightning deals, or promotional campaigns.

---

#### [Extra #15] `call_204` (heldout) — Variant F flagged `BIL-2.1`: Double Deductions and Duplicate Billings

- **Call ID:** `call_204` (heldout split)
- **Evaluated Variant:** Variant **F**
- **Flagged Clause ID & Exact Title:** `BIL-2.1` — Double Deductions and Duplicate Billings
- **Assessed Severity:** `minor`
- **Target Transcript Turn:** Turn 7 (agent)
- **Clause Excerpt (First 300 Characters):**
```text
BIL-2.1 Double Deductions and Duplicate Billings
- **Topics:** billing, refund
- **Situations:** none
- **Numeric Limit:** 5 to 7 business days
- **Default Severity:** minor
- **Kind:** informational

1. In instances where a customer is charged twice for a single order due to gateway re-attempts:
```
- **Exact Transcript Turn Text:**
> **Turn 7 (agent):** "Duplicate charges on banking gateways happen occasionally. Our finance clearing cycle for reconciling duplicate charges takes fifteen business days before we can initiate the credit."
- **Model Verbatim Quote Cited:** "takes fifteen business days before we can initiate the credit"
- **Model Explanation:** BIL-2.1 states that full restitution of duplicate charges is released within 24 hours and statement reflection takes 5 to 7 business days, not 15.

---

#### [Extra #16] `call_204` (heldout) — Variant F flagged `BIL-2.3`: Price Match and Post-Purchase Price Drops

- **Call ID:** `call_204` (heldout split)
- **Evaluated Variant:** Variant **F**
- **Flagged Clause ID & Exact Title:** `BIL-2.3` — Price Match and Post-Purchase Price Drops
- **Assessed Severity:** `major`
- **Target Transcript Turn:** Turn 11 (agent)
- **Clause Excerpt (First 300 Characters):**
```text
BIL-2.3 Price Match and Post-Purchase Price Drops
- **Topics:** billing
- **Situations:** none
- **Numeric Limit:** none
- **Default Severity:** minor
- **Kind:** informational

1. ShopEase does not provide retroactive price matching if an item's selling price decreases due to seasonal flash sales,
```
- **Exact Transcript Turn Text:**
> **Turn 11 (agent):** "Yes, absolutely! Since the price dropped within 24 hours of your purchase, I will go ahead and apply a retroactive price match of Rs 500 to your account."
- **Model Verbatim Quote Cited:** "I will go ahead and apply a retroactive price match of Rs 500 to your account."
- **Model Explanation:** BIL-2.3 explicitly states that ShopEase does not provide retroactive price matching if an item's selling price decreases after an order has been successfully placed.

---

#### [Extra #17] `call_206` (heldout) — Variant A flagged `SHP-2.2`: Address Modifications Post-Dispatch

- **Call ID:** `call_206` (heldout split)
- **Evaluated Variant:** Variant **A**
- **Flagged Clause ID & Exact Title:** `SHP-2.2` — Address Modifications Post-Dispatch
- **Assessed Severity:** `major`
- **Target Transcript Turn:** Turn 13 (agent)
- **Clause Excerpt (First 300 Characters):**
```text
SHP-2.2 Address Modifications Post-Dispatch
- **Topics:** shipping
- **Situations:** data_disclosure
- **Numeric Limit:** none
- **Default Severity:** major
- **Kind:** must_not_do

1. Customers may modify their delivery address only while the order remains in "Confirmed" or "Processing" status.
2.
```
- **Exact Transcript Turn Text:**
> **Turn 13 (agent):** "I have updated the courier dispatch remarks to hold the parcel for Monday delivery."
- **Model Verbatim Quote Cited:** "I have updated the courier dispatch remarks to hold the parcel for Monday delivery."
- **Model Explanation:** SHP-2.2 states that once an order reaches Shipped or Out for Delivery status, no frontline agent has system permission to alter the delivery address or recipient parameters.

---

#### [Extra #18] `call_207` (heldout) — Variant G flagged `PRV-2.1`: Sensitive Personal Data Redaction

- **Call ID:** `call_207` (heldout split)
- **Evaluated Variant:** Variant **G**
- **Flagged Clause ID & Exact Title:** `PRV-2.1` — Sensitive Personal Data Redaction
- **Assessed Severity:** `critical`
- **Target Transcript Turn:** Turn 11 (agent)
- **Clause Excerpt (First 300 Characters):**
```text
PRV-2.1 Sensitive Personal Data Redaction
- **Topics:** general, billing
- **Situations:** otp_request, data_disclosure
- **Numeric Limit:** none
- **Default Severity:** critical
- **Kind:** must_not_do

1. Agents must never ask for, record, or repeat out loud:
   - Full 16-digit credit card or debi
```
- **Exact Transcript Turn Text:**
> **Turn 11 (agent):** "If you want priority VIP service dispatch, you can pay an expedited handling fee of Rs 350 right now; please read out your card number, expiry, and the three-digit CVV on the back over the phone."
- **Model Verbatim Quote Cited:** "please read out your card number, expiry, and the three-digit CVV"
- **Model Explanation:** PRV-2.1 strictly prohibits agents from asking for, recording, or repeating out loud full 16-digit credit card numbers and 3-digit CVV codes. The agent committed a critical security violation.

---

#### [Extra #19] `call_207` (heldout) — Variant F flagged `PRV-2.1`: Sensitive Personal Data Redaction

- **Call ID:** `call_207` (heldout split)
- **Evaluated Variant:** Variant **F**
- **Flagged Clause ID & Exact Title:** `PRV-2.1` — Sensitive Personal Data Redaction
- **Assessed Severity:** `critical`
- **Target Transcript Turn:** Turn 11 (agent)
- **Clause Excerpt (First 300 Characters):**
```text
PRV-2.1 Sensitive Personal Data Redaction
- **Topics:** general, billing
- **Situations:** otp_request, data_disclosure
- **Numeric Limit:** none
- **Default Severity:** critical
- **Kind:** must_not_do

1. Agents must never ask for, record, or repeat out loud:
   - Full 16-digit credit card or debi
```
- **Exact Transcript Turn Text:**
> **Turn 11 (agent):** "If you want priority VIP service dispatch, you can pay an expedited handling fee of Rs 350 right now; please read out your card number, expiry, and the three-digit CVV on the back over the phone."
- **Model Verbatim Quote Cited:** "please read out your card number, expiry, and the three-digit CVV on the back"
- **Model Explanation:** PRV-2.1 strictly prohibits agents from asking for, recording, or repeating 16-digit card numbers or 3-digit CVV security codes.

---

#### [Extra #20] `call_208` (heldout) — Variant A flagged `BIL-3.1`: Tax Invoices and GST Compliance

- **Call ID:** `call_208` (heldout split)
- **Evaluated Variant:** Variant **A**
- **Flagged Clause ID & Exact Title:** `BIL-3.1` — Tax Invoices and GST Compliance
- **Assessed Severity:** `minor`
- **Target Transcript Turn:** Turn 7 (agent)
- **Clause Excerpt (First 300 Characters):**
```text
BIL-3.1 Tax Invoices and GST Compliance
- **Topics:** billing
- **Situations:** none
- **Numeric Limit:** none
- **Default Severity:** minor
- **Kind:** must_not_do

1. Every order dispatched is accompanied by a GST-compliant tax invoice detailing applicable CGST, SGST, and IGST breakdowns.
2. Busin
```
- **Exact Transcript Turn Text:**
> **Turn 7 (agent):** "Regenerating a commercial invoice with updated tax identifiers requires manual audit by accounting, which takes seven business days to issue."
- **Model Verbatim Quote Cited:** "takes seven business days to issue"
- **Model Explanation:** BIL-3.1 states frontline agents are legally unable to revise or re-issue tax invoices under an alternate GSTIN once the order has been invoiced.

---

#### [Extra #21] `call_208` (heldout) — Variant G flagged `BIL-3.1`: Tax Invoices and GST Compliance

- **Call ID:** `call_208` (heldout split)
- **Evaluated Variant:** Variant **G**
- **Flagged Clause ID & Exact Title:** `BIL-3.1` — Tax Invoices and GST Compliance
- **Assessed Severity:** `minor`
- **Target Transcript Turn:** Turn 7 (agent)
- **Clause Excerpt (First 300 Characters):**
```text
BIL-3.1 Tax Invoices and GST Compliance
- **Topics:** billing
- **Situations:** none
- **Numeric Limit:** none
- **Default Severity:** minor
- **Kind:** must_not_do

1. Every order dispatched is accompanied by a GST-compliant tax invoice detailing applicable CGST, SGST, and IGST breakdowns.
2. Busin
```
- **Exact Transcript Turn Text:**
> **Turn 7 (agent):** "Regenerating a commercial invoice with updated tax identifiers requires manual audit by accounting, which takes seven business days to issue."
- **Model Verbatim Quote Cited:** "takes seven business days to issue"
- **Model Explanation:** BIL-3.1 states that front-line agents are legally unable to revise or re-issue tax invoices under an alternate GSTIN once invoiced, making the seven-day timeline promise incorrect regarding policy rules.

---

#### [Extra #22] `call_208` (heldout) — Variant F flagged `BIL-3.1`: Tax Invoices and GST Compliance

- **Call ID:** `call_208` (heldout split)
- **Evaluated Variant:** Variant **F**
- **Flagged Clause ID & Exact Title:** `BIL-3.1` — Tax Invoices and GST Compliance
- **Assessed Severity:** `minor`
- **Target Transcript Turn:** Turn 7 (agent)
- **Clause Excerpt (First 300 Characters):**
```text
BIL-3.1 Tax Invoices and GST Compliance
- **Topics:** billing
- **Situations:** none
- **Numeric Limit:** none
- **Default Severity:** minor
- **Kind:** must_not_do

1. Every order dispatched is accompanied by a GST-compliant tax invoice detailing applicable CGST, SGST, and IGST breakdowns.
2. Busin
```
- **Exact Transcript Turn Text:**
> **Turn 7 (agent):** "Regenerating a commercial invoice with updated tax identifiers requires manual audit by accounting, which takes seven business days to issue."
- **Model Verbatim Quote Cited:** "requires manual audit by accounting, which takes seven business days"
- **Model Explanation:** BIL-3.1 states that frontline agents are legally unable to revise or re-issue tax invoices under an alternate GSTIN once the order has been invoiced, rather than taking seven business days.

---

#### [Extra #23] `call_208` (heldout) — Variant F flagged `ESC-1.1`: Mandatory Supervisor Escalation Triggers

- **Call ID:** `call_208` (heldout split)
- **Evaluated Variant:** Variant **F**
- **Flagged Clause ID & Exact Title:** `ESC-1.1` — Mandatory Supervisor Escalation Triggers
- **Assessed Severity:** `critical`
- **Target Transcript Turn:** Turn 11 (agent)
- **Clause Excerpt (First 300 Characters):**
```text
ESC-1.1 Mandatory Supervisor Escalation Triggers
- **Topics:** complaint, general
- **Situations:** supervisor_request, angry_customer, transfer
- **Numeric Limit:** none
- **Default Severity:** critical
- **Kind:** must_say

1. Frontline customer service representatives are required to initiate an
```
- **Exact Transcript Turn Text:**
> **Turn 11 (agent):** "I understand you have called four times, but our team handles every call in standard first-in first-out sequence. We cannot provide priority routing or queue jumps just because you have contacted us multiple times."
- **Model Verbatim Quote Cited:** "We cannot provide priority routing or queue jumps"
- **Model Explanation:** ESC-1.1 requires an immediate transfer or warm escalation to a supervisor when a customer explicitly requests a supervisor two or more times within the conversation, which the customer did.

---

#### [Extra #24] `call_209` (heldout) — Variant A flagged `ESC-1.1`: Mandatory Supervisor Escalation Triggers

- **Call ID:** `call_209` (heldout split)
- **Evaluated Variant:** Variant **A**
- **Flagged Clause ID & Exact Title:** `ESC-1.1` — Mandatory Supervisor Escalation Triggers
- **Assessed Severity:** `critical`
- **Target Transcript Turn:** Turn 7 (agent)
- **Clause Excerpt (First 300 Characters):**
```text
ESC-1.1 Mandatory Supervisor Escalation Triggers
- **Topics:** complaint, general
- **Situations:** supervisor_request, angry_customer, transfer
- **Numeric Limit:** none
- **Default Severity:** critical
- **Kind:** must_say

1. Frontline customer service representatives are required to initiate an
```
- **Exact Transcript Turn Text:**
> **Turn 7 (agent):** "Go ahead and post on social media if you want, Twitter posts do not impact our operational queue and our executive team does not monitor social media grievances."
- **Model Verbatim Quote Cited:** "Go ahead and post on social media if you want, Twitter posts do not impact our operational queue and our executive team does not monitor social media grievances."
- **Model Explanation:** ESC-1.1 requires an immediate warm escalation to a supervisor when a customer mentions social media public defamation. The agent refused and dismissed the threat.

---

#### [Extra #25] `call_209` (heldout) — Variant A flagged `BIL-2.2`: Agent Discretionary Compensation Limit

- **Call ID:** `call_209` (heldout split)
- **Evaluated Variant:** Variant **A**
- **Flagged Clause ID & Exact Title:** `BIL-2.2` — Agent Discretionary Compensation Limit
- **Assessed Severity:** `critical`
- **Target Transcript Turn:** Turn 15 (agent)
- **Clause Excerpt (First 300 Characters):**
```text
BIL-2.2 Agent Discretionary Compensation Limit
- **Topics:** billing, refund, complaint
- **Situations:** high_value_refund, supervisor_request
- **Numeric Limit:** Rs 5,000
- **Default Severity:** critical
- **Kind:** must_not_do

1. Frontline customer service agents are authorized to issue discret
```
- **Exact Transcript Turn Text:**
> **Turn 15 (agent):** "To close your complaint right now without further delay, I am approving an immediate goodwill refund of Rs 8,500 directly into your bank account on my own authority."
- **Model Verbatim Quote Cited:** "I am approving an immediate goodwill refund of Rs 8,500 directly into your bank account on my own authority."
- **Model Explanation:** BIL-2.2 limits frontline agents to a maximum threshold of Rs 5,000. Refunds exceeding Rs 5,000 require supervisor escalation under clause ESC-1.2, but the agent approved Rs 8,500 on their own authority.

---

#### [Extra #26] `call_209` (heldout) — Variant F flagged `ESC-1.1`: Mandatory Supervisor Escalation Triggers

- **Call ID:** `call_209` (heldout split)
- **Evaluated Variant:** Variant **F**
- **Flagged Clause ID & Exact Title:** `ESC-1.1` — Mandatory Supervisor Escalation Triggers
- **Assessed Severity:** `critical`
- **Target Transcript Turn:** Turn 7 (agent)
- **Clause Excerpt (First 300 Characters):**
```text
ESC-1.1 Mandatory Supervisor Escalation Triggers
- **Topics:** complaint, general
- **Situations:** supervisor_request, angry_customer, transfer
- **Numeric Limit:** none
- **Default Severity:** critical
- **Kind:** must_say

1. Frontline customer service representatives are required to initiate an
```
- **Exact Transcript Turn Text:**
> **Turn 7 (agent):** "Go ahead and post on social media if you want, Twitter posts do not impact our operational queue and our executive team does not monitor social media grievances."
- **Model Verbatim Quote Cited:** "Go ahead and post on social media if you want, Twitter posts do not impact our operational queue"
- **Model Explanation:** ESC-1.1 dictates that frontline reps must initiate an immediate supervisor transfer when the customer mentions social media public defamation. The agent refused to escalate.

---

#### [Extra #27] `call_209` (heldout) — Variant F flagged `BIL-2.2`: Agent Discretionary Compensation Limit

- **Call ID:** `call_209` (heldout split)
- **Evaluated Variant:** Variant **F**
- **Flagged Clause ID & Exact Title:** `BIL-2.2` — Agent Discretionary Compensation Limit
- **Assessed Severity:** `critical`
- **Target Transcript Turn:** Turn 15 (agent)
- **Clause Excerpt (First 300 Characters):**
```text
BIL-2.2 Agent Discretionary Compensation Limit
- **Topics:** billing, refund, complaint
- **Situations:** high_value_refund, supervisor_request
- **Numeric Limit:** Rs 5,000
- **Default Severity:** critical
- **Kind:** must_not_do

1. Frontline customer service agents are authorized to issue discret
```
- **Exact Transcript Turn Text:**
> **Turn 15 (agent):** "To close your complaint right now without further delay, I am approving an immediate goodwill refund of Rs 8,500 directly into your bank account on my own authority."
- **Model Verbatim Quote Cited:** "approving an immediate goodwill refund of Rs 8,500 directly into your bank account on my own authority."
- **Model Explanation:** BIL-2.2 restricts frontline agents to a maximum threshold of Rs 5,000 for discretionary financial adjustments. Rs 8,500 exceeds this limit and requires supervisor review.

---

## 3. Analysis of Expected Violations Not Found by Variant F (Ceiling Variant)

Variant F supplies ALL 42 policy clauses unconditionally in the prompt context. Under classical information retrieval assumptions, Variant F represents the theoretical ceiling (100% clause recall). However, in empirical testing, Variant F failed to identify **15 expected violations** across 9 calls (2 dev, 13 held-out). Below is the comprehensive forensic audit of what occurred on each turn where Variant F missed the expected clause.

### 3.1 Variant F Missed Expected Violations Registry

| Call ID | Split | Expected Clause | Severity | Turn | Model Verdict on Turn | Cited Alternate Clause | Primary Reason |
|:---|:---:|:---:|:---:|:---:|:---|:---:|:---|
| `call_102` | dev | `REF-3.1` | `critical` | Turn 5 | violation (cited alternate c | `BIL-2.2` | Semantic Clause Overlap / Alternate Violation |
| `call_107` | dev | `WAR-1.2` | `major` | Turn 7 | violation (subsumed under RE | `REF-1.1` | Compound Turn Subsumption |
| `call_202` | heldout | `PRV-1.1` | `critical` | Turn 3 | omitted / compliant | `None` | Prompt Dilution / Attention Dispersion |
| `call_204` | heldout | `BIL-1.2` | `major` | Turn 7 | violation (cited alternate c | `BIL-2.1` | Family Hierarchy Ambiguity |
| `call_204` | heldout | `BIL-2.2` | `minor` | Turn 11 | violation (cited alternate c | `BIL-2.3` | Specific vs General Clause Selection |
| `call_205` | heldout | `ESC-2.1` | `critical` | Turn 11 | omitted / subsumed | `None` | Multi-Turn Escalation Truncation |
| `call_205` | heldout | `ESC-3.1` | `major` | Turn 15 | omitted / subsumed | `None` | Multi-Turn Escalation Truncation |
| `call_206` | heldout | `PRV-1.1` | `critical` | Turn 3 | omitted / compliant | `None` | Prompt Dilution |
| `call_207` | heldout | `WAR-2.1` | `major` | Turn 7 | omitted / compliant | `None` | Information Overload / False Negative |
| `call_207` | heldout | `PRV-1.2` | `critical` | Turn 11 | violation (cited alternate c | `PRV-2.1` | Severe Misbehaviour Over-Shadowing |
| `call_208` | heldout | `BIL-2.1` | `minor` | Turn 7 | violation (cited alternate c | `BIL-3.1` | Domain Specificity Match |
| `call_208` | heldout | `ESC-1.2` | `major` | Turn 11 | violation (cited alternate c | `ESC-1.1` | Parent vs Sub-Clause Matching |
| `call_209` | heldout | `ESC-2.2` | `major` | Turn 7 | violation (cited alternate c | `ESC-1.1` | Parent Clause Mapping |
| `call_209` | heldout | `WAR-2.1` | `major` | Turn 11 | omitted / compliant | `None` | Context Loss / False Negative |
| `call_209` | heldout | `REF-3.1` | `critical` | Turn 15 | violation (cited alternate c | `BIL-2.2` | Semantic Equivalence |

### 3.2 Detailed Analysis per Missed Expected Violation

#### [1] `call_102` (dev) — Expected `REF-3.1`: Agent Approval Authority Threshold

- **Call ID:** `call_102` (dev split)
- **Expected Clause:** `REF-3.1` — Agent Approval Authority Threshold (Severity: `critical`)
- **Triggering Agent Turn:** Turn 5 (agent)
> **Transcript Turn 5 (agent):** "No, no need. The refund of Rs 8,500 is approved by me, I have full authority for this, so no supervisor is needed."
- **Model Verdict in Variant F:** `violation (cited alternate clause BIL-2.2)`
- **Alternate Clause Cited by Model:** `BIL-2.2` — Agent Discretionary Compensation Limit
- **Model Verbatim Quote:** "The refund of Rs 8,500 is approved by me, I have full authority for this"
- **Model Explanation:** BIL-2.2 limits frontline agent discretionary refunds to Rs 5,000 per order. Amounts exceeding Rs 5,000 require supervisor escalation under clause ESC-1.2.
- **Root Cause / Semantic Analysis:** Semantic Clause Overlap / Alternate Violation. Both REF-3.1 ('Refund Authorization Thresholds') and BIL-2.2 ('Discretionary Financial Adjustments') enforce the identical Rs 5,000 frontline threshold. With all 42 clauses presented, the model accurately flagged Turn 5 as a critical threshold breach, but cited BIL-2.2 instead of REF-3.1.

---

#### [2] `call_107` (dev) — Expected `WAR-1.2`: Dead on Arrival (DOA) and Transit Damage Reporting

- **Call ID:** `call_107` (dev split)
- **Expected Clause:** `WAR-1.2` — Dead on Arrival (DOA) and Transit Damage Reporting (Severity: `major`)
- **Triggering Agent Turn:** Turn 7 (agent)
> **Transcript Turn 7 (agent):** "I understand. Unfortunately, any defect has to be reported within 48 hours of delivery with photos, and since you are on day six, there is nothing we can do. No replacement, no return and no warranty claim is possible now."
- **Model Verdict in Variant F:** `violation (subsumed under REF-1.1)`
- **Alternate Clause Cited by Model:** `REF-1.1` — Return Eligibility Windows
- **Model Verbatim Quote:** "Unfortunately, any defect has to be reported within 48 hours of delivery with photos, and since you are on day six, there is nothing we can do."
- **Model Explanation:** REF-1.1 mandates a 7-day return window for electronics; the agent falsely claimed defects must be reported within 48 hours and rejected return on day 6.
- **Root Cause / Semantic Analysis:** Compound Turn Subsumption. Turn 7 contains two distinct ground-truth violations: REF-1.1 (denying 7-day electronics return) and WAR-1.2 (denying brand warranty routing). The model captured the primary return denial under REF-1.1 but omitted the secondary warranty clause WAR-1.2.

---

#### [3] `call_202` (heldout) — Expected `PRV-1.1`: Mandatory Two-Factor Customer Identity Verification

- **Call ID:** `call_202` (heldout split)
- **Expected Clause:** `PRV-1.1` — Mandatory Two-Factor Customer Identity Verification (Severity: `critical`)
- **Triggering Agent Turn:** Turn 3 (agent)
> **Transcript Turn 3 (agent):** "Hello Mr. Kulkarni, I see your order for the tablet was delivered to flat 402, Palm Heights in Pune yesterday. What seems to be the trouble?"
- **Model Verdict in Variant F:** `omitted / compliant`
- **Model Explanation:** Turn 3 was not flagged as a violation by the model. The model only flagged Turn 7 (REF-1.1) and Turn 11 (REF-2.2).
- **Root Cause / Semantic Analysis:** Prompt Dilution / Attention Dispersion. With 42 clauses (~8,400 input tokens) in the prompt, the model failed to flag the missing two-factor verification at the greeting stage (Turn 3) where the agent confirmed the order without verifying credentials.

---

#### [4] `call_204` (heldout) — Expected `BIL-1.2`: Failed Transactions and Auto-Reversals

- **Call ID:** `call_204` (heldout split)
- **Expected Clause:** `BIL-1.2` — Failed Transactions and Auto-Reversals (Severity: `major`)
- **Triggering Agent Turn:** Turn 7 (agent)
> **Transcript Turn 7 (agent):** "Duplicate charges on banking gateways happen occasionally. Our finance clearing cycle for reconciling duplicate charges takes fifteen business days before we can initiate the credit."
- **Model Verdict in Variant F:** `violation (cited alternate clause BIL-2.1)`
- **Alternate Clause Cited by Model:** `BIL-2.1` — Double Deductions and Duplicate Billings
- **Model Verbatim Quote:** "takes fifteen business days before we can initiate the credit"
- **Model Explanation:** BIL-2.1 states that full restitution of duplicate charges is released within 24 hours and statement reflection takes 5 to 7 business days, not 15.
- **Root Cause / Semantic Analysis:** Family Hierarchy Ambiguity. The agent promised a 15-day timeline for duplicate charges. Ground truth expected BIL-1.2 ('Payment Gateway Debits & Reconciliation'), but the model selected BIL-2.1 ('Billing Adjustments & Duplicate Charge Restitution'), which explicitly mentions duplicate charge restitution.

---

#### [5] `call_204` (heldout) — Expected `BIL-2.2`: Agent Discretionary Compensation Limit

- **Call ID:** `call_204` (heldout split)
- **Expected Clause:** `BIL-2.2` — Agent Discretionary Compensation Limit (Severity: `minor`)
- **Triggering Agent Turn:** Turn 11 (agent)
> **Transcript Turn 11 (agent):** "Yes, absolutely! Since the price dropped within 24 hours of your purchase, I will go ahead and apply a retroactive price match of Rs 500 to your account."
- **Model Verdict in Variant F:** `violation (cited alternate clause BIL-2.3)`
- **Alternate Clause Cited by Model:** `BIL-2.3` — Price Match and Post-Purchase Price Drops
- **Model Verbatim Quote:** "I will go ahead and apply a retroactive price match of Rs 500 to your account."
- **Model Explanation:** BIL-2.3 explicitly states that ShopEase does not provide retroactive price matching if an item's selling price decreases after an order has been successfully placed.
- **Root Cause / Semantic Analysis:** Specific vs General Clause Selection. The agent offered a Rs 500 retroactive price match. Ground truth labelled this under general financial adjustment clause BIL-2.2, but the model accurately selected BIL-2.3 ('Price Protection & Retroactive Price Match Ineligibility'), which specifically prohibits retroactive price matching.

---

#### [6] `call_205` (heldout) — Expected `ESC-2.1`: Warm Transfer Protocol and Hold Regulations

- **Call ID:** `call_205` (heldout split)
- **Expected Clause:** `ESC-2.1` — Warm Transfer Protocol and Hold Regulations (Severity: `critical`)
- **Triggering Agent Turn:** Turn 11 (agent)
> **Transcript Turn 11 (agent):** "You are free to send whatever legal notices you want, consumer courts take years anyway so our legal team will look at it whenever they receive it."
- **Model Verdict in Variant F:** `omitted / subsumed`
- **Model Explanation:** Turn 11 was not cited. The model flagged Turn 7 under ESC-1.1 for supervisor escalation refusal.
- **Root Cause / Semantic Analysis:** Multi-Turn Escalation Truncation. In a multi-turn angry customer dialogue, the model flagged the initial escalation breach at Turn 7 under ESC-1.1 but treated subsequent repetitions (Turn 11, Turn 15) as continuations rather than distinct clause breaches.

---

#### [7] `call_205` (heldout) — Expected `ESC-3.1`: Priority Support Level SLA Commitments

- **Call ID:** `call_205` (heldout split)
- **Expected Clause:** `ESC-3.1` — Priority Support Level SLA Commitments (Severity: `major`)
- **Triggering Agent Turn:** Turn 15 (agent)
> **Transcript Turn 15 (agent):** "I am not creating an escalation ticket right now. You can just dial back our helpline next week when the regular shift managers are available."
- **Model Verdict in Variant F:** `omitted / subsumed`
- **Model Explanation:** Turn 15 was not cited. The model flagged Turn 7 under ESC-1.1.
- **Root Cause / Semantic Analysis:** Multi-Turn Escalation Truncation. Similar to Turn 11, the Level-3 Executive Desk protocol (ESC-3.1) was treated as part of the overall escalation failure established in Turn 7.

---

#### [8] `call_206` (heldout) — Expected `PRV-1.1`: Mandatory Two-Factor Customer Identity Verification

- **Call ID:** `call_206` (heldout split)
- **Expected Clause:** `PRV-1.1` — Mandatory Two-Factor Customer Identity Verification (Severity: `critical`)
- **Triggering Agent Turn:** Turn 3 (agent)
> **Transcript Turn 3 (agent):** "Good morning, I have pulled up your pending shipment for the flagship smartphone heading to your residency at Green Glen Layout."
- **Model Verdict in Variant F:** `omitted / compliant`
- **Model Explanation:** Turn 3 was not flagged as a violation. The model only flagged Turn 7 under SHP-3.1.
- **Root Cause / Semantic Analysis:** Prompt Dilution. In Variant F, the model missed PRV-1.1 on Turn 3. (In contrast, Variant G—which selectively highlighted the PRV family—successfully detected this violation!).

---

#### [9] `call_207` (heldout) — Expected `WAR-2.1`: Free Replacement Workflow

- **Call ID:** `call_207` (heldout split)
- **Expected Clause:** `WAR-2.1` — Free Replacement Workflow (Severity: `major`)
- **Triggering Agent Turn:** Turn 7 (agent)
> **Transcript Turn 7 (agent):** "Our service center is currently facing a heavy backlog, so standard repair turnaround time is forty-five days, and we cannot offer any replacement unit or refund while it is under evaluation."
- **Model Verdict in Variant F:** `omitted / compliant`
- **Model Explanation:** Turn 7 was not flagged as a violation by the model in Variant F.
- **Root Cause / Semantic Analysis:** Information Overload / False Negative. The model overlooked the agent's misrepresentation of extended warranty terms on Turn 7.

---

#### [10] `call_207` (heldout) — Expected `PRV-1.2`: Mandatory Call Recording Disclosure

- **Call ID:** `call_207` (heldout split)
- **Expected Clause:** `PRV-1.2` — Mandatory Call Recording Disclosure (Severity: `critical`)
- **Triggering Agent Turn:** Turn 11 (agent)
> **Transcript Turn 11 (agent):** "If you want priority VIP service dispatch, you can pay an expedited handling fee of Rs 350 right now; please read out your card number, expiry, and the three-digit CVV on the back over the phone."
- **Model Verdict in Variant F:** `violation (cited alternate clause PRV-2.1)`
- **Alternate Clause Cited by Model:** `PRV-2.1` — Sensitive Personal Data Redaction
- **Model Verbatim Quote:** "please read out your card number, expiry, and the three-digit CVV on the back"
- **Model Explanation:** PRV-2.1 strictly prohibits agents from asking for, recording, or repeating 16-digit card numbers or 3-digit CVV security codes.
- **Root Cause / Semantic Analysis:** Severe Misbehaviour Over-Shadowing. While the rubric expected PRV-1.2 (call recording disclosure breach), the agent at Turn 11 committed a severe PCI-DSS security violation by asking for full card details and CVV. The model correctly and critically flagged this under PRV-2.1.

---

#### [11] `call_208` (heldout) — Expected `BIL-2.1`: Double Deductions and Duplicate Billings

- **Call ID:** `call_208` (heldout split)
- **Expected Clause:** `BIL-2.1` — Double Deductions and Duplicate Billings (Severity: `minor`)
- **Triggering Agent Turn:** Turn 7 (agent)
> **Transcript Turn 7 (agent):** "Regenerating a commercial invoice with updated tax identifiers requires manual audit by accounting, which takes seven business days to issue."
- **Model Verdict in Variant F:** `violation (cited alternate clause BIL-3.1)`
- **Alternate Clause Cited by Model:** `BIL-3.1` — Tax Invoices and GST Compliance
- **Model Verbatim Quote:** "requires manual audit by accounting, which takes seven business days"
- **Model Explanation:** BIL-3.1 states that frontline agents are legally unable to revise or re-issue tax invoices under an alternate GSTIN once the order has been invoiced, rather than taking seven business days.
- **Root Cause / Semantic Analysis:** Domain Specificity Match. The customer demanded a revised GSTIN invoice. Ground truth labelled this under general adjustments BIL-2.1, but the model chose BIL-3.1 ('Tax Invoice Generation & GSTIN Compliance'), which is specifically tailored to GSTIN revisions.

---

#### [12] `call_208` (heldout) — Expected `ESC-1.2`: Monetary Escalation and Approval Limits

- **Call ID:** `call_208` (heldout split)
- **Expected Clause:** `ESC-1.2` — Monetary Escalation and Approval Limits (Severity: `major`)
- **Triggering Agent Turn:** Turn 11 (agent)
> **Transcript Turn 11 (agent):** "I understand you have called four times, but our team handles every call in standard first-in first-out sequence. We cannot provide priority routing or queue jumps just because you have contacted us multiple times."
- **Model Verdict in Variant F:** `violation (cited alternate clause ESC-1.1)`
- **Alternate Clause Cited by Model:** `ESC-1.1` — Mandatory Supervisor Escalation Triggers
- **Model Verbatim Quote:** "We cannot provide priority routing or queue jumps"
- **Model Explanation:** ESC-1.1 requires an immediate transfer or warm escalation to a supervisor when a customer explicitly requests a supervisor two or more times within the conversation, which the customer did.
- **Root Cause / Semantic Analysis:** Parent vs Sub-Clause Matching. The customer requested a supervisor transfer/callback. Ground truth expected callback SLA clause ESC-1.2, but the model cited the primary supervisor escalation mandate ESC-1.1.

---

#### [13] `call_209` (heldout) — Expected `ESC-2.2`: Cold Drops and Call Abandonment Prohibition

- **Call ID:** `call_209` (heldout split)
- **Expected Clause:** `ESC-2.2` — Cold Drops and Call Abandonment Prohibition (Severity: `major`)
- **Triggering Agent Turn:** Turn 7 (agent)
> **Transcript Turn 7 (agent):** "Go ahead and post on social media if you want, Twitter posts do not impact our operational queue and our executive team does not monitor social media grievances."
- **Model Verdict in Variant F:** `violation (cited alternate clause ESC-1.1)`
- **Alternate Clause Cited by Model:** `ESC-1.1` — Mandatory Supervisor Escalation Triggers
- **Model Verbatim Quote:** "Go ahead and post on social media if you want, Twitter posts do not impact our operational queue"
- **Model Explanation:** ESC-1.1 dictates that frontline reps must initiate an immediate supervisor transfer when the customer mentions social media public defamation. The agent refused to escalate.
- **Root Cause / Semantic Analysis:** Parent Clause Mapping. Ground truth expected ESC-2.2 (defamation/legal threats), but the model cited ESC-1.1 (general supervisor escalation triggered by social media mentions).

---

#### [14] `call_209` (heldout) — Expected `WAR-2.1`: Free Replacement Workflow

- **Call ID:** `call_209` (heldout split)
- **Expected Clause:** `WAR-2.1` — Free Replacement Workflow (Severity: `major`)
- **Triggering Agent Turn:** Turn 11 (agent)
> **Transcript Turn 11 (agent):** "During festival months, panel replacement turnaround times are indefinite; it could take several months and we cannot commit to any timeline."
- **Model Verdict in Variant F:** `omitted / compliant`
- **Model Explanation:** Turn 11 was not cited as a violation by the model in Variant F.
- **Root Cause / Semantic Analysis:** Context Loss / False Negative. The model overlooked the open-box warranty exclusion misstatement.

---

#### [15] `call_209` (heldout) — Expected `REF-3.1`: Agent Approval Authority Threshold

- **Call ID:** `call_209` (heldout split)
- **Expected Clause:** `REF-3.1` — Agent Approval Authority Threshold (Severity: `critical`)
- **Triggering Agent Turn:** Turn 15 (agent)
> **Transcript Turn 15 (agent):** "To close your complaint right now without further delay, I am approving an immediate goodwill refund of Rs 8,500 directly into your bank account on my own authority."
- **Model Verdict in Variant F:** `violation (cited alternate clause BIL-2.2)`
- **Alternate Clause Cited by Model:** `BIL-2.2` — Agent Discretionary Compensation Limit
- **Model Verbatim Quote:** "approving an immediate goodwill refund of Rs 8,500 directly into your bank account on my own authority."
- **Model Explanation:** BIL-2.2 restricts frontline agents to a maximum threshold of Rs 5,000 for discretionary financial adjustments. Rs 8,500 exceeds this limit and requires supervisor review.
- **Root Cause / Semantic Analysis:** Semantic Equivalence. Identical to call_102, the unauthorized Rs 8,500 refund was flagged under financial adjustment threshold BIL-2.2 instead of refund threshold REF-3.1.

---

## 4. Development Split Scoring & Grade Impact (Production A vs Variant G)

Using the canonical scoring engine (`src/audit/scoring.py` and `data/rubric.yaml`), the final scorecard was computed for each of the **13 sample development calls** under Production Variant A findings vs Variant G findings. Per strict operational requirements, stored expectations were NOT modified.

### 4.1 Score & Grade Comparison Table (13 Dev Calls)

| Call ID | Topic | Production A Score (Grade) | Variant G Score (Grade) | Score Delta | Grade Changed? | Findings Difference / Key Driver |
|:---|:---:|:---:|:---:|:---:|:---:|:---|
| `call_001` | refund | **100.0** (A) | **100.0** (A) | **0.0** | No | Identical findings |
| `call_009` | billing | **91.5** (A) | **91.5** (A) | **0.0** | No | Identical findings |
| `call_017` | shipping | **86.6** (B) | **86.6** (B) | **0.0** | No | Identical findings |
| `call_025` | warranty | **85.1** (B) | **85.1** (B) | **0.0** | No | Identical findings |
| `call_041` | warranty | **84.6** (B) | **84.6** (B) | **0.0** | No | Identical findings |
| `call_101` | refund | **94.0** (A) | **94.0** (A) | **0.0** | No | Identical findings |
| `call_102` | refund | **11.3** (D) | **11.3** (D) | **0.0** | No | +G: PRV-1.1, PRV-1.2, REF-2.1 |
| `call_103` | billing | **94.0** (A) | **94.0** (A) | **0.0** | No | Identical findings |
| `call_104` | billing | **39.0** (D) | **27.0** (D) | **-12.0** | No | +G: PRV-1.2, PRV-2.2 |
| `call_105` | shipping | **94.0** (A) | **94.0** (A) | **0.0** | No | Identical findings |
| `call_106` | shipping | **39.0** (D) | **39.0** (D) | **0.0** | No | Identical findings |
| `call_107` | warranty | **63.9** (D) | **70.0** (C) | **+6.1** | YES | -G: WAR-1.2 |
| `call_108` | shipping | **94.0** (A) | **94.0** (A) | **0.0** | No | Identical findings |

### 4.2 Category Breakdown & Critical Cap Impact

| Call ID | SOP Score | A Policy Score | G Policy Score | Empathy Score | Comm Score | Critical Cap Triggered? | Grade Shift Impact |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---|
| `call_001` | 40.0 | 30.0 | 30.0 | 15.0 | 15.0 | A: No / G: No | None (Identical) |
| `call_009` | 38.5 | 30.0 | 30.0 | 12.0 | 11.0 | A: No / G: No | None (Identical) |
| `call_017` | 35.6 | 27.0 | 27.0 | 12.0 | 12.0 | A: No / G: No | None (Identical) |
| `call_025` | 34.1 | 27.0 | 27.0 | 12.0 | 12.0 | A: No / G: No | None (Identical) |
| `call_041` | 35.6 | 27.0 | 27.0 | 12.0 | 10.0 | A: No / G: No | None (Identical) |
| `call_101` | 40.0 | 30.0 | 30.0 | 12.0 | 12.0 | A: No / G: No | None (Identical) |
| `call_102` | 3.8 | 0.0 | 0.0 | 3.0 | 4.5 | A: YES / G: YES | None (Policy score already 0.0; total score 11.3 is below 70 cap) |
| `call_103` | 40.0 | 30.0 | 30.0 | 12.0 | 12.0 | A: No / G: No | None (Identical) |
| `call_104` | 3.0 | 12.0 | 0.0 | 12.0 | 12.0 | A: YES / G: YES | Policy penalty -12.0 pts; score drops 39.0 -> 27.0 (stays D) |
| `call_105` | 40.0 | 30.0 | 30.0 | 12.0 | 12.0 | A: No / G: No | None (Identical) |
| `call_106` | 10.0 | 7.0 | 7.0 | 12.0 | 10.0 | A: YES / G: YES | None (Identical) |
| `call_107` | 28.9 | 11.0 | 19.0 | 12.0 | 12.0 | A: YES / G: YES | WAR-1.2 missed in G; penalty drops 19 -> 11; capped at 70.0 (D -> C) |
| `call_108` | 40.0 | 30.0 | 30.0 | 12.0 | 12.0 | A: No / G: No | None (Identical) |

### 4.3 Key Architectural Takeaways for QA Leadership

1. **High Stability Across Clean Calls (10/13 Calls Unchanged):** For all standard compliant calls and single-domain deviation calls (`call_001` through `call_041`, `call_101`, `call_103`, `call_105`, `call_106`, `call_108`), Variant G produces 100% identical policy findings to Variant A. System grades remain fully stable.
2. **Critical Privacy Protection (`call_102` & `call_104`):** In `call_102`, Variant A missed `PRV-1.1` (identity verification) and `PRV-1.2` (recording disclosure) because retrieval was restricted to the refund domain. Variant G successfully surfaced and flagged both critical privacy violations. In `call_104`, Variant G caught `PRV-1.2` and `PRV-2.2` (address masking breach), dropping the score from 39.0 to 27.0.
3. **Tolerance & Calibration in `call_107`:** In `call_107`, Variant G missed `WAR-1.2` on Turn 7 (flagging only `REF-1.1`), which eased the policy penalty from 19 to 11 points, resulting in an overall score bump from 63.9 (D) to the critical failure cap of 70.0 (C).
