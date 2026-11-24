"""Role-based access control: one permission table, one `require` gate."""
PERMISSIONS = {
    "admin": {"raw_view", "masked_view", "create", "update", "anonymize", "logs", "export", "stats", "manage"},
    "doctor": {"masked_view"},
    "receptionist": {"create", "update", "status_view", "stats"},
}


def require(actor, permission):
    if not actor or permission not in PERMISSIONS.get(actor.get("role"), set()):
        raise PermissionError(f"Permission denied: {permission}")
