# SPDX-License-Identifier: Apache-2.0
"""Audit trail integrity tests. Independent of running server."""
import json
import pytest

from app.config import INITIAL_HASH
from app.core.security import sha3_256_hex


def test_sha3_256_hex_deterministic():
    """Same input produces same hash."""
    h1 = sha3_256_hex("a", "b")
    h2 = sha3_256_hex("a", "b")
    assert h1 == h2
    assert len(h1) == 64


def test_sha3_256_hex_different_inputs():
    """Different inputs produce different hashes."""
    h1 = sha3_256_hex("a")
    h2 = sha3_256_hex("b")
    assert h1 != h2


def test_chain_integrity():
    """Write 10 entries, verify chain (previous_hash -> entry_hash)."""
    chain = []
    prev = INITIAL_HASH
    for i in range(10):
        payload = f"action_{i}actor_{i}{json.dumps({'i': i})}2025-01-01T00:00:00{prev}"
        entry_hash = sha3_256_hex(payload)
        chain.append({"prev": prev, "payload": payload, "entry_hash": entry_hash})
        prev = entry_hash
    for j, link in enumerate(chain):
        recomputed = sha3_256_hex(link["payload"])
        assert link["entry_hash"] == recomputed
        if j > 0:
            assert link["prev"] == chain[j - 1]["entry_hash"]
    assert chain[0]["prev"] == INITIAL_HASH


def test_tamper_detection():
    """Modify one entry, verify chain breaks."""
    chain = []
    prev = INITIAL_HASH
    for i in range(5):
        payload = f"action_{i}actor_{i}{json.dumps({'i': i})}2025-01-01T00:00:00{prev}"
        entry_hash = sha3_256_hex(payload)
        chain.append({"payload": payload, "entry_hash": entry_hash})
        prev = entry_hash
    # Tamper: change payload of entry 2 (payload contains "i": 2 from json.dumps({'i': 2}))
    tampered_payload = chain[2]["payload"].replace('"i": 2', '"i": 99')
    tampered_hash = sha3_256_hex(tampered_payload)
    assert tampered_hash != chain[2]["entry_hash"]
    # Next link would use wrong previous_hash
    next_payload = f"action_3actor_3{json.dumps({'i': 3})}2025-01-01T00:00:00{chain[2]['entry_hash']}"
    next_hash_correct = sha3_256_hex(next_payload)
    next_payload_broken = f"action_3actor_3{json.dumps({'i': 3})}2025-01-01T00:00:00{tampered_hash}"
    next_hash_broken = sha3_256_hex(next_payload_broken)
    assert next_hash_broken != next_hash_correct


def test_codebase_hash_deterministic():
    """Call integrity twice, verify identical hash (when no file changes)."""
    from app.services.integrity_service import get_deployment_integrity
    d1 = get_deployment_integrity()
    d2 = get_deployment_integrity()
    assert "codebase_hash" in d1 and "codebase_hash" in d2
    assert d1["codebase_hash"] == d2["codebase_hash"]
