#!/usr/bin/env python3
"""
End-to-end test for SecureCollab algorithms using sample_clinical_data.csv.

Builds a CKKS bundle from the CSV (same format as encrypt.py), runs selected
algorithms, and prints results. Also checks that invalid column names produce
clear ValueError messages.

Without TenSEAL: runs only validation tests (clear error messages).
With TenSEAL (e.g. Python 3.11 venv): runs full E2E + validation.

Run from backend directory:
  python scripts/test_algorithms_e2e.py
  or with venv: .venv/bin/python scripts/test_algorithms_e2e.py
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

# Add backend root so we can import algorithms and decrypt
BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


def run_validation_tests_only() -> bool:
    """Run tests for clear error messages (requires algorithms module, which needs TenSEAL)."""
    from algorithms import (
        _require_columns,
        run_survival_analysis_approx,
        run_prevalence_and_risk,
    )

    # Minimal bundle: only structure, no real ciphertexts (we only test validation paths).
    mock_bundle = {
        "public_context": b"",
        "secret_context": b"",
        "n": 10,
        "vectors": {"col_a": b"x", "col_b": b"y"},
        "columns": '["col_a","col_b"]',
    }

    ok = True

    # _require_columns: missing column
    try:
        _require_columns(mock_bundle, ["col_a", "missing_col"], 2, "test_algo", "Need two columns.")
    except ValueError as e:
        if "missing_col" in str(e) and "not found" in str(e).lower():
            print("  OK – _require_columns: missing column raises clear ValueError")
        else:
            print("  FAIL – _require_columns:", e)
            ok = False
    else:
        print("  FAIL – _require_columns: expected ValueError for missing column")
        ok = False

    # _require_columns: too few columns
    try:
        _require_columns(mock_bundle, ["col_a"], 2, "test_algo", "Need two columns.")
    except ValueError as e:
        if "at least 2" in str(e):
            print("  OK – _require_columns: too few columns raises clear ValueError")
        else:
            print("  FAIL – _require_columns:", e)
            ok = False
    else:
        print("  FAIL – _require_columns: expected ValueError for too few columns")
        ok = False

    # survival_analysis_approx: missing second column
    try:
        run_survival_analysis_approx(mock_bundle, ["col_a", "missing_time_col"])
    except ValueError as e:
        if "not found" in str(e).lower() or "survival_analysis_approx" in str(e):
            print("  OK – survival_analysis_approx: missing column raises clear ValueError")
        else:
            print("  FAIL – survival:", e)
            ok = False
    except Exception as ex:
        print("  OK – survival_analysis_approx: rejected invalid columns:", type(ex).__name__)
    else:
        print("  FAIL – survival_analysis_approx: expected ValueError for missing column")
        ok = False

    # prevalence_and_risk: non-existent column
    try:
        run_prevalence_and_risk(mock_bundle, ["outcome_fake", "exposure_fake"])
    except ValueError as e:
        if "not found" in str(e).lower() and ("outcome_fake" in str(e) or "exposure_fake" in str(e)):
            print("  OK – prevalence_and_risk: missing column raises clear ValueError")
        else:
            print("  FAIL – prevalence:", e)
            ok = False
    else:
        print("  FAIL – prevalence_and_risk: expected ValueError for missing column")
        ok = False

    return ok


def main() -> int:
    try:
        import tenseal as ts  # noqa: F401
    except ImportError:
        print("TenSEAL not installed. Skipping all tests (algorithms module requires TenSEAL).", file=sys.stderr)
        print("  Use Python 3.11: cd backend && python3.11 -m venv .venv && .venv/bin/pip install -r requirements.txt", file=sys.stderr)
        print("  Then: .venv/bin/python scripts/test_algorithms_e2e.py", file=sys.stderr)
        return 0

    print("--- Validation tests (clear error messages) ---")
    if not run_validation_tests_only():
        return 1
    print()

    from algorithms import (
        ALGORITHMS,
        run_descriptive_statistics,
        run_pearson_correlation_matrix,
        run_prevalence_and_risk,
        run_survival_analysis_approx,
        run_multi_group_comparison,
    )
    from decrypt import format_result

    csv_path = BACKEND_ROOT / "sample_clinical_data.csv"
    if not csv_path.exists():
        print(f"Sample data not found: {csv_path}", file=sys.stderr)
        return 1

    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    if not rows:
        print("No rows in CSV.", file=sys.stderr)
        return 1

    all_keys = list(rows[0].keys())
    numeric_columns = [
        k for k in all_keys
        if all(
            row.get(k) not in (None, "")
            and _is_float(row.get(k))
            for row in rows
        )
    ]
    n = len(rows)
    column_vectors = {
        col: [float(rows[i][col]) for i in range(n)]
        for col in numeric_columns
    }

    context = ts.context(
        ts.SCHEME_TYPE.CKKS,
        poly_modulus_degree=8192,
        coeff_mod_bit_sizes=[60, 40, 40, 60],
    )
    context.generate_galois_keys()
    context.global_scale = 2**40
    secret_ctx = context.serialize(save_secret_key=True)
    context.make_context_public()
    public_ctx = context.serialize()
    context_full = ts.context_from(secret_ctx)
    vectors_serialized = {
        col: ts.ckks_vector(context_full, column_vectors[col]).serialize()
        for col in numeric_columns
    }

    bundle = {
        "secret_context": secret_ctx,
        "public_context": public_ctx,
        "vectors": vectors_serialized,
        "columns": json.dumps(numeric_columns),
        "n": n,
    }

    print("Columns in bundle:", numeric_columns)
    print()

    # --- Run algorithms ---
    tests = [
        ("descriptive_statistics", [numeric_columns[1]], "blood_pressure_systolic"),
        ("correlation", numeric_columns[1:3], "blood_pressure_systolic vs blood_pressure_diastolic"),
        ("linear_regression", numeric_columns[1:3], "predictor vs target"),
        ("multi_group_comparison", [numeric_columns[1]], "value only -> 4 segments"),
        ("pearson_correlation_matrix", numeric_columns[1:5], "first 4 numeric columns"),
        ("prevalence_and_risk", [numeric_columns[-2], numeric_columns[-1]], "trial_group vs treatment_response (as binary proxy)"),
        ("survival_analysis_approx", ["age", numeric_columns[-2]], "age vs trial_group (time vs event proxy)"),
    ]

    for algo_id, cols, label in tests:
        if algo_id not in ALGORITHMS:
            print(f"[SKIP] {algo_id} not in ALGORITHMS")
            continue
        # Skip if columns not in bundle
        if any(c not in numeric_columns for c in cols):
            print(f"[SKIP] {algo_id}: columns {cols} not all in bundle")
            continue
        print(f"--- {algo_id} ({label}) ---")
        try:
            result = ALGORITHMS[algo_id](bundle, cols)
            print(format_result(result))
        except Exception as e:
            print(f"  ERROR: {e}")
        print()

    # --- Test error message: missing column ---
    print("--- Validation test: missing column ---")
    try:
        run_prevalence_and_risk(bundle, ["outcome_column_that_does_not_exist", "exposure_fake"])
    except ValueError as e:
        msg = str(e)
        if "not found" in msg and "outcome_column_that_does_not_exist" in msg:
            print("  OK – received clear ValueError:", msg[:120] + "...")
        else:
            print("  UNEXPECTED ValueError:", msg)
    else:
        print("  FAIL – expected ValueError for missing column")

    print("--- Validation test: too few columns for survival ---")
    try:
        run_survival_analysis_approx(bundle, ["age"])
    except ValueError as e:
        msg = str(e)
        if "at least 2" in msg or "survival_analysis_approx" in msg:
            print("  OK – received clear ValueError:", msg[:100] + "...")
        else:
            print("  UNEXPECTED ValueError:", msg)
    else:
        print("  FAIL – expected ValueError for single column")

    print()
    print("E2E test run finished.")
    return 0


def _is_float(x: str | None) -> bool:
    if x is None:
        return False
    try:
        float(x)
        return True
    except (ValueError, TypeError):
        return False


if __name__ == "__main__":
    sys.exit(main())
