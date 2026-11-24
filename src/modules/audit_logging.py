"""Append-only audit trail (integrity + accountability)."""
from datetime import timedelta

from database.db import connection
from src.modules.authorization import require
from src.utils.dates import last_days, now, now_iso


def record(db, actor, action, details=""):
    # Callers pass identifiers/counts only, never patient content or passwords.
    db.execute("INSERT INTO logs(user_id,role,action,timestamp,details) VALUES (?,?,?,?,?)",
               (actor["user_id"] if actor else None, actor["role"] if actor else "unknown",
                action, now_iso(), details))


def record_action(actor, action, details="", path=None):
    """Record an action that occurs in the UI, such as consent or a download."""
    with connection(path) as db:
        record(db, actor, action, details)


def list_logs(actor, path=None, log=True):
    """Full audit log (admin). Pass log=False for re-renders so views are not double counted."""
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
