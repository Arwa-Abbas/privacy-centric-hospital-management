"""Administrator pages: raw and anonymized data, anonymization, retention, audit log and backups."""
import pandas as pd
import streamlit as st

from database.seed import seed_demo_patients
from src import ui
from src.dashboards.forms import add_form, update_form
from src.modules.audit_logging import activity_summary, list_logs, record_action
from src.modules.backup import export_csv
from src.modules.gdpr import RETENTION_DAYS, retention_end
from src.modules.patient_management import anonymize_pending, erase_expired, list_patients, patient_stats

RAW_LABELS = {"patient_id": "Patient ID", "name": "Name", "contact": "Contact", "diagnosis": "Diagnosis",
              "date_added": "Registered", "retention_end": "Retention ends"}
MASKED_LABELS = {"patient_id": "Patient ID", "anonymized_name": "Anonymized name",
                 "anonymized_contact": "Anonymized contact", "anonymized_diagnosis": "Redacted diagnosis",
                 "anonymized_at": "Anonymized at"}
LOG_LABELS = {"log_id": "Log ID", "timestamp": "Timestamp (UTC)", "role": "Role", "user_id": "User ID",
              "action": "Action", "details": "Details"}


def _series(per_day, name):
    """Daily counts as a date-indexed series so Streamlit orders the bars chronologically."""
    return pd.Series(list(per_day.values()), index=pd.to_datetime(list(per_day)), name=name)


def _dashboard(actor, visit):
    stats, activity = patient_stats(actor), activity_summary(actor)
    if not stats["total"]:
        st.info("No patients yet. Register a fictional record or load sample data to begin.")
        if st.button("Load fictional demo patients", type="primary"):
            seed_demo_patients(actor)
            st.rerun()
        return
    percent = round(100 * stats["protected"] / stats["total"])
    a, b, c, d = st.columns(4)
    a.metric("Total patients", stats["total"], f"+{stats['added_today']} today")
    b.metric("Protected records", stats["protected"], f"{percent}% of total", delta_color="off")
    c.metric("Pending anonymization", stats["pending"])
    d.metric("Failed logins (24h)", activity["failed_logins"])

    left, right = st.columns(2)
    with left, st.container(border=True):
        st.subheader("User actions per day")
        st.caption("From the audit log, last 7 days")
        st.bar_chart(_series(activity["per_day"], "Actions"), color="#188c79", height=220)
    with right, st.container(border=True):
        st.subheader("Patients registered per day")
        st.caption("Last 7 days")
        st.bar_chart(_series(stats["per_day"], "Patients"), color="#7cc9b7", height=220)

    left, right = st.columns([1.4, 1])
    with left, st.container(border=True):
        st.subheader("Recent registrations")
        st.caption("Newest records and their privacy status")
        ui.item_list((f"Patient #{row['patient_id']}", f"Registered {ui.fmt_time(row['date_added'])}",
                      ui.status_pill(row["status"])) for row in stats["recent"])
    with right:
        with st.container(border=True):
            st.subheader("Alerts & notifications")
            alerts = []
            if stats["pending"]:
                alerts.append((f"{stats['pending']} record(s) await anonymization", "warn"))
            if stats["expired_ids"]:
                alerts.append((f"{len(stats['expired_ids'])} record(s) past the {RETENTION_DAYS}-day retention period", "warn"))
            if activity["failed_logins"]:
                alerts.append((f"{activity['failed_logins']} failed login attempt(s) in the last 24 hours", "danger"))
            for text, kind in alerts or [("All records are protected. No issues detected.", "ok")]:
                ui.alert(text, kind)
        with st.container(border=True):
            st.subheader("Recent activity")
            ui.item_list((row["action"].replace("_", " ").title(), f"{row['role'].title()} · {ui.fmt_time(row['timestamp'])}", "")
                         for row in activity["recent"])


def _patients(actor, visit):
    rows = list_patients(actor, log=visit)
    if not rows:
        st.info("No patients registered yet.")
        return
    raw_tab, masked_tab = st.tabs(["Raw records (admin only)", "Anonymized view (what doctors see)"])
    with raw_tab:
        st.caption("Contains personal data. Do not share screenshots of this tab.")
        query = st.text_input("Search", placeholder="Search by name or patient ID", label_visibility="collapsed")
        frame = pd.DataFrame(rows)
        frame["retention_end"] = frame["date_added"].map(retention_end)
        if query:
            frame = frame[frame["name"].str.contains(query, case=False) | frame["patient_id"].astype(str).eq(query.strip())]
        frame["date_added"] = frame["date_added"].map(ui.fmt_time)
        st.dataframe(frame[list(RAW_LABELS)].rename(columns=RAW_LABELS), width="stretch", hide_index=True)
    with masked_tab:
        st.caption("Pending records have no anonymized version yet and stay hidden from doctors.")
        frame = pd.DataFrame(rows)[list(MASKED_LABELS)]
        frame["anonymized_at"] = frame["anonymized_at"].map(lambda value: ui.fmt_time(value, "Pending"))
        st.dataframe(frame.fillna("Pending").rename(columns=MASKED_LABELS), width="stretch", hide_index=True)


def _anonymization(actor, visit):
    stats = patient_stats(actor)
    a, b = st.columns(2)
    a.metric("Pending records", stats["pending"])
    b.metric("Protected records", stats["protected"])
    if "anonymized_count" in st.session_state:
        st.success(f"Anonymized {st.session_state.pop('anonymized_count')} record(s).")
    with st.container(border=True):
        st.subheader("Protect patient data")
        st.write("Names become ANON_ tokens, contacts keep only their last four digits (XXX-XXX-1234) and "
                 "diagnoses are redacted. Doctors only ever see this masked version.")
        if st.button("Anonymize pending records", type="primary", disabled=not stats["pending"]):
            st.session_state["anonymized_count"] = anonymize_pending(actor)
            st.rerun()
    rows = [row for row in list_patients(actor, log=visit) if row["anonymized_at"]][:5]
    if rows:
        with st.container(border=True):
            st.subheader("Latest masked records")
            frame = pd.DataFrame(rows)[list(MASKED_LABELS)]
            frame["anonymized_at"] = frame["anonymized_at"].map(ui.fmt_time)
            st.dataframe(frame.rename(columns=MASKED_LABELS), width="stretch", hide_index=True)


def _retention(actor, visit):
    expired = patient_stats(actor)["expired_ids"]
    a, b = st.columns(2)
    a.metric("Retention period", f"{RETENTION_DAYS} days")
    b.metric("Records past retention", len(expired))
    with st.container(border=True):
        st.subheader("Storage limitation")
        st.write("Personal data must not be kept longer than needed. Records older than the retention period "
                 "are listed here and can be permanently erased; each erasure is written to the audit log.")
        if not expired:
            ui.alert("No records have exceeded the retention period.", "ok")
            return
        ui.alert("Patient IDs past retention: " + ", ".join(f"#{value}" for value in expired), "warn")
        confirmed = st.checkbox("I have exported a backup and want to permanently erase these records.")
        if st.button("Erase expired records", type="primary", disabled=not confirmed):
            st.toast(f"Erased {erase_expired(actor)} record(s).")
            st.rerun()


def _audit_log(actor, visit):
    rows = list_logs(actor, log=visit)
    with st.container(border=True):
        st.subheader("Integrity audit log")
        st.caption("A timestamped, append-only record of every staff action. Rows cannot be edited or deleted.")
        actions = st.multiselect("Filter by action", sorted({row["action"] for row in rows}))
        shown = [row for row in rows if not actions or row["action"] in actions]
        frame = pd.DataFrame(shown, columns=list(LOG_LABELS))
        frame["timestamp"] = frame["timestamp"].str.replace("T", " ").str.slice(0, 19)
        st.dataframe(frame.rename(columns=LOG_LABELS), width="stretch", hide_index=True)


def _backups(actor, visit):
    st.warning("Patient exports contain decrypted personal data. Store them securely and delete after use.")
    for column, (table, title, filename) in zip(st.columns(2), (
            ("patients", "Patient records", "patients.csv"), ("logs", "Audit log", "audit_log.csv"))):
        with column, st.container(border=True):
            st.subheader(title)
            st.caption(f"Download a CSV copy of the {title.lower()} for recovery.")
            if st.button(f"Prepare {title.lower()} CSV", key=f"prepare_{table}"):
                st.session_state[f"{table}_csv"] = export_csv(actor, table)
            if f"{table}_csv" in st.session_state:
                st.download_button(f"Download {filename}", st.session_state[f"{table}_csv"], filename, "text/csv",
                                   on_click=record_action, args=(actor, "CSV_DOWNLOAD", f"table={table}"))


PAGES = {
    "Dashboard": _dashboard,
    "Patients": _patients,
    "Add patient": lambda actor, visit: add_form(actor, "admin"),
    "Update patient": lambda actor, visit: update_form(actor, "admin"),
    "Anonymization": _anonymization,
    "Data retention": _retention,
    "Audit log": _audit_log,
    "Backups": _backups,
}


def render(actor, page):
    PAGES[page](actor, ui.new_visit(page))
