from database.db import connection
from src.modules.authentication import hash_password


def seed_users(path):
    # Demonstration credentials from the assignment; never persist plaintext.
    accounts = (("admin", "admin123", "admin"),
                ("Dr. Bob", "doc123", "doctor"),
                ("Alice_recep", "rec123", "receptionist"))
    with connection(path) as db:
        for username, password, role in accounts:
            if not db.execute("SELECT 1 FROM users WHERE username=?", (username,)).fetchone():
                db.execute("INSERT INTO users(username,password_hash,role) VALUES (?,?,?)",
                           (username, hash_password(password), role))
