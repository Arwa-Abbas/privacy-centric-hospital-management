# Holistic - GDPR-Compliant Mini Hospital Management System

**Course:** Information Security (CS-3002) - Assignment 4: *Privacy, Trust & the CIA Triad in Modern Information Systems*

A Streamlit + SQLite hospital dashboard that protects patient data with encryption, masking,
role-based access control (RBAC) and an append-only audit trail, following GDPR principles
(purpose limitation, data minimisation, storage limitation, accountability).

> All patient data in this project is **fictional**. The demo credentials are for coursework only.

---

## Quick start

```powershell
pip install -r requirements.txt
streamlit run Assignment4.py
```

The app opens at <http://localhost:8501>. On first run it creates `database/hospital.db`,
the encryption key `database/hospital.key`, the three user accounts, 18 fictional patients
and a week of sample activity so every chart has data.

Run the automated tests:

```powershell
python -m unittest discover -s src/tests -v
```

Reset to a clean demo: close the app, delete **both** `database/hospital.db` and
`database/hospital.key`, then start it again.

## Demo accounts

| Role | Username | Password | Can do |
|---|---|---|---|
| Admin | `admin` | `admin@123` | Raw + anonymized data, anonymize, retention, audit log, CSV export |
| Doctor | `arwaabbas` | `arwa@123` | View **anonymized** records only |
| Receptionist | `sarakhan` | `sara@123` | Register/update patients; never sees names, contacts or diagnoses |

---

## How the CIA triad is implemented

### Confidentiality
| Control | Where |
|---|---|
| Raw name, contact and diagnosis are encrypted with **Fernet** before they reach the database | `src/modules/encryption.py` |
| **Masking/pseudonymisation** with keyed HMAC-SHA256: `Maya Ahmed -> ANON_3F9A...`, `0300-111-4592 -> XXX-XXX-4592`, diagnosis -> `REDACTED_...` | `src/modules/anonymization.py` |
| **RBAC**: one permission table and a single `require()` gate used by every operation; each role's query only selects the columns it may see | `src/modules/authorization.py`, `src/modules/patient_management.py` |
| Login with salted **PBKDF2-HMAC-SHA256** (350k iterations); passwords are never stored in plaintext | `src/modules/authentication.py` |

### Integrity
| Control | Where |
|---|---|
| Every login, failed login, view, create, update, anonymization, export, erasure and consent is logged with user, role, timestamp and action | `src/modules/audit_logging.py` |
| The `logs` table is **append-only**: SQLite triggers abort any `UPDATE` or `DELETE` | `database/schema.sql` |
| Logs store IDs and counts only, never patient content | `src/modules/audit_logging.py` |
| Input validation plus `CHECK` constraints (roles, non-empty fields, phone format, length limits) | `src/utils/validators.py`, `database/schema.sql` |
| "Integrity Audit Log" page, admin only, with action filter | `src/dashboards/admin.py` |

### Availability
| Control | Where |
|---|---|
| `try/except` around login and database operations; failed operations roll back and show a friendly message | `src/app.py`, `database/db.py` |
| **CSV backup/export** of patients and audit log (admin; each download is logged) | `src/modules/backup.py` |
| System **uptime and last-sync time** in the footer of every page | `src/ui.py` |
| Database set-up runs once per server start, so the dashboard stays responsive | `src/app.py` |

### GDPR alignment (bonus features included)
- **Consent banner** shown before login; acceptance is written to the audit log.
- **Storage limitation:** the *Data retention* page flags records older than `RETENTION_DAYS` (365) and lets the admin erase them; each erasure is logged.
- **Data minimisation:** doctors and receptionists only receive the columns their role needs; dashboard statistics are computed in SQL without decrypting any patient data.
- **Accountability:** a complete, tamper-resistant audit trail and real-time activity graphs.
- **Reversible protection:** raw data is Fernet-encrypted (reversible for the admin) while the masked view is one-way.

---

## Project structure

```
Assignment4.py            Entry point (maps each assignment step to its file)
database/
  schema.sql              Tables, constraints, append-only triggers
  db.py                   Connection context manager (commit / rollback)
  seed.py                 Demo accounts and fictional demo data
src/
  app.py                  Consent + login, role-based navigation, footer
  ui.py                   Theme and small HTML components
  config.py               Paths and RETENTION_DAYS
  modules/                authentication, authorization, encryption, anonymization,
                          audit_logging, patient_management, backup, gdpr
  dashboards/             admin.py, doctor.py, receptionist.py, forms.py
  utils/                  validators.py, dates.py
  tests/                  test_workflows.py
docs/IMPLEMENTATION_PLAN.md   Original planning notes
```

## Database schema

- `users(user_id, username, password_hash, role, is_active)`
- `patients(patient_id, name, contact, diagnosis, anonymized_name, anonymized_contact, anonymized_diagnosis, date_added, updated_at, anonymized_at)` - `name`, `contact` and `diagnosis` hold Fernet ciphertext
- `logs(log_id, user_id, role, action, timestamp, details)` - append-only

## Typical workflow

1. A user accepts the consent notice and signs in; the role decides the pages offered.
2. The receptionist registers a patient (stored encrypted, status *Pending*).
3. The admin runs **Anonymize pending records**, creating masked values.
4. The doctor sees only the anonymized records.
5. Every step appears in the admin's **Audit log**; the admin can export CSV backups.

## Configuration and security notes

- `HOSPITAL_PSEUDONYM_KEY` (optional env var, see `.env.example`): private key for pseudonyms. Set it before the first run and never change it afterwards.
- `database/hospital.key` is required to read encrypted data. Keep it with any copy of the database; it is excluded from Git.
- Admin CSV exports contain decrypted data and must be stored securely.
- Timestamps are stored and shown in UTC.
- This is a coursework prototype demonstrating GDPR-aligned controls; it is not a production medical-records system or legal compliance advice.
