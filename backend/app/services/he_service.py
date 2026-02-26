# SPDX-License-Identifier: Apache-2.0
"""Homomorphic encryption operations: run algorithms on encrypted bundles."""
from __future__ import annotations

import json
import pickle
from pathlib import Path
from typing import Any

from algorithms import ALGORITHMS


def run_computation(
    bundle: dict[str, Any] | str | Path,
    algorithm: str,
    selected_columns: list[str] | None = None,
    parameters: dict | None = None,
) -> dict[str, Any]:
    """
    Run a registered HE algorithm on an encrypted bundle.
    bundle: either a dict (in-memory) or path to a .bin file.
    """
    if algorithm not in ALGORITHMS:
        raise ValueError(f"Unknown algorithm: {algorithm}. Allowed: {list(ALGORITHMS.keys())}")
    if isinstance(bundle, (str, Path)):
        with open(bundle, "rb") as f:
            bundle = pickle.load(f)
    if selected_columns is None:
        selected_columns = []
    if "vectors" in bundle and not selected_columns:
        try:
            cols = json.loads(bundle.get("columns", "[]"))
        except (json.JSONDecodeError, TypeError):
            cols = list(bundle.get("vectors", {}).keys())
        if algorithm in ("correlation", "linear_regression", "prevalence_and_risk", "survival_analysis_approx"):
            selected_columns = cols[:2]
        elif algorithm == "pearson_correlation_matrix":
            selected_columns = cols[: min(6, len(cols))]
        elif algorithm in ("logistic_regression_approx", "multi_group_comparison", "subgroup_analysis"):
            selected_columns = cols[: min(6, len(cols))]
        elif algorithm == "federated_mean_aggregation":
            selected_columns = cols[:2] if len(cols) >= 2 else cols[:1]
        else:
            selected_columns = cols[:1]
    return ALGORITHMS[algorithm](bundle, selected_columns)
