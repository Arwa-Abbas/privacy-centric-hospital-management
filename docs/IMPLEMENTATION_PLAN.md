# Assignment 4 Implementation Plan

## 1. Project Goal

Build a small Streamlit hospital management dashboard that demonstrates how the CIA triad and GDPR-aligned privacy practices can be applied to patient records.

The implementation should be easy to demonstrate and explain. It is an educational prototype, not a production hospital system and not a claim of full legal GDPR compliance.

### Required stack

- Python 3
- Streamlit
- SQLite
- Standard-library security utilities (`hashlib`, `hmac`, `secrets`)
- Pandas only where it simplifies Streamlit tables and CSV export
- Optional `cryptography` dependency only if the Fernet bonus is attempted

### Recommended implementation choices

- Use SQLite rather than MySQL because it satisfies the assignment and needs no external server.
- Submit `Assignment4.py` as the required `.py` file and Streamlit entry point.
- Use salted PBKDF2 password hashes; never store the sample plaintext passwords from the assignment.
- Implement required masking/pseudonymization first. Treat Fernet encryption, charts, retention, and consent as optional bonus work.
- Keep all authorization checks in Python services, not only in hidden Streamlit buttons.

## 2. Scope and Boundaries

### In scope

- Login and logout
- Three roles: admin, doctor, and receptionist
- Patient creation, restricted viewing, and controlled updating
- Admin-triggered anonymization/masking
- Role-specific dashboards
- Audit logging of security-relevant activity
- Input validation and database constraints
- Error handling and stable SQLite access
- Admin-only CSV backup/export
- Uptime or last synchronization time in the footer
- A 3-5 page PDF report with diagrams and screenshots
- Optional short demonstration video

### Deliberately out of scope

- Patient appointments, billing, pharmacy, and clinical workflows
- Self-registration, email verification, and password-reset services
- Cloud deployment, Docker, microservices, and REST APIs
- A full hospital-grade GDPR/HIPAA compliance program
- Complex key-management infrastructure
- Advanced analytics unless the optional activity chart is added

These exclusions prevent the project from becoming larger than the assignment.

## 3. Requirement Inventory

### 3.1 Confidentiality and privacy

1. Authenticate every user through a login screen.
2. Store passwords as salted PBKDF2 hashes.
3. Enforce role-based access control:
   - **Admin:** view raw and anonymized data, trigger anonymization, review logs, and download backups.
   - **Doctor:** read anonymized patient data only; no raw identifiers and no edits.
   - **Receptionist:** add patients and update records without displaying stored sensitive values.
4. Protect name, contact, and diagnosis with masked or pseudonymized versions.
5. Use a stable pseudonym such as `ANON_<digest>` for names.
6. Mask contacts in the assignment's expected style, such as `XXX-XXX-4592`.
7. Replace a diagnosis with a non-identifying digest/token in anonymized views.
8. Never place raw patient data in audit-log details or error messages.
9. Restrict patient and log CSV downloads to the admin.

### 3.2 Integrity and accountability

1. Log at least:
   - successful and failed login attempts;
   - logout;
   - patient creation and update;
   - patient-list views;
   - anonymization;
   - audit-log views;
   - CSV exports;
   - handled database/application errors where appropriate.
2. Each log entry records user ID when known, role, timestamp, action, and sanitized details.
3. Provide no application operation that edits or deletes audit rows; the log service only inserts and reads.
4. Use SQLite foreign keys, `NOT NULL`, `UNIQUE`, and `CHECK` constraints.
5. Validate and normalize inputs before every write.
6. Use parameterized SQL and transactions.
7. Reject actions when the role lacks permission even if a UI function is called directly.
8. When a receptionist changes raw patient data, clear the old anonymized fields so doctors cannot see stale data. The admin must anonymize the updated record again.

### 3.3 Availability and reliability

1. Open and close database connections safely with context managers.
2. Initialize the database and seed demo users automatically and idempotently.
3. Catch login, validation, and database failures and show useful but non-sensitive messages.
4. Keep the app usable after a handled failure.
5. Offer an admin-only patient backup as an in-memory CSV download.
6. Offer a separate admin-only audit-log CSV download to match the example workflow.
7. Show app uptime and/or last successful database synchronization in the footer.
8. Use SQLite configuration suitable for a small demo, including foreign keys and a short busy timeout. WAL mode may be enabled if it works reliably in the target environment.

### 3.4 GDPR alignment to demonstrate and discuss

The report and demo should map features to these principles:

- **Data minimization:** collect only name, contact, diagnosis, and operational timestamps needed by the scenario.
- **Purpose limitation:** describe the system's purpose as managing hospital patient records for authorized staff.
- **Confidentiality and security:** authentication, RBAC, masking/pseudonymization, password hashing, and restricted exports.
- **Accuracy/integrity:** validation, controlled updates, constraints, transactions, and invalidation of stale anonymized data.
- **Accountability:** timestamped audit records showing who did what and why/where appropriate.
- **Storage limitation:** discuss retention and deletion as a limitation; implement a retention timer only as an optional bonus.
- **Transparency/consent:** discuss clear notices and lawful processing; implement a consent banner only as an optional bonus.

Do not overstate compliance. A real deployment would also require a lawful basis, data-subject request handling, organizational policies, breach procedures, access reviews, secure hosting, key management, and a formal impact assessment.

### 3.5 Deliverables

- Source-code folder containing `.py` files and the SQLite database file.
- `Assignment4.py` with clear steps/comments; this also serves as the Streamlit entry point.
- PDF report of 3-5 pages containing:
  - a system overview diagram showing CIA layers;
  - screenshots of login, anonymization, and audit-log screens;
  - discussion of CIA implementation and GDPR alignment.
- Optional 2-3 minute demo video, uploaded to Drive, with its link placed in the PDF report.

### 3.6 Optional bonus, attempted only after required work passes

- Fernet encryption for reversible protection of raw patient fields.
- Real-time activity graph, such as actions per day.
- Data-retention timer.
- User consent/privacy notice banner.

## 4. Proposed Repository Structure

```text
A4/
|-- Assignment4.py              # Submission launcher for Streamlit
|-- README.md                   # Setup, run command, demo accounts, security notes
|-- requirements.txt            # Minimal pinned/runtime dependencies
|-- .gitignore                  # Ignore caches, local secrets, temporary exports
|-- .env.example                # Optional documented secret names; no real secrets
|
|-- database/
|   |-- db.py                   # SQLite connection, initialization, transactions
|   |-- schema.sql              # Users, patients, audit tables and constraints
|   |-- seed.py                 # Idempotent demo-account seeding
|   `-- hospital.db             # Generated SQLite database included in final submission
|
|-- src/
|   |-- app.py                 # Streamlit entry flow and styling
|   |-- config.py              # Paths and configuration
|   |-- modules/               # Auth, RBAC, anonymization, patient operations, audit, CSV
|   |-- dashboards/            # Admin, doctor, and receptionist Streamlit views
|   |-- utils/                 # Input validation helpers
|   `-- tests/                 # Security and workflow tests
|
|-- report/
|   |-- Assignment4_Report.pdf  # Final 3-5 page report
|   |-- report_source.md        # Report source/outline for reproducibility
|   `-- screenshots/            # Required UI evidence
|
`-- docs/                       # This plan and eventual final report
```

### Why this structure is sufficient

- `Assignment4.py` remains the submission entry point and runs `app.py`.
- Security, privacy, database, audit, and patient operations are separated because each maps directly to a rubric area.
- UI modules are not split further; the app is too small to justify a page framework.
- Tests cover risky rules rather than trying to test Streamlit rendering.
- Bonus code should be added inside the existing modules or one small chart helper, not as a new subsystem.

## 5. Data Model

### `users`

| Column | Purpose |
|---|---|
| `user_id` | Integer primary key |
| `username` | Unique login name |
| `password_hash` | PBKDF2 result, never plaintext |
| Salt in `password_hash` | Random per-user salt encoded alongside PBKDF2 parameters |
| `role` | `admin`, `doctor`, or `receptionist` with a `CHECK` constraint |
| `is_active` | Allows a user to be disabled without deletion |

Seed the three assignment accounts on first run, but document demo-only passwords in the README. Hash the passwords before insertion.

### `patients`

| Column | Purpose |
|---|---|
| `patient_id` | Integer primary key |
| `name` | Raw name; admin only |
| `contact` | Raw contact; admin only |
| `diagnosis` | Raw diagnosis; admin only |
| `anonymized_name` | Stable `ANON_...` token |
| `anonymized_contact` | Masked contact ending in the last four digits |
| `anonymized_diagnosis` | Non-identifying diagnosis token/redaction |
| `date_added` | Creation timestamp |
| `updated_at` | Latest raw-data change |
| `anonymized_at` | Latest anonymization timestamp or `NULL` when pending |

All three anonymized fields become `NULL` on a raw-data update. This makes anonymization status unambiguous.

### `logs`

| Column | Purpose |
|---|---|
| `log_id` | Integer primary key |
| `user_id` | Nullable foreign key; failed login may not identify a user |
| `role` | Role at the time of action, or `unknown` for failed login |
| `action` | Controlled action name such as `LOGIN_SUCCESS` or `PATIENT_UPDATE` |
| `timestamp` | UTC timestamp stored in ISO 8601 format |
| `details` | Sanitized context, e.g. patient ID, never raw medical data |

Store timestamps in UTC and format them for display consistently. The report may note the local demonstration timezone if needed.

## 6. Authorization Matrix

| Capability | Admin | Doctor | Receptionist |
|---|:---:|:---:|:---:|
| View raw patient data | Yes | No | No |
| View anonymized patient data | Yes | Yes | No |
| Add a patient | Yes | No | Yes |
| Update raw patient fields | Yes | No | Yes, through write-only/re-entry form |
| Trigger anonymization | Yes | No | No |
| View audit logs | Yes | No | No |
| Export patient backup | Yes | No | No |
| Export audit logs | Yes | No | No |
| View uptime/last sync | Yes | Yes | Yes |

Receptionist editing should work by selecting a patient ID and entering replacement values. The UI may show dates/status and masked placeholders, but it must not prefill or reveal stored name, contact, or diagnosis.

## 7. Application Flow and Screens

### 7.1 Login screen

- Username and password fields.
- Generic error for invalid credentials.
- On success, store only user ID, username, and role in `st.session_state`.
- Log success or failure; never log the supplied password.

### 7.2 Shared dashboard shell

- App title and signed-in role.
- Role-appropriate navigation/tabs.
- Logout button.
- Footer showing uptime and last successful database action/synchronization.

### 7.3 Admin view

- **Patient records:** raw and anonymized columns together.
- **Anonymization:** count/list pending patient IDs and an `Anonymize pending records` button.
- **Audit log:** filterable/read-only table and secure CSV download.
- **Backup:** patient CSV download.
- Every view/export/anonymize action is audited.

### 7.4 Doctor view

- Read-only table containing patient ID and anonymized fields only.
- Pending/non-anonymized patients are omitted.
- No export unless explicitly justified; safest assignment implementation is no doctor export.

### 7.5 Receptionist view

- Add-patient form.
- Update form using patient ID and replacement values.
- A minimal list may show patient ID, date added, updated time, and anonymization status only.
- No raw or anonymized sensitive values are displayed.

## 8. Security and Privacy Design Details

### Passwords

- Generate salts with `secrets.token_bytes`.
- Derive password hashes with `hashlib.pbkdf2_hmac('sha256', ...)` using a defensible iteration count.
- Compare with `hmac.compare_digest`.
- Keep the hash format and iteration count explicit so verification is reproducible.

### Pseudonymization and masking

- Normalize inputs before token generation.
- Create a stable name pseudonym from a keyed digest/pepper plus patient ID/name, then expose only a short prefix such as `ANON_A1B2C3D4`.
- Preserve only the last four contact digits in the masked value.
- Represent the diagnosis with a stable token or `REDACTED_<digest>` rather than the raw diagnosis.
- Keep the pseudonymization pepper outside source control through an environment variable where possible. For marking convenience, document a clearly labeled demo fallback and its limitations.

### RBAC

- Define one permission matrix in `src/modules/authorization.py`.
- Call `require_permission(...)` inside patient/audit functions before data access.
- Use UI hiding only as a usability layer; do not treat it as authorization.
- Return role-specific SQL columns so unauthorized raw fields are never loaded for doctor/receptionist screens.

### Audit safety

- Use controlled action constants.
- Log patient IDs, record counts, and success/failure, not names, contacts, diagnoses, passwords, or CSV contents.
- Do not offer update/delete operations for logs.
- If simple to implement, add SQLite triggers rejecting log updates/deletes; otherwise document application-level append-only enforcement as the prototype boundary.

### Database safety

- Use `?` parameters for every value in SQL.
- Enable foreign keys per connection.
- Wrap multi-step changes, such as anonymizing and logging, in one transaction where practical.
- Validate lengths and required formats in Python and reinforce core invariants with database constraints.

## 9. Validation Rules

- Username/password: required at login; do not reveal which field was wrong.
- Patient name: required, trimmed, reasonable length, no empty/whitespace-only value.
- Contact: required; normalize allowed digits and common separators; require at least four digits for masking.
- Diagnosis: required, trimmed, reasonable length.
- Patient ID: positive integer and must exist before update.
- Update form: require at least one replacement field; blank fields mean `leave unchanged`.
- Role: must be one of the three fixed values.
- CSV export: admin permission required immediately before data retrieval.

## 10. Phased Implementation Plan

### Phase 0 - Confirm scope and acceptance checklist

1. Turn the requirement inventory and rubric below into a checklist.
2. Commit to SQLite and the proposed minimal structure.
3. Decide whether optional bonus features will be attempted only after the base system is complete.

**Exit condition:** every assignment statement maps to a feature, test, report section, or explicit optional item.

### Phase 1 - Project skeleton and database

1. Create folders, `requirements.txt`, `.gitignore`, and README skeleton.
2. Implement configuration and database path creation.
3. Create the `users`, `patients`, and `logs` schema with constraints.
4. Implement idempotent initialization and seed the three hashed demo accounts.
5. Add safe connection/transaction helpers.

**Exit condition:** a clean run creates `database/hospital.db` once, repeat runs do not duplicate users, and foreign keys/constraints work.

### Phase 2 - Authentication and RBAC

1. Implement PBKDF2 hashing and verification.
2. Implement login/logout session state.
3. Define the permission matrix and authorization guard.
4. Audit login success, login failure, and logout.
5. Build a minimal login screen and role-aware dashboard shell.

**Exit condition:** all three users reach only their dashboard, invalid login is handled, and direct unauthorized service calls fail.

### Phase 3 - Patient workflows and confidentiality

1. Implement validation and patient creation.
2. Implement admin/receptionist updates with stale anonymized fields cleared.
3. Implement name, contact, and diagnosis anonymization.
4. Add admin raw/anonymized view.
5. Add doctor anonymized-only view.
6. Add receptionist write-only/re-entry workflow.
7. Audit creates, updates, views, and anonymization.

**Exit condition:** the role matrix is satisfied and no unauthorized screen/service returns raw data.

### Phase 4 - Integrity, availability, and exports

1. Finish the admin-only audit-log screen.
2. Add database/application exception handling with sanitized messages.
3. Add admin-only patient and log CSV download buttons.
4. Add uptime and last successful synchronization/database-action footer.
5. Check transaction rollback on a forced failure.
6. Add concise status feedback for successful actions.

**Exit condition:** normal errors do not crash the app, exports work, audit actions are recorded, and the footer updates.

### Phase 5 - Tests and manual security verification

1. Test password hashing and incorrect-password rejection.
2. Test every permission in the authorization matrix.
3. Test exact masking output and stable pseudonyms.
4. Test input validation and SQL parameterization paths.
5. Test update invalidation and re-anonymization.
6. Test that logs contain no raw sensitive values.
7. Test that only admins can read/export logs and patient backups.
8. Perform a manual three-role walkthrough in Streamlit.

**Exit condition:** automated tests pass and the manual acceptance script below passes without data leakage.

### Phase 6 - Report and demonstration evidence

1. Create a simple architecture/CIA diagram.
2. Capture required screenshots:
   - login;
   - admin anonymization before/after;
   - admin integrity audit log.
3. Write the 3-5 page report using the outline below.
4. Verify the PDF visually for readable screenshots, diagram labels, page count, and no clipping.
5. Optionally record a 2-3 minute demo and add its Drive link to the PDF.

**Exit condition:** deliverables match the assignment wording and the report visibly proves the main features.

### Phase 7 - Optional bonus

Attempt only if Phases 0-6 are complete:

1. Add one simple activity-per-day chart from audit counts.
2. Add a concise consent/privacy notice banner.
3. Add a configurable retention indicator or cleanup workflow with audit logging.
4. Add Fernet encryption only if key loading, migration, failure handling, and demonstration can be completed safely.

**Exit condition:** bonus work does not weaken or complicate required functionality.

## 11. Manual Acceptance Script

1. Start with `streamlit run Assignment4.py`.
2. Try an invalid login and verify a generic error plus sanitized failed-login log.
3. Log in as receptionist and add a patient.
4. Confirm the receptionist sees the new patient ID/status but not stored sensitive values.
5. Update the patient and confirm anonymization status is pending.
6. Log in as doctor and verify the pending patient is not visible.
7. Log in as admin, view raw data, and trigger anonymization.
8. Confirm the admin sees both raw and masked values.
9. Log in as doctor and confirm only masked/anonymized columns are visible.
10. Confirm doctor and receptionist cannot reach logs, raw views, anonymization, or exports.
11. Log in as admin and verify the audit trail includes login, create, update, view, anonymize, and export actions with timestamps and roles.
12. Download both CSVs and confirm they are admin-only and correctly formed.
13. Trigger harmless validation and database-error cases and confirm the app remains usable.
14. Verify uptime/last synchronization in the footer.

## 12. Rubric Coverage Matrix

| Rubric component | Marks | Evidence to implement and show |
|---|---:|---|
| Privacy & GDPR Compliance | 20 | Data minimization, purpose statement, restricted processing, masking, accountability, report mapping and limitations |
| Confidentiality Implementation | 20 | Login, PBKDF2 passwords, RBAC, role-specific queries, masked name/contact/diagnosis, restricted exports |
| Integrity - Logging & Validation | 20 | Complete audit trail, sanitized details, constraints, validation, parameterized SQL, transactions, stale-anonymization invalidation |
| Availability & Reliability | 15 | Safe SQLite access, exception handling, responsive Streamlit flow, CSV recovery, uptime/last sync |
| Dashboard Functionality & Design | 10 | Clear role-based navigation, usable forms/tables, status feedback, consistent layout |
| Documentation & Screenshots | 10 | 3-5 page PDF, CIA diagram, required screenshots, concise setup README |
| Presentation/Demo/Video | 5 | Rehearsed walkthrough; optional 2-3 minute video link in report if produced |

## 13. Suggested Report Outline (3-5 Pages)

### Page 1 - Overview and architecture

- Problem and scope
- Technology choices
- CIA-layer architecture diagram

### Page 2 - Confidentiality and privacy

- Authentication and RBAC table
- Masking/pseudonymization explanation
- Login and anonymization screenshots

### Page 3 - Integrity and accountability

- Validation, constraints, parameterized queries, and transactions
- Audit-log screenshot and example sanitized event

### Page 4 - Availability and GDPR alignment

- Error handling, SQLite reliability, CSV recovery, and uptime/last sync
- GDPR principle-to-feature mapping
- Honest limitations

### Page 5 - Demonstration and conclusion, if needed

- Short workflow summary
- Test results
- Optional demo-video link
- Conclusion

## 14. Architecture Diagram Content

The report diagram can use four simple layers:

```text
Users: Admin | Doctor | Receptionist
                |
Streamlit UI: Login + role-specific views
                |
Security/Service Layer:
  Confidentiality -> authentication, RBAC, masking
  Integrity       -> validation, transactions, audit logs
  Availability    -> exception handling, reliable queries, CSV backup
                |
SQLite: users | patients | logs
```

No complex deployment diagram is necessary. The supplied assignment and reference PDFs are kept locally in the ignored `tmp/` folder.

## 15. Main Risks and Controls

| Risk | Control |
|---|---|
| UI hides a button but service still allows access | Enforce permissions inside every service function |
| Passwords copied from assignment are stored plaintext | Seed only derived PBKDF2 hashes and salts |
| Doctor query accidentally selects raw columns | Use explicit role-specific column lists, never `SELECT *` |
| Receptionist sees old values while editing | Use write-only replacement fields and show only patient ID/status |
| Updated raw values leave old anonymized values | Clear anonymized fields in the same update transaction |
| Logs leak patient data or passwords | Allowlisted actions and sanitized ID/count-only details |
| CSV backup leaks sensitive data | Admin-only permission check immediately before retrieval/download |
| App crashes on a locked/missing database | Initialize safely, use timeout/context managers, catch and report failures |
| Bonus encryption adds key failures late | Keep Fernet optional and implement only after the base rubric passes |
| Report claims legal compliance too broadly | State that the prototype demonstrates GDPR-aligned controls within assignment scope |

## 16. Definition of Done

The project is complete when:

- every mandatory requirement has a visible implementation and test/evidence;
- all role restrictions work at both UI and service levels;
- passwords and logs contain no plaintext secrets or patient-sensitive details;
- admin, doctor, and receptionist workflows pass the manual script;
- CSV recovery and footer status work;
- the SQLite database is included and opens with seeded demo accounts/sample data;
- `Assignment4.py` is commented and runs from documented commands;
- automated tests pass;
- the report is 3-5 pages, includes the CIA diagram and required screenshots, and accurately discusses GDPR alignment;
- optional bonus work is clearly labeled and does not interfere with required features.

