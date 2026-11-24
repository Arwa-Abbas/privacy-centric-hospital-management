import streamlit as st

from src.dashboards.forms import add_form, update_form
from src.modules.patient_management import list_patients


def render(actor, page):
    rows = list_patients(actor)
    pending = sum(row["status"] == "Pending" for row in rows)
    if page == "Dashboard":
        a, b = st.columns(2)
        a.metric("Registered patients", len(rows))
        b.metric("Pending anonymization", pending)
        with st.container(border=True):
            st.subheader("Recent registration status")
            st.caption("Sensitive patient fields are not displayed in this role.")
            st.dataframe(rows[:8], width="stretch", hide_index=True)
    elif page == "Register patient":
        add_form(actor, "receptionist")
    elif page == "Update patient":
        update_form(actor, "receptionist")
    else:
        with st.container(border=True):
            st.subheader("Record status")
            st.caption("Patient IDs and processing status only.")
            st.dataframe(rows, width="stretch", hide_index=True)
