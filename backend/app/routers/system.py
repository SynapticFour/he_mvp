# SPDX-License-Identifier: Apache-2.0
"""Health, integrity, and algorithms endpoints."""
import sys

from fastapi import APIRouter, Query, Request

from app.core.security import rate_limit
from app.services.integrity_service import get_deployment_integrity, verify_codebase_hash

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/health")
def health():
    """Liveness/readiness."""
    return {"status": "ok"}


@router.get("/integrity")
@rate_limit("100/hour")
def system_integrity(request: Request):
    """Codebase hash, Git commit, versions for verification."""
    integrity = get_deployment_integrity()
    try:
        import tenseal as ts
        tenseal_version = getattr(ts, "__version__", "unknown")
    except ImportError:
        tenseal_version = "not installed"
    try:
        import fastapi
        fastapi_version = getattr(fastapi, "__version__", "unknown")
    except ImportError:
        fastapi_version = "unknown"
    return {
        "codebase_hash": integrity.get("codebase_hash", "unknown"),
        "git_commit": integrity.get("git_commit", "unknown"),
        "computed_at": integrity.get("computed_at", ""),
        "tenseal_version": tenseal_version,
        "fastapi_version": fastapi_version,
        "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
    }


@router.get("/integrity/verify")
@rate_limit("100/hour")
def system_integrity_verify(request: Request, expected: str = Query(..., alias="expected_hash")):
    """Verify current codebase hash matches expected."""
    try:
        return verify_codebase_hash(expected)
    except Exception:
        return {"verified": False, "expected_hash": expected, "current_hash": "unknown", "error": "Verification failed"}


