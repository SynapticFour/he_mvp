# SPDX-License-Identifier: Apache-2.0
"""SDK-specific exceptions."""


class SecureCollabSDKError(Exception):
    """Base exception for SDK."""


class CryptoError(SecureCollabSDKError):
    """Encryption/decryption or key error."""


class SchemaError(SecureCollabSDKError):
    """Schema validation or negotiation error."""


class APIError(SecureCollabSDKError):
    """API request failed (HTTP or validation)."""
