"""Build 12 held-out labelled calls (call_201 .. call_212) into data/heldout/.

Creates:
- data/heldout/transcripts/call_201.json .. call_212.json
- data/heldout/expected_heldout.json

Rules:
- Strictly compliant with FullTranscriptSchema and scripts/validate_transcripts.py
- Labels derive ONLY from data/policies/*.md
- No LLM calls or API keys
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_TRANSCRIPTS = ROOT / "data" / "heldout" / "transcripts"
OUT_EXPECTED = ROOT / "data" / "heldout" / "expected_heldout.json"

GEN_STEPS = [f"GEN-0{i}" for i in range(1, 9)]

def all_followed():
    return {s: "followed" for s in GEN_STEPS}

def make_turn(i: int, speaker: str, text: str, pause: float = 0.5, interrupts: bool = False):
    return {
        "i": i,
        "speaker": speaker,
        "text": text,
        "pause_before_sec": pause,
        "interrupts_previous": interrupts,
    }

CALLS_DATA = []

# ==============================================================================
# call_201: shipping, BAD (single attempt delivery claim -> SHP-2.1)
# ==============================================================================
t201 = [
    make_turn(1, "agent", "Thank you for contacting ShopEase customer support. My name is Rahul Verma. Please note that this conversation is recorded for quality monitoring and training purposes. How can I assist you today?"),
    make_turn(2, "customer", "Hello Rahul, this is Ananya Sharma. I ordered leather boots last Friday under order ORD-61294, and your tracking app states a delivery attempt failed this morning, but nobody rang my doorbell."),
    make_turn(3, "agent", "I am very sorry to hear about that, Ms. Sharma. I would be glad to check the logistics log for you. Before we proceed, could you please confirm your Order ID and the last four digits of your registered phone number?"),
    make_turn(4, "customer", "Sure, the order number is ORD-61294 and the last four digits of my mobile are 3829."),
    make_turn(5, "agent", "Thank you, Ms. Sharma, your account details are verified. Let me examine the dispatch notes for your package."),
    make_turn(6, "agent", "The courier partner reached your apartment entrance once earlier today. Under our courier agreement terms, drivers make only one single delivery attempt, and because you were unavailable, the shipment is immediately sent back to our central warehouse for return to origin."),
    make_turn(7, "customer", "Wait, are you serious? Just one attempt? I was in a meeting for twenty minutes. Can the delivery executive not come back tomorrow?"),
    make_turn(8, "agent", "No, our policy does not allow re-dispatch once an attempt has been logged; the shipment will be returned to the merchant and you will need to place a fresh order online."),
    make_turn(9, "customer", "That is terribly inconvenient. I needed those boots for an event this weekend."),
    make_turn(10, "agent", "I understand your disappointment, Ms. Sharma. However, the package is already marked for return transit in the carrier portal, so I cannot alter the route."),
    make_turn(11, "customer", "Is there really no other option to stop the return?"),
    make_turn(12, "agent", "Unfortunately not. Once marked for return, the shipment cannot be held at the local facility."),
    make_turn(13, "customer", "Fine, I will see what other store has them in stock."),
    make_turn(14, "agent", "I apologize again for the frustration caused. Thank you for calling ShopEase, and have a good day."),
]

CALLS_DATA.append({
    "id": "call_201",
    "topic": "shipping",
    "quality": "bad_deviation",
    "split": "test",
    "applicable_sops": ["general_call_flow"],
    "applicable_steps": GEN_STEPS,
    "hold_scenario": "none",
    "customer_name": "Ananya Sharma",
    "agent_name": "Rahul Verma",
    "order_id": "ORD-61294",
    "registered_phone_last4": "3829",
    "customer_persona": "Ananya Sharma is frustrated that her package was marked for immediate return after a single missed buzzer.",
    "verified": True,
    "verification_notes": "Passed verification of order ID and last 4 phone digits.",
    "turns": t201,
    "ground_truth": {
        "sop_steps": {**all_followed(), "GEN-06": "missed"},
        "policy_violations": [
            {
                "turn": 6,
                "said": t201[5]["text"],
                "clause_id": "SHP-2.1",
                "severity": "major",
                "correct_fact": "Couriers must make up to three distinct delivery attempts on consecutive business days before returning a shipment to origin.",
            }
        ],
        "customer_emotion_arc": ["neutral", "frustrated", "disappointed"],
        "gaps": [],
    },
})

# ==============================================================================
# call_202: refund, BAD (no verification -> PRV-1.1, 3-day electronics -> REF-1.1, wallet credit only -> REF-2.2)
# ==============================================================================
t202 = [
    make_turn(1, "agent", "Good afternoon, thank you for dialing ShopEase. My name is Priya Sen. This call is being recorded for quality monitoring purposes. How may I assist you?"),
    make_turn(2, "customer", "Hi Priya, my name is Rajesh Kulkarni. I purchased an Android tablet that arrived yesterday and the touchscreen is continuously flickering."),
    make_turn(3, "agent", "Hello Mr. Kulkarni, I see your order for the tablet was delivered to flat 402, Palm Heights in Pune yesterday. What seems to be the trouble?"),
    make_turn(4, "customer", "Yes, that is my flat. When I turn on the display, random green lines flicker across the screen, so I want to send it back and receive my money back."),
    make_turn(5, "agent", "I see. Let me look into our return guidelines for this tablet model."),
    make_turn(6, "customer", "Thank you, please tell me how quickly you can collect it."),
    make_turn(7, "agent", "For portable electronics and tablets, our return window is strictly limited to 3 days from delivery date, so after today you would not have been eligible."),
    make_turn(8, "customer", "Well, good thing I called right away then. The courier can pick it up tomorrow, right?"),
    make_turn(9, "agent", "Yes, I can arrange a return pickup within 48 hours. The courier will inspect the unit and collect the box."),
    make_turn(10, "customer", "Great. I paid Rs 14,999 on my Visa credit card, so please credit it back to that card."),
    make_turn(11, "agent", "Since you purchased this during the weekend clearance sale, refunds cannot be returned to your Visa card; the amount of Rs 14,999 will only be credited as ShopEase wallet credits for future purchases."),
    make_turn(12, "customer", "What? Why would I want wallet credits? I paid with real money from my card and the device is defective!"),
    make_turn(13, "agent", "Clearance items are strictly non-refundable to card accounts under our system policies; only store credits can be offered."),
    make_turn(14, "customer", "This is very disappointing. Let me speak to someone who can process a proper bank refund."),
    make_turn(15, "agent", "Our payment backend restricts promotional orders to wallet refunds only, so another representative would tell you the exact same thing."),
    make_turn(16, "customer", "I will take this up separately then. Good day."),
]

CALLS_DATA.append({
    "id": "call_202",
    "topic": "refund",
    "quality": "bad_deviation",
    "split": "test",
    "applicable_sops": ["general_call_flow"],
    "applicable_steps": GEN_STEPS,
    "hold_scenario": "none",
    "customer_name": "Rajesh Kulkarni",
    "agent_name": "Priya Sen",
    "order_id": "ORD-84521",
    "registered_phone_last4": "9104",
    "customer_persona": "Rajesh Kulkarni bought a defective tablet and is shocked when told refunds are wallet-only and address was revealed unverified.",
    "verified": True,
    "verification_notes": "Passed transcript audit check.",
    "turns": t202,
    "ground_truth": {
        "sop_steps": {**all_followed(), "GEN-02": "missed", "GEN-06": "missed"},
        "policy_violations": [
            {
                "turn": 3,
                "said": t202[2]["text"],
                "clause_id": "PRV-1.1",
                "severity": "critical",
                "correct_fact": "Customer identity must be verified using Order ID and last 4 mobile digits before disclosing delivery address or order particulars.",
            },
            {
                "turn": 7,
                "said": t202[6]["text"],
                "clause_id": "REF-1.1",
                "severity": "major",
                "correct_fact": "Electronic items carry a return window of 7 calendar days from delivery, not 3 days.",
            },
            {
                "turn": 11,
                "said": t202[10]["text"],
                "clause_id": "REF-2.2",
                "severity": "major",
                "correct_fact": "Refunds must always be credited back to the original payment source used during purchase.",
            },
        ],
        "customer_emotion_arc": ["neutral", "neutral", "frustrated", "angry"],
        "gaps": [],
    },
})

# ==============================================================================
# call_203: warranty, BAD (electronics return denied on day 5 -> REF-1.1, 6 mo warranty -> WAR-1.1)
# ==============================================================================
t203 = [
    make_turn(1, "agent", "Welcome to ShopEase support. My name is Vikram Malhotra. This call is recorded for quality monitoring and compliance. How can I assist you?"),
    make_turn(2, "customer", "Hi Vikram, I am Deepa Sundaram. I ordered an office laptop under order ORD-33910 five days ago, and it suddenly shuts down every twenty minutes. I want to return it or get an immediate replacement."),
    make_turn(3, "agent", "I am sorry to hear your laptop is shutting down, Ms. Sundaram. To pull up your file securely, could you give me your Order ID and the last four digits of your registered mobile number?"),
    make_turn(4, "customer", "Yes, the order is ORD-33910 and my phone ends in 5271."),
    make_turn(5, "agent", "Thank you, that validates your profile. Let me check the order history and delivery record."),
    make_turn(6, "customer", "It was delivered five days ago on Thursday afternoon."),
    make_turn(7, "agent", "Because the laptop was delivered 5 days ago, our return window is completely closed. Electronics can only be returned within 48 hours of transit damage, so ShopEase cannot accept a return or issue a refund; you must take it to an authorized brand service center yourself."),
    make_turn(8, "customer", "Wait, five days is less than a week! Why can't I return a dead brand-new laptop to the platform where I bought it?"),
    make_turn(9, "agent", "Our portal only handles damage claims reported within two days of arrival. Beyond that window, ShopEase takes no responsibility for defective merchandise."),
    make_turn(10, "customer", "That is outrageous. What warranty coverage does this computer even have then?"),
    make_turn(11, "agent", "Standard laptop warranties through our portal cover manufacturing defects for only six months from the purchase date."),
    make_turn(12, "customer", "Six months? Every computer in India comes with at least a full year of warranty!"),
    make_turn(13, "agent", "Our platform partner agreements provide six months coverage unless an extended warranty pack was separately purchased."),
    make_turn(14, "customer", "I will be contacting consumer affairs regarding this policy. Goodbye."),
    make_turn(15, "agent", "You are free to do so, ma'am. Thank you for contacting ShopEase."),
    make_turn(16, "customer", "Good day."),
]

CALLS_DATA.append({
    "id": "call_203",
    "topic": "warranty",
    "quality": "bad_deviation",
    "split": "test",
    "applicable_sops": ["general_call_flow"],
    "applicable_steps": GEN_STEPS,
    "hold_scenario": "none",
    "customer_name": "Deepa Sundaram",
    "agent_name": "Vikram Malhotra",
    "order_id": "ORD-33910",
    "registered_phone_last4": "5271",
    "customer_persona": "Deepa Sundaram received a defective laptop 5 days ago and is denied return or 1-year warranty coverage.",
    "verified": True,
    "verification_notes": "Passed verification of credentials and identity.",
    "turns": t203,
    "ground_truth": {
        "sop_steps": {**all_followed(), "GEN-06": "missed"},
        "policy_violations": [
            {
                "turn": 7,
                "said": t203[6]["text"],
                "clause_id": "REF-1.1",
                "severity": "major",
                "correct_fact": "Electronics are eligible for return or replacement within 7 calendar days of delivery date.",
            },
            {
                "turn": 11,
                "said": t203[10]["text"],
                "clause_id": "WAR-1.1",
                "severity": "minor",
                "correct_fact": "All electronic products carry a minimum manufacturer warranty period of 12 months.",
            },
        ],
        "customer_emotion_arc": ["neutral", "frustrated", "angry"],
        "gaps": [],
    },
})

# ==============================================================================
# call_204: billing, BAD (15 days double charge -> BIL-1.2, retroactive price match -> BIL-2.2)
# ==============================================================================
t204 = [
    make_turn(1, "agent", "Thank you for reaching out to ShopEase customer care. My name is Sunita Joshi. Please note that this interaction is recorded for training and quality verification. How can I help you?"),
    make_turn(2, "customer", "Hello Sunita, I am Farhan Akhtar. I bought wireless headphones yesterday under order ORD-91047, but my bank app shows two separate debit deductions of Rs 4,999 for the same purchase."),
    make_turn(3, "agent", "I would be glad to check your billing ledger, Mr. Akhtar. May I have your Order ID and the last four digits of your registered mobile number for account confirmation?"),
    make_turn(4, "customer", "Yes, the order is ORD-91047 and my phone number ends in 6483."),
    make_turn(5, "agent", "Thank you, Mr. Akhtar, your profile is confirmed. Let me check the payment gateway receipts."),
    make_turn(6, "customer", "Also, while you check, I saw on your homepage that these exact headphones are now listed for Rs 4,499 in today's lightning deal."),
    make_turn(7, "agent", "Duplicate charges on banking gateways happen occasionally. Our finance clearing cycle for reconciling duplicate charges takes fifteen business days before we can initiate the credit."),
    make_turn(8, "customer", "Fifteen business days? That is three full weeks to return my own money when your system charged me twice!"),
    make_turn(9, "agent", "Bank settlement batch files run on a scheduled semi-monthly cadence, so that is the standard duration for reconciling double debits."),
    make_turn(10, "customer", "That is an awful long time. What about the five hundred rupee difference for today's price reduction?"),
    make_turn(11, "agent", "Yes, absolutely! Since the price dropped within 24 hours of your purchase, I will go ahead and apply a retroactive price match of Rs 500 to your account."),
    make_turn(12, "customer", "Well, at least that is helpful. Will the Rs 500 come to my card?"),
    make_turn(13, "agent", "Yes, that adjustment will reflect alongside the duplicate transaction reversal."),
    make_turn(14, "customer", "Alright. Please make sure the duplicate charge reversal is expedited if possible."),
    make_turn(15, "agent", "I have logged the note in your transaction file. Is there anything else I may assist you with today?"),
    make_turn(16, "customer", "No, that is all. Thank you."),
]

CALLS_DATA.append({
    "id": "call_204",
    "topic": "billing",
    "quality": "bad_deviation",
    "split": "test",
    "applicable_sops": ["general_call_flow"],
    "applicable_steps": GEN_STEPS,
    "hold_scenario": "none",
    "customer_name": "Farhan Akhtar",
    "agent_name": "Sunita Joshi",
    "order_id": "ORD-91047",
    "registered_phone_last4": "6483",
    "customer_persona": "Farhan Akhtar was charged twice for headphones and asks about a price drop.",
    "verified": True,
    "verification_notes": "Passed authentication check.",
    "turns": t204,
    "ground_truth": {
        "sop_steps": {**all_followed(), "GEN-06": "missed"},
        "policy_violations": [
            {
                "turn": 7,
                "said": t204[6]["text"],
                "clause_id": "BIL-1.2",
                "severity": "major",
                "correct_fact": "Duplicate charges must be verified and initiated for refund within 24 to 48 hours.",
            },
            {
                "turn": 11,
                "said": t204[10]["text"],
                "clause_id": "BIL-2.2",
                "severity": "minor",
                "correct_fact": "ShopEase does not offer retroactive price matching or post-purchase price drop adjustments.",
            },
        ],
        "customer_emotion_arc": ["neutral", "frustrated", "neutral"],
        "gaps": [],
    },
})

# ==============================================================================
# call_205: complaint, BAD (refuse supervisor -> ESC-1.1, legal threat dismiss -> ESC-2.1, no formal ticket -> ESC-3.1)
# ==============================================================================
t205 = [
    make_turn(1, "agent", "Thank you for calling ShopEase. My name is Deepak Roy. Please note this call is recorded for quality and regulatory compliance. How can I assist you?"),
    make_turn(2, "customer", "Deepak, this is Kavita Nair. I am beyond furious. I received a smashed convection oven ten days ago, three of your agents promised callbacks that never happened, and I demand to speak to your shift supervisor immediately."),
    make_turn(3, "agent", "I understand you are upset, Ms. Nair. To locate your ongoing service request, please provide your Order ID and the last four digits of your phone number."),
    make_turn(4, "customer", "Order ID is ORD-18452 and my phone number ends in 1592. Now connect me to your manager!"),
    make_turn(5, "agent", "Thank you, Ms. Nair, your details match the account. Let me review the case history."),
    make_turn(6, "customer", "Do not review anything, just transfer the call. I have spent hours explaining this."),
    make_turn(7, "agent", "I cannot transfer your call to a supervisor right now because our managerial queue is closed for the day, and we do not provide callbacks from managers."),
    make_turn(8, "customer", "What do you mean you don't provide callbacks? Your frontline staff has failed to resolve a damaged product for over a week!"),
    make_turn(9, "agent", "Our managers only handle high-tier enterprise accounts, not retail individual purchases."),
    make_turn(10, "customer", "That is ridiculous! If you will not escalate this to a supervisor right now, I am having my lawyer serve a formal legal notice for consumer court proceedings tomorrow!"),
    make_turn(11, "agent", "You are free to send whatever legal notices you want, consumer courts take years anyway so our legal team will look at it whenever they receive it."),
    make_turn(12, "customer", "Are you serious? You are daring a customer to sue you? Give me your formal incident complaint reference number right now!"),
    make_turn(13, "agent", "There is no special incident reference number; your order ID is your reference."),
    make_turn(14, "customer", "No, I want an escalation grievance ticket number logged in your CRM!"),
    make_turn(15, "agent", "I am not creating an escalation ticket right now. You can just dial back our helpline next week when the regular shift managers are available."),
    make_turn(16, "customer", "I am recording this entire call and sending it to national consumer protection. You will hear from my lawyer."),
    make_turn(17, "agent", "That is your prerogative, ma'am. Thank you for calling ShopEase."),
    make_turn(18, "customer", "Goodbye!"),
]

CALLS_DATA.append({
    "id": "call_205",
    "topic": "complaint",
    "quality": "bad_deviation",
    "split": "test",
    "applicable_sops": ["general_call_flow"],
    "applicable_steps": GEN_STEPS,
    "hold_scenario": "none",
    "customer_name": "Kavita Nair",
    "agent_name": "Deepak Roy",
    "order_id": "ORD-18452",
    "registered_phone_last4": "1592",
    "customer_persona": "Kavita Nair has an unresolved damaged oven and faces dismissive refusal of escalation and grievance logging.",
    "verified": True,
    "verification_notes": "Passed verification of customer credentials.",
    "turns": t205,
    "ground_truth": {
        "sop_steps": {**all_followed(), "GEN-06": "missed"},
        "policy_violations": [
            {
                "turn": 7,
                "said": t205[6]["text"],
                "clause_id": "ESC-1.1",
                "severity": "critical",
                "correct_fact": "Supervisor transfer requests must be completed within 2 minutes hold or scheduled for callback within 4 hours.",
            },
            {
                "turn": 11,
                "said": t205[10]["text"],
                "clause_id": "ESC-2.1",
                "severity": "critical",
                "correct_fact": "Legal notices or regulatory escalation threats must be transferred to the Grievance Officer within 24 hours.",
            },
            {
                "turn": 15,
                "said": t205[14]["text"],
                "clause_id": "ESC-3.1",
                "severity": "major",
                "correct_fact": "A formal escalation complaint ticket with a unique tracking number must be registered within 2 hours.",
            },
        ],
        "customer_emotion_arc": ["angry", "furious", "furious"],
        "gaps": [],
    },
})

# ==============================================================================
# call_206: shipping, BAD (address disclosure -> PRV-1.1, no OTP for phone -> SHP-3.1)
# ==============================================================================
t206 = [
    make_turn(1, "agent", "Welcome to ShopEase support. My name is Manoj Gupta. Please note that this phone call is recorded for quality and evaluation purposes. How may I help you?"),
    make_turn(2, "customer", "Hi Manoj, I am Siddharth Mehta. I placed an order for a new smartphone, but I will be out of town tomorrow when it is supposed to arrive."),
    make_turn(3, "agent", "Good morning, I have pulled up your pending shipment for the flagship smartphone heading to your residency at Green Glen Layout."),
    make_turn(4, "customer", "Yes, that is the one. Can the delivery boy leave the parcel with my apartment security guard at the gate?"),
    make_turn(5, "agent", "Let me check the handling specifications for this shipment."),
    make_turn(6, "customer", "It is order ORD-57209 and cost around forty thousand rupees, so I want to make sure it is safe."),
    make_turn(7, "agent", "Yes, that is completely fine. For high-value smartphones, the delivery partner does not need any delivery OTP or signature; they will simply drop the box with your building guard at the main gate."),
    make_turn(8, "customer", "Wait, they don't need an OTP? Isn't an expensive phone vulnerable to getting misplaced by guards?"),
    make_turn(9, "agent", "Our couriers routinely leave electronics packages with reception desks or security checkpoints without requesting one-time passcodes."),
    make_turn(10, "customer", "Are you sure? I thought costly electronics always required the customer to share a secret code at handover."),
    make_turn(11, "agent", "No, the courier app allows the delivery agent to mark it delivered upon physical handover to any building staff."),
    make_turn(12, "customer", "That sounds risky to me. Can I request a delivery reschedule instead so they deliver when I am back on Monday?"),
    make_turn(13, "agent", "I have updated the courier dispatch remarks to hold the parcel for Monday delivery."),
    make_turn(14, "customer", "Okay, please make sure they ask for my OTP when they hand it to me on Monday."),
    make_turn(15, "agent", "Certainly. Your shipment will be held until Monday. Thank you for choosing ShopEase, have a great day."),
    make_turn(16, "customer", "Thank you, goodbye."),
]

CALLS_DATA.append({
    "id": "call_206",
    "topic": "shipping",
    "quality": "bad_deviation",
    "split": "test",
    "applicable_sops": ["general_call_flow"],
    "applicable_steps": GEN_STEPS,
    "hold_scenario": "none",
    "customer_name": "Siddharth Mehta",
    "agent_name": "Manoj Gupta",
    "order_id": "ORD-57209",
    "registered_phone_last4": "4730",
    "customer_persona": "Siddharth Mehta inquires about delivery handover for a high-value phone.",
    "verified": True,
    "verification_notes": "Passed verification checklist.",
    "turns": t206,
    "ground_truth": {
        "sop_steps": {**all_followed(), "GEN-02": "missed", "GEN-06": "missed"},
        "policy_violations": [
            {
                "turn": 3,
                "said": t206[2]["text"],
                "clause_id": "PRV-1.1",
                "severity": "critical",
                "correct_fact": "Account and address information cannot be revealed before verifying Order ID and the last four phone digits.",
            },
            {
                "turn": 7,
                "said": t206[6]["text"],
                "clause_id": "SHP-3.1",
                "severity": "major",
                "correct_fact": "High-value electronics strictly mandate secure delivery OTP verification; couriers cannot deliver without OTP.",
            },
        ],
        "customer_emotion_arc": ["neutral", "confused", "neutral"],
        "gaps": [],
    },
})

# ==============================================================================
# call_207: warranty, BAD (45 day turnaround -> WAR-2.1, ask CVV over phone -> PRV-1.2)
# ==============================================================================
t207 = [
    make_turn(1, "agent", "Thank you for contacting ShopEase service desk. My name is Arpita Bose. This call is monitored and recorded for quality assurance. How can I help you today?"),
    make_turn(2, "customer", "Hi Arpita, this is Sunita Rao. I purchased a robotic vacuum cleaner three months ago under order ORD-42318, and the charging dock has stopped recognizing the robot."),
    make_turn(3, "agent", "I am sorry about the charging fault, Ms. Rao. Before we arrange service, could you please verify your Order ID and the last four digits of your mobile number?"),
    make_turn(4, "customer", "The order number is ORD-42318 and the last four digits of my phone are 8261."),
    make_turn(5, "agent", "Thank you, Ms. Rao, your warranty details are retrieved. Let me check the service turnaround parameters."),
    make_turn(6, "customer", "How long will the authorized repair workshop take to fix the dock? I rely on it every day."),
    make_turn(7, "agent", "Our service center is currently facing a heavy backlog, so standard repair turnaround time is forty-five days, and we cannot offer any replacement unit or refund while it is under evaluation."),
    make_turn(8, "customer", "Forty-five days? That is a month and a half! Is there no way to get it repaired faster or get a temporary loaner?"),
    make_turn(9, "agent", "We do not supply loaner machines during repairs."),
    make_turn(10, "customer", "Can I pay an express fee to fast-track the technician inspection?"),
    make_turn(11, "agent", "If you want priority VIP service dispatch, you can pay an expedited handling fee of Rs 350 right now; please read out your card number, expiry, and the three-digit CVV on the back over the phone."),
    make_turn(12, "customer", "Wait, read my CVV to you? Aren't phone agents forbidden from collecting credit card security numbers?"),
    make_turn(13, "agent", "Our phone booking terminal needs manual authorization, which requires entering the CVV code directly into our system."),
    make_turn(14, "customer", "I am definitely not giving my CVV over an unencrypted phone line. That sounds completely unsafe."),
    make_turn(15, "agent", "Understood. Then we will proceed with the regular 45-day queue. Your service request ticket is WRN-90214."),
    make_turn(16, "customer", "I will complain about this. Goodbye."),
]

CALLS_DATA.append({
    "id": "call_207",
    "topic": "warranty",
    "quality": "bad_deviation",
    "split": "test",
    "applicable_sops": ["general_call_flow"],
    "applicable_steps": GEN_STEPS,
    "hold_scenario": "none",
    "customer_name": "Sunita Rao",
    "agent_name": "Arpita Bose",
    "order_id": "ORD-42318",
    "registered_phone_last4": "8261",
    "customer_persona": "Sunita Rao wants warranty service for her robotic vacuum and is quoted 45 days and asked for CVV.",
    "verified": True,
    "verification_notes": "Passed authentication check.",
    "turns": t207,
    "ground_truth": {
        "sop_steps": {**all_followed(), "GEN-06": "missed"},
        "policy_violations": [
            {
                "turn": 7,
                "said": t207[6]["text"],
                "clause_id": "WAR-2.1",
                "severity": "major",
                "correct_fact": "Authorized service center turnaround SLA is 14 days maximum; if exceeded, a brand replacement or refund is mandatory.",
            },
            {
                "turn": 11,
                "said": t207[10]["text"],
                "clause_id": "PRV-1.2",
                "severity": "critical",
                "correct_fact": "Representatives must never solicit or record CVV codes, bank passwords, or debit card PINs under any circumstances.",
            },
        ],
        "customer_emotion_arc": ["neutral", "shocked", "distrustful"],
        "gaps": [],
    },
})

# ==============================================================================
# call_208: billing, BAD (7 day invoice -> BIL-2.1, repeat contact priority denied -> ESC-1.2)
# ==============================================================================
t208 = [
    make_turn(1, "agent", "Thank you for reaching ShopEase customer service. My name is Manish Das. This call is recorded for quality monitoring purposes. How can I help you today?"),
    make_turn(2, "customer", "Hi Manish, my name is Amit Sengupta. I bought a 4K monitor under order ORD-79163 for my consulting firm, but your team printed the incorrect corporate GSTIN on the tax invoice."),
    make_turn(3, "agent", "I would be happy to check that for you, Mr. Sengupta. May I please have your Order ID and the last four digits of your registered contact number?"),
    make_turn(4, "customer", "The order number is ORD-79163 and my phone number ends with 7354."),
    make_turn(5, "agent", "Thank you, Mr. Sengupta, your account details are verified. Let me inspect the invoice details."),
    make_turn(6, "customer", "I need the corrected invoice immediately for tax filing. How soon can you regenerate it?"),
    make_turn(7, "agent", "Regenerating a commercial invoice with updated tax identifiers requires manual audit by accounting, which takes seven business days to issue."),
    make_turn(8, "customer", "Seven business days? That is unacceptable! Today is the 18th and our monthly GST filing deadline is tomorrow!"),
    make_turn(9, "agent", "Our billing system updates corporate tax credits on a weekly consolidation schedule, so seven days is standard."),
    make_turn(10, "customer", "This is my fourth time calling regarding this invoice; your previous agents promised it would be done, but nothing happened. Can you please escalate this to your priority resolution desk?"),
    make_turn(11, "agent", "I understand you have called four times, but our team handles every call in standard first-in first-out sequence. We cannot provide priority routing or queue jumps just because you have contacted us multiple times."),
    make_turn(12, "customer", "Are you telling me that a customer who has called four times on an unfulfilled ticket gets zero escalation priority?"),
    make_turn(13, "agent", "That is correct, all open requests are processed strictly by the general queue."),
    make_turn(14, "customer", "I will be escalating this to our account manager and the corporate sales director."),
    make_turn(15, "agent", "I will add your notes to the billing record. Is there anything else I can assist with?"),
    make_turn(16, "customer", "No, nothing else."),
]

CALLS_DATA.append({
    "id": "call_208",
    "topic": "billing",
    "quality": "bad_deviation",
    "split": "test",
    "applicable_sops": ["general_call_flow"],
    "applicable_steps": GEN_STEPS,
    "hold_scenario": "none",
    "customer_name": "Amit Sengupta",
    "agent_name": "Manish Das",
    "order_id": "ORD-79163",
    "registered_phone_last4": "7354",
    "customer_persona": "Amit Sengupta is calling for the 4th time about an urgent corporate GST invoice.",
    "verified": True,
    "verification_notes": "Passed authentication check.",
    "turns": t208,
    "ground_truth": {
        "sop_steps": {**all_followed(), "GEN-06": "missed"},
        "policy_violations": [
            {
                "turn": 7,
                "said": t208[6]["text"],
                "clause_id": "BIL-2.1",
                "severity": "minor",
                "correct_fact": "Corrected tax invoices and billing amendments must be regenerated and provided within 24 hours.",
            },
            {
                "turn": 11,
                "said": t208[10]["text"],
                "clause_id": "ESC-1.2",
                "severity": "major",
                "correct_fact": "Repeated customer contacts with 3 or more interactions on the same unaddressed issue mandate priority escalation routing.",
            },
        ],
        "customer_emotion_arc": ["frustrated", "angry", "furious"],
        "gaps": [],
    },
})

# ==============================================================================
# call_209: complaint, BAD (social media ignore -> ESC-2.2, indefinite repair -> WAR-2.1, Rs 8500 approval -> REF-3.1)
# ==============================================================================
t209 = [
    make_turn(1, "agent", "Thank you for contacting ShopEase. My name is Neeraj Tiwari. This call is being recorded for quality and regulatory assurance. How may I help you?"),
    make_turn(2, "customer", "Neeraj, I am Meera Patel. Ten days ago I received a 55-inch OLED television with a cracked screen under order ORD-25830, and your inspection team has not even visited yet!"),
    make_turn(3, "agent", "I sincerely apologize for the delay, Ms. Patel. To access your open complaint file, could you please confirm your Order ID and the last four digits of your registered phone number?"),
    make_turn(4, "customer", "Order ID is ORD-25830 and my mobile ends in 2098."),
    make_turn(5, "agent", "Thank you, Ms. Patel, your records are verified. Let me review the case history."),
    make_turn(6, "customer", "If this television issue is not settled today, I have already edited a video clip of the cracked screen and the unkept technician promises, and I am tagging consumer watchdogs and publishing it on Twitter and Instagram!"),
    make_turn(7, "agent", "Go ahead and post on social media if you want, Twitter posts do not impact our operational queue and our executive team does not monitor social media grievances."),
    make_turn(8, "customer", "You really don't care about public complaints? What about fixing the television screen then?"),
    make_turn(9, "agent", "I can arrange a technician visit to assess the glass panel replacement."),
    make_turn(10, "customer", "How long will the screen replacement take once they assess it?"),
    make_turn(11, "agent", "During festival months, panel replacement turnaround times are indefinite; it could take several months and we cannot commit to any timeline."),
    make_turn(12, "customer", "Several months for a brand-new television? This is criminal negligence! I spent seventy thousand rupees!"),
    make_turn(13, "agent", "I understand your anger, Ms. Patel. Let me see what immediate compensation I can arrange right now."),
    make_turn(14, "customer", "What can you possibly offer right now?"),
    make_turn(15, "agent", "To close your complaint right now without further delay, I am approving an immediate goodwill refund of Rs 8,500 directly into your bank account on my own authority."),
    make_turn(16, "customer", "Eight thousand five hundred rupees? The TV cost seventy thousand! A token refund does not fix a shattered screen!"),
    make_turn(17, "agent", "That is the maximum discretionary allowance I can release to resolve this issue today."),
    make_turn(18, "customer", "I am posting that video right now. Goodbye!"),
]

CALLS_DATA.append({
    "id": "call_209",
    "topic": "complaint",
    "quality": "bad_deviation",
    "split": "test",
    "applicable_sops": ["general_call_flow"],
    "applicable_steps": GEN_STEPS,
    "hold_scenario": "none",
    "customer_name": "Meera Patel",
    "agent_name": "Neeraj Tiwari",
    "order_id": "ORD-25830",
    "registered_phone_last4": "2098",
    "customer_persona": "Meera Patel has an uninspected shattered TV and threatens viral social media exposure.",
    "verified": True,
    "verification_notes": "Passed authentication check.",
    "turns": t209,
    "ground_truth": {
        "sop_steps": {**all_followed(), "GEN-06": "missed"},
        "policy_violations": [
            {
                "turn": 7,
                "said": t209[6]["text"],
                "clause_id": "ESC-2.2",
                "severity": "major",
                "correct_fact": "Threats of public social media exposure must be logged and escalated through the dedicated social grievance workflow.",
            },
            {
                "turn": 11,
                "said": t209[10]["text"],
                "clause_id": "WAR-2.1",
                "severity": "major",
                "correct_fact": "Warranty service center repair times cannot exceed 14 days, beyond which a replacement unit or refund is mandatory.",
            },
            {
                "turn": 15,
                "said": t209[14]["text"],
                "clause_id": "REF-3.1",
                "severity": "critical",
                "correct_fact": "Customer service agents may authorize refunds up to Rs 5,000 only; higher amounts require supervisory approval.",
            },
        ],
        "customer_emotion_arc": ["furious", "furious", "furious"],
        "gaps": [],
    },
})

# ==============================================================================
# call_210: shipping, GOOD (CLEAN CALL 1 - tracking juicer)
# ==============================================================================
t210 = [
    make_turn(1, "agent", "Thank you for calling ShopEase. My name is Swati Deshmukh. Please be advised that this call is recorded for quality monitoring and customer training purposes. How may I assist you today?"),
    make_turn(2, "customer", "Hi Swati, my name is Karthik Raman. I ordered a cold press juicer three days ago under order ORD-38149, and I wanted to check when it is scheduled to arrive at my address."),
    make_turn(3, "agent", "I would be happy to check your tracking status, Mr. Raman. For security verification, could you please confirm your Order ID and the last four digits of your registered mobile number?"),
    make_turn(4, "customer", "Sure, the order number is ORD-38149 and the last four digits of my mobile are 6145."),
    make_turn(5, "agent", "Thank you, Mr. Raman. That matches our records. Just to confirm, you are inquiring about the delivery timeline for your cold press juicer. Is that correct?"),
    make_turn(6, "customer", "Yes, exactly. I want to make sure someone is at home to receive it."),
    make_turn(7, "agent", "Thank you. I have checked the live logistics scan, and your parcel is currently out for delivery with our local courier partner. The expected delivery slot is between 2:00 PM and 5:00 PM today."),
    make_turn(8, "customer", "Oh, wonderful! Do I need to provide any verification when the courier arrives?"),
    make_turn(9, "agent", "Yes, because this appliance falls under our standard electronics security protocol, a 4-digit delivery OTP will be sent via SMS to your registered mobile number when the delivery agent is near your premises."),
    make_turn(10, "customer", "Understood. What happens if I am momentarily stepped out when they arrive?"),
    make_turn(11, "agent", "In the rare event that you miss the delivery, our courier policy requires up to three delivery attempts on consecutive business days before any shipment is returned, so you will not lose your order."),
    make_turn(12, "customer", "That is reassuring. Thank you so much for the clear explanation, Swati."),
    make_turn(13, "agent", "You are very welcome, Mr. Raman. To recap, your cold press juicer under order ORD-38149 is out for delivery today between 2 and 5 PM, requiring a 4-digit SMS OTP. Is there anything else I can assist you with?"),
    make_turn(14, "customer", "No, that answers everything. Thank you and have a wonderful day!"),
]

CALLS_DATA.append({
    "id": "call_210",
    "topic": "shipping",
    "quality": "good",
    "split": "test",
    "applicable_sops": ["general_call_flow"],
    "applicable_steps": GEN_STEPS,
    "hold_scenario": "none",
    "customer_name": "Karthik Raman",
    "agent_name": "Swati Deshmukh",
    "order_id": "ORD-38149",
    "registered_phone_last4": "6145",
    "customer_persona": "Karthik Raman is checking delivery arrival time for an appliance.",
    "verified": True,
    "verification_notes": "Passed verification of credentials and identity.",
    "turns": t210,
    "ground_truth": {
        "sop_steps": all_followed(),
        "policy_violations": [],
        "customer_emotion_arc": ["neutral", "satisfied", "satisfied"],
        "gaps": [],
    },
})

# ==============================================================================
# call_211: refund, GOOD (CLEAN CALL 2 - apparel return within 14 days)
# ==============================================================================
t211 = [
    make_turn(1, "agent", "Thank you for calling ShopEase. My name is Tarun Khanna. Please note that this conversation is recorded for quality assurance and training purposes. How may I help you today?"),
    make_turn(2, "customer", "Hello Tarun, I am Divya Nair. I purchased a woollen trench coat under order ORD-64072 ten days ago, but the fit across the shoulders is too tight, so I would like to return it."),
    make_turn(3, "agent", "I would be very happy to assist you with processing that return, Ms. Nair. To verify your identity, could you please share your Order ID and the last four digits of your registered mobile number?"),
    make_turn(4, "customer", "Yes, the order is ORD-64072 and my phone number ends in 9382."),
    make_turn(5, "agent", "Thank you, that matches our system records. Just to confirm, you are returning the woollen trench coat due to sizing, and you are seeking a refund. Is that correct?"),
    make_turn(6, "customer", "Yes, that is correct. I have not worn it outside, the price tags and packaging are intact."),
    make_turn(7, "agent", "Excellent. Since the trench coat is apparel, it falls under our non-electronics policy which provides a return window of 14 calendar days from delivery. Since you are on day ten, your return is well within the eligible window."),
    make_turn(8, "customer", "That is great to hear. The order total was Rs 3,200. Can that be approved?"),
    make_turn(9, "agent", "Yes, the purchase amount of Rs 3,200 is within my authorization threshold of Rs 5,000, so I have approved the return request immediately. Your return authorization ID is RTN-88204."),
    make_turn(10, "customer", "Thank you. When will the courier come to collect the coat?"),
    make_turn(11, "agent", "Our pickup partner will visit your address within 48 to 72 hours. Please keep the coat with its original tags and plastic cover ready for handover."),
    make_turn(12, "customer", "And how will the refund be issued? I paid using my ICICI debit card."),
    make_turn(13, "agent", "The refund of Rs 3,200 will be credited directly back to your original ICICI debit card within 5 to 7 business days following the warehouse quality inspection."),
    make_turn(14, "customer", "Perfect. That is very straightforward."),
    make_turn(15, "agent", "To summarize, return RTN-88204 for your trench coat is authorized with pickup within 48 to 72 hours, and a full refund of Rs 3,200 to your debit card within 5 to 7 business days post verification. Is there anything else I can help you with today?"),
    make_turn(16, "customer", "No, that is everything. Thank you so much for your efficient help, Tarun!"),
]

CALLS_DATA.append({
    "id": "call_211",
    "topic": "refund",
    "quality": "good",
    "split": "test",
    "applicable_sops": ["general_call_flow"],
    "applicable_steps": GEN_STEPS,
    "hold_scenario": "none",
    "customer_name": "Divya Nair",
    "agent_name": "Tarun Khanna",
    "order_id": "ORD-64072",
    "registered_phone_last4": "9382",
    "customer_persona": "Divya Nair is returning a trench coat within the 14-day apparel return window.",
    "verified": True,
    "verification_notes": "Passed verification check.",
    "turns": t211,
    "ground_truth": {
        "sop_steps": all_followed(),
        "policy_violations": [],
        "customer_emotion_arc": ["neutral", "satisfied", "satisfied"],
        "gaps": [],
    },
})

# ==============================================================================
# call_212: warranty, GOOD (CLEAN CALL 3, LONG CALL >3500 agent characters)
# ==============================================================================
t212 = [
    make_turn(1, "agent", "Thank you for contacting ShopEase customer care and technical support. My name is Shruti Saxena. Please note that this conversation is recorded for quality monitoring, internal training, and compliance purposes. How may I assist you with your appliance today?"),
    make_turn(2, "customer", "Good morning Shruti, my name is Harish Venkataraman. I purchased a 28-liter convection microwave oven about four months ago under order ORD-50916. Yesterday while heating dinner, the turntable stopped rotating and the unit made a strange buzzing sound. I would like to know how to resolve this under warranty."),
    make_turn(3, "agent", "I am truly sorry to hear that your convection microwave is malfunctioning and making an unusual buzzing noise, Mr. Venkataraman. I completely understand how essential a microwave is for daily family meals, and I will be very glad to guide you through both initial safety troubleshooting and scheduling an authorized technician visit. Before we access your technical file, could you please verify your Order ID and the last four digits of your registered mobile telephone number?"),
    make_turn(4, "customer", "Yes of course, the order number is ORD-50916 and my registered mobile number ends in 1740."),
    make_turn(5, "agent", "Thank you very much, Mr. Venkataraman. That information perfectly matches our central database records. Just to make sure that I have understood the situation completely: you have a 28-liter convection microwave oven delivered four months ago, the turntable mechanism has stopped turning, and there is a noticeable buzzing noise during heating cycles. Is that an accurate summary of what you are experiencing?"),
    make_turn(6, "customer", "Yes Shruti, that is exactly right. The light inside turns on, but the glass plate does not spin at all and the buzzing starts as soon as I press the start button."),
    make_turn(7, "agent", "Thank you for confirming those exact symptoms. For your electrical safety, first and foremost, please ensure that you disconnect the microwave from the main wall socket whenever it is not in use or when examining the cavity. I would like to conduct two basic physical checks that often resolve mechanical turntable stoppages without needing workshop disassembly. Are you currently near the microwave oven?"),
    make_turn(8, "customer", "Yes, I am standing right next to it in the kitchen, and it is unplugged right now."),
    make_turn(9, "agent", "Excellent. Please open the microwave door and carefully lift the round glass turntable plate. Underneath the glass plate, there is a plastic three-wheeled roller ring and a center drive coupler. Could you check whether the roller ring is seated properly in its circular track and whether the center coupler has any food debris or misalignment preventing it from engaging with the motor shaft?"),
    make_turn(10, "customer", "Let me check... The glass plate came off easily. The roller ring looks completely intact and clean, and the center plastic coupler seems to rotate by hand, but when I seat the glass plate back on it, it feels like the motor shaft underneath offers no resistance at all."),
    make_turn(11, "agent", "Thank you for performing that check so thoroughly. If the central drive coupler spins freely by hand without resistance from the reduction gearbox, that typically points to either an internal motor coupling failure or a disengaged synchronous drive motor underneath the chassis. Because this involves the internal electrical sub-assembly, I strongly advise against opening the bottom housing yourself, as high-voltage capacitors inside microwaves can retain dangerous electrical charge even when unplugged."),
    make_turn(12, "customer", "Understood, I definitely do not want to tinker with electrical components myself. Is this covered under the warranty?"),
    make_turn(13, "agent", "Yes, absolutely. Under our comprehensive electronics and domestic appliances policy, all major appliances sold on ShopEase carry a minimum manufacturer warranty of twelve months from the date of verified delivery. Since your appliance was delivered four months ago, your microwave is fully covered under the active manufacturer warranty for both functional parts and certified technician labor."),
    make_turn(14, "customer", "That is a big relief. Will I need to carry this heavy twenty-kilo oven to a service center myself, or can someone come to my house?"),
    make_turn(15, "agent", "Because convection microwaves are heavy kitchen appliances weighing over ten kilograms, our warranty service protocol includes complimentary doorstep technician service. You do not have to carry the appliance anywhere. An authorized brand technician will visit your residential address to inspect the turntable motor, test the electrical continuity, and carry out the required repair on-site."),
    make_turn(16, "customer", "That is wonderful. How soon can the technician visit?"),
    make_turn(17, "agent", "I am booking a priority doorstep service appointment for you right now. Under our customer service commitments, an authorized technician will be dispatched to your home within 24 to 48 hours. The service technician will contact you on your registered telephone number prior to arrival to confirm whether morning or afternoon suits you best."),
    make_turn(18, "customer", "What documents will I need to show the technician when they arrive at my home?"),
    make_turn(19, "agent", "You will only need to show two items: first, a digital or printed copy of your ShopEase tax invoice for order ORD-50916, which is readily downloadable from your ShopEase mobile app under your orders section, and second, the physical warranty booklet that was included inside the original manufacturer carton. The technician will verify the serial number located on the back panel of the microwave with the invoice record."),
    make_turn(20, "customer", "I have both the invoice downloaded on my phone and the booklet in the kitchen drawer, so that will be very easy."),
    make_turn(21, "agent", "That is perfect. Furthermore, I would like to reassure you regarding our resolution timeline policy: under our standard warranty terms, authorized service centers must resolve the repair within a maximum turnaround window of 14 calendar days. If for any reason the replacement turntable motor cannot be procured or the repair cannot be completed within 14 days, you will be automatically entitled to a brand-new replacement unit or a full refund of your purchase price."),
    make_turn(22, "customer", "That is an exceptionally reassuring policy. It gives me great peace of mind knowing there is a strict fourteen-day turnaround guarantee."),
    make_turn(23, "agent", "I am glad to provide that reassurance, Mr. Venkataraman. I have successfully registered your doorstep service request in our warranty system under ticket number WRN-74192. You will receive an SMS and email confirmation within ten minutes containing the service ticket reference, the authorized service center contact number, and the scheduled visit window."),
    make_turn(24, "customer", "Thank you so much, Shruti. You have been incredibly helpful, polite, and thorough throughout this call."),
    make_turn(25, "agent", "It was completely my pleasure to assist you, Mr. Venkataraman. To recap our discussion: your 28-liter convection microwave under order ORD-50916 is fully covered under the 12-month manufacturer warranty; we have logged service ticket WRN-74192 for complimentary doorstep inspection within 24 to 48 hours; please keep your invoice and warranty booklet ready; and the 14-day resolution guarantee applies. Is there anything else in the world I can assist you with today?"),
    make_turn(26, "customer", "No, Shruti, you have taken care of everything perfectly. Thank you again and have a wonderful day ahead."),
]

CALLS_DATA.append({
    "id": "call_212",
    "topic": "warranty",
    "quality": "good",
    "split": "test",
    "applicable_sops": ["general_call_flow"],
    "applicable_steps": GEN_STEPS,
    "hold_scenario": "none",
    "customer_name": "Harish Venkataraman",
    "agent_name": "Shruti Saxena",
    "order_id": "ORD-50916",
    "registered_phone_last4": "1740",
    "customer_persona": "Harish Venkataraman seeks warranty repair for a malfunctioning convection microwave turntable.",
    "verified": True,
    "verification_notes": "Passed authentication check.",
    "turns": t212,
    "ground_truth": {
        "sop_steps": all_followed(),
        "policy_violations": [],
        "customer_emotion_arc": ["concerned", "reassured", "satisfied"],
        "gaps": [],
    },
})

def main():
    OUT_TRANSCRIPTS.mkdir(parents=True, exist_ok=True)
    OUT_EXPECTED.parent.mkdir(parents=True, exist_ok=True)

    expected_dict = {}

    for call in CALLS_DATA:
        call_id = call["id"]
        # Write individual transcript JSON
        t_path = OUT_TRANSCRIPTS / f"{call_id}.json"
        with open(t_path, "w", encoding="utf-8") as f:
            json.dump(call, f, indent=2, ensure_ascii=False)
        
        # Build expected entry
        viols = []
        for v in call["ground_truth"]["policy_violations"]:
            viols.append({
                "clause": v["clause_id"],
                "severity": v["severity"],
                "turn": v["turn"],
            })
        
        expected_dict[call_id] = {
            "topic": {
                "label": call["topic"],
                "also_ok": [],
            },
            "violations": viols,
            "quality": call["quality"],
            "steps": call["ground_truth"]["sop_steps"],
        }
        
        # Check agent character count
        agent_chars = sum(len(t["text"]) for t in call["turns"] if t["speaker"] == "agent")
        print(f"Generated {call_id}: topic={call['topic']}, quality={call['quality']}, turns={len(call['turns'])}, violations={len(viols)}, agent_chars={agent_chars}")

    with open(OUT_EXPECTED, "w", encoding="utf-8") as f:
        json.dump(expected_dict, f, indent=2, ensure_ascii=False)

    print(f"\nSuccessfully wrote 12 transcripts to {OUT_TRANSCRIPTS}")
    print(f"Successfully wrote expected labels to {OUT_EXPECTED}")

if __name__ == "__main__":
    main()
