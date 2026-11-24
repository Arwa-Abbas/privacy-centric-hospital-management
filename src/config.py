from pathlib import Path
import time

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "database" / "hospital.db"
ROLES = ("admin", "doctor", "receptionist")
RETENTION_DAYS = 365  # GDPR storage limitation: records older than this are flagged for erasure
DEMO_PEPPER = "assignment4-local-demo-pepper-change-before-real-use"
PROCESS_STARTED = time.monotonic()
