"""Patient operations. Each function enforces RBAC and writes an audit entry."""
from database.db import connection
from src.modules.anonymization import mask_patient
from src.modules.audit_logging import record
from src.modules.authorization import require
from src.modules.encryption import decrypt, encrypt
from src.modules.gdpr import retention_cutoff
from src.utils.dates import last_days, now_iso
from src.utils.validators import patient_fields

STATUS_SQL = "CASE WHEN anonymized_at IS NULL THEN 'Pending' ELSE 'Anonymized' END"


def add_patient(actor, name, contact, diagnosis, path=None):
    require(actor, "create")
    name, contact, diagnosis = patient_fields(name, contact, diagnosis)
    with connection(path) as db:
        now = now_iso()
        cursor = db.execute("INSERT INTO patients(name,contact,diagnosis,date_added,updated_at) VALUES (?,?,?,?,?)",
                            (encrypt(name, path), encrypt(contact, path), encrypt(diagnosis, path), now, now))
        record(db, actor, "PATIENT_CREATE", f"patient_id={cursor.lastrowid}")
        return cursor.lastrowid


def update_patient(actor, patient_id, name="", contact="", diagnosis="", path=None):
    """Replace only the supplied fields; the record returns to 'pending anonymization'."""
    require(actor, "update")
    if not any((name.strip(), contact.strip(), diagnosis.strip())):
        raise ValueError("Enter at least one replacement value")
    with connection(path) as db:
        row = db.execute("SELECT name,contact,diagnosis FROM patients WHERE patient_id=?", (patient_id,)).fetchone()
        if row is None:
            raise ValueError("Patient ID was not found")
        values = patient_fields(name.strip() or decrypt(row["name"], path),
                                contact.strip() or decrypt(row["contact"], path),
                                diagnosis.strip() or decrypt(row["diagnosis"], path))
        encrypted = tuple(encrypt(value, path) for value in values)
        db.execute("""UPDATE patients SET name=?,contact=?,diagnosis=?,updated_at=?,
                     anonymized_name=NULL,anonymized_contact=NULL,anonymized_diagnosis=NULL,
                     anonymized_at=NULL WHERE patient_id=?""", (*encrypted, now_iso(), patient_id))
        record(db, actor, "PATIENT_UPDATE", f"patient_id={patient_id}; anonymization=pending")


def anonymize_pending(actor, path=None):
    require(actor, "anonymize")
    with connection(path) as db:
        rows = db.execute("SELECT patient_id,name,contact,diagnosis FROM patients WHERE anonymized_at IS NULL").fetchall()
        for row in rows:
            masked = mask_patient(row["patient_id"], decrypt(row["name"], path),
                                  decrypt(row["contact"], path), decrypt(row["diagnosis"], path))
            db.execute("""UPDATE patients SET anonymized_name=?,anonymized_contact=?,
                         anonymized_diagnosis=?,anonymized_at=? WHERE patient_id=?""",
                       (*masked, now_iso(), row["patient_id"]))
        record(db, actor, "ANONYMIZE", f"count={len(rows)}")
        return len(rows)


def list_patients(actor, path=None, log=True):
    """Return only the columns the actor's role may see. log=False skips the PATIENT_VIEW entry."""
    role = actor.get("role") if actor else None
    if role == "admin":
        require(actor, "raw_view")
        sql = """SELECT patient_id,name,contact,diagnosis,anonymized_name,
                 anonymized_contact,anonymized_diagnosis,date_added,updated_at,anonymized_at
                 FROM patients ORDER BY patient_id DESC"""
    elif role == "doctor":
        require(actor, "masked_view")
        sql = """SELECT patient_id,anonymized_name,anonymized_contact,
                 anonymized_diagnosis,anonymized_at FROM patients
                 WHERE anonymized_at IS NOT NULL ORDER BY patient_id DESC"""
    else:
        require(actor, "status_view")
        sql = f"""SELECT patient_id,date_added,updated_at,{STATUS_SQL} AS status
                 FROM patients ORDER BY patient_id DESC"""
    with connection(path) as db:
        rows = [dict(row) for row in db.execute(sql)]
        if role == "admin":
            for row in rows:
                for field in ("name", "contact", "diagnosis"):
                    row[field] = decrypt(row[field], path)
        if log:
            purpose = {"admin": "record administration", "doctor": "clinical review",
                       "receptionist": "registration status"}[role]
            record(db, actor, "PATIENT_VIEW", f"scope=patients; purpose={purpose}; count={len(rows)}")
        return rows


def patient_ids(actor, path=None):
    """IDs only (no personal data) so forms can offer a picker instead of free-typed numbers."""
    require(actor, "update")
    with connection(path) as db:
        return [row[0] for row in db.execute("SELECT patient_id FROM patients ORDER BY patient_id DESC")]


def patient_stats(actor, path=None):
    """Counts for dashboards, computed in SQL so no personal data is decrypted."""
    require(actor, "stats")
    days = last_days(7)
    with connection(path) as db:
        total, pending = db.execute(
            "SELECT COUNT(*), COALESCE(SUM(anonymized_at IS NULL),0) FROM patients").fetchone()
        expired = [row[0] for row in db.execute(
            "SELECT patient_id FROM patients WHERE date_added < ? ORDER BY patient_id", (retention_cutoff(),))]
        counts = {row[0]: row[1] for row in db.execute(
            "SELECT substr(date_added,1,10), COUNT(*) FROM patients WHERE substr(date_added,1,10) >= ? GROUP BY 1",
            (days[0],))}
        recent = [dict(row) for row in db.execute(
            f"SELECT patient_id,date_added,{STATUS_SQL} AS status FROM patients ORDER BY date_added DESC LIMIT 6")]
    per_day = {day: counts.get(day, 0) for day in days}
    return {"total": total, "pending": pending, "protected": total - pending, "expired_ids": expired,
            "per_day": per_day, "added_today": per_day[days[-1]], "recent": recent}


def erase_expired(actor, path=None):
    """GDPR storage limitation: permanently delete records past the retention period."""
    require(actor, "manage")
    with connection(path) as db:
        count = db.execute("DELETE FROM patients WHERE date_added < ?", (retention_cutoff(),)).rowcount
        record(db, actor, "RETENTION_ERASE", f"count={count}")
        return count
