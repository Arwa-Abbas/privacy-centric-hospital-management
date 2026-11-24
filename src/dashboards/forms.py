"""Patient forms shared by admin and receptionist dashboards."""
import streamlit as st

from src.modules.patient_management import add_patient, update_patient


def add_form(actor, key):
    with st.form(f"add_patient_{key}", clear_on_submit=True):
        st.subheader("Register a patient")
        st.caption("Use fictional data in this coursework demo.")
        name = st.text_input("Name")
        contact = st.text_input("Contact")
        diagnosis = st.text_area("Diagnosis")
        submitted = st.form_submit_button("Register patient", type="primary")
    if submitted:
        patient_id = add_patient(actor, name, contact, diagnosis)
        st.success(f"Patient #{patient_id} registered. Anonymization is pending.")


def update_form(actor, key):
    with st.form(f"edit_patient_{key}", clear_on_submit=True):
        st.subheader("Update a patient")
        st.caption("Enter only the fields that need replacing. A new anonymization pass will be required.")
        patient_id = st.number_input("Patient ID", min_value=1, step=1)
        name = st.text_input("New name (optional)")
        contact = st.text_input("New contact (optional)")
        diagnosis = st.text_area("New diagnosis (optional)")
        submitted = st.form_submit_button("Save changes", type="primary")
    if submitted:
        update_patient(actor, int(patient_id), name, contact, diagnosis)
        st.success("Record updated. Anonymization is pending.")
