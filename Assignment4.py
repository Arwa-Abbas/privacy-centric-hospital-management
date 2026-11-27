"""Assignment 4 - GDPR-compliant mini Hospital Management System implementing the CIA triad.

Single-file edition. Run with:   streamlit run Assignment4.py

Sections (in order):
  0. Setup ................ imports, configuration, demo accounts
  1. Database ............. schema (with append-only log triggers), connection helper, seeding
  2. Authentication & RBAC  PBKDF2 login, role -> permission table, `require()` gate
  3. Confidentiality ...... Fernet encryption of raw fields, HMAC masking / anonymization
  4. Integrity ............ audit logging, input validation
  5. Availability ......... CSV / encrypted backup, error handling, uptime footer
  6. GDPR ................. consent notice, retention (storage limitation)
  7. Patient operations ... add / update / anonymize / list / stats / erase (all RBAC + audited)
  8. User interface ....... theme, small HTML components
  9. Role dashboards ...... admin, doctor, receptionist pages
 10. App shell ............ consent + login gate, role-based navigation, footer

The same logic is also provided as a modular project (src/, database/); both editions share
database/hospital.db and database/hospital.key.
"""
# ============================================================================
# 0. SETUP
# ============================================================================
import base64
import csv
import hashlib
import hmac
import html
import io
import os
import re
import secrets
import sqlite3
import sys
import time
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import streamlit as st
from cryptography.fernet import Fernet, InvalidToken

ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "database" / "hospital.db"
RETENTION_DAYS = 365  # GDPR storage limitation: older records are flagged for erasure
PBKDF2_ITERATIONS = 350_000
FERNET_PREFIX = "fernet:"
PSEUDONYM_KEY = os.environ.get("HOSPITAL_PSEUDONYM_KEY", "assignment4-local-demo-pepper-change-before-real-use")

# Demo accounts from the assignment. Only salted password hashes are stored in the database.
ACCOUNTS = (("admin", "admin123", "admin"),
            ("Dr. Bob", "doc123", "doctor"),
            ("Alice_recep", "rec123", "receptionist"))

CONSENT_TEXT = ("This system processes personal health data. Data is collected only for hospital administration "
                "(purpose limitation), shown only to the roles that need it (data minimisation), "
                f"kept for at most {RETENTION_DAYS} days (storage limitation), and every action you take is "
                "recorded in an audit log. Continue only if you are authorised staff.")


def now():
    return datetime.now(timezone.utc)


def now_iso():
    return now().isoformat(timespec="seconds")


def last_days(count):
    """ISO dates for the last `count` days (UTC), oldest first, ending today."""
    today = now().date()
    return [(today - timedelta(days=offset)).isoformat() for offset in range(count - 1, -1, -1)]


# ============================================================================
# 1. DATABASE  (SQLite)
# ============================================================================
SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('admin','doctor','receptionist')),
    is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0,1))
);
CREATE TABLE IF NOT EXISTS patients (
    patient_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL CHECK (length(trim(name)) > 0),
    contact TEXT NOT NULL CHECK (length(trim(contact)) > 0),
    diagnosis TEXT NOT NULL CHECK (length(trim(diagnosis)) > 0),
    anonymized_name TEXT,
    anonymized_contact TEXT,
    anonymized_diagnosis TEXT,
    date_added TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    anonymized_at TEXT
);
CREATE TABLE IF NOT EXISTS logs (
    log_id INTEGER PRIMARY KEY,
    user_id INTEGER REFERENCES users(user_id),
    role TEXT NOT NULL,
    action TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    details TEXT NOT NULL DEFAULT ''
);
-- Integrity: the audit log is append-only; any UPDATE or DELETE is aborted by the database itself.
CREATE TRIGGER IF NOT EXISTS logs_no_update BEFORE UPDATE ON logs
BEGIN SELECT RAISE(ABORT, 'audit log is append only'); END;
CREATE TRIGGER IF NOT EXISTS logs_no_delete BEFORE DELETE ON logs
BEGIN SELECT RAISE(ABORT, 'audit log is append only'); END;
"""


@contextmanager
def connection(path=None):
    """Open the database; commit on success, roll back on any error."""
    path = Path(path or DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=5)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


# ============================================================================
# 2. AUTHENTICATION & RBAC  (who are you, and what may you do?)
# ============================================================================
PERMISSIONS = {
    "admin": {"raw_view", "masked_view", "create", "update", "anonymize", "logs", "export", "stats", "manage"},
    "doctor": {"masked_view"},
    "receptionist": {"create", "update", "status_view", "stats"},
}


def require(actor, permission):
    """Single RBAC gate: every operation below calls this before touching data."""
    if not actor or permission not in PERMISSIONS.get(actor.get("role"), set()):
        raise PermissionError(f"Permission denied: {permission}")


def hash_password(password):
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password, encoded):
    try:
        algorithm, rounds, salt, expected = encoded.split("$")
        if algorithm != "pbkdf2_sha256":
            return False
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(rounds))
        return hmac.compare_digest(actual, bytes.fromhex(expected))
    except (ValueError, TypeError):
        return False


def login(username, password, path=None):
    """Return the actor (id, username, role) for valid credentials, otherwise None. Both outcomes are logged."""
    with connection(path) as db:
        row = db.execute("SELECT user_id,username,password_hash,role FROM users WHERE username=? AND is_active=1",
                         (username.strip(),)).fetchone()
        if not row or not verify_password(password, row["password_hash"]):
            record(db, None, "LOGIN_FAILED", "Unknown username or invalid credentials")
            return None
        actor = {key: row[key] for key in ("user_id", "username", "role")}
        record(db, actor, "LOGIN_SUCCESS")
        return actor


def logout(actor, path=None):
    with connection(path) as db:
        record(db, actor, "LOGOUT")


# ============================================================================
# 3. CONFIDENTIALITY  (Fernet encryption + masking)
# ============================================================================
def _cipher(path=None):
    """Fernet key lives next to the database in hospital.key (created on first use)."""
    key_path = Path(path or DB_PATH).with_suffix(".key")
    try:
        key = key_path.read_bytes()
    except FileNotFoundError:
        key = Fernet.generate_key()
        try:
            with key_path.open("xb") as stream:
                stream.write(key)
        except FileExistsError:
            key = key_path.read_bytes()
    try:
        return Fernet(key)
    except ValueError as exc:
        raise ValueError("The local encryption key is invalid") from exc


def encrypt(value, path=None):
    return FERNET_PREFIX + _cipher(path).encrypt(value.encode("utf-8")).decode("ascii")


def decrypt(value, path=None):
    if not value.startswith(FERNET_PREFIX):
        return value  # legacy plaintext rows are migrated at start-up
    try:
        return _cipher(path).decrypt(value[len(FERNET_PREFIX):].encode("ascii")).decode("utf-8")
    except InvalidToken as exc:
        raise ValueError("Patient data could not be decrypted; check the local key") from exc


def migrate_plaintext(db, path=None):
    """Encrypt any legacy plaintext rows, preserving patient IDs and audit history."""
    rows = db.execute("SELECT patient_id,name,contact,diagnosis FROM patients").fetchall()
    key_path = Path(path or DB_PATH).with_suffix(".key")
    if rows and not key_path.exists() and any(
            row[field].startswith(FERNET_PREFIX) for row in rows for field in ("name", "contact", "diagnosis")):
        raise ValueError("Encrypted patient data exists but its local key is missing")
    for row in rows:
        values = [row[field] for field in ("name", "contact", "diagnosis")]
        if any(not value.startswith(FERNET_PREFIX) for value in values):
            encrypted = [value if value.startswith(FERNET_PREFIX) else encrypt(value, path) for value in values]
            db.execute("UPDATE patients SET name=?,contact=?,diagnosis=? WHERE patient_id=?",
                       (*encrypted, row["patient_id"]))


def _token(value, patient_id, label):
    """Stable one-way pseudonym: keyed HMAC-SHA256, so tokens cannot be reversed or guessed without the key."""
    message = f"{label}:{patient_id}:{value.strip().casefold()}".encode()
    return hmac.new(PSEUDONYM_KEY.encode(), message, hashlib.sha256).hexdigest()[:10].upper()


def mask_patient(patient_id, name, contact, diagnosis):
    """Name -> ANON_xxxx, Contact -> XXX-XXX-4592, Diagnosis -> REDACTED_xxxx."""
    digits = re.sub(r"\D", "", contact)
    return (f"ANON_{_token(name, patient_id, 'name')}",
            f"XXX-XXX-{digits[-4:]}",
            f"REDACTED_{_token(diagnosis, patient_id, 'diagnosis')}")


# ============================================================================
# 4. INTEGRITY  (audit trail + validation)
# ============================================================================
CONTACT_PATTERN = re.compile(r"^\+?[\d\s\-()]+$")


def patient_fields(name, contact, diagnosis):
    """Validate and normalise patient input before it is stored."""
    name, contact, diagnosis = (value.strip() for value in (name, contact, diagnosis))
    if not all((name, contact, diagnosis)):
        raise ValueError("Name, contact, and diagnosis are required")
    if len(name) > 120 or len(contact) > 40 or len(diagnosis) > 500:
        raise ValueError("A field exceeds the allowed length")
    if not CONTACT_PATTERN.match(contact) or len(re.sub(r"\D", "", contact)) < 4:
        raise ValueError("Contact must be a phone number with at least four digits")
    return name, contact, diagnosis


def record(db, actor, action, details=""):
    # Callers pass identifiers/counts only, never patient content or passwords.
    db.execute("INSERT INTO logs(user_id,role,action,timestamp,details) VALUES (?,?,?,?,?)",
               (actor["user_id"] if actor else None, actor["role"] if actor else "unknown",
                action, now_iso(), details))


def record_action(actor, action, details="", path=None):
    """Record an action that happens in the UI, such as consent or a download."""
    with connection(path) as db:
        record(db, actor, action, details)


def list_logs(actor, path=None, log=True):
    """Full audit log (admin only). log=False avoids counting UI re-renders as new views."""
    require(actor, "logs")
    with connection(path) as db:
        rows = [dict(row) for row in db.execute(
            "SELECT log_id,user_id,role,action,timestamp,details FROM logs ORDER BY log_id DESC")]
        if log:
            record(db, actor, "AUDIT_VIEW", f"rows={len(rows)}")
    return rows


def activity_summary(actor, path=None):
    """Aggregates for the admin dashboard: actions per day, failed logins, latest events."""
    require(actor, "logs")
    days = last_days(7)
    since = (now() - timedelta(hours=24)).isoformat(timespec="seconds")
    with connection(path) as db:
        counts = {row[0]: row[1] for row in db.execute(
            "SELECT substr(timestamp,1,10), COUNT(*) FROM logs WHERE substr(timestamp,1,10) >= ? GROUP BY 1",
            (days[0],))}
        failed = db.execute("SELECT COUNT(*) FROM logs WHERE action='LOGIN_FAILED' AND timestamp >= ?",
                            (since,)).fetchone()[0]
        recent = [dict(row) for row in db.execute(
            "SELECT action,role,timestamp FROM logs ORDER BY log_id DESC LIMIT 6")]
    return {"per_day": {day: counts.get(day, 0) for day in days}, "failed_logins": failed, "recent": recent}


# ============================================================================
# 5. AVAILABILITY  (backup / recovery, uptime)
# ============================================================================
def export_csv(actor, table, path=None):
    """CSV backup of the patients or logs table (admin only). Patient fields are decrypted."""
    require(actor, "export")
    if table not in ("patients", "logs"):
        raise ValueError("Unsupported export")
    columns = (["patient_id", "name", "contact", "diagnosis", "anonymized_name", "anonymized_contact",
                "anonymized_diagnosis", "date_added", "updated_at", "anonymized_at"]
               if table == "patients" else ["log_id", "user_id", "role", "action", "timestamp", "details"])
    with connection(path) as db:
        rows = db.execute(f"SELECT {','.join(columns)} FROM {table} ORDER BY 1").fetchall()
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(columns)
        for row in rows:
            values = dict(row)
            if table == "patients":
                for field in ("name", "contact", "diagnosis"):
                    values[field] = decrypt(values[field], path)
            writer.writerow([values[column] for column in columns])
        record(db, actor, "CSV_PREPARE", f"table={table}; count={len(rows)}")
        return output.getvalue().encode("utf-8-sig")


def export_encrypted(actor, table, path=None):
    """Same data as export_csv but Fernet-encrypted: useless without database/hospital.key."""
    return _cipher(path).encrypt(export_csv(actor, table, path))


def decrypt_backup(token, path=None):
    """Recover CSV bytes from an encrypted backup:  python Assignment4.py --decrypt patients.enc"""
    try:
        return _cipher(path).decrypt(token)
    except InvalidToken as exc:
        raise ValueError("Backup could not be decrypted; it is corrupt or the key does not match") from exc


@st.cache_resource
def process_started():
    """Start time of this server process (cached so Streamlit reruns do not reset the uptime)."""
    return time.monotonic()


# ============================================================================
# 6. GDPR  (storage limitation)
# ============================================================================
def retention_cutoff():
    return (now() - timedelta(days=RETENTION_DAYS)).isoformat(timespec="seconds")


def retention_end(date_added):
    return (datetime.fromisoformat(date_added) + timedelta(days=RETENTION_DAYS)).date().isoformat()


# ============================================================================
# 7. PATIENT OPERATIONS  (each one: RBAC check -> work -> audit entry)
# ============================================================================
STATUS_SQL = "CASE WHEN anonymized_at IS NULL THEN 'Pending' ELSE 'Anonymized' END"


def add_patient(actor, name, contact, diagnosis, path=None):
    require(actor, "create")
    name, contact, diagnosis = patient_fields(name, contact, diagnosis)
    with connection(path) as db:
        stamp = now_iso()
        cursor = db.execute("INSERT INTO patients(name,contact,diagnosis,date_added,updated_at) VALUES (?,?,?,?,?)",
                            (encrypt(name, path), encrypt(contact, path), encrypt(diagnosis, path), stamp, stamp))
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
    """Admin action: mask every record that has not been anonymized yet."""
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
    """Return only the columns the actor's role may see (this is where RBAC meets confidentiality)."""
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
    """IDs only (no personal data) so forms can offer a picker."""
    require(actor, "update")
    with connection(path) as db:
        return [row[0] for row in db.execute("SELECT patient_id FROM patients ORDER BY patient_id DESC")]


def patient_stats(actor, path=None):
    """Dashboard counts computed in SQL, so no personal data is decrypted."""
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
    """GDPR storage limitation: permanently delete records older than the retention period."""
    require(actor, "manage")
    with connection(path) as db:
        count = db.execute("DELETE FROM patients WHERE date_added < ?", (retention_cutoff(),)).rowcount
        record(db, actor, "RETENTION_ERASE", f"count={count}")
        return count


# ---- demo data -------------------------------------------------------------
# (name, contact, diagnosis, days since registration). The last two exceed the retention period.
DEMO_PATIENTS = (
    ("Maya Ahmed", "0300-111-4592", "Seasonal allergies", 0),
    ("Omar Khan", "0300-222-7284", "Routine checkup", 0),
    ("Sara Ali", "0300-333-8416", "Mild asthma", 0),
    ("Hamza Raza", "0301-444-1180", "Type 2 diabetes follow-up", 1),
    ("Ayesha Noor", "0302-555-9023", "Migraine", 1),
    ("Bilal Sheikh", "0303-666-3347", "Hypertension", 2),
    ("Zainab Malik", "0304-777-5561", "Iron deficiency", 2),
    ("Usman Tariq", "0305-888-2290", "Lower back pain", 2),
    ("Hira Siddiqui", "0306-999-7714", "Thyroid review", 3),
    ("Danish Iqbal", "0307-121-6638", "Sprained ankle", 3),
    ("Fatima Zahra", "0308-232-4405", "Anemia", 4),
    ("Rayyan Butt", "0309-343-8872", "Bronchitis", 4),
    ("Mehak Javed", "0310-454-1196", "Prenatal checkup", 5),
    ("Talha Mirza", "0311-565-7023", "Gastritis", 5),
    ("Noor Fatima", "0312-676-3351", "Eczema", 6),
    ("Ali Hassan", "0313-787-9047", "Cholesterol screening", 6),
    ("Kiran Aslam", "0314-898-2268", "Archived: knee surgery recovery", 400),
    ("Imran Yousuf", "0315-909-5534", "Archived: pneumonia", 372),
)


def seed_users(path=None):
    """Make the users table match ACCOUNTS: add missing accounts, reset drifted demo credentials,
    deactivate any other account."""
    with connection(path) as db:
        for username, password, role in ACCOUNTS:
            row = db.execute("SELECT user_id,password_hash,role,is_active FROM users WHERE username=?",
                             (username,)).fetchone()
            if row is None:
                db.execute("INSERT INTO users(username,password_hash,role) VALUES (?,?,?)",
                           (username, hash_password(password), role))
            elif row["role"] != role or not row["is_active"] or not verify_password(password, row["password_hash"]):
                db.execute("UPDATE users SET password_hash=?,role=?,is_active=1 WHERE user_id=?",
                           (hash_password(password), role, row["user_id"]))
        marks = ",".join("?" * len(ACCOUNTS))
        db.execute(f"UPDATE users SET is_active=0 WHERE username NOT IN ({marks})", [a[0] for a in ACCOUNTS])


def _insert_demo(db, path):
    """Insert fictional patients and matching back-dated audit entries; returns the patient count."""
    user_ids = {row["role"]: row["user_id"] for row in db.execute("SELECT user_id,role FROM users")}
    logs = []
    current = now()
    for index, (name, contact, diagnosis, age) in enumerate(DEMO_PATIENTS):
        added = current - timedelta(days=age, minutes=index * 7)
        stamp = added.isoformat(timespec="seconds")
        cursor = db.execute("INSERT INTO patients(name,contact,diagnosis,date_added,updated_at) VALUES (?,?,?,?,?)",
                            (encrypt(name, path), encrypt(contact, path), encrypt(diagnosis, path), stamp, stamp))
        patient_id = cursor.lastrowid
        logs.append((stamp, "receptionist", "PATIENT_CREATE", f"patient_id={patient_id}; demo_seed"))
        if age > 0:  # registrations from today stay pending so the demo shows both states
            done = (added + timedelta(hours=2)).isoformat(timespec="seconds")
            db.execute("""UPDATE patients SET anonymized_name=?,anonymized_contact=?,anonymized_diagnosis=?,
                         anonymized_at=? WHERE patient_id=?""",
                       (*mask_patient(patient_id, name, contact, diagnosis), done, patient_id))
            logs.append((done, "admin", "ANONYMIZE", "count=1; demo_seed"))
    for age in range(7):  # sign-ins and clinical reviews give the activity chart a realistic shape
        day = current - timedelta(days=age, minutes=30)
        for role in ("admin", "receptionist", "doctor"):
            logs.append((day.isoformat(timespec="seconds"), role, "LOGIN_SUCCESS", "demo_seed"))
        for view in range(2 + (age * 3) % 4):
            stamp = (day - timedelta(minutes=5 + view)).isoformat(timespec="seconds")
            logs.append((stamp, "doctor", "PATIENT_VIEW", "scope=patients; purpose=clinical review; demo_seed"))
    for stamp, role, action, details in sorted(logs):  # keep log_id order consistent with time
        db.execute("INSERT INTO logs(user_id,role,action,timestamp,details) VALUES (?,?,?,?,?)",
                   (user_ids[role], role, action, stamp, details))
    return len(DEMO_PATIENTS)


def seed_demo_if_new(path=None):
    """First-run convenience: load demo data only if no patient was ever registered."""
    with connection(path) as db:
        used = db.execute("SELECT 1 FROM logs WHERE action='PATIENT_CREATE' LIMIT 1").fetchone()
        if not used and not db.execute("SELECT 1 FROM patients LIMIT 1").fetchone():
            _insert_demo(db, path)


def seed_demo_patients(actor, path=None):
    """Admin button: load demo data into an empty patient table."""
    require(actor, "manage")
    with connection(path) as db:
        if db.execute("SELECT 1 FROM patients LIMIT 1").fetchone():
            raise ValueError("Demo data can only be loaded when there are no patients")
        count = _insert_demo(db, path)
        record(db, actor, "DEMO_DATA_LOADED", f"count={count}")
        return count


def initialize(path=None, demo=False):
    """Create tables, seed the demo accounts and encrypt any legacy plaintext (optionally load demo data)."""
    with connection(path) as db:
        db.executescript(SCHEMA)
    seed_users(path)
    with connection(path) as db:
        migrate_plaintext(db, path)
    if demo:
        seed_demo_if_new(path)


# ============================================================================
# 8. USER INTERFACE  (theme + small HTML components; no business logic)
# ============================================================================
LOGO_SVG = ('<svg xmlns="http://www.w3.org/2000/svg" width="180" height="44" viewBox="0 0 180 44">'
            '<rect x="2" y="4" width="36" height="36" rx="10" fill="#188c79"/>'
            '<path d="M20 11v22M9 22h22" stroke="#fff" stroke-width="5" stroke-linecap="round"/>'
            '<text x="48" y="30" font-family="Arial, sans-serif" font-size="22" font-weight="700" '
            'fill="#188c79">Holistic</text></svg>')
LOGO_URI = "data:image/svg+xml;base64," + base64.b64encode(LOGO_SVG.encode()).decode()

CSS = """<style>
html, body, [data-testid="stAppViewContainer"], .stApp {background:#f5f8f7 !important; color:#243b37 !important;}
[data-testid="stHeader"] {background:#f5f8f7 !important;}
[data-testid="stSidebar"] {background:#fff !important; border-right:1px solid #e4eeeb;}
[data-testid="stSidebar"] * {color:#243b37;}
[data-testid="stSidebarNavLink"] {border-radius:10px; margin-bottom:4px; padding:.5rem .7rem;}
[data-testid="stSidebarNavLink"][aria-current="page"] {background:#188c79 !important;}
[data-testid="stSidebarNavLink"][aria-current="page"] * {color:#fff !important;}
.block-container {padding:1.4rem 2rem 2rem; max-width:1420px;}
h1 {font-size:2rem !important; letter-spacing:-.03em; margin-bottom:.1rem !important;}
h3 {font-size:1.1rem !important;}
[data-testid="stCaptionContainer"] p {color:#82918e !important;}
[data-testid="stMetric"] {background:#fff; border:1px solid #e4eeeb; border-radius:14px;
  padding:16px 20px; box-shadow:0 4px 16px #17473d0a;}
[data-testid="stMetricLabel"] p {color:#738783 !important; font-size:.86rem;}
[data-testid="stMetricValue"] {color:#203e38 !important;}
[data-testid="stVerticalBlockBorderWrapper"] > div {background:#fff; border-color:#e4eeeb !important;
  border-radius:14px !important; box-shadow:0 4px 16px #17473d0a;}
[data-testid="stForm"] {background:#fff; border:1px solid #e4eeeb; border-radius:14px; padding:1.4rem;}
[data-testid="stDataFrame"] {border:1px solid #e4eeeb; border-radius:10px;}
div.stButton > button[kind="primary"] {background:#188c79 !important; border-color:#188c79 !important;}
div.stButton > button[kind="primary"] * {color:#fff !important;}
div.stButton > button, div.stDownloadButton > button {border-radius:9px;}
.item {display:flex; justify-content:space-between; align-items:center; gap:.8rem;
  padding:.65rem 0; border-bottom:1px solid #eef3f1;}
.item:last-child {border-bottom:none;}
.item b {font-size:.93rem;} .item .sub {display:block; color:#82918e; font-size:.8rem;}
.pill {padding:.18rem .7rem; border-radius:999px; font-size:.75rem; font-weight:600; white-space:nowrap;}
.pill-ok {background:#e1f4ed; color:#12705f;} .pill-warn {background:#fff3dd; color:#a15c00;}
.alert {padding:.65rem .9rem; border-radius:10px; margin-bottom:.5rem; font-size:.88rem; border:1px solid;}
.alert-ok {background:#edf8f4; border-color:#cdeadf; color:#12705f;}
.alert-warn {background:#fff8e8; border-color:#f6e2b3; color:#8a5300;}
.alert-danger {background:#fdeeee; border-color:#f5c9c9; color:#9f1f14;}
@media (max-width:900px) {.block-container {padding:1rem .8rem 1.5rem;}}
</style>"""


def new_visit(page):
    """True only when the user has just opened `page`, so views are audited once, not on every rerun."""
    changed = st.session_state.get("_page") != page
    st.session_state["_page"] = page
    return changed


def fmt_time(iso, missing="-"):
    """Format an ISO timestamp; pandas turns NULLs into NaN, so any non-string means 'no value'."""
    if not isinstance(iso, str):
        return missing
    return datetime.fromisoformat(iso).strftime("%d %b, %H:%M UTC")


def status_pill(status):
    return f'<span class="pill pill-{"ok" if status == "Anonymized" else "warn"}">{html.escape(status)}</span>'


def item_list(items):
    """Render (title, subtitle, pill_html) rows as a compact list."""
    rows = "".join(
        f'<div class="item"><div><b>{html.escape(title)}</b><span class="sub">{html.escape(sub)}</span></div>{badge}</div>'
        for title, sub, badge in items)
    st.markdown(rows or '<p style="color:#82918e">Nothing to show yet.</p>', unsafe_allow_html=True)


def alert(text, kind="ok"):
    st.markdown(f'<div class="alert alert-{kind}">{html.escape(text)}</div>', unsafe_allow_html=True)


def footer():
    """Availability: uptime and last synchronisation time on every page."""
    elapsed = int(time.monotonic() - process_started())
    st.divider()
    st.caption(f"System uptime: {elapsed // 60}m {elapsed % 60}s  ·  Last sync: {now():%H:%M:%S} UTC")


def series(per_day, name):
    """Daily counts as a date-indexed series so Streamlit orders the bars chronologically."""
    return pd.Series(list(per_day.values()), index=pd.to_datetime(list(per_day)), name=name)


# ============================================================================
# 9. ROLE DASHBOARDS
# ============================================================================
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


# ---- Admin ------------------------------------------------------------------
RAW_LABELS = {"patient_id": "Patient ID", "name": "Name", "contact": "Contact", "diagnosis": "Diagnosis",
              "date_added": "Registered", "retention_end": "Retention ends"}
MASKED_LABELS = {"patient_id": "Patient ID", "anonymized_name": "Anonymized name",
                 "anonymized_contact": "Anonymized contact", "anonymized_diagnosis": "Redacted diagnosis",
                 "anonymized_at": "Anonymized at"}
LOG_LABELS = {"log_id": "Log ID", "timestamp": "Timestamp (UTC)", "role": "Role", "user_id": "User ID",
              "action": "Action", "details": "Details"}


def admin_dashboard(actor, visit):
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
        st.bar_chart(series(activity["per_day"], "Actions"), color="#188c79", height=220)
    with right, st.container(border=True):
        st.subheader("Patients registered per day")
        st.caption("Last 7 days")
        st.bar_chart(series(stats["per_day"], "Patients"), color="#7cc9b7", height=220)
    left, right = st.columns([1.4, 1])
    with left, st.container(border=True):
        st.subheader("Recent registrations")
        st.caption("Newest records and their privacy status")
        item_list((f"Patient #{row['patient_id']}", f"Registered {fmt_time(row['date_added'])}",
                   status_pill(row["status"])) for row in stats["recent"])
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
                alert(text, kind)
        with st.container(border=True):
            st.subheader("Recent activity")
            item_list((row["action"].replace("_", " ").title(), f"{row['role'].title()} · {fmt_time(row['timestamp'])}", "")
                      for row in activity["recent"])


def admin_patients(actor, visit):
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
        frame["date_added"] = frame["date_added"].map(fmt_time)
        st.dataframe(frame[list(RAW_LABELS)].rename(columns=RAW_LABELS), width="stretch", hide_index=True)
    with masked_tab:
        st.caption("Pending records have no anonymized version yet and stay hidden from doctors.")
        frame = pd.DataFrame(rows)[list(MASKED_LABELS)]
        frame["anonymized_at"] = frame["anonymized_at"].map(lambda value: fmt_time(value, "Pending"))
        st.dataframe(frame.fillna("Pending").rename(columns=MASKED_LABELS), width="stretch", hide_index=True)


def admin_anonymization(actor, visit):
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
            frame["anonymized_at"] = frame["anonymized_at"].map(fmt_time)
            st.dataframe(frame.rename(columns=MASKED_LABELS), width="stretch", hide_index=True)


def admin_retention(actor, visit):
    expired = patient_stats(actor)["expired_ids"]
    a, b = st.columns(2)
    a.metric("Retention period", f"{RETENTION_DAYS} days")
    b.metric("Records past retention", len(expired))
    with st.container(border=True):
        st.subheader("Storage limitation")
        st.write("Personal data must not be kept longer than needed. Records older than the retention period "
                 "are listed here and can be permanently erased; each erasure is written to the audit log.")
        if not expired:
            alert("No records have exceeded the retention period.", "ok")
            return
        alert("Patient IDs past retention: " + ", ".join(f"#{value}" for value in expired), "warn")
        confirmed = st.checkbox("I have exported a backup and want to permanently erase these records.")
        if st.button("Erase expired records", type="primary", disabled=not confirmed):
            st.toast(f"Erased {erase_expired(actor)} record(s).")
            st.rerun()


def admin_audit_log(actor, visit):
    rows = list_logs(actor, log=visit)
    with st.container(border=True):
        st.subheader("Integrity audit log")
        st.caption("A timestamped, append-only record of every staff action. Rows cannot be edited or deleted.")
        actions = st.multiselect("Filter by action", sorted({row["action"] for row in rows}))
        shown = [row for row in rows if not actions or row["action"] in actions]
        frame = pd.DataFrame(shown, columns=list(LOG_LABELS))
        frame["timestamp"] = frame["timestamp"].str.replace("T", " ").str.slice(0, 19)
        st.dataframe(frame.rename(columns=LOG_LABELS), width="stretch", hide_index=True)


def admin_backups(actor, visit):
    st.warning("Plain CSV exports contain decrypted personal data. Prefer the encrypted backup; "
               "it can only be restored with this system's key file (database/hospital.key).")
    for column, (table, title) in zip(st.columns(2), (("patients", "Patient records"), ("logs", "Audit log"))):
        with column, st.container(border=True):
            st.subheader(title)
            choice = st.radio("Format", ("Encrypted backup (.enc)", "Plain CSV"), key=f"format_{table}", horizontal=True)
            encrypted = choice.startswith("Encrypted")
            if st.button(f"Prepare {title.lower()} export", key=f"prepare_{table}"):
                data = (export_encrypted if encrypted else export_csv)(actor, table)
                st.session_state[f"{table}_export"] = (data, f"{table}.{'enc' if encrypted else 'csv'}", encrypted)
            if f"{table}_export" in st.session_state:
                data, filename, was_encrypted = st.session_state[f"{table}_export"]
                st.download_button(f"Download {filename}", data, filename,
                                   "application/octet-stream" if was_encrypted else "text/csv",
                                   on_click=record_action,
                                   args=(actor, "CSV_DOWNLOAD", f"table={table}; encrypted={was_encrypted}"))
    st.caption("Restore an encrypted backup to CSV with:  python Assignment4.py --decrypt patients.enc")


ADMIN_PAGES = {
    "Dashboard": admin_dashboard,
    "Patients": admin_patients,
    "Add patient": lambda actor, visit: add_form(actor, "admin"),
    "Update patient": lambda actor, visit: update_form(actor, "admin"),
    "Anonymization": admin_anonymization,
    "Data retention": admin_retention,
    "Audit log": admin_audit_log,
    "Backups": admin_backups,
}


# ---- Doctor -----------------------------------------------------------------
DOCTOR_LABELS = {"patient_id": "Patient ID", "anonymized_name": "Patient (anonymized)",
                 "anonymized_contact": "Contact", "anonymized_diagnosis": "Diagnosis (redacted)",
                 "anonymized_at": "Anonymized at"}


def doctor_table(rows, query=""):
    frame = pd.DataFrame(rows, columns=list(DOCTOR_LABELS))
    if query:
        frame = frame[frame["anonymized_name"].str.contains(query, case=False, na=False)
                      | frame["patient_id"].astype(str).eq(query.strip())]
    frame["anonymized_at"] = frame["anonymized_at"].map(fmt_time)
    st.dataframe(frame.rename(columns=DOCTOR_LABELS), width="stretch", hide_index=True)


def doctor_page(actor, page, visit):
    rows = list_patients(actor, log=visit)
    if page == "Dashboard":
        a, b = st.columns(2)
        a.metric("Anonymized records available", len(rows))
        b.metric("Access level", "Anonymized only")
        with st.container(border=True):
            st.subheader("Latest anonymized records")
            st.caption("Names, contacts and diagnoses are masked. Pending records stay hidden until an admin anonymizes them.")
            doctor_table(rows[:5])
    else:
        with st.container(border=True):
            st.subheader("Patient records")
            query = st.text_input("Search", placeholder="Search by anonymized name or patient ID",
                                  label_visibility="collapsed")
            doctor_table(rows, query)


# ---- Receptionist -----------------------------------------------------------
def receptionist_page(actor, page, visit):
    if page == "Dashboard":
        stats = patient_stats(actor)
        a, b, c = st.columns(3)
        a.metric("Registered patients", stats["total"], f"+{stats['added_today']} today")
        b.metric("Pending anonymization", stats["pending"])
        c.metric("Anonymized", stats["protected"])
        with st.container(border=True):
            st.subheader("Recent registrations")
            st.caption("Sensitive patient fields are never displayed in this role.")
            item_list((f"Patient #{row['patient_id']}", f"Registered {fmt_time(row['date_added'])}",
                       status_pill(row["status"])) for row in stats["recent"])
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
                frame[column] = frame[column].map(fmt_time)
            st.dataframe(frame.rename(columns={"patient_id": "Patient ID", "date_added": "Registered",
                                               "updated_at": "Last updated", "status": "Status"}),
                         width="stretch", hide_index=True)


def render_role_page(actor, page):
    visit = new_visit(page)
    if actor["role"] == "admin":
        ADMIN_PAGES[page](actor, visit)
    elif actor["role"] == "doctor":
        doctor_page(actor, page, visit)
    else:
        receptionist_page(actor, page, visit)


# ============================================================================
# 10. APP SHELL  (consent + login gate, role-based navigation, footer)
# ============================================================================
# role -> [(page title, material icon)]. The first page is the landing page.
ROLE_PAGES = {
    "admin": [("Dashboard", "dashboard"), ("Patients", "groups"), ("Add patient", "person_add"),
              ("Update patient", "edit_note"), ("Anonymization", "shield"), ("Data retention", "schedule"),
              ("Audit log", "fact_check"), ("Backups", "download")],
    "doctor": [("Dashboard", "dashboard"), ("Patients", "groups")],
    "receptionist": [("Dashboard", "dashboard"), ("Register patient", "person_add"),
                     ("Update patient", "edit_note"), ("Record status", "list_alt")],
}


@st.cache_resource
def setup_database():
    """Create/seed the database once per server process instead of on every rerun."""
    initialize(demo=True)


def login_page():
    st.markdown("<style>[data-testid='stSidebar'],[data-testid='stSidebarCollapsedControl']{display:none}</style>",
                unsafe_allow_html=True)
    _, center, _ = st.columns([1, 1.2, 1])
    with center:
        st.image(LOGO_URI, width=190)
        st.title("Staff login")
        st.caption("Sign in to your secure hospital workspace.")
        if not st.session_state.get("consent"):  # GDPR: consent banner before any sign-in
            st.info(CONSENT_TEXT)
            if st.button("I understand and accept", type="primary", width="stretch"):
                try:
                    record_action(None, "CONSENT_ACCEPTED")
                except sqlite3.Error:
                    pass  # consent is still honoured for this session; the DB error surfaces at login
                st.session_state["consent"] = True
                st.rerun()
            return
        with st.form("login"):
            username = st.text_input("Username", placeholder="Enter your username")
            password = st.text_input("Password", type="password", placeholder="Enter your password")
            submitted = st.form_submit_button("Sign in", type="primary", width="stretch")
        if submitted:
            try:
                actor = login(username, password)
            except sqlite3.Error:  # Availability: a database fault must not crash the page
                st.error("Login is temporarily unavailable. Try again.")
            else:
                if actor:
                    st.session_state["actor"] = actor
                    st.rerun()
                st.error("Invalid username or password.")


def make_page(actor, title, icon, default):
    def page():
        st.title(title)
        st.caption(f"Signed in as {actor['username']} · {actor['role'].title()}")
        try:
            render_role_page(actor, title)
        except (ValueError, PermissionError) as exc:
            st.error(str(exc))
        except sqlite3.Error:
            st.error("A database operation failed. Your changes were rolled back; please try again.")
    page.__name__ = title.lower().replace(" ", "_")  # Streamlit derives each page's URL from the name
    return st.Page(page, title=title, icon=f":material/{icon}:", default=default)


def main():
    st.set_page_config(page_title="Holistic | Hospital Dashboard", page_icon="✚", layout="wide")
    st.markdown(CSS, unsafe_allow_html=True)
    try:
        setup_database()
    except sqlite3.Error:
        st.error("The database is unavailable. Check database folder access and try again.")
        st.stop()
    except ValueError as exc:
        st.error(str(exc))
        st.stop()
    actor = st.session_state.get("actor")
    if not actor:
        st.navigation([st.Page(login_page, title="Sign in")], position="hidden").run()
    else:
        st.logo(LOGO_URI, size="large")
        navigation = st.navigation([make_page(actor, title, icon, index == 0)
                                    for index, (title, icon) in enumerate(ROLE_PAGES[actor["role"]])])
        with st.sidebar:
            st.divider()
            st.markdown(f"**{actor['username']}**")
            st.caption(actor["role"].title())
            if st.button("Sign out", icon=":material/logout:", width="stretch"):
                try:
                    logout(actor)
                except sqlite3.Error:
                    pass  # never trap a user in a session because the log write failed
                st.session_state.clear()
                st.rerun()
        navigation.run()
    footer()


if len(sys.argv) == 3 and sys.argv[1] == "--decrypt":  # recovery without starting the UI
    source = Path(sys.argv[2])
    source.with_suffix(".csv").write_bytes(decrypt_backup(source.read_bytes()))
    print(f"Recovered {source.with_suffix('.csv')}")
else:
    main()
