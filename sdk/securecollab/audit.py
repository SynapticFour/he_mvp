# SPDX-License-Identifier: Apache-2.0
"""Local audit log management and verification."""
def write_local_audit(institution_email: str, action: str, details: dict) -> str:
    """Placeholder: append signed entry to local audit file."""
    raise NotImplementedError("Migrate from backend/sdk.py")

def verify_audit(api_base_url: str, study_id: int, local_audit_path: str) -> dict:
    """Placeholder: verify local audit against server trail."""
    raise NotImplementedError("Migrate from backend/sdk.py")
