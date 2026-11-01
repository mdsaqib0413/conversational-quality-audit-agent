"""AuditIQ: conversational quality audit for support calls.

Run:  streamlit run app/streamlit_app.py
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from pathlib import Path
from typing import List, Optional

t_script_start = time.perf_counter()
t_load_report = 0.0
t_render = 0.0

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "app"))

import streamlit as st
import streamlit.components.v1 as components

from theme import get_app_css, get_plotly_template, html
from src.audit import explain as X
from src.audit import ui_html as U
from src.audit.call_player import render_player_component, resolve_audio_path
from src.audit.llm import FatalLLMError, LLMError, NetworkError, QuotaExhaustedError, gemini_gateway, requests_used_today
from src.audit.pipeline import AUDIO_EXT, AuditPipeline
from src.audit.policy_check import get_involved_clause_ids
from src.audit.rag import KnowledgeBase, get_embedder, get_kb
from src.audit.review import apply_reviews_to_report
from src.audit.schemas import AuditReport
from src.audit.topic import detect_topic, get_live_context
from src.audit.transcript_io import find_transcripts, load_transcript_json
from src.live.engine import LiveSession
from src.live.player import LiveSimulator
from observability import render_observability_dashboard

st.set_page_config(page_title="AuditIQ · Call quality", page_icon="🎧", layout="wide", initial_sidebar_state="expanded")

# Check local Hugging Face cache for embedding model to set offline mode
def _is_model_in_hf_cache(model_name: str = "BAAI/bge-small-en-v1.5") -> bool:
    try:
        hf_hub = Path(os.getenv("HF_HOME", Path.home() / ".cache" / "huggingface" / "hub"))
        folder_name = "models--" + model_name.replace("/", "--")
        target = hf_hub / folder_name
        return target.is_dir() and any(target.iterdir())
    except Exception:
        return False


if _is_model_in_hf_cache():
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"

AUDIT_DIR = ROOT / "data" / "cache" / "audits"
LIVE_CALLS_DIR = ROOT / "data" / "live_calls"
PAGES = ["Dashboard", "Audit a call", "Report", "Policy lookup", "Live assist", "Test lab", "Observability"]


# ------------------------------------------------------------------------------ cached resource helpers
@st.cache_resource(show_spinner=False)
def get_cached_kb() -> KnowledgeBase:
    return get_kb()


@st.cache_resource(show_spinner=False)
def get_pipeline() -> AuditPipeline:
    return AuditPipeline(kb=get_cached_kb())


@st.cache_resource(show_spinner=False)
def get_cached_embedder(name: str = "BAAI/bge-small-en-v1.5"):
    return get_embedder(name)


import logging
import threading

_logger = logging.getLogger(__name__)

# Silence the "Please replace st.components.v1.html with st.iframe" deprecation
# st.iframe takes a URL src, not a raw HTML string, so it cannot be a drop-in replacement.
class _SuppressComponentsHtmlWarning(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:  # noqa: A003
        return "st.components.v1.html" not in record.getMessage()

logging.getLogger("streamlit").addFilter(_SuppressComponentsHtmlWarning())


def render_html_component(markup: str, height: int = 400, scrolling: bool = True) -> None:
    """Single call-site for injecting a self-contained HTML component."""
    components.html(markup, height=height, scrolling=scrolling)
_WARMED = False
_WARM_LOCK = threading.Lock()


def _warm_heavy_resources() -> None:
    try:
        try:
            from streamlit.runtime.scriptrunner_utils.script_run_context import SCRIPT_RUN_CONTEXT_ATTR_NAME
            if hasattr(threading.current_thread(), SCRIPT_RUN_CONTEXT_ATTR_NAME):
                delattr(threading.current_thread(), SCRIPT_RUN_CONTEXT_ATTR_NAME)
        except Exception:
            pass

        import jinja2  # noqa: F401
        import pandas  # noqa: F401
        import plotly  # noqa: F401

        get_kb()
        get_embedder()
    except Exception as exc:  # noqa: BLE001
        _logger.debug("Warmup error: %s", exc)


def warm_once() -> None:
    global _WARMED
    with _WARM_LOCK:
        if not _WARMED:
            _WARMED = True
            t = threading.Thread(target=_warm_heavy_resources, name="warmup_thread", daemon=True)
            t.start()


warm_once()


def get_audit_dir_mtime() -> int:
    if not AUDIT_DIR.exists():
        return 0
    return AUDIT_DIR.stat().st_mtime_ns


# ------------------------------------------------------------------------------ cached data helpers
@st.cache_data(show_spinner=False)
def load_report_cached(path_str: str, mtime: int) -> AuditReport:
    return AuditReport.model_validate_json(Path(path_str).read_text(encoding="utf-8"))


@st.cache_data(show_spinner=False)
def get_audit_index(dir_mtime: int) -> List[dict]:
    """Lightweight index of audits for navigation and selectors without parsing full reports on every rerun."""
    files = sorted(AUDIT_DIR.glob("*.json")) if AUDIT_DIR.exists() else []
    best: dict = {}
    for f in files:
        try:
            m = json.loads(f.read_text(encoding="utf-8"))
            cid = m.get("call_id")
            gen = m.get("generated_at", "")
            old = best.get(cid)
            if old is None or gen >= old.get("generated_at", ""):
                best[cid] = {
                    "call_id": cid,
                    "path": str(f),
                    "mtime": f.stat().st_mtime_ns,
                    "generated_at": gen,
                    "overall": m.get("scores", {}).get("overall", 0.0),
                    "grade": m.get("scores", {}).get("grade", "D"),
                    "critical_failure": m.get("scores", {}).get("critical_failure", False),
                    "source_set": m.get("meta", {}).get("source_set", "synthetic"),
                    "risk_flags": m.get("risk_flags", []),
                    "topic": m.get("topic", "general"),
                }
        except Exception:
            continue
    return [best[k] for k in sorted(best)]


@st.cache_data(show_spinner=False)
def saved_audits(dir_mtime: int) -> List[AuditReport]:
    idx = get_audit_index(dir_mtime)
    return [load_report_cached(it["path"], it["mtime"]) for it in idx]


def get_report_by_id(call_id: str) -> Optional[AuditReport]:
    idx = get_audit_index(get_audit_dir_mtime())
    item = next((x for x in idx if x["call_id"] == call_id), None)
    if not item:
        return None
    return load_report_cached(item["path"], item["mtime"])


@st.cache_data(show_spinner=False)
def get_cached_html_data(path_str: str, mtime: int, dark: bool = False) -> str:
    from src.audit.report import render_html
    rep = load_report_cached(path_str, mtime)
    return render_html(rep, dark=dark)


@st.cache_data(show_spinner=False)
def get_cached_pdf_data(path_str: str, mtime: int) -> bytes:
    from src.audit.report import render_pdf
    rep = load_report_cached(path_str, mtime)
    return render_pdf(rep)


@st.cache_data(show_spinner=False)
def build_plotly_fig_cached(fig_key: str, template: str = "plotly_white"):
    """Cached wrapper for Plotly figure construction when used."""
    return None


def goto(page: str) -> None:
    st.session_state["_goto"] = page


def open_report(rep: AuditReport) -> None:
    st.session_state["report"] = rep
    st.session_state["_goto"] = "Report"


@st.cache_data(show_spinner=False)
def sample_sources_cached(audio_mtime: int, trans_mtime: int):
    audio = sorted((ROOT / "data" / "audio").glob("call_*.mp3"))
    mono = [p for p in audio if not p.stem.endswith("_stereo")]
    stereo = [p for p in audio if p.stem.endswith("_stereo")]
    return mono, stereo, find_transcripts(ROOT / "data" / "transcripts")


def sample_sources():
    a_dir = ROOT / "data" / "audio"
    t_dir = ROOT / "data" / "transcripts"
    am = a_dir.stat().st_mtime_ns if a_dir.exists() else 0
    tm = t_dir.stat().st_mtime_ns if t_dir.exists() else 0
    return sample_sources_cached(am, tm)


# ------------------------------------------------------------------------------ navigation + sidebar
if "_goto" in st.session_state:
    st.session_state["nav"] = st.session_state.pop("_goto")
st.session_state.setdefault("nav", "Dashboard")
st.session_state.setdefault("dark_mode", False)

with st.sidebar:
    html(U.brand())
    st.write("")
    st.radio("Navigate", PAGES, key="nav", label_visibility="collapsed")
    st.write("")
    st.info("🔒 **Data Privacy Notice:** Calls may contain customer personal data (PII). Real customer audio must not be uploaded without approval. See docs/PRIVACY.md.")
    st.divider()
    dark_mode = st.toggle("Dark mode", value=st.session_state["dark_mode"], key="sidebar_dark_toggle")
    st.session_state["dark_mode"] = dark_mode
    use_cache = st.toggle("Reuse saved audits", value=True, help="Saved audits open instantly and use no AI requests.")
    try:
        model = gemini_gateway.describe()
    except Exception:  # noqa: BLE001
        model = "not configured"
    st.caption(f"AI model: `{model}`")
    st.caption(f"AI requests today: **{requests_used_today()}**")
    try:
        deg = getattr(gemini_gateway.provider, "degraded", [])
        if deg:
            st.caption("Compatibility mode: " + ", ".join(dict.fromkeys(deg)))
    except Exception:  # noqa: BLE001
        pass
    if st.button("Reload .env", help="After changing keys or models"):
        gemini_gateway.reload()
        st.cache_resource.clear()
        st.cache_data.clear()
        st.toast("Settings reloaded")
    kb = get_cached_kb()
    st.caption(f"Knowledge base: {len(kb.policies)} policy clauses · {len(kb.sops)} script steps")

# Inject styled theme CSS
html(f"<style>{get_app_css(st.session_state['dark_mode'])}{U.css()}</style>")

page = st.session_state["nav"]


# ------------------------------------------------------------------------------ pages
def page_dashboard() -> None:
    reps = saved_audits(get_audit_dir_mtime())
    scored = [r for r in reps if not getattr(r, "risk_flags", None)]
    unscored = [r for r in reps if getattr(r, "risk_flags", None)]
    n_scored, n_ns = len(scored), len(unscored)
    c1, c2 = st.columns([5, 1.4])
    with c1:
        ns_suffix = f", {n_ns} not scored" if n_ns else ""
        sub = (f"{n_scored} audited call(s){ns_suffix}. Open any call to see exactly what happened and why it scored that way."
               if reps else "Audit your first call to see the overview here.")
        html(U.page_header("Quality overview", sub))
    with c2:
        st.write("")
        st.button("＋  Audit a call", type="primary", on_click=goto, args=("Audit a call",))
    if not reps:
        html(U.empty_state("No audits yet", "Use “Audit a call”, or run  python eval/run_eval.py  to audit all sample calls."))
        return
    html(U.dash_hero(scored, unscored))
    html(U.section_title("All calls by grade", "click Open to see the full report"))
    ncols = 5 if unscored else 4
    grade_cols = st.columns(ncols)
    groups = [("A", "A · Excellent"), ("B", "B · Good"), ("C", "C · Needs work"), ("D", "D · Failing")]
    for col, (g, title) in zip(grade_cols, groups):
        items = [r for r in scored if r.scores.grade == g]
        with col:
            html(f'<div class="aq-gh"><span>{title}</span><span class="n">{len(items)}</span></div>')
            if not items:
                html('<div class="aq-empty" style="padding:14px">No calls</div>')
            for r in items:
                html(U.call_card(r))
                st.button("Open", key=f"open_{r.call_id}", on_click=open_report, args=(r,), use_container_width=True)
    if unscored:
        with grade_cols[4]:
            html(f'<div class="aq-gh"><span>Not scored · possible scam ({n_ns})</span><span class="n">{n_ns}</span></div>')
            for r in unscored:
                html(U.call_card(r))
                st.button("Open", key=f"open_{r.call_id}", on_click=open_report, args=(r,), use_container_width=True)
    html(U.section_title("What to focus on across all calls"))
    html(U.insights_card(scored))


def _run_audit(kind: str, path: str, name: str, language: Optional[str] = None) -> None:
    pipe = get_pipeline()
    holder = st.empty()
    skip_audio = kind != "audio"
    holder.markdown(U.progress_stepper("transcribe", skip_audio), unsafe_allow_html=True)
    bar = st.progress(0.0, text="Starting...")

    def progress(stage: str, frac: float, msg: str) -> None:
        bar.progress(min(max(frac, 0.0), 1.0), text=msg)
        holder.markdown(U.progress_stepper(stage, skip_audio), unsafe_allow_html=True)

    try:
        if kind == "audio":
            rep = pipe.audit_audio(path, call_id=name, use_cache=use_cache, progress=progress, language=language)
        else:
            rep = pipe.audit_transcript_file(path, use_cache=use_cache, progress=progress)
    except NetworkError as e:
        bar.empty()
        holder.empty()
        st.error("Cannot reach the AI service from this computer, so no request was sent and no quota was used. Check your internet, turn off VPN/proxy, or try a hotspot. "
                 "Run `python scripts/check_network.py` to see which address fails.")
        st.caption(str(e)[:300])
        return
    except QuotaExhaustedError as e:
        bar.empty()
        holder.empty()
        st.error("The AI daily quota is used up. Wait for the reset, or add a fallback model in `.env` (GEMINI_FALLBACK_MODELS=... or Groq/Ollama). Saved audits still open instantly.")
        st.caption(str(e)[:400])
        return
    except FatalLLMError as e:
        bar.empty()
        holder.empty()
        st.error(f"AI configuration problem: {str(e)[:500]}")
        return
    except LLMError as e:
        bar.empty()
        holder.empty()
        st.error(f"The AI step failed: {str(e)[:500]}")
        return
    except Exception as e:  # noqa: BLE001
        bar.empty()
        holder.empty()
        st.error(f"Could not audit this file: {e}")
        return
    bar.empty()
    holder.empty()
    open_report(rep)
    st.rerun()


@st.fragment
def _audit_sample_selector_fragment(options: dict, language: Optional[str] = None) -> None:
    pick = st.selectbox("Sample call", list(options))
    kind, p = options[pick]
    if kind == "audio":
        st.audio(str(p))
    stem = p.stem.replace("_stereo", "")
    tj = ROOT / "data" / "transcripts" / f"{stem}.json"
    if tj.exists() and st.toggle("Testing mode: show the expected result", value=False):
        gt = json.loads(tj.read_text(encoding="utf-8"))
        dev = [f"{k} ({v})" for k, v in gt["ground_truth"]["sop_steps"].items() if v != "followed"]
        viol = [f"{v['clause_id']} ({v['severity']})" for v in gt["ground_truth"]["policy_violations"]]
        gaps = ", ".join(gt["ground_truth"]["gaps"]) or "none"
        html(U.empty_state(f"Expected: {gt['quality'].replace('_', ' ')}",
                           f"Missed or partial steps: {', '.join(dev) or 'none'} · Rule violations: {', '.join(viol) or 'none'} · Gaps: {gaps}"))
    if st.button("Run audit on this sample", type="primary"):
        _run_audit(kind, str(p), stem, language=language)


def page_audit() -> None:
    html(U.page_header("Audit a call", "Upload a recording or pick a sample. You get a scored report in about a minute."))
    col_mode, col_lang = st.columns([3, 2])
    with col_mode:
        mode = st.radio("Source", ["Upload a recording", "Pick a sample call"], horizontal=True, label_visibility="collapsed")
    with col_lang:
        lang_choice = st.selectbox("Language", ["Auto", "English", "Telugu", "Hindi"], index=0, key="audit_lang_select")
        lang_map = {"Auto": "auto", "English": "en", "Telugu": "te", "Hindi": "hi"}
        chosen_lang = lang_map.get(lang_choice, "auto")

    if mode == "Upload a recording":
        up = st.file_uploader("Drop a call recording (MP3, WAV, M4A) or a transcript (.json)", type=[e.strip(".") for e in AUDIO_EXT] + ["json"])
        if up:
            if Path(up.name).suffix.lower() in AUDIO_EXT:
                st.audio(up)
            if st.button("Run audit", type="primary"):
                suffix = Path(up.name).suffix.lower()
                with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as f:
                    f.write(up.getbuffer())
                _run_audit("transcript" if suffix == ".json" else "audio", f.name, Path(up.name).stem, language=chosen_lang)
        return
    mono, stereo, transcripts = sample_sources()
    options: dict = {}
    for p in mono:
        options[f"{p.stem} · recording (mono, speakers found by AI)"] = ("audio", p)
    for p in stereo:
        options[f"{p.stem.replace('_stereo', '')} · recording (stereo, exact speaker split)"] = ("audio", p)
    for p in transcripts:
        options[f"{p.stem} · transcript only (fast, skips speech-to-text)"] = ("transcript", p)
    if not options:
        html(U.empty_state("No samples yet", "Generate them with  python scripts/make_audio.py --all"))
        return
    _audit_sample_selector_fragment(options, language=chosen_lang)


@st.fragment
def _script_view_fragment(rep: AuditReport) -> None:
    view = st.radio("View", ["Board", "Table"], horizontal=True, label_visibility="collapsed", key="script_view_toggle")
    html(U.script_board(rep) if view == "Board" else U.script_table(rep))


def page_report() -> None:
    global t_load_report
    t_lr_start = time.perf_counter()

    # Cache index lookup without parsing 36 full reports
    idx = get_audit_index(get_audit_dir_mtime())
    rep: Optional[AuditReport] = st.session_state.get("report")
    if rep is None and idx:
        rep = load_report_cached(idx[0]["path"], idx[0]["mtime"])
        st.session_state["report"] = rep

    t_load_report = time.perf_counter() - t_lr_start

    if rep is None:
        html(U.page_header("Report", "Nothing to show yet."))
        html(U.empty_state("No call selected", "Audit a call, or open one from the dashboard."))
        st.button("Audit a call", type="primary", on_click=goto, args=("Audit a call",))
        return

    top1, top2 = st.columns([3, 2])
    with top1:
        src_filter = st.radio("Source", ["All", "Synthetic", "Real"], horizontal=True, label_visibility="collapsed",
                              key="rpt_src_filter")
        filtered_idx = idx
        if src_filter == "Synthetic":
            filtered_idx = [x for x in idx if x["source_set"] == "synthetic"]
        elif src_filter == "Real":
            filtered_idx = [x for x in idx if x["source_set"] == "real"]

        def _pick_label(x: dict) -> str:
            if x.get("risk_flags"):
                return f"{x['call_id']}  ·  Not scored"
            return f"{x['call_id']}  ·  {x['overall']:.0f}/100  {x['grade']}"

        id_map = {x["call_id"]: _pick_label(x) for x in filtered_idx}
        if rep.call_id not in id_map:
            id_map[rep.call_id] = f"{rep.call_id}  ·  {'Not scored' if getattr(rep, 'risk_flags', None) else f'{rep.scores.overall:.0f}/100 {rep.scores.grade}'}"
        sorted_ids = sorted(id_map)
        pick_labels = [id_map[i] for i in sorted_ids]
        default_idx = sorted_ids.index(rep.call_id) if rep.call_id in sorted_ids else 0
        chosen_label = st.selectbox("Open a saved audit", pick_labels, index=default_idx, label_visibility="collapsed")
        choice = sorted_ids[pick_labels.index(chosen_label)]
        if choice != rep.call_id:
            nxt = get_report_by_id(choice)
            if nxt:
                st.session_state["report"] = nxt
                st.rerun()

    with top2:
        d1, d2, d3 = st.columns(3)
        # Find item in index for cached downloads
        cur_item = next((x for x in idx if x["call_id"] == rep.call_id), None)
        item_path = cur_item["path"] if cur_item else str(AUDIT_DIR / f"{rep.call_id}.json")
        item_mtime = cur_item["mtime"] if cur_item else 0
        try:
            pdf_bytes = get_cached_pdf_data(item_path, item_mtime)
            d1.download_button("PDF", pdf_bytes, file_name=f"audit_{rep.call_id}.pdf", mime="application/pdf", use_container_width=True)
        except Exception:  # noqa: BLE001
            d1.caption("PDF unavailable")
        html_str = get_cached_html_data(item_path, item_mtime, dark=st.session_state["dark_mode"])
        d2.download_button("HTML", html_str, file_name=f"audit_{rep.call_id}.html", mime="text/html", use_container_width=True)
        d3.download_button("JSON", rep.model_dump_json(indent=1), file_name=f"audit_{rep.call_id}.json", mime="application/json", use_container_width=True)

    html(U.report_header(rep))

    # ---- Real call: show dataset reference summary in a collapsed expander ----
    if rep.meta.source_set == "real":
        ref_path = ROOT / "data" / "audio" / "real_calls" / f"{rep.call_id}.reference.json"
        if ref_path.exists():
            with st.expander("Dataset reference summary (for comparison)", expanded=False):
                ref = json.loads(ref_path.read_text(encoding="utf-8"))
                st.caption(f"Source: [{ref.get('dataset', '')}]({ref.get('dataset_url', '')}), folder: `{ref.get('source_folder', '')}`")
                st.info(ref.get("note", ""))
                s = ref.get("summary", {})
                for k, v in s.items():
                    if v:
                        st.markdown(f"**{k.replace('_', ' ').title()}:** {v}")

    if rep.meta.diarization_method.startswith("heuristic"):
        st.error("Speaker separation used a low-confidence guess. Check the transcript tab before trusting these findings.")

    # Always show verdict banner (including scam warning)
    html(U.verdict_banner(rep))

    # ---- Call audio player with clickable key moments & synchronized transcript ----
    audio_path = resolve_audio_path(rep.call_id)
    player_html = render_player_component(rep, audio_path, dark=st.session_state["dark_mode"])
    render_html_component(player_html, height=580, scrolling=True)

    html(U.score_cards(rep))
    rep = apply_reviews_to_report(rep)
    tabs = st.tabs(["Overview", "QA Review", "Timeline", "Call script", "Company rules", "Coaching", "Transcript", "Score breakdown", "Details", "Trace"])
    with tabs[0]:
        html(U.summary_card(rep))
        html(U.section_title("The call in numbers", "what each number means"))
        html(U.metrics_grid(rep))
    with tabs[1]:
        html(U.findings_observed_section(rep))
        html(U.findings_inferred_section(rep))
        st.markdown("### Human Review & Calibration")
        st.caption("Reviewers can accept or overturn AI findings. Overturned findings remain visible with calibration notes.")
        if not rep.findings:
            st.info("No structured findings recorded for this call.")
        else:
            for f in rep.findings:
                with st.expander(f"[{f.kind.upper()}] {f.criterion_id} - {f.name} ({f.verdict})", expanded=f.verdict in ("missed", "violation")):
                    c_l, c_r = st.columns([3, 2])
                    with c_l:
                        st.markdown(f"**AI Determination:** `{f.verdict.upper()}` | Severity: `{f.severity.upper()}` | Certainty: `{f.certainty.upper()}`")
                        if f.certainty_reason:
                            st.caption(f"Certainty reason: {f.certainty_reason}")
                        if f.evidence:
                            st.markdown("**Evidence Quotes:**")
                            for ev in f.evidence:
                                ts = f"[{int(ev.start_s//60):02d}:{int(ev.start_s%60):02d}-{int(ev.end_s//60):02d}:{int(ev.end_s%60):02d}]" if ev.end_s else f"[Turn {ev.turn_id}]"
                                st.markdown(f'- `{ts}` *{ev.speaker.upper()}*: "{ev.quote}"')
                        if f.explanation:
                            st.info(f.explanation)
                    with c_r:
                        cur_status = f.reviewer_status
                        status_color = "🟢" if cur_status == "accepted" else ("🔴" if cur_status == "overturned" else "🟡")
                        st.markdown(f"**Reviewer Status:** {status_color} `{cur_status.upper()}`")
                        note = st.text_input("Reviewer note", value=f.reviewer_note or "", key=f"note_{f.finding_id}_{rep.call_id}")
                        b_acc, b_ovt = st.columns(2)
                        if b_acc.button("Accept", key=f"acc_{f.finding_id}_{rep.call_id}", use_container_width=True):
                            save_review_decision(rep.call_id, f.finding_id, "accepted", note)
                            st.rerun()
                        if b_ovt.button("Overturn", key=f"ovt_{f.finding_id}_{rep.call_id}", use_container_width=True):
                            save_review_decision(rep.call_id, f.finding_id, "overturned", note)
                            st.rerun()
    with tabs[2]:
        html(U.emotion_section(rep))
        html(U.section_title("Conversation gaps"))
        html(U.gaps_section(rep))
    with tabs[3]:
        _script_view_fragment(rep)
    with tabs[4]:
        html(U.policy_section(rep))
        html(U.policies_and_sops_involved_section(rep, kb=kb))
    with tabs[5]:
        html(U.coaching_section(rep))
    with tabs[6]:
        html(U.transcript_section(rep))
    with tabs[7]:
        html(U.walkthrough_section(rep))
    with tabs[8]:
        html(U.details_section(rep))


@st.fragment
def _policy_page_fragment() -> None:
    idx = get_audit_index(get_audit_dir_mtime())
    call_options = ["All policies (no call filter)"] + [x["call_id"] for x in idx]
    pick_call = st.selectbox("Pick a call to view its involved policies", call_options)

    if pick_call != "All policies (no call filter)":
        call_rep = get_report_by_id(pick_call)
        if call_rep:
            clause_ids, was_computed = get_involved_clause_ids(call_rep, kb)
            st.info(f"Showing {len(clause_ids)} policies involved in **{pick_call}** (topic: `{call_rep.topic}`).")
            clauses = [kb.by_id[cid] for cid in clause_ids if cid in kb.by_id]
            for c in clauses:
                html(f'<div class="aq-pol"><div class="head"><span class="aq-chip">{U.esc(c.id)}</span><b>{U.esc(c.title)}</b></div>'
                     f'<div style="font-size:13.5px;color:var(--aq-text-body,#3C3C38)">{U.esc(c.body(900))}</div></div>')
            return

    c1, c2 = st.columns([1, 2])
    topic = c1.selectbox("Topic", ["refund", "billing", "shipping", "warranty", "complaint", "general"], format_func=X.topic_label)
    query = c2.text_input("Or describe the situation", placeholder="Customer wants a refund for a smartwatch delivered 9 days ago")
    if query.strip():
        det = detect_topic([("customer", query)])
        html(f'<div style="margin:6px 0 12px 0"><span class="aq-pill dark">Detected: {X.topic_label(det.topic)}</span> <span class="aq-tiny">{det.confidence:.0%} confident</span></div>')
        clauses = kb.retrieve_policies(query, topic=det.topic if det.topic != "general" else topic, k=8)
    else:
        clauses = kb.policies_for_topic(topic)
    for c in clauses:
        html(f'<div class="aq-pol"><div class="head"><span class="aq-chip">{U.esc(c.id)}</span><b>{U.esc(c.title)}</b></div>'
             f'<div style="font-size:13.5px;color:var(--aq-text-body,#3C3C38)">{U.esc(c.body(900))}</div></div>')


def page_policy() -> None:
    html(U.page_header("Policy lookup", "Find the company rules that apply. In live mode the same search runs while the agent is talking."))
    _policy_page_fragment()


@st.fragment(run_every=1.5)
def _live_stream_view() -> None:
    session: Optional[LiveSession] = st.session_state.get("live_session")
    sim: Optional[LiveSimulator] = st.session_state.get("live_simulator")
    if session is None:
        html(U.empty_state("Live engine ready", "Select a call recording above and click 'Start Live' to begin real-time streaming."))
        return

    snap = session.get_snapshot()

    # ---- End-of-call card when session has ENDED (return early to stop repainting) ----
    if snap.status == "ended":
        if st.session_state.get("_live_last_known_status") != "ended":
            st.session_state["_live_last_known_status"] = "ended"
            st.rerun()

        dur_mm = int(snap.duration_sec // 60)
        dur_ss = int(snap.duration_sec % 60)
        danger_ct = sum(1 for a in snap.alerts if a.severity == "danger")
        warn_ct = sum(1 for a in snap.alerts if a.severity == "warning")
        info_ct = sum(1 for a in snap.alerts if a.severity == "info")
        done_steps = [s for s in snap.sop_checklist if s.status == "done"]
        partial_steps = [s for s in snap.sop_checklist if s.status == "partial"]
        missed_steps = [s for s in snap.sop_checklist if s.status in ("not_yet", "pending", "missed")]
        missed_ids = ", ".join(s.step_id for s in missed_steps) or "None"
        mood_hist = snap.customer_mood

        sop_summary = f"SOP done {len(done_steps)} / partial {len(partial_steps)} / missed {len(missed_steps)}"
        next_action = f"Call complete: missed steps {missed_ids}"

        html(
            f'<div class="aq-card" style="border:2px solid var(--aq-accent,#8B9BFF);padding:18px 22px;margin-bottom:16px">'
            f'<div style="display:flex;align-items:center;gap:10px;margin-bottom:12px">'
            f'<span style="background:#6F7685;color:#fff;border-radius:20px;padding:3px 14px;font-size:12px;font-weight:700;letter-spacing:0.07em">CALL ENDED</span>'
            f'<span style="font-size:14px;font-weight:700">Duration: {dur_mm}:{dur_ss:02d}</span>'
            f'</div>'
            f'<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-bottom:12px">'
            f'<div class="aq-card" style="padding:7px 8px;text-align:center"><div class="aq-tiny" style="font-weight:700">DANGER</div><div style="font-size:17px;font-weight:800;color:#F87171">{danger_ct}</div></div>'
            f'<div class="aq-card" style="padding:7px 8px;text-align:center"><div class="aq-tiny" style="font-weight:700">WARNING</div><div style="font-size:17px;font-weight:800;color:#FBBF24">{warn_ct}</div></div>'
            f'<div class="aq-card" style="padding:7px 8px;text-align:center"><div class="aq-tiny" style="font-weight:700">INFO</div><div style="font-size:17px;font-weight:800;color:#60A5FA">{info_ct}</div></div>'
            f'<div class="aq-card" style="padding:7px 8px;text-align:center"><div class="aq-tiny" style="font-weight:700">SOP STEPS</div><div style="font-size:14px;font-weight:800;color:#34D399">{len(done_steps)} <span style="font-size:11px;color:#FBBF24">+{len(partial_steps)}p</span> <span style="font-size:11px;color:#F87171">-{len(missed_steps)}m</span></div></div>'
            f'</div>'
            f'<div style="font-size:12.5px;margin-bottom:4px"><b>{sop_summary}</b> · <b>Final topic:</b> {U.esc(snap.detected_topic.replace("_"," ").title())} · <b>Customer mood:</b> {U.esc(mood_hist)} · <b>Missed SOP:</b> {U.esc(missed_ids)}</div>'
            f'<div style="font-size:12px;color:var(--aq-accent,#8B9BFF);font-weight:600;margin-top:2px">Next prescribed action: {U.esc(next_action)}</div>'
            f'</div>'
        )

        cid = snap.call_id or f"live_{int(snap.duration_sec)}"
        col_audit, col_restart = st.columns([2, 1])
        with col_audit:
            if st.button("📋 Run full audit on this call",
                         help="Uses 2 AI requests. Saves transcript to data/live_calls/ then opens the full report.",
                         type="primary", key="live_run_audit_btn"):
                import json as _json
                LIVE_CALLS_DIR.mkdir(parents=True, exist_ok=True)
                live_json_path = LIVE_CALLS_DIR / f"{cid}_live.json"
                turns_data = [
                    {
                        "turn_id": t.turn_id,
                        "speaker": t.speaker,
                        "text": t.text,
                        "start_time": round(t.start, 2),
                        "end_time": round(t.end, 2),
                        "pause_before_sec": round(max(0.0, t.start - (snap.turns[i-1].end if i > 0 else 0.0)), 2),
                        "interrupts_previous": bool(i > 0 and t.start < snap.turns[i-1].end),
                    }
                    for i, t in enumerate(snap.turns)
                ]
                live_json_path.write_text(
                    _json.dumps({"id": cid, "call_id": cid, "source_set": "live", "turns": turns_data},
                                indent=2, ensure_ascii=False),
                    encoding="utf-8",
                )
                pipe = get_pipeline()
                try:
                    call, _ = load_transcript_json(str(live_json_path))
                    call.call_id = cid
                    rep = pipe.audit_call(call, use_cache=False, source_set="live")
                    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
                    (AUDIT_DIR / f"{cid}.json").write_text(rep.model_dump_json(indent=1), encoding="utf-8")
                    st.cache_data.clear()
                    open_report(rep)
                    st.rerun()
                except Exception as _e:
                    st.error(f"Audit failed: {_e}")
        with col_restart:
            if st.button("🔄 Start again", key="live_restart_btn_card"):
                st.session_state.pop("live_session", None)
                st.session_state.pop("live_simulator", None)
                st.session_state.pop("_live_last_known_status", None)
                st.rerun()
        return

    # ---- end_suggested non-blocking banner ----
    if snap.end_suggested:
        html('<div style="background:rgba(139,155,255,0.10);border:1px solid var(--aq-accent,#8B9BFF);border-radius:8px;padding:7px 13px;margin-bottom:8px;font-size:12.5px;color:var(--aq-accent,#8B9BFF);font-weight:600">📞 Call looks finished. Use \'End call\' to close the session.</div>')

    # Alert strip
    if snap.alerts:
        alert_boxes = []
        for a in snap.alerts:
            sev_bg = "var(--aq-risk-bg, rgba(248,113,113,0.12))" if a.severity == "danger" else "var(--aq-real-bg, rgba(251,191,36,0.12))"
            sev_border = "var(--aq-risk-border, #F87171)" if a.severity == "danger" else "var(--aq-real-border, #FBBF24)"
            sev_color = "var(--aq-risk-text, #F87171)" if a.severity == "danger" else "var(--aq-real-text, #FBBF24)"
            alert_boxes.append(
                f'<div style="background:{sev_bg};border:1.5px solid {sev_border};border-radius:12px;padding:9px 13px;margin-bottom:8px">'
                f'<div style="display:flex;align-items:center;justify-content:space-between">'
                f'<b style="font-size:13px;color:{sev_color}">⚠ [{a.clause_id}] {U.esc(a.name)}</b>'
                f'<span class="aq-tiny" style="font-weight:700">{int(a.time_sec//60)}:{int(a.time_sec%60):02d}</span>'
                f'</div>'
                f'<div style="font-size:12.5px;color:var(--aq-text);margin-top:3px">{U.esc(a.message)}</div>'
                f'<div style="font-size:11.5px;font-style:italic;color:var(--aq-text-muted);margin-top:2px">Offending speech: "{U.esc(a.offending_quote)}"</div>'
                f'</div>'
            )
        alert_html = "".join(alert_boxes)
    else:
        alert_html = '<div style="background:var(--aq-zone-pos, rgba(52,211,153,0.08));border:1px solid #34D399;border-radius:12px;padding:8px 12px;margin-bottom:10px;font-size:12.5px;color:#34D399;font-weight:600">✓ No compliance violations detected so far</div>'

    left, right = st.columns([1.15, 1])

    with left:
        html(f'<div class="aq-h" style="margin-bottom:8px">Real-Time Compliance Alerts</div>{alert_html}')

        # Transcript bubbles
        bubbles = []
        for t in snap.turns:
            spk_lbl = "Agent" if t.speaker == "agent" else "Customer"
            partial_note = " <i>(speaking...)</i>" if t.partial else ""
            p_style = "opacity:0.8;font-style:italic;" if t.partial else ""
            t_mm = int(t.start // 60)
            t_ss = int(t.start % 60)
            bubbles.append(
                f'<div class="aq-turn {t.speaker}">'
                f'<div class="meta"><b>{spk_lbl}</b> · #{t.turn_id} · {t_mm}:{t_ss:02d}{partial_note}</div>'
                f'<div class="bub" style="{p_style}">{U.esc(t.text)}</div>'
                f'</div>'
            )

        sub_lbl = f"Duration: {int(snap.duration_sec//60)}:{int(snap.duration_sec%60):02d} · {'Stereo (exact speakers)' if snap.stereo_exact else 'Mono (approximate)'}"
        if not bubbles:
            bubbles_html = '<div style="padding:24px;text-align:center;color:var(--aq-text-muted)">Listening for incoming audio...</div>'
        else:
            bubbles_html = "".join(bubbles)

        html(
            f'<div class="aq-card" style="display:flex;flex-direction:column">'
            f'<div class="aq-h">Live Conversation</div>'
            f'<div class="aq-sub">{sub_lbl}</div>'
            f'<div id="live-turn-stream" style="max-height:430px;overflow-y:auto;display:flex;flex-direction:column;gap:8px;padding-right:4px;margin-top:6px">{bubbles_html}</div>'
            f'</div>'
            f'<script>var b=document.getElementById("live-turn-stream");if(b)b.scrollTop=b.scrollHeight;</script>'
        )

    with right:
        # Detected topic card
        sig_chips = "".join(f'<span class="aq-pill info">{U.esc(s.replace("_", " "))}</span> ' for s in snap.signals)
        html(
            f'<div class="aq-card tint" style="padding:12px 16px;margin-bottom:10px">'
            f'<div class="aq-tiny" style="font-weight:700;letter-spacing:.08em">DETECTED TOPIC</div>'
            f'<div class="aq-big" style="font-size:26px;margin:2px 0">{U.esc(X.topic_label(snap.detected_topic))}</div>'
            f'<div class="aq-tiny">{snap.topic_confidence:.0%} confident</div>'
            f'<div style="margin-top:6px">{sig_chips}</div>'
            f'</div>'
        )

        # 4 Small meters
        m_timer = f"{int(snap.duration_sec // 60)}:{int(snap.duration_sec % 60):02d}"
        m_share = f"{int(snap.agent_talk_share*100)}% / {int(snap.customer_talk_share*100)}%"
        mood_color = "#34D399" if snap.customer_mood == "Calm" else ("#F87171" if snap.customer_mood in ("Angry", "Frustrated") else "#A3A9B5")
        m_silence = f"{snap.last_silence_sec:.1f}s"

        html(
            f'<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-bottom:12px">'
            f'<div class="aq-card" style="padding:8px 6px;text-align:center"><div class="aq-tiny" style="font-weight:700">TIMER</div><div style="font-size:15px;font-weight:700;margin-top:2px">{m_timer}</div></div>'
            f'<div class="aq-card" style="padding:8px 6px;text-align:center"><div class="aq-tiny" style="font-weight:700">AGENT/CUST</div><div style="font-size:13px;font-weight:600;margin-top:4px">{m_share}</div></div>'
            f'<div class="aq-card" style="padding:8px 6px;text-align:center"><div class="aq-tiny" style="font-weight:700">MOOD</div><div style="font-size:13px;font-weight:700;margin-top:4px;color:{mood_color}">{snap.customer_mood}</div></div>'
            f'<div class="aq-card" style="padding:8px 6px;text-align:center"><div class="aq-tiny" style="font-weight:700">DEAD AIR</div><div style="font-size:13px;font-weight:600;margin-top:4px">{m_silence}</div></div>'
            f'</div>'
        )

        # SOP checklist & Next Step Callout
        if snap.next_step:
            crit_badge = " · Critical" if snap.next_step.critical else ""
            html(
                f'<div style="background:rgba(139,155,255,0.14);border:1.5px solid var(--aq-accent,#8B9BFF);border-radius:12px;padding:9px 13px;margin-bottom:10px">'
                f'<div class="aq-tiny" style="color:var(--aq-accent,#8B9BFF);font-weight:700;letter-spacing:0.06em">NEXT PRESCRIBED ACTION</div>'
                f'<div style="font-weight:700;font-size:14px;margin-top:2px">[{snap.next_step.step_id}] {snap.next_step.name}{crit_badge}</div>'
                f'</div>'
            )

        html('<div class="aq-h" style="margin:4px 0 6px 2px">Policies for this call right now</div>')
        for cl in snap.top_clauses:
            html(
                f'<div class="aq-pol" style="margin-bottom:6px">'
                f'<div class="head"><span class="aq-chip">{U.esc(cl.id)}</span><b style="font-size:13px">{U.esc(cl.title)}</b></div>'
                f'<div style="font-size:12px;color:var(--aq-text-body,#3C3C38);line-height:1.4">{cl.text}</div>'
                f'</div>'
            )

        # Compact SOP Checklist
        if snap.sop_checklist:
            sop_items = []
            for s in snap.sop_checklist:
                if s.status == "done":
                    icon = '<span style="color:#34D399;font-weight:700" title="Done">✓</span>'
                    st_style = "color:var(--aq-text-muted);text-decoration:none;"
                elif s.status == "partial":
                    icon = '<span style="color:#FBBF24;font-weight:700" title="Partial">◐</span>'
                    st_style = "color:#FBBF24;font-weight:600;"
                else:  # not yet
                    icon = '<span style="color:var(--aq-text-tiny,#6F7685);font-weight:600" title="Not yet">○</span>'
                    st_style = "color:var(--aq-text-tiny,#6F7685);"
                sop_items.append(f'<div style="display:flex;align-items:center;gap:7px;font-size:12px;margin-bottom:3px">{icon} <span style="{st_style}">[{s.step_id}] {U.esc(s.name)}</span></div>')
            html(f'<div class="aq-card" style="padding:10px 14px;margin-top:10px"><div class="aq-tiny" style="font-weight:700;letter-spacing:0.06em;margin-bottom:6px">SOP MILESTONE TRACKER</div>{"".join(sop_items[:8])}</div>')


def _live_assist_controls() -> None:
    audio_dir = ROOT / "data" / "audio"
    audio_files = sorted(audio_dir.glob("*.mp3"))
    if not audio_files:
        st.warning("No audio files found in data/audio.")
        return

    options = []
    file_map = {}
    for p in audio_files:
        is_stereo = "_stereo" in p.name
        label = f"{p.stem.replace('_stereo', '')} ({'Stereo' if is_stereo else 'Mono'})"
        options.append(label)
        file_map[label] = p

    sess: Optional[LiveSession] = st.session_state.get("live_session")
    session_status = sess.status if sess is not None else "idle"
    session_ended = session_status == "ended"
    is_running = session_status == "running"

    c1, c2, c3, c4, c5 = st.columns([2.5, 1.2, 1.1, 1.1, 1.4])
    selected_label = c1.selectbox("Recording to simulate", options, key="live_audio_picker", disabled=session_ended or is_running)
    speed_label = c2.selectbox("Speed", ["1.0x (Real-time)", "2.0x (Fast)"], key="live_speed_picker", disabled=session_ended or is_running)
    speed = 2.0 if "2.0x" in speed_label else 1.0

    sim: Optional[LiveSimulator] = st.session_state.get("live_simulator")

    if session_ended:
        if c3.button("🔄 Start again", use_container_width=True, key="live_start_again_btn", type="primary"):
            st.session_state.pop("live_session", None)
            st.session_state.pop("live_simulator", None)
            st.session_state.pop("_live_last_known_status", None)
            st.rerun()
    elif not is_running:
        if c3.button("▶ Start Live", type="primary", use_container_width=True, key="live_start_btn"):
            old_sim: Optional[LiveSimulator] = st.session_state.get("live_simulator")
            if old_sim:
                old_sim.stop()
            old_sess2: Optional[LiveSession] = st.session_state.get("live_session")
            if old_sess2:
                old_sess2.stop()

            target_audio = file_map[selected_label]
            call_id_extracted = target_audio.stem.replace("_stereo", "")
            new_session = LiveSession(model_size="base.en", chunk_duration_sec=3.0, overlap_sec=0.5, call_id=call_id_extracted)
            simulator = LiveSimulator(audio_path=target_audio, session=new_session, speed=speed)
            st.session_state["live_session"] = new_session
            st.session_state["live_simulator"] = simulator
            st.session_state.pop("_live_last_known_status", None)
            simulator.start()
            st.rerun()
    else:
        if c3.button("⏹ Stop", use_container_width=True, key="live_stop_btn"):
            if sim:
                sim.stop()
            if sess:
                sess.flush_and_end()
            st.session_state["_live_last_known_status"] = "ended"
            st.rerun()

    # Manual End call button (only available while running)
    if is_running:
        if c4.button("🔚 End call", use_container_width=True, key="live_end_call_btn"):
            if sim:
                sim.stop()
            if sess:
                sess.flush_and_end()
            st.session_state["_live_last_known_status"] = "ended"
            st.rerun()

    with c5:
        if session_ended:
            html('<div style="display:flex;align-items:center;gap:8px;padding-top:28px"><span style="width:10px;height:10px;border-radius:50%;background:#6F7685;display:inline-block"></span><span style="background:#6F7685;color:#fff;border-radius:12px;padding:3px 10px;font-size:11px;font-weight:700;letter-spacing:0.06em">CALL ENDED</span> <span class="aq-pill" style="font-size:11px">AI: 0</span></div>')
        elif is_running:
            html('<div style="display:flex;align-items:center;gap:8px;padding-top:28px"><span style="width:10px;height:10px;border-radius:50%;background:#34D399;display:inline-block;box-shadow:0 0 8px #34D399"></span><b style="font-size:13px;color:#34D399">STREAMING LIVE</b> <span class="aq-pill" style="font-size:11px">AI: 0</span></div>')
        else:
            html('<div style="display:flex;align-items:center;gap:8px;padding-top:28px"><span style="width:10px;height:10px;border-radius:50%;background:#6F7685;display:inline-block"></span><span style="font-size:13px;color:var(--aq-text-muted)">Ready</span> <span class="aq-pill" style="font-size:11px">AI: 0</span></div>')


@st.fragment
def _live_assist_fragment(tsamples) -> None:
    pick = st.selectbox("Call", [p.name for p in tsamples], key="live_pick")
    call, _raw = load_transcript_json(next(p for p in tsamples if p.name == pick))
    c1, c2 = st.columns(2)
    upto = c1.slider("How far into the call", 1, len(call.turns), min(4, len(call.turns)))
    window = c2.slider("Turns the assistant looks at", 2, 10, 6)
    so_far = call.turns[:upto]
    ctx = get_live_context(so_far, window=window, kb=kb, k=6)
    left, right = st.columns([1.15, 1])
    with left:
        bubbles = "".join(
            f'<div class="aq-turn {t.speaker}"><div class="meta"><b>{"Agent" if t.speaker == "agent" else "Customer"}</b> · #{t.turn_id}</div><div class="bub">{U.esc(t.text)}</div></div>'
            for t in so_far[-window:])
        html(f'<div class="aq-card" style="display:flex;flex-direction:column"><div class="aq-h">Conversation so far</div><div class="aq-sub">Last {min(window, len(so_far))} turn(s)</div>{bubbles}</div>')
    with right:
        sig = "".join(f'<span class="aq-pill info">{U.esc(s.replace("_", " "))}</span> ' for s in ctx.signals)
        html(f'<div class="aq-card tint"><div class="aq-tiny" style="font-weight:700;letter-spacing:.08em">DETECTED TOPIC</div><div class="aq-big" style="font-size:30px;margin:4px 0">{U.esc(X.topic_label(ctx.detected_topic))}</div>'
             f'<div class="aq-tiny">{ctx.confidence:.0%} confident</div><div style="margin-top:8px">{sig}</div></div>')
        html('<div class="aq-h" style="margin:6px 0 8px 2px">Rules to keep in view</div>')
        for cl in ctx.clauses:
            html(f'<div class="aq-pol"><div class="head"><span class="aq-chip">{U.esc(cl["id"])}</span><b style="font-size:13.5px">{U.esc(cl["title"])}</b></div>'
                 f'<div style="font-size:12.5px;color:var(--aq-text-muted,#55554F)">{U.esc(cl["text"][:260])}</div></div>')


def page_live() -> None:
    html(U.page_header("Live Assist", "Real-time co-pilot for active calls. Transcribes speech, surfaces authoritative policy clauses, and alerts on compliance risks as words are spoken. Zero AI requests used."))
    tab_live, tab_replay = st.tabs(["Live", "Replay (old)"])

    with tab_live:
        _live_assist_controls()
        _live_stream_view()

    with tab_replay:
        _, _, tsamples = sample_sources()
        if not tsamples:
            html(U.empty_state("No transcripts yet", "Add transcripts to data/transcripts."))
        else:
            _live_assist_fragment(tsamples)


def page_test_lab() -> None:
    try:
        import test_lab
    except ImportError:
        html(U.page_header("Test lab", "Expected versus actual results for every feature."))
        html(U.empty_state("Test lab not installed", "Add app/test_lab.py to enable it."))
        return
    test_lab.render(ROOT, saved_audits(get_audit_dir_mtime()))


ROUTER = {"Dashboard": page_dashboard, "Audit a call": page_audit, "Report": page_report, "Policy lookup": page_policy,
          "Live assist": page_live, "Test lab": page_test_lab, "Observability": render_observability_dashboard}

t_render_start = time.perf_counter()
ROUTER[page]()
t_render = time.perf_counter() - t_render_start

t_script_total = time.perf_counter() - t_script_start
if os.getenv("AUDIT_DEBUG_TIMING") == "1":
    print(f"[timing] page={page} script_total={t_script_total:.3f} load_report={t_load_report:.3f} render={t_render:.3f}", flush=True)
