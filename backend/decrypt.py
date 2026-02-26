# SPDX-License-Identifier: Apache-2.0
#!/usr/bin/env python3
"""
Liest result.json (oder result_encrypted.bin bei alter Pipeline),
entschlüsselt ggf. und formatiert result_json für die Ausgabe.
"""
import json
import pickle
import sys
from pathlib import Path

import tenseal as ts


def decrypt_result_from_bundle(secret_context_bytes: bytes, result_encrypted_bytes: bytes) -> float:
    """Entschlüsselt pickled serialisierten Ergebnis-Vektor -> Float (Legacy)."""
    context = ts.context_from(secret_context_bytes)
    serialized_vector = pickle.loads(result_encrypted_bytes)
    result_vec = ts.lazy_ckks_vector_from(serialized_vector)
    result_vec.link_context(context)
    decrypted = result_vec.decrypt()
    return float(decrypted[0])


def format_result(data: dict) -> str:
    """Formatiert result_json für die Konsolenausgabe (alle Algorithmen)."""
    lines = ["========== Ergebnis (auf verschlüsselten Daten berechnet) =========="]
    if "mean" in data and "n" in data and len(data) > 2:
        for k in ("mean", "std_dev", "variance", "min", "max", "iqr_approx", "skewness_approx", "n"):
            if k in data:
                lines.append(f"  {k}: {data[k]}")
    elif "mean" in data and len(data) == 1:
        lines.append(f"  Mittelwert: {data['mean']}")
    elif "mean" in data or "std_dev" in data:
        for k in ("mean", "std_dev", "min", "max"):
            if k in data:
                lines.append(f"  {k}: {data[k]}")
    elif "groups" in data and "pairwise_differences" in data:
        lines.append("  Gruppen:")
        for g in data.get("groups", []):
            lines.append(f"    {g.get('name', '')}: mean={g.get('mean')}, std_dev={g.get('std_dev')}, n={g.get('n')}")
        lines.append("  Paarweise Differenzen:")
        for p in data.get("pairwise_differences", []):
            lines.append(f"    {p.get('group_a')} vs {p.get('group_b')}: {p.get('difference')}")
    elif "correlation" in data:
        lines.append(f"  Korrelation ({data.get('column1', '')} vs {data.get('column2', '')}): {data['correlation']}")
    elif "matrix" in data and "strongest_correlations" in data:
        lines.append("  Stärkste Korrelationen:")
        for s in data.get("strongest_correlations", [])[:5]:
            lines.append(f"    {s.get('col_a')} vs {s.get('col_b')}: r={s.get('r')} ({s.get('interpretation', '')})")
    elif "group1_mean" in data:
        lines.append(f"  Gruppe 1 (Mittelwert): {data['group1_mean']}")
        lines.append(f"  Gruppe 2 (Mittelwert): {data['group2_mean']}")
        lines.append(f"  Differenz: {data['difference']}")
    elif "coefficients" in data and "intercept" in data:
        lines.append("  Koeffizienten (approx.): " + str(data.get("coefficients", {})))
        lines.append(f"  Intercept: {data['intercept']}")
    elif "slope" in data:
        lines.append(f"  Steigung: {data['slope']}")
        lines.append(f"  Intercept: {data['intercept']}")
        lines.append(f"  Prädiktor: {data.get('predictor', '')}, Ziel: {data.get('target', '')}")
    elif "median_survival_approx" in data:
        lines.append(f"  Median Survival (approx.): {data.get('median_survival_approx')}")
        lines.append(f"  Hazard Rate: {data.get('hazard_rate', '')}")
    elif "prevalence" in data:
        lines.append(f"  Prävalenz: {data.get('prevalence')}")
        lines.append(f"  Relative Risk: {data.get('relative_risk')}")
        lines.append(f"  Odds Ratio: {data.get('odds_ratio')}")
    elif "global_mean" in data or "weighted_mean" in data:
        lines.append(f"  Global Mean: {data.get('global_mean')}")
        lines.append(f"  Weighted Mean: {data.get('weighted_mean')}")
        lines.append(f"  Total n: {data.get('total_n')}")
    elif "subgroups" in data:
        for s in data.get("subgroups", []):
            lines.append(f"  {s.get('name', '')}: mean={s.get('mean')}, std_dev={s.get('std_dev')}, n_approx={s.get('n_approx')}")
    elif "buckets" in data:
        lines.append("  Verteilung (Buckets):")
        for b in data["buckets"]:
            lines.append(f"    {b.get('range', '')}: {b.get('count', 0)}")
    else:
        for k, v in data.items():
            lines.append(f"  {k}: {v}")
    lines.append("")
    lines.append("(Berechnet auf verschlüsselten Daten – Rohdaten wurden nie entschlüsselt.)")
    return "\n".join(lines)


def main():
    result_path = Path("result.json")
    encrypted_bin_path = Path("encrypted.bin")
    if len(sys.argv) >= 2:
        result_path = Path(sys.argv[1])
    if len(sys.argv) >= 3:
        encrypted_bin_path = Path(sys.argv[2])

    if result_path.exists():
        with open(result_path, encoding="utf-8") as f:
            data = json.load(f)
        print(format_result(data))
        return

    result_bin = Path("result_encrypted.bin")
    if result_bin.exists() and encrypted_bin_path.exists():
        with open(encrypted_bin_path, "rb") as f:
            bundle = pickle.load(f)
        with open(result_bin, "rb") as f:
            raw = f.read()
        mean_val = decrypt_result_from_bundle(bundle["secret_context"], raw)
        print(format_result({"mean": mean_val}))
        return

    print(f"Fehler: Weder {result_path} noch {result_bin} gefunden.", file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    main()
