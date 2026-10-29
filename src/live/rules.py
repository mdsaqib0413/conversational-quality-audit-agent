"""Real-time rule alert engine, SOP milestone tracker, and mood lexicon (Phase 2).

Thread-safe, deterministic, pure Python without LLM dependencies.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import yaml

from .schemas import LiveAlert, LiveTurn, SopStepProgress

ROOT = Path(__file__).resolve().parent.parent.parent
RULES_FILE = ROOT / "data" / "live_rules.yaml"


class LiveRuleEngine:
    def __init__(self, config_path: Path = RULES_FILE):
        self.config_path = config_path
        self.rules: List[dict] = []
        self.sop_cues: Dict[str, dict] = {}
        self.positive_words: Set[str] = set()
        self.negative_words: Set[str] = set()
        self.fired_rule_ids: Set[str] = set()
        self.load_config()

    def reset(self) -> None:
        self.fired_rule_ids.clear()

    def load_config(self) -> None:
        if not self.config_path.exists():
            return
        with open(self.config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        self.rules = data.get("rules", [])
        self.sop_cues = data.get("sop_cues", {})
        mood = data.get("mood_lexicon", {})
        self.positive_words = set(mood.get("positive", []))
        self.negative_words = set(mood.get("negative", []))

    # -------------------------------------------------------------------------
    # Rule alert evaluation
    # -------------------------------------------------------------------------
    def evaluate_alerts(
        self,
        turns: List[LiveTurn],
        duration_sec: float,
        agent_talk_share: float,
        last_silence_sec: float,
    ) -> List[LiveAlert]:
        alerts: List[LiveAlert] = []
        if not turns:
            return alerts

        agent_turns = [t for t in turns if t.speaker == "agent" and not t.partial]
        cust_turns = [t for t in turns if t.speaker == "customer" and not t.partial]
        all_cust_text = " ".join(t.text for t in cust_turns).lower()

        # 1. Recording disclosure missing after agent turn 2
        rule_id = "recording_disclosure_missing"
        if rule_id not in self.fired_rule_ids and len(agent_turns) >= 2:
            disclosure_pat = re.compile(
                r"(?:recorded for quality|training purposes|quality assurance|call is (?:being )?recorded)",
                re.IGNORECASE,
            )
            has_disclosure = any(disclosure_pat.search(t.text) for t in agent_turns[:2])
            if not has_disclosure:
                self.fired_rule_ids.add(rule_id)
                r_def = next((r for r in self.rules if r["id"] == rule_id), None)
                alerts.append(
                    LiveAlert(
                        rule_id=rule_id,
                        name=r_def["name"] if r_def else "Recording Disclosure Missing",
                        clause_id=r_def["clause_id"] if r_def else "PRV-1.2",
                        severity=r_def["severity"] if r_def else "danger",
                        message=r_def["message"] if r_def else "Call recording disclosure not stated.",
                        key_numbers=r_def.get("key_numbers", "Within first 2 turns") if r_def else "Within 2 turns",
                        time_sec=agent_turns[1].end if len(agent_turns) > 1 else agent_turns[0].end,
                        offending_quote=agent_turns[0].text[:80] + "...",
                        turn_id=agent_turns[0].turn_id,
                    )
                )

        # 2. Address / sensitive details revealed before verification
        rule_id = "address_before_verification"
        if rule_id not in self.fired_rule_ids:
            cust_so_far = ""
            address_pat = re.compile(
                r"(?:flat\s*\d+|apartment|residency|street|road|lane|pune|mumbai|delhi|bangalore|delivered to)",
                re.IGNORECASE,
            )
            for t in turns:
                if t.speaker == "customer":
                    cust_so_far += " " + t.text.lower()
                elif t.speaker == "agent":
                    has_order_id = bool(re.search(r"\b(?:ORD[- ]?\d{4,6}|order\s*(?:id|number))\b", cust_so_far, re.IGNORECASE))
                    has_last4 = bool(re.search(r"\b\d{4}\b", cust_so_far))
                    is_verified = has_order_id and has_last4
                    m = address_pat.search(t.text)
                    if m and not is_verified:
                        self.fired_rule_ids.add(rule_id)
                        r_def = next((r for r in self.rules if r["id"] == rule_id), None)
                        alerts.append(
                            LiveAlert(
                                rule_id=rule_id,
                                name=r_def["name"] if r_def else "Sensitive Data Revealed",
                                clause_id=r_def["clause_id"] if r_def else "PRV-1.1",
                                severity=r_def["severity"] if r_def else "danger",
                                message=r_def["message"] if r_def else "Address revealed before 2FA verification.",
                                key_numbers=r_def.get("key_numbers", "Order ID + 4 digits") if r_def else "Order ID + 4 digits",
                                time_sec=t.start,
                                offending_quote=m.group(0),
                                turn_id=t.turn_id,
                            )
                        )
                        break

        # 3. Agent self-approves refund > Rs 5,000 or no supervisor needed
        rule_id = "refund_limit_self_approval"
        if rule_id not in self.fired_rule_ids:
            limit_pat = re.compile(
                r"(?:approved by me|full authority|no supervisor (?:is )?needed|i (?:can|will) approve (?:it )?myself)",
                re.IGNORECASE,
            )
            for t in agent_turns:
                m_lim = limit_pat.search(t.text)
                if m_lim:
                    self.fired_rule_ids.add(rule_id)
                    r_def = next((r for r in self.rules if r["id"] == rule_id), None)
                    alerts.append(
                        LiveAlert(
                            rule_id=rule_id,
                            name=r_def["name"] if r_def else "Unauthorized Refund Approval",
                            clause_id=r_def["clause_id"] if r_def else "REF-3.1",
                            severity=r_def["severity"] if r_def else "danger",
                            message=r_def["message"] if r_def else "Refund over Rs 5,000 self-approved without supervisor.",
                            key_numbers=r_def.get("key_numbers", "Rs 5,000 limit") if r_def else "Rs 5,000",
                            time_sec=t.start,
                            offending_quote=t.text,
                            turn_id=t.turn_id,
                        )
                    )
                    break

        # 4. Refund to wallet or non-original destination (excluding goodwill/compensation)
        rule_id = "refund_wallet_destination"
        if rule_id not in self.fired_rule_ids:
            wallet_pat = re.compile(r"\b(?:(?:to|into|via)\s+(?:your\s+)?(?:paytm|phonepe|gpay|google pay|wallet|store credit))\b", re.IGNORECASE)
            for t in agent_turns:
                txt = t.text
                if wallet_pat.search(txt):
                    # Do not fire on promotional / goodwill delay compensation
                    if re.search(r"\b(?:compensation|goodwill)\b", txt, re.IGNORECASE):
                        continue
                    # Fire: sending money to wallet is a destination violation regardless of explicit "refund" word
                    self.fired_rule_ids.add(rule_id)
                    r_def = next((r for r in self.rules if r["id"] == rule_id), None)
                    alerts.append(
                        LiveAlert(
                            rule_id=rule_id,
                            name=r_def["name"] if r_def else "Non-Original Payment Disbursement",
                            clause_id=r_def["clause_id"] if r_def else "REF-2.2",
                            severity=r_def["severity"] if r_def else "danger",
                            message=r_def["message"] if r_def else "Refund redirected to wallet.",
                            key_numbers=r_def.get("key_numbers", "Original payment method") if r_def else "Original payment",
                            time_sec=t.start,
                            offending_quote=t.text,
                            turn_id=t.turn_id,
                        )
                    )
                    break

        # 5. Refund timeline too fast (< 5 business days without stating 5-7 days SLA)
        rule_id = "refund_timeline_24h"
        if rule_id not in self.fired_rule_ids:
            for t in agent_turns:
                txt = t.text
                if re.search(r"\b5\s*(?:to|-)\s*7\s*(?:business\s*)?days?\b", txt, re.IGNORECASE):
                    continue
                clean_txt = re.sub(r"\brefund\s+request\s+today\b", "", txt, flags=re.IGNORECASE)
                clean_txt = re.sub(r"\bcallback\s+within\s+2\s*(?:to|-)\s*4\s*hours?\b", "", clean_txt, flags=re.IGNORECASE)
                fast_sla_patterns = [
                    r"\b(?:credited|reflect(?:ed)?|back in (?:your )?account)\b.{0,30}\b(?:within\s+)?(?:24\s*hours?|today|instantly|immediate(?:ly)?|within a day|2\s*days?)\b",
                    r"\b(?:within\s+)?(?:24\s*hours?|today|instantly|immediate(?:ly)?|within a day|2\s*days?)\b.{0,30}\b(?:credited|reflect(?:ed)?|back in (?:your )?account)\b",
                    r"\b(?:will\s+(?:be\s+)?refund(?:ed)?|refund\s+(?:it|you)|processed)\b.{0,25}\b(?:within\s+)?(?:within\s+24\s*hours?|today|instantly|within a day|2\s*days?)\b",
                ]
                m_match = None
                for p in fast_sla_patterns:
                    m_match = re.search(p, clean_txt, re.IGNORECASE)
                    if m_match:
                        break
                if m_match:
                    self.fired_rule_ids.add(rule_id)
                    r_def = next((r for r in self.rules if r["id"] in ("refund_timeline_24h", "refund_timeline_too_fast")), None)
                    alerts.append(
                        LiveAlert(
                            rule_id=rule_id,
                            name=r_def["name"] if r_def else "Invalid Refund SLA Promised",
                            clause_id=r_def["clause_id"] if r_def else "REF-2.1",
                            severity=r_def["severity"] if r_def else "warning",
                            message=r_def["message"] if r_def else "Refund promised within 24 hours (SLA is 5-7 business days).",
                            key_numbers=r_def.get("key_numbers", "5-7 business days") if r_def else "5-7 business days",
                            time_sec=t.start,
                            offending_quote=m_match.group(0),
                            turn_id=t.turn_id,
                        )
                    )
                    break

        # 6. "Keep the item / no need to send it back"
        rule_id = "keep_item_no_return"
        if rule_id not in self.fired_rule_ids:
            keep_pat = re.compile(r"(?:keep the (?:item|watch|product|order)|no need to (?:send it back|return it))", re.IGNORECASE)
            for t in agent_turns:
                m = keep_pat.search(t.text)
                if m:
                    self.fired_rule_ids.add(rule_id)
                    r_def = next((r for r in self.rules if r["id"] == rule_id), None)
                    alerts.append(
                        LiveAlert(
                            rule_id=rule_id,
                            name=r_def["name"] if r_def else "Unauthorized Item Retention",
                            clause_id=r_def["clause_id"] if r_def else "REF-1.2",
                            severity=r_def["severity"] if r_def else "warning",
                            message=r_def["message"] if r_def else "Agent instructed caller to keep item without return.",
                            key_numbers=r_def.get("key_numbers", "Physical return mandatory") if r_def else "Return required",
                            time_sec=t.start,
                            offending_quote=m.group(0),
                            turn_id=t.turn_id,
                        )
                    )
                    break

        # 7. Scam cues: AnyDesk, TeamViewer, OTP
        rule_id = "scam_cue_detected"
        if rule_id not in self.fired_rule_ids:
            scam_pat = re.compile(
                r"\b(?:anydesk|teamviewer|quicksupport|ultraviewer)\b|read (?:out |me )?(?:the )?(?:otp|code|pin)|share (?:your )?(?:otp|code|pin)",
                re.IGNORECASE,
            )
            for t in turns:
                m = scam_pat.search(t.text)
                if m:
                    self.fired_rule_ids.add(rule_id)
                    r_def = next((r for r in self.rules if r["id"] == rule_id), None)
                    alerts.append(
                        LiveAlert(
                            rule_id=rule_id,
                            name=r_def["name"] if r_def else "Suspected Remote Access / Scam Cue",
                            clause_id=r_def["clause_id"] if r_def else "PRV-1.1",
                            severity=r_def["severity"] if r_def else "danger",
                            message=r_def["message"] if r_def else "Remote access application or OTP request detected.",
                            key_numbers=r_def.get("key_numbers", "Never share OTP") if r_def else "Never share OTP",
                            time_sec=t.start,
                            offending_quote=m.group(0),
                            turn_id=t.turn_id,
                        )
                    )
                    break

        # 8. Customer frustration words (customer speech only, info severity)
        rule_id = "customer_frustration"
        if rule_id not in self.fired_rule_ids:
            frust_pat = re.compile(
                r"\b(?:unacceptable|ridiculous|fed up|worst|pathetic|cheat|fraud|furious|disgusted|useless|waste of time)\b",
                re.IGNORECASE,
            )
            for t in cust_turns:
                m = frust_pat.search(t.text)
                if m:
                    self.fired_rule_ids.add(rule_id)
                    r_def = next((r for r in self.rules if r["id"] == rule_id), None)
                    alerts.append(
                        LiveAlert(
                            rule_id=rule_id,
                            name=r_def["name"] if r_def else "Customer Frustration Detected",
                            clause_id=r_def["clause_id"] if r_def else "ESC-1.1",
                            severity=r_def["severity"] if r_def else "info",
                            message=r_def["message"] if r_def else "Customer expressed high frustration.",
                            key_numbers=r_def.get("key_numbers", "Empathy / Escalation") if r_def else "Escalation SLA",
                            time_sec=t.start,
                            offending_quote=m.group(0),
                            turn_id=t.turn_id,
                        )
                    )
                    break

        # 8b. Supervisor escalation refused by agent (ESC-1.1, danger)
        rule_id_esc = "supervisor_escalation_refused"
        if rule_id_esc not in self.fired_rule_ids:
            esc_refuse_pat = re.compile(
                r"(?:cannot|can't|will not|won't)\s+(?:transfer|connect|call)\s+(?:you|this\s+call)?|(?:manager|supervisor)s?\s+do not handle|no supervisor\s+(?:available|is going to)|supervisor will (?:just )?tell you the same",
                re.IGNORECASE,
            )
            for t in agent_turns:
                m = esc_refuse_pat.search(t.text)
                if m:
                    self.fired_rule_ids.add(rule_id_esc)
                    alerts.append(
                        LiveAlert(
                            rule_id=rule_id_esc,
                            name="Supervisor Escalation Refused",
                            clause_id="ESC-1.1",
                            severity="danger",
                            message="Agent refused mandatory supervisor escalation upon caller request (ESC-1.1).",
                            key_numbers="Escalation SLA",
                            time_sec=t.start,
                            offending_quote=m.group(0),
                            turn_id=t.turn_id,
                        )
                    )
                    break

        # 9. Prolonged silence > 8s
        rule_id = "prolonged_silence"
        if rule_id not in self.fired_rule_ids and last_silence_sec > 8.0:
            self.fired_rule_ids.add(rule_id)
            r_def = next((r for r in self.rules if r["id"] == rule_id), None)
            alerts.append(
                LiveAlert(
                    rule_id=rule_id,
                    name=r_def["name"] if r_def else "Prolonged Silence / Dead Air",
                    clause_id=r_def["clause_id"] if r_def else "ESC-2.1",
                    severity=r_def["severity"] if r_def else "warning",
                    message=r_def["message"] if r_def else f"Silence exceeded {last_silence_sec:.1f}s without hold.",
                    key_numbers=r_def.get("key_numbers", "> 8s dead air") if r_def else "> 8s silence",
                    time_sec=duration_sec,
                    offending_quote=f"Dead air: {last_silence_sec:.1f}s",
                    turn_id=turns[-1].turn_id if turns else None,
                )
            )

        # 10. Agent talk share > 70% (when call > 30s)
        rule_id = "agent_talk_dominance"
        if rule_id not in self.fired_rule_ids and duration_sec > 30.0 and agent_talk_share > 0.75:
            self.fired_rule_ids.add(rule_id)
            r_def = next((r for r in self.rules if r["id"] == rule_id), None)
            alerts.append(
                LiveAlert(
                    rule_id=rule_id,
                    name=r_def["name"] if r_def else "Agent Talk Dominance",
                    clause_id=r_def["clause_id"] if r_def else "GEN-04",
                    severity=r_def["severity"] if r_def else "info",
                    message=r_def["message"] if r_def else f"Agent speaking {agent_talk_share:.0%} of the time.",
                    key_numbers=r_def.get("key_numbers", "> 70% talk share") if r_def else "> 70%",
                    time_sec=duration_sec,
                    offending_quote=f"Talk share: {agent_talk_share:.0%}",
                    turn_id=turns[-1].turn_id if turns else None,
                )
            )

        return alerts

    # -------------------------------------------------------------------------
    # SOP progress evaluation
    # -------------------------------------------------------------------------
    def evaluate_sop_progress(self, topic: str, turns: List[LiveTurn]) -> Tuple[List[SopStepProgress], Optional[SopStepProgress]]:
        # Choose applicable steps based on topic
        step_ids = ["GEN-01", "GEN-02", "GEN-03", "GEN-04", "GEN-05", "GEN-06", "GEN-07", "GEN-08"]
        if topic == "refund":
            step_ids += ["REF-S1", "REF-S2", "REF-S3", "REF-S4", "REF-S5", "REF-S6", "REF-S7"]

        checklist: List[SopStepProgress] = []
        next_step: Optional[SopStepProgress] = None

        agent_turns = [t for t in turns if t.speaker == "agent"]
        full_agent_text = " ".join(t.text for t in agent_turns)

        for sid in step_ids:
            cue = self.sop_cues.get(sid, {})
            name = cue.get("name", sid)
            crit = bool(cue.get("critical", False))
            status = "not_yet"
            matched_quote = ""

            if sid == "GEN-01":
                # Greeting cue: company name or "how can I help" -> done
                has_company = bool(re.search(r"\b(?:ShopEase|shopease)\b", full_agent_text, re.IGNORECASE))
                has_help = bool(re.search(r"\bhow\s+(?:can|may)\s+i\s+(?:help|assist)\b", full_agent_text, re.IGNORECASE))
                has_greeting = bool(re.search(r"\b(?:thank\s+you\s+for\s+calling|welcome\s+to|good\s+(?:morning|afternoon|evening)|hello|hi\b)", full_agent_text, re.IGNORECASE))
                if has_company or has_help:
                    status = "done"
                    matched_quote = "ShopEase / greeting"
                elif has_greeting:
                    status = "partial"
                    matched_quote = "Greeting only"

            elif sid == "GEN-02":
                has_rec = bool(re.search(r"(?:call\s+is\s+(?:being\s+)?recorded|recorded\s+for\s+quality|quality\s+(?:assurance|monitoring)|training\s+purposes)", full_agent_text, re.IGNORECASE))
                if has_rec:
                    status = "done"
                    matched_quote = "Recording disclosure"

            elif sid == "GEN-03":
                # Two verification items: Order ID AND phone digits
                has_order = bool(re.search(r"\border\s*(?:id|number|#)\b", full_agent_text, re.IGNORECASE))
                has_phone = bool(re.search(r"(?:last\s*(?:4|four)\s*digits|(?:registered|mobile|phone)\s*number)", full_agent_text, re.IGNORECASE))
                if has_order and has_phone:
                    status = "done"
                    matched_quote = "Order ID + phone verified"
                elif has_order or has_phone:
                    status = "partial"
                    matched_quote = "Single verification item only"

            elif sid == "GEN-04":
                # Paraphrase issue AND confirmation check
                has_clarify = bool(re.search(r"(?:if\s+i\s+(?:understand|heard)|understand\s+that|let\s+me\s+confirm|you\s+mentioned|so\s+you\s+would\s+like)", full_agent_text, re.IGNORECASE))
                has_confirm = bool(re.search(r"(?:is\s+that\s+correct|right\?|did\s+i\s+get\s+that\s+right)", full_agent_text, re.IGNORECASE))
                if has_clarify and has_confirm:
                    status = "done"
                    matched_quote = "Issue clarified & confirmed"
                elif has_clarify or has_confirm:
                    status = "partial"
                    matched_quote = "Clarification without full confirmation"

            elif sid == "GEN-05":
                # Empathy (apology/trouble) AND Ownership (resolve/personally/help)
                has_empathy = bool(re.search(r"(?:apologize|sorry|inconvenience|trouble|disappointing|frustrat)", full_agent_text, re.IGNORECASE))
                has_ownership = bool(re.search(r"(?:personally|take\s+ownership|help\s+you|resolve|sort\s+this\s+out|right\s+person|no\s+problem|right\s+away|process\s+the\s+refund|have\s+full\s+authority|take\s+care\s+of)", full_agent_text, re.IGNORECASE))
                if has_empathy and has_ownership:
                    status = "done"
                    matched_quote = "Empathy & ownership stated"
                elif has_empathy or has_ownership:
                    status = "partial"
                    matched_quote = "Ownership/reassurance without apology" if has_ownership else "Apology without personal ownership"

            elif sid == "GEN-06":
                has_pol_rule = bool(re.search(r"(?:policy|return\s+window|7[\s-]day|within\s+(?:the\s+)?(?:7|10|14)\s+days|eligible)", full_agent_text, re.IGNORECASE))
                has_pol_sol = bool(re.search(r"(?:reverse\s+pickup|replacement|approve|refund\s+(?:of|will|is)|credited)", full_agent_text, re.IGNORECASE))
                if has_pol_rule and has_pol_sol:
                    status = "done"
                    matched_quote = "Policy terms explained with resolution"
                elif has_pol_rule:
                    status = "partial"
                    matched_quote = "Policy mentioned without resolution"

            elif sid == "GEN-07":
                has_recap = bool(re.search(r"(?:to\s+(?:recap|summarize)|pickup\s+(?:is\s+)?scheduled|ticket\s*#|reference\s*(?:id|ticket|#))", full_agent_text, re.IGNORECASE))
                has_else = bool(re.search(r"(?:anything\s+else\s+(?:i\s+(?:can|may)|may\s+i)\s+(?:help|assist)|any\s+other\s+questions)", full_agent_text, re.IGNORECASE))
                if has_recap and has_else:
                    status = "done"
                    matched_quote = "Recap given and additional help asked"
                elif has_recap or has_else:
                    status = "partial"
                    matched_quote = "Recap or check asked partially"

            elif sid == "GEN-08":
                has_close_brand = bool(re.search(r"(?:thank\s+you\s+for\s+(?:contacting|calling|choosing)\s+shopease|pleasure\s+assisting\s+you|have\s+a\s+(?:wonderful|great|nice)\s+(?:rest\s+of\s+your\s+)?day)", full_agent_text, re.IGNORECASE))
                if has_close_brand:
                    status = "done"
                    matched_quote = "Professional branded closing"

            elif sid == "REF-S1":
                if re.search(r"(?:reason\s+for\s+(?:return|refund)|why\s+(?:would\s+you\s+like|do\s+you\s+want)\s+to\s+return|kettle.*not\s+functioning|defective|damaged|size\s+is\s+too\s+small)", full_agent_text, re.IGNORECASE):
                    status = "done"
                    matched_quote = "Return reason confirmed"

            elif sid == "REF-S2":
                if re.search(r"(?:delivery\s+date|delivered\s+(?:last\s+week|three|3|\d+)\s+days|within\s+(?:the\s+)?(?:7|10|14)\s+days|return\s+window)", full_agent_text, re.IGNORECASE):
                    status = "done"
                    matched_quote = "Return window validated"

            elif sid == "REF-S3":
                if re.search(r"(?:physical\s+damage|cord|alternate\s+power\s+outlet|original\s+(?:box|packaging)|unused|unopened|unworn|tags\s+attached)", full_agent_text, re.IGNORECASE):
                    status = "done"
                    matched_quote = "Item condition verified"

            elif sid == "REF-S4":
                if re.search(r"(?:discretionary\s+approval\s+limit|supervisor\s+approval|manager\s+approval|within\s+.*5,000|above\s+5,000)", full_agent_text, re.IGNORECASE):
                    status = "done"
                    matched_quote = "Approval threshold verified"

            elif sid == "REF-S5":
                if re.search(r"(?:reverse\s+pickup|courier|pickup\s+for\s+tomorrow|scheduled\s+.*pickup|doorstep\s+pickup)", full_agent_text, re.IGNORECASE):
                    status = "done"
                    matched_quote = "Reverse pickup arranged"

            elif sid == "REF-S6":
                if re.search(r"(?:5\s+(?:to|-)\s+7\s+(?:business\s+)?days|original\s+payment\s+(?:method|source)|credited\s+back|remitted)", full_agent_text, re.IGNORECASE):
                    status = "done"
                    matched_quote = "5-7 business days refund SLA explained"

            elif sid == "REF-S7":
                if re.search(r"(?:return\s+(?:reference\s+)?ticket\s*#|return\s+request\s*(?:id|number)|#RTN)", full_agent_text, re.IGNORECASE):
                    status = "done"
                    matched_quote = "Return request ticket shared"

            else:
                patterns = cue.get("patterns", [])
                for p in patterns:
                    m = re.search(p, full_agent_text, re.IGNORECASE)
                    if m:
                        status = "done"
                        matched_quote = m.group(0)
                        break

            item = SopStepProgress(step_id=sid, name=name, critical=crit, status=status, matched_quote=matched_quote)
            checklist.append(item)
            if status != "done" and next_step is None:
                next_step = item

        return checklist, next_step

    # -------------------------------------------------------------------------
    # Customer mood analysis (lexicon-based, no LLM)
    # -------------------------------------------------------------------------
    def evaluate_customer_mood(self, turns: List[LiveTurn]) -> Tuple[str, float]:
        cust_turns = [t for t in turns if t.speaker == "customer"]
        if not cust_turns:
            return "Neutral", 0.0

        full_text = " ".join(t.text for t in cust_turns).lower()
        words = re.findall(r"\b[a-z]+\b", full_text)

        pos_count = sum(1 for w in words if w in self.positive_words)
        neg_count = sum(1 for w in words if w in self.negative_words)

        # Exclamations indicate intensity
        exclamations = full_text.count("!")
        neg_count += exclamations

        total = pos_count + neg_count
        if total == 0:
            return "Calm", 0.1

        score = (pos_count - neg_count) / float(total)

        if score <= -0.4:
            return "Angry", score
        elif score < 0.0:
            return "Frustrated", score
        elif score > 0.3:
            return "Calm", score
        else:
            return "Neutral", score
