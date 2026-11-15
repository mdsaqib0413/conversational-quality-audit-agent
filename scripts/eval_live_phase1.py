"""Replay the 13 canonical dev calls and compare live alerts against cached audit findings."""
from __future__ import annotations

import glob
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.audit.live import CallSimulator, LiveRules

DEV_CALLS = [
    "call_001", "call_009", "call_017", "call_025", "call_041",
    "call_101", "call_102", "call_103", "call_104", "call_105",
    "call_106", "call_107", "call_108",
]


def run_evaluation():
    cache_dir = ROOT / "data" / "cache" / "audits"
    transcripts_dir = ROOT / "data" / "transcripts"

    results = []

    for cid in DEV_CALLS:
        tpath = transcripts_dir / f"{cid}.json"
        if not tpath.exists():
            continue

        matching_audits = list(cache_dir.glob(f"{cid}_*.json"))
        if not matching_audits:
            continue
        audit_data = json.loads(matching_audits[0].read_text(encoding="utf-8"))

        # 1. Run live replay
        sim = CallSimulator(tpath)
        rules = LiveRules()
        events = sim.build_events()
        for ev in events:
            rules.process_event(ev)

        # Collect live alerts
        live_alerts = rules.alerts
        live_alert_ids = [a.rule_id for a in live_alerts]

        # 2. Extract cached audit findings
        # SOP misses
        sop_misses = [s["step_id"] for s in audit_data.get("sop_results", []) if s.get("status") == "missed"]
        # Policy violations
        policy_violations = []
        for f in audit_data.get("findings", []):
            code = f.get("code") or f.get("finding_id") or f.get("criterion_id") or ""
            if "policy_" in code or f.get("finding_type") == "violation":
                policy_violations.append(code.replace("policy_", "").split("_")[0])
            elif code.startswith("PRV-") or code.startswith("REF-") or code.startswith("BIL-") or code.startswith("WAR-"):
                policy_violations.append(code)

        for p in audit_data.get("policy_results", []):
            if p.get("status") in ("violated", "missed", "violation"):
                policy_violations.append(p.get("clause_id", ""))
        policy_violations = sorted(set(v for v in policy_violations if v))

        # Timing gaps
        gaps = [g.get("gap_type") for g in audit_data.get("gaps", [])]

        # 3. Categorize
        agreements = []
        live_only = []
        audit_only = []

        # Compare GEN-02
        if "GEN-02" in live_alert_ids and "GEN-02" in sop_misses:
            agreements.append("GEN-02 (Recording Disclosure)")
        elif "GEN-02" in live_alert_ids and "GEN-02" not in sop_misses:
            live_only.append("GEN-02 (Live flagged disclosure missing)")
        elif "GEN-02" not in live_alert_ids and "GEN-02" in sop_misses:
            audit_only.append("GEN-02 (Missed by live)")

        # Compare GEN-03
        if "GEN-03" in live_alert_ids and ("GEN-03" in sop_misses or "id_verif_breach" in [f.get("code") for f in audit_data.get("findings", [])]):
            agreements.append("GEN-03 (2FA Breach)")
        elif "GEN-03" in live_alert_ids:
            live_only.append("GEN-03 (Live flagged unverified disclosure)")
        elif "GEN-03" in sop_misses:
            audit_only.append("GEN-03 (Audit flagged 2FA miss)")

        # Compare HLD-02
        if "HLD-02" in live_alert_ids and ("HLD-02" in sop_misses or "hold_too_long" in gaps):
            agreements.append("HLD-02 (Hold Ceiling > 2m)")
        elif "HLD-02" in live_alert_ids:
            live_only.append("HLD-02 (Hold ceiling)")
        elif "HLD-02" in sop_misses or "hold_too_long" in gaps:
            audit_only.append("HLD-02 (Hold ceiling > 2m in audit)")

        # Compare ANG-02
        if "ANG-02" in live_alert_ids and ("ANG-02" in sop_misses or "no_empathy" in gaps):
            agreements.append("ANG-02 (Empathy Missing)")
        elif "ANG-02" in live_alert_ids:
            live_only.append("ANG-02 (Live unaddressed anger)")
        elif "ANG-02" in sop_misses or "no_empathy" in gaps:
            audit_only.append("ANG-02 (Audit empathy deduction)")

        # Compare DEAD-AIR
        if "DEAD-AIR" in live_alert_ids and "dead_air" in gaps:
            agreements.append("DEAD-AIR (Prolonged silence)")
        elif "DEAD-AIR" in live_alert_ids:
            live_only.append("DEAD-AIR (Timing gap)")
        elif "dead_air" in gaps:
            audit_only.append("dead_air (Audit gap)")

        # Compare INTERRUPTION
        if "INTERRUPTION" in live_alert_ids and "interruption" in gaps:
            agreements.append("INTERRUPTION (Overlapping speech)")
        elif "INTERRUPTION" in live_alert_ids:
            live_only.append("INTERRUPTION (Agent overlap)")
        elif "interruption" in gaps:
            audit_only.append("interruption (Audit gap)")

        # Topic retrieval alerts (informational)
        topic_alerts = [a.triggering_quote for a in live_alerts if a.rule_id == "TOPIC-RETRIEVAL"]
        if topic_alerts:
            live_only.append(f"Topic cards: {', '.join(set(topic_alerts))}")

        # Post-call audit findings the live rules cannot see (semantic / policy / un-monitored SOPs)
        unmonitored_sops = [s for s in sop_misses if s not in ("GEN-02", "GEN-03", "HLD-02", "ANG-02")]
        if unmonitored_sops:
            audit_only.append(f"SOP misses: {', '.join(unmonitored_sops)}")
        if policy_violations:
            audit_only.append(f"Policies: {', '.join(policy_violations)}")

        results.append({
            "call_id": cid,
            "topic": audit_data.get("topic", "general"),
            "agreements": agreements,
            "live_only": live_only,
            "audit_only": audit_only,
            "live_alerts_count": len(live_alerts),
            "sop_misses_count": len(sop_misses),
            "policy_violations_count": len(policy_violations),
        })

    # Print markdown table
    print("\n### Phase 1 Live Rules vs. Cached Post-Call Audit Findings (13 Dev Calls)\n")
    print("| Call ID | Topic | Agreements | Live Alerts (No Audit Finding) | Audit Findings Live Rules Cannot See |")
    print("| :--- | :--- | :--- | :--- | :--- |")

    for r in results:
        agr_str = "<br>".join(f"• {a}" for a in r["agreements"]) if r["agreements"] else "—"
        live_str = "<br>".join(f"• {a}" for a in r["live_only"]) if r["live_only"] else "—"
        audit_str = "<br>".join(f"• {a}" for a in r["audit_only"]) if r["audit_only"] else "—"
        print(f"| **{r['call_id']}** | {r['topic'].title()} | {agr_str} | {live_str} | {audit_str} |")

    return results


if __name__ == "__main__":
    run_evaluation()
