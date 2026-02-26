# SPDX-License-Identifier: Apache-2.0
"""Datasets router API tests."""
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_dataset_columns_404():
    r = client.get("/datasets/99999/columns")
    assert r.status_code == 404


def test_datasets_list():
    r = client.get("/datasets")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_datasets_accessible_empty():
    r = client.get("/datasets/accessible/nobody@example.com")
    assert r.status_code == 200
    assert r.json() == []


def test_access_datasets_by_owner_empty():
    r = client.get("/access/datasets/no-owner@example.com")
    assert r.status_code == 200
    assert isinstance(r.json(), list)
    assert r.json() == []
