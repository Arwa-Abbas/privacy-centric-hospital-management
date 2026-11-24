import sqlite3
import tempfile
import unittest
from pathlib import Path

from database.db import connection, initialize
from src.modules.authentication import login
from src.modules.backup import export_csv
from src.modules.patient_management import add_patient, anonymize_pending, list_patients, update_patient


class HospitalWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "hospital.db"
        initialize(self.path)
        self.admin = login("admin", "admin123", self.path)
        self.doctor = login("Dr. Bob", "doc123", self.path)
        self.receptionist = login("Alice_recep", "rec123", self.path)

    def tearDown(self):
        self.temp.cleanup()

    def test_passwords_and_access(self):
        self.assertIsNone(login("admin", "wrong", self.path))
        with connection(self.path) as db:
            stored = db.execute("SELECT password_hash FROM users WHERE username='admin'").fetchone()[0]
        self.assertNotIn("admin123", stored)
        with self.assertRaises(PermissionError):
            export_csv(self.doctor, "patients", self.path)
        with self.assertRaises(PermissionError):
            anonymize_pending(self.receptionist, self.path)

    def test_masking_update_and_audit(self):
        patient_id = add_patient(self.receptionist, "Jane Doe", "0300-123-4592", "Asthma", self.path)
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


if __name__ == "__main__":
    unittest.main()
