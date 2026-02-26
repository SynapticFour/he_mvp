# SPDX-License-Identifier: Apache-2.0
"""Codebase hash and integrity tests."""
from fastapi.testclient import TestClient

from app.main import app
from app.services.integrity_service import get_deployment_integrity, verify_codebase_hash

client = TestClient(app)


def test_get_system_integrity():
    r = client.get("/system/integrity")
    assert r.status_code == 200
    data = r.json()
    assert "codebase_hash" in data
    assert "python_version" in data


def test_get_deployment_integrity():
    d = get_deployment_integrity()
    assert "codebase_hash" in d


def test_verify_codebase_hash():
    result = verify_codebase_hash("nonexistent_hash_12345")
    assert "verified" in result
    assert result["expected_hash"] == "nonexistent_hash_12345"
