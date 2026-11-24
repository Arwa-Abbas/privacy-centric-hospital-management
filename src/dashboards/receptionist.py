"""Receptionist pages: register and edit records without reading sensitive fields."""
import pandas as pd
import streamlit as st

from src import ui
from src.dashboards.forms import add_form, update_form
from src.modules.patient_management import list_patients, patient_stats


def _dashboard(actor):
    stats = patient_stats(actor)
    a, b, c = st.columns(3)
    a.metric("Registered patients", stats["total"], f"+{stats['added_today']} today")
    b.metric("Pending anonymization", stats["pending"])
    c.metric("Anonymized", stats["protected"])
    with st.container(border=True):
        st.subheader("Recent registrations")
        st.caption("Sensitive patient fields are never displayed in this role.")
        ui.item_list((f"Patient #{row['patient_id']}", f"Registered {ui.fmt_time(row['date_added'])}",
                      ui.status_pill(row["status"])) for row in stats["recent"])


def render(actor, page):
    visit = ui.new_visit(page)
    if page == "Dashboard":
        _dashboard(actor)
    elif page == "Register patient":
        add_form(actor, "receptionist")
    elif page == "Update patient":
        update_form(actor, "receptionist")
    else:
        with st.container(border=True):
            st.subheader("Record status")
            st.caption("Patient IDs and processing status only.")
            rows = list_patients(actor, log=visit)
            if not rows:
                st.info("No patients registered yet.")
                return
            frame = pd.DataFrame(rows)
            for column in ("date_added", "updated_at"):
                frame[column] = frame[column].map(ui.fmt_time)
            st.dataframe(frame.rename(columns={"patient_id": "Patient ID", "date_added": "Registered",
                                               "updated_at": "Last updated", "status": "Status"}),
                         width="stretch", hide_index=True)
