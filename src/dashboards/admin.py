import pandas as pd
import streamlit as st

from src.modules.audit_logging import list_logs
from src.modules.audit_logging import record_action
from src.modules.backup import export_csv
from src.modules.patient_management import add_patient, anonymize_pending, list_patients
from src.dashboards.forms import add_form, update_form


def render(actor, page):
    patients = list_patients(actor)
    pending = sum(row["anonymized_at"] is None for row in patients)
    protected = len(patients) - pending
    if page == "Dashboard":
        logs = list_logs(actor)
        a, b, c, d = st.columns(4)
        a.metric("Total patients", len(patients))
        b.metric("Protected records", protected)
        c.metric("Pending review", pending)
        d.metric("Activity events", len(logs))
        left, right = st.columns([1.6, 1])
        with left:
            with st.container(border=True):
                st.subheader("Patient overview")
                st.caption("Current privacy status of registered records")
                if patients:
                    counts = pd.DataFrame({"Status": ["Protected", "Pending"],
                                           "Records": [protected, pending]}).set_index("Status")
                    st.bar_chart(counts, color="#188c79", height=230)
                else:
                    st.info("No patients yet. Register a fictional record to begin.")
                    if st.button("Load fictional demo patients", type="primary"):
                        examples = (
                            ("Maya Ahmed", "0300-111-4592", "Seasonal allergies"),
                            ("Omar Khan", "0300-222-7284", "Routine checkup"),
                            ("Sara Ali", "0300-333-8416", "Mild asthma"),
                        )
                        for name, contact, diagnosis in examples:
                            add_patient(actor, name, contact, diagnosis)
                        st.rerun()
            with st.container(border=True):
                st.subheader("Recent patients")
                columns = ["patient_id", "anonymized_name", "date_added", "anonymized_at"]
                st.dataframe([{key: row[key] for key in columns} for row in patients[:5]],
                             width="stretch", hide_index=True)
        with right:
            with st.container(border=True):
                st.subheader("Privacy alerts")
                if pending:
                    st.warning(f"{pending} record(s) await anonymization.")
                else:
                    st.success("All current records are protected.")
                st.caption("Doctors see records only after anonymization.")
            with st.container(border=True):
                st.subheader("Recent activity")
                for row in logs[:5]:
                    st.markdown(f"**{row['action'].replace('_', ' ').title()}**")
                    st.caption(f"{row['role'].title()} · {row['timestamp']}")
        with st.container(border=True):
            st.subheader("Activity by day")
            st.caption("Timestamped actions from the audit log")
            counts = pd.Series([row["timestamp"][:10] for row in logs]).value_counts().sort_index()
            if not counts.empty:
                st.bar_chart(counts.rename("Actions"), color="#188c79", height=180)
            else:
                st.info("Activity will appear after staff use the system.")
    elif page == "Patients":
        with st.container(border=True):
            st.subheader("Patient records")
            st.caption("Administrator view includes raw and anonymized fields.")
            st.dataframe(patients, width="stretch", hide_index=True)
    elif page == "Add patient":
        add_form(actor, "admin")
    elif page == "Update patient":
        update_form(actor, "admin")
    elif page == "Anonymization":
        a, b = st.columns(2)
        a.metric("Pending records", pending)
        b.metric("Protected records", protected)
        with st.container(border=True):
            st.subheader("Protect patient data")
            st.write("Mask names and contacts and redact diagnoses for the doctor view.")
            ids = ", ".join(str(row["patient_id"]) for row in patients if row["anonymized_at"] is None)
            st.caption("Pending patient IDs: " + (ids or "None"))
            if st.button("Anonymize pending records", type="primary"):
                count = anonymize_pending(actor)
                st.toast(f"Anonymized {count} record(s).")
                st.rerun()
    elif page == "Audit log":
        with st.container(border=True):
            st.subheader("Integrity audit log")
            st.caption("A timestamped, append-only record of staff actions.")
            st.dataframe(list_logs(actor), width="stretch", hide_index=True)
    elif page == "Backups":
        with st.container(border=True):
            st.subheader("Export for recovery")
            st.caption("These downloads include sensitive records. Store them securely.")
            if st.button("Prepare patient CSV"):
                st.session_state["patient_csv"] = export_csv(actor, "patients")
            if "patient_csv" in st.session_state:
                st.download_button("Download patient backup", st.session_state["patient_csv"],
                                   "patients.csv", "text/csv", on_click=record_action,
                                   args=(actor, "CSV_DOWNLOAD", "table=patients"))
            if st.button("Prepare audit CSV"):
                st.session_state["audit_csv"] = export_csv(actor, "logs")
            if "audit_csv" in st.session_state:
                st.download_button("Download audit log", st.session_state["audit_csv"],
                                   "audit_log.csv", "text/csv", on_click=record_action,
                                   args=(actor, "CSV_DOWNLOAD", "table=logs"))
