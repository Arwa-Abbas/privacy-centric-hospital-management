# Privacy-Centric Hospital Management Dashboard

Small Streamlit and SQLite demonstration for Information Security Assignment 4.

## Run

```powershell
python -m pip install -r requirements.txt
streamlit run Assignment4.py
```

The database is created and seeded on first run at `database/hospital.db`.

Run the focused tests with `python -m unittest discover -s src/tests -v`.

| Role | Username | Demo password |
|---|---|---|
| Admin | `admin` | `admin123` |
| Doctor | `Dr. Bob` | `doc123` |
| Receptionist | `Alice_recep` | `rec123` |

Use fictional records only. These credentials are solely for the coursework demo.
Passwords are stored as salted PBKDF2 hashes. Set `HOSPITAL_PSEUDONYM_KEY`
before first run for a private stable pseudonym key; keep its value unchanged.

Receptionist registers and updates records without reading stored sensitive
fields. Admin anonymizes pending records and reviews/exports logs. Doctor sees
only anonymized records. Patient and log CSV files are admin only.

The detailed plan is in `docs/IMPLEMENTATION_PLAN.md`.

This prototype demonstrates GDPR-aligned controls; it is not a complete legal
compliance or production medical-record system.
