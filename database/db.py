import sqlite3
from contextlib import contextmanager

from src.config import DB_PATH


@contextmanager
def connection(path=DB_PATH):
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


def initialize(path=DB_PATH):
    schema = (DB_PATH.parent / "schema.sql").read_text(encoding="utf-8")
    with connection(path) as db:
        db.executescript(schema)
    from database.seed import seed_users
    seed_users(path)
