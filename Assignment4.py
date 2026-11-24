"""Assignment 4 - GDPR-compliant mini Hospital Management System (CIA triad).

Run with:  streamlit run Assignment4.py

Where each step of the assignment lives:
  1. Database + schema ........ database/schema.sql, database/db.py, database/seed.py
  2. Login + RBAC ............. src/modules/authentication.py, src/modules/authorization.py
  3. Confidentiality .......... src/modules/encryption.py (Fernet), src/modules/anonymization.py (HMAC masking)
  4. Integrity ................ src/modules/audit_logging.py (append-only logs), src/utils/validators.py
  5. Availability ............. src/modules/backup.py (CSV export), error handling in src/app.py, uptime footer
  6. GDPR bonus ............... src/modules/gdpr.py (consent banner, retention), activity graphs in the admin dashboard
  7. Streamlit UI ............. src/app.py (shell), src/dashboards/*.py (one module per role)
"""
import runpy

runpy.run_module("src.app", run_name="__main__")
