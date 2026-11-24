import sqlite3
import tempfile
import unittest
from pathlib import Path

from database.db import connection, initialize
from database.seed import seed_demo_patients
from src.modules.audit_logging import activity_summary, list_logs
from src.modules.authentication import login
from src.modules.backup import export_csv
from src.modules.encryption import decrypt
from src.modules.patient_management import (add_patient, anonymize_pending, erase_expired, list_patients,
                                            patient_stats, update_patient)
from src.utils.validators import patient_fields


class HospitalWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "hospital.db"
        initialize(self.path)
        self.admin = login("admin", "admin@123", self.path)
        self.doctor = login("arwaabbas", "arwa@123", self.path)
        self.receptionist = login("sarakhan", "sara@123", self.path)

    def tearDown(self):
        self.temp.cleanup()

    def test_passwords_and_access(self):
        self.assertIsNone(login("admin", "wrong", self.path))
        with connection(self.path) as db:
            stored = db.execute("SELECT password_hash FROM users WHERE username='admin'").fetchone()[0]
        self.assertNotIn("admin@123", stored)
        with self.assertRaises(PermissionError):
            export_csv(self.doctor, "patients", self.path)
        with self.assertRaises(PermissionError):
            anonymize_pending(self.receptionist, self.path)

    def test_masking_update_and_audit(self):
        patient_id = add_patient(self.receptionist, "Jane Doe", "0300-123-4592", "Asthma", self.path)
        with connection(self.path) as db:
            stored = db.execute("SELECT name,contact,diagnosis FROM patients WHERE patient_id=?",
                                (patient_id,)).fetchone()
            self.assertTrue(all(value.startswith("fernet:") for value in stored))
            self.assertEqual("Jane Doe", decrypt(stored["name"], self.path))
        self.assertEqual([], list_patients(self.doctor, self.path))
        self.assertEqual(1, anonymize_pending(self.admin, self.path))
        doctor_view = list_patients(self.doctor, self.path)[0]
        self.assertEqual("XXX-XXX-4592", doctor_view["anonymized_contact"])
        self.assertNotIn("name", doctor_view)
        self.assertNotIn("diagnosis", doctor_view)
        self.assertNotIn("Jane Doe", str(doctor_view))
        self.assertNotIn("name", list_patients(self.receptionist, self.path)[0])
        update_patient(self.receptionist, patient_id, diagnosis="New diagnosis", path=self.path)
        self.assertEqual([], list_patients(self.doctor, self.path))
        self.assertEqual(1, anonymize_pending(self.admin, self.path))
        with connection(self.path) as db:
            logs = [row[0] for row in db.execute("SELECT details FROM logs")]
            self.assertNotIn("Jane Doe", str(logs))
            self.assertNotIn("Asthma", str(logs))
            with self.assertRaises(sqlite3.DatabaseError):
                db.execute("DELETE FROM logs")
        self.assertIn(b"Jane Doe", export_csv(self.admin, "patients", self.path))

    def test_admin_write_and_legacy_migration(self):
        patient_id = add_patient(self.admin, "Admin Test", "03001234567", "Checkup", self.path)
        update_patient(self.admin, patient_id, name="Updated Test", path=self.path)
        with connection(self.path) as db:
            db.execute("UPDATE patients SET name='Legacy Name' WHERE patient_id=?", (patient_id,))
        initialize(self.path)
        with connection(self.path) as db:
            value = db.execute("SELECT name FROM patients WHERE patient_id=?", (patient_id,)).fetchone()[0]
        self.assertTrue(value.startswith("fernet:"))
        self.assertEqual("Legacy Name", decrypt(value, self.path))
        self.path.with_suffix(".key").unlink()
        with self.assertRaisesRegex(ValueError, "key is missing"):
            initialize(self.path)

    def test_validation_rejects_bad_input(self):
        for bad in (("", "0300-123-4592", "Flu"), ("Jane", "abcd", "Flu"), ("Jane", "12", "Flu")):
            with self.assertRaises(ValueError):
                patient_fields(*bad)
        with self.assertRaises(ValueError):
            add_patient(self.receptionist, "Jane", "not-a-number", "Flu", self.path)

    def test_views_can_skip_audit_entry(self):
        add_patient(self.admin, "Jane Doe", "0300-123-4592", "Asthma", self.path)
        before = len(list_logs(self.admin, self.path, log=False))
        list_patients(self.admin, self.path, log=False)
        self.assertEqual(before, len(list_logs(self.admin, self.path, log=False)))
        list_patients(self.admin, self.path)
        self.assertEqual(before + 1, len(list_logs(self.admin, self.path, log=False)))
        with self.assertRaises(PermissionError):
            list_logs(self.doctor, self.path)
        with self.assertRaises(PermissionError):
            activity_summary(self.receptionist, self.path)

    def test_demo_data_stats_and_retention(self):
        count = seed_demo_patients(self.admin, self.path)
        stats = patient_stats(self.admin, self.path)
        self.assertEqual(count, stats["total"])
        self.assertEqual(2, len(stats["expired_ids"]))
        self.assertTrue(stats["pending"] > 0 and stats["protected"] > 0)
        self.assertEqual(7, len(activity_summary(self.admin, self.path)["per_day"]))
        with self.assertRaises(ValueError):
            seed_demo_patients(self.admin, self.path)
        with self.assertRaises(PermissionError):
            erase_expired(self.receptionist, self.path)
        self.assertEqual(2, erase_expired(self.admin, self.path))
        self.assertEqual([], patient_stats(self.admin, self.path)["expired_ids"])
        with self.assertRaises(PermissionError):
            patient_stats(self.doctor, self.path)


if __name__ == "__main__":
    unittest.main()
