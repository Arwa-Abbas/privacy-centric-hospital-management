from datetime import datetime, timezone

from database.db import connection
from src.modules.authorization import require


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def record(db, actor, action, details=""):
    # Callers pass identifiers/counts only, never patient content or passwords.
    db.execute("INSERT INTO logs(user_id,role,action,timestamp,details) VALUES (?,?,?,?,?)",
               (actor["user_id"] if actor else None, actor["role"] if actor else "unknown",
                action, utc_now(), details))


def list_logs(actor, path=None):
    require(actor, "logs")
    kwargs = {"path": path} if path is not None else {}
    with connection(**kwargs) as db:
        rows = [dict(row) for row in db.execute(
            "SELECT log_id,user_id,role,action,timestamp,details FROM logs ORDER BY log_id DESC")]
        record(db, actor, "AUDIT_VIEW", f"rows={len(rows)}")
        return rows


def record_action(actor, action, details="", path=None):
    """Record an action that occurs in the UI, such as clicking a download."""
    kwargs = {"path": path} if path is not None else {}
    with connection(**kwargs) as db:
        record(db, actor, action, details)
