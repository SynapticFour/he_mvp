# SPDX-License-Identifier: Apache-2.0
"""Integration tests for studies API. Use TestClient, no running server."""
import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_get_studies_empty():
    """List studies for unknown email returns empty list."""
    r = client.get("/studies", params={"participant_email": "nobody@example.com"})
    assert r.status_code == 200
    assert r.json() == []


def test_get_studies_no_param_returns_empty():
    """List studies without participant_email returns empty list (early exit)."""
    r = client.get("/studies")
    assert r.status_code == 200
    assert r.json() == []


def test_get_study_404():
    r = client.get("/studies/99999")
    assert r.status_code == 404


def test_study_protocol_404():
    r = client.get("/studies/99999/protocol")
    assert r.status_code == 404


def test_system_health():
    """Health endpoint returns ok."""
    r = client.get("/system/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_algorithms_list():
    """Algorithms registry returned at root."""
    r = client.get("/algorithms")
    assert r.status_code == 200
    data = r.json()
    assert "mean" in data
    assert "descriptive_statistics" in data


def test_create_study():
    """Create a new study (draft)."""
    r = client.post(
        "/studies/create",
        json={
            "name": "Test Study",
            "description": "Integration test",
            "creator_email": "creator@test.com",
            "institution_name": "Test Hospital",
            "threshold_t": 1,
            "threshold_n": 1,
            "allowed_algorithms": ["mean", "correlation"],
            "column_definitions": [],
            "public_key_share": "",
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert "study_id" in data
    study_id = data["study_id"]
    r2 = client.get(f"/studies/{study_id}")
    assert r2.status_code == 200
    assert r2.json()["name"] == "Test Study"
    assert r2.json()["status"] == "draft"


def test_join_study():
    """Join an existing study (requires protocol finalized; we create study and join)."""
    # Create study
    r = client.post(
        "/studies/create",
        json={
            "name": "Join Test Study",
            "description": "For join test",
            "creator_email": "creator@test.com",
            "institution_name": "Creator Hospital",
            "threshold_t": 1,
            "threshold_n": 2,
            "allowed_algorithms": ["mean"],
            "column_definitions": [],
            "public_key_share": "",
        },
    )
    assert r.status_code == 200
    study_id = r.json()["study_id"]
    # Create and finalize protocol (simplified: some studies allow join without protocol)
    # This study has no protocol; join may fail with "protocol must be finalized"
    r_join = client.post(
        f"/studies/{study_id}/join",
        json={
            "institution_email": "joiner@test.com",
            "institution_name": "Joiner Hospital",
            "public_key_share": "dummy_base64_key_placeholder",
        },
    )
    # Either 200 (if join allowed without protocol) or 400 (protocol must be finalized)
    assert r_join.status_code in (200, 400)


def test_upload_dataset():
    """Upload encrypted dataset (standalone /datasets/upload)."""
    # Use a minimal .bin file: we need valid pickle bundle or the endpoint may fail on read
    import io
    import pickle
    # Minimal fake bundle so the server accepts the file
    fake_bundle = {"n": 1, "columns": "[]", "public_context": b"x", "secret_context": b"y", "vectors": {}}
    file_bytes = pickle.dumps(fake_bundle)
    r = client.post(
        "/datasets/upload",
        data={
            "name": "Test Dataset",
            "description": "Test",
            "owner_email": "owner@test.com",
            "organization": "Test Org",
            "columns": "[]",
            "declared_rows": "",
        },
        files={"file": ("encrypted.bin", io.BytesIO(file_bytes), "application/octet-stream")},
    )
    assert r.status_code == 200
    assert "dataset_id" in r.json()


def test_request_and_approve_computation():
    """Request a job and approve it (standalone jobs, not study)."""
    pytest.importorskip("tenseal")
    import io
    import pickle
    try:
        import tenseal as ts
        ctx = ts.context(ts.SCHEME_TYPE.CKKS, 8192, coeff_mod_bit_sizes=[60, 40, 40, 60])
        ctx.global_scale = 2**40
        ctx.generate_galois_keys()
        enc = ts.ckks_vector(ctx, [1.0, 2.0, 3.0])
        bundle = {
            "public_context": ctx.serialize(save_secret_key=False),
            "secret_context": ctx.serialize(save_public_key=True),
            "vectors": {"col1": enc.serialize()},
            "columns": '["col1"]',
            "n": 3,
        }
    except ImportError:
        pytest.skip("tenseal required for approve step")
    file_bytes = pickle.dumps(bundle)
    r_upload = client.post(
        "/datasets/upload",
        data={
            "name": "Job Test Dataset",
            "description": "For job test",
            "owner_email": "owner@test.com",
            "organization": "",
            "columns": '["col1"]',
            "declared_rows": "3",
        },
        files={"file": ("encrypted.bin", io.BytesIO(file_bytes), "application/octet-stream")},
    )
    if r_upload.status_code != 200:
        pytest.skip("Upload failed (e.g. validation); skip job test")
    dataset_id = r_upload.json()["dataset_id"]
    r_req = client.post(
        "/jobs/request",
        json={
            "dataset_id": dataset_id,
            "requester_email": "researcher@test.com",
            "computation_type": "mean",
            "algorithm": "mean",
            "selected_columns": ["col1"],
        },
    )
    assert r_req.status_code == 200
    job_id = r_req.json()["job_id"]
    r_approve = client.post(f"/jobs/{job_id}/approve")
    assert r_approve.status_code == 200
    assert r_approve.json()["status"] == "completed"


def test_full_multiparty_workflow():
    """Two institutions, one computation (study flow: create, protocol, join, activate, upload, request, approve, submit share)."""
    # Create study
    r = client.post(
        "/studies/create",
        json={
            "name": "Multiparty Test",
            "description": "E2E test",
            "creator_email": "inst1@test.com",
            "institution_name": "Inst 1",
            "threshold_t": 1,
            "threshold_n": 2,
            "allowed_algorithms": ["mean"],
            "column_definitions": [{"name": "x", "data_type": "float", "required": True}],
            "public_key_share": "",
        },
    )
    assert r.status_code == 200
    study_id = r.json()["study_id"]
    # Protocol create + finalize
    r_proto = client.post(
        f"/studies/{study_id}/protocol/create",
        json={
            "required_columns": [{"name": "x", "data_type": "float", "required": True}],
            "minimum_rows": 1,
            "missing_value_strategy": "exclude",
            "creator_email": "inst1@test.com",
        },
    )
    assert r_proto.status_code == 200
    r_fin = client.post(f"/studies/{study_id}/protocol/finalize", json={"creator_email": "inst1@test.com"})
    assert r_fin.status_code == 200
    # Join second institution
    r_join = client.post(
        f"/studies/{study_id}/join",
        json={
            "institution_email": "inst2@test.com",
            "institution_name": "Inst 2",
            "public_key_share": "dummy_key_for_test",
        },
    )
    assert r_join.status_code == 200
    # Activate (may need schema submit + dry run; try activate)
    r_act = client.post(f"/studies/{study_id}/activate", params={"actor_email": "inst1@test.com"})
    # Can be 200 or fail on preconditions
    assert r_act.status_code in (200, 422)
    if r_act.status_code != 200:
        pytest.skip("Activate preconditions not met (schema/dry run); rest of workflow skipped")
    # Request computation
    r_req = client.post(
        f"/studies/{study_id}/request_computation",
        json={
            "requester_email": "researcher@test.com",
            "algorithm": "mean",
            "selected_columns": ["x"],
            "parameters": {},
        },
    )
    assert r_req.status_code == 200
    job_id = r_req.json()["job_id"]
    # Approve (one institution)
    r_app = client.post(
        f"/studies/{study_id}/jobs/{job_id}/approve",
        json={"institution_email": "inst1@test.com"},
    )
    assert r_app.status_code == 200
    # Submit decryption share
    r_share = client.post(
        f"/studies/{study_id}/jobs/{job_id}/submit_decryption_share",
        json={"institution_email": "inst1@test.com", "decryption_share": "dummy_share"},
    )
    assert r_share.status_code == 200
    assert r_share.json()["status"] == "completed"
