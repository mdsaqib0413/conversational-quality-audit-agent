"""Test lab: expected versus actual, per feature and per call."""
from __future__ import annotations

import streamlit as st

from theme import html

from src.audit import ui_html as U
from src.audit.expectations import load_expected, load_spec
from src.audit.featuretests import call_comparison, run_all
from src.audit.rag import get_kb
from src.audit.transcript_io import find_transcripts, load_transcript_json

MARK = {"PASS": "✓", "FAIL": "✗", "WARN": "!", "SKIP": "–"}


def _table(rows) -> str:
    out = ['<div class="aq-card flush"><div style="padding:6px 18px">'
           '<div class="aq-cmp h"><span></span><span>What is checked</span><span>Expected</span><span>Actual</span></div>']
    for r in rows:
        st_ = "PASS" if r["ok"] else ("FAIL" if r["level"] == "hard" else "WARN")
        out.append(f'<div class="aq-cmp"><span class="aq-res {st_}">{MARK[st_]}</span><span>{U.esc(r["item"])}</span><span>{U.esc(r["expected"])}</span><span>{U.esc(r["actual"])}</span></div>')
    out.append("</div></div>")
    return "".join(out)


def render(root, audits) -> None:
    html(U.page_header("Test lab", "Every feature has an expected result written down in advance. This page shows what the system actually produced next to it."))
    expected, spec, kb = load_expected(), load_spec(), get_kb()
    if not expected:
        html(U.empty_state("No expected results yet", "Run  python scripts/build_expectations.py"))
        return
    files = [p for p in find_transcripts(root / "data" / "transcripts", only_verified=True) if p.stem in expected]
    reports = {r.call_id: r for r in audits if r.call_id in expected}
    result = run_all(files, kb, expected, spec, reports)
    s = result["summary"]
    cols = st.columns(4)
    for col, (k, label) in zip(cols, [("PASS", "Passing"), ("WARN", "Worth a look"), ("FAIL", "Failing"), ("SKIP", "Waiting for AI audits")]):
        col.markdown(f'<div class="aq-kpi"><div class="t">{label}</div><div class="v">{s.get(k, 0)}<small> features</small></div></div>', unsafe_allow_html=True)
    html(f'<div class="aq-tiny" style="margin:6px 2px 0 2px">{len(result["calls"])} labelled calls · {len(reports)} with a saved AI audit. Hard checks must pass; soft checks only warn.</div>')
    html(U.section_title("Feature by feature", "expected vs actual"))
    for f in result["features"]:
        icon = {"PASS": "PASS", "FAIL": "FAIL", "WARN": "WARN", "SKIP": "SKIP"}[f["status"]]
        with st.expander(f"{MARK[f['status']]}  {f['title']}  ·  {f['status']}", expanded=f["status"] in ("FAIL", "WARN")):
            html(f'<div class="aq-sub">{U.esc(f["plain"])}</div>')
            rows = [{"item": c["label"], "expected": c["expected"], "actual": c["actual"], "ok": c["status"] in ("PASS", "SKIP"), "level": c["level"]} for c in f["checks"]]
            html(_table(rows))
    html(U.section_title("Compare one call", "the same checks, call by call"))
    ids = result["calls"]
    pick = st.selectbox("Call", ids, label_visibility="collapsed")
    path = next(p for p in files if p.stem == pick)
    call, raw = load_transcript_json(path)
    exp = expected[pick]
    html(f'<div style="margin:4px 0 10px 0"><span class="aq-pill dark">Expected: {U.esc(exp["quality"].replace("_", " "))}</span> '
         f'<span class="aq-pill">{U.esc(raw["topic"])}</span></div>')
    if pick in reports:
        rows = call_comparison(reports[pick], call, raw, exp, kb)
    else:
        from src.audit.featuretests import offline_rows

        rows = offline_rows(call, raw, exp, kb)
        html(U.empty_state("No saved AI audit for this call", "Only the checks that need no AI are shown. Audit the call to see the rest."))
    bad = [r for r in rows if not r["ok"]]
    html(f'<div class="aq-sub">{len(rows) - len(bad)} of {len(rows)} checks match the expected result.</div>')
    html(_table(sorted(rows, key=lambda r: r["ok"])))
