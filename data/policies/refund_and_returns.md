---
category: refunds_and_returns
type: policy
version: 1.0
last_updated: 2026-10-15
author: Quality & Compliance Operations, ShopEase
---

# ShopEase Returns and Refunds Policy

This document defines the formal rules, criteria, eligibility windows, and execution thresholds governing returns and monetary refunds across all ShopEase marketplace channels.

---

### [REF-1.1] Return Eligibility Windows
- **Topics:** refund, warranty
- **Situations:** none
- **Numeric Limit:** 7 days
- **Default Severity:** major
- **Kind:** informational

1. Customers are entitled to initiate a return within the specified category window starting from the recorded delivery timestamp:
   - **Electronics Category:** Exactly **7 calendar days** from the date of delivery. This includes smartphones, laptops, audio accessories, wearables, smart home appliances, and electronic components.
   - **Non-Electronics Category:** Exactly **14 calendar days** from the date of delivery. This covers apparel, footwear, home furnishings, fitness accessories, books, and general lifestyle merchandise.
2. Items initiated past these windows are ineligible for standard returns and must be serviced via manufacturer warranty or standard repair policies.

---

### [REF-1.2] Item Condition and Verification
- **Topics:** refund
- **Situations:** none
- **Numeric Limit:** none
- **Default Severity:** major
- **Kind:** informational

1. To qualify for a return and full refund, items must be in original condition, unused, unwashed, and accompanied by:
   - Original brand packaging, tags, warranty cards, manuals, and bundled accessories.
   - Intact serial numbers / IMEI numbers matching the invoice record.
2. Couriers perform a mandatory physical doorstep check upon pickup. Pickup will be rejected if serial numbers do not match or if physical abuse is detected.

---

### [REF-2.1] Refund Processing Timelines
- **Topics:** refund
- **Situations:** none
- **Numeric Limit:** 5 to 7 business days
- **Default Severity:** minor
- **Kind:** informational

1. All approved refunds are processed within **5 to 7 business days** following successful return pickup and warehouse verification.
2. Public holidays, second/fourth Saturdays, and Sundays are excluded from business day calculations.
3. Once initiated by ShopEase finance, bank clearance times depend on the recipient financial institution:
   - UPI and IMPS transfers typically credit within 24 to 48 hours.
   - Credit card and debit card accounts reflect within 5 to 7 business days.

---

### [REF-2.2] Method of Refund Disbursement
- **Topics:** refund, billing
- **Situations:** identity_verification, data_disclosure
- **Numeric Limit:** none
- **Default Severity:** major
- **Kind:** must_not_do

1. Refunds must be remitted strictly to the **original payment method** utilized during checkout:
   - Credit / Debit Card payments return to the identical card account.
   - Net Banking and UPI payments return to the source bank account.
2. **Cash on Delivery (COD) Purchases:** Refunds for COD orders are disbursed via NEFT bank transfer to the verified bank account or UPI VPA nominated by the customer in their account profile after completing identity verification. Refunds cannot be handed over in physical cash.
3. Under no circumstances may an agent redirect a refund to a third-party wallet or alternate bank account not registered to the customer profile.

---

### [REF-3.1] Agent Approval Authority Threshold
- **Topics:** refund
- **Situations:** high_value_refund, supervisor_request
- **Numeric Limit:** Rs 5,000
- **Default Severity:** critical
- **Kind:** must_not_do

1. Frontline customer support agents possess discretionary authority to approve instant refunds and concessions up to a maximum limit of **Rs 5,000** (Rupees Five Thousand only) per order, provided return eligibility criteria are met.
2. Any refund request exceeding **Rs 5,000** strictly requires supervisor review, fraud desk clearance, and secondary authorization prior to confirmation.
3. Agents are strictly prohibited from splitting refund line items across multiple tickets to circumvent the Rs 5,000 single-agent ceiling.

---

### [REF-3.2] Non-Returnable Goods and Exceptions
- **Topics:** refund
- **Situations:** none
- **Numeric Limit:** 48 hours
- **Default Severity:** major
- **Kind:** informational

1. The following categories are categorically non-returnable once opened or delivered, except where dead-on-arrival or damaged in transit:
   - Personal hygiene products, innerwear, and cosmetics.
   - Perishable consumables, gourmet food, and nutritional supplements.
   - Downloadable software licenses and digital gift cards.
2. If an item in a non-returnable category arrives physically damaged, the customer must report it within **48 hours** under policy clause `[WAR-1.2]`.

---

### [REF-4.1] Return Logistics and Reverse Pickup
- **Topics:** refund, shipping
- **Situations:** none
- **Numeric Limit:** 3 attempts
- **Default Severity:** minor
- **Kind:** informational

1. Reverse pickup is scheduled within 48 to 72 hours of return acceptance across standard service pin codes.
2. In non-serviceable pin codes, customers may self-ship the product via registered India Post Speed Post. ShopEase reimburses courier expenses up to Rs 200 upon presentation of valid courier receipts.
3. Maximum 3 reverse pickup attempts will be made by our logistics partner before the return request is automatically cancelled.

---

### [REF-4.2] Partial Returns and Bundle Discounts
- **Topics:** refund, billing
- **Situations:** none
- **Numeric Limit:** none
- **Default Severity:** minor
- **Kind:** informational

1. When products purchased under combo promotions or "Buy 1 Get 1" offers are returned partially, the discount applied across the order will be prorated.
2. The refund amount will reflect the deduction of the promotional benefit enjoyed on the retained item.
