---
category: billing_and_payments
type: policy
version: 1.0
last_updated: 2026-10-15
author: Finance Operations & Payment Gateway Risk, ShopEase
---

# ShopEase Billing and Payments Policy

This document governs payment processing mechanisms, failed and duplicate charge reconciliations, Cash on Delivery (COD) accounting, tax invoicing, and monetary reversal regulations.

---

### [BIL-1.1] Accepted Payment Instruments
1. ShopEase supports the following payment methods through verified secure payment gateways:
   - Unified Payments Interface (UPI: Google Pay, PhonePe, Paytm, BHIM, and bank VPAs).
   - Credit Cards and Debit Cards issued by Visa, MasterCard, RuPay, and American Express.
   - Net Banking across all RBI-scheduled Indian commercial banks.
   - Cash on Delivery (COD) for eligible domestic shipments up to Rs 10,000.
   - ShopEase Wallet balances and promotional gift vouchers.
2. Direct cryptocurrency, foreign cash remittances, or post-dated cheques are strictly non-acceptable.

---

### [BIL-1.2] Failed Transactions and Auto-Reversals
1. When a customer's bank account or payment card is debited but the order fails to generate on ShopEase ("Payment Pending" or "Dropped Session"):
   - The payment gateway executes an automated settlement reconciliation every 4 hours.
   - If funds were captured by ShopEase without order creation, an automatic refund is triggered within 24 hours.
   - Funds reflect in the customer's source account within **5 to 7 business days** under standard banking turnaround times (`[REF-2.1]`).
2. Agents must request the unique 12-digit Bank Reference Number (UTR / RRN) from the caller to check bank payment gateway logs.

---

### [BIL-1.3] Cash on Delivery (COD) Settlement & Verification
1. COD is limited to orders with a cumulative cart value not exceeding Rs 10,000. Orders above Rs 10,000 require full digital prepayment.
2. In the event of a product return or order cancellation on a COD order:
   - Courier delivery agents are strictly prohibited from handing out cash refunds at the doorstep.
   - All COD refunds are disbursed exclusively via **NEFT bank transfer** to the customer's validated bank account or verified UPI VPA.
   - Before capturing bank details for COD refunds, the agent must perform mandatory identity verification (`[PRV-1.1]`).

---

### [BIL-2.1] Double Deductions and Duplicate Billings
1. In instances where a customer is charged twice for a single order due to gateway re-attempts:
   - The secondary debit is flagged by the automated audit reconciliation.
   - Full restitution of the duplicate charge is released immediately to the original payment source within 24 hours.
   - Reversal reflection in the customer's statement takes **5 to 7 business days**.

---

### [BIL-2.2] Agent Discretionary Compensation Limit
1. Frontline customer service agents are authorized to issue discretionary financial adjustments, convenience compensations, or direct refunds up to a maximum threshold of **Rs 5,000** per order.
2. Any concession, partial waiver, or refund exceeding **Rs 5,000** must be escalated to a team supervisor or finance desk for formal secondary review and system sign-off under clause `[ESC-1.2]`.

---

### [BIL-2.3] Price Match and Post-Purchase Price Drops
1. ShopEase does not provide retroactive price matching if an item's selling price decreases due to seasonal flash sales, lightning deals, or promotional coupon campaigns after an order has been successfully placed.
2. If an order has not shipped, the customer holds the right to cancel the order and place a fresh order at the lower prevailing price.

---

### [BIL-3.1] Tax Invoices and GST Compliance
1. Every order dispatched is accompanied by a GST-compliant tax invoice detailing applicable CGST, SGST, and IGST breakdowns.
2. Business customers requiring B2B input tax credits must input their valid 15-character GSTIN at the time of checkout. Frontline agents are legally unable to revise or re-issue tax invoices under an alternate GSTIN once the order has been invoiced.
