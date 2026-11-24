"""Local Fernet protection for raw patient fields."""
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

from src.config import DB_PATH

PREFIX = "fernet:"


def _cipher(path=None):
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
    return PREFIX + _cipher(path).encrypt(value.encode("utf-8")).decode("ascii")


def decrypt(value, path=None):
    if not value.startswith(PREFIX):
        return value  # Existing plaintext records are migrated at initialization.
    try:
        return _cipher(path).decrypt(value[len(PREFIX):].encode("ascii")).decode("utf-8")
    except InvalidToken as exc:
        raise ValueError("Patient data could not be decrypted; check the local key") from exc


def migrate_plaintext(db, path=None):
    """Upgrade legacy plaintext rows, preserving patient IDs and audit history."""
    rows = db.execute("SELECT patient_id,name,contact,diagnosis FROM patients").fetchall()
    key_path = Path(path or DB_PATH).with_suffix(".key")
    if rows and not key_path.exists() and any(
        row[field].startswith(PREFIX) for row in rows for field in ("name", "contact", "diagnosis")
    ):
        raise ValueError("Encrypted patient data exists but its local key is missing")
    for row in rows:
        values = [row[field] for field in ("name", "contact", "diagnosis")]
        if any(not value.startswith(PREFIX) for value in values):
            encrypted = [value if value.startswith(PREFIX) else encrypt(value, path) for value in values]
            db.execute("UPDATE patients SET name=?,contact=?,diagnosis=? WHERE patient_id=?",
                       (*encrypted, row["patient_id"]))
