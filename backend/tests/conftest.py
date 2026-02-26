# SPDX-License-Identifier: Apache-2.0
"""pytest fixtures for backend tests."""
import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    """FastAPI test client."""
    return TestClient(app)
