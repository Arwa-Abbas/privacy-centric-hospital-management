import streamlit as st

from src.modules.patient_management import add_patient, list_patients, update_patient


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
        with st.form("add_patient", clear_on_submit=True):
            st.subheader("Register a patient")
            name = st.text_input("Name")
            contact = st.text_input("Contact")
            diagnosis = st.text_input("Diagnosis")
            if st.form_submit_button("Register patient", type="primary"):
                st.success(f"Patient #{add_patient(actor, name, contact, diagnosis)} registered.")
    elif page == "Update patient":
        with st.form("edit_patient", clear_on_submit=True):
            st.subheader("Update a patient")
            st.caption("Enter replacement values. Existing sensitive values are never shown here.")
            patient_id = st.number_input("Patient ID", min_value=1, step=1)
            name = st.text_input("New name (optional)")
            contact = st.text_input("New contact (optional)")
            diagnosis = st.text_input("New diagnosis (optional)")
            if st.form_submit_button("Save changes", type="primary"):
                update_patient(actor, int(patient_id), name, contact, diagnosis)
                st.success("Record updated. Anonymization is pending admin review.")
    else:
        with st.container(border=True):
            st.subheader("Record status")
            st.caption("Patient IDs and processing status only.")
            st.dataframe(rows, width="stretch", hide_index=True)
