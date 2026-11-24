from database.db import connection
from src.modules.anonymization import mask_patient
from src.modules.audit_logging import record, utc_now
from src.modules.authorization import require
from src.utils.validators import patient_fields


def _connect(path):
    return connection(**({"path": path} if path is not None else {}))


def add_patient(actor, name, contact, diagnosis, path=None):
    require(actor, "create")
    name, contact, diagnosis = patient_fields(name, contact, diagnosis)
    with _connect(path) as db:
        now = utc_now()
        cursor = db.execute("INSERT INTO patients(name,contact,diagnosis,date_added,updated_at) VALUES (?,?,?,?,?)",
                            (name, contact, diagnosis, now, now))
        record(db, actor, "PATIENT_CREATE", f"patient_id={cursor.lastrowid}")
        return cursor.lastrowid


def update_patient(actor, patient_id, name="", contact="", diagnosis="", path=None):
    require(actor, "update")
    if not any((name.strip(), contact.strip(), diagnosis.strip())):
        raise ValueError("Enter at least one replacement value")
    with _connect(path) as db:
        row = db.execute("SELECT name,contact,diagnosis FROM patients WHERE patient_id=?", (patient_id,)).fetchone()
        if row is None:
            raise ValueError("Patient ID was not found")
        values = patient_fields(name.strip() or row["name"], contact.strip() or row["contact"],
                                diagnosis.strip() or row["diagnosis"])
        db.execute("""UPDATE patients SET name=?,contact=?,diagnosis=?,updated_at=?,
                     anonymized_name=NULL,anonymized_contact=NULL,anonymized_diagnosis=NULL,
                     anonymized_at=NULL WHERE patient_id=?""", (*values, utc_now(), patient_id))
        record(db, actor, "PATIENT_UPDATE", f"patient_id={patient_id}; anonymization=pending")


def anonymize_pending(actor, path=None):
    require(actor, "anonymize")
    with _connect(path) as db:
        rows = db.execute("SELECT patient_id,name,contact,diagnosis FROM patients WHERE anonymized_at IS NULL").fetchall()
        for row in rows:
            masked = mask_patient(row["patient_id"], row["name"], row["contact"], row["diagnosis"])
            db.execute("""UPDATE patients SET anonymized_name=?,anonymized_contact=?,
                         anonymized_diagnosis=?,anonymized_at=? WHERE patient_id=?""",
                       (*masked, utc_now(), row["patient_id"]))
        record(db, actor, "ANONYMIZE", f"count={len(rows)}")
        return len(rows)


def list_patients(actor, path=None):
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
        sql = """SELECT patient_id,date_added,updated_at,
                 CASE WHEN anonymized_at IS NULL THEN 'Pending' ELSE 'Anonymized' END AS status
                 FROM patients ORDER BY patient_id DESC"""
    with _connect(path) as db:
        rows = [dict(row) for row in db.execute(sql)]
        record(db, actor, "PATIENT_VIEW", f"count={len(rows)}")
        return rows
