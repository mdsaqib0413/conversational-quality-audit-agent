"""Build 8 hand-written, hand-checked labelled calls (call_101 .. call_108) into data/transcripts/.

Every label was written together with the dialogue and checked against data/policies and data/sops.
Violations are stored with `said` = the exact text of the agent turn (computed here), so the dataset tests pass.

  python scripts/build_handwritten_calls.py
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "transcripts"

PAUSES = [0.6, 0.9, 0.5, 1.1, 0.7, 0.4, 1.0, 0.8, 0.6, 1.2]
GEN = [f"GEN-0{i}" for i in range(1, 9)]
REF = [f"REF-S{i}" for i in range(1, 8)]
ANG = [f"ANG-0{i}" for i in range(1, 6)]   # ANG-06 (abusive language) does not apply to these calls


def A(text, pause=None, interrupts=False):
    return ("agent", text, pause, interrupts)


def C(text, pause=None, interrupts=False):
    return ("customer", text, pause, interrupts)


def all_followed(steps):
    return {s: "followed" for s in steps}


CALLS = []

# --------------------------------------------------------------------------- call_101: refund, GOOD (non-electronics, COD)
CALLS.append(dict(
    id="call_101", topic="refund", quality="good", split="train", sops=["general_call_flow", "refund_call_sop"], hold="none",
    persona="Pooja Menon is calm and polite; the kurta set she ordered is the wrong size.",
    agent="Sneha Iyer", customer="Pooja Menon", order="ORD-44210", last4="7186",
    steps=all_followed(GEN + REF), violations=[], gaps=[], arc=["neutral", "neutral", "satisfied"],
    turns=[
        A("Thank you for calling ShopEase. My name is Sneha Iyer. Please note that this call is recorded for quality assurance and training purposes. How may I help you today?"),
        C("Hi Sneha, this is Pooja Menon. I ordered a cotton kurta set last week but the size is too small for me, and I would like to return it and get a refund."),
        A("I would be happy to help with that, Ms. Menon. To verify your identity first, could you please share your Order ID and the last four digits of your registered mobile number?"),
        C("Sure, the order ID is ORD-44210 and the last four digits of my phone number are 7186."),
        A("Thank you, that matches our records. Just to confirm that I have understood correctly, you received the cotton kurta set in size M, it does not fit, and you would like to return it for a refund. Is that right?"),
        C("Yes, exactly. I should have ordered size L."),
        A("I am sorry for the inconvenience, Ms. Menon, and I will personally make sure this return is arranged smoothly for you. May I ask when the parcel was delivered?"),
        C("It was delivered nine days ago."),
        A("Thank you. A kurta set falls under the non-electronics category, which has a return window of 14 calendar days from delivery, so your return is eligible. Is the item unused and with the tags and original packaging intact?"),
        C("Yes, I only tried it once, the tags are still on and I have the packaging."),
        A("Perfect. Since the reason is a size issue, I do not need photographs. The order value is Rs 1,299, which is within my approval limit of Rs 5,000, so I can approve the refund right away."),
        C("That is great. How will I get the money back? I paid cash on delivery."),
        A("Since this was a cash on delivery order, our delivery partner cannot hand over cash. The refund will be sent by NEFT bank transfer to your verified bank account, within 5 to 7 business days after the reverse pickup and warehouse verification."),
        C("Okay, that works for me. When will the pickup happen?"),
        A("I have booked the reverse pickup, and it will be scheduled within 48 to 72 hours. Your return reference ticket is RTN-55120. Please keep the kurta set in its original packaging with the tags attached for the courier."),
        C("Alright, I will keep it ready."),
        A("To summarise, the return for order ORD-44210 is approved under ticket RTN-55120, pickup within 48 to 72 hours, and a refund of Rs 1,299 by NEFT within 5 to 7 business days after verification. Is there anything else I can help you with today?"),
        C("No, that is all. Thank you so much, Sneha."),
        A("It was my pleasure, Ms. Menon. Thank you for contacting ShopEase. Have a wonderful day!"),
        C("You too, goodbye."),
    ],
))

# --------------------------------------------------------------------------- call_102: refund, BAD (no verification, over limit, wallet refund)
CALLS.append(dict(
    id="call_102", topic="refund", quality="bad_deviation", split="test", sops=["general_call_flow", "refund_call_sop"], hold="none",
    persona="Vikram Rao is a calm customer with a flickering smartwatch screen; the agent breaks several rules.",
    agent="Ravi", customer="Vikram Rao", order="ORD-31877", last4="2250",
    steps={**all_followed(GEN + REF),
           "GEN-01": "partial", "GEN-02": "missed", "GEN-03": "missed", "GEN-04": "missed", "GEN-05": "missed", "GEN-06": "missed",
           "GEN-07": "partial", "GEN-08": "partial",
           "REF-S1": "missed", "REF-S2": "missed", "REF-S3": "partial", "REF-S4": "missed", "REF-S5": "missed", "REF-S6": "missed", "REF-S7": "missed"},
    violations=[
        (3, "PRV-1.1", "critical", "Account and order details such as the delivery address must not be disclosed before the Order ID and last four phone digits are verified."),
        (5, "REF-3.1", "critical", "Agents may approve refunds up to Rs 5,000 only; larger amounts need supervisor review and secondary authorization."),
        (7, "REF-2.2", "major", "Refunds go strictly to the original payment method used at checkout."),
        (9, "REF-2.1", "major", "Refunds are processed within 5 to 7 business days after successful return pickup and warehouse verification."),
    ],
    gaps=[], arc=["neutral", "confused", "confused"],
    turns=[
        A("Hello, ShopEase customer service. How can I help you?"),
        C("Hi, my name is Vikram Rao. I bought a Noise ColorFit smartwatch from your website four days ago and the screen keeps flickering. I want a refund, the price was Rs 8,500."),
        A("Okay Mr. Rao, no problem, I can see your order here, the smartwatch delivered to Flat 12, Sai Residency, Pune. I will process the refund right away."),
        C("Oh, that was quick. Do you not need my order number or anything?"),
        A("No, no need. The refund of Rs 8,500 is approved by me, I have full authority for this, so no supervisor is needed."),
        C("Okay. And how will I get the money back, to my card?"),
        A("I will send it to your Paytm wallet, that is the quickest way."),
        C("Alright. How long will it take to show up?"),
        A("It will be credited within 24 hours. You can keep the watch, no need to send it back."),
        C("Really? I can keep the watch as well? That is surprising, but okay."),
        A("Yes sir. Anything else?"),
        C("No, that is all."),
        A("Okay, bye."),
    ],
))

# --------------------------------------------------------------------------- call_103: billing, GOOD (duplicate debit)
CALLS.append(dict(
    id="call_103", topic="billing", quality="good", split="test", sops=["general_call_flow"], hold="none",
    persona="Arjun Nair is worried about a duplicate UPI debit but stays polite.",
    agent="Meera Pillai", customer="Arjun Nair", order="ORD-61905", last4="3340",
    steps=all_followed(GEN), violations=[], gaps=[], arc=["anxious", "neutral", "satisfied"],
    turns=[
        A("Thank you for calling ShopEase. My name is Meera Pillai. Please note that this call is recorded for quality assurance and training purposes. How may I help you today?"),
        C("Hello Meera, I am Arjun Nair. I placed an order yesterday and my bank statement shows that the payment of Rs 2,199 was deducted twice. I am quite worried about this double charge."),
        A("I understand your concern, Mr. Nair, and I will look into this right away. First, for your security, could you please share your Order ID and the last four digits of your registered mobile number?"),
        C("Yes, the order ID is ORD-61905 and the last four digits are 3340."),
        A("Thank you, you are verified. Just to make sure I have understood correctly, you placed one order for Rs 2,199 but your bank shows two debits of the same amount. Is that correct?"),
        C("Yes, that is exactly it. Two debits within a minute of each other, both through UPI."),
        A("I am sorry for the worry this has caused, Mr. Nair, and I will personally follow this through until it is resolved. Let me check the payment gateway logs."),
        C("Sure, please check."),
        A("I can see the second debit was caused by a gateway re-attempt while the first payment was being confirmed. It has already been flagged by our automated audit reconciliation as a duplicate."),
        C("Okay. So what happens to the extra amount?"),
        A("Under our policy, the full duplicate amount of Rs 2,199 is released to your original payment source, your UPI bank account, within 24 hours. After that, it can take 5 to 7 business days to show in your bank statement."),
        C("So it may take up to a week to see it in my statement?"),
        A("Yes, the release from our side happens within 24 hours, but the bank's own clearance can take 5 to 7 business days to reflect. Your actual order for Rs 2,199 is confirmed and will not be affected."),
        C("That is a relief. Will I get any confirmation?"),
        A("I have logged this under ticket number BIL-30871, and you will receive an SMS once the release is initiated."),
        C("Great, thank you."),
        A("To summarise, one duplicate debit of Rs 2,199 on order ORD-61905 has been flagged, the amount is released to your UPI source within 24 hours, and the bank statement will reflect it in 5 to 7 business days. The reference is BIL-30871. Is there anything else I can help you with?"),
        C("No, that covers everything. Thanks for sorting it out quickly."),
        A("You are most welcome, Mr. Nair. Thank you for contacting ShopEase. Have a great day!"),
        C("Bye."),
    ],
))

# --------------------------------------------------------------------------- call_104: billing, BAD (privacy breach before verification)
CALLS.append(dict(
    id="call_104", topic="billing", quality="bad_deviation", split="train", sops=["general_call_flow"], hold="none",
    persona="Suresh Gupta calls about his wife's order; the agent discloses details without verifying anyone.",
    agent="Karthik", customer="Suresh Gupta", order="ORD-20456", last4="4475",
    steps={**all_followed(GEN), "GEN-01": "partial", "GEN-02": "missed", "GEN-03": "missed", "GEN-04": "missed", "GEN-05": "missed",
           "GEN-06": "missed", "GEN-07": "partial", "GEN-08": "missed"},
    violations=[
        (5, "PRV-1.1", "critical", "Item, address and payment details must not be revealed before the Order ID and last four phone digits are verified."),
        (7, "BIL-2.1", "minor", "A duplicate charge is released to the original source within 24 hours and shows in the statement in 5 to 7 business days."),
    ],
    gaps=[], arc=["neutral", "frustrated", "neutral"],
    turns=[
        A("Hello, ShopEase support, tell me."),
        C("Hi, my wife placed an order on your website and there is a charge of Rs 4,750 on our bank statement. I want to know what this payment is for and where it was shipped."),
        A("Sure sir, give me your wife's name and I will check."),
        C("Her name is Anita Gupta. I do not have the order ID with me, and I do not know her phone number by heart."),
        A("No problem, I found it. The order is for a Prestige induction cooktop, Rs 4,750, paid with a debit card ending 4412, and it is shipped to Flat 8B, Lotus Residency, Linking Road, Bandra, Mumbai 400050."),
        C("Okay, that is what I wanted to know. But I see the same Rs 4,750 charged two times on our bank statement."),
        A("Yes, I can see two charges. The duplicate will be sorted out, it takes around 15 to 20 working days to come back."),
        C("That is very long. Can you not do it faster?"),
        A("That is the process sir, nothing can be done."),
        C("Fine. Please just note my complaint about the double charge."),
        A("Done sir. Anything else?"),
        C("No."),
        A("Okay."),
    ],
))

# --------------------------------------------------------------------------- call_105: complaint, GOOD (angry, escalation, callback)
CALLS.append(dict(
    id="call_105", topic="complaint", quality="good", split="train", sops=["general_call_flow", "angry_customer_sop", "hold_and_transfer_sop"], hold="callback",
    persona="Deepa Krishnan is angry about a mixer grinder stuck in transit; the agent stays composed and escalates correctly.",
    agent="Aman Gupta", customer="Deepa Krishnan", order="ORD-77302", last4="5521",
    steps={**all_followed(GEN + ANG), "HLD-01": "followed", "HLD-02": "followed", "HLD-03": "followed", "HLD-05": "followed"},
    violations=[], gaps=[], arc=["angry", "frustrated", "satisfied"],
    turns=[
        A("Thank you for calling ShopEase. My name is Aman Gupta. Please note that this call is recorded for quality assurance and training purposes. How may I assist you today?"),
        C("This is unacceptable! My name is Deepa Krishnan and I ordered a mixer grinder fifteen days ago. It was dispatched fourteen days ago and nobody gives me a straight answer. This is the third time I am calling and I am fed up."),
        A("I am truly sorry, Ms. Krishnan. I can hear how frustrating this has been, especially after calling three times, and I will personally take ownership of this until it is resolved. May I please have your Order ID and the last four digits of your registered mobile number?"),
        C("The order ID is ORD-77302 and the last four digits are 5521. Please just tell me where my parcel is."),
        A("Thank you, you are verified. Let me make sure I have this right: your mixer grinder was dispatched fourteen days ago with standard delivery, it has not been delivered, and you have already called us twice before. Is that correct?"),
        C("Yes! And each time they just say it is in transit."),
        A("Could I ask one quick question so I can pinpoint the problem: did you receive any out-for-delivery message or call from the courier in the last few days?"),
        C("No, nothing. Not a single message."),
        A("Thank you, that helps. Our standard delivery commitment is 3 to 7 business days, so your parcel is well beyond that commitment. Here is what I am doing right now: I am raising a logistics tracking ticket with the courier partner, and I am adding a goodwill wallet credit of Rs 100 to your account for this delay."),
        C("A hundred rupees? I want to speak to a supervisor right now, I want a proper answer from someone senior."),
        A("I understand, Ms. Krishnan. Let me first complete the logistics ticket for you, and then I will make sure someone senior hears you. The ticket number is LOG-88213 and the courier partner must respond within 48 hours."),
        C("Forty-eight more hours? I want a supervisor on this call now. This is the second time I am asking."),
        A("You are absolutely right to ask, and I am escalating this to a supervisor right now. May I place you on a brief hold for up to two minutes while I connect with them?"),
        C("Yes, go ahead."),
        A("Thank you for holding, Ms. Krishnan, and I apologise for the wait. Our supervisors are all assisting other escalated callers at the moment. Rather than keep you waiting, I can schedule a confirmed supervisor callback for you within the next 2 to 4 hours. Would that be acceptable?", pause=75.0),
        C("Fine. Please make sure someone actually calls. I have wasted enough time."),
        A("I will personally note this as a priority callback, Ms. Krishnan. The supervisor will call you on your registered number ending 5521 within 2 to 4 hours, and the logistics ticket LOG-88213 is already active with the courier. The Rs 100 wallet credit will be added to your account today."),
        C("Okay. That is something at least. Thank you for not just brushing me off."),
        A("Thank you for your patience. To recap: ticket LOG-88213 is raised with the courier with a 48 hour response, a Rs 100 goodwill credit is added, and a supervisor will call you within 2 to 4 hours. Is there anything else I can help you with?"),
        C("No, that is everything."),
        A("Thank you for contacting ShopEase, Ms. Krishnan. Have a good day, and again, I am sorry for the trouble."),
        C("Bye."),
    ],
))

# --------------------------------------------------------------------------- call_106: complaint, BAD (defensive, refuses escalation, long hold)
CALLS.append(dict(
    id="call_106", topic="complaint", quality="bad_deviation", split="test", sops=["general_call_flow", "angry_customer_sop", "hold_and_transfer_sop"], hold="hold_only",
    persona="Rahul Bose is furious about a monitor stuck in transit; the agent blames him, refuses a supervisor and leaves him on hold for over two minutes.",
    agent="Sunil", customer="Rahul Bose", order="ORD-90417", last4="1198",
    steps={**all_followed(GEN + ANG),
           "GEN-01": "followed", "GEN-02": "followed", "GEN-03": "partial", "GEN-04": "missed", "GEN-05": "missed", "GEN-06": "missed", "GEN-07": "missed", "GEN-08": "missed",
           "ANG-01": "missed", "ANG-02": "missed", "ANG-03": "missed", "ANG-04": "missed", "ANG-05": "missed",
           "HLD-01": "partial", "HLD-02": "missed", "HLD-03": "missed"},
    violations=[
        (7, "ESC-1.1", "critical", "A customer who asks for a supervisor twice must be escalated immediately."),
        (9, "SHP-2.3", "major", "Transit beyond 14 days without updates is declared lost: immediate full refund or priority reshipment, and a courier tracking ticket must be raised."),
    ],
    gaps=["interruption", "hold_too_long"], arc=["angry", "angry", "angry"],
    turns=[
        A("ShopEase customer care, Sunil speaking. Please note this call is recorded for quality assurance and training purposes. How may I help?"),
        C("I am calling about my order, a Samsung monitor that was dispatched fifteen days ago, and the tracking has not moved for the last ten days. This is ridiculous! Nobody has helped me in three calls."),
        A("Sir, you must have given the wrong address or a wrong phone number, these delays happen because of customer mistakes. Did you check your address before ordering? Are you sure the phone number was right?"),
        C("I gave the right address, I have ordered many times before. I want to speak to a manager."),
        A("Sir, managers do not handle delivery issues, I can check it for you. What is your order number?"),
        C("It is ORD-90417. And I am asking for a manager again, this is the second time."),
        A("Sir, I told you I cannot transfer you. It is showing in transit, the courier will deliver when it delivers."),
        C("In transit for fifteen days? This is unacceptable, I want my money back or a replacement."),
        A("Compensation or refund is not possible until thirty days are over, that is our rule. And there is no point creating a ticket, the courier will not respond."),
        C("That is the worst service I have ever seen, you people are cheating customers!"),
        A("Sir please listen, sir, listen to me, you are not allowing me to speak.", interrupts=True),
        C("I am done listening. I am filing a complaint in consumer court."),
        A("Okay sir, wait, I am putting you on hold, I will check with someone."),
        A("Hello sir, yes, nobody is available. Anything else?", pause=135.0),
        C("Nobody? Then what is the use of this call. Forget it."),
        A("Okay sir. Bye."),
    ],
))

# --------------------------------------------------------------------------- call_107: warranty, BAD (wrong policy, denies return)
CALLS.append(dict(
    id="call_107", topic="warranty", quality="bad_deviation", split="train", sops=["general_call_flow"], hold="none",
    persona="Neha Sethi has a dead earbud on day six; the agent wrongly says nothing can be done.",
    agent="Imran Sheikh", customer="Neha Sethi", order="ORD-52816", last4="8093",
    steps={**all_followed(GEN), "GEN-05": "partial", "GEN-06": "missed", "GEN-07": "partial"},
    violations=[
        (7, "WAR-1.2", "major", "After the 48-hour transit-damage window, the request proceeds under the regular manufacturer warranty claim process; it is not refused."),
        (7, "REF-1.1", "major", "Electronics can be returned within exactly 7 calendar days of delivery, so day six is still eligible."),
        (9, "WAR-1.1", "minor", "Electronics carry a minimum 12-month manufacturer warranty."),
    ],
    gaps=[], arc=["neutral", "frustrated", "frustrated"],
    turns=[
        A("Thank you for calling ShopEase. My name is Imran Sheikh. Please note that this call is recorded for quality assurance and training purposes. How may I help you today?"),
        C("Hi Imran, I am Neha Sethi. I bought boAt Airdopes six days ago and the left earbud is completely dead. I want to know what I can do."),
        A("Sorry to hear that, Ms. Sethi. For verification, please share your Order ID and the last four digits of your registered mobile number."),
        C("ORD-52816 and 8093."),
        A("Thank you. So the left earbud of your boAt Airdopes stopped working and you want a solution. Correct?"),
        C("Yes, that is right. It never worked since I opened the box."),
        A("I understand. Unfortunately, any defect has to be reported within 48 hours of delivery with photos, and since you are on day six, there is nothing we can do. No replacement, no return and no warranty claim is possible now."),
        C("No warranty at all? The box says one year warranty."),
        A("Warranty covers only six months for audio products, and it is void if you did not claim in the first two days."),
        C("That cannot be right. Can I at least return it? It is only day six."),
        A("I am sorry, that is our policy and I cannot do anything. Is there anything else?"),
        C("No, that is not helpful at all. I will check with the brand directly."),
        A("You can do that. Thank you for calling ShopEase, have a nice day."),
    ],
))

# --------------------------------------------------------------------------- call_108: shipping, GOOD (address change after dispatch)
CALLS.append(dict(
    id="call_108", topic="shipping", quality="good", split="test", sops=["general_call_flow"], hold="none",
    persona="Rohit Chawla moved house and wants to change the address of a shipped order.",
    agent="Farah Khan", customer="Rohit Chawla", order="ORD-38760", last4="6612",
    steps=all_followed(GEN), violations=[], gaps=[], arc=["neutral", "neutral", "satisfied"],
    turns=[
        A("Thank you for calling ShopEase. My name is Farah Khan. Please note that this call is recorded for quality assurance and training purposes. How may I assist you today?"),
        C("Hi Farah, I am Rohit Chawla. I moved to a new flat last week and I want to change the delivery address on an order I placed two days ago."),
        A("I would be glad to look into that, Mr. Chawla. First, could you please share your Order ID and the last four digits of your registered mobile number for verification?"),
        C("Sure, ORD-38760, and the last four digits are 6612."),
        A("Thank you, you are verified. To make sure I understand, you would like to change the delivery address for order ORD-38760 because you have moved. Is that right?"),
        C("Yes, exactly."),
        A("I understand how inconvenient a house move can be, and I will personally help you find the best option. Let me check the order status."),
        C("Okay."),
        A("I can see the order is already in Shipped status. Address changes are only possible while an order is Confirmed or Processing, and once it is shipped, none of our agents has system permission to alter the address or recipient name."),
        C("Oh no. Is there nothing at all I can do? I will not be at the old address."),
        A("There is one option. In such cases you can request a cancellation of this order and place a fresh order to your new address. Since the order has not been delivered yet, I can raise the cancellation request for you right now if you wish."),
        C("That sounds fine. Please cancel it and I will reorder with the new address."),
        A("Done, I have raised the cancellation request under ticket SHP-77412. Our team will confirm the cancellation by SMS, and any amount paid will return to your original payment method."),
        C("Great, thanks for explaining this clearly."),
        A("To summarise, the address cannot be changed on a shipped order, the cancellation request is raised under ticket SHP-77412, and you can place a fresh order with your new address. Is there anything else I can help you with?"),
        C("No, that is all."),
        A("Thank you for contacting ShopEase, Mr. Chawla. Have a wonderful day and best wishes for your new home!"),
        C("Thank you, goodbye."),
    ],
))


def build(c):
    turns = []
    for i, (spk, text, pause, interrupts) in enumerate(c["turns"], start=1):
        p = pause if pause is not None else (0.5 if i == 1 else PAUSES[i % len(PAUSES)])
        turns.append({"i": i, "speaker": spk, "text": text, "pause_before_sec": p, "interrupts_previous": interrupts})
    by_i = {t["i"]: t for t in turns}
    viol = []
    for turn, clause, sev, fact in c["violations"]:
        assert by_i[turn]["speaker"] == "agent", (c["id"], turn)
        viol.append({"turn": turn, "said": by_i[turn]["text"], "clause_id": clause, "severity": sev, "correct_fact": fact})
    return {
        "id": c["id"], "topic": c["topic"], "quality": c["quality"], "split": c["split"],
        "applicable_sops": c["sops"], "applicable_steps": list(c["steps"].keys()), "hold_scenario": c["hold"],
        "order_id": c["order"], "registered_phone_last4": c["last4"], "agent_name": c["agent"], "customer_name": c["customer"],
        "customer_persona": c["persona"], "verified": True,
        "verification_notes": "Hand-written and checked against data/policies and data/sops; labels written together with the dialogue.",
        "source": "handwritten",
        "turns": turns,
        "ground_truth": {"sop_steps": c["steps"], "policy_violations": viol, "customer_emotion_arc": c["arc"], "gaps": c["gaps"]},
    }


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for c in CALLS:
        data = build(c)
        (OUT / f"{c['id']}.json").write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"wrote {c['id']}: {c['topic']:<9} {c['quality']:<14} {len(data['turns'])} turns, "
              f"{sum(1 for s in c['steps'].values() if s != 'followed')} deviations, {len(c['violations'])} violations")


if __name__ == "__main__":
    main()
