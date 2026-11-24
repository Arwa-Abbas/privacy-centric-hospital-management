"""Shared look and feel: theme CSS and small HTML components. No business logic here."""
import html
import time
from datetime import datetime

import streamlit as st

from src.config import PROCESS_STARTED
from src.utils.dates import now

_CSS = """<style>
html, body, [data-testid="stAppViewContainer"], .stApp {background:#f5f8f7 !important; color:#243b37 !important;}
[data-testid="stHeader"] {background:#f5f8f7 !important;}
[data-testid="stSidebar"] {background:#fff !important; border-right:1px solid #e4eeeb;}
[data-testid="stSidebar"] * {color:#243b37;}
[data-testid="stSidebarNavLink"] {border-radius:10px; margin-bottom:4px; padding:.5rem .7rem;}
[data-testid="stSidebarNavLink"][aria-current="page"] {background:#188c79 !important;}
[data-testid="stSidebarNavLink"][aria-current="page"] * {color:#fff !important;}
.block-container {padding:1.4rem 2rem 2rem; max-width:1420px;}
h1 {font-size:2rem !important; letter-spacing:-.03em; margin-bottom:.1rem !important;}
h3 {font-size:1.1rem !important;}
[data-testid="stCaptionContainer"] p {color:#82918e !important;}
[data-testid="stMetric"] {background:#fff; border:1px solid #e4eeeb; border-radius:14px;
  padding:16px 20px; box-shadow:0 4px 16px #17473d0a;}
[data-testid="stMetricLabel"] p {color:#738783 !important; font-size:.86rem;}
[data-testid="stMetricValue"] {color:#203e38 !important;}
[data-testid="stVerticalBlockBorderWrapper"] > div {background:#fff; border-color:#e4eeeb !important;
  border-radius:14px !important; box-shadow:0 4px 16px #17473d0a;}
[data-testid="stForm"] {background:#fff; border:1px solid #e4eeeb; border-radius:14px; padding:1.4rem;}
[data-testid="stDataFrame"] {border:1px solid #e4eeeb; border-radius:10px;}
div.stButton > button[kind="primary"] {background:#188c79 !important; border-color:#188c79 !important;}
div.stButton > button[kind="primary"] * {color:#fff !important;}
div.stButton > button, div.stDownloadButton > button {border-radius:9px;}
.item {display:flex; justify-content:space-between; align-items:center; gap:.8rem;
  padding:.65rem 0; border-bottom:1px solid #eef3f1;}
.item:last-child {border-bottom:none;}
.item b {font-size:.93rem;} .item .sub {display:block; color:#82918e; font-size:.8rem;}
.pill {padding:.18rem .7rem; border-radius:999px; font-size:.75rem; font-weight:600; white-space:nowrap;}
.pill-ok {background:#e1f4ed; color:#12705f;} .pill-warn {background:#fff3dd; color:#a15c00;}
.pill-info {background:#e5efff; color:#2459a8;} .pill-danger {background:#fde8e8; color:#b42318;}
.alert {padding:.65rem .9rem; border-radius:10px; margin-bottom:.5rem; font-size:.88rem; border:1px solid;}
.alert-ok {background:#edf8f4; border-color:#cdeadf; color:#12705f;}
.alert-warn {background:#fff8e8; border-color:#f6e2b3; color:#8a5300;}
.alert-danger {background:#fdeeee; border-color:#f5c9c9; color:#9f1f14;}
@media (max-width:900px) {.block-container {padding:1rem .8rem 1.5rem;}}
</style>"""


def inject_theme():
    st.markdown(_CSS, unsafe_allow_html=True)


def hide_sidebar():
    st.markdown("<style>[data-testid='stSidebar'],[data-testid='stSidebarCollapsedControl']"
                "{display:none}</style>", unsafe_allow_html=True)


def page_header(title, subtitle=""):
    st.title(title)
    if subtitle:
        st.caption(subtitle)


def new_visit(page):
    """True only when the user has just opened `page`, so views are audited once, not on every rerun."""
    changed = st.session_state.get("_page") != page
    st.session_state["_page"] = page
    return changed


def fmt_time(iso, missing="-"):
    """Format an ISO timestamp; pandas turns NULLs into NaN, so any non-string means 'no value'."""
    if not isinstance(iso, str):
        return missing
    return datetime.fromisoformat(iso).strftime("%d %b, %H:%M UTC")


def pill(text, kind="info"):
    return f'<span class="pill pill-{kind}">{html.escape(text)}</span>'


def status_pill(status):
    return pill(status, "ok" if status == "Anonymized" else "warn")


def item_list(items):
    """Render (title, subtitle, pill_html) rows as a compact list."""
    rows = "".join(
        f'<div class="item"><div><b>{html.escape(title)}</b><span class="sub">{html.escape(sub)}</span></div>{badge}</div>'
        for title, sub, badge in items)
    st.markdown(rows or '<p style="color:#82918e">Nothing to show yet.</p>', unsafe_allow_html=True)


def alert(text, kind="ok"):
    st.markdown(f'<div class="alert alert-{kind}">{html.escape(text)}</div>', unsafe_allow_html=True)


def footer():
    elapsed = int(time.monotonic() - PROCESS_STARTED)
    st.divider()
    st.caption(f"System uptime: {elapsed // 60}m {elapsed % 60}s  ·  Last sync: {now():%H:%M:%S} UTC  ·  "
               "Local demonstration system")
