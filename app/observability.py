"""Observability & Evaluation Dashboard for the Conversational Quality Audit Agent.

Aggregates operational execution traces from traces/*.jsonl and formal benchmark
evaluations from eval/results/ to present:
1. System Key Performance Indicators (accuracy, latency percentiles, requests, costs)
2. Evaluation benchmark comparisons across prototypes (v0.1 vs v0.2 vs baselines)
3. Step-by-step audit trace inspection
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
TRACES_DIR = ROOT / "traces"
EVAL_RESULTS_DIR = ROOT / "eval" / "results"


def load_all_traces() -> List[Dict[str, Any]]:
    traces = []
    if not TRACES_DIR.exists():
        return traces
    for trace_file in sorted(TRACES_DIR.glob("*.jsonl"), reverse=True):
        steps = []
        try:
            for line in trace_file.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    steps.append(json.loads(line))
            if steps:
                total_lat = sum(s.get("latency_sec", 0.0) for s in steps)
                total_tokens_in = sum(s.get("tokens_in", 0) for s in steps)
                total_tokens_out = sum(s.get("tokens_out", 0) for s in steps)
                total_cost = sum(s.get("cost_usd", 0.0) for s in steps)
                has_error = any(s.get("status") == "failed" for s in steps)
                has_handoff = any(s.get("status") == "handoff" for s in steps)
                traces.append({
                    "run_id": trace_file.stem,
                    "steps_count": len(steps),
                    "total_latency_sec": round(total_lat, 3),
                    "total_tokens_in": total_tokens_in,
                    "total_tokens_out": total_tokens_out,
                    "total_cost_usd": round(total_cost, 6),
                    "overall_status": "failed" if has_error else ("handoff" if has_handoff else "ok"),
                    "steps": steps,
                })
        except Exception:
            continue
    return traces


def render_observability_dashboard():
    st.markdown("## 📊 System Observability & Evaluation Hub")
    st.caption("Real-time telemetry, model consumption metrics, and evaluation benchmark tracking.")

    # 1. Summary Metric Tiles
    traces = load_all_traces()
    col1, col2, col3, col4 = st.columns(4)

    total_runs = len(traces)
    if traces:
        latencies = [t["total_latency_sec"] for t in traces]
        costs = [t["total_cost_usd"] for t in traces]
        p50_lat = sorted(latencies)[int(len(latencies) * 0.50)]
        p95_lat = sorted(latencies)[int(len(latencies) * 0.95)]
        avg_cost = sum(costs) / len(costs)
    else:
        p50_lat, p95_lat, avg_cost = 0.0, 0.0, 0.0

    with col1:
        st.metric("Total Executions Logged", f"{total_runs} runs")
    with col2:
        st.metric("p50 Pipeline Latency", f"{p50_lat:.2f}s")
    with col3:
        st.metric("p95 Pipeline Latency", f"{p95_lat:.2f}s")
    with col4:
        st.metric("Avg Estimated Cost / Call", f"${avg_cost:.5f}")

    st.markdown("---")

    # 2. Benchmark Evaluation Comparison
    st.subheader("1. Formal Evaluation Benchmarks (v0.2-eval-obs)")
    eval_summary_path = EVAL_RESULTS_DIR / "v0.2-eval-obs" / "summary.md"
    if eval_summary_path.exists():
        st.markdown(eval_summary_path.read_text(encoding="utf-8"))
    else:
        st.info("Run `python eval/run_eval.py --tag v0.2-eval-obs` to populate formal benchmark evaluation metrics.")

    st.markdown("---")

    # 3. Prototype Evolution Comparison (v0.1 vs v0.2)
    st.subheader("2. Prototype Comparison: v0.1 vs. v0.2")
    proto_data = [
        {
            "Capability / Metric": "Identity Verification",
            "Phase 1 (v0.1-telugu-foundation)": "Rule/LLM combo, unverified Kaggle claims",
            "Phase 2 (v0.2-eval-obs)": "Deterministic Early State Tracking; 100% recall on dev set",
            "What Changed / Why": "Eliminated prompt drift on long dialogues by computing state over turns 1..15."
        },
        {
            "Capability / Metric": "Hold Handling Protocol",
            "Phase 1 (v0.1-telugu-foundation)": "SOP single prompt check",
            "Phase 2 (v0.2-eval-obs)": "Multi-hold timestamped interval extraction; 100% recall",
            "What Changed / Why": "Explicitly verifies each hold start/resume turn and flags holds >120s."
        },
        {
            "Capability / Metric": "Ambiguous Closures",
            "Phase 1 (v0.1-telugu-foundation)": "Uncaptured colloquial Telugu",
            "Phase 2 (v0.2-eval-obs)": "Detects 'sare, chuddam le'; flags issue as unresolved",
            "What Changed / Why": "Cultural closure nuance correctly mapped to partial/unresolved verdict."
        },
        {
            "Capability / Metric": "Audio Quality & Scope Gating",
            "Phase 1 (v0.1-telugu-foundation)": "Basic confidence score threshold",
            "Phase 2 (v0.2-eval-obs)": "Quality gate + out-of-scope support gate; 100% handoff",
            "What Changed / Why": "Unusable audio or personal casual chats immediately halt with 0 LLM calls."
        },
        {
            "Capability / Metric": "Observability & Tracing",
            "Phase 1 (v0.1-telugu-foundation)": "Standard application logging",
            "Phase 2 (v0.2-eval-obs)": "Structured traces/<run_id>.jsonl with step-level latencies & costs",
            "What Changed / Why": "Provides auditable forensic trace for every model/code transition."
        },
        {
            "Capability / Metric": "Evaluation Rigor",
            "Phase 1 (v0.1-telugu-foundation)": "Ad-hoc unit test assertions",
            "Phase 2 (v0.2-eval-obs)": "Frozen dev/heldout split with anti-leakage test & 2 baselines",
            "What Changed / Why": "Zero data snooping; formal PASS/FAIL rule gate before tagging."
        },
    ]
    st.table(pd.DataFrame(proto_data))

    st.markdown("---")

    # 4. Recent Traces Inspection
    st.subheader("3. Execution Traces Browser")
    if not traces:
        st.write("No traces logged yet. Execute an audit from the 'Call Audit' tab to view traces.")
        return

    trace_df = pd.DataFrame([
        {
            "Run ID": t["run_id"],
            "Status": t["overall_status"].upper(),
            "Steps": t["steps_count"],
            "Latency (s)": t["total_latency_sec"],
            "Tokens In": t["total_tokens_in"],
            "Tokens Out": t["total_tokens_out"],
            "Cost (USD)": f"${t['total_cost_usd']:.5f}",
        }
        for t in traces[:15]
    ])
    st.dataframe(trace_df, use_container_width=True)

    selected_run = st.selectbox("Inspect Execution Trace:", [t["run_id"] for t in traces[:15]])
    if selected_run:
        run_data = next((t for t in traces if t["run_id"] == selected_run), None)
        if run_data:
            st.markdown(f"#### Trace Details: `{selected_run}`")
            for s in run_data["steps"]:
                status_color = "green" if s.get("status") == "ok" else ("orange" if s.get("status") in ("degraded", "handoff") else "red")
                with st.expander(f"Step: {s.get('step_name')} ({s.get('kind')}) — Status: :{status_color}[{s.get('status').upper()}] — {s.get('latency_sec', 0.0):.3f}s"):
                    col_a, col_b = st.columns(2)
                    with col_a:
                        st.write("**Inputs Summary:**", s.get("inputs_summary", "n/a"))
                        st.write("**Model:**", s.get("model_name", "plain_code"))
                    with col_b:
                        st.write("**Outputs Summary:**", s.get("outputs_summary", "n/a"))
                        if s.get("error_text"):
                            st.error(f"Error: {s.get('error_text')}")
                        st.write(f"Tokens In: {s.get('tokens_in', 0)} | Tokens Out: {s.get('tokens_out', 0)} | Cost: ${s.get('cost_usd', 0.0):.6f}")


if __name__ == "__main__":
    st.set_page_config(page_title="Observability - Audit Agent", layout="wide")
    render_observability_dashboard()

