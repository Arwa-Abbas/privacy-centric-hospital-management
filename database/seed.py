"""Demo data: the three assignment accounts plus fictional patients and back-dated activity."""
from datetime import timedelta

from database.db import connection
from src.modules.anonymization import mask_patient
from src.modules.audit_logging import record
from src.modules.authentication import hash_password, verify_password
from src.modules.authorization import require
from src.modules.encryption import encrypt
from src.utils.dates import now

ACCOUNTS = (("admin", "admin123", "admin"),
            ("Dr. Bob", "doc123", "doctor"),
            ("Alice_recep", "rec123", "receptionist"))

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
    """Make the users table match ACCOUNTS: add missing accounts, reset drifted demo
    credentials and deactivate any other account. Only salted hashes are stored."""
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
