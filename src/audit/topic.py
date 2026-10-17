"""Topic detection module operating on rolling windows of turns for live assistance (Phase 2)."""

import logging
from typing import List
from .schemas import DialogueTurn, LiveWindowContext

logger = logging.getLogger(__name__)

TOPIC_KEYWORDS = {
    "refund_and_returns": ["refund", "return", "money back", "pickup", "bank account", "neft", "courier return"],
    "shipping_delivery": ["shipping", "delivery", "late", "courier", "tracking", "delay", "express delivery", "dispatch"],
    "warranty_replacement": ["warranty", "replacement", "damaged", "broken", "defective", "repair", "not working"],
    "billing_payments": ["charge", "double charged", "cod", "credit card", "upi", "invoice", "payment deduction"],
    "escalation": ["supervisor", "manager", "complaint", "escalate", "senior", "consumer court"],
    "privacy_identity_verification": ["otp", "verification", "phone number", "order id", "security question"]
}

def detect_topic_rolling_window(turns: List[DialogueTurn], window_size: int = 4) -> str:
    """Standalone function to detect customer intent / topic over recent turns."""
    recent_turns = turns[-window_size:] if len(turns) >= window_size else turns
    combined_text = " ".join([t.text.lower() for t in recent_turns])

    topic_scores = {}
    for topic, keywords in TOPIC_KEYWORDS.items():
        score = sum(combined_text.count(kw) for kw in keywords)
        topic_scores[topic] = score

    top_topic = max(topic_scores, key=topic_scores.get)
    if topic_scores[top_topic] > 0:
        return top_topic
    return "general_inquiry"

def get_live_window_context(turns: List[DialogueTurn], window_size: int = 4) -> LiveWindowContext:
    """Produces live context for real-time agent co-piloting."""
    topic = detect_topic_rolling_window(turns, window_size)
    recent = turns[-window_size:] if len(turns) >= window_size else turns

    # Default suggested script cues for the agent based on detected topic
    cues = {
        "refund_and_returns": ["Check if within 7 days for electronics or 14 days for general items."],
        "shipping_delivery": ["Remind customer standard shipping is 3-7 business days."],
        "warranty_replacement": ["Ask for photo proof within 48 hours for damaged items."],
        "billing_payments": ["Verify if payment was deducted from bank account."],
        "escalation": ["Offer supervisor callback if customer requested escalation twice."],
        "privacy_identity_verification": ["Verify Order ID and last 4 digits of phone before proceeding."]
    }

    return LiveWindowContext(
        window_turn_count=len(recent),
        detected_topic=topic,
        confidence=0.85 if topic != "general_inquiry" else 0.40,
        relevant_clause_ids=[],
        suggested_scripts=cues.get(topic, ["Listen actively and acknowledge customer request."])
    )
