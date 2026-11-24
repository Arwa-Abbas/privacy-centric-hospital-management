import sqlite3
from contextlib import contextmanager
from pathlib import Path

from src.config import DB_PATH

SCHEMA_PATH = Path(__file__).with_name("schema.sql")


@contextmanager
def connection(path=None):
    """Open the database, commit on success and roll back on any error."""
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


def initialize(path=None, demo=False):
    """Create tables, seed the three demo accounts and encrypt any legacy plaintext.

    With demo=True, fictional patients are loaded once into a never-used database.
    """
    from database.seed import seed_demo_if_new, seed_users
    from src.modules.encryption import migrate_plaintext
    with connection(path) as db:
        db.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    seed_users(path)
    with connection(path) as db:
        migrate_plaintext(db, path)
    if demo:
        seed_demo_if_new(path)
