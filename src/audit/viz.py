"""SVG charts shared by the Streamlit app and the standalone HTML report (pure Python, no JavaScript).

Design language: warm off-white canvas, white cards, near-black ink, ticked gauge, black bars,
soft status colours. Every chart has native SVG <title> tooltips.
"""

from __future__ import annotations

import math
from html import escape
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from .emotion import TONE_VALENCE, VALENCE
from .schemas import AuditReport

# ---------------------------------------------------------------------------------- palette
INK = "#111111"
MUTED = "#6B6B66"
FAINT = "#A3A299"
LINE = "#E7E5DC"
CANVAS = "#F5F4EE"
TINT = "#EEEDE3"
CARD = "#FFFFFF"
GOOD = "#1F8F4E"
WARN = "#C98A12"
BAD = "#D64545"
INFO = "#3B6FE0"

GRADE_COLOR = {"A": GOOD, "B": "#4C9A2A", "C": WARN, "D": BAD}

EMOTION_COLOR = {
    "angry": "#D64545", "frustrated": "#E8793A", "anxious": "#E2B03B", "confused": "#8E7CC3",
    "neutral": "#8A8A85", "satisfied": "#4DA36A", "happy": "#1F8F4E",
}
TONE_COLOR = {
    "empathetic": "#1F8F4E", "warm": "#4DA36A", "calm": "#3B6FE0", "neutral": "#8A8A85",
    "rushed": "#E2B03B", "defensive": "#E8793A", "dismissive": "#D64545",
}


def esc(text) -> str:
    """HTML-escape and neutralise characters that Markdown/LaTeX would treat specially when embedded in Streamlit."""
    return escape(str(text if text is not None else ""), quote=True).replace("$", "&#36;").replace("`", "&#96;")


def mmss(seconds: float) -> str:
    s = max(0, int(round(seconds)))
    return f"{s // 60:d}:{s % 60:02d}"


# ---------------------------------------------------------------------------------- gauge
def gauge_svg(score: float, grade: str, label: str = "Overall score", width: int = 280) -> str:
    n, cx, cy, r_out, r_in = 61, 140, 138, 118, 92
    color = GRADE_COLOR.get(grade, INK)
    filled = int(round(max(0.0, min(100.0, score)) / 100 * (n - 1)))
    ticks = []
    for i in range(n):
        ang = math.pi - i * math.pi / (n - 1)
        x1, y1 = cx + r_in * math.cos(ang), cy - r_in * math.sin(ang)
        x2, y2 = cx + r_out * math.cos(ang), cy - r_out * math.sin(ang)
        long_tick = i % 10 == 0
        if long_tick:
            x1, y1 = cx + (r_in - 7) * math.cos(ang), cy - (r_in - 7) * math.sin(ang)
        col = color if i <= filled else "var(--aq-border, #D8D6CB)"
        ticks.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{col}" stroke-width="{3.2 if long_tick else 2.4}" stroke-linecap="round"/>')
    h = int(width * 160 / 280)
    return (
        f'<svg viewBox="0 0 280 160" width="{width}" height="{h}" role="img" aria-label="{esc(label)} {score:.0f} out of 100, grade {esc(grade)}" xmlns="http://www.w3.org/2000/svg">'
        + "".join(ticks)
        + f'<text x="{cx}" y="{cy - 22}" text-anchor="middle" font-size="50" font-weight="650" fill="var(--aq-text, {INK})" font-family="Inter,Segoe UI,system-ui,sans-serif">{score:.0f}</text>'
        + f'<text x="{cx}" y="{cy - 4}" text-anchor="middle" font-size="13" fill="var(--aq-text-muted, {MUTED})" font-family="Inter,Segoe UI,system-ui,sans-serif">out of 100</text>'
        + "</svg>"
    )


# ---------------------------------------------------------------------------------- dashboard bars
def _shorten_bar_label(label: str) -> str:
    """Strip common prefix fragments to keep x-axis labels short: en_real_001 -> real_001, call_002 -> 002."""
    import re
    label = re.sub(r'^call_', '', label)
    label = re.sub(r'^[a-z]{2}_', '', label)  # strip language prefix like en_
    return label[:9]  # hard cap


def score_bars_svg(
    items: Sequence[Tuple[str, float, str]],
    unscored: Sequence[str] = (),
    width: int = 560,
    height: int = 240,
) -> str:
    """items = [(label, score, grade)]; unscored = [label, ...] drawn as grey neutral bars.
    solid accent = 75+, grey hatched = 60-75, red hatched = below 60, diagonal-grey = unscored."""
    all_bars = [(lbl, sc, gr, False) for lbl, sc, gr in items] + [(lbl, 0.0, '-', True) for lbl in unscored]
    if not all_bars:
        return ""
    pad_l, pad_b, pad_t = 34, 52, 14  # pad_b larger for rotated labels
    plot_h = height - pad_b - pad_t
    n = len(all_bars)
    slot = (width - pad_l - 6) / n
    bw = min(34.0, slot * 0.58)
    out = [f'<svg viewBox="0 0 {width} {height}" width="100%" role="img" aria-label="Scores by call" xmlns="http://www.w3.org/2000/svg">',
           '<defs>'
           f'<pattern id="aq-hatch" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><rect width="6" height="6" fill="var(--aq-card-tint, #EDEBE0)"/><line x1="0" y1="0" x2="0" y2="6" stroke="#9B9A90" stroke-width="2.4"/></pattern>'
           f'<pattern id="aq-hatch-red" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><rect width="6" height="6" fill="var(--aq-risk-bg, #FBE9E6)"/><line x1="0" y1="0" x2="0" y2="6" stroke="{BAD}" stroke-width="2.4"/></pattern>'
           f'<pattern id="aq-hatch-grey" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><rect width="6" height="6" fill="var(--aq-card-tint, #EDEBE0)"/><line x1="0" y1="0" x2="0" y2="6" stroke="var(--aq-text-tiny, #8A897F)" stroke-width="2"/></pattern>'
           '</defs>']
    for v in (0, 50, 100):
        y = pad_t + plot_h * (1 - v / 100)
        out.append(f'<line x1="{pad_l}" y1="{y:.1f}" x2="{width}" y2="{y:.1f}" stroke="var(--aq-border, {LINE})" stroke-width="1"/>')
        out.append(f'<text x="{pad_l - 8}" y="{y + 4:.1f}" text-anchor="end" font-size="11" fill="var(--aq-text-tiny, {FAINT})" font-family="Inter,Segoe UI,sans-serif">{v}</text>')
    lbl_y = pad_t + plot_h + 8  # baseline for rotated labels
    for i, (label, score, grade, is_ns) in enumerate(all_bars):
        cx = pad_l + slot * i + slot / 2
        x = cx - bw / 2
        if is_ns:
            hgt = max(8.0, plot_h * 0.18)  # short stub
            y = pad_t + plot_h - hgt
            fill = "url(#aq-hatch-grey)"
            title = f'{esc(label)}: not scored'
            score_lbl = "n/s"
        else:
            hgt = max(3.0, plot_h * max(0.0, min(100.0, score)) / 100)
            y = pad_t + plot_h - hgt
            fill = "var(--aq-bar-fill, #111111)" if score >= 75 else ("url(#aq-hatch)" if score >= 60 else "url(#aq-hatch-red)")
            title = f'{esc(label)}: {score:.0f}/100 (grade {esc(grade)})'
            score_lbl = ""
        out.append(f'<g class="aq-bar"><title>{title}</title>'
                   f'<rect x="{x:.1f}" y="{y:.1f}" width="{bw:.1f}" height="{hgt:.1f}" rx="7" fill="{fill}"/>')
        if score_lbl:
            out.append(f'<text x="{cx:.1f}" y="{y - 3:.1f}" text-anchor="middle" font-size="9" fill="var(--aq-text-tiny,{FAINT})" font-family="Inter,Segoe UI,sans-serif">{esc(score_lbl)}</text>')
        out.append('</g>')
        short = _shorten_bar_label(label)
        out.append(f'<text x="{cx:.1f}" y="{lbl_y}" text-anchor="end" font-size="10" fill="var(--aq-text-muted, {MUTED})" '
                   f'font-family="Inter,Segoe UI,sans-serif" transform="rotate(-40 {cx:.1f} {lbl_y})">{esc(short)}</text>')
    out.append("</svg>")
    return "".join(out)


# ---------------------------------------------------------------------------------- smooth curve
def monotone_path(points: Sequence[Tuple[float, float]]) -> str:
    """SVG path through points using monotone cubic interpolation (no overshoot between samples)."""
    pts = sorted(points)
    n = len(pts)
    if n == 0:
        return ""
    if n == 1:
        return f"M{pts[0][0]:.1f},{pts[0][1]:.1f}"
    if n == 2:
        return f"M{pts[0][0]:.1f},{pts[0][1]:.1f} L{pts[1][0]:.1f},{pts[1][1]:.1f}"
    dx = [pts[i + 1][0] - pts[i][0] for i in range(n - 1)]
    dy = [pts[i + 1][1] - pts[i][1] for i in range(n - 1)]
    sl = [dy[i] / dx[i] if dx[i] else 0.0 for i in range(n - 1)]
    m = [sl[0]] + [0.0] * (n - 2) + [sl[-1]]
    for i in range(1, n - 1):
        m[i] = 0.0 if sl[i - 1] * sl[i] <= 0 else (sl[i - 1] + sl[i]) / 2
    for i in range(n - 1):
        if sl[i] == 0:
            m[i] = m[i + 1] = 0.0
            continue
        a, b = m[i] / sl[i], m[i + 1] / sl[i]
        s = a * a + b * b
        if s > 9:
            t = 3 / math.sqrt(s)
            m[i], m[i + 1] = t * a * sl[i], t * b * sl[i]
    d = [f"M{pts[0][0]:.1f},{pts[0][1]:.1f}"]
    for i in range(n - 1):
        x0, y0 = pts[i]
        x1, y1 = pts[i + 1]
        h = dx[i] / 3
        d.append(f"C{x0 + h:.1f},{y0 + m[i] * h:.1f} {x1 - h:.1f},{y1 - m[i + 1] * h:.1f} {x1:.1f},{y1:.1f}")
    return " ".join(d)


def _nice_step(duration: float) -> int:
    for step in (5, 10, 15, 30, 60, 120, 300):
        if duration / step <= 8:
            return step
    return 600


# ---------------------------------------------------------------------------------- emotion timeline
Y_LABELS = [(1.5, "Happy"), (1.0, "Satisfied"), (0.0, "Neutral"), (-0.5, "Confused"), (-1.0, "Anxious"), (-1.5, "Frustrated"), (-2.0, "Angry")]


def build_timeline_events(report: AuditReport) -> List[dict]:
    """Things that happened during the call, positioned in time: used by the chart and the event list."""
    turns = {t.turn_id: t for t in report.transcript.turns}
    events: List[dict] = []
    for h in report.metrics.holds:
        events.append({"kind": "hold_too_long" if h.exceeded else "hold", "start": h.start_time, "end": h.end_time,
                       "label": f"On hold {mmss(h.seconds)}" + (" (over the 2:00 limit)" if h.exceeded else ""), "turn": h.end_turn})
    for g in report.metrics.dead_air_events:
        t = turns.get(g.turn or 0)
        if t:
            events.append({"kind": "dead_air", "start": max(0.0, t.start_time - t.silence_before), "end": t.start_time,
                           "label": f"Silence {t.silence_before:.0f}s", "turn": t.turn_id})
    for g in report.metrics.interruption_events:
        t = turns.get(g.turn or 0)
        if t:
            who = "Agent" if t.speaker == "agent" else "Customer"
            events.append({"kind": "interruption", "start": t.start_time, "end": t.start_time, "label": f"{who} talked over the other person", "turn": t.turn_id})
    for p in report.policy_results:
        if p.verdict == "violation":
            t = turns.get(p.turn or 0)
            if t:
                events.append({"kind": "violation", "start": t.start_time, "end": t.start_time,
                               "label": f"Rule broken ({p.clause_id}, {p.severity})", "turn": t.turn_id})
    return sorted(events, key=lambda e: e["start"])


def emotion_timeline_svg(report: AuditReport, width: int = 1000, height: int = 400) -> str:
    turns = {t.turn_id: t for t in report.transcript.turns}
    duration = max([report.metrics.duration_sec] + [t.end_time for t in report.transcript.turns] + [1.0])
    left, right, top = 112, width - 104, 34
    plot_b = height - 118
    ymin, ymax = -2.35, 1.85

    def X(sec: float) -> float:
        return left + (right - left) * (sec / duration)

    def Y(v: float) -> float:
        return top + (plot_b - top) * (ymax - v) / (ymax - ymin)

    o: List[str] = [f'<svg viewBox="0 0 {width} {height}" width="100%" role="img" aria-label="Emotion timeline of the call" class="aq-timeline" xmlns="http://www.w3.org/2000/svg" font-family="Inter,Segoe UI,system-ui,sans-serif">']
    # zones
    o.append(f'<rect x="{left}" y="{Y(ymax):.1f}" width="{right - left}" height="{Y(0) - Y(ymax):.1f}" fill="var(--aq-zone-pos, #EEF6F0)"/>')
    o.append(f'<rect x="{left}" y="{Y(0):.1f}" width="{right - left}" height="{Y(ymin) - Y(0):.1f}" fill="var(--aq-zone-neg, #FBF0ED)"/>')
    for v, name in Y_LABELS:
        y = Y(v)
        dash = "" if v == 0 else 'stroke-dasharray="3 5"'
        o.append(f'<line x1="{left}" y1="{y:.1f}" x2="{right}" y2="{y:.1f}" stroke="{"var(--aq-text-muted, #9B9A90)" if v == 0 else "var(--aq-border, #E2E0D6)"}" stroke-width="{1.4 if v == 0 else 1}" {dash}/>')
        o.append(f'<text x="{left - 12}" y="{y + 4:.1f}" text-anchor="end" font-size="12" fill="var(--aq-text-muted, {MUTED})">{name}</text>')
    # right axis: how the agent sounds (same vertical scale)
    for v, name in [(1.5, "Empathetic"), (1.0, "Warm"), (0.5, "Calm"), (-0.5, "Rushed"), (-1.5, "Defensive")]:
        o.append(f'<text x="{right + 12}" y="{Y(v) + 4:.1f}" font-size="12" fill="var(--aq-axis-agent, #7C8BB0)">{name}</text>')
    o.append(f'<text x="{left - 12}" y="16" text-anchor="end" font-size="11" font-weight="700" fill="var(--aq-text, {INK})">CUSTOMER</text>')
    o.append(f'<text x="{right + 12}" y="16" font-size="11" font-weight="700" fill="var(--aq-axis-agent, #7C8BB0)">AGENT</text>')
    # x axis
    step = _nice_step(duration)
    t = 0
    while t <= duration + 0.01:
        x = X(t)
        o.append(f'<line x1="{x:.1f}" y1="{plot_b}" x2="{x:.1f}" y2="{plot_b + 5}" stroke="var(--aq-border, {FAINT})"/>')
        o.append(f'<text x="{x:.1f}" y="{plot_b + 20}" text-anchor="middle" font-size="11" fill="var(--aq-text-muted, {MUTED})">{mmss(t)}</text>')
        t += step
    o.append(f'<line x1="{left}" y1="{plot_b}" x2="{right}" y2="{plot_b}" stroke="var(--aq-border, {FAINT})"/>')
    # event spans (holds, silences)
    events = build_timeline_events(report)
    for e in events:
        if e["kind"] in ("hold", "hold_too_long", "dead_air") and e["end"] > e["start"]:
            x0, x1 = X(e["start"]), X(e["end"])
            col = BAD if e["kind"] == "hold_too_long" else (WARN if e["kind"] == "dead_air" else "#8A8A85")
            o.append(f'<g><title>{esc(e["label"])}</title><rect x="{x0:.1f}" y="{top}" width="{max(3.0, x1 - x0):.1f}" height="{plot_b - top}" fill="{col}" opacity="0.13"/>'
                     f'<line x1="{x0:.1f}" y1="{top}" x2="{x0:.1f}" y2="{plot_b}" stroke="{col}" stroke-width="1" stroke-dasharray="4 4" opacity="0.6"/>'
                     f'<line x1="{x1:.1f}" y1="{top}" x2="{x1:.1f}" y2="{plot_b}" stroke="{col}" stroke-width="1" stroke-dasharray="4 4" opacity="0.6"/>'
                     f'<text x="{(x0 + x1) / 2:.1f}" y="{top + 14}" text-anchor="middle" font-size="11" font-weight="600" fill="{col}">{esc(e["label"])}</text></g>')
    # series
    def series(points, colors, valence_map, who: str, dashed: bool):
        coords = []
        for p in points:
            tt = turns.get(p.turn)
            if not tt:
                continue
            mid = (tt.start_time + tt.end_time) / 2
            coords.append((X(mid), Y(p.valence), p, tt))
        return coords

    cust = series(report.emotion.points, EMOTION_COLOR, VALENCE, "Customer", False)
    agent = series(report.agent_tone.points, TONE_COLOR, TONE_VALENCE, "Agent", True)
    if agent:
        o.append(f'<path d="{monotone_path([(x, y) for x, y, _, _ in agent])}" fill="none" stroke="#9AA6C2" stroke-width="2.6" stroke-dasharray="7 6" stroke-linecap="round"/>')
    if cust:
        path = monotone_path([(x, y) for x, y, _, _ in cust])
        o.append(f'<path d="{path} L{cust[-1][0]:.1f},{Y(0):.1f} L{cust[0][0]:.1f},{Y(0):.1f} Z" fill="var(--aq-text, {INK})" opacity="0.06"/>')
        o.append(f'<path d="{path}" fill="none" stroke="var(--aq-text, {INK})" stroke-width="3.4" stroke-linecap="round" stroke-linejoin="round"/>')
    for x, y, p, tt in agent:
        o.append(f'<g class="aq-dot"><title>Agent · turn {p.turn} · {mmss(tt.start_time)} · {esc(p.emotion)}</title>'
                 f'<rect x="{x - 5.5:.1f}" y="{y - 5.5:.1f}" width="11" height="11" rx="3" fill="var(--aq-card-bg, #fff)" stroke="{TONE_COLOR.get(p.emotion, MUTED)}" stroke-width="2.6"/></g>')
    for x, y, p, tt in cust:
        o.append(f'<g class="aq-dot"><title>Customer · turn {p.turn} · {mmss(tt.start_time)} · {esc(p.emotion)}</title>'
                 f'<circle cx="{x:.1f}" cy="{y:.1f}" r="7" fill="{EMOTION_COLOR.get(p.emotion, MUTED)}" stroke="var(--aq-card-bg, #fff)" stroke-width="2.4"/></g>')
    # point events (violations / interruptions) on a strip under the axis
    strip_y = plot_b + 46
    o.append(f'<text x="{left - 12}" y="{strip_y + 4}" text-anchor="end" font-size="12" fill="var(--aq-text-muted, {MUTED})">Events</text>')
    o.append(f'<line x1="{left}" y1="{strip_y}" x2="{right}" y2="{strip_y}" stroke="var(--aq-border, {LINE})" stroke-width="1.5"/>')
    for e in events:
        x = X(e["start"])
        if e["kind"] == "violation":
            o.append(f'<g class="aq-dot"><title>{esc(e["label"])} · turn {e["turn"]}</title><path d="M{x:.1f},{strip_y - 9} l9,9 l-9,9 l-9,-9 Z" fill="{BAD}"/>'
                     f'<text x="{x:.1f}" y="{strip_y + 3.5}" text-anchor="middle" font-size="10" font-weight="700" fill="#fff">!</text></g>')
        elif e["kind"] == "interruption":
            o.append(f'<g class="aq-dot"><title>{esc(e["label"])} · turn {e["turn"]}</title><circle cx="{x:.1f}" cy="{strip_y}" r="9" fill="{WARN}"/>'
                     f'<path d="M{x + 1.5:.1f},{strip_y - 5} l-4,6 h3 l-1.5,5 l5,-7 h-3.2 Z" fill="#fff"/></g>')
        else:
            col = BAD if e["kind"] == "hold_too_long" else (WARN if e["kind"] == "dead_air" else "#8A8A85")
            x1 = X(e["end"])
            o.append(f'<g class="aq-dot"><title>{esc(e["label"])}</title><rect x="{x:.1f}" y="{strip_y - 6}" width="{max(8.0, x1 - x):.1f}" height="12" rx="6" fill="{col}" opacity="0.85"/></g>')
    # legend
    ly = height - 14
    items = [("Customer emotion", f'<circle cx="0" cy="-4" r="6" fill="{EMOTION_COLOR["frustrated"]}" stroke="var(--aq-card-bg, #fff)" stroke-width="2"/>'),
             ("Agent tone", f'<rect x="-5" y="-9" width="10" height="10" rx="3" fill="var(--aq-card-bg, #fff)" stroke="{TONE_COLOR["calm"]}" stroke-width="2.4"/>'),
             ("Rule broken", f'<path d="M0,-12 l7,7 l-7,7 l-7,-7 Z" fill="{BAD}"/>'),
             ("Talked over", f'<circle cx="0" cy="-5" r="7" fill="{WARN}"/>'),
             ("Hold or silence", f'<rect x="-7" y="-10" width="14" height="10" rx="5" fill="#8A8A85" opacity="0.85"/>')]
    x = left
    for name, icon in items:
        o.append(f'<g transform="translate({x + 8},{ly})">{icon}</g><text x="{x + 22}" y="{ly}" font-size="12" fill="var(--aq-text-muted, {MUTED})">{name}</text>')
        x += 40 + len(name) * 6.6
    o.append("</svg>")
    return "".join(o)
