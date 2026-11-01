---
category: shipping_and_delivery
type: policy
version: 1.0
last_updated: 2026-10-15
author: Logistics & Supply Chain Operations, ShopEase
---

# ShopEase Shipping and Delivery Policy

This document outlines the standard delivery service tiers, transit SLAs, address change regulations, delivery attempts, and escalation procedures for lost or damaged parcels.

---

### [SHP-1.1] Service Tiers and Standard Transit SLAs
- **Topics:** shipping
- **Situations:** none
- **Numeric Limit:** 3 to 7 business days
- **Default Severity:** minor
- **Kind:** informational

1. ShopEase provides two official shipping tiers across serviced Indian postal codes:
   - **Standard Delivery:** Delivery within **3 to 7 business days** from order dispatch date.
   - **Express Delivery:** Expedited delivery within **1 to 2 business days** for eligible metro and tier-1 city pin codes.
2. Orders placed on Sundays and national holidays are packed and handed over to logistics partners on the following working business day.

---

### [SHP-1.2] Delivery Fees and Minimum Spend Thresholds
- **Topics:** shipping, billing
- **Situations:** none
- **Numeric Limit:** Rs 499
- **Default Severity:** minor
- **Kind:** informational

1. Standard Delivery is complimentary (free) on all orders with a total cart value equal to or exceeding Rs 499.
2. Orders below Rs 499 incur a fixed non-refundable shipping fee of Rs 49.
3. Express Delivery incurs a convenience surcharge of Rs 99 regardless of total order value.

---

### [SHP-2.1] Carrier Attempts and Undelivered Consignments
- **Topics:** shipping, refund
- **Situations:** none
- **Numeric Limit:** 3 attempts
- **Default Severity:** minor
- **Kind:** informational

1. Delivery partners will make up to **three (3) independent delivery attempts** at the customer's shipping address.
2. Prior to each attempt, the customer receives an automated SMS and WhatsApp notification containing an Out-For-Delivery (OFD) alert and the delivery partner contact number.
3. If all three attempts fail due to customer unavailability, incorrect landmark, or contact failure, the shipment is marked "Return To Origin" (RTO).
4. Prepaid orders that encounter RTO are processed for automatic refund within **5 to 7 business days** of receipt back at the origin fulfillment center, under policy clause `[REF-2.1]`.

---

### [SHP-2.2] Address Modifications Post-Dispatch
- **Topics:** shipping
- **Situations:** data_disclosure
- **Numeric Limit:** none
- **Default Severity:** major
- **Kind:** must_not_do

1. Customers may modify their delivery address only while the order remains in "Confirmed" or "Processing" status.
2. Once the order reaches "Shipped" or "Out for Delivery" status, no frontline agent has system permission to alter the delivery address or recipient name.
3. In exceptional emergency cases, the customer must request an order cancellation and reorder to the updated address.

---

### [SHP-2.3] Delayed Shipments and Compensation Protocol
- **Topics:** shipping, complaint, refund
- **Situations:** angry_customer
- **Numeric Limit:** 48 hours
- **Default Severity:** major
- **Kind:** informational

1. A shipment is officially categorized as "Delayed in Transit" when transit time exceeds the published SLA (7 business days for standard delivery, 2 business days for express delivery).
2. If a shipment is delayed beyond 48 hours past the SLA:
   - The agent must initiate a logistics tracking ticket with courier partner dispatch.
   - The customer is eligible for a goodwill promotional wallet credit of Rs 100 for verified operational delays.
3. If transit exceeds 14 calendar days without status updates, the package is declared lost in transit, and an immediate full refund or priority reshipment is granted.

---

### [SHP-3.1] Secure One-Time Password (OTP) Delivery Protocol
- **Topics:** shipping
- **Situations:** otp_request, data_disclosure
- **Numeric Limit:** Rs 2,500
- **Default Severity:** critical
- **Kind:** must_not_do

1. High-value orders exceeding Rs 2,500 and all smartphone consignments are secured using a mandatory 4-digit Delivery Verification OTP.
2. Couriers are legally prohibited from releasing parcels without entering the customer-provided OTP into the field scanner.
3. Agents must never disclose the delivery OTP to any caller over phone support.

---

### [SHP-3.2] Damaged Packages at Delivery Handover
- **Topics:** shipping, warranty
- **Situations:** none
- **Numeric Limit:** 48 hours
- **Default Severity:** major
- **Kind:** informational

1. If a parcel outer box shows visible signs of severe tampering, crushing, or water damage at the time of delivery, the customer is strongly advised to reject the package with the remark "Damaged Box".
2. If accepted, the customer must report transit damage within **48 hours** with clear unboxing photographs as mandated under clause `[WAR-1.2]`.

---

### [SHP-4.1] Non-Serviceable and Remote Pin Codes
- **Topics:** shipping
- **Situations:** none
- **Numeric Limit:** 10 to 12 business days
- **Default Severity:** minor
- **Kind:** must_say

1. Certain remote locations in Jammu & Kashmir, Ladakh, and North-Eastern states may take up to 10 to 12 business days under standard postal routing.
2. Agents must proactively communicate this extended transit window during pre-order or post-order delivery inquiries for these designated remote zones.
