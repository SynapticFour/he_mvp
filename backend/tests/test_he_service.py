# SPDX-License-Identifier: Apache-2.0
"""Unit tests for HE operations. Independent of running server."""
import math
import pickle
import pytest

try:
    import tenseal as ts
    import numpy as np
    TENSEAL_AVAILABLE = True
except ImportError:
    TENSEAL_AVAILABLE = False

from app.core.algorithms import ALGORITHM_REGISTRY


def _make_simple_bundle(values: list[float], col_name: str = "col1"):
    """Build a minimal CKKS bundle (single column) for testing."""
    if not TENSEAL_AVAILABLE:
        pytest.skip("tenseal not installed")
    ctx = ts.context(ts.SCHEME_TYPE.CKKS, 8192, coeff_mod_bit_sizes=[60, 40, 40, 60])
    ctx.global_scale = 2**40
    ctx.generate_galois_keys()
    enc = ts.ckks_vector(ctx, values)
    n = len(values)
    bundle = {
        "public_context": ctx.serialize(save_secret_key=False),
        "secret_context": ctx.serialize(save_public_key=True),
        "vectors": {col_name: enc.serialize()},
        "columns": f'["{col_name}"]',
        "n": n,
    }
    return bundle


def _make_two_column_bundle(col1: list[float], col2: list[float], name1: str = "a", name2: str = "b"):
    """Build a two-column CKKS bundle for correlation test."""
    if not TENSEAL_AVAILABLE:
        pytest.skip("tenseal not installed")
    n = len(col1)
    assert len(col2) == n
    ctx = ts.context(ts.SCHEME_TYPE.CKKS, 8192, coeff_mod_bit_sizes=[60, 40, 40, 60])
    ctx.global_scale = 2**40
    ctx.generate_galois_keys()
    enc1 = ts.ckks_vector(ctx, col1)
    enc2 = ts.ckks_vector(ctx, col2)
    bundle = {
        "public_context": ctx.serialize(save_secret_key=False),
        "secret_context": ctx.serialize(save_public_key=True),
        "vectors": {name1: enc1.serialize(), name2: enc2.serialize()},
        "columns": f'["{name1}", "{name2}"]',
        "n": n,
    }
    return bundle


def test_algorithm_registry_non_empty():
    """Registry is populated and contains expected algorithms."""
    assert len(ALGORITHM_REGISTRY) > 0
    assert "mean" in ALGORITHM_REGISTRY
    assert "descriptive_statistics" in ALGORITHM_REGISTRY
    assert "correlation" in ALGORITHM_REGISTRY


def test_run_computation_unknown_algorithm():
    """Unknown algorithm raises ValueError."""
    from app.services.he_service import run_computation
    with pytest.raises(ValueError, match="Unknown algorithm"):
        run_computation({}, "invalid_algorithm")


@pytest.mark.skipif(not TENSEAL_AVAILABLE, reason="tenseal not installed")
def test_encrypt_decrypt_roundtrip():
    """Encrypt values, decrypt, verify within 0.01."""
    ctx = ts.context(ts.SCHEME_TYPE.CKKS, 8192, coeff_mod_bit_sizes=[60, 40, 40, 60])
    ctx.global_scale = 2**40
    ctx.generate_galois_keys()
    plain = [1.0, 2.0, 3.0, 4.0, 5.0]
    enc = ts.ckks_vector(ctx, plain)
    dec = enc.decrypt()
    for i, (p, d) in enumerate(zip(plain, dec)):
        assert abs(p - d) < 0.01, f"Index {i}: expected {p}, got {d}"


@pytest.mark.skipif(not TENSEAL_AVAILABLE, reason="tenseal not installed")
def test_mean_computation():
    """Known values: run mean algorithm, verify result within tolerance."""
    from app.services.he_service import run_computation
    values = [10.0, 20.0, 30.0, 40.0, 50.0]
    expected_mean = sum(values) / len(values)  # 30.0
    bundle = _make_simple_bundle(values)
    result = run_computation(bundle, "mean", ["col1"])
    assert "mean" in result
    assert abs(result["mean"] - expected_mean) < 0.5


@pytest.mark.skipif(not TENSEAL_AVAILABLE, reason="tenseal not installed")
def test_correlation_computation():
    """Verify correlation result against numpy reference."""
    from app.services.he_service import run_computation
    a = [1.0, 2.0, 3.0, 4.0, 5.0]
    b = [2.0, 4.0, 5.0, 4.0, 6.0]
    bundle = _make_two_column_bundle(a, b)
    result = run_computation(bundle, "correlation", ["a", "b"])
    assert "correlation" in result
    expected = np.corrcoef(a, b)[0, 1]
    assert abs(result["correlation"] - expected) < 0.1


@pytest.mark.skipif(not TENSEAL_AVAILABLE, reason="tenseal not installed")
def test_ciphertext_size_reasonable():
    """Ciphertext size is not absurdly large for a small vector."""
    bundle = _make_simple_bundle([1.0, 2.0, 3.0] * 10)
    raw = bundle["vectors"]["col1"]
    size_bytes = len(raw) if isinstance(raw, bytes) else len(pickle.dumps(raw))
    assert size_bytes < 10 * 1024 * 1024, "Ciphertext should be under 10 MB for small vector"
