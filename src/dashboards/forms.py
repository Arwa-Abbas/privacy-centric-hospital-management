"""Patient forms shared by the admin and receptionist dashboards."""
import streamlit as st

from src.modules.patient_management import add_patient, patient_ids, update_patient


def add_form(actor, key):
    with st.form(f"add_patient_{key}"):
        st.subheader("Register a patient")
        st.caption("Use fictional data in this coursework demo. Details are encrypted as soon as you save.")
        name = st.text_input("Full name", placeholder="e.g. Maya Ahmed")
        contact = st.text_input("Contact number", placeholder="e.g. 0300-111-4592")
        diagnosis = st.text_area("Diagnosis", placeholder="e.g. Seasonal allergies")
        submitted = st.form_submit_button("Register patient", type="primary")
    if submitted:
        try:
            patient_id = add_patient(actor, name, contact, diagnosis)
        except ValueError as exc:
            st.error(str(exc))
        else:
            st.success(f"Patient #{patient_id} registered. Anonymization is pending.")


def update_form(actor, key):
    ids = patient_ids(actor)
    if not ids:
        st.info("No patients registered yet.")
        return
    with st.form(f"edit_patient_{key}"):
        st.subheader("Update a patient")
        st.caption("Fill in only the fields that change; blank fields keep their current value. "
                   "The record goes back to 'pending' until it is anonymized again.")
        patient_id = st.selectbox("Patient", ids, format_func=lambda value: f"Patient #{value}")
        name = st.text_input("New name", placeholder="Leave blank to keep")
        contact = st.text_input("New contact number", placeholder="Leave blank to keep")
        diagnosis = st.text_area("New diagnosis", placeholder="Leave blank to keep")
        submitted = st.form_submit_button("Save changes", type="primary")
    if submitted:
        try:
            update_patient(actor, patient_id, name, contact, diagnosis)
        except ValueError as exc:
            st.error(str(exc))
        else:
            st.success(f"Patient #{patient_id} updated. Anonymization is pending.")
