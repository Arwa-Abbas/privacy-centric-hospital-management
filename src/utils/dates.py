from datetime import datetime, timedelta, timezone


def now():
    return datetime.now(timezone.utc)


def now_iso():
    return now().isoformat(timespec="seconds")


def last_days(count):
    """ISO dates for the last `count` days (UTC), oldest first, ending today."""
    today = now().date()
    return [(today - timedelta(days=offset)).isoformat() for offset in range(count - 1, -1, -1)]
