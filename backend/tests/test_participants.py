# SPDX-License-Identifier: Apache-2.0
"""Participants router API tests."""
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_participant_studies_empty():
    r = client.get("/participants/studies/nobody@example.com")
    assert r.status_code == 200
    assert r.json() == []
