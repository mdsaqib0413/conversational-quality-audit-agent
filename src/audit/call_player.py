"""Call audio player with interactive timeline, clickable key moments and synchronized transcript."""

from __future__ import annotations

import base64
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

import streamlit as st

from .schemas import AuditReport
from .viz import esc, mmss

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def resolve_audio_path(call_id: str, repo_root: Optional[Path] = None) -> Optional[Path]:
    """Resolve audio path for a call:
    1. data/audio/<call_id>.mp3 (prefer mono)
    2. data/audio/<call_id>_stereo.mp3 (fallback)
    3. data/audio/real_calls/<call_id>.mp3
    """
    root = repo_root or REPO_ROOT
    mono = root / "data" / "audio" / f"{call_id}.mp3"
    if mono.is_file():
        return mono
    stereo = root / "data" / "audio" / f"{call_id}_stereo.mp3"
    if stereo.is_file():
        return stereo
    real = root / "data" / "audio" / "real_calls" / f"{call_id}.mp3"
    if real.is_file():
        return real
    return None


@dataclass
class KeyMoment:
    time_sec: float
    mm_ss: str
    label: str
    who: str            # "Agent" | "Customer" | "System"
    severity: str       # "bad" | "warn" | "good" | "info"
    quote: str = ""
    turn_id: Optional[int] = None
    category: str = ""


@dataclass
class NeverHappenedItem:
    step_id: str
    title: str
    missing_reason: str


def extract_key_moments(report: AuditReport) -> Tuple[List[KeyMoment], List[NeverHappenedItem]]:
    """Extract key moments from existing report data, sorted by time."""
    turn_map = {t.turn_id: t for t in report.transcript.turns}
    moments: List[KeyMoment] = []
    never_happened: List[NeverHappenedItem] = []

    # 1. Customer emotion turning negative (first frustrated/angry/negative turn, and later recovery)
    cust_neg_turns = [
        t for t in report.transcript.turns
        if t.speaker == "customer" and (t.emotion in ("angry", "frustrated", "anxious", "confused"))
    ]
    if cust_neg_turns:
        first_neg = cust_neg_turns[0]
        emo = first_neg.emotion or "negative"
        sev = "bad" if emo in ("angry", "frustrated") else "warn"
        moments.append(KeyMoment(
            time_sec=first_neg.start_time,
            mm_ss=mmss(first_neg.start_time),
            label=f"Customer became {emo} at {mmss(first_neg.start_time)}",
            who="Customer",
            severity=sev,
            quote=first_neg.text,
            turn_id=first_neg.turn_id,
            category="emotion",
        ))

        # Check for subsequent recovery
        recovered = [
            t for t in report.transcript.turns
            if t.speaker == "customer" and t.turn_id > first_neg.turn_id and t.emotion in ("satisfied", "happy")
        ]
        if recovered:
            rec = recovered[0]
            moments.append(KeyMoment(
                time_sec=rec.start_time,
                mm_ss=mmss(rec.start_time),
                label=f"Customer emotion recovered ({rec.emotion}) at {mmss(rec.start_time)}",
                who="Customer",
                severity="good",
                quote=rec.text,
                turn_id=rec.turn_id,
                category="emotion",
            ))

    # 2. SOP steps partial/missed
    for s in report.sop_results:
        if s.status in ("missed", "partial"):
            if s.turn and s.turn in turn_map:
                t = turn_map[s.turn]
                status_txt = "skipped" if s.status == "missed" else "partially completed"
                title_txt = s.title or s.missing or s.reason or s.step_id
                moments.append(KeyMoment(
                    time_sec=t.start_time,
                    mm_ss=mmss(t.start_time),
                    label=f"Agent deviated at {mmss(t.start_time)}: {status_txt} {title_txt} ({s.step_id})",
                    who="Agent",
                    severity="bad" if (s.critical or s.status == "missed") else "warn",
                    quote=s.quote or s.missing or s.reason,
                    turn_id=s.turn,
                    category="sop",
                ))
            else:
                never_happened.append(NeverHappenedItem(
                    step_id=s.step_id,
                    title=s.title or s.step_id,
                    missing_reason=s.missing or s.reason or "Step not observed in call",
                ))

    # 3. Policy violations
    for p in report.policy_results:
        if p.verdict == "violation":
            t = turn_map.get(p.turn) if p.turn else None
            time_sec = t.start_time if t else 0.0
            time_str = mmss(time_sec)
            desc = p.explanation or p.claim or "Violation"
            moments.append(KeyMoment(
                time_sec=time_sec,
                mm_ss=time_str,
                label=f"Policy violation ({p.clause_id}) at {time_str}: {desc[:110]}",
                who="Agent",
                severity="bad" if p.severity in ("critical", "major") else "warn",
                quote=p.quote,
                turn_id=p.turn,
                category="policy",
            ))

    # 4. Long dead air/hold gaps
    for h in getattr(report.metrics, "holds", []):
        if h.exceeded or h.seconds >= 30:
            moments.append(KeyMoment(
                time_sec=h.start_time,
                mm_ss=mmss(h.start_time),
                label=f"Long hold gap ({int(h.seconds)}s) at {mmss(h.start_time)}",
                who="Agent",
                severity="bad" if h.exceeded else "warn",
                quote=f"Hold lasted {int(h.seconds)}s (turns {h.start_turn} to {h.end_turn})",
                turn_id=h.start_turn,
                category="gap",
            ))

    for g in getattr(report.metrics, "dead_air_events", []):
        if g.turn and g.turn in turn_map:
            t = turn_map[g.turn]
            moments.append(KeyMoment(
                time_sec=t.start_time,
                mm_ss=mmss(t.start_time),
                label=f"Dead air silence at {mmss(t.start_time)}",
                who="System",
                severity="warn",
                quote=g.detail or g.quote,
                turn_id=g.turn,
                category="gap",
            ))

    # 5. Agent interruptions
    for g in getattr(report.metrics, "interruption_events", []):
        if g.turn and g.turn in turn_map:
            t = turn_map[g.turn]
            moments.append(KeyMoment(
                time_sec=t.start_time,
                mm_ss=mmss(t.start_time),
                label=f"Agent interruption at {mmss(t.start_time)}",
                who="Agent",
                severity="warn",
                quote=g.quote or g.detail,
                turn_id=g.turn,
                category="gap",
            ))

    # 6. No-empathy moments
    for g in report.gaps:
        if g.gap_type in ("no_empathy", "no_empathy_shown", "empathy_gap"):
            if g.turn and g.turn in turn_map:
                t = turn_map[g.turn]
                moments.append(KeyMoment(
                    time_sec=t.start_time,
                    mm_ss=mmss(t.start_time),
                    label=f"No empathy shown at {mmss(t.start_time)}",
                    who="Agent",
                    severity="warn",
                    quote=g.quote or g.detail,
                    turn_id=g.turn,
                    category="gap",
                ))

    # 7. Closing
    if report.transcript.turns:
        agent_turns = [t for t in report.transcript.turns if t.speaker == "agent"]
        closing_turn = agent_turns[-1] if agent_turns else report.transcript.turns[-1]
        moments.append(KeyMoment(
            time_sec=closing_turn.start_time,
            mm_ss=mmss(closing_turn.start_time),
            label=f"Call closing at {mmss(closing_turn.start_time)}",
            who="Agent",
            severity="info",
            quote=closing_turn.text[:120],
            turn_id=closing_turn.turn_id,
            category="closing",
        ))

    # Sort all key moments by time ascending
    moments.sort(key=lambda m: m.time_sec)

    # De-duplicate moments with same label and time
    dedup: List[KeyMoment] = []
    seen = set()
    for m in moments:
        k = (m.time_sec, m.label)
        if k not in seen:
            seen.add(k)
            dedup.append(m)

    return dedup, never_happened


@st.cache_data(show_spinner=False)
def load_audio_base64(path_str: str, mtime: int) -> str:
    data = Path(path_str).read_bytes()
    return base64.b64encode(data).decode("ascii")


def render_player_component(report: AuditReport, audio_path: Optional[Path], dark: bool = False) -> str:
    """Build ONE self-contained HTML+JS component for audio playback, timeline, key moments, and transcript."""
    moments, never_happened = extract_key_moments(report)
    duration = report.metrics.duration_sec
    if duration <= 0 and report.transcript.turns:
        duration = max(t.end_time for t in report.transcript.turns)
    if duration <= 0:
        duration = 1.0

    has_audio = audio_path is not None and audio_path.is_file()
    audio_src = ""
    if has_audio:
        try:
            mtime = audio_path.stat().st_mtime_ns
            b64 = load_audio_base64(str(audio_path), mtime)
            audio_src = f"data:audio/mp3;base64,{b64}"
        except Exception:
            has_audio = False

    bg = "#1A1C22" if dark else "#FFFFFF"
    card_tint = "#23262F" if dark else "#F6F5EF"
    border = "#2C303B" if dark else "#E7E5DC"
    text = "#F3F2EC" if dark else "#111111"
    text_muted = "#9E9D95" if dark else "#6B6B66"
    track_bg = "#2C303B" if dark else "#E2E0D3"
    btn_bg = "#23262F" if dark else "#F6F5EF"
    btn_border = "#353A47" if dark else "#DAD8CC"
    accent = "#1F8F4E"

    # Color mapping for pins and badges
    colors = {
        "bad": "#D64545",
        "warn": "#C98A12",
        "good": "#1F8F4E",
        "info": "#3B6FE0",
    }

    # Build timeline pins HTML
    pins_html = []
    for idx, m in enumerate(moments):
        pct = max(0.0, min(100.0, (m.time_sec / duration) * 100))
        color = colors.get(m.severity, "#8A8A85")
        pin_title = f"{m.mm_ss} · {m.who}: {m.label}"
        pins_html.append(
            f'<div class="timeline-pin" data-idx="{idx}" data-sec="{m.time_sec}" '
            f'data-time="{m.mm_ss}" data-label="{esc(m.label)}" data-who="{esc(m.who)}" '
            f'style="left:{pct:.2f}%;background:{color}" title="{esc(pin_title)}"></div>'
        )

    # Build key moments list HTML
    moments_html = []
    for idx, m in enumerate(moments):
        color = colors.get(m.severity, "#8A8A85")
        btn_action = f'onclick="seekTo({m.time_sec})"' if has_audio else ""
        btn_cursor = "pointer" if has_audio else "default"
        quote_div = f'<div class="moment-quote">“{esc(m.quote[:130])}”</div>' if m.quote else ""
        moments_html.append(
            f'<div class="moment-item" id="moment-{idx}" data-sec="{m.time_sec}" data-idx="{idx}" {btn_action} style="cursor:{btn_cursor}">'
            f'<div class="moment-top">'
            f'<span class="moment-time" style="background:{color}">{m.mm_ss}</span>'
            f'<span class="moment-who">{esc(m.who)}</span>'
            f'<span class="moment-label">{esc(m.label)}</span>'
            f'</div>'
            f'{quote_div}'
            f'</div>'
        )

    # Build never-happened list HTML
    never_html = []
    if never_happened:
        items = "".join(
            f'<div class="never-item"><b>{esc(n.step_id)}:</b> {esc(n.title)} <span class="never-reason">({esc(n.missing_reason)})</span></div>'
            for n in never_happened
        )
        never_html.append(
            f'<div class="never-box">'
            f'<div class="never-title">Never happened in this call (no timestamp)</div>'
            f'{items}'
            f'</div>'
        )

    # Build transcript turns HTML
    turns_html = []
    for t in report.transcript.turns:
        speaker_lbl = "Agent" if t.speaker == "agent" else "Customer"
        turn_action = f'onclick="seekTo({t.start_time})"' if has_audio else ""
        t_cursor = "cursor:pointer;" if has_audio else ""
        time_btn = f'<span class="turn-seek-btn" {turn_action} style="{t_cursor}">[{mmss(t.start_time)}]</span>'
        turns_html.append(
            f'<div class="t-row {t.speaker}" id="turn-{t.turn_id}" data-start="{t.start_time}" data-end="{t.end_time}">'
            f'<div class="t-meta">{time_btn} <b>{speaker_lbl}</b> #{t.turn_id}</div>'
            f'<div class="t-bub">{esc(t.text)}</div>'
            f'</div>'
        )

    audio_element = (
        f'<audio id="player" preload="metadata" style="display:none;">'
        f'<source src="{audio_src}" type="audio/mp3"></audio>'
        if has_audio else ""
    )

    player_bar_html = f"""
    <div class="cp-bar" id="cp-bar">
      <div class="cp-left">
        <button class="cp-btn cp-play" id="btn-play" title="Play / Pause (Space)" aria-label="Play">
          <svg id="icon-play" width="15" height="15" viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z"/></svg>
          <svg id="icon-pause" width="15" height="15" viewBox="0 0 24 24" fill="currentColor" style="display:none;"><path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z"/></svg>
        </button>
        <button class="cp-btn cp-skip" id="btn-back" title="Back 10 seconds" aria-label="Back 10 seconds">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><path d="M11 17l-5-5 5-5M18 17l-5-5 5-5"/></svg>
          <span>-10s</span>
        </button>
        <button class="cp-btn cp-skip" id="btn-fwd" title="Forward 10 seconds" aria-label="Forward 10 seconds">
          <span>+10s</span>
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><path d="M13 17l5-5-5-5M6 17l5-5-5-5"/></svg>
        </button>
        <div class="cp-time">
          <span id="cur-time">0:00</span>
          <span class="cp-sep">/</span>
          <span id="dur-time">{mmss(duration)}</span>
        </div>
      </div>

      <div class="cp-timeline-wrap" id="timeline-wrap">
        <div class="cp-track" id="track">
          <div class="cp-progress" id="progress"></div>
          <div class="cp-playhead" id="playhead"></div>
          {"".join(pins_html)}
        </div>
        <div class="cp-tooltip" id="tooltip"></div>
      </div>

      <div class="cp-right">
        <div class="cp-speed-wrap">
          <button class="cp-btn cp-speed-btn" id="btn-speed" title="Cycle playback speed: 1x → 1.5x → 2x → 1x">1x</button>
        </div>
        <div class="cp-vol-wrap">
          <button class="cp-btn cp-vol-btn" id="btn-vol" title="Mute / Unmute" aria-label="Mute / Unmute">
            <svg id="icon-vol" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"></polygon><path d="M19.07 4.93a10 10 0 0 1 0 14.14M15.54 8.46a5 5 0 0 1 0 7.07"></path></svg>
            <svg id="icon-mute" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="display:none;"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"></polygon><line x1="23" y1="9" x2="17" y2="15"></line><line x1="17" y1="9" x2="23" y2="15"></line></svg>
          </button>
          <input type="range" class="cp-vol-slider" id="vol-slider" min="0" max="1" step="0.05" value="1" title="Volume">
        </div>
      </div>
    </div>
    """ if has_audio else '<div class="no-audio-banner">No audio for this call</div>'

    scrollbar_css = f"""
  * {{ scrollbar-color: #2A303C {bg}; scrollbar-width: thin; }}
  *::-webkit-scrollbar {{ width: 6px; height: 6px; }}
  *::-webkit-scrollbar-track {{ background: {bg}; }}
  *::-webkit-scrollbar-thumb {{ background: #2A303C; border-radius: 3px; }}
  *::-webkit-scrollbar-thumb:hover {{ background: #384152; }}
  *::-webkit-scrollbar-corner {{ background: {bg} !important; }}
  *::-webkit-scrollbar-button {{ display: none !important; width: 0 !important; height: 0 !important; }}
""" if dark else ""

    component_html = f"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<style>
  * {{ box-sizing: border-box; margin:0; padding:0; }}
  html, body {{ font-family: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background:{bg}; color:{text}; padding:14px; font-size:13px; color-scheme: {"dark" if dark else "light"}; }}
  {scrollbar_css}
  .player-card {{ background:{bg}; border:1px solid {border}; border-radius:18px; padding:16px; margin-bottom:12px; }}
  .player-sticky-header {{ position:sticky; top:0; z-index:50; background:{bg}; padding-bottom:10px; margin-bottom:12px; border-bottom:1px solid {border}; }}
  .no-audio-banner {{ background:{card_tint}; border:1px dashed {border}; color:{text_muted}; padding:14px 18px; border-radius:12px; font-weight:600; text-align:center; }}

  /* Compact Player Bar */
  .cp-bar {{ display:flex; align-items:center; gap:12px; background:{card_tint}; border:1px solid {border}; border-radius:14px; padding:8px 14px; }}
  .cp-left, .cp-right {{ display:flex; align-items:center; gap:8px; flex-shrink:0; }}
  .cp-btn {{ display:inline-flex; align-items:center; justify-content:center; gap:3px; background:{btn_bg}; border:1px solid {btn_border}; color:{text}; border-radius:10px; padding:6px 10px; font-size:12px; font-weight:600; cursor:pointer; outline:none; transition:all 0.12s; }}
  .cp-btn:hover {{ border-color:{text}; }}
  .cp-play {{ width:34px; height:34px; border-radius:50%; background:{text}; color:{bg}; border:none; padding:0; }}
  .cp-play:hover {{ opacity:0.9; }}
  .cp-skip {{ font-size:11px; padding:4px 8px; }}
  .cp-time {{ font-size:12px; font-weight:600; font-variant-numeric:tabular-nums; color:{text}; margin-left:4px; white-space:nowrap; }}
  .cp-sep {{ color:{text_muted}; margin:0 2px; }}

  /* Timeline */
  .cp-timeline-wrap {{ flex:1; position:relative; min-width:140px; padding:8px 0; }}
  .cp-track {{ position:relative; height:10px; background:{track_bg}; border-radius:5px; cursor:pointer; }}
  .cp-progress {{ position:absolute; top:0; left:0; height:100%; width:0%; background:{accent}; border-radius:5px; pointer-events:none; }}
  .cp-playhead {{ position:absolute; top:-3px; left:0%; width:16px; height:16px; background:{text}; border:2.5px solid {bg}; border-radius:50%; transform:translateX(-50%); pointer-events:none; box-shadow:0 1px 4px rgba(0,0,0,0.35); }}
  .timeline-pin {{ position:absolute; top:-3px; width:7px; height:16px; border-radius:2.5px; transform:translateX(-50%); cursor:pointer; z-index:2; border:1px solid {bg}; transition:transform 0.1s; }}
  .timeline-pin:hover {{ transform:translateX(-50%) scale(1.4); z-index:5; }}

  /* Tooltip */
  .cp-tooltip {{ position:absolute; bottom:26px; left:0; transform:translateX(-50%); background:{text}; color:{bg}; font-size:11px; font-weight:600; padding:4px 8px; border-radius:6px; pointer-events:none; white-space:nowrap; display:none; z-index:100; box-shadow:0 2px 8px rgba(0,0,0,0.25); }}

  /* Speed and Volume */
  .cp-speed-wrap {{ position:relative; }}
  .cp-speed-btn {{ min-width:38px; font-variant-numeric:tabular-nums; }}
  .cp-vol-wrap {{ display:flex; align-items:center; gap:6px; }}
  .cp-vol-slider {{ width:65px; height:4px; accent-color:{accent}; cursor:pointer; }}

  /* Grid and content */
  .main-grid {{ display:grid; grid-template-columns:1.1fr 0.9fr; gap:16px; margin-top:14px; }}
  @media (max-width:850px) {{ .main-grid {{ grid-template-columns:1fr; }} }}
  .section-h {{ font-size:14px; font-weight:700; margin-bottom:10px; display:flex; align-items:center; justify-content:space-between; }}
  .moments-list {{ max-height:430px; overflow-y:auto; display:flex; flex-direction:column; gap:8px; padding-right:4px; }}
  .moment-item {{ background:{card_tint}; border:1px solid {border}; border-radius:12px; padding:10px 12px; transition:all 0.15s; }}
  .moment-item:hover {{ border-color:#3B6FE0; }}
  .moment-item.active {{ border-color:{accent}; background:{bg}; box-shadow:0 0 0 2px #1F8F4E55; }}
  .moment-top {{ display:flex; align-items:center; gap:8px; flex-wrap:wrap; }}
  .moment-time {{ color:#fff; font-size:11px; font-weight:700; padding:2px 7px; border-radius:6px; }}
  .moment-who {{ font-size:11px; font-weight:700; color:{text_muted}; text-transform:uppercase; letter-spacing:0.04em; }}
  .moment-label {{ font-size:12.5px; font-weight:600; color:{text}; flex:1; }}
  .moment-quote {{ font-size:11.5px; color:{text_muted}; font-style:italic; margin-top:5px; padding-left:4px; border-left:2px solid {border}; }}
  .never-box {{ margin-top:14px; background:{card_tint}; border:1px solid {border}; border-radius:12px; padding:12px; }}
  .never-title {{ font-size:12px; font-weight:700; color:{text_muted}; text-transform:uppercase; letter-spacing:0.05em; margin-bottom:6px; }}
  .never-item {{ font-size:12px; margin-top:4px; color:{text}; }}
  .never-reason {{ color:{text_muted}; font-size:11px; }}
  .transcript-pane {{ max-height:430px; overflow-y:auto; padding-right:6px; display:flex; flex-direction:column; gap:8px; }}
  .t-row {{ display:flex; flex-direction:column; max-width:85%; }}
  .t-row.agent {{ align-self:flex-start; }}
  .t-row.customer {{ align-self:flex-end; }}
  .t-meta {{ font-size:11px; color:{text_muted}; margin-bottom:3px; display:flex; align-items:center; gap:6px; }}
  .turn-seek-btn {{ color:#3B6FE0; font-weight:700; }}
  .turn-seek-btn:hover {{ text-decoration:underline; }}
  .t-bub {{ padding:8px 12px; border-radius:14px; font-size:12.5px; background:{card_tint}; border:1px solid {border}; color:{text}; }}
  .t-row.customer .t-bub {{ background:{"#282B34" if dark else "#111"}; color:#FFF; border-color:{"#282B34" if dark else "#111"}; }}
  .t-row.active .t-bub {{ box-shadow:0 0 0 2px {accent}; }}
</style>
</head>
<body class="{'dark' if dark else 'light'}">
<div class="player-card">
  {audio_element}
  <div class="player-sticky-header">
    {player_bar_html}
  </div>

  <div class="main-grid">
    <div>
      <div class="section-h">
        <span>Key Moments ({len(moments)})</span>
        <span style="font-size:11px;font-weight:normal;color:{text_muted};">{"Click any timestamp to seek & play" if has_audio else "Timestamps from turn start"}</span>
      </div>
      <div class="moments-list" id="moments-list">
        {"".join(moments_html) if moments_html else '<div style="color:' + text_muted + ';padding:10px;">No key deviation moments detected.</div>'}
      </div>
      {"".join(never_html)}
    </div>

    <div>
      <div class="section-h">
        <span>Synchronized Transcript</span>
        <span style="font-size:11px;font-weight:normal;color:{text_muted};">Click [mm:ss] to seek</span>
      </div>
      <div class="transcript-pane" id="transcript-pane">
        {"".join(turns_html)}
      </div>
    </div>
  </div>
</div>

<script>
  const player = document.getElementById('player');
  const track = document.getElementById('track');
  const progress = document.getElementById('progress');
  const playhead = document.getElementById('playhead');
  const curTime = document.getElementById('cur-time');
  const durTime = document.getElementById('dur-time');
  const tooltip = document.getElementById('tooltip');
  const timelineWrap = document.getElementById('timeline-wrap');
  const btnPlay = document.getElementById('btn-play');
  const iconPlay = document.getElementById('icon-play');
  const iconPause = document.getElementById('icon-pause');
  const btnBack = document.getElementById('btn-back');
  const btnFwd = document.getElementById('btn-fwd');
  const btnSpeed = document.getElementById('btn-speed');
  const btnVol = document.getElementById('btn-vol');
  const iconVol = document.getElementById('icon-vol');
  const iconMute = document.getElementById('icon-mute');
  const volSlider = document.getElementById('vol-slider');

  let totalDuration = {duration};
  let isDragging = false;

  function fmtTime(sec) {{
    if (!sec || isNaN(sec) || sec < 0) sec = 0;
    const m = Math.floor(sec / 60);
    const s = Math.floor(sec % 60);
    return m + ':' + (s < 10 ? '0' : '') + s;
  }}

  function repositionPins(newDur) {{
    if (!newDur || newDur <= 0) return;
    const pins = document.querySelectorAll('.timeline-pin');
    pins.forEach(pin => {{
      const sec = parseFloat(pin.getAttribute('data-sec') || '0');
      const pct = Math.max(0, Math.min(100, (sec / newDur) * 100));
      pin.style.left = pct.toFixed(2) + '%';
    }});
  }}

  function updateAudioDuration(d) {{
    if (d && isFinite(d) && d > 0) {{
      totalDuration = d;
      if (durTime) durTime.textContent = fmtTime(totalDuration);
      repositionPins(totalDuration);
    }}
  }}

  function togglePlay() {{
    if (!player) return;
    if (player.paused) {{
      player.play();
    }} else {{
      player.pause();
    }}
  }}

  function seekTo(sec) {{
    if (!player) return;
    player.currentTime = Math.max(0, Math.min(totalDuration, sec));
    player.play();
  }}

  if (player) {{
    player.addEventListener('loadedmetadata', function() {{
      updateAudioDuration(player.duration);
    }});
    player.addEventListener('durationchange', function() {{
      updateAudioDuration(player.duration);
    }});
    player.addEventListener('play', function() {{
      if (iconPlay) iconPlay.style.display = 'none';
      if (iconPause) iconPause.style.display = 'block';
    }});
    player.addEventListener('pause', function() {{
      if (iconPlay) iconPlay.style.display = 'block';
      if (iconPause) iconPause.style.display = 'none';
    }});
    player.addEventListener('ended', function() {{
      if (iconPlay) iconPlay.style.display = 'block';
      if (iconPause) iconPause.style.display = 'none';
    }});

    if (btnPlay) btnPlay.addEventListener('click', togglePlay);
    if (btnBack) btnBack.addEventListener('click', () => {{ player.currentTime = Math.max(0, player.currentTime - 10); }});
    if (btnFwd) btnFwd.addEventListener('click', () => {{ player.currentTime = Math.min(totalDuration, player.currentTime + 10); }});

    // Speed cycle button: 1x -> 1.5x -> 2x -> 1x
    const _speedSteps = [1, 1.5, 2];
    let _speedIdx = 0;
    if (btnSpeed) {{
      btnSpeed.addEventListener('click', () => {{
        _speedIdx = (_speedIdx + 1) % _speedSteps.length;
        const rate = _speedSteps[_speedIdx];
        player.playbackRate = rate;
        btnSpeed.textContent = rate + 'x';
      }});
    }}

    // Volume
    if (btnVol && volSlider) {{
      btnVol.addEventListener('click', () => {{
        player.muted = !player.muted;
        if (player.muted) {{
          iconVol.style.display = 'none';
          iconMute.style.display = 'block';
        }} else {{
          iconVol.style.display = 'block';
          iconMute.style.display = 'none';
        }}
      }});
      volSlider.addEventListener('input', () => {{
        player.volume = parseFloat(volSlider.value);
        player.muted = player.volume === 0;
        if (player.muted) {{
          iconVol.style.display = 'none';
          iconMute.style.display = 'block';
        }} else {{
          iconVol.style.display = 'block';
          iconMute.style.display = 'none';
        }}
      }});
    }}

    // Timeline scrubbing (click or drag)
    function seekFromEvent(e) {{
      if (!track) return;
      const rect = track.getBoundingClientRect();
      const clickX = e.clientX - rect.left;
      const frac = Math.max(0, Math.min(1, clickX / rect.width));
      player.currentTime = frac * totalDuration;
      const pct = frac * 100;
      if (progress) progress.style.width = pct + '%';
      if (playhead) playhead.style.left = pct + '%';
      if (curTime) curTime.textContent = fmtTime(player.currentTime);
    }}

    if (track) {{
      track.addEventListener('mousedown', function(e) {{
        isDragging = true;
        seekFromEvent(e);
      }});
      window.addEventListener('mousemove', function(e) {{
        if (isDragging) {{
          seekFromEvent(e);
        }}
      }});
      window.addEventListener('mouseup', function() {{
        isDragging = false;
      }});

      // Hover tooltip
      track.addEventListener('mousemove', function(e) {{
        if (!tooltip) return;
        const rect = track.getBoundingClientRect();
        const offsetX = e.clientX - rect.left;
        const frac = Math.max(0, Math.min(1, offsetX / rect.width));
        const hoverSec = frac * totalDuration;

        // Check if close to a pin
        let pinText = '';
        const pins = document.querySelectorAll('.timeline-pin');
        pins.forEach(pin => {{
          const pinSec = parseFloat(pin.getAttribute('data-sec') || '0');
          if (Math.abs(hoverSec - pinSec) <= Math.max(2.0, totalDuration * 0.02)) {{
            pinText = pin.getAttribute('data-time') + ' · ' + (pin.getAttribute('data-who') || '') + ': ' + pin.getAttribute('data-label');
          }}
        }});

        tooltip.style.display = 'block';
        tooltip.style.left = offsetX + 'px';
        tooltip.textContent = pinText || fmtTime(hoverSec);
      }});

      track.addEventListener('mouseleave', function() {{
        if (tooltip) tooltip.style.display = 'none';
      }});
    }}

    // Time update loop
    player.addEventListener('timeupdate', function() {{
      if (isDragging) return;
      const t = player.currentTime;
      if (curTime) curTime.textContent = fmtTime(t);
      const pct = Math.max(0, Math.min(100, (t / totalDuration) * 100));
      if (progress) progress.style.width = pct + '%';
      if (playhead) playhead.style.left = pct + '%';

      // Highlight active moment
      const momentEls = document.querySelectorAll('.moment-item');
      let activeIdx = -1;
      for (let i = 0; i < momentEls.length; i++) {{
        const sec = parseFloat(momentEls[i].getAttribute('data-sec') || '0');
        if (t >= sec - 1.5) {{
          activeIdx = i;
        }}
      }}
      momentEls.forEach((el, idx) => {{
        if (idx === activeIdx) {{
          el.classList.add('active');
        }} else {{
          el.classList.remove('active');
        }}
      }});

      // Highlight active transcript turn & scroll into view
      const turnEls = document.querySelectorAll('.t-row');
      turnEls.forEach(el => {{
        const start = parseFloat(el.getAttribute('data-start') || '0');
        const end = parseFloat(el.getAttribute('data-end') || '0');
        if (t >= start && t <= end + 0.5) {{
          el.classList.add('active');
        }} else {{
          el.classList.remove('active');
        }}
      }});
    }});

    // Space key to play/pause
    window.addEventListener('keydown', function(e) {{
      if (e.code === 'Space' || e.key === ' ') {{
        const tag = (e.target && e.target.tagName) ? e.target.tagName.toLowerCase() : '';
        if (tag !== 'input' && tag !== 'textarea' && tag !== 'button') {{
          e.preventDefault();
          togglePlay();
        }}
      }}
    }});
  }}
</script>
</body>
</html>
"""
    return component_html
