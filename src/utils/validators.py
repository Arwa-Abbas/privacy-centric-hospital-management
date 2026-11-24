import re


def patient_fields(name, contact, diagnosis):
    name, contact, diagnosis = (value.strip() for value in (name, contact, diagnosis))
    if not all((name, contact, diagnosis)):
        raise ValueError("Name, contact, and diagnosis are required")
    if len(name) > 120 or len(contact) > 40 or len(diagnosis) > 500:
        raise ValueError("A field exceeds the allowed length")
    if len(re.sub(r"\D", "", contact)) < 4:
        raise ValueError("Contact must contain at least four digits")
    return name, contact, diagnosis
