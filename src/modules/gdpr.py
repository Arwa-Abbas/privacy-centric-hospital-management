"""GDPR helpers: consent notice and storage-limitation (retention) rules."""
from datetime import datetime, timedelta

from src.config import RETENTION_DAYS
from src.utils.dates import now

NOTICE = ("Demo patient records are used only for authorized hospital management. "
          "Access is role restricted and actions are audited. Use fictional data for this assignment demo.")

CONSENT_TEXT = ("This system processes personal health data. Data is collected only for hospital administration "
                "(purpose limitation), shown only to the roles that need it (data minimisation), "
                f"kept for at most {RETENTION_DAYS} days (storage limitation), and every action you take is "
                "recorded in an audit log. Continue only if you are authorised staff.")


def retention_cutoff():
    """Records added before this ISO timestamp have exceeded the retention period."""
    return (now() - timedelta(days=RETENTION_DAYS)).isoformat(timespec="seconds")


def retention_end(date_added):
    return (datetime.fromisoformat(date_added) + timedelta(days=RETENTION_DAYS)).date().isoformat()
