import csv
import io

from database.db import connection
from src.config import DB_PATH
from src.modules.audit_logging import record
from src.modules.authorization import require
from src.modules.encryption import decrypt


def export_csv(actor, table, path=None):
    require(actor, "export")
    if table not in ("patients", "logs"):
        raise ValueError("Unsupported export")
    kwargs = {"path": path} if path is not None else {}
    with connection(**kwargs) as db:
        columns = (["patient_id", "name", "contact", "diagnosis", "anonymized_name",
                    "anonymized_contact", "anonymized_diagnosis", "date_added", "updated_at", "anonymized_at"]
                   if table == "patients" else ["log_id", "user_id", "role", "action", "timestamp", "details"])
        rows = db.execute(f"SELECT {','.join(columns)} FROM {table} ORDER BY 1").fetchall()
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(columns)
        for row in rows:
            values = dict(row)
            if table == "patients":
                for field in ("name", "contact", "diagnosis"):
                    values[field] = decrypt(values[field], path or DB_PATH)
            writer.writerow([values[column] for column in columns])
        record(db, actor, "CSV_PREPARE", f"table={table}; count={len(rows)}")
        return output.getvalue().encode("utf-8-sig")
