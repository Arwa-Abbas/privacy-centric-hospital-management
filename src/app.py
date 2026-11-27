"""Streamlit entry layer: theme, consent + login gate, role-based navigation and footer."""
import sqlite3

import streamlit as st

from database.db import initialize
from src import ui
from src.config import ROOT
from src.dashboards import admin, doctor, receptionist
from src.modules.audit_logging import record_action
from src.modules.authentication import login, logout
from src.modules.gdpr import CONSENT_TEXT

# role -> (dashboard module, [(page title, icon), ...]). The first page is the landing page.
ROLE_PAGES = {
    "admin": (admin, [("Dashboard", "dashboard"), ("Patients", "groups"), ("Add patient", "person_add"),
                      ("Update patient", "edit_note"), ("Anonymization", "shield"), ("Data retention", "schedule"),
                      ("Audit log", "fact_check"), ("Backups", "download")]),
    "doctor": (doctor, [("Dashboard", "dashboard"), ("Patients", "groups")]),
    "receptionist": (receptionist, [("Dashboard", "dashboard"), ("Register patient", "person_add"),
                                    ("Update patient", "edit_note"), ("Record status", "list_alt")]),
}

st.set_page_config(page_title="Holistic | Hospital Dashboard", page_icon="✚", layout="wide")
ui.inject_theme()

@st.cache_resource
def setup_database():
    """Create/seed the database once per server process instead of on every rerun."""
    initialize(demo=True)


try:
    setup_database()
except sqlite3.Error:
    st.error("The database is unavailable. Check database folder access and try again.")
    st.stop()
except ValueError as exc:
    st.error(str(exc))
    st.stop()


def login_page():
    ui.hide_sidebar()
    _, center, _ = st.columns([1, 1.2, 1])
    with center:
        st.image(str(ROOT / "src" / "assets" / "logo.svg"), width=190)
        st.title("Staff login")
        st.caption("Sign in to your secure hospital workspace.")
        if not st.session_state.get("consent"):
            st.info(CONSENT_TEXT)
            if st.button("I understand and accept", type="primary", width="stretch"):
                try:
                    record_action(None, "CONSENT_ACCEPTED")
                except sqlite3.Error:
                    pass  # consent is still honoured for this session; the DB error surfaces at login
                st.session_state["consent"] = True
                st.rerun()
            return
        with st.form("login"):
            username = st.text_input("Username", placeholder="Enter your username")
            password = st.text_input("Password", type="password", placeholder="Enter your password")
            submitted = st.form_submit_button("Sign in", type="primary", width="stretch")
        if submitted:
            try:
                actor = login(username, password)
            except sqlite3.Error:
                st.error("Login is temporarily unavailable. Try again.")
            else:
                if actor:
                    st.session_state["actor"] = actor
                    st.rerun()
                st.error("Invalid username or password.")


def make_page(actor, module, title, icon, default):
    def page():
        ui.page_header(title, f"Signed in as {actor['username']} · {actor['role'].title()}")
        try:
            module.render(actor, title)
        except (ValueError, PermissionError) as exc:
            st.error(str(exc))
        except sqlite3.Error:
            st.error("A database operation failed. Your changes were rolled back; please try again.")
    page.__name__ = title.lower().replace(" ", "_")  # Streamlit derives each page's URL from the name
    return st.Page(page, title=title, icon=f":material/{icon}:", default=default)


actor = st.session_state.get("actor")
if not actor:
    st.navigation([st.Page(login_page, title="Sign in")], position="hidden").run()
else:
    module, pages = ROLE_PAGES[actor["role"]]
    st.logo(str(ROOT / "src" / "assets" / "logo.svg"), size="large")
    navigation = st.navigation([make_page(actor, module, title, icon, index == 0)
                                for index, (title, icon) in enumerate(pages)])
    with st.sidebar:
        st.divider()
        st.markdown(f"**{actor['username']}**")
        st.caption(actor["role"].title())
        if st.button("Sign out", icon=":material/logout:", width="stretch"):
            try:
                logout(actor)
            except sqlite3.Error:
                pass  # never trap a user in a session because the log write failed
            st.session_state.clear()
            st.rerun()
    navigation.run()
ui.footer()
