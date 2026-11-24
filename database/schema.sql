PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('admin','doctor','receptionist')),
    is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0,1))
);
CREATE TABLE IF NOT EXISTS patients (
    patient_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL CHECK (length(trim(name)) > 0),
    contact TEXT NOT NULL CHECK (length(trim(contact)) > 0),
    diagnosis TEXT NOT NULL CHECK (length(trim(diagnosis)) > 0),
    anonymized_name TEXT,
    anonymized_contact TEXT,
    anonymized_diagnosis TEXT,
    date_added TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    anonymized_at TEXT
);
CREATE TABLE IF NOT EXISTS logs (
    log_id INTEGER PRIMARY KEY,
    user_id INTEGER REFERENCES users(user_id),
    role TEXT NOT NULL,
    action TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    details TEXT NOT NULL DEFAULT ''
);
CREATE TRIGGER IF NOT EXISTS logs_no_update BEFORE UPDATE ON logs
BEGIN SELECT RAISE(ABORT, 'audit log is append only'); END;
CREATE TRIGGER IF NOT EXISTS logs_no_delete BEFORE DELETE ON logs
BEGIN SELECT RAISE(ABORT, 'audit log is append only'); END;
