import hashlib
import hmac
import secrets

from database.db import connection
from src.modules.audit_logging import record

ITERATIONS = 350_000


def hash_password(password):
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, ITERATIONS)
    return f"pbkdf2_sha256${ITERATIONS}${salt.hex()}${digest.hex()}"


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
    kwargs = {"path": path} if path is not None else {}
    with connection(**kwargs) as db:
        row = db.execute("SELECT user_id,username,password_hash,role FROM users WHERE username=? AND is_active=1",
                         (username.strip(),)).fetchone()
        if not row or not verify_password(password, row["password_hash"]):
            record(db, None, "LOGIN_FAILED", "Unknown username or invalid credentials")
            return None
        actor = {key: row[key] for key in ("user_id", "username", "role")}
        record(db, actor, "LOGIN_SUCCESS")
        return actor


def logout(actor, path=None):
    kwargs = {"path": path} if path is not None else {}
    with connection(**kwargs) as db:
        record(db, actor, "LOGOUT")
