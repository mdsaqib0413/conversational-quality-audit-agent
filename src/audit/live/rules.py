"""Deterministic LiveRules engine for streaming caption events."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import re
from typing import Any, Dict, List, Optional, Sequence, Set

from ..topic import _ANGER, detect_topic


@dataclass
class LiveAlert:
    """Alert emitted by the live rules engine upon detecting a compliance risk or event."""
    rule_id: str
    severity: str  # "danger" | "warning" | "info"
    time_sec: float
    triggering_quote: str
    related_step_or_clause: str
    message: str
    turn_id: Optional[int] = None

    @property
    def time(self) -> float:
        """Alias for time_sec."""
        return self.time_sec

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


DEFAULT_LIVE_CONFIG: Dict[str, Any] = {
    # GEN-02: Recording disclosure missing after agent's first N turns
    "disclosure_max_agent_turns": 2,
    # GEN-03: Two-factor caller verification
    "require_order_id": True,
    "require_phone_last4": True,
    # HLD-02: Maximum hold ceiling in seconds
    "max_hold_seconds": 120.0,
    # COM-01: Dead air threshold in seconds
    "dead_air_threshold_sec": 4.0,
    # Overlap threshold in seconds
    "overlap_threshold_sec": 0.2,
    # ANG-02: Agent turns allowed to acknowledge customer anger
    "empathy_window_turns": 2,
    # Topic detection & retrieval window
    "topic_window_turns": 6,
    "clause_top_k": 4,
}

_RECORD_RE = re.compile(r"\b(recorded|recording|monitored|quality\s*assurance)\b|(?:రికార్డ్|నాణ్యత)", re.IGNORECASE)
_ORDER_ID_RE = re.compile(r"\b(ORD[\s\-]?\d{4,6})\b|(?:ఆర్డర్\s*ఐడి)", re.IGNORECASE)
_PHONE_DIGITS_RE = re.compile(r"\b(last\s*(four|4)\s*digits)\b|(?:చివరి\s*(నాలుగు|4)|ఫోన్\s*నంబర్)", re.IGNORECASE)
_DIGITS_4_RE = re.compile(r"\b\d{4}\b")
_ACCOUNT_DETAILS_RE = re.compile(
    r"\b(delivered\s*to|residency|flat\s*\d+|street|pincode|bank\s*account|wallet|(?:delivery\s+|your\s+)?address\s+(?:is|was|in|at|:)|rs\.?\s*\d+)\b|(?:విలాసం|అడ్రస్|రెసిడెన్సీ|ఫ్లాట్|ఖాతా|రూపాయ|రూ\.?)",
    re.IGNORECASE,
)
_HOLD_REQUEST_RE = re.compile(
    r"\bon (a )?(brief |short |quick |courtesy )?hold\b|\bhold (the|your) line\b|\bplease hold\b|\bplace you on hold\b|\bput (you|the call) on hold\b|\bhold on\b",
    re.IGNORECASE,
)
_HOLD_RETURN_RE = re.compile(
    r"\b(thank\s*(?:you)?\s*for\s*(?:holding|waiting|your\s*patience)|thanks\s*for\s*(?:holding|waiting)|back\s*on\s*the\s*line)\b"
    r"|(?:వేచి\s*ఉన్నందుకు|లైన్\s*లో\s*వేచి)",
    re.IGNORECASE,
)
_EMPATHY_RE = re.compile(
    r"\b(sorry|apologiz\w*|understand\b.*\b(?:frustrat|upset|concern|situation|trouble|inconvenienc|disappoint)|in your shoes|hear your frustration|make this right|pardon|regret)\b",
    re.IGNORECASE,
)


class LiveRules:
    """Consumes CaptionEvents sequentially, maintaining live state and emitting de-duplicated alerts."""

    def __init__(self, config: Optional[Dict[str, Any]] = None, kb=None) -> None:
        self.config = dict(DEFAULT_LIVE_CONFIG)
        if config:
            self.config.update(config)

        self._kb = kb
        self.events: List[Any] = []
        self.alerts: List[LiveAlert] = []
        self.fired_keys: Set[str] = set()

        # Conversational counters & state
        self.agent_turn_count = 0
        self.customer_turn_count = 0
        self.recording_disclosed = False
        self.recording_turn: Optional[int] = None

        # Verification state
        self.order_id_verified = False
        self.phone_last4_verified = False
        self.identity_verified = False
        self.account_disclosed = False
        self.verification_breached = False

        # Hold state
        self.on_hold = False
        self.hold_start_sec: float = 0.0
        self.hold_start_quote: str = ""
        self.hold_start_turn: Optional[int] = None
        self.completed_holds_exceeded = False
        self.completed_holds_count = 0

        # Anger & Empathy state
        self.unaddressed_anger: Optional[Dict[str, Any]] = None
        self.empathy_shown = False

        # Topic & clauses
        self.detected_topic = "general"
        self.topic_confidence = 0.0
        self.active_clauses: List[Dict[str, Any]] = []

        # Previous final event for timing checks
        self.prev_final_event: Optional[Any] = None

    def _get_kb(self):
        if self._kb is None:
            try:
                from ..rag import KnowledgeBase
                self._kb = KnowledgeBase(use_embeddings=False)
            except Exception:
                self._kb = None
        return self._kb

    def process_event(self, event: Any) -> List[LiveAlert]:
        """Process an incoming CaptionEvent.

        Interim events (final=False) are ignored for compliance and milestone alerts.
        """
        if not event.final:
            return []

        new_alerts: List[LiveAlert] = []
        text = event.text.strip()
        role = event.role
        start_sec = event.start_sec
        end_sec = event.end_sec
        turn_id = event.turn_id or (len(self.events) + 1)
        self.events.append(event)

        # ----------------------------------------------------------------------
        # 1. HOLD CHECK & UPDATE
        # ----------------------------------------------------------------------
        was_on_hold = False
        if self.on_hold:
            was_on_hold = True
            # Check if current event timing indicates hold ceiling was exceeded
            elapsed_hold = start_sec - self.hold_start_sec
            if elapsed_hold > self.config["max_hold_seconds"]:
                k = f"HLD-02:hold_{self.hold_start_turn}"
                if k not in self.fired_keys:
                    self.fired_keys.add(k)
                    self.completed_holds_exceeded = True
                    alert = LiveAlert(
                        rule_id="HLD-02",
                        severity="danger",
                        time_sec=round(self.hold_start_sec + self.config["max_hold_seconds"], 2),
                        triggering_quote=self.hold_start_quote,
                        related_step_or_clause="HLD-02",
                        message=f"Customer placed on hold for {elapsed_hold:.1f}s, exceeding maximum 2-minute ceiling.",
                        turn_id=self.hold_start_turn,
                    )
                    new_alerts.append(alert)
                    self.alerts.append(alert)

            # Customer speaking during hold initiation confirms/updates hold start
            if role == "customer":
                self.hold_start_sec = max(self.hold_start_sec, end_sec)

            # Hold concludes when agent speaks or explicit return phrase spoken
            if role == "agent":
                self.on_hold = False
                self.completed_holds_count += 1

        # Check if agent is requesting a new hold
        if role == "agent" and _HOLD_REQUEST_RE.search(text):
            self.on_hold = True
            self.hold_start_sec = end_sec
            self.hold_start_quote = text
            self.hold_start_turn = turn_id

        # ----------------------------------------------------------------------
        # 2. TIMING: DEAD AIR & INTERRUPTION
        # ----------------------------------------------------------------------
        if self.prev_final_event is not None:
            # Dead air: silence between turns exceeding threshold (unless on an announced hold or returning from it)
            gap = start_sec - self.prev_final_event.end_sec
            if gap >= self.config["dead_air_threshold_sec"] and not self.on_hold and not was_on_hold:
                k = f"DEAD_AIR:{self.prev_final_event.turn_id}_{turn_id}"
                if k not in self.fired_keys:
                    self.fired_keys.add(k)
                    alert = LiveAlert(
                        rule_id="DEAD-AIR",
                        severity="warning",
                        time_sec=start_sec,
                        triggering_quote=f"{gap:.1f}s silence before turn {turn_id}",
                        related_step_or_clause="COM-01",
                        message=f"Dead air detected: {gap:.1f}s of silence between turns.",
                        turn_id=turn_id,
                    )
                    new_alerts.append(alert)
                    self.alerts.append(alert)

            # Agent interruption: agent starts speaking while customer still talking
            if role == "agent" and self.prev_final_event.role == "customer":
                overlap = self.prev_final_event.end_sec - start_sec
                if overlap > self.config["overlap_threshold_sec"]:
                    k = f"INTERRUPT:{self.prev_final_event.turn_id}_{turn_id}"
                    if k not in self.fired_keys:
                        self.fired_keys.add(k)
                        alert = LiveAlert(
                            rule_id="INTERRUPTION",
                            severity="warning",
                            time_sec=start_sec,
                            triggering_quote=text,
                            related_step_or_clause="ANG-01",
                            message=f"Agent talked over customer (speech overlapped by {overlap:.2f}s).",
                            turn_id=turn_id,
                        )
                        new_alerts.append(alert)
                        self.alerts.append(alert)

        # ----------------------------------------------------------------------
        # 3. CONVERSATIONAL ROLE PROCESSING
        # ----------------------------------------------------------------------
        if role == "agent":
            self.agent_turn_count += 1

            # Check recording disclosure
            if not self.recording_disclosed and _RECORD_RE.search(text):
                self.recording_disclosed = True
                self.recording_turn = turn_id

            # Rule GEN-02: Missing recording disclosure after first N agent turns
            if self.agent_turn_count >= self.config["disclosure_max_agent_turns"] and not self.recording_disclosed:
                k = "GEN-02:disclosure_missing"
                if k not in self.fired_keys:
                    self.fired_keys.add(k)
                    alert = LiveAlert(
                        rule_id="GEN-02",
                        severity="danger",
                        time_sec=end_sec,
                        triggering_quote=text,
                        related_step_or_clause="GEN-02",
                        message="Mandatory call recording disclosure not articulated within the first two conversation turns.",
                        turn_id=turn_id,
                    )
                    new_alerts.append(alert)
                    self.alerts.append(alert)

            # Check verification prompts by agent
            if _ORDER_ID_RE.search(text):
                self.order_id_verified = True
            if _PHONE_DIGITS_RE.search(text):
                self.phone_last4_verified = True

            # Check if agent discloses account details
            if _ACCOUNT_DETAILS_RE.search(text):
                self.account_disclosed = True
                if not (self.order_id_verified and self.phone_last4_verified):
                    self.verification_breached = True
                    k = "GEN-03:unverified_disclosure"
                    if k not in self.fired_keys:
                        self.fired_keys.add(k)
                        alert = LiveAlert(
                            rule_id="GEN-03",
                            severity="danger",
                            time_sec=start_sec,
                            triggering_quote=text,
                            related_step_or_clause="GEN-03",
                            message="Order or account data disclosed before completing 2FA verification (Order ID + registered phone last 4 digits).",
                            turn_id=turn_id,
                        )
                        new_alerts.append(alert)
                        self.alerts.append(alert)

            # Check empathy response to prior customer anger
            if self.unaddressed_anger is not None:
                self.unaddressed_anger["agent_turns"] += 1
                if _EMPATHY_RE.search(text):
                    self.empathy_shown = True
                    self.unaddressed_anger = None
                elif self.unaddressed_anger["agent_turns"] >= self.config["empathy_window_turns"]:
                    k = f"ANG-02:turn_{self.unaddressed_anger['turn']}"
                    if k not in self.fired_keys:
                        self.fired_keys.add(k)
                        alert = LiveAlert(
                            rule_id="ANG-02",
                            severity="warning",
                            time_sec=end_sec,
                            triggering_quote=self.unaddressed_anger["quote"],
                            related_step_or_clause="ANG-02",
                            message=f"Customer frustration unacknowledged: no sincere empathy statement offered within {self.config['empathy_window_turns']} agent turns.",
                            turn_id=turn_id,
                        )
                        new_alerts.append(alert)
                        self.alerts.append(alert)
                    self.unaddressed_anger = None

        elif role == "customer":
            self.customer_turn_count += 1

            # Check customer verification responses
            if _ORDER_ID_RE.search(text):
                self.order_id_verified = True
            if _DIGITS_4_RE.search(text):
                self.phone_last4_verified = True

            # Check customer anger cues
            is_angry = any(p.search(text) for p in _ANGER) or text.count("!") >= 2
            if is_angry and self.unaddressed_anger is None:
                self.unaddressed_anger = {
                    "turn": turn_id,
                    "quote": text,
                    "time_sec": end_sec,
                    "agent_turns": 0,
                }

        # Update identity verified state
        if self.order_id_verified and self.phone_last4_verified and not self.verification_breached:
            self.identity_verified = True

        # ----------------------------------------------------------------------
        # 4. TOPIC DETECTION & CLAUSE CARDS RETRIEVAL
        # ----------------------------------------------------------------------
        if len(self.events) >= 2:
            turns_tuples = [(ev.role, ev.text) for ev in self.events[-self.config["topic_window_turns"]:]]
            res = detect_topic(turns_tuples)
            self.detected_topic = res.topic
            self.topic_confidence = res.confidence

            # Surface retrieved clauses if topic is recognized or changes
            kb = self._get_kb()
            if kb is not None:
                query = " ".join(ev.text for ev in self.events[-self.config["topic_window_turns"]:])
                clauses = kb.retrieve_policies(query, topic=res.topic, k=self.config["clause_top_k"])
                self.active_clauses = [
                    {"id": c.id, "title": c.title, "text": c.short(250), "topic": res.topic}
                    for c in clauses
                ]
                if res.topic != "general" and res.confidence >= 0.3:
                    k = f"TOPIC:{res.topic}"
                    if k not in self.fired_keys:
                        self.fired_keys.add(k)
                        alert = LiveAlert(
                            rule_id="TOPIC-RETRIEVAL",
                            severity="info",
                            time_sec=end_sec,
                            triggering_quote=res.topic,
                            related_step_or_clause="RAG",
                            message=f"Detected topic '{res.topic.upper()}' ({res.confidence:.0%}). Surfaced {len(clauses)} policy clauses.",
                            turn_id=turn_id,
                        )
                        new_alerts.append(alert)
                        self.alerts.append(alert)

        self.prev_final_event = event
        return new_alerts

    def get_checklist_status(self) -> Dict[str, Dict[str, str]]:
        """Return structured compliance checklist state for live UI cards."""
        # 1. Recording disclosure (GEN-02)
        if self.recording_disclosed:
            disc_status = "completed"
            disc_desc = f"Disclosed at turn {self.recording_turn or 1}"
        elif self.agent_turn_count >= self.config["disclosure_max_agent_turns"]:
            disc_status = "missed"
            disc_desc = "Missed statutory disclosure in opening"
        else:
            disc_status = "pending"
            disc_desc = "Awaiting agent disclosure"

        # 2. 2FA Identity verification (GEN-03)
        if self.verification_breached:
            id_status = "breached"
            id_desc = "Account data disclosed before verification"
        elif self.identity_verified:
            id_status = "verified"
            id_desc = "Order ID and phone last-4 confirmed"
        elif self.order_id_verified or self.phone_last4_verified:
            id_status = "in_progress"
            id_desc = "Partial verification received"
        else:
            id_status = "pending"
            id_desc = "Awaiting verification exchange"

        # 3. Empathy (ANG-02 / GEN-05)
        any_empathy_alert = any(a.rule_id == "ANG-02" for a in self.alerts)
        if any_empathy_alert:
            emp_status = "missed"
            emp_desc = "Failed to empathize with customer distress"
        elif self.empathy_shown:
            emp_status = "completed"
            emp_desc = "Empathetic acknowledgment provided"
        elif self.unaddressed_anger is not None:
            emp_status = "pending"
            emp_desc = "Customer agitation active — empathy needed"
        else:
            emp_status = "not_applicable"
            emp_desc = "No customer distress detected"

        # 4. Hold status (HLD-02)
        if self.completed_holds_exceeded or any(a.rule_id == "HLD-02" for a in self.alerts):
            hld_status = "exceeded"
            hld_desc = "Hold exceeded maximum 2-minute ceiling"
        elif self.on_hold:
            hld_status = "active"
            hld_desc = "Customer currently on hold"
        elif self.completed_holds_count > 0:
            hld_status = "under_limit"
            hld_desc = f"{self.completed_holds_count} hold(s) completed under ceiling"
        else:
            hld_status = "none"
            hld_desc = "No holds initiated"

        return {
            "disclosure": {"status": disc_status, "detail": disc_desc, "step_id": "GEN-02"},
            "id_verification": {"status": id_status, "detail": id_desc, "step_id": "GEN-03"},
            "empathy": {"status": emp_status, "detail": emp_desc, "step_id": "ANG-02"},
            "hold_status": {"status": hld_status, "detail": hld_desc, "step_id": "HLD-02"},
        }
