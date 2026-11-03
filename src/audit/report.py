"""Render an AuditReport to HTML and PDF (coaching document for the agent)."""

from __future__ import annotations

import base64
import io
import logging
import re
from typing import Optional

from jinja2 import Environment, select_autoescape

from .schemas import AuditReport, extract_failure_reason, extract_degraded_reason, extract_degraded_reason
from .viz import esc

logger = logging.getLogger(__name__)

STATUS_COLOR = {"followed": "#1a7f37", "partial": "#b7791f", "missed": "#c0262d", "not_applicable": "#6b7280"}
STATUS_LABEL = {"followed": "Followed", "partial": "Partial", "missed": "Missed", "not_applicable": "N/A"}
GRADE_COLOR = {"A": "#1a7f37", "B": "#2b6cb0", "C": "#b7791f", "D": "#c0262d"}
SEV_COLOR = {"none": "#6b7280", "minor": "#b7791f", "major": "#dd6b20", "critical": "#c0262d"}

TEMPLATE = """<!doctype html>
<html><head><meta charset="utf-8"><title>Audit report {{ r.call_id }}</title>
<style>
 @page { size: A4; margin: 1.5cm; }
 body { font-family: Helvetica, Arial, sans-serif; font-size: 10pt; color: #1f2937; }
 h1 { font-size: 20pt; margin: 0 0 4px 0; color: #111827; }
 h2 { font-size: 13pt; margin: 18px 0 6px 0; color: #5b21b6; border-bottom: 1px solid #ddd6fe; padding-bottom: 3px; }
 h3 { font-size: 10.5pt; margin: 10px 0 4px 0; }
 table { width: 100%; border-spacing: 0; }
 th { background-color: #f3f0ff; text-align: left; font-size: 9pt; padding: 5px; border: 1px solid #e5e7eb; }
 td { padding: 5px; border: 1px solid #e5e7eb; vertical-align: top; font-size: 9pt; }
 .muted { color: #6b7280; font-size: 8.5pt; }
 .quote { color: #374151; font-style: italic; }
 .badge { font-weight: bold; }
 .warn { background-color: #fff7ed; border: 1px solid #fed7aa; padding: 6px; font-size: 9pt; }
 .box { border: 1px solid #e5e7eb; padding: 8px; }
 .grade { font-size: 30pt; font-weight: bold; }
</style></head><body>

<table style="border:none"><tr>
 <td style="border:none; width:70%">
  <div class="muted">CONVERSATIONAL QUALITY AUDIT &middot; ShopEase</div>
  <h1>Call {{ r.call_id }}</h1>
  <div class="muted">Topic: <b>{{ r.topic }}</b> ({{ (r.topic_confidence*100)|round|int }}% confidence){% if r.signals %} &middot; signals: {{ r.signals|join(', ') }}{% endif %} &middot; generated {{ r.generated_at }}</div>
 </td>
 <td style="border:none; text-align:center">
  {% if r.status == "failed" %}
  <div class="grade" style="color:#c0262d;font-size:16pt">Audit failed</div>
  <div class="muted">No score</div>
  {% elif r.risk_flags %}
  <div class="grade" style="color:#c0262d;font-size:15pt">Not scored</div>
  <div class="muted">Possible scam / social-engineering pattern</div>
  {% else %}
  <div class="grade" style="color:{{ grade_color }}">{{ r.scores.grade }}</div>
  <div><b>{{ r.scores.overall }}</b> / 100</div>
  <div class="muted">{{ grade_label_display }}</div>
  {% endif %}
 </td></tr></table>

{% if r.status == "failed" %}
<div class="warn" style="background-color:#fee2e2; border:1px solid #ef4444; color:#991b1b; padding:10px 14px; margin-top:8px; font-weight:600; border-radius:6px; font-size:11pt">
Audit failed: {{ failed_reason }}; no score
</div>
{% elif r.status == "degraded" %}
<div class="warn" style="background-color:#fef3c7; border:1px solid #f59e0b; color:#92400e; padding:8px 12px; margin-top:8px; font-weight:600; border-radius:6px">
degraded input quality ({{ degraded_reason }})
</div>
{% endif %}

{% if r.risk_flags %}
<div class="warn" style="background-color:#fee2e2; border:1px solid #ef4444; color:#991b1b; padding:8px 12px; margin-top:8px; font-weight:600; border-radius:6px">
Possible scam / social-engineering pattern: {{ r.risk_flags|join(', ') }}. Agent coaching may not apply.
</div>
{% endif %}

{% if r.meta.source_set == "real" %}
<div class="warn" style="margin-top:8px"><b>Real call:</b> Real call from a third-party dataset. Not scored against ShopEase policies. Scoring is for pipeline robustness testing only; speaker roles may not match a ShopEase agent/customer setup.</div>
{% endif %}

{% if is_capped and r.scores.overall < r.scores.overall_before_cap %}
<div class="warn" style="background-color:#fee2e2; border:1px solid #ef4444; color:#991b1b; padding:8px 12px; margin-top:8px; font-weight:600; border-radius:6px">
<b>Score capped at {{ capped_overall_display }} because:</b> {{ cap_reasons_summary }}
<div style="font-weight:normal; margin-top:2px; color:#7f1d1d">Score before the critical-failure cap: {{ capped_before_display }}.</div>
</div>
{% elif r.scores.cap_reasons %}
<div class="warn"><b>Score capped / flagged:</b>
 <ul>{% for c in r.scores.cap_reasons %}<li>{{ c }}</li>{% endfor %}</ul>
 {% if r.scores.overall_before_cap != r.scores.overall %}Score before the critical-failure cap: {{ r.scores.overall_before_cap }}.{% endif %}
</div>
{% endif %}

<h2>Summary</h2>
<p>{{ r.summary }}</p>
<p class="muted">Customer issue: <b>{{ r.customer_issue }}</b> &middot; Resolved: <b>{{ 'yes' if r.resolved else 'no' }}</b> &middot;
 Customer emotion: {{ r.emotion.start }} to {{ r.emotion.end }} ({{ r.emotion.trend }})</p>

<h2>Scores</h2>
{% if r.status == "failed" %}
<div class="warn" style="background-color:#fee2e2; border:1px solid #ef4444; color:#991b1b; padding:10px 14px; font-weight:600; border-radius:6px">
Audit failed: {{ failed_reason }}; no score
</div>
{% else %}
{% if r.status == "degraded" %}
<div class="warn" style="background-color:#fef3c7; border:1px solid #f59e0b; color:#92400e; padding:6px 10px; margin-bottom:8px; font-size:10pt">
degraded input quality ({{ degraded_reason }})
</div>
{% endif %}
<table>
 <tr><th>Category</th><th style="width:12%">Score</th><th style="width:48%">&nbsp;</th></tr>
 {% for name, val, mx in bars %}
 <tr><td>{{ name }}</td><td>{{ val }} / {{ mx }} ({{ (100*val/mx)|round|int if mx else 0 }}%)</td>
  <td><table style="border:none;width:100%"><tr>
    <td style="border:none;padding:0;background-color:#7c3aed;width:{{ (100*val/mx)|round|int if mx else 0 }}%;height:9px">&nbsp;</td>
    <td style="border:none;padding:0;background-color:#ede9fe;height:9px">&nbsp;</td></tr></table></td></tr>
 {% endfor %}
</table>
<div class="muted">SOP points {{ r.scores.sop_points_earned }} / {{ r.scores.sop_points_possible }} &middot; {% if not r.scores.policy_applicable %}policy category excluded{% if r.scores.policy_penalty_total %}; general-clause penalties applied: -{{ r.scores.policy_penalty_total|round|int }}{% endif %}{% else %}policy penalties {{ r.scores.policy_penalty_total }}{% endif %}{% if r.scores.timing_notes %} &middot; communication adjusted: {{ r.scores.timing_notes|join('; ') }}{% endif %}</div>
{% endif %}

<h2>What to work on (coaching)</h2>
{% if r.coaching %}
 {% for c in r.coaching %}
 <div class="box" style="margin-bottom:5px"><b>{{ loop.index }}. {{ c.title }}</b><br>{{ c.advice }}
  {% if c.evidence %}<br><span class="muted">Evidence: {{ c.evidence }}</span>{% endif %}</div>
 {% endfor %}
{% else %}<p>No coaching points. Nice work.</p>{% endif %}

{% if not r.risk_flags %}
<h2>Strengths</h2>
{% if r.strengths %}<ul>{% for s in r.strengths %}<li>{{ s }}</li>{% endfor %}</ul>{% else %}<p class="muted">None recorded.</p>{% endif %}
{% endif %}

<h2>SOP checklist</h2>
<table>
 <tr><th style="width:9%">Step</th><th>Requirement</th><th style="width:10%">Status</th><th style="width:7%">Turn</th><th style="width:34%">Evidence</th></tr>
 {% for s in sop %}
 <tr>
  <td><b>{{ s.step_id }}</b>{% if s.critical %}<br><span style="color:#c0262d;font-size:7.5pt">CRITICAL</span>{% endif %}</td>
  <td>{{ s.title }}<br><span class="muted">weight {{ s.weight }}{% if s.missing %} &middot; <b>missing: {{ s.missing }}</b>{% endif %}{% if s.reason %} &middot; {{ s.reason }}{% endif %}</span></td>
  <td><span class="badge" style="color:{{ status_color[s.status] }}">{{ status_label[s.status] }}</span></td>
  <td>{{ s.turn if s.turn else '-' }}</td>
  <td>{% if s.quote and s.status in ('followed','partial') %}<span class="quote">&ldquo;{{ s.quote }}&rdquo;</span>{% if not s.evidence_verified %}<br><span style="color:#c0262d;font-size:8pt">not verified in transcript</span>{% endif %}{% else %}<span class="muted">-</span>{% endif %}</td>
 </tr>
 {% endfor %}
</table>

<h2>Policy compliance</h2>
{% if violations %}
<table>
 <tr><th style="width:17%">Clause</th><th style="width:10%">Severity</th><th style="width:8%">Turn</th><th>What was said vs what the policy says</th></tr>
 {% for p in violations %}
 <tr><td><b>{{ p.clause_id }}</b><br><span class="muted">{{ p.policy_title.split(':')[0] }}</span></td>
  <td><span class="badge" style="color:{{ sev_color[p.severity] }}">{{ p.severity|upper }}</span><br><span class="muted">-{{ p.penalty|round|int }} pts</span></td>
  <td>{{ p.turn if p.turn else '-' }}{% if p.repeat_turns %}<br><span class="muted">repeated at {{ p.repeat_turns|join(', ') }}</span>{% endif %}</td>
  <td><span class="quote">&ldquo;{{ p.quote }}&rdquo;</span><br>{{ p.explanation }}
   {% if p.policy_text %}<br><span class="muted">Policy: {{ p.policy_text }}</span>{% endif %}</td></tr>
 {% endfor %}
</table>
{% else %}<p>No policy violations found.</p>{% endif %}
{% if compliant %}<p class="muted">Statements checked and found correct: {% for p in compliant %}{{ p.clause_id }}{% if not loop.last %}, {% endif %}{% endfor %}.</p>{% endif %}

{% if involved_policies %}
<h3>Policies &amp; SOPs involved</h3>
<table>
 <tr><th style="width:14%">Clause</th><th style="width:16%">Status</th><th style="width:26%">Title</th><th>Detail</th></tr>
 {% for ip in involved_policies %}
 <tr><td><b>{{ ip.id }}</b></td>
  <td><span class="badge" style="color:{{ ip.color }}">{{ ip.status }}</span></td>
  <td>{{ ip.title }}</td>
  <td>{{ ip.text }}</td></tr>
 {% endfor %}
</table>
{% endif %}

<h2>Conversation gaps</h2>
{% if r.gaps %}
<table><tr><th style="width:18%">Type</th><th style="width:8%">Turn</th><th>Detail</th></tr>
 {% for g in r.gaps %}<tr><td>{{ g.gap_type.replace('_',' ') }}</td><td>{{ g.turn if g.turn else '-' }}</td>
  <td>{{ g.detail }}{% if g.quote %}<br><span class="quote">&ldquo;{{ g.quote }}&rdquo;</span>{% endif %}</td></tr>{% endfor %}
</table>
{% else %}<p>No gaps detected.</p>{% endif %}

<h2>Emotion and call metrics</h2>
{% if chart %}<img src="data:image/png;base64,{{ chart }}" style="width:100%">{% endif %}
<table>
 <tr><th>Duration</th><th>Agent talk share</th><th>Longest silence</th><th>Agent speech rate</th><th>Turns (agent / customer)</th></tr>
 <tr><td>{{ (r.metrics.duration_sec/60)|round(1) }} min</td><td>{{ (r.metrics.agent_talk_ratio*100)|round|int }}%</td>
  <td>{{ r.metrics.longest_silence_sec }} s</td><td>{{ r.metrics.agent_words_per_minute|int }} wpm</td>
  <td>{{ r.metrics.agent_turns }} / {{ r.metrics.customer_turns }}</td></tr>
</table>

<h2>Transcript</h2>
<table>
 {% for t in r.transcript.turns %}
 <tr><td style="width:6%">{{ t.turn_id }}</td>
  <td style="width:11%"><b>{{ t.speaker|capitalize }}</b>{% if t.emotion %}<br><span class="muted">{{ t.emotion }}</span>{% endif %}</td>
  <td>{{ t.text }}{% if t.silence_before >= 2 %}<br><span class="muted">[{{ t.silence_before|round|int }}s silence before this turn]</span>{% endif %}</td></tr>
 {% endfor %}
</table>

{% if r.meta.warnings %}
<h2>Notes about this audit</h2>
<ul>{% for w in r.meta.warnings %}<li class="muted">{{ w }}</li>{% endfor %}</ul>
{% endif %}
<p class="muted">Model: {{ r.meta.model }} &middot; speaker separation: {{ r.meta.diarization_method }} &middot; LLM requests: {{ r.meta.llm_requests }}{% if r.meta.cache_hit %} (loaded from cache){% endif %}.
 Findings are generated by an AI auditor against ShopEase's policies and SOPs; every finding cites the transcript turn it is based on.</p>
</body></html>"""


def emotion_chart_base64(report: AuditReport) -> Optional[str]:
    pts = report.emotion.points
    if len(pts) < 2:
        return None
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:  # noqa: BLE001
        return None
    fig, ax = plt.subplots(figsize=(7.2, 2.3), dpi=130)
    xs, ys = [p.turn for p in pts], [p.valence for p in pts]
    ax.plot(xs, ys, color="#7c3aed", marker="o", linewidth=2)
    ax.axhline(0, color="#9ca3af", linewidth=0.8)
    ax.set_yticks([-2, -1, 0, 1, 1.5])
    ax.set_yticklabels(["angry", "upset", "neutral", "satisfied", "happy"], fontsize=7)
    ax.set_xlabel("Turn number", fontsize=8)
    ax.set_title("Customer emotion across the call", fontsize=9)
    ax.tick_params(axis="x", labelsize=7)
    ax.set_ylim(-2.3, 1.8)
    for p in pts:
        ax.annotate(p.emotion, (p.turn, p.valence), textcoords="offset points", xytext=(0, 6), ha="center", fontsize=6, color="#4b5563")
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def _clean_display_policy_text(text: str) -> str:
    """Strip metadata lines if present in user-facing policy text."""
    if not text:
        return ""
    lines = text.split("\n")
    cleaned = [
        line for line in lines
        if not re.match(r"^\s*-\s*(?:\*\*)?(?:Topics|Situations|Numeric Limit|Default Severity|Kind):", line)
    ]
    t = " ".join(cleaned)
    t = re.sub(r"-\s*(?:Topics|Situations|Numeric Limit|Default Severity|Kind):[^\d\n]+(?=\d+\.|\Z)", "", t)
    return re.sub(r"\s+", " ", t).strip()


def render_pdf_html(report: AuditReport) -> str:
    env = Environment(autoescape=select_autoescape(default=True, default_for_string=True))
    sc = report.scores
    bars = [
        ("SOP adherence", sc.sop_score, 40), ("Policy compliance", sc.policy_score, 30),
        ("Empathy", sc.empathy_score, 15), ("Communication", sc.communication_score, 15),
    ]
    sop = sorted(report.sop_results, key=lambda s: (s.status == "not_applicable", s.step_id))
    from .policy_check import get_involved_clause_ids
    from .rag import get_kb

    kb = get_kb()
    clause_ids, _ = get_involved_clause_ids(report, kb)
    res_map = {p.clause_id: p for p in report.policy_results}
    status_colors = {"Violated": "#c0262d", "Followed": "#1a7f37", "No issue found": "#1a7f37", "Not assessed": "#6b7280"}
    involved = []
    for cid in clause_ids:
        chunk = kb.by_id.get(cid)
        p = res_map.get(cid)
        if p and p.verdict == "violation":
            st, rank = "Violated", 0
            txt = f"Violated: {p.quote} ({p.explanation})"
        elif p and p.verdict == "compliant":
            st, rank = "Followed", 1
            txt = chunk.body(180) if chunk else ""
        elif p and p.verdict == "unverifiable":
            st, rank = "Not assessed", 3
            txt = chunk.body(180) if chunk else ""
        else:
            st, rank = "No issue found", 2
            txt = chunk.body(180) if chunk else ""
        title = chunk.title if chunk else (p.policy_title if p else "")
        involved.append({
            "id": cid, "status": st, "title": title, "text": txt,
            "color": status_colors.get(st, "#6b7280"), "rank": rank,
        })
    involved.sort(key=lambda x: (x["rank"], x["id"]))

    failed_reason = extract_failure_reason(report) if getattr(report, "status", "ok") == "failed" else ""
    degraded_reason = extract_degraded_reason(report) if getattr(report, "status", "ok") == "degraded" else ""
    is_capped = (bool(sc.cap_reasons) and sc.overall < sc.overall_before_cap) or getattr(sc, "critical_failure", False)
    meaningful = [r for r in sc.cap_reasons if not r.startswith("No topic-specific") and not r.startswith("No applicable SOP")]
    cap_reasons_summary = "; ".join(meaningful) if meaningful else "; ".join(sc.cap_reasons)
    if not cap_reasons_summary:
        cap_reasons_summary = "critical rule violation"

    from .ui_html import display_grade_label
    grade_label_display = display_grade_label(sc)
    capped_overall_display = f"{sc.overall:g}"
    capped_before_display = f"{sc.overall_before_cap:g}"

    return env.from_string(TEMPLATE).render(
        r=report, bars=bars, sop=sop, status_color=STATUS_COLOR, status_label=STATUS_LABEL, sev_color=SEV_COLOR,
        grade_color=GRADE_COLOR.get(sc.grade, "#111827"), chart=emotion_chart_base64(report),
        failed_reason=failed_reason, degraded_reason=degraded_reason,
        is_capped=is_capped, cap_reasons_summary=cap_reasons_summary, grade_label_display=grade_label_display, capped_overall_display=capped_overall_display, capped_before_display=capped_before_display,
        violations=[
            p.model_copy(update={"policy_text": _clean_display_policy_text(p.policy_text)})
            for p in report.policy_results if p.verdict == "violation"
        ],
        compliant=[p for p in report.policy_results if p.verdict == "compliant"],
        involved_policies=involved,
    )



def render_pdf(report: AuditReport) -> bytes:
    from xhtml2pdf import pisa

    html = render_pdf_html(report)
    out = io.BytesIO()
    status = pisa.CreatePDF(src=html, dest=out, encoding="utf-8")
    if status.err:
        raise RuntimeError("PDF rendering failed; the HTML report is still available.")
    return out.getvalue()


# ---------------------------------------------------------------------------------- modern standalone HTML report
def render_html(report: AuditReport, dark: bool = False) -> str:
    """One self-contained page (open it in any browser, or print it to PDF). Same components as the app."""
    from . import ui_html as U

    try:
        from theme import get_theme_vars
        theme_vars = get_theme_vars(dark)
    except Exception:
        try:
            from app.theme import get_theme_vars
            theme_vars = get_theme_vars(dark)
        except Exception:
            theme_vars = ""

    body = "".join([
        U.report_header(report),
        U.verdict_banner(report),
        U.score_cards(report),
        U.section_title("What happened"),
        U.summary_card(report),
        U.section_title("Observed Gaps (Factual)", "strictly observed factual breaches with timestamps"),
        U.findings_observed_section(report),
        U.section_title("Uncertain Interpretations", "subjective tone, empathy and non-committal closures"),
        U.findings_inferred_section(report),
        U.section_title("The call in numbers", "plain-language meaning under every number"),
        U.metrics_grid(report),
        U.section_title("Emotion timeline", "customer emotion and agent tone over time"),
        U.emotion_section(report),
        U.section_title("Coaching"),
        U.coaching_section(report),
        U.section_title("Call script (SOP)", "the steps the company expects on every call"),
        U.script_board(report),
        "<details style=\"margin-top:10px\"><summary style=\"cursor:pointer;font-weight:600;color:#2A55B8\">Show the same checklist as a table</summary><div style=\"margin-top:10px\">" + U.script_table(report) + "</div></details>",
        U.section_title("Company rules (policy)", "what the agent said compared with the policy"),
        U.policy_section(report),
        U.policies_and_sops_involved_section(report),
        U.section_title("Conversation gaps"),
        U.gaps_section(report),
        U.section_title("Transcript", "with emotion and tone for every turn"),
        U.transcript_section(report),
        U.section_title("How the score was worked out"),
        U.walkthrough_section(report),
        U.details_section(report),
    ])
    page_bg = "#121316" if dark else "#F5F4EE"
    page_css = (f"body{{margin:0;background:{page_bg}}}.aq-page{{max-width:1160px;margin:0 auto;padding:34px 28px 70px}}"
                "@media print{body{background:#fff}.aq-page{padding:0}.aq-card,.aq-step,.aq-pol,.aq-coach,.aq-tile,.aq-kpi{break-inside:avoid}}")
    return ("<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
            f"<title>Call audit {esc(report.call_id)}</title><style>{theme_vars}{page_css}{U.css()}</style></head><body class=\"{'dark' if dark else 'light'}\"><div class=\"aq aq-page\">{body}</div></body></html>")
