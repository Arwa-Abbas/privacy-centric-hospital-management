import streamlit as st

from src.modules.patient_management import list_patients


def render(actor, page):
    rows = list_patients(actor)
    st.metric("Anonymized patient records", len(rows))
    with st.container(border=True):
        st.subheader("Protected patient overview" if page == "Dashboard" else "Patient records")
        st.caption("Only anonymized records appear here. Pending records remain hidden.")
        st.dataframe(rows, width="stretch", hide_index=True)
