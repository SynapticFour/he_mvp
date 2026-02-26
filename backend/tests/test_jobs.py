# SPDX-License-Identifier: Apache-2.0
"""API integration tests for jobs."""
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_jobs_my_empty():
    r = client.get("/jobs/my/nobody@example.com")
    assert r.status_code == 200
    assert r.json() == []
