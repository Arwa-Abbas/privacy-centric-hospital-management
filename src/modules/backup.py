import csv
import io

from database.db import connection
from src.modules.audit_logging import record
from src.modules.authorization import require
from src.modules.encryption import decrypt, decrypt_bytes, encrypt_bytes


def export_csv(actor, table, path=None):
    """Plain CSV (patient fields decrypted). Prefer export_encrypted for anything stored or shared."""
    require(actor, "export")
    if table not in ("patients", "logs"):
        raise ValueError("Unsupported export")
    with connection(path) as db:
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
                    values[field] = decrypt(values[field], path)
            writer.writerow([values[column] for column in columns])
        record(db, actor, "CSV_PREPARE", f"table={table}; count={len(rows)}")
        return output.getvalue().encode("utf-8-sig")


def export_encrypted(actor, table, path=None):
    """Same data as export_csv, but Fernet-encrypted so the file is useless without the key."""
    return encrypt_bytes(export_csv(actor, table, path), path)


def decrypt_backup(token, path=None):
    """Recover the CSV bytes from an encrypted backup (needs database/hospital.key)."""
    return decrypt_bytes(token, path)


if __name__ == "__main__":  # python -m src.modules.backup patients.enc  ->  patients.csv
    import sys
    from pathlib import Path
    source = Path(sys.argv[1])
    source.with_suffix(".csv").write_bytes(decrypt_backup(source.read_bytes()))
    print(f"Recovered {source.with_suffix('.csv')}")
