"""Streamlit presentation layer for the assignment demo."""
import sqlite3
import time
from importlib import reload

import streamlit as st

from database.db import initialize
from src.dashboards import admin, doctor, receptionist
from src.modules.authentication import login, logout
from src.modules.gdpr import NOTICE

# Streamlit reruns this entry point in the same Python process. Refresh dashboard
# modules so a running development server does not retain their old signatures.
admin = reload(admin)
doctor = reload(doctor)
receptionist = reload(receptionist)

st.set_page_config(page_title="Holistic | Hospital Dashboard", page_icon="✚", layout="wide",
                   initial_sidebar_state="expanded")
st.markdown("""<style>
html, body, [data-testid="stAppViewContainer"], .stApp {
  background: #f5f8f7 !important; color: #243b37 !important;
}
[data-testid="stHeader"] {background: #f5f8f7 !important;}
[data-testid="stSidebar"] {background: #fff !important; border-right: 1px solid #e4eeeb;}
[data-testid="stSidebar"] * {color: #243b37;}
.block-container {padding-top: 1.35rem; max-width: 1420px;}
h1, h2, h3, h4 {color: #243b37;}
h1 {font-size: 2rem !important; letter-spacing: -.035em; margin-bottom: .15rem !important;}
h3 {font-size: 1.14rem !important;}
[data-testid="stCaptionContainer"] p {color: #82918e !important;}
[data-testid="stMetric"] {background: #fff; border: 1px solid #e4eeeb;
  border-radius: 14px; padding: 18px 20px; box-shadow: 0 4px 16px #17473d0a;}
[data-testid="stMetricLabel"] p {color: #738783 !important; font-size: .86rem;}
[data-testid="stMetricValue"] {color: #203e38 !important;}
[data-testid="stVerticalBlockBorderWrapper"] > div {background: #fff; border-color: #e4eeeb !important;
  border-radius: 14px !important; box-shadow: 0 4px 16px #17473d0a;}
[data-testid="stForm"] {background: #fff; border: 1px solid #e4eeeb; border-radius: 14px;
  padding: 1.4rem; box-shadow: 0 4px 16px #17473d0a;}
[data-testid="stTextInput"] input, [data-testid="stNumberInput"] input {
  background: #fff !important; color: #243b37 !important; border-color: #dce8e4 !important;
}
[data-testid="stDataFrame"] {border: 1px solid #e4eeeb; border-radius: 10px;}
div.stButton > button[kind="primary"] {background: #188c79 !important;
  border-color: #188c79 !important; color: #fff !important;}
div.stButton > button[kind="primary"] * {color: #fff !important;}
div.stButton > button, div.stDownloadButton > button {border-radius: 9px;}
div[role="radiogroup"] label {border-radius: 9px; padding: .28rem .45rem;}
div[role="radiogroup"] label:has(input:checked) {background: #e1f4ed;}
hr {border-color: #e4eeeb;}
</style>""", unsafe_allow_html=True)

if "started" not in st.session_state:
    st.session_state.started = time.monotonic()

try:
    initialize()
except sqlite3.Error:
    st.error("The database is unavailable. Check database folder access and try again.")
    st.stop()

st.sidebar.markdown("## ✚ Holistic")
st.sidebar.caption("HOSPITAL MANAGEMENT")
st.sidebar.divider()
actor = st.session_state.get("actor")

if not actor:
    _, center, _ = st.columns([1, 1.25, 1])
    with center:
        st.markdown("### Welcome back")
        st.title("Staff login")
        st.caption("Sign in to your secure hospital workspace.")
        with st.form("login"):
            username = st.text_input("Username", placeholder="Enter your username")
            password = st.text_input("Password", type="password", placeholder="Enter your password")
            submitted = st.form_submit_button("Sign in", type="primary", width="stretch")
        if submitted:
            try:
                actor = login(username, password)
                if actor:
                    st.session_state.actor = actor
                    st.rerun()
                st.error("Invalid username or password.")
            except sqlite3.Error:
                st.error("Login is temporarily unavailable. Try again.")
        st.caption(NOTICE)
else:
    options = {"admin": ["Dashboard", "Patients", "Anonymization", "Audit log", "Backups"],
               "doctor": ["Dashboard", "Patients"],
               "receptionist": ["Dashboard", "Register patient", "Update patient", "Record status"]}[actor["role"]]
    page = st.sidebar.radio("Navigation", options, label_visibility="collapsed")
    st.sidebar.divider()
    st.sidebar.markdown(f"**{actor['username']}**")
    st.sidebar.caption(actor["role"].title())
    if st.sidebar.button("↪ Sign out", width="stretch"):
        logout(actor)
        for key in ("actor", "patient_csv", "audit_csv"):
            st.session_state.pop(key, None)
        st.rerun()
    st.title(page)
    st.caption("Welcome back. Here is what is happening with your hospital records today.")
    try:
        {"admin": admin.render, "doctor": doctor.render, "receptionist": receptionist.render}[actor["role"]](actor, page)
    except (ValueError, PermissionError) as exc:
        st.error(str(exc))
    except sqlite3.Error:
        st.error("A database operation failed. Your changes were rolled back; please try again.")

elapsed = int(time.monotonic() - st.session_state.started)
st.divider()
st.caption(f"Session uptime: {elapsed // 60}m {elapsed % 60}s  ·  Local demonstration system")
