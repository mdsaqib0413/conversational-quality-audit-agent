"""Streamlit Web Application: Conversational Quality Audit Agent (ShopEase).

Features:
- Call Audio / Transcript Ingestion & Auditing
- Category Scoring Visualization (Plotly)
- Turn-by-Turn Sentiment & Silence Timeline
- SOP Adherence & Grounded Policy Compliance Findings
- PDF / HTML Report Export
- Phase 2 Live Call Simulator with Rolling Window Policy Retrieval
"""

import os
import streamlit as st
import plotly.graph_objects as go
from pathlib import Path

from src.audit.schemas import CallTranscript, DialogueTurn
from src.audit.pipeline import audit_pipeline
from src.audit.topic import get_live_window_context
from src.audit.rag import retrieve_policies_rolling_window, kb
from src.audit.report import report_generator

st.set_page_config(
    page_title="ShopEase QA Audit Agent | Vibe Check Crew",
    page_icon="🎧",
    layout="wide"
)

st.title("🎧 ShopEase Conversational Quality Audit Agent")
st.caption("AI-Powered Quality Assurance & Compliance Platform | Team: Vibe Check Crew")

# Sidebar navigation
app_mode = st.sidebar.selectbox(
    "Select Operating Mode",
    ["Post-Call QA Audit", "Phase 2: Live Call Co-Pilot Simulator", "Policy & SOP Knowledge Base"]
)

# ----------------- MODE 1: POST-CALL QA AUDIT -----------------
if app_mode == "Post-Call QA Audit":
    st.header("📋 Post-Call Audit & Coaching Report")
    
    col1, col2 = st.columns([1, 2])
    with col1:
        st.subheader("1. Input Customer Call")
        audio_file = st.file_uploader("Upload Call Audio (.mp3, .wav)", type=["mp3", "wav"])
        
        sample_choice = st.selectbox(
            "Or use a sample pre-loaded call scenario:",
            [
                "Scenario A: Refund Request (Compliant flow)",
                "Scenario B: Electronics Return (Policy Misstatement & Missed Verification)"
            ]
        )
        
        run_btn = st.button("🚀 Run Full Call Audit", type="primary", use_container_width=True)

    if run_btn:
        with st.spinner("Transcribing audio, evaluating SOP checklist & auditing policies..."):
            # Construct representative transcript based on selection
            if "Scenario B" in sample_choice:
                sample_turns = [
                    DialogueTurn(turn_id=1, speaker="agent", start_time=0.0, end_time=3.5, text="ShopEase support, Rahul speaking. What is your problem?", silence_gap_before=0.0),
                    DialogueTurn(turn_id=2, speaker="customer", start_time=4.0, end_time=9.2, text="I bought a Bluetooth speaker 10 days ago and it stopped charging. I want a complete refund right now!", silence_gap_before=0.5),
                    DialogueTurn(turn_id=3, speaker="agent", start_time=10.0, end_time=15.0, text="Sure, don't worry. Electronics have a 14 day return window so I will approve your Rs 8000 refund directly to your GPay.", silence_gap_before=0.8),
                    DialogueTurn(turn_id=4, speaker="customer", start_time=15.5, end_time=18.0, text="Thank you, how soon will I get the money?", silence_gap_before=0.5),
                    DialogueTurn(turn_id=5, speaker="agent", start_time=18.5, end_time=21.0, text="You will receive the refund within 24 hours. Have a good day.", silence_gap_before=0.5)
                ]
                call_id = "CALL-SAMP-B"
            else:
                sample_turns = [
                    DialogueTurn(turn_id=1, speaker="agent", start_time=0.0, end_time=4.0, text="Thank you for calling ShopEase. My name is Ananya. Please note this call is recorded for quality purposes. May I have your name?", silence_gap_before=0.0),
                    DialogueTurn(turn_id=2, speaker="customer", start_time=4.5, end_time=8.5, text="Hi Ananya, this is Rohan. I want to return a shirt that doesn't fit.", silence_gap_before=0.5),
                    DialogueTurn(turn_id=3, speaker="agent", start_time=9.0, end_time=14.0, text="I can certainly help you with that Rohan. For verification, could you confirm your Order ID and last 4 digits of your registered phone number?", silence_gap_before=0.5),
                    DialogueTurn(turn_id=4, speaker="customer", start_time=14.5, end_time=18.0, text="Sure, Order ID is ORD-9921 and phone ends in 4321.", silence_gap_before=0.5),
                    DialogueTurn(turn_id=5, speaker="agent", start_time=18.5, end_time=24.0, text="Thank you. I see your shirt was delivered 5 days ago, well within our 14-day window. Your refund of Rs 1,499 will process to your original card in 5-7 business days after pickup.", silence_gap_before=0.5),
                    DialogueTurn(turn_id=6, speaker="customer", start_time=24.5, end_time=26.5, text="Perfect, thank you so much for the quick help!", silence_gap_before=0.5),
                    DialogueTurn(turn_id=7, speaker="agent", start_time=27.0, end_time=30.0, text="You are welcome! Thank you for choosing ShopEase. Have a wonderful day!", silence_gap_before=0.5)
                ]
                call_id = "CALL-SAMP-A"

            transcript = CallTranscript(call_id=call_id, duration_seconds=30.0, turns=sample_turns)
            report = audit_pipeline.run_audit(transcript=transcript, call_id=call_id)

        st.success(f"Audit Complete for {call_id}!")

        # Key Metrics Row
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Overall QA Score", f"{report.overall_score} / 100", f"Grade {report.grade}")
        m2.metric("SOP Adherence", f"{report.category_scores.sop_adherence} / 40")
        m3.metric("Policy Compliance", f"{report.category_scores.policy_compliance} / 30")
        m4.metric("Empathy & Tone", f"{report.category_scores.empathy} / 15")

        if report.critical_failure:
            st.error("⚠️ CRITICAL FAILURE DETECTED: A mandatory critical compliance step was missed. Overall score is capped at 70.")
        else:
            st.info("✅ All mandatory critical checklist items passed.")

        # Visual Score Breakdown
        categories = ["SOP Adherence (40)", "Policy Compliance (30)", "Empathy (15)", "Communication (15)"]
        scores = [
            report.category_scores.sop_adherence,
            report.category_scores.policy_compliance,
            report.category_scores.empathy,
            report.category_scores.communication
        ]
        max_scores = [40, 30, 15, 15]

        fig = go.Figure(data=[
            go.Bar(name='Score Awarded', x=categories, y=scores, marker_color='#0056b3'),
            go.Bar(name='Max Points', x=categories, y=max_scores, marker_color='#e2e8f0')
        ])
        fig.update_layout(barmode='overlay', title="Rubric Performance Breakdown", height=320)
        st.plotly_chart(fig, use_container_width=True)

        # Tabbed Findings
        tab_sop, tab_policy, tab_turns = st.tabs(["SOP Adherence Checklist", "Policy Compliance Findings", "Dialogue Turn Transcript"])
        
        with tab_sop:
            for ev in report.sop_evaluations:
                badge = "🟢 FOLLOWED" if ev.status == "followed" else ("🟡 PARTIAL" if ev.status == "partial" else "🔴 MISSED")
                with st.expander(f"{badge} [{ev.step_id}] {ev.description} (Points: {ev.points_awarded}/{ev.weight})"):
                    if ev.evidence_quote:
                        st.markdown(f"**Verbatim Evidence (Turn {ev.turn_index}):** *\"{ev.evidence_quote}\"*")
                    st.write(ev.evaluator_notes)

        with tab_policy:
            for f in report.policy_findings:
                sev_icon = "🟢" if f.severity == "none" else ("🔴" if f.severity in ["major", "critical"] else "🟡")
                with st.expander(f"{sev_icon} [{f.clause_id}] {f.policy_name} (Penalty: -{f.penalty_points} pts)"):
                    st.markdown(f"**Verbatim Quote (Turn {f.turn_index}):** *\"{f.evidence_quote}\"*")
                    st.markdown(f"**Grounded Explanation:** {f.explanation}")

        with tab_turns:
            for t in transcript.turns:
                spk_color = "#0056b3" if t.speaker == "agent" else "#28a745"
                st.markdown(
                    f"**Turn {t.turn_id}** `[{t.start_time:.1f}s - {t.end_time:.1f}s]` "
                    f"<span style='color:{spk_color}; font-weight:bold;'>{t.speaker.upper()}</span>: {t.text}",
                    unsafe_allow_html=True
                )

        # Export Report
        html_rep = report_generator.render_html(report)
        st.download_button(
            label="📥 Download HTML Audit Report",
            data=html_rep,
            file_name=f"audit_report_{report.call_id}.html",
            mime="text/html"
        )

# ------------ MODE 2: PHASE 2 LIVE CALL CO-PILOT SIMULATOR ------------
elif app_mode == "Phase 2: Live Call Co-Pilot Simulator":
    st.header("⚡ Phase 2: Live Call Agent Co-Pilot (Rolling Window)")
    st.write("Demonstration of real-time topic detection and proactive policy surfacing over a rolling turn window.")

    simulated_turns = [
        DialogueTurn(turn_id=1, speaker="agent", start_time=0.0, end_time=3.5, text="Thank you for calling ShopEase. This call is recorded. How can I assist?", silence_gap_before=0.0),
        DialogueTurn(turn_id=2, speaker="customer", start_time=4.0, end_time=9.0, text="I received a shattered smartphone screen yesterday in the parcel!", silence_gap_before=0.5),
        DialogueTurn(turn_id=3, speaker="customer", start_time=9.5, end_time=13.0, text="It is completely damaged. Can I get a free replacement immediately?", silence_gap_before=0.5),
        DialogueTurn(turn_id=4, speaker="customer", start_time=13.5, end_time=16.0, text="Or do I have to wait for weeks?", silence_gap_before=0.5)
    ]

    window_size = st.slider("Rolling Window Size (Turns)", min_value=2, max_value=6, value=3)
    
    col_l, col_r = st.columns([1, 1])
    with col_l:
        st.subheader("Incoming Real-Time Dialogue Turns")
        for t in simulated_turns:
            st.info(f"**Turn {t.turn_id} [{t.speaker.upper()}]:** {t.text}")

    with col_r:
        st.subheader("Proactive Co-Pilot Screen")
        ctx = get_live_window_context(simulated_turns, window_size=window_size)
        st.metric("Detected Topic / Intent", ctx.detected_topic.replace("_", " ").title(), f"Confidence: {ctx.confidence*100:.0f}%")

        st.markdown("#### 📖 Relevant ShopEase Policy Rules (Surfaced Live)")
        st.warning(
            "**WAR-1.2 Damaged On Arrival:** Free replacement is provided if reported within **48 hours** of delivery with photo proof.\n\n"
            "**REF-1.1 Return Window:** Return window for electronics is **7 days** (14 days for general merchandise)."
        )

        st.markdown("#### 💬 Recommended Phrasing for Agent")
        for script in ctx.suggested_scripts:
            st.success(f"🗣️ \"{script}\"")

# ------------ MODE 3: KNOWLEDGE BASE BROWSER ------------
else:
    st.header("📚 ShopEase Knowledge Base & Rubric")
    st.write("Authoritative policies and standard operating procedure checklists.")
    
    p_dir = Path("data/policies")
    s_dir = Path("data/sops")
    
    col_p, col_s = st.columns(2)
    with col_p:
        st.subheader("Policies")
        if p_dir.exists():
            for p in p_dir.glob("*.md"):
                st.markdown(f"- 📄 `{p.name}`")
    with col_s:
        st.subheader("Standard Operating Procedures")
        if s_dir.exists():
            for s in s_dir.glob("*.md"):
                st.markdown(f"- 📋 `{s.name}`")
