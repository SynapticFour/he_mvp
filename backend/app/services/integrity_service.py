# SPDX-License-Identifier: Apache-2.0
"""Codebase integrity: hash computation and verification."""
from __future__ import annotations

import logging
from datetime import datetime

logger = logging.getLogger("securecollab")

_DEPLOYMENT_INTEGRITY: dict = {}
_verify_impl = None

try:
    from integrity import compute_codebase_hash, verify_codebase_hash as _verify_impl
except Exception as e:
    logger.warning("Integrity module unavailable: %s", e)
    compute_codebase_hash = None

    def _verify_impl(expected: str):
        return {
            "verified": False,
            "expected_hash": expected,
            "current_hash": "unknown",
            "error": "Integrity module unavailable",
        }


def _init_integrity() -> dict:
    global _DEPLOYMENT_INTEGRITY
    if not _DEPLOYMENT_INTEGRITY:
        if compute_codebase_hash is not None:
            try:
                _DEPLOYMENT_INTEGRITY = compute_codebase_hash()
            except Exception as e:
                logger.warning("Codebase integrity computation failed: %s", e)
                _DEPLOYMENT_INTEGRITY = _unknown_integrity()
        else:
            _DEPLOYMENT_INTEGRITY = _unknown_integrity()
    return _DEPLOYMENT_INTEGRITY


def _unknown_integrity() -> dict:
    return {
        "codebase_hash": "unknown",
        "git_commit": "unknown",
        "computed_at": datetime.utcnow().isoformat(),
        "file_count": 0,
        "files_included": [],
    }


def get_deployment_integrity() -> dict:
    """Return current codebase hash and metadata (for audit and /system/integrity)."""
    return _init_integrity()


def verify_codebase_hash(expected: str) -> dict:
    """Compare client-provided hash with current codebase hash."""
    if _verify_impl is None:
        return {"verified": False, "expected_hash": expected, "current_hash": "unknown", "error": "Integrity module unavailable"}
    return _verify_impl(expected)
