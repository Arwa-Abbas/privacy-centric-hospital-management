from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "database" / "hospital.db"
ROLES = ("admin", "doctor", "receptionist")
DEMO_PEPPER = "assignment4-local-demo-pepper-change-before-real-use"
