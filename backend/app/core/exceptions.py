# SPDX-License-Identifier: Apache-2.0
"""Custom exception classes."""
from __future__ import annotations


class SecureCollabError(Exception):
    """Base exception for SecureCollab."""


class ValidationError(SecureCollabError):
    """Input or schema validation failed."""


class NotFoundError(SecureCollabError):
    """Resource not found."""


class AlgorithmNotAllowedError(SecureCollabError):
    """Requested algorithm not in study protocol."""
