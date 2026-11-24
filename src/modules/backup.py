import csv
import io

from database.db import connection
from src.modules.audit_logging import record
from src.modules.authorization import require


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
        writer.writerows(tuple(row) for row in rows)
        record(db, actor, "CSV_EXPORT", f"table={table}; count={len(rows)}")
        return output.getvalue().encode("utf-8-sig")
