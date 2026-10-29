"""Running conversational state computed in plain code from early call turns.

Ensures that long calls (>50 turns) preserve early critical milestones
(greeting, identity verification, recording disclosure, issue statement, early holds)
even when evaluating later chunks of the dialogue.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional, Sequence

from .schemas import DialogueTurn
from .telugu_utils import is_telugu

_BRAND_RE = re.compile(r"\b(shopease)\b|(?:షాపేజ్|షాపీజ్)", re.IGNORECASE)
_RECORD_RE = re.compile(r"\b(recorded|recording)\b|(?:రికార్డ్|నాణ్యత)", re.IGNORECASE)
_ORDER_ID_RE = re.compile(r"\b(ORD[\s\-]?\d{4,6})\b|(?:ఆర్డర్\s*ఐడి)", re.IGNORECASE)
_PHONE_DIGITS_RE = re.compile(r"\b(last\s*(four|4)\s*digits)\b|(?:చివరి\s*(నాలుగు|4)|ఫోన్\s*నంబర్)", re.IGNORECASE)
_ACCOUNT_DETAILS_RE = re.compile(
    r"\b(delivered\s*to|residency|flat\s*\d+|street|pincode|bank\s*account|wallet|(?:delivery\s+|your\s+)?address\s+(?:is|was|in|at|:)|rs\.?\s*\d+)\b|(?:విలాసం|అడ్రస్|రెసిడెన్సీ|ఫ్లాట్|ఖాతా|రూపాయ|రూ\.?)",
    re.IGNORECASE,
)
_HOLD_RE = re.compile(r"\b(hold|brief\s*hold)\b|(?:హోల్డ్|ఆగండి|లైన్లో\s*ఉండండి)", re.IGNORECASE)


@dataclass
class EarlyCallState:
    greeting_done: bool = False
    greeting_turn: Optional[int] = None
    recording_disclosed: bool = False
    recording_turn: Optional[int] = None
    verification_attempted: bool = False
    verification_turn: Optional[int] = None
    verification_completed: bool = False
    account_details_discussed: bool = False
    first_account_turn: Optional[int] = None
    first_account_quote: str = ""
    identity_verified_before_account: bool = False
    identity_breach_detected: bool = False
    issue_statement: str = ""
    issue_turn: Optional[int] = None
    holds_count: int = 0
    hold_turns: List[int] = field(default_factory=list)

    def format_for_prompt(self) -> str:
        """Compact context block passed into prompt chunks."""
        v_status = (
            "VERIFIED_BEFORE_ACCOUNT"
            if self.identity_verified_before_account
            else ("BREACH_ACCOUNT_DISCUSSED_BEFORE_VERIFICATION" if self.identity_breach_detected else "NOT_YET_VERIFIED")
        )
        lines = [
            f"- Greeting completed: {self.greeting_done} (turn {self.greeting_turn or 'none'})",
            f"- Recording disclosed: {self.recording_disclosed} (turn {self.recording_turn or 'none'})",
            f"- Identity verification status: {v_status}",
            f"- First account details turn: {self.first_account_turn or 'none'}",
            f"- Customer issue stated: '{self.issue_statement or 'unknown'}' (turn {self.issue_turn or 'none'})",
            f"- Holds so far: {self.holds_count}",
        ]
        return "\n".join(lines)


def compute_call_state(turns: Sequence[DialogueTurn], early_window: int = 15) -> EarlyCallState:
    """Analyze the conversational trajectory and produce a deterministic state."""
    state = EarlyCallState()
    early_turns = turns[:early_window]

    # 1. Opening greeting & recording disclosure
    for t in early_turns:
        if t.speaker == "agent":
            if not state.greeting_done and _BRAND_RE.search(t.text):
                state.greeting_done = True
                state.greeting_turn = t.turn_id
            if not state.recording_disclosed and _RECORD_RE.search(t.text):
                state.recording_disclosed = True
                state.recording_turn = t.turn_id

    # 2. Identity verification & Account details sequencing
    for t in turns:
        # Check hold events
        if _HOLD_RE.search(t.text):
            state.holds_count += 1
            state.hold_turns.append(t.turn_id)

        # Check customer issue statement
        if t.speaker == "customer" and not state.issue_statement and len(t.text.split()) >= 3:
            state.issue_statement = t.text[:120].strip()
            state.issue_turn = t.turn_id

        # Verification check
        if t.speaker == "agent":
            has_order = bool(_ORDER_ID_RE.search(t.text))
            has_phone = bool(_PHONE_DIGITS_RE.search(t.text))
            if has_order or has_phone:
                state.verification_attempted = True
                if not state.verification_turn:
                    state.verification_turn = t.turn_id
                if has_order and has_phone:
                    state.verification_completed = True

        # Customer providing verification
        if t.speaker == "customer":
            has_order_ans = bool(_ORDER_ID_RE.search(t.text))
            has_phone_ans = bool(re.search(r"\b\d{4}\b", t.text))
            if has_order_ans and has_phone_ans:
                state.verification_completed = True

        # Check account details disclosure
        if t.speaker == "agent":
            if _ACCOUNT_DETAILS_RE.search(t.text):
                if not state.account_details_discussed:
                    state.account_details_discussed = True
                    state.first_account_turn = t.turn_id
                    state.first_account_quote = " ".join(t.text.split()[:15])

    # Sequencing logic: did verification complete before account details were discussed?
    if state.account_details_discussed:
        if state.verification_completed and state.verification_turn and state.verification_turn < state.first_account_turn:
            state.identity_verified_before_account = True
            state.identity_breach_detected = False
        else:
            state.identity_verified_before_account = False
            state.identity_breach_detected = True
    elif state.verification_completed:
        state.identity_verified_before_account = True
        state.identity_breach_detected = False

    return state

