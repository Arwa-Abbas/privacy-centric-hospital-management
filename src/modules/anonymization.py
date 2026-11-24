import hashlib
import hmac
import os
import re

from src.config import DEMO_PEPPER


def token(value, patient_id, label):
    key = os.environ.get("HOSPITAL_PSEUDONYM_KEY", DEMO_PEPPER).encode()
    message = f"{label}:{patient_id}:{value.strip().casefold()}".encode()
    return hmac.new(key, message, hashlib.sha256).hexdigest()[:10].upper()


def mask_patient(patient_id, name, contact, diagnosis):
    digits = re.sub(r"\D", "", contact)
    return (f"ANON_{token(name, patient_id, 'name')}",
            f"XXX-XXX-{digits[-4:]}",
            f"REDACTED_{token(diagnosis, patient_id, 'diagnosis')}")
