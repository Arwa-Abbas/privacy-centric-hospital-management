"""Doctor pages: anonymized records only."""
import pandas as pd
import streamlit as st

from src import ui
from src.modules.patient_management import list_patients

LABELS = {"patient_id": "Patient ID", "anonymized_name": "Patient (anonymized)",
          "anonymized_contact": "Contact", "anonymized_diagnosis": "Diagnosis (redacted)",
          "anonymized_at": "Anonymized at"}


def _table(rows, query=""):
    frame = pd.DataFrame(rows, columns=list(LABELS))
    if query:
        frame = frame[frame["anonymized_name"].str.contains(query, case=False, na=False)
                      | frame["patient_id"].astype(str).eq(query.strip())]
    frame["anonymized_at"] = frame["anonymized_at"].map(ui.fmt_time)
    st.dataframe(frame.rename(columns=LABELS), width="stretch", hide_index=True)


def render(actor, page):
    rows = list_patients(actor, log=ui.new_visit(page))
    if page == "Dashboard":
        a, b = st.columns(2)
        a.metric("Anonymized records available", len(rows))
        b.metric("Access level", "Anonymized only")
        with st.container(border=True):
            st.subheader("Latest anonymized records")
            st.caption("Names, contacts and diagnoses are masked. Pending records stay hidden until an admin anonymizes them.")
            _table(rows[:5])
    else:
        with st.container(border=True):
            st.subheader("Patient records")
            query = st.text_input("Search", placeholder="Search by anonymized name or patient ID",
                                  label_visibility="collapsed")
            _table(rows, query)
