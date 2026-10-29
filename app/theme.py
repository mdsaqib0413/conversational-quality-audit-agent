"""Streamlit chrome styling and theme tokens (light and dark mode)."""

from __future__ import annotations

import streamlit as st


def _icon(path: str) -> str:
    svg = (
        "<svg xmlns='http://www.w3.org/2000/svg' width='18' height='18' viewBox='0 0 24 24' fill='none' stroke='%23111' stroke-width='1.9' "
        "stroke-linecap='round' stroke-linejoin='round'>" + path + "</svg>"
    )
    return 'url("data:image/svg+xml,' + svg.replace('"', "'") + '")'


ICONS = [
    "<rect x='3' y='3' width='7' height='7' rx='1.5'/><rect x='14' y='3' width='7' height='7' rx='1.5'/><rect x='3' y='14' width='7' height='7' rx='1.5'/><rect x='14' y='14' width='7' height='7' rx='1.5'/>",
    "<path d='M5 4h4l2 5-2.5 1.5a11 11 0 0 0 5 5L15 13l5 2v4a2 2 0 0 1-2 2A16 16 0 0 1 3 6a2 2 0 0 1 2-2z'/>",
    "<path d='M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z'/><path d='M14 3v5h5M9 13h6M9 17h6'/>",
    "<circle cx='11' cy='11' r='7'/><path d='m20 20-3.5-3.5'/>",
    "<path d='M13 2 4 14h7l-1 8 9-12h-7z'/>",
    "<path d='M9 12l2 2 4-4'/><circle cx='12' cy='12' r='9'/>",
]


def _nav_icon_css() -> str:
    out = []
    for i, p in enumerate(ICONS):
        n = i + 1
        out.append(
            f'section[data-testid="stSidebar"] div[role="radiogroup"] > div:nth-of-type({n}) label > div:first-of-type::before,'
            f'section[data-testid="stSidebar"] div[role="radiogroup"] > label:nth-of-type({n}) > div:first-of-type::before{{background-image:{_icon(p)}}}'
        )
    return "".join(out)


NAV_ICON_CSS = _nav_icon_css()


def get_theme_vars(dark: bool = False) -> str:
    if dark:
        return """
:root, .stApp, body {
  color-scheme: dark;
  --aq-bg: #0F1218;
  --aq-card-bg: #161A22;
  --aq-card-tint: #1D222C;
  --aq-card-subtle: #161A22;
  --aq-sidebar-bg: #0B0D12;
  --aq-border: #384152;
  --aq-border-subtle: #2A303C;
  --aq-border-tint: #424B5D;
  --aq-text: #E7E9EE;
  --aq-text-body: #BEC4CF;
  --aq-text-muted: #A3A9B5;
  --aq-text-tiny: #6F7685;
  --aq-pill-bg: #1D222C;
  --aq-pill-text: #BEC4CF;
  --aq-quote-bg: #1A1F28;
  --aq-quote-text: #BEC4CF;
  --aq-table-th: #131720;
  --aq-table-border: #2A303C;
  --aq-btn-bg: #1D222C;
  --aq-btn-border: #586377;
  --aq-btn-text: #E7E9EE;
  --aq-btn-hover-border: #8B9BFF;
  --aq-btn-primary-bg: #8B9BFF;
  --aq-btn-primary-text: #0F1218;
  --aq-input-bg: #1A1F28;
  --aq-input-border: #2A303C;
  --aq-tab-bg: #1D222C;
  --aq-tab-border: #2A303C;
  --aq-tab-text: #A3A9B5;
  --aq-tab-active-bg: #8B9BFF;
  --aq-tab-active-text: #0F1218;
  --aq-radio-hover: rgba(139,155,255,0.07);
  --aq-radio-checked-bg: rgba(139,155,255,0.16);
  --aq-radio-checked-text: #8B9BFF;
  --aq-icon-filter: invert(0.78) brightness(1.1);
  --aq-icon-checked-filter: invert(0.62) sepia(1) saturate(3) hue-rotate(205deg) brightness(1.2);
  --aq-step-na-bg: #131720;
  --aq-bar-track: #252B38;
  --aq-bar-fill: #8B9BFF;
  --aq-next-bg: #1A1F28;
  --aq-risk-bg: rgba(248,113,113,0.10);
  --aq-risk-border: #F87171;
  --aq-risk-text: #FCA5A5;
  --aq-real-bg: rgba(251,191,36,0.10);
  --aq-real-border: #FBBF24;
  --aq-real-text: #FDE68A;
  --aq-zone-pos: rgba(52,211,153,0.10);
  --aq-zone-neg: rgba(248,113,113,0.10);
  --aq-axis-agent: #8B9BFF;
  --aq-cust-bubble-bg: #262F4F;
  --aq-cust-bubble-text: #E7E9EE;
  --aq-pill-good-bg: rgba(52,211,153,0.14);
  --aq-pill-good-text: #34D399;
  --aq-pill-ok-bg: rgba(52,211,153,0.09);
  --aq-pill-ok-text: #6EE7B7;
  --aq-pill-warn-bg: rgba(251,191,36,0.14);
  --aq-pill-warn-text: #FBBF24;
  --aq-pill-bad-bg: rgba(248,113,113,0.14);
  --aq-pill-bad-text: #F87171;
  --aq-pill-info-bg: rgba(96,165,250,0.14);
  --aq-pill-info-text: #60A5FA;
  --aq-accent: #8B9BFF;
}
"""
    return """
:root, .stApp, body {
  --aq-bg: #F5F4EE;
  --aq-card-bg: #FFFFFF;
  --aq-card-tint: #EEEDE3;
  --aq-card-subtle: #F6F5EF;
  --aq-sidebar-bg: #FFFFFF;
  --aq-border: #E7E5DC;
  --aq-border-subtle: #EFEEE6;
  --aq-border-tint: #E2E0D3;
  --aq-text: #111111;
  --aq-text-body: #3C3C38;
  --aq-text-muted: #6B6B66;
  --aq-text-tiny: #8A897F;
  --aq-pill-bg: #EEEDE3;
  --aq-pill-text: #3C3C38;
  --aq-quote-bg: #F6F5EF;
  --aq-quote-text: #3C3C38;
  --aq-table-th: #FBFBF8;
  --aq-table-border: #EFEEE6;
  --aq-btn-bg: #FFFFFF;
  --aq-btn-border: #DAD8CC;
  --aq-btn-text: #111111;
  --aq-btn-hover-border: #111111;
  --aq-btn-primary-bg: #111111;
  --aq-btn-primary-text: #FFFFFF;
  --aq-input-bg: #FFFFFF;
  --aq-input-border: #E1DFD3;
  --aq-tab-bg: #FFFFFF;
  --aq-tab-border: #E1DFD3;
  --aq-tab-text: #3C3C38;
  --aq-tab-active-bg: #111111;
  --aq-tab-active-text: #FFFFFF;
  --aq-radio-hover: #F5F4EE;
  --aq-radio-checked-bg: #111111;
  --aq-radio-checked-text: #FFFFFF;
  --aq-icon-filter: none;
  --aq-icon-checked-filter: invert(1);
  --aq-step-na-bg: #FBFBF8;
  --aq-bar-track: #EEEDE3;
  --aq-bar-fill: #111111;
  --aq-next-bg: #F6F5EF;
  --aq-risk-bg: #fef2f2;
  --aq-risk-border: #ef4444;
  --aq-risk-text: #991b1b;
  --aq-real-bg: #fff7ed;
  --aq-real-border: #fed7aa;
  --aq-real-text: #9a3412;
  --aq-zone-pos: #EEF6F0;
  --aq-zone-neg: #FBF0ED;
  --aq-axis-agent: #7C8BB0;
  --aq-cust-bubble-bg: #111111;
  --aq-cust-bubble-text: #FFFFFF;
  --aq-pill-good-bg: #E3F3E9;
  --aq-pill-good-text: #16723D;
  --aq-pill-ok-bg: #E8F3DD;
  --aq-pill-ok-text: #3C7A1E;
  --aq-pill-warn-bg: #FBF0D6;
  --aq-pill-warn-text: #8F6209;
  --aq-pill-bad-bg: #FBE3E0;
  --aq-pill-bad-text: #B3342F;
  --aq-pill-info-bg: #E4ECFB;
  --aq-pill-info-text: #2A55B8;
}
"""


def get_app_css(dark: bool = False) -> str:
    vars_css = get_theme_vars(dark)
    dark_overrides = ""
    if dark:
        dark_overrides = """
/* ===== DARK MODE OVERRIDES ===== */

/* Scrollbars */
* { scrollbar-color: #2A303C #0F1218; scrollbar-width: thin; }
*::-webkit-scrollbar { width:6px; height:6px; }
*::-webkit-scrollbar-track { background:#0F1218; }
*::-webkit-scrollbar-thumb { background:#2A303C; border-radius:3px; }
*::-webkit-scrollbar-thumb:hover { background:#323844; }
*::-webkit-scrollbar-corner { background:#0F1218 !important; }
*::-webkit-scrollbar-button { display:none !important; width:0 !important; height:0 !important; }
iframe { color-scheme: dark; }

/* Text */
div[data-testid="stRadio"] label, div[data-testid="stCheckbox"] label, div[data-testid="stToggle"] label,
[data-testid="stWidgetLabel"] label, [data-testid="stWidgetLabel"] p, [data-testid="stRadio"] p,
[data-testid="stCheckbox"] p, [data-testid="stToggle"] p, .stRadio label, .stCheckbox label, .stToggle label {
  color: var(--aq-text) !important;
}

/* Radios — hollow circle when unselected with 2px border (#6F7685, lighter on hover); accent ring + inner dot when selected */
div[data-testid="stRadio"] label[data-testid="stRadioOption"] > div > div:first-child,
div[data-testid="stRadio"] [data-baseweb="radio"] > div:first-child {
  background: transparent !important;
  border: 2px solid #6F7685 !important;
  box-shadow: none !important;
}
div[data-testid="stRadio"] label[data-testid="stRadioOption"]:hover > div > div:first-child,
div[data-testid="stRadio"] [data-baseweb="radio"]:hover > div:first-child {
  border-color: #A3A9B5 !important;
}
div[data-testid="stRadio"] label[data-testid="stRadioOption"][data-selected="true"] > div > div:first-child,
div[data-testid="stRadio"] label[data-testid="stRadioOption"]:has(input:checked) > div > div:first-child,
div[data-testid="stRadio"] [data-baseweb="radio"]:has(input:checked) > div:first-child {
  background: transparent !important;
  border: 2px solid var(--aq-accent) !important;
  box-shadow: none !important;
}
div[data-testid="stRadio"] label[data-testid="stRadioOption"][data-selected="true"] > div > div:first-child > div,
div[data-testid="stRadio"] label[data-testid="stRadioOption"]:has(input:checked) > div > div:first-child > div,
div[data-testid="stRadio"] [data-baseweb="radio"]:has(input:checked) > div:first-child > div {
  background: var(--aq-accent) !important;
  width: 6px !important;
  height: 6px !important;
  border-radius: 50% !important;
  border: none !important;
}

/* Toggles — off = visible grey track (#3A4150) with 1px lighter border; on = accent track; white knob */
div[data-testid="stToggle"] [role="switch"],
div[data-testid="stCheckbox"]:has(input[role="switch"]) label > div:first-of-type,
div[data-testid="stToggle"] label > div:first-of-type {
  background-color: #3A4150 !important;
  border: 1px solid #4E5666 !important;
}
div[data-testid="stToggle"] [role="switch"][aria-checked="true"],
div[data-testid="stCheckbox"]:has(input[role="switch"]:checked) label > div:first-of-type,
div[data-testid="stCheckbox"][data-selected="true"]:has(input[role="switch"]) label > div:first-of-type,
div[data-testid="stToggle"]:has(input[role="switch"]:checked) label > div:first-of-type,
div[data-testid="stToggle"][data-selected="true"] label > div:first-of-type {
  background-color: var(--aq-accent) !important;
  border-color: var(--aq-accent) !important;
}
div[data-testid="stToggle"] [role="switch"]::before,
div[data-testid="stToggle"] [role="switch"] > span,
div[data-testid="stCheckbox"]:has(input[role="switch"]) label > div:first-of-type > div,
div[data-testid="stToggle"] label > div:first-of-type > div {
  background-color: #FFFFFF !important;
}

/* Tooltip "?" icons: transparent background, light glyph (#A3A9B5), no solid grey disc */
[data-testid="stTooltipIcon"] button,
[data-testid="stTooltipHoverTarget"] button,
button[aria-label^="Help"] {
  background: transparent !important;
  background-color: transparent !important;
  border: none !important;
  box-shadow: none !important;
}
[data-testid="stTooltipIcon"] svg,
[data-testid="stTooltipHoverTarget"] svg,
button[aria-label^="Help"] svg {
  color: #A3A9B5 !important;
  fill: none !important;
  stroke: #A3A9B5 !important;
}

/* Sidebar brand: remove stray rectangle background behind brand, accent-tinted dark tile for logo */
section[data-testid="stSidebar"] .aq-brand,
section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"]:first-child > div.aq-brand,
section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"]:first-child > div {
  background: transparent !important;
  border: none !important;
}
.aq-logo {
  background: rgba(139,155,255,0.18) !important;
  border: 1px solid rgba(139,155,255,0.3) !important;
}
.aq-logo svg {
  stroke: #E7E9EE !important;
}
/* Sidebar divider */
section[data-testid="stSidebar"] hr { border-color: #2A303C !important; }

/* Selectbox and open dropdown */
div[data-testid="stSelectbox"] label, div[data-testid="stSelectbox"] label p {
  color: var(--aq-text) !important;
}
div[data-testid="stSelectbox"] div[data-baseweb="select"] > div,
div[data-testid="stSelectbox"] [data-rac=""][role="combobox"] {
  background: var(--aq-input-bg) !important;
  color: var(--aq-text) !important;
  border-color: var(--aq-input-border) !important;
}
div[data-testid="stSelectboxVirtualDropdown"],
div[data-baseweb="popover"], div[data-baseweb="popover"] > div, div[data-baseweb="menu"],
ul[data-baseweb="menu"], ul[role="listbox"] {
  background: #161A22 !important;
  background-color: #161A22 !important;
  color: var(--aq-text) !important;
  border: 1px solid var(--aq-border) !important;
  box-shadow: 0 8px 24px rgba(0,0,0,0.45) !important;
}
li[data-baseweb="menu-item"], li[role="option"],
div[data-rac=""][role="option"], div[role="option"] {
  background: #161A22 !important;
  background-color: #161A22 !important;
  color: var(--aq-text) !important;
}
li[data-baseweb="menu-item"]:hover, li[data-baseweb="menu-item"][aria-selected="true"],
li[role="option"]:hover, li[role="option"][aria-selected="true"],
div[data-rac=""][role="option"]:hover, div[data-rac=""][role="option"][data-selected="true"],
div[data-rac=""][role="option"][data-focused="true"] {
  background: rgba(139,155,255,0.14) !important;
  background-color: rgba(139,155,255,0.14) !important;
  color: #FFFFFF !important;
}
div[data-testid="stSelectboxVirtualDropdown"] *, div[data-baseweb="popover"] * {
  color: var(--aq-text) !important;
}
div[data-testid="stSelectboxVirtualDropdown"] *:hover, div[data-baseweb="popover"] *:hover {
  color: #FFFFFF !important;
}

/* Report header chips & pills */
.aq-pill {
  background: var(--aq-pill-bg) !important;
  color: var(--aq-text) !important;
  border: 1px solid var(--aq-border-subtle) !important;
}
.aq-pill.dark {
  background: rgba(139,155,255,0.18) !important;
  color: #E7E9EE !important;
  border: 1px solid rgba(139,155,255,0.38) !important;
}
.aq-pill.info {
  background: var(--aq-pill-info-bg) !important;
  color: var(--aq-pill-info-text) !important;
}
.aq-pill.good {
  background: var(--aq-pill-good-bg) !important;
  color: var(--aq-pill-good-text) !important;
}
.aq-pill.warn {
  background: var(--aq-pill-warn-bg) !important;
  color: var(--aq-pill-warn-text) !important;
}
.aq-pill.bad {
  background: var(--aq-pill-bad-bg) !important;
  color: var(--aq-pill-bad-text) !important;
}
.aq-badge {
  background: var(--aq-card-tint) !important;
  color: var(--aq-text) !important;
  border: 1px solid var(--aq-border) !important;
}

/* Text inputs, multiselect, uploader */
div[data-testid="stTextInput"] input, div[data-testid="stTextArea"] textarea, div[data-testid="stNumberInput"] input {
  background: var(--aq-input-bg) !important;
  color: var(--aq-text) !important;
  border-color: var(--aq-input-border) !important;
}
div[data-testid="stTextInput"] label, div[data-testid="stTextArea"] label {
  color: var(--aq-text) !important;
}

/* Expanders */
[data-testid="stExpander"] {
  background: var(--aq-card-bg) !important;
  border: 1px solid var(--aq-border) !important;
  color: var(--aq-text) !important;
}
[data-testid="stExpander"] summary, [data-testid="stExpander"] summary p,
[data-testid="stExpander"] summary span, [data-testid="stExpander"] summary svg {
  color: var(--aq-text) !important;
  fill: var(--aq-text) !important;
}
[data-testid="stExpander"] details, [data-testid="stExpanderDetails"],
[data-testid="stExpanderDetails"] * {
  background: var(--aq-card-bg) !important;
  color: var(--aq-text) !important;
}

/* Captions and markdown */
[data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] p,
[data-testid="stCaptionContainer"] span, .stCaption, .stCaption p {
  color: var(--aq-text-muted) !important;
}
[data-testid="stMarkdownContainer"] p, [data-testid="stMarkdownContainer"] span,
[data-testid="stMarkdownContainer"] li, [data-testid="stMarkdownContainer"] div {
  color: var(--aq-text-body) !important;
}
[data-testid="stMarkdownContainer"] h1, [data-testid="stMarkdownContainer"] h2,
[data-testid="stMarkdownContainer"] h3, [data-testid="stMarkdownContainer"] h4,
[data-testid="stMarkdownContainer"] strong, [data-testid="stMarkdownContainer"] b {
  color: var(--aq-text) !important;
}
[data-testid="stMarkdownContainer"] a { color: var(--aq-pill-info-text) !important; }
code, .stCode { background: #1A1F28 !important; color: #A3A9B5 !important; }

/* Metrics */
[data-testid="stMetric"], [data-testid="stMetric"] * { color: var(--aq-text) !important; }
[data-testid="stMetricLabel"] p, [data-testid="stMetricLabel"] span { color: var(--aq-text-muted) !important; }
[data-testid="stMetricValue"] div { color: var(--aq-text) !important; }

/* Tables */
[data-testid="stDataFrame"], [data-testid="stTable"], table {
  background: var(--aq-card-bg) !important;
  color: var(--aq-text) !important;
}
th {
  background: var(--aq-table-th) !important;
  color: var(--aq-text) !important;
  border-color: var(--aq-table-border) !important;
}
td { color: var(--aq-text-body) !important; border-color: var(--aq-table-border) !important; }

/* Buttons - secondary */
.stDownloadButton > button, .stButton > button, [data-testid="stFileUploaderDropzone"] button,
button[data-testid="baseButton-secondary"], button[data-testid="stBaseButton-secondary"],
button[kind="secondary"] {
  background: var(--aq-btn-bg) !important;
  color: var(--aq-btn-text) !important;
  border: 1px solid var(--aq-btn-border) !important;
  box-shadow: 0 1px 2px rgba(0,0,0,0.25) !important;
}
.stDownloadButton > button:hover, .stButton > button:hover, [data-testid="stFileUploaderDropzone"] button:hover,
button[data-testid="baseButton-secondary"]:hover, button[data-testid="stBaseButton-secondary"]:hover,
button[kind="secondary"]:hover {
  border-color: var(--aq-btn-hover-border) !important;
  color: #FFFFFF !important;
  background: #252B38 !important;
}
.stDownloadButton > button p, .stButton > button p, [data-testid="stFileUploaderDropzone"] button p,
button[data-testid="baseButton-secondary"] p, button[data-testid="stBaseButton-secondary"] p,
button[kind="secondary"] p { color: inherit !important; }
/* Primary button uses accent */
.stButton > button[kind="primary"], .stButton > button[data-testid="stBaseButton-primary"] {
  background: var(--aq-btn-primary-bg) !important;
  color: var(--aq-btn-primary-text) !important;
  border-color: var(--aq-btn-primary-bg) !important;
}
.stButton > button[kind="primary"] p,
.stButton > button[data-testid="stBaseButton-primary"] p {
  color: var(--aq-btn-primary-text) !important;
}
/* Disabled buttons still legible */
.stButton > button:disabled, .stDownloadButton > button:disabled {
  opacity: 0.45 !important;
  color: var(--aq-text-muted) !important;
}

/* File uploader */
[data-testid="stFileUploaderDropzone"] {
  background: var(--aq-card-bg) !important;
  border-color: var(--aq-border) !important;
}
[data-testid="stFileUploaderDropzone"] * { color: var(--aq-text) !important; }
[data-testid="stFileUploaderDropzone"] svg {
  fill: var(--aq-text) !important;
  stroke: var(--aq-text) !important;
}

/* Progress bars */
.stProgress > div > div > div > div { background: var(--aq-bar-fill) !important; }

/* Radios / selectbox labels */
.stRadio > label, .stSelectbox > label, .stCheckbox label {
  color: var(--aq-text) !important;
  font-weight: 600;
}

/* Alerts using new semantic colors */
div[data-testid="stAlert"] { border-radius: 14px; }
div[data-testid="stAlert"] * { color: inherit !important; }
div[data-testid="stAlert"]:has([data-testid="stNotificationContentInfo"]) {
  background: rgba(96,165,250,0.12) !important;
  border: 1px solid rgba(96,165,250,0.35) !important;
  color: #60A5FA !important;
}
div[data-testid="stAlert"]:has([data-testid="stNotificationContentWarning"]) {
  background: rgba(251,191,36,0.12) !important;
  border: 1px solid rgba(251,191,36,0.35) !important;
  color: #FBBF24 !important;
}
div[data-testid="stAlert"]:has([data-testid="stNotificationContentError"]) {
  background: rgba(248,113,113,0.12) !important;
  border: 1px solid rgba(248,113,113,0.35) !important;
  color: #F87171 !important;
}
div[data-testid="stAlert"]:has([data-testid="stNotificationContentSuccess"]) {
  background: rgba(52,211,153,0.12) !important;
  border: 1px solid rgba(52,211,153,0.35) !important;
  color: #34D399 !important;
}
"""
    return (
        vars_css
        + f"""
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;650;700;750&display=swap');
html,body,.stApp,[data-testid="stAppViewContainer"]{{font-family:Inter,"Segoe UI",system-ui,-apple-system,Roboto,Arial,sans-serif !important;background:var(--aq-bg) !important;color:var(--aq-text) !important}}
header[data-testid="stHeader"]{{background:transparent}}
[data-testid="stToolbar"],[data-testid="stDecoration"],#MainMenu,footer{{display:none !important;visibility:hidden}}
.block-container{{padding-top:2.2rem;padding-bottom:4rem;max-width:1260px}}
h1,h2,h3,h4,h5,h6{{letter-spacing:-.02em;color:var(--aq-text) !important}}
p,span,label{{color:inherit}}
/* sidebar */
section[data-testid="stSidebar"]{{background:var(--aq-sidebar-bg) !important;border-right:1px solid var(--aq-border) !important}}
section[data-testid="stSidebar"] .block-container,section[data-testid="stSidebar"] [data-testid="stSidebarUserContent"]{{padding-top:1.4rem}}
section[data-testid="stSidebar"] div[role="radiogroup"]{{gap:4px}}
section[data-testid="stSidebar"] label[data-testid="stRadioOption"],section[data-testid="stSidebar"] div[role="radiogroup"] > label{{padding:9px 12px;border-radius:12px;width:100%;cursor:pointer;margin:0;align-items:center;box-sizing:border-box}}
section[data-testid="stSidebar"] label[data-testid="stRadioOption"] > div,section[data-testid="stSidebar"] div[role="radiogroup"] > label > div{{display:flex;align-items:center;gap:0}}
section[data-testid="stSidebar"] label[data-testid="stRadioOption"] > div > div:first-child,section[data-testid="stSidebar"] div[role="radiogroup"] > label > div:first-child:not(:only-child){{display:none !important}}
section[data-testid="stSidebar"] label[data-testid="stRadioOption"] > div::before,section[data-testid="stSidebar"] div[role="radiogroup"] > label > div:first-of-type::before{{content:"";width:18px;height:18px;margin-right:11px;background-repeat:no-repeat;background-size:18px;flex:none;opacity:.85;display:block;filter:var(--aq-icon-filter)}}
section[data-testid="stSidebar"] label[data-testid="stRadioOption"] p,section[data-testid="stSidebar"] div[role="radiogroup"] > label p{{font-size:14.5px;font-weight:550;color:var(--aq-text-body);margin:0}}
section[data-testid="stSidebar"] label[data-testid="stRadioOption"]:hover,section[data-testid="stSidebar"] div[role="radiogroup"] > label:hover{{background:var(--aq-radio-hover)}}
section[data-testid="stSidebar"] label[data-testid="stRadioOption"][data-selected="true"],section[data-testid="stSidebar"] label[data-testid="stRadioOption"]:has(input:checked),section[data-testid="stSidebar"] div[role="radiogroup"] > label:has(input:checked){{background:var(--aq-radio-checked-bg) !important}}
section[data-testid="stSidebar"] label[data-testid="stRadioOption"][data-selected="true"] p,section[data-testid="stSidebar"] label[data-testid="stRadioOption"]:has(input:checked) p,section[data-testid="stSidebar"] div[role="radiogroup"] > label:has(input:checked) p{{color:var(--aq-radio-checked-text) !important}}
section[data-testid="stSidebar"] label[data-testid="stRadioOption"][data-selected="true"] > div::before,section[data-testid="stSidebar"] label[data-testid="stRadioOption"]:has(input:checked) > div::before,section[data-testid="stSidebar"] div[role="radiogroup"] > label:has(input:checked) > div:first-of-type::before{{filter:var(--aq-icon-checked-filter);opacity:1}}
{NAV_ICON_CSS}
/* buttons */
.stButton > button,.stDownloadButton > button{{border-radius:12px;border:1px solid var(--aq-btn-border);background:var(--aq-btn-bg);color:var(--aq-btn-text);font-weight:600;padding:.5rem 1.05rem;transition:all .12s}}
.stButton > button:hover,.stDownloadButton > button:hover{{border-color:var(--aq-btn-hover-border);color:var(--aq-btn-text);background:var(--aq-btn-bg)}}
.stButton > button[kind="primary"],.stButton > button[data-testid="stBaseButton-primary"]{{background:var(--aq-btn-primary-bg) !important;color:var(--aq-btn-primary-text) !important;border-color:var(--aq-btn-primary-bg) !important}}
.stButton > button[kind="primary"]:hover,.stButton > button[data-testid="stBaseButton-primary"]:hover{{opacity:.9}}
.stButton > button[kind="primary"] p,.stButton > button[data-testid="stBaseButton-primary"] p{{color:var(--aq-btn-primary-text) !important}}
.stTabs{{margin-top:14px}}
/* tabs as pills */
.stTabs [role="tablist"]{{gap:8px;border-bottom:none !important;flex-wrap:wrap;box-shadow:none !important}}
.stTabs [role="tablist"]::after,.stTabs [data-baseweb="tab-highlight"],.stTabs [data-baseweb="tab-border"],.stTabs .react-aria-SelectionIndicator{{display:none !important}}
.stTabs [role="tab"]{{border-radius:999px;padding:7px 18px;background:var(--aq-tab-bg) !important;border:1px solid var(--aq-tab-border) !important;height:auto;cursor:pointer;margin:0}}
.stTabs [role="tab"] p{{font-size:14px;font-weight:600;color:var(--aq-tab-text) !important;margin:0}}
.stTabs [role="tab"][aria-selected="true"]{{background:var(--aq-tab-active-bg) !important;border-color:var(--aq-tab-active-bg) !important}}
.stTabs [role="tab"][aria-selected="true"] p{{color:var(--aq-tab-active-text) !important}}
.stTabs [role="tab"]:hover{{border-color:var(--aq-tab-active-bg) !important}}
.stTabs [role="tabpanel"],.stTabs [data-baseweb="tab-panel"]{{padding-top:18px}}
/* inputs */
div[data-baseweb="select"] > div,.stTextInput input,.stTextArea textarea{{border-radius:12px !important;background:var(--aq-input-bg) !important;color:var(--aq-text) !important;border-color:var(--aq-input-border) !important}}
div[data-baseweb="popover"],div[data-baseweb="menu"],ul[data-baseweb="menu"]{{background:var(--aq-card-bg) !important;color:var(--aq-text) !important;border-color:var(--aq-border) !important}}
li[data-baseweb="menu-item"]{{background:var(--aq-card-bg) !important;color:var(--aq-text) !important}}
li[data-baseweb="menu-item"]:hover{{background:var(--aq-card-tint) !important}}
[data-testid="stFileUploaderDropzone"]{{background:var(--aq-card-bg) !important;border:1.5px dashed var(--aq-border) !important;border-radius:18px;padding:26px}}
[data-testid="stFileUploaderDropzone"] button{{border-radius:12px}}
.stProgress > div > div > div > div{{background:var(--aq-text) !important}}
[data-testid="stExpander"]{{background:var(--aq-card-bg) !important;border:1px solid var(--aq-border) !important;border-radius:16px;color:var(--aq-text) !important}}
[data-testid="stExpander"] summary{{font-weight:600;color:var(--aq-text) !important}}
[data-testid="stAlert"]{{border-radius:14px}}
.stRadio > label,.stSelectbox > label,.stCheckbox label{{font-weight:600;color:var(--aq-text) !important}}
div[data-testid="stHorizontalBlock"]{{gap:1.1rem}}
.aq-openbtn .stButton > button{{width:100%;padding:.25rem .5rem;font-size:13px;border-radius:10px;background:transparent}}
/* remove stray olive/beige highlight rectangle on radio and toggle labels after click */
label[data-testid="stRadioOption"][data-focus-visible],
div[data-testid="stCheckbox"] label[data-focus-visible],
div[data-testid="stToggle"] label[data-focus-visible],
label[data-testid="stRadioOption"]:focus-visible,
div[data-testid="stCheckbox"] label:focus-visible,
div[data-testid="stToggle"] label:focus-visible {{
  background-color: transparent !important;
  outline: 2px solid var(--aq-btn-hover-border, #111111) !important;
  outline-offset: 2px !important;
  border-radius: 8px !important;
}}
label[data-testid="stRadioOption"]:focus:not(:focus-visible),
div[data-testid="stCheckbox"] label:focus:not(:focus-visible),
div[data-testid="stToggle"] label:focus:not(:focus-visible),
label[data-testid="stRadioOption"][data-focused]:not([data-focus-visible]),
div[data-testid="stCheckbox"] label[data-focused]:not([data-focus-visible]),
div[data-testid="stToggle"] label[data-focused]:not([data-focus-visible]) {{
  background-color: transparent !important;
  outline: none !important;
  box-shadow: none !important;
}}
{dark_overrides}
"""
    )


APP_CSS = get_app_css(False)


def get_plotly_template(dark: bool = False) -> str:
    return "plotly_dark" if dark else "plotly_white"


def html(markup: str) -> None:
    st.markdown(markup, unsafe_allow_html=True)
