# SPDX-License-Identifier: Apache-2.0
#!/usr/bin/env python3
"""
Liest eine CSV, erkennt alle numerischen Spalten, verschlüsselt jede Spalte
als eigenen CKKS-Vektor und speichert encrypted.bin (Context + Vektoren-Dict + Spaltenliste).
"""
import csv
import json
import pickle
import sys
from pathlib import Path

import tenseal as ts


def is_numeric_column(rows: list[dict], key: str) -> bool:
    """Prüft ob eine Spalte in allen Zeilen numerische Werte hat."""
    for row in rows:
        val = row.get(key, "")
        if val is None or val == "":
            return False
        try:
            float(val)
        except (ValueError, TypeError):
            return False
    return True


def main():
    csv_path = Path("sample_clinical_data.csv")
    out_path = Path("encrypted.bin")
    if len(sys.argv) >= 2:
        csv_path = Path(sys.argv[1])
    if len(sys.argv) >= 3:
        out_path = Path(sys.argv[2])

    if not csv_path.exists():
        print(f"Fehler: {csv_path} nicht gefunden.", file=sys.stderr)
        sys.exit(1)

    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    if not rows:
        print("Fehler: Keine Daten in CSV.", file=sys.stderr)
        sys.exit(1)

    all_keys = list(rows[0].keys())
    numeric_columns = [k for k in all_keys if is_numeric_column(rows, k)]
    if not numeric_columns:
        print("Fehler: Keine numerischen Spalten gefunden.", file=sys.stderr)
        sys.exit(1)

    n = len(rows)
    column_vectors = {col: [float(rows[i][col]) for i in range(n)] for col in numeric_columns}

    print("Gefundene und verschlüsselte Spalten:", ", ".join(numeric_columns))

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
    vectors_serialized = {}
    for col in numeric_columns:
        enc_vec = ts.ckks_vector(context_full, column_vectors[col])
        vectors_serialized[col] = enc_vec.serialize()

    bundle = {
        "secret_context": secret_ctx,
        "public_context": public_ctx,
        "vectors": vectors_serialized,
        "columns": json.dumps(numeric_columns),
        "n": n,
    }
    with open(out_path, "wb") as f:
        pickle.dump(bundle, f)

    print(f"Encrypted {len(numeric_columns)} columns, {n} rows -> {out_path}")
    print("Columns JSON (für Upload Form-Feld 'columns'):")
    print(json.dumps(numeric_columns))


if __name__ == "__main__":
    main()
