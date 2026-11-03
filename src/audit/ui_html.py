"""HTML fragments + CSS for the report. The Streamlit app and the downloadable HTML report render the SAME
fragments, so what you see on screen is what you download.

Rules for every fragment: returned as ONE line (no blank lines, so Markdown cannot break it), all dynamic text
passes through `esc()`, class names are prefixed `aq-`.
"""

from __future__ import annotations

import re
from typing import Iterable, List, Optional, Sequence

from . import explain as X
from .schemas import AuditReport, PolicyResult, SOPResult
from .viz import (BAD, EMOTION_COLOR, GOOD, GRADE_COLOR, INK, MUTED, TONE_COLOR, WARN, emotion_timeline_svg, esc, gauge_svg, mmss,
                  build_timeline_events)

FONT = 'Inter, "Segoe UI", system-ui, -apple-system, Roboto, Arial, sans-serif'

CSS = """
.aq{font-family:%(font)s;color:var(--aq-text,#111);line-height:1.45;-webkit-font-smoothing:antialiased}
.aq *{box-sizing:border-box}
.aq-card{background:var(--aq-card-bg,#fff);border:1px solid var(--aq-border,#E7E5DC);border-radius:20px;padding:20px 22px;margin:0 0 16px 0;color:var(--aq-text,#111)}
.aq-card.tint{background:var(--aq-card-tint,#EEEDE3);border-color:var(--aq-border-tint,#E2E0D3)}
.aq-card.flush{padding:0;overflow:hidden}
.aq-h{font-size:18px;font-weight:650;letter-spacing:-.01em;margin:0 0 4px 0;color:var(--aq-text,#111)}
.aq-sub{font-size:13.5px;color:var(--aq-text-muted,#6B6B66);margin:0 0 14px 0}
.aq-muted{color:var(--aq-text-muted,#6B6B66)}
.aq-tiny{font-size:12px;color:var(--aq-text-tiny,#8A897F)}
.aq-row{display:flex;gap:16px;flex-wrap:wrap;align-items:stretch}
.aq-grid{display:grid;gap:14px}
.aq-g2{grid-template-columns:repeat(auto-fit,minmax(320px,1fr))}
.aq-g3{grid-template-columns:repeat(auto-fit,minmax(240px,1fr))}
.aq-g4{grid-template-columns:repeat(4,minmax(0,1fr))}
@media (max-width:1180px){.aq-g4{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media (max-width:640px){.aq-g4,.aq-g3,.aq-g2{grid-template-columns:1fr}}
.aq-pill{display:inline-flex;align-items:center;gap:6px;padding:3px 11px;border-radius:999px;font-size:12px;font-weight:600;background:var(--aq-pill-bg,#EEEDE3);color:var(--aq-pill-text,#3C3C38);white-space:nowrap}
.aq-pill.good{background:var(--aq-pill-good-bg,#E3F3E9);color:var(--aq-pill-good-text,#16723D)}.aq-pill.ok{background:var(--aq-pill-ok-bg,#E8F3DD);color:var(--aq-pill-ok-text,#3C7A1E)}.aq-pill.warn{background:var(--aq-pill-warn-bg,#FBF0D6);color:var(--aq-pill-warn-text,#8F6209)}
.aq-pill.bad{background:var(--aq-pill-bad-bg,#FBE3E0);color:var(--aq-pill-bad-text,#B3342F)}.aq-pill.dark{background:var(--aq-text,#111);color:var(--aq-bg,#fff)}.aq-pill.info{background:var(--aq-pill-info-bg,#E4ECFB);color:var(--aq-pill-info-text,#2A55B8)}
.aq-banner-risk{margin-top:10px;padding:10px 14px;background:var(--aq-risk-bg,#fef2f2);border:1.5px solid var(--aq-risk-border,#ef4444);border-radius:10px;color:var(--aq-risk-text,#991b1b);font-size:13.5px;font-weight:600}
.aq-banner-real{margin-top:10px;padding:8px 12px;background:var(--aq-real-bg,#fff7ed);border:1px solid var(--aq-real-border,#fed7aa);border-radius:8px;color:var(--aq-real-text,#9a3412);font-size:12.5px;font-weight:500}
.aq-dot{display:inline-block;width:9px;height:9px;border-radius:50%%;background:#8A8A85}
.aq-dot.good{background:#1F8F4E}.aq-dot.watch,.aq-dot.warn{background:#C98A12}.aq-dot.bad{background:#D64545}.aq-dot.info{background:#B9B8AD}
/* verdict */
.aq-verdict{display:grid;grid-template-columns:minmax(250px,300px) 1fr;gap:26px;align-items:center}
.aq-verdict .gauge{text-align:center}
.aq-vhead{font-size:30px;font-weight:700;letter-spacing:-.02em;margin:0 0 4px 0;color:var(--aq-text,#111)}
.aq-vsub{font-size:15px;color:var(--aq-text-muted,#4A4A45);margin:0 0 14px 0}
.aq-reasons{list-style:none;padding:0;margin:0 0 14px 0;display:grid;gap:7px}
.aq-reasons li{display:flex;gap:10px;align-items:flex-start;font-size:14px;color:var(--aq-text,#111)}
.aq-reasons .aq-dot{margin-top:6px;flex:none}
.aq-next{background:var(--aq-next-bg,#F6F5EF);border:1px solid var(--aq-border,#E7E5DC);border-radius:14px;padding:11px 14px;font-size:13.5px;color:var(--aq-text,#111)}
.aq-next b{display:block;font-size:11px;letter-spacing:.08em;color:var(--aq-text-muted,#6B6B66);margin-bottom:2px}
.aq-gradebadge{display:inline-flex;align-items:center;justify-content:center;width:46px;height:46px;border-radius:50%%;color:#fff;font-size:22px;font-weight:700;margin-right:12px;vertical-align:middle}
/* score cards */
.aq-kpi{background:var(--aq-card-bg,#fff);border:1px solid var(--aq-border,#E7E5DC);border-radius:18px;padding:16px 18px;color:var(--aq-text,#111)}
.aq-kpi .t{font-size:13px;color:var(--aq-text-muted,#6B6B66);font-weight:600}
.aq-kpi .v{font-size:32px;font-weight:650;letter-spacing:-.02em;margin:2px 0 6px 0;color:var(--aq-text,#111)}
.aq-kpi .v small{font-size:15px;color:var(--aq-text-tiny,#8A897F);font-weight:500}
.aq-bar{height:8px;background:var(--aq-bar-track,#EEEDE3);border-radius:99px;overflow:hidden;margin:2px 0 10px 0}
.aq-bar>i{display:block;height:100%%;border-radius:99px;background:var(--aq-bar-fill,#111)}
.aq-kpi .p{font-size:12.5px;color:var(--aq-text-body,#55554F)}
.aq-kpi .tech{font-size:11px;color:var(--aq-text-tiny,#9A998F);margin-top:6px}
/* metric tiles */
.aq-tile{background:var(--aq-card-bg,#fff);border:1px solid var(--aq-border,#E7E5DC);border-radius:16px;padding:14px 16px;color:var(--aq-text,#111)}
.aq-tile .l{display:flex;align-items:center;gap:8px;font-size:12.5px;font-weight:600;color:var(--aq-text-body,#55554F)}
.aq-tile .v{font-size:26px;font-weight:650;letter-spacing:-.02em;margin:4px 0 2px 0;color:var(--aq-text,#111)}
.aq-tile .v small{font-size:12px;color:var(--aq-text-tiny,#8A897F);font-weight:500;margin-left:4px}
.aq-tile .h{font-size:12.5px;color:var(--aq-text-muted,#6B6B66)}
.aq-tile .r{font-size:11.5px;color:var(--aq-text-tiny,#9A998F);margin-top:4px}
/* section head */
.aq-sec{display:flex;align-items:baseline;justify-content:space-between;gap:12px;margin:26px 2px 10px 2px}
.aq-sec h2{font-size:21px !important;font-weight:700;letter-spacing:-.02em;margin:0;color:var(--aq-text,#111);padding:0}
.aq-sec span{font-size:13px;color:var(--aq-text-muted,#6B6B66)}
/* board */
.aq-board{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px;align-items:start}
@media (max-width:1100px){.aq-board{grid-template-columns:repeat(2,minmax(0,1fr))}}
.aq-colhead{display:flex;align-items:center;justify-content:space-between;font-size:15px;font-weight:650;margin:0 2px 10px 2px;color:var(--aq-text,#111)}
.aq-colhead .n{background:var(--aq-card-bg,#fff);border:1px solid var(--aq-border-tint,#E2E0D3);border-radius:10px;padding:1px 10px;font-size:13px;color:var(--aq-text-body,#55554F)}
.aq-step{background:var(--aq-card-bg,#fff);border:1px solid var(--aq-border,#E7E5DC);border-radius:16px;padding:13px 14px;margin:0 0 10px 0;color:var(--aq-text,#111)}
.aq-step.s-missed{border-left:4px solid #D64545}.aq-step.s-partial{border-left:4px solid #C98A12}.aq-step.s-followed{border-left:4px solid #1F8F4E}.aq-step.s-not_applicable{border-left:4px solid #C9C8BD;background:var(--aq-step-na-bg,#FBFBF8)}
.aq-step .top{display:flex;gap:6px;flex-wrap:wrap;align-items:center;margin-bottom:6px}
.aq-chip{font-size:11px;font-weight:700;letter-spacing:.03em;background:var(--aq-pill-bg,#F1F0E8);color:var(--aq-text-body,#55554F);border-radius:8px;padding:2px 8px}
.aq-chip.crit{background:var(--aq-pill-bad-bg,#FBE3E0);color:var(--aq-pill-bad-text,#B3342F)}
.aq-step .ti{font-size:14px;font-weight:600;line-height:1.3;color:var(--aq-text,#111)}
.aq-step .no{font-size:12.5px;color:var(--aq-text-muted,#6B6B66);margin-top:4px}
.aq-step .mi{font-size:12.5px;color:var(--aq-pill-bad-text,#B3342F);margin-top:5px;font-weight:600}
.aq-quote{font-size:12.5px;color:var(--aq-quote-text,#3C3C38);background:var(--aq-quote-bg,#F6F5EF);border-radius:10px;padding:7px 10px;margin-top:8px;font-style:italic}
.aq-step details,.aq-kpi details{margin-top:8px;font-size:12.5px;color:var(--aq-text-body,#55554F)}
.aq-step summary,.aq-kpi summary,.aq-walk summary{cursor:pointer;color:#2A55B8;font-weight:600;font-size:12.5px}
/* table */
.aq-table{width:100%%;border-collapse:collapse;font-size:13.5px}
.aq-table th{text-align:left;font-size:11.5px;letter-spacing:.05em;text-transform:uppercase;color:var(--aq-text-muted,#6B6B66);padding:10px 12px;border-bottom:1px solid var(--aq-border,#E7E5DC);background:var(--aq-table-th,#FBFBF8)}
.aq-table td{padding:11px 12px;border-bottom:1px solid var(--aq-table-border,#EFEEE6);vertical-align:top;color:var(--aq-text,#111)}
.aq-table tr:last-child td{border-bottom:none}
/* policy */
.aq-pol{background:var(--aq-card-bg,#fff);border:1px solid var(--aq-border,#E7E5DC);border-radius:18px;padding:16px 18px;margin:0 0 12px 0;color:var(--aq-text,#111)}
.aq-pol.bad{border-left:5px solid #D64545}.aq-pol.warn{border-left:5px solid #C98A12}
.aq-pol .head{display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin-bottom:8px}
.aq-pol .say{font-size:14px;margin:6px 0;color:var(--aq-text,#111)}
.aq-pol .rule{font-size:13px;color:var(--aq-text-body,#55554F);background:var(--aq-quote-bg,#F6F5EF);border-radius:12px;padding:9px 12px;margin-top:8px}
/* coaching */
.aq-coach{display:flex;gap:14px;background:var(--aq-card-bg,#fff);border:1px solid var(--aq-border,#E7E5DC);border-radius:18px;padding:15px 18px;margin:0 0 10px 0;color:var(--aq-text,#111)}
.aq-coach .num{flex:none;width:30px;height:30px;border-radius:50%%;background:var(--aq-text,#111);color:var(--aq-bg,#fff);font-weight:700;font-size:14px;display:flex;align-items:center;justify-content:center}
.aq-coach .tt{font-weight:650;font-size:14.5px;margin-bottom:3px;color:var(--aq-text,#111)}
.aq-coach .ad{font-size:13.5px;color:var(--aq-text-body,#3C3C38)}
.aq-coach .ev{font-size:12.5px;color:var(--aq-text-muted,#6B6B66);margin-top:5px}
.aq-str{display:flex;gap:10px;align-items:flex-start;padding:8px 0;border-bottom:1px solid var(--aq-border-subtle,#F0EFE7);font-size:14px;color:var(--aq-text,#111)}
.aq-str:last-child{border-bottom:none}
.aq-str .tick{flex:none;width:20px;height:20px;border-radius:50%%;background:#E3F3E9;color:#16723D;font-weight:800;font-size:12px;display:flex;align-items:center;justify-content:center;margin-top:1px}
/* transcript */
.aq-turn{display:flex;flex-direction:column;margin:0 0 12px 0;max-width:78%%}
.aq-turn.agent{align-items:flex-start}.aq-turn.customer{align-items:flex-end;margin-left:auto}
.aq-turn .meta{font-size:11.5px;color:var(--aq-text-tiny,#8A897F);margin:0 6px 4px 6px;display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.aq-turn .bub{padding:11px 15px;border-radius:18px;font-size:14px;border:1px solid var(--aq-border,#E7E5DC);background:var(--aq-card-bg,#fff);color:var(--aq-text,#111)}
.aq-turn.customer .bub{background:var(--aq-cust-bubble-bg,var(--aq-text,#111));color:var(--aq-cust-bubble-text,var(--aq-bg,#fff));border-color:var(--aq-cust-bubble-bg,var(--aq-text,#111))}
.aq-turn.flag .bub{box-shadow:0 0 0 2px #D6454555}
.aq-emo{font-size:11px;font-weight:700;border-radius:99px;padding:1px 9px;color:#fff}
.aq-sys{align-self:center;text-align:center;font-size:12px;color:var(--aq-text-tiny,#8A897F);margin:2px 0 12px 0;background:var(--aq-card-tint,#EEEDE3);border-radius:99px;padding:3px 12px}
/* walkthrough */
.aq-walk{display:grid;grid-template-columns:150px 110px 1fr;gap:6px 16px;padding:12px 0;border-bottom:1px solid var(--aq-table-border,#EFEEE6);align-items:start}
.aq-walk:last-child{border-bottom:none}
.aq-walk .t{font-weight:650;color:var(--aq-text,#111)}.aq-walk .pt{font-weight:700;font-variant-numeric:tabular-nums;color:var(--aq-text,#111)}
.aq-walk .f{font-size:13px;font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;color:var(--aq-text-body,#2C2C28)}
.aq-walk .pl{grid-column:3;font-size:13px;color:var(--aq-text-muted,#6B6B66)}
.aq-kv{display:grid;grid-template-columns:200px 1fr;gap:8px 16px;font-size:13.5px}
.aq-kv div:nth-child(odd){color:var(--aq-text-muted,#6B6B66)}
.aq-kv div:nth-child(even){color:var(--aq-text,#111)}
.aq-hdr{display:flex;justify-content:space-between;gap:16px;flex-wrap:wrap;align-items:flex-end;margin:0 0 18px 0}
.aq-hdr h1{font-size:34px !important;letter-spacing:-.03em;margin:4px 0 8px 0;font-weight:750;color:var(--aq-text,#111);padding:0}
.aq-evt{display:flex;gap:10px;align-items:center;padding:8px 0;border-bottom:1px solid var(--aq-border-subtle,#F0EFE7);font-size:13.5px}
.aq-evt:last-child{border-bottom:none}
.aq-timeline text{font-family:%(font)s}
.aq-dot:hover circle,.aq-dot:hover rect{stroke-width:4}
.aq-empty{text-align:center;color:var(--aq-text-tiny,#8A897F);padding:28px 10px;font-size:14px}
""" % {"font": FONT}



def css() -> str:
    return CSS + DASH_CSS


def _one(s: str) -> str:
    return "".join(line.strip() for line in s.splitlines())


def _pill(text: str, tone: str = "") -> str:
    return f'<span class="aq-pill {tone}">{esc(text)}</span>'


def _emo_chip(emotion: Optional[str], speaker: str) -> str:
    if not emotion:
        return ""
    col = (EMOTION_COLOR if speaker == "customer" else TONE_COLOR).get(emotion, MUTED)
    return f'<span class="aq-emo" style="background:{col}">{esc(emotion)}</span>'


# ---------------------------------------------------------------------------------- header + verdict
def report_header(rep: AuditReport, subtitle: str = "Call audit") -> str:
    m = rep.metrics
    pills = [_pill(X.topic_label(rep.topic), "dark"), _pill(f"{m.duration_sec / 60:.1f} min"), _pill(f"{m.agent_turns + m.customer_turns} turns")]
    if rep.meta.diarization_method:
        pills.append(_pill("Speakers: " + ("by channel" if rep.meta.diarization_method.startswith("stereo") else "by AI" if "llm" in rep.meta.diarization_method else "from the script" if rep.meta.diarization_method == "given" else "estimated"), ""))
    pills += [_pill(s.replace("_", " "), "info") for s in rep.signals[:4]]
    real_note = ""
    if rep.meta.source_set == "real":
        real_note = ('<div class="aq-banner-real">'
                     'Real call from a third-party dataset. Not scored against ShopEase policies. '
                     'Scoring is for pipeline robustness testing only; speaker roles may not match a ShopEase agent/customer setup.</div>')
    risk_banner = ""
    if getattr(rep, "risk_flags", None):
        flags_text = esc(", ".join(rep.risk_flags))
        risk_banner = (f'<div class="aq-banner-risk">'
                       f'Possible scam / social-engineering pattern: {flags_text}. Agent coaching may not apply.</div>')
    return _one(f'<div class="aq-hdr"><div><div class="aq-tiny" style="letter-spacing:.1em;font-weight:700">{esc(subtitle.upper())}</div><h1>{esc(rep.call_id)}</h1><div style="display:flex;gap:8px;flex-wrap:wrap">{"".join(pills)}</div>{risk_banner}{real_note}</div>'
                f'<div class="aq-tiny" style="text-align:right">Generated {esc(rep.generated_at.replace("T", " "))}<br>{esc(rep.meta.model)} · {rep.meta.llm_requests} AI request(s){" · saved result" if rep.meta.cache_hit else ""}</div></div>')


def verdict_banner(rep: AuditReport) -> str:
    if getattr(rep, "risk_flags", None):
        return _one(
            f'<div class="aq-card"><div class="aq-verdict" style="grid-template-columns:1fr">'
            f'<div><div class="aq-vhead" style="color:var(--aq-risk-text, #991b1b)">Not scored</div>'
            f'<div class="aq-vsub">Possible scam / social-engineering pattern detected. Numeric score is stored in the JSON for testing only and is not displayed here.</div>'
            f'<ul class="aq-reasons">'
            + "".join(f'<li><span class="aq-dot bad"></span><span>{esc(f)}</span></li>' for f in rep.risk_flags)
            + f'</ul><div class="aq-next"><b>NOTE</b>Agent coaching tabs are visible but scores should not be used for performance review.</div></div></div></div>')
    v = X.verdict(rep)
    sc = rep.scores
    tone_pill = {"good": "good", "ok": "ok", "warn": "warn", "bad": "bad"}[v["tone"]]
    reasons = "".join(f'<li><span class="aq-dot {t}"></span><span>{esc(x)}</span></li>' for t, x in v["reasons"])
    cap = f'<div class="aq-tiny" style="margin-top:6px">Score before the critical-failure cap: {sc.overall_before_cap:g}</div>' if v["capped"] else ""
    return _one(
        f'<div class="aq-card"><div class="aq-verdict"><div class="gauge">{gauge_svg(sc.overall, sc.grade, width=280)}'
        f'<div style="margin-top:2px"><span class="aq-pill {tone_pill}">Grade {esc(sc.grade)} · {esc(sc.grade_label)}</span></div>{cap}</div>'
        f'<div><div class="aq-vhead">{esc(v["headline"])}</div><div class="aq-vsub">{esc(v["sub"])}</div>'
        f'<ul class="aq-reasons">{reasons}</ul>'
        f'<div class="aq-next"><b>BEST NEXT STEP FOR THE AGENT</b>{esc(v["next_step"])}</div></div></div></div>')


def score_cards(rep: AuditReport) -> str:
    sc = rep.scores
    vals = {"sop_score": sc.sop_score, "policy_score": sc.policy_score, "empathy_score": sc.empathy_score, "communication_score": sc.communication_score}
    walk = {w["title"]: w for w in X.score_walkthrough(rep)}
    cards = []
    for key, title, mx, tech, short, what in X.CATEGORIES:
        val = vals[key]
        pct = 0 if not mx else max(0, min(100, val / mx * 100))
        col = GOOD if pct >= 85 else (WARN if pct >= 60 else BAD)
        w = walk.get(title)
        calc = f'<details><summary>How was this worked out?</summary><div style="margin-top:6px">{esc(w["formula"])}<br><span class="aq-muted">{esc(w["plain"])}</span></div></details>' if w else ""
        cards.append(f'<div class="aq-kpi"><div class="t">{esc(title)}</div><div class="v">{val:g}<small> / {mx}</small> <span class="aq-muted" style="font-size:14px;font-weight:normal">({pct:.0f}%)</span></div>'
                     f'<div class="aq-bar"><i style="width:{pct:.0f}%;background:{col}"></i></div><div class="p">{esc(short)}</div>{calc}<div class="tech">Technical name: {esc(tech)}</div></div>')
    return _one(f'<div class="aq-grid aq-g4">{"".join(cards)}</div>')


def summary_card(rep: AuditReport) -> str:
    cust, agent = X.emotion_summary(rep)
    return _one(f'<div class="aq-card"><div class="aq-sub" style="margin-bottom:10px">Customer issue: <b>{esc(rep.customer_issue)}</b> · Solved: <b>{"yes" if rep.resolved else "no"}</b></div>'
                f'<p style="margin:0 0 10px 0;font-size:15px">{esc(rep.summary)}</p><p class="aq-muted" style="margin:0;font-size:13.5px">{esc(cust)} {esc(agent)}</p></div>')


# ---------------------------------------------------------------------------------- metrics
def metrics_grid(rep: AuditReport) -> str:
    tiles = []
    for c in X.metric_cards(rep):
        rng = f'<div class="r">{esc(c["range"])}</div>' if c["range"] else ""
        tiles.append(f'<div class="aq-tile"><div class="l"><span class="aq-dot {c["state"]}"></span>{esc(c["label"])}</div>'
                     f'<div class="v">{esc(c["value"])}<small>{esc(c["unit"])}</small></div><div class="h">{esc(c["hint"])}</div>{rng}</div>')
    return _one(f'<div class="aq-grid aq-g4">{"".join(tiles)}</div>')


# ---------------------------------------------------------------------------------- emotion + events
def emotion_section(rep: AuditReport) -> str:
    cust, agent = X.emotion_summary(rep)
    events = build_timeline_events(rep)
    ev_rows = []
    for e in events:
        tone = {"violation": "bad", "hold_too_long": "bad", "dead_air": "warn", "interruption": "warn", "hold": "info"}[e["kind"]]
        ev_rows.append(f'<div class="aq-evt"><span class="aq-pill {tone}">{esc(mmss(e["start"]))}</span><span>{esc(e["label"])}</span><span class="aq-tiny">turn {e["turn"]}</span></div>')
    ev = "".join(ev_rows) or '<div class="aq-empty">Nothing unusual happened: no long silences, holds, interruptions or rule breaks.</div>'
    return _one(
        f'<div class="aq-card"><div class="aq-h">How the call felt, minute by minute</div>'
        f'<div class="aq-sub">Black line: the customer\'s emotion. Dashed line: how the agent came across. Shaded bands are holds or silences. Hover a dot for details.</div>'
        f'{emotion_timeline_svg(rep)}'
        f'<div class="aq-grid aq-g2" style="margin-top:14px"><div class="aq-tile"><div class="l">Customer</div><div class="h" style="margin-top:6px;font-size:14px;color:#111">{esc(cust)}</div></div>'
        f'<div class="aq-tile"><div class="l">Agent</div><div class="h" style="margin-top:6px;font-size:14px;color:#111">{esc(agent)}</div></div></div></div>'
        f'<div class="aq-card"><div class="aq-h">Moments that mattered</div><div class="aq-sub">Events placed on the timeline above.</div>{ev}</div>')


def gaps_section(rep: AuditReport) -> str:
    if not rep.gaps:
        return '<div class="aq-card"><div class="aq-empty">No conversation gaps were found.</div></div>'
    rows = []
    for g in rep.gaps:
        src = {"timing": "measured from the audio timing", "script": "follows from a missed script step"}.get(g.source, "spotted by the AI reviewer")
        q = f'<div class="aq-quote">“{esc(g.quote)}”</div>' if g.quote else ""
        rows.append(f'<tr><td><b>{esc(X.gap_title(g.gap_type))}</b><div class="aq-tiny">{esc(X.gap_help(g.gap_type))}</div></td><td>{esc(g.turn) if g.turn else "-"}</td>'
                    f'<td>{esc(g.detail)}{q}<div class="aq-tiny" style="margin-top:4px">{src}</div></td></tr>')
    return _one(f'<div class="aq-card flush"><table class="aq-table"><tr><th style="width:34%">What</th><th style="width:8%">Turn</th><th>Details</th></tr>{"".join(rows)}</table></div>')


# ---------------------------------------------------------------------------------- script (SOP)
def _step_card(r: SOPResult) -> str:
    crit = '<span class="aq-chip crit">CRITICAL</span>' if r.critical else ""
    note = f'<div class="no">{esc(r.reason)}</div>' if r.reason else ""
    miss = f'<div class="mi">Missing: {esc(r.missing)}</div>' if r.missing else ""
    quote = ""
    if r.quote and r.status in ("followed", "partial"):
        unv = ' <span class="aq-tiny" style="color:#B3342F">(not found in transcript)</span>' if not r.evidence_verified else ""
        quote = f'<div class="aq-quote">“{esc(r.quote)}”{unv}</div>'
    turn = f'<span class="aq-chip">turn {r.turn}</span>' if r.turn else ""
    req = f'<details><summary>What this step requires</summary><div style="margin-top:5px">{esc(r.what_good_looks_like)}</div></details>' if r.what_good_looks_like else ""
    return (f'<div class="aq-step s-{r.status}"><div class="top"><span class="aq-chip">{esc(r.step_id)}</span>{crit}{turn}<span class="aq-tiny">weight {r.weight}</span></div>'
            f'<div class="ti">{esc(r.title)}</div>{note}{miss}{quote}{req}</div>')


def script_board(rep: AuditReport) -> str:
    cols = X.step_columns(rep)
    heads = [("missed", "Missed", "bad"), ("partial", "Partly done", "warn"), ("followed", "Done", "good"), ("not_applicable", "Did not apply", "")]
    out = []
    for key, title, tone in heads:
        items = cols[key]
        body = "".join(_step_card(r) for r in items) or '<div class="aq-empty" style="padding:14px">Nothing here</div>'
        out.append(f'<div><div class="aq-colhead"><span>{esc(title)}</span><span class="n">{len(items)}</span></div>{body}</div>')
    return _one(f'<div class="aq-board">{"".join(out)}</div>')


def script_table(rep: AuditReport) -> str:
    rows = []
    tone = {"followed": "good", "partial": "warn", "missed": "bad", "not_applicable": ""}
    for r in sorted(rep.sop_results, key=lambda s: (s.status == "not_applicable", s.step_id)):
        q = f'<span class="aq-muted" style="font-style:italic">“{esc(r.quote)}”</span>' if r.quote and r.status in ("followed", "partial") else ""
        crit = ' <span class="aq-chip crit">CRITICAL</span>' if r.critical else ""
        rows.append(f'<tr><td><span class="aq-chip">{esc(r.step_id)}</span>{crit}</td>'
                    f'<td><b>{esc(r.title)}</b><div class="aq-tiny">{esc(r.reason)}{(" · missing: " + esc(r.missing)) if r.missing else ""}</div></td>'
                    f'<td>{_pill(X.STATUS_LABEL[r.status], tone[r.status])}</td><td>{r.points_earned:g} / {r.points_possible:g}</td><td>{esc(r.turn) if r.turn else "-"}</td><td>{q}</td></tr>')
    return _one(f'<div class="aq-card flush"><table class="aq-table"><tr><th>Step</th><th>What was expected</th><th>Result</th><th>Points</th><th>Turn</th><th>Evidence</th></tr>{"".join(rows)}</table></div>')


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


# ---------------------------------------------------------------------------------- policy
def policy_section(rep: AuditReport) -> str:
    viol = [p for p in rep.policy_results if p.verdict == "violation"]
    ok = [p for p in rep.policy_results if p.verdict == "compliant"]
    out = []
    if not viol:
        out.append('<div class="aq-card"><div class="aq-empty">The agent did not state anything that conflicts with company policy.</div></div>')
    for p in viol:
        tone = "bad" if p.severity == "critical" else "warn"
        rep_note = f' <span class="aq-tiny">· repeated at turn {", ".join(str(t) for t in p.repeat_turns)} (counted once)</span>' if p.repeat_turns else ""
        pol_txt = _clean_display_policy_text(p.policy_text)
        pol = f'<div class="rule"><b>What the policy says</b> ({esc(p.clause_id)}): {esc(pol_txt)}</div>' if pol_txt else ""
        out.append(f'<div class="aq-pol {tone}"><div class="head"><span class="aq-chip">{esc(p.clause_id)}</span>{_pill(X.SEVERITY_LABEL[p.severity], "bad" if p.severity == "critical" else "warn")}'
                   f'<span class="aq-pill">−{p.penalty:g} points</span><span class="aq-tiny">{esc(p.policy_title.split(":")[0])} · turn {esc(p.turn) if p.turn else "-"}{rep_note}</span></div>'
                   f'<div class="say"><b>The agent said:</b> <i>“{esc(p.quote)}”</i></div><div style="font-size:14px">{esc(p.explanation)}</div>{pol}'
                   f'<div class="aq-tiny" style="margin-top:8px">{esc(X.SEVERITY_HELP.get(p.severity, ""))}</div></div>')
    if ok:
        out.append(f'<div class="aq-card"><div class="aq-h">Checked and correct</div><div class="aq-sub">Statements the agent made that match policy.</div>'
                   + "".join(f'<div class="aq-str"><span class="tick">✓</span><span><b>{esc(p.clause_id)}</b> · {esc(p.claim)}</span></div>' for p in ok) + '</div>')
    return _one("".join(out))


def policies_and_sops_involved_section(rep: AuditReport, kb=None) -> str:
    """Grouped by policy family, cards with id/title/body, status chips (Violated/Followed/No issue found/Not assessed),
    side-by-side what was said vs policy for violations, SOP families and step IDs used, violated first."""
    from collections import OrderedDict
    from .policy_check import get_involved_clause_ids
    from .rag import get_kb, POLICY_PREFIX_NAMES

    kb = kb or get_kb()
    clause_ids, was_computed_now = get_involved_clause_ids(rep, kb)
    turn_map = {t.turn_id: t for t in rep.transcript.turns}
    res_map = {p.clause_id: p for p in rep.policy_results}

    clause_items = []
    for cid in clause_ids:
        chunk = kb.by_id.get(cid)
        p = res_map.get(cid)
        if p:
            if p.verdict == "violation":
                status = "Violated"
                chip_class = "bad"
                sort_rank = 0
            elif p.verdict == "compliant":
                status = "Followed"
                chip_class = "good"
                sort_rank = 1
            else:
                status = "Not assessed"
                chip_class = "info"
                sort_rank = 3
        else:
            status = "No issue found"
            chip_class = "good"
            sort_rank = 2

        family_code = cid.split("-")[0]
        family_name = POLICY_PREFIX_NAMES.get(family_code, family_code)
        title = chunk.title if chunk else (p.policy_title if p else "")
        body_text = chunk.body(400) if chunk else (_clean_display_policy_text(p.policy_text) if p else "")
        clause_items.append({
            "id": cid,
            "family": family_name,
            "family_code": family_code,
            "title": title,
            "body": body_text,
            "status": status,
            "chip_class": chip_class,
            "sort_rank": sort_rank,
            "p": p,
        })

    # Violated first
    clause_items.sort(key=lambda x: (x["sort_rank"], x["id"]))

    families = OrderedDict()
    for item in clause_items:
        fam = item["family"]
        if fam not in families:
            families[fam] = []
        families[fam].append(item)

    # SOP families and steps
    sop_fams = {}
    for s in rep.sop_results:
        f_name = s.sop or (s.step_id.split("-")[0] if "-" in s.step_id else "SOP")
        if f_name not in sop_fams:
            sop_fams[f_name] = []
        sop_fams[f_name].append(s.step_id)

    sop_chips = " · ".join(
        f"<b>{esc(fname)}:</b> {', '.join(f'<code>{esc(sid)}</code>' for sid in sids)}"
        for fname, sids in sop_fams.items()
    ) or "None assessed"
    sop_header = (
        f'<div class="aq-card" style="margin-bottom:14px">'
        f'<div class="aq-h">SOP Families & Steps Used</div>'
        f'<div class="aq-sub" style="margin-bottom:0">{sop_chips}</div>'
        f'</div>'
    )

    computed_badge = ' <span class="aq-pill info" style="font-size:11px">retrieved now</span>' if was_computed_now else ""
    no_topic_notice = ""
    if rep.topic == "general" or not any(it["family_code"] not in ("PRV", "ESC") for it in clause_items):
        no_topic_notice = (
            '<div class="aq-next" style="margin-bottom:14px">'
            '<b>NOTICE</b>No topic-specific policy was triggered for this call. '
            'General baseline policy clauses were checked: PRV-1.1, ESC-1.1, ESC-1.2.</div>'
        )

    fam_sections = []
    for fam_name, items in families.items():
        cards = []
        for it in items:
            p = it["p"]
            cid = it["id"]
            status_chip = f'<span class="aq-pill {it["chip_class"]}">{it["status"]}</span>'
            if it["status"] == "Violated" and p:
                t = turn_map.get(p.turn)
                time_lbl = f"turn {p.turn}" + (f" ({mmss(t.start_time)})" if t else "")
                side_by_side = (
                    f'<div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:10px;background:var(--aq-card-tint,#EEEDE3);padding:10px 12px;border-radius:12px;">'
                    f'<div><b style="font-size:12px;color:var(--aq-text,#111)">What was said ({esc(time_lbl)}):</b>'
                    f'<div style="font-style:italic;margin-top:4px;color:var(--aq-text-body,#3C3C38)">“{esc(p.quote)}”</div>'
                    f'<div class="aq-tiny" style="margin-top:4px">{esc(p.explanation)}</div></div>'
                    f'<div><b style="font-size:12px;color:var(--aq-text,#111)">What the policy says:</b>'
                    f'<div style="margin-top:4px;color:var(--aq-text-body,#3C3C38);font-size:12.5px">{esc(it["body"])}</div></div>'
                    f'</div>'
                )
                cards.append(
                    f'<div class="aq-pol bad" style="margin-bottom:10px">'
                    f'<div class="head"><span class="aq-chip">{esc(cid)}</span><b>{esc(it["title"])}</b>{status_chip}</div>'
                    f'{side_by_side}'
                    f'</div>'
                )
            else:
                cards.append(
                    f'<div class="aq-pol" style="margin-bottom:10px">'
                    f'<div class="head"><span class="aq-chip">{esc(cid)}</span><b>{esc(it["title"])}</b>{status_chip}</div>'
                    f'<div style="font-size:12.5px;color:var(--aq-text-body,#55554F)">{esc(it["body"])}</div>'
                    f'</div>'
                )

        fam_sections.append(
            f'<div style="margin-bottom:16px"><div class="aq-colhead" style="font-size:16px">'
            f'<span>{esc(fam_name)}</span><span class="n">{len(items)} clause(s)</span></div>'
            f'{"".join(cards)}</div>'
        )

    return _one(
        f'<div><div class="aq-sec" style="margin-top:18px"><h2>Policies & SOPs involved{computed_badge}</h2>'
        f'<span>authoritative clauses checked for this call</span></div>'
        f'{no_topic_notice}{sop_header}{"".join(fam_sections)}</div>'
    )



# ---------------------------------------------------------------------------------- coaching
def coaching_section(rep: AuditReport) -> str:
    left = []
    if not rep.coaching:
        left.append('<div class="aq-card"><div class="aq-empty">No coaching points. Nice work!</div></div>')
    for i, c in enumerate(rep.coaching, 1):
        ev = f'<div class="ev">Why: {esc(c.evidence)}</div>' if c.evidence else ""
        left.append(f'<div class="aq-coach"><div class="num">{i}</div><div><div class="tt">{esc(c.title)}</div><div class="ad">{esc(c.advice)}</div>{ev}</div></div>')
    strengths = "".join(f'<div class="aq-str"><span class="tick">✓</span><span>{esc(s)}</span></div>' for s in rep.strengths) or '<div class="aq-empty">None recorded.</div>'
    if getattr(rep, "risk_flags", None):
        return _one(f'<div><div class="aq-sec" style="margin-top:0"><h2>What to work on</h2></div>{"".join(left)}</div>')
    return _one(f'<div class="aq-grid" style="grid-template-columns:minmax(0,1.5fr) minmax(0,1fr);gap:18px;align-items:start"><div><div class="aq-sec" style="margin-top:0"><h2>What to work on</h2></div>{"".join(left)}</div>'
                f'<div><div class="aq-sec" style="margin-top:0"><h2>What went well</h2></div><div class="aq-card">{strengths}</div></div></div>')


# ---------------------------------------------------------------------------------- transcript
def transcript_section(rep: AuditReport) -> str:
    viol_turns = {p.turn for p in rep.policy_results if p.verdict == "violation" and p.turn}
    out = []
    holds_after = {h.end_turn for h in rep.metrics.holds}
    for t in rep.transcript.turns:
        if t.turn_id in holds_after:
            out.append(f'<div class="aq-sys">⏸ Customer on hold for {esc(mmss(t.silence_before))}</div>')
        elif t.silence_before >= 4:
            out.append(f'<div class="aq-sys">Silence for {t.silence_before:.0f}s</div>')
        flags = []
        if t.overlaps_previous:
            flags.append('<span class="aq-pill warn">talked over</span>')
        if t.turn_id in viol_turns:
            flags.append('<span class="aq-pill bad">rule broken</span>')
        who = "Agent" if t.speaker == "agent" else "Customer"
        out.append(f'<div class="aq-turn {t.speaker}{" flag" if t.turn_id in viol_turns else ""}"><div class="meta"><b>{who}</b> · #{t.turn_id} · {esc(mmss(t.start_time))} {_emo_chip(t.emotion, t.speaker)} {"".join(flags)}</div>'
                   f'<div class="bub">{esc(t.text)}</div></div>')
    return _one(f'<div class="aq-card" style="display:flex;flex-direction:column">{"".join(out)}</div>')


# ---------------------------------------------------------------------------------- how the score works / details
def walkthrough_section(rep: AuditReport) -> str:
    rows = []
    for w in X.score_walkthrough(rep):
        rows.append(f'<div class="aq-walk"><div class="t">{esc(w["title"])}</div><div class="pt">{w["points"]:g} / {w["max"]}</div><div class="f">{esc(w["formula"])}</div><div class="pl">{esc(w["plain"])}</div></div>')
    grade = "A 90+ · B 80 to 89 · C 70 to 79 · D below 70"
    return _one(f'<div class="aq-card"><div class="aq-h">How the score was worked out</div><div class="aq-sub">Every point is accounted for. The score is calculated by fixed rules in code, not guessed by the AI. Grades: {grade}.</div>{"".join(rows)}</div>')


def details_section(rep: AuditReport) -> str:
    m = rep.meta
    kv = [("Model used", m.model), ("Speaker separation", m.diarization_method), ("AI requests used", f"{m.llm_requests}" + (" (loaded from a saved audit)" if m.cache_hit else "")),
          ("Time to transcribe", f"{m.transcribe_seconds:g} s"), ("Time to audit", f"{m.audit_seconds:g} s"), ("Topic confidence", f"{rep.topic_confidence * 100:.0f}%"),
          ("Signals detected", ", ".join(rep.signals) or "none")]
    body = "".join(f'<div>{esc(k)}</div><div>{esc(v)}</div>' for k, v in kv)
    warn = "".join(f'<li>{esc(w)}</li>' for w in m.warnings)
    warn_html = f'<div class="aq-h" style="margin-top:18px">Notes from the audit</div><ul style="margin:6px 0 0 18px;font-size:13px;color:#55554F">{warn}</ul>' if warn else ""
    return _one(f'<div class="aq-card"><div class="aq-h">Technical details</div><div class="aq-sub">For the curious and for debugging.</div><div class="aq-kv">{body}</div>{warn_html}</div>')


def section_title(title: str, hint: str = "") -> str:
    return f'<div class="aq-sec"><h2>{esc(title)}</h2><span>{esc(hint)}</span></div>'


# ---------------------------------------------------------------------------------- dashboard + app chrome
DASH_CSS = """
.aq-hero{display:grid;grid-template-columns:minmax(0,1.5fr) minmax(250px,.9fr) minmax(190px,.6fr);gap:26px;align-items:center}
@media (max-width:1100px){.aq-hero{grid-template-columns:1fr}}
.aq-hero .ttl{font-size:15px;font-weight:650;margin-bottom:4px;color:var(--aq-text,#111)}
.aq-hero .cap{font-size:12.5px;color:var(--aq-text-muted,#6B6B66);text-align:center}
.aq-big{font-size:46px;font-weight:650;letter-spacing:-.03em;line-height:1;color:var(--aq-text,#111)}
.aq-bigcap{font-size:13px;color:var(--aq-text-muted,#6B6B66);margin:6px 0 18px 0}
.aq-legend{display:flex;gap:14px;flex-wrap:wrap;font-size:11.5px;color:var(--aq-text-muted,#6B6B66);margin-top:2px}
.aq-legend i{display:inline-block;width:12px;height:12px;border-radius:4px;margin-right:5px;vertical-align:-2px}
.aq-gh{display:flex;align-items:center;justify-content:space-between;margin:0 2px 10px 2px;font-size:15px;font-weight:650;color:var(--aq-text,#111)}
.aq-gh .n{background:var(--aq-card-bg,#fff);border:1px solid var(--aq-border-tint,#E2E0D3);border-radius:10px;padding:1px 10px;font-size:13px;color:var(--aq-text-body,#55554F)}
.aq-call{background:var(--aq-card-bg,#fff);border:1px solid var(--aq-border,#E7E5DC);border-radius:18px;padding:14px 16px;margin:0 0 6px 0;color:var(--aq-text,#111)}
.aq-call.crit{background:var(--aq-card-tint,#111);color:var(--aq-text,#fff);border-color:var(--aq-border,#111)}
.aq-call.ns{background:var(--aq-card-subtle,#F6F5EF);border-color:var(--aq-border-subtle,#EFEEE6);opacity:.88}
.aq-call .id{font-size:15px;font-weight:650;display:flex;justify-content:space-between;align-items:center}
.aq-call .sc{font-size:22px;font-weight:700}
.aq-call .is{font-size:12.5px;color:var(--aq-text-muted,#6B6B66);margin:6px 0 8px 0;min-height:34px}
.aq-call.crit .is{color:var(--aq-text-muted,#C9C8BD)}
.aq-call .fl{display:flex;gap:6px;flex-wrap:wrap}
.aq-ins{display:grid;grid-template-columns:1fr 70px;gap:4px 12px;align-items:center;font-size:13px;margin:7px 0}
.aq-ins .b{height:7px;background:var(--aq-bar-track,#EEEDE3);border-radius:99px;overflow:hidden;grid-column:1 / span 2}
.aq-ins .b i{display:block;height:100%;background:var(--aq-bar-fill,#111);border-radius:99px}
.aq-steps{display:flex;gap:10px;flex-wrap:wrap;margin:14px 0}
.aq-stp{display:flex;align-items:center;gap:9px;background:var(--aq-card-bg,#fff);border:1px solid var(--aq-border,#E7E5DC);border-radius:14px;padding:9px 14px;font-size:13.5px;font-weight:600;color:var(--aq-text-tiny,#8A897F)}
.aq-stp .c{width:22px;height:22px;border-radius:50%;background:var(--aq-pill-bg,#EEEDE3);color:var(--aq-text-tiny,#8A897F);font-size:12px;display:flex;align-items:center;justify-content:center}
.aq-stp.on{color:var(--aq-text,#111);border-color:var(--aq-text,#111)}.aq-stp.on .c{background:var(--aq-text,#111);color:var(--aq-bg,#fff)}
.aq-stp.done{color:#16723D}.aq-stp.done .c{background:#1F8F4E;color:#fff}
.aq-brand{display:flex;align-items:center;gap:10px;margin:2px 0 4px 2px}
.aq-logo{width:34px;height:34px;border-radius:11px;background:var(--aq-text,#111);display:flex;align-items:center;justify-content:center}
.aq-brand b{font-size:19px;letter-spacing:-.02em;color:var(--aq-text,#111)}
.aq-brand span{display:block;font-size:11.5px;color:var(--aq-text-tiny,#8A897F);margin-top:-2px;word-spacing:2px}
.aq-pagehead{display:flex;justify-content:space-between;align-items:flex-end;gap:16px;margin:0 0 6px 0}
.aq-pagehead h1{font-size:30px !important;letter-spacing:-.03em;margin:0;font-weight:750;color:var(--aq-text,#111);padding:0}
.aq-pagehead p{margin:4px 0 0 0;font-size:14px;color:var(--aq-text-muted,#6B6B66)}
.aq-cmp{display:grid;grid-template-columns:34px 1.2fr 1fr 1fr;gap:6px 14px;font-size:13px;padding:9px 0;border-bottom:1px solid var(--aq-table-border,#EFEEE6);align-items:start}
.aq-cmp.h{font-size:11.5px;letter-spacing:.05em;text-transform:uppercase;color:var(--aq-text-muted,#6B6B66);font-weight:700}
.aq-res{display:inline-flex;align-items:center;justify-content:center;width:24px;height:24px;border-radius:50%;font-size:13px;font-weight:800;color:#fff}
.aq-res.PASS{background:#1F8F4E}.aq-res.FAIL{background:#D64545}.aq-res.WARN{background:#C98A12}.aq-res.SKIP{background:#B9B8AD}
"""

LOGO = ('<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2.4" stroke-linecap="round">'
        '<path d="M4 12v0M8 8v8M12 4v16M16 9v6M20 12v0"/></svg>')


def brand() -> str:
    return _one(f'<div class="aq-brand"><div class="aq-logo">{LOGO}</div><div><b>AuditIQ</b><span>ShopEase · call quality</span></div></div>')


def page_header(title: str, subtitle: str = "") -> str:
    return _one(f'<div class="aq-pagehead"><div><h1>{esc(title)}</h1><p>{esc(subtitle)}</p></div></div>')


def empty_state(title: str, text: str) -> str:
    return _one(f'<div class="aq-card"><div class="aq-empty"><div style="font-size:17px;font-weight:650;color:var(--aq-text, #111);margin-bottom:6px">{esc(title)}</div>{esc(text)}</div></div>')


def progress_stepper(stage: str, skip_audio: bool = False) -> str:
    order = [("transcribe", "Listening to the call"), ("diarize", "Who said what"), ("topic", "Reading the call"), ("policy", "Checking the rules"), ("score", "Scoring")]
    alias = {"sop": "topic", "done": "end"}
    cur = alias.get(stage, stage)
    idx = next((i for i, (k, _) in enumerate(order) if k == cur), len(order) if cur == "end" else 0)
    out = []
    for i, (k, label) in enumerate(order):
        if skip_audio and k in ("transcribe", "diarize"):
            state, mark = "done", "✓"
        elif i < idx:
            state, mark = "done", "✓"
        elif i == idx:
            state, mark = "on", str(i + 1)
        else:
            state, mark = "", str(i + 1)
        out.append(f'<div class="aq-stp {state}"><span class="c">{mark}</span>{esc(label)}</div>')
    return _one(f'<div class="aq-steps">{"".join(out)}</div>')


def dash_hero(scored: Sequence[AuditReport], unscored: Sequence[AuditReport] = ()) -> str:
    from .viz import score_bars_svg

    scored_items = [(r.call_id.replace("call_", ""), r.scores.overall, r.scores.grade) for r in scored][-14:]
    ns_labels = [r.call_id for r in unscored]
    n = len(scored)
    avg = sum(r.scores.overall for r in scored) / n if n else 0
    grade = "A" if avg >= 90 else "B" if avg >= 80 else "C" if avg >= 70 else "D"
    crit = sum(1 for r in scored if r.scores.critical_failure)
    passing = sum(1 for r in scored if r.scores.overall >= 70)
    legend = ('<div class="aq-legend"><span><i style="background:var(--aq-bar-fill, #111)"></i>75 and above</span><span><i style="background:repeating-linear-gradient(45deg,#9B9A90,#9B9A90 2px,#EDEBE0 2px,#EDEBE0 5px)"></i>60 to 74</span>'
              '<span><i style="background:repeating-linear-gradient(45deg,#D64545,#D64545 2px,var(--aq-risk-bg, #FBE9E6) 2px,var(--aq-risk-bg, #FBE9E6) 5px)"></i>below 60</span>'
              '<span><i style="background:repeating-linear-gradient(45deg,var(--aq-text-tiny,#8A897F),var(--aq-text-tiny,#8A897F) 2px,var(--aq-card-tint,#EDEBE0) 2px,var(--aq-card-tint,#EDEBE0) 5px)"></i>not scored</span></div>')
    return _one(
        f'<div class="aq-card tint"><div class="aq-hero"><div><div class="ttl">Score by call</div>{score_bars_svg(scored_items, ns_labels)}{legend}</div>'
        f'<div style="text-align:center">{gauge_svg(avg, grade, width=270)}<div class="cap">Average across {n} audited call(s)</div></div>'
        f'<div><div class="aq-big">{n}</div><div class="aq-bigcap">calls audited</div>'
        f'<div class="aq-big" style="color:{BAD if crit else "var(--aq-text, #111)"}">{crit}</div>'
        f'<div class="aq-bigcap">critical failure(s)</div><div class="aq-big">{(passing / n * 100) if n else 0:.0f}%</div>'
        f'<div class="aq-bigcap" style="margin-bottom:0">scored 70 or more</div></div></div></div>')


def call_card(rep: AuditReport) -> str:
    sc = rep.scores
    crit = sc.critical_failure
    is_ns = bool(getattr(rep, "risk_flags", None))
    flags = []
    if is_ns:
        flags.append(_pill("Not scored", ""))  # neutral grey
    elif crit:
        flags.append(_pill("Critical failure", "bad"))
    viol = sum(1 for p in rep.policy_results if p.verdict == "violation")
    if viol and not is_ns:
        flags.append(_pill(f"{viol} rule(s) broken", "warn"))
    if rep.metrics.hold_events:
        flags.append(_pill("Long hold", "warn"))
    if not flags:
        flags.append(_pill("Clean", "good"))
    issue = rep.customer_issue or rep.summary
    sc_span = "" if is_ns else f'<span class="sc">{sc.overall:.0f}</span>'
    card_cls = "aq-call ns" if is_ns else ("aq-call crit" if crit else "aq-call")
    return _one(f'<div class="{card_cls}"><div class="id"><span>{esc(rep.call_id)}</span>{sc_span}</div>'
                f'<div class="is">{esc(X.topic_label(rep.topic))} · {esc(issue[:70])}</div><div class="fl">{"".join(flags)}</div></div>')


def insights_card(reports: Sequence[AuditReport]) -> str:
    miss: dict = {}
    titles: dict = {}
    viol: dict = {}
    for r in reports:
        for s in r.sop_results:
            if s.status in ("missed", "partial"):
                miss[s.step_id] = miss.get(s.step_id, 0) + 1
                titles[s.step_id] = s.title
        for p in r.policy_results:
            if p.verdict == "violation":
                viol[p.clause_id] = viol.get(p.clause_id, 0) + 1

    def rows(d, label):
        if not d:
            return '<div class="aq-empty" style="padding:10px">Nothing yet</div>'
        top = sorted(d.items(), key=lambda kv: -kv[1])[:5]
        mx = max(v for _, v in top)
        return "".join(f'<div class="aq-ins"><span>{esc(label(k))}</span><span style="text-align:right;font-weight:650">{v} call(s)</span><div class="b"><i style="width:{v / mx * 100:.0f}%"></i></div></div>' for k, v in top)

    return _one(f'<div class="aq-grid aq-g2"><div class="aq-card"><div class="aq-h">Most missed script steps</div><div class="aq-sub">Where agents most often slip</div>{rows(miss, lambda k: k + " · " + titles[k])}</div>'
                f'<div class="aq-card"><div class="aq-h">Most broken company rules</div><div class="aq-sub">Policy clauses agents most often get wrong</div>{rows(viol, lambda k: k)}</div></div>')



def findings_observed_section(report: AuditReport) -> str:
    """Visibly separate section for observed factual gaps with verbatim quotes, timestamps and reviewer status."""
    gaps = report.observed_gaps
    if not gaps:
        return _one('<div class="aq-card"><div class="aq-h">Observed Gaps (Factual Breaches)</div><div class="aq-sub">Factual, procedural findings strictly grounded in transcript evidence</div><div class="aq-muted">No factual breaches observed in this call.</div></div>')

    rows = []
    for f in gaps:
        ev_lines = []
        for e in f.evidence:
            ts = f"[{mmss(e.start_s)}-{mmss(e.end_s)}]" if (e.start_s or e.end_s) else f"[Turn {e.turn_id}]"
            ev_lines.append(f'<div style="margin:2px 0"><span class="aq-tiny" style="font-weight:600;color:#5b21b6">{ts} {esc(e.speaker.upper())}:</span> <span class="quote">&ldquo;{esc(e.quote)}&rdquo;</span></div>')
        ev_html = "".join(ev_lines) if ev_lines else '<span class="aq-muted">No quote cited</span>'

        rev_badge = f'<span class="aq-pill {"good" if f.reviewer_status=="accepted" else ("bad" if f.reviewer_status=="overturned" else "")}">{esc(f.reviewer_status.upper())}</span>'
        sev_cls = "bad" if f.severity in ("critical", "major") else "warn"
        cert_reason_html = f'<br><span class="aq-tiny">{esc(f.certainty_reason)}</span>' if f.certainty_reason else ""
        expl_html = f'<br><span class="aq-muted">{esc(f.explanation)}</span>' if f.explanation else ""
        note_html = f'<br><span class="aq-tiny">{esc(f.reviewer_note)}</span>' if f.reviewer_note else ""
        rows.append(
            f'<tr><td style="padding:8px;border-bottom:1px solid var(--aq-border,#E7E5DC)"><b>{esc(f.criterion_id)}</b><br><span class="aq-tiny">{esc(f.name)}</span></td>'
            f'<td style="padding:8px;border-bottom:1px solid var(--aq-border,#E7E5DC)"><span class="aq-pill {sev_cls}">{esc(f.severity.upper())}</span><br><span class="aq-tiny">{esc(f.verdict)}</span></td>'
            f'<td style="padding:8px;border-bottom:1px solid var(--aq-border,#E7E5DC)"><span class="aq-pill info">{esc(f.certainty.upper())}</span>{cert_reason_html}</td>'
            f'<td style="padding:8px;border-bottom:1px solid var(--aq-border,#E7E5DC)">{ev_html}{expl_html}</td>'
            f'<td style="padding:8px;border-bottom:1px solid var(--aq-border,#E7E5DC)">{rev_badge}{note_html}</td></tr>'
        )
    return _one(
        '<div class="aq-card">'
        '<div class="aq-h">Observed Gaps (Factual Breaches)</div>'
        '<div class="aq-sub">Factual, procedural findings strictly grounded in transcript evidence</div>'
        '<table class="aq-table" style="width:100%;border-collapse:collapse;font-size:13px">'
        '<thead><tr style="text-align:left;background:var(--aq-card-tint,#EEEDE3)"><th style="padding:8px;width:18%">Criterion</th><th style="padding:8px;width:14%">Severity / Verdict</th><th style="padding:8px;width:14%">Certainty</th><th style="padding:8px">Evidence &amp; Timestamps</th><th style="padding:8px;width:12%">Review</th></tr></thead>'
        f'<tbody>{"".join(rows)}</tbody></table></div>'
    )


def findings_inferred_section(report: AuditReport) -> str:
    """Visibly separate section for tonal and intent interpretations."""
    items = report.uncertain_interpretations
    if not items:
        return _one('<div class="aq-card"><div class="aq-h">Uncertain Interpretations (Tone, Empathy &amp; Intent)</div><div class="aq-sub">Interpretive assessments (always labeled as interpretations; never mixed with observed facts)</div><div class="aq-muted">No uncertain interpretations recorded.</div></div>')

    rows = []
    for f in items:
        ev_lines = []
        for e in f.evidence:
            ts = f"[{mmss(e.start_s)}-{mmss(e.end_s)}]" if (e.start_s or e.end_s) else f"[Turn {e.turn_id}]"
            ev_lines.append(f'<div style="margin:2px 0"><span class="aq-tiny" style="font-weight:600;color:#5b21b6">{ts} {esc(e.speaker.upper())}:</span> <span class="quote">&ldquo;{esc(e.quote)}&rdquo;</span></div>')
        ev_html = "".join(ev_lines) if ev_lines else '<span class="aq-muted">None cited</span>'

        rev_badge = f'<span class="aq-pill {"good" if f.reviewer_status=="accepted" else ("bad" if f.reviewer_status=="overturned" else "")}">{esc(f.reviewer_status.upper())}</span>'
        cert_reason_html = f'<br><span class="aq-tiny">{esc(f.certainty_reason)}</span>' if f.certainty_reason else ""
        expl_html = f'<br><span class="aq-muted">{esc(f.explanation)}</span>' if f.explanation else ""
        note_html = f'<br><span class="aq-tiny">{esc(f.reviewer_note)}</span>' if f.reviewer_note else ""
        rows.append(
            f'<tr><td style="padding:8px;border-bottom:1px solid var(--aq-border,#E7E5DC)"><b>{esc(f.criterion_id)}</b><br><span class="aq-tiny">{esc(f.name)}</span></td>'
            f'<td style="padding:8px;border-bottom:1px solid var(--aq-border,#E7E5DC)"><span class="aq-pill ok">{esc(f.verdict)}</span></td>'
            f'<td style="padding:8px;border-bottom:1px solid var(--aq-border,#E7E5DC)"><span class="aq-pill warn">{esc(f.certainty.upper())}</span>{cert_reason_html}</td>'
            f'<td style="padding:8px;border-bottom:1px solid var(--aq-border,#E7E5DC)">{ev_html}{expl_html}</td>'
            f'<td style="padding:8px;border-bottom:1px solid var(--aq-border,#E7E5DC)">{rev_badge}{note_html}</td></tr>'
        )
    return _one(
        '<div class="aq-card">'
        '<div class="aq-h">Uncertain Interpretations (Tone, Empathy &amp; Intent)</div>'
        '<div class="aq-sub">Interpretive assessments (always labeled as interpretations; never mixed with observed facts)</div>'
        '<table class="aq-table" style="width:100%;border-collapse:collapse;font-size:13px">'
        '<thead><tr style="text-align:left;background:var(--aq-card-tint,#EEEDE3)"><th style="padding:8px;width:18%">Criterion</th><th style="padding:8px;width:14%">Verdict</th><th style="padding:8px;width:14%">Certainty</th><th style="padding:8px">Evidence &amp; Interpretation</th><th style="padding:8px;width:12%">Review</th></tr></thead>'
        f'<tbody>{"".join(rows)}</tbody></table></div>'
    )
