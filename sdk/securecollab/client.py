# SPDX-License-Identifier: Apache-2.0
"""Main SDK class: SecureCollabClient. Wraps crypto, schema, audit, API calls."""
# Full implementation: see backend/sdk.py (CLI commands and helpers).
# This class should expose: set_api_base, generate_key_share, encrypt_and_upload, request_computation, approve, submit_decryption_share, verify_audit, etc.


class SecureCollabClient:
    """Client for SecureCollab API and local HE operations."""

    def __init__(self, api_base_url: str = "http://localhost:8000"):
        self.api_base_url = api_base_url.rstrip("/")

    def get_algorithms(self) -> dict:
        """Fetch algorithm registry from API."""
        import json
        from urllib.request import urlopen, Request
        req = Request(f"{self.api_base_url}/algorithms", method="GET")
        with urlopen(req) as resp:
            return json.loads(resp.read().decode())
