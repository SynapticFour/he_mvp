# SPDX-License-Identifier: Apache-2.0
#!/usr/bin/env python3
"""
Liest encrypted.bin, führt den gewählten Algorithmus auf den gewählten Spalten aus
und schreibt result.json (entschlüsseltes result_json).
Parameter: algorithm (str), selected_columns (JSON-Array).
"""
import json
import pickle
import sys
from pathlib import Path

from algorithms import ALGORITHMS


def main():
    in_path = Path("encrypted.bin")
    out_path = Path("result.json")
    algorithm = "mean"
    selected_columns = []

    args = sys.argv[1:]
    if args:
        algorithm = args[0]
    if len(args) >= 2:
        try:
            selected_columns = json.loads(args[1])
            if not isinstance(selected_columns, list):
                selected_columns = [str(selected_columns)]
        except (json.JSONDecodeError, TypeError):
            selected_columns = []
    if len(args) >= 3:
        in_path = Path(args[2])
    if len(args) >= 4:
        out_path = Path(args[3])

    if not in_path.exists():
        print(f"Fehler: {in_path} nicht gefunden.", file=sys.stderr)
        sys.exit(1)

    with open(in_path, "rb") as f:
        bundle = pickle.load(f)

    if algorithm not in ALGORITHMS:
        print(f"Unbekannter Algorithmus: {algorithm}. Erlaubt: {list(ALGORITHMS.keys())}", file=sys.stderr)
        sys.exit(1)

    if "vectors" in bundle and not selected_columns:
        try:
            cols = json.loads(bundle.get("columns", "[]"))
        except (json.JSONDecodeError, TypeError):
            cols = list(bundle["vectors"].keys())
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

    try:
        result = ALGORITHMS[algorithm](bundle, selected_columns)
    except Exception as e:
        print(f"Berechnung fehlgeschlagen: {e}", file=sys.stderr)
        sys.exit(1)

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    print(f"Algorithmus '{algorithm}' ausgeführt -> {out_path}")
    print("result_json:")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
