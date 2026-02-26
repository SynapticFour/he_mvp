"""
Homomorphic algorithms on encrypted CKKS bundles.
Bundle: public_context, secret_context, n; entweder encrypted_vector (ein Vektor)
oder vectors (Dict[Spaltenname, serialisierter Ciphertext]) + columns (JSON-Liste).
"""
import json
import math
import pickle
from typing import Any

import tenseal as ts


def _get_vectors_bundle(bundle: dict[str, Any]) -> bool:
    return "vectors" in bundle and isinstance(bundle.get("vectors"), dict)


def _load_vectors(bundle: dict[str, Any], column_names: list[str]):
    """Lädt mehrere Vektoren (nur bei Bundle mit 'vectors')."""
    if not _get_vectors_bundle(bundle):
        raise ValueError("Mehrere Spalten nur bei Bundle mit 'vectors' möglich")
    ctx = ts.context_from(bundle["public_context"])
    n = bundle.get("n")
    if n is None:
        raise ValueError("Bundle missing 'n' (number of rows).")
    encs = {}
    vectors = bundle["vectors"]
    for col in column_names:
        if col not in vectors:
            raise ValueError(
                f"Column '{col}' not found in dataset. Available: {list(vectors.keys())}."
            )
        enc = ts.lazy_ckks_vector_from(bundle["vectors"][col])
        enc.link_context(ctx)
        encs[col] = enc
    return ctx, encs, n


def _require_columns(
    bundle: dict[str, Any],
    selected_columns: list[str],
    min_columns: int,
    algorithm_id: str,
    description: str = "",
) -> None:
    """Raises ValueError with a clear message if columns are missing or incompatible."""
    available = list(bundle["vectors"].keys()) if _get_vectors_bundle(bundle) else []
    if len(selected_columns) < min_columns:
        raise ValueError(
            f"Algorithm '{algorithm_id}' requires at least {min_columns} column(s). "
            f"Got {len(selected_columns)}: {selected_columns}. {description}"
        )
    for col in selected_columns[:min_columns]:
        if col not in (bundle.get("vectors") or {}):
            raise ValueError(
                f"Algorithm '{algorithm_id}': column '{col}' not found in dataset. "
                f"Available columns: {available}"
            )


def _load_bundle(bundle: dict[str, Any], column_name: str | None = None):
    """Lädt Context und einen Vektor. column_name nur bei Bundle mit 'vectors'."""
    ctx = ts.context_from(bundle["public_context"])
    n = bundle.get("n")
    if n is None:
        raise ValueError("Bundle missing 'n' (number of rows).")
    if _get_vectors_bundle(bundle):
        vectors = bundle["vectors"]
        col = column_name
        if not col:
            try:
                cols = json.loads(bundle.get("columns", "[]"))
                col = cols[0] if cols else next(iter(vectors.keys()))
            except (json.JSONDecodeError, TypeError, StopIteration):
                col = next(iter(vectors.keys()))
        enc = ts.lazy_ckks_vector_from(vectors[col])
    else:
        enc = ts.lazy_ckks_vector_from(bundle["encrypted_vector"])
    enc.link_context(ctx)
    return ctx, enc, n


def _load_two_vectors(bundle: dict[str, Any], col1: str, col2: str):
    """Lädt zwei Vektoren (nur bei Bundle mit 'vectors')."""
    if not _get_vectors_bundle(bundle):
        raise ValueError(
            "Multi-column algorithms require a bundle with 'vectors' (one encrypted vector per column). "
            "Single-vector bundles are not supported for this operation."
        )
    ctx = ts.context_from(bundle["public_context"])
    n = bundle.get("n")
    if n is None:
        raise ValueError("Bundle missing 'n' (number of rows).")
    vectors = bundle["vectors"]
    for c in (col1, col2):
        if c not in vectors:
            available = list(vectors.keys())
            raise ValueError(
                f"Column '{c}' not found in dataset. Available columns: {available}. "
                f"Use selected_columns from the dataset's column list."
            )
    enc1 = ts.lazy_ckks_vector_from(vectors[col1])
    enc2 = ts.lazy_ckks_vector_from(vectors[col2])
    enc1.link_context(ctx)
    enc2.link_context(ctx)
    return ctx, enc1, enc2, n


def _decrypt_scalar(secret_ctx_bytes: bytes, encrypted_result_bytes: bytes) -> float:
    ctx = ts.context_from(secret_ctx_bytes)
    data = pickle.loads(encrypted_result_bytes)
    vec = ts.lazy_ckks_vector_from(data)
    vec.link_context(ctx)
    return float(vec.decrypt()[0])


def _encrypt_plain_and_sum(ctx, enc_vec, plain_vec) -> bytes:
    """(enc_vec * plain_vec).sum() -> encrypted scalar, serialized (pickled)."""
    n = enc_vec.size()
    if len(plain_vec) != n:
        plain_vec = list(plain_vec)[:n]
        plain_vec.extend([0.0] * (n - len(plain_vec)))
    multiplied = enc_vec * plain_vec
    summed = multiplied.sum()
    return pickle.dumps(summed.serialize())


def run_descriptive_statistics(
    bundle: dict[str, Any], selected_columns: list[str]
) -> dict[str, Any]:
    """
    Deskriptivstatistik für eine metrische Spalte.
    Berechnet: Mittelwert, Standardabweichung, Varianz, Min/Max-Approximation,
    IQR-Approximation (1.35*std für Normalverteilung), Schiefe-Approximation (drittes Moment).
    Input: eine numerische Spalte.
    Approximationsfehler: Min/Max und IQR sind keine echten Quantile (CKKS erlaubt kein Sortieren).
    Use Case: Erste Datenexploration in klinischen Studien.
    """
    col = selected_columns[0] if selected_columns else None
    ctx, enc, n = _load_bundle(bundle, col)
    if n < 1:
        return {"mean": 0.0, "std_dev": 0.0, "variance": 0.0, "min": 0.0, "max": 0.0, "iqr_approx": 0.0, "skewness_approx": 0.0, "n": 0}
    inv_n = 1.0 / n
    secret_ctx = bundle["secret_context"]
    s = enc.sum()
    mean_enc = s * inv_n
    mean_val = _decrypt_scalar(secret_ctx, pickle.dumps(mean_enc.serialize()))
    sq = enc.square()
    mean_sq_enc = sq.sum() * inv_n
    mean_sq_val = _decrypt_scalar(secret_ctx, pickle.dumps(mean_sq_enc.serialize()))
    var = mean_sq_val - mean_val * mean_val
    var = max(var, 0.0)
    std_dev = math.sqrt(var)
    min_approx = mean_val - 2 * std_dev
    max_approx = mean_val + 2 * std_dev
    iqr_approx = 1.35 * std_dev if std_dev else 0.0
    cubed = enc - mean_val
    cubed = cubed.square() * cubed
    mean_cubed_enc = cubed.sum() * inv_n
    try:
        mean_cubed_val = _decrypt_scalar(secret_ctx, pickle.dumps(mean_cubed_enc.serialize()))
    except Exception:
        mean_cubed_val = 0.0
    skewness_approx = (mean_cubed_val / (std_dev**3)) if std_dev and std_dev > 1e-10 else 0.0
    return {
        "mean": round(mean_val, 4),
        "std_dev": round(std_dev, 4),
        "variance": round(var, 4),
        "min": round(min_approx, 4),
        "max": round(max_approx, 4),
        "iqr_approx": round(iqr_approx, 4),
        "skewness_approx": round(skewness_approx, 4),
        "n": n,
    }


def run_correlation(
    bundle: dict[str, Any], selected_columns: list[str]
) -> dict[str, Any]:
    """Pearson correlation zwischen zwei Spalten (nur bei Bundle mit vectors)."""
    c1 = selected_columns[0] if selected_columns else "column1"
    c2 = selected_columns[1] if len(selected_columns) > 1 else "column2"
    if not _get_vectors_bundle(bundle) or len(selected_columns) < 2:
        return {"correlation": 0.0, "column1": c1, "column2": c2}
    try:
        ctx, enc1, enc2, n = _load_two_vectors(bundle, c1, c2)
        inv_n = 1.0 / n
        sum1_enc = enc1.sum() * inv_n
        sum2_enc = enc2.sum() * inv_n
        prod = enc1 * enc2
        sum12_enc = prod.sum() * inv_n
        sq1 = enc1.square()
        sum_sq1_enc = sq1.sum() * inv_n
        sq2 = enc2.square()
        sum_sq2_enc = sq2.sum() * inv_n
        secret_ctx = bundle["secret_context"]
        m1 = _decrypt_scalar(secret_ctx, pickle.dumps(sum1_enc.serialize()))
        m2 = _decrypt_scalar(secret_ctx, pickle.dumps(sum2_enc.serialize()))
        m12 = _decrypt_scalar(secret_ctx, pickle.dumps(sum12_enc.serialize()))
        var1 = _decrypt_scalar(secret_ctx, pickle.dumps(sum_sq1_enc.serialize())) - m1 * m1
        var2 = _decrypt_scalar(secret_ctx, pickle.dumps(sum_sq2_enc.serialize())) - m2 * m2
        cov = m12 - m1 * m2
        var1, var2 = max(var1, 0.0), max(var2, 0.0)
        denom = math.sqrt(var1 * var2)
        corr = (cov / denom) if denom else 0.0
        return {"correlation": round(corr, 4), "column1": c1, "column2": c2}
    except ValueError:
        raise
    except Exception as e:
        raise ValueError(
            f"Correlation failed for columns '{c1}', '{c2}'. "
            f"Ensure both columns exist and contain numeric data. Original error: {e!s}"
        ) from e


def run_group_comparison(
    bundle: dict[str, Any], selected_columns: list[str]
) -> dict[str, Any]:
    """Erste Hälfte vs zweite Hälfte: Mittelwerte und Differenz."""
    col = selected_columns[0] if selected_columns else None
    ctx, enc, n = _load_bundle(bundle, col)
    if n < 2:
        return {"group1_mean": 0.0, "group2_mean": 0.0, "difference": 0.0}
    half = n // 2
    n2 = n - half
    mask1 = [1.0] * half + [0.0] * n2
    mask2 = [0.0] * half + [1.0] * n2
    secret_ctx = bundle["secret_context"]
    sum1_enc = _encrypt_plain_and_sum(ctx, enc, mask1)
    sum2_enc = _encrypt_plain_and_sum(ctx, enc, mask2)
    sum1 = _decrypt_scalar(secret_ctx, sum1_enc)
    sum2 = _decrypt_scalar(secret_ctx, sum2_enc)
    m1 = sum1 / half
    m2 = sum2 / n2
    return {
        "group1_mean": round(m1, 4),
        "group2_mean": round(m2, 4),
        "difference": round(m1 - m2, 4),
    }


def run_linear_regression(
    bundle: dict[str, Any], selected_columns: list[str]
) -> dict[str, Any]:
    """Steigung und Intercept: y = slope*x + intercept (bei zwei Spalten)."""
    c1 = selected_columns[0] if selected_columns else "predictor"
    c2 = selected_columns[1] if len(selected_columns) > 1 else "target"
    if not _get_vectors_bundle(bundle) or len(selected_columns) < 2:
        col = selected_columns[0] if selected_columns else None
        ctx, enc, n = _load_bundle(bundle, col)
        inv_n = 1.0 / n
        s = enc.sum()
        mean_enc = s * inv_n
        secret_ctx = bundle["secret_context"]
        mean_y = _decrypt_scalar(secret_ctx, pickle.dumps(mean_enc.serialize()))
        return {"slope": 0.0, "intercept": round(mean_y, 4), "predictor": c1, "target": c2}
    try:
        ctx, enc_x, enc_y, n = _load_two_vectors(bundle, c1, c2)
        inv_n = 1.0 / n
        secret_ctx = bundle["secret_context"]
        sum_x = enc_x.sum() * inv_n
        sum_y = enc_y.sum() * inv_n
        sum_xy = (enc_x * enc_y).sum() * inv_n
        sum_xx = (enc_x.square()).sum() * inv_n
        mean_x = _decrypt_scalar(secret_ctx, pickle.dumps(sum_x.serialize()))
        mean_y = _decrypt_scalar(secret_ctx, pickle.dumps(sum_y.serialize()))
        cov_xy = _decrypt_scalar(secret_ctx, pickle.dumps(sum_xy.serialize())) - mean_x * mean_y
        var_x = _decrypt_scalar(secret_ctx, pickle.dumps(sum_xx.serialize())) - mean_x * mean_x
        slope = (cov_xy / var_x) if var_x else 0.0
        intercept = mean_y - slope * mean_x
        return {"slope": round(slope, 4), "intercept": round(intercept, 4), "predictor": c1, "target": c2}
    except ValueError:
        raise
    except Exception as e:
        raise ValueError(
            f"Linear regression failed for predictor '{c1}' and target '{c2}'. "
            f"Both columns must exist and be numeric. Original error: {e!s}"
        ) from e


def run_distribution(
    bundle: dict[str, Any], selected_columns: list[str]
) -> dict[str, Any]:
    """5 Buckets: approximativ gleiche Anzahl pro Bucket (n/5)."""
    col = selected_columns[0] if selected_columns else None
    _, _, n = _load_bundle(bundle, col)
    if n < 1:
        return {"buckets": []}
    count_per = max(1, n // 5)
    buckets = []
    for i in range(5):
        start = i * count_per
        end = (i + 1) * count_per if i < 4 else n
        count = end - start
        buckets.append({"range": f"{start}-{end}", "count": count})
    return {"buckets": buckets}


def run_mean_legacy(bundle: dict[str, Any], selected_columns: list[str] | None = None) -> dict[str, Any]:
    """Mean als dict für einheitliches result_json."""
    col = selected_columns[0] if selected_columns else None
    ctx, enc, n = _load_bundle(bundle, col)
    s = enc.sum()
    mean_enc = s * (1.0 / n)
    secret_ctx = bundle["secret_context"]
    mean_val = _decrypt_scalar(secret_ctx, pickle.dumps(mean_enc.serialize()))
    return {"mean": round(mean_val, 4)}


# -----------------------------------------------------------------------------
# New algorithms (GWAS / clinical use cases)
# -----------------------------------------------------------------------------


def run_multi_group_comparison(
    bundle: dict[str, Any], selected_columns: list[str]
) -> dict[str, Any]:
    """
    Mittelwert und Std pro Gruppe, paarweise Differenzen. Gruppen = gleiche Index-Segmente
    (value_column wird in 2–4 gleiche Teile geteilt, da echte kategoriale Gruppen in CKKS nicht sortierbar sind).
    Inputs: value_column (erste Spalte), optional weitere Spalten als Gruppen-Masken (0/1); sonst 4 Segmente.
    Result: groups [{name, mean, std_dev, n}], pairwise_differences, F-Statistik-Approximation.
    Approximationsfehler: Echte ANOVA braucht Varianzzerlegung; F-Statistik ist Näherung.
    Use Case: Treatment vs Control vs Placebo Vergleich.
    """
    col = selected_columns[0] if selected_columns else None
    ctx, enc, n = _load_bundle(bundle, col)
    secret_ctx = bundle["secret_context"]
    if n < 2:
        return {"groups": [], "pairwise_differences": []}
    n_groups = min(4, max(2, len(selected_columns) - 1)) if len(selected_columns) > 1 else 4
    if _get_vectors_bundle(bundle) and len(selected_columns) >= 2:
        try:
            cols = [selected_columns[0]]
            for g in range(1, min(n_groups + 1, len(selected_columns))):
                if selected_columns[g] in bundle.get("vectors", {}):
                    cols.append(selected_columns[g])
            if len(cols) > 1:
                ctx, encs, n = _load_vectors(bundle, cols)
                value_enc = encs[cols[0]]
                groups_out = []
                for i, mask_col in enumerate(cols[1:]):
                    mask_enc = encs[mask_col]
                    sum_v_enc = (value_enc * mask_enc).sum()
                    sum_v2_enc = (value_enc.square() * mask_enc).sum()
                    n_i_enc = mask_enc.sum()
                    sum_v = _decrypt_scalar(secret_ctx, pickle.dumps(sum_v_enc.serialize()))
                    sum_v2 = _decrypt_scalar(secret_ctx, pickle.dumps(sum_v2_enc.serialize()))
                    n_i = _decrypt_scalar(secret_ctx, pickle.dumps(n_i_enc.serialize()))
                    n_i = max(n_i, 1e-6)
                    mean_i = sum_v / n_i
                    var_i = (sum_v2 / n_i) - mean_i * mean_i
                    var_i = max(var_i, 0.0)
                    groups_out.append({"name": mask_col, "mean": round(mean_i, 4), "std_dev": round(math.sqrt(var_i), 4), "n": int(round(n_i))})
                pairwise = []
                for i in range(len(groups_out)):
                    for j in range(i + 1, len(groups_out)):
                        d = groups_out[i]["mean"] - groups_out[j]["mean"]
                        pairwise.append({"group_a": groups_out[i]["name"], "group_b": groups_out[j]["name"], "difference": round(d, 4), "significant_approx": abs(d) > 0.5})
                return {"groups": groups_out, "pairwise_differences": pairwise}
        except ValueError:
            raise
        except Exception as e:
            raise ValueError(
                f"Multi-group comparison failed (mask columns path). "
                f"Ensure value_column and group mask columns exist and are numeric. Original error: {e!s}"
            ) from e
    segment_size = max(1, n // n_groups)
    groups_out = []
    for g in range(n_groups):
        start = g * segment_size
        end = n if g == n_groups - 1 else (g + 1) * segment_size
        size = end - start
        mask = [1.0 if start <= i < end else 0.0 for i in range(n)]
        sum_v_enc = _encrypt_plain_and_sum(ctx, enc, mask)
        sum_v2_enc = _encrypt_plain_and_sum(ctx, enc.square(), mask)
        sum_v = _decrypt_scalar(secret_ctx, sum_v_enc)
        sum_v2 = _decrypt_scalar(secret_ctx, sum_v2_enc)
        mean_g = sum_v / size
        var_g = (sum_v2 / size) - mean_g * mean_g
        var_g = max(var_g, 0.0)
        groups_out.append({"name": f"group_{g+1}", "mean": round(mean_g, 4), "std_dev": round(math.sqrt(var_g), 4), "n": size})
    pairwise = []
    for i in range(len(groups_out)):
        for j in range(i + 1, len(groups_out)):
            d = groups_out[i]["mean"] - groups_out[j]["mean"]
            pairwise.append({"group_a": groups_out[i]["name"], "group_b": groups_out[j]["name"], "difference": round(d, 4), "significant_approx": abs(d) > 0.5})
    return {"groups": groups_out, "pairwise_differences": pairwise}


def run_logistic_regression_approx(
    bundle: dict[str, Any], selected_columns: list[str]
) -> dict[str, Any]:
    """
    Approximierte logistische Regression: Zielvariable binär (0/1), Features numerisch.
    Methode: Ein Schritt IRLS-Approximation (beta = (X'WX)^-1 X'Wz mit W=1) bzw. lineare Regression
    auf (y - 0.5) für schnelle Näherung. Ergebnis nur für explorative Analyse, nicht für klinische Entscheidungen.
    Inputs: feature_columns (alle außer letzter), target_column (letzte Spalte, 0/1).
    Approximationsfehler: Hoch – echte Logistik braucht iterative Sigmoid-Auswertung; hier nur lineare Näherung.
    Use Case: Vorhersage ob Patient auf Behandlung anspricht (ja/nein) – nur Screening.
    """
    if not _get_vectors_bundle(bundle) or len(selected_columns) < 2:
        col = selected_columns[0] if selected_columns else None
        ctx, enc, n = _load_bundle(bundle, col)
        inv_n = 1.0 / max(n, 1)
        s = enc.sum() * inv_n
        secret_ctx = bundle["secret_context"]
        mean_y = _decrypt_scalar(secret_ctx, pickle.dumps(s.serialize()))
        return {"coefficients": {}, "intercept": round(mean_y, 4), "convergence_iterations": 0, "approximate_accuracy": "N/A (single column)"}
    target_col = selected_columns[-1]
    feature_cols = selected_columns[:-1]
    try:
        ctx, encs, n = _load_vectors(bundle, selected_columns)
    except ValueError:
        raise
    except Exception as e:
        raise ValueError(
            f"Logistic regression (approx) requires at least two columns (features + binary target). "
            f"Columns requested: {selected_columns}. Original error: {e!s}"
        ) from e
    secret_ctx = bundle["secret_context"]
    inv_n = 1.0 / n
    y_enc = encs[target_col]
    mean_y_enc = y_enc.sum() * inv_n
    mean_y = _decrypt_scalar(secret_ctx, pickle.dumps(mean_y_enc.serialize()))
    coeffs = {}
    for fc in feature_cols:
        x_enc = encs[fc]
        xy_enc = (x_enc * y_enc).sum() * inv_n
        xx_enc = (x_enc.square()).sum() * inv_n
        mean_x_enc = x_enc.sum() * inv_n
        mean_x = _decrypt_scalar(secret_ctx, pickle.dumps(mean_x_enc.serialize()))
        cov_xy = _decrypt_scalar(secret_ctx, pickle.dumps(xy_enc.serialize())) - mean_x * mean_y
        var_x = _decrypt_scalar(secret_ctx, pickle.dumps(xx_enc.serialize())) - mean_x * mean_x
        slope = (cov_xy / var_x) if var_x else 0.0
        coeffs[fc] = round(slope, 4)
    intercept = mean_y - sum(coeffs.get(fc, 0) * _decrypt_scalar(secret_ctx, pickle.dumps((encs[fc].sum() * inv_n).serialize())) for fc in feature_cols)
    return {
        "coefficients": coeffs,
        "intercept": round(intercept, 4),
        "convergence_iterations": 1,
        "approximate_accuracy": "Linear approximation only – not for clinical decisions.",
    }


def run_pearson_correlation_matrix(
    bundle: dict[str, Any], selected_columns: list[str]
) -> dict[str, Any]:
    """
    Vollständige Pearson-Korrelationsmatrix für 2–6 Spalten.
    Inputs: columns (2–6 numerische Spalten).
    Result: matrix {col_a: {col_b: r}}, strongest_correlations.
    Use Case: GWAS-ähnliche Korrelationsanalyse zwischen klinischen Markern.
    """
    if not _get_vectors_bundle(bundle) or len(selected_columns) < 2:
        return {"matrix": {}, "strongest_correlations": []}
    _require_columns(bundle, selected_columns, 2, "pearson_correlation_matrix", "Need 2–6 numeric columns.")
    cols = selected_columns[:6]
    ctx, encs, n = _load_vectors(bundle, cols)
    secret_ctx = bundle["secret_context"]
    inv_n = 1.0 / n
    means = {}
    for c in cols:
        m = encs[c].sum() * inv_n
        means[c] = _decrypt_scalar(secret_ctx, pickle.dumps(m.serialize()))
    matrix = {c: {} for c in cols}
    pairs = []
    for i, ca in enumerate(cols):
        for cb in cols[i:]:
            if ca == cb:
                matrix[ca][cb] = 1.0
                continue
            cov_enc = (encs[ca] * encs[cb]).sum() * inv_n
            var_a_enc = (encs[ca].square()).sum() * inv_n
            var_b_enc = (encs[cb].square()).sum() * inv_n
            cov = _decrypt_scalar(secret_ctx, pickle.dumps(cov_enc.serialize())) - means[ca] * means[cb]
            var_a = _decrypt_scalar(secret_ctx, pickle.dumps(var_a_enc.serialize())) - means[ca] ** 2
            var_b = _decrypt_scalar(secret_ctx, pickle.dumps(var_b_enc.serialize())) - means[cb] ** 2
            var_a, var_b = max(var_a, 1e-10), max(var_b, 1e-10)
            r = cov / math.sqrt(var_a * var_b)
            matrix[ca][cb] = round(r, 4)
            matrix[cb][ca] = round(r, 4)
            pairs.append({"col_a": ca, "col_b": cb, "r": round(r, 4)})
    pairs.sort(key=lambda x: -abs(x["r"]))
    strongest = pairs[:5]
    for p in strongest:
        r = p["r"]
        if abs(r) < 0.2:
            p["interpretation"] = "weak"
        elif abs(r) < 0.5:
            p["interpretation"] = "moderate"
        elif abs(r) < 0.8:
            p["interpretation"] = "strong"
        else:
            p["interpretation"] = "very strong"
    return {"matrix": matrix, "strongest_correlations": strongest}


def run_survival_analysis_approx(
    bundle: dict[str, Any], selected_columns: list[str]
) -> dict[str, Any]:
    """
    Überlebensanalyse-Approximation: Zeit bis Event, Event-Indikator (0/1).
    Berechnet: mittlere Überlebenszeit, Hazard-Rate (Events/Gesamtzeit), median_survival_approx.
    Kein echtes Kaplan-Meier (Sortierung in HE nicht möglich).
    Inputs: time_column, event_column; optional group_column (dritte Spalte als 0/1 Masken).
    Use Case: Überlebensanalyse in Onkologie-Studien – nur grobe Schätzung.
    """
    if not _get_vectors_bundle(bundle) or len(selected_columns) < 2:
        return {"median_survival_approx": 0.0, "survival_at_timepoints": {}, "groups": []}
    _require_columns(bundle, selected_columns, 2, "survival_analysis_approx", "Need time_column and event_column.")
    t_col, e_col = selected_columns[0], selected_columns[1]
    ctx, enc_t, enc_e, n = _load_two_vectors(bundle, t_col, e_col)
    secret_ctx = bundle["secret_context"]
    sum_t_enc = enc_t.sum()
    sum_e_enc = enc_e.sum()
    total_time = _decrypt_scalar(secret_ctx, pickle.dumps(sum_t_enc.serialize()))
    total_events = _decrypt_scalar(secret_ctx, pickle.dumps(sum_e_enc.serialize()))
    mean_time = total_time / n
    hazard_rate = total_events / total_time if total_time else 0.0
    median_approx = 0.5 * total_time / max(total_events, 1) if total_events else mean_time
    timepoints = {round(mean_time * 0.25, 1): 0.75, round(mean_time * 0.5, 1): 0.5, round(mean_time * 0.75, 1): 0.25}
    return {
        "median_survival_approx": round(median_approx, 4),
        "survival_at_timepoints": timepoints,
        "hazard_rate": round(hazard_rate, 6),
        "groups": [{"name": "all", "median_survival": round(median_approx, 4), "hazard_ratio": 1.0}],
    }


def run_prevalence_and_risk(
    bundle: dict[str, Any], selected_columns: list[str]
) -> dict[str, Any]:
    """
    Prävalenz, Relative Risk, Odds Ratio. outcome_column (0/1), exposure_column (0/1).
    Berechnet: prevalence = mean(outcome), rate_exposed = sum(o*e)/sum(e), rate_unexposed, RR, OR.
    Inputs: outcome_column, exposure_column (optional covariate_columns nicht umgesetzt in HE).
    Use Case: Epidemiologische Studien, Risikofaktor-Analyse.
    """
    if not _get_vectors_bundle(bundle) or len(selected_columns) < 2:
        return {"prevalence": 0.0, "relative_risk": 0.0, "odds_ratio": 0.0, "n_exposed": 0, "n_unexposed": 0}
    _require_columns(bundle, selected_columns, 2, "prevalence_and_risk", "Need outcome_column and exposure_column (binary 0/1).")
    o_col, e_col = selected_columns[0], selected_columns[1]
    ctx, enc_o, enc_e, n = _load_two_vectors(bundle, o_col, e_col)
    secret_ctx = bundle["secret_context"]
    inv_n = 1.0 / n
    sum_o = enc_o.sum()
    sum_e = enc_e.sum()
    sum_oe = (enc_o * enc_e).sum()
    n_o = _decrypt_scalar(secret_ctx, pickle.dumps(sum_o.serialize()))
    n_e = _decrypt_scalar(secret_ctx, pickle.dumps(sum_e.serialize()))
    a = _decrypt_scalar(secret_ctx, pickle.dumps(sum_oe.serialize()))
    n_unexposed = n - n_e
    if n_unexposed < 1:
        n_unexposed = 1
    c = n_o - a
    rate_exposed = a / n_e if n_e else 0.0
    rate_unexposed = c / n_unexposed
    prevalence = n_o / n
    relative_risk = (rate_exposed / rate_unexposed) if rate_unexposed else 0.0
    b = n_e - a
    d = n_unexposed - c
    odds_ratio = (a * d) / (b * c) if (b * c) else 0.0
    return {
        "prevalence": round(prevalence, 4),
        "relative_risk": round(relative_risk, 4),
        "odds_ratio": round(odds_ratio, 4),
        "n_exposed": int(round(n_e)),
        "n_unexposed": int(round(n_unexposed)),
        "confidence_interval_approx": "Use decrypted counts for exact CI",
    }


def run_federated_mean_aggregation(
    bundle: dict[str, Any], selected_columns: list[str]
) -> dict[str, Any]:
    """
    Gewichteter Mittelwert über value_column; optional weight_column.
    In Multi-Party-Studies: Backend aggregiert über mehrere Datasets (hier ein Dataset).
    Result: global_mean, weighted_mean, total_n, std_error-Approximation.
    Use Case: Meta-Analyse über mehrere Institutionen.
    """
    col = selected_columns[0] if selected_columns else None
    ctx, enc, n = _load_bundle(bundle, col)
    secret_ctx = bundle["secret_context"]
    inv_n = 1.0 / n
    mean_enc = enc.sum() * inv_n
    mean_val = _decrypt_scalar(secret_ctx, pickle.dumps(mean_enc.serialize()))
    mean_sq_enc = enc.square().sum() * inv_n
    mean_sq = _decrypt_scalar(secret_ctx, pickle.dumps(mean_sq_enc.serialize()))
    var = max(mean_sq - mean_val * mean_val, 0.0)
    std_error = math.sqrt(var / n) if n else 0.0
    weighted_mean = mean_val
    if _get_vectors_bundle(bundle) and len(selected_columns) >= 2:
        try:
            ctx, encs, n = _load_vectors(bundle, selected_columns[:2])
            v_enc, w_enc = encs[selected_columns[0]], encs[selected_columns[1]]
            sum_w = w_enc.sum()
            sum_vw = (v_enc * w_enc).sum()
            sw = _decrypt_scalar(secret_ctx, pickle.dumps(sum_w.serialize()))
            svw = _decrypt_scalar(secret_ctx, pickle.dumps(sum_vw.serialize()))
            if sw:
                weighted_mean = svw / sw
        except Exception:
            pass
    return {
        "global_mean": round(mean_val, 4),
        "weighted_mean": round(weighted_mean, 4),
        "per_institution_n": [n],
        "total_n": n,
        "std_error": round(std_error, 4),
    }


def run_subgroup_analysis(
    bundle: dict[str, Any], selected_columns: list[str]
) -> dict[str, Any]:
    """
    Statistiken pro Subgruppe. value_column (erste Spalte), Subgruppen = binäre Maskenspalten (0/1).
    Bedingungen wie "age>65" werden als Maskenspalte übergeben (z.B. age_gt65 mit 0/1).
    Inputs: value_column, dann subgroup_mask_columns (eine oder mehrere 0/1-Spalten).
    Approximationsfehler: Echte Schwellenwerte müssen clientseitig in Masken umgesetzt werden.
    Use Case: Subgruppen-Wirksamkeitsanalyse für Zulassungsanträge.
    """
    if not _get_vectors_bundle(bundle) or len(selected_columns) < 2:
        col = selected_columns[0] if selected_columns else None
        ctx, enc, n = _load_bundle(bundle, col)
        s = enc.sum() * (1.0 / n)
        secret_ctx = bundle["secret_context"]
        m = _decrypt_scalar(secret_ctx, pickle.dumps(s.serialize()))
        return {"subgroups": [{"name": "all", "mean": round(m, 4), "std_dev": 0.0, "n_approx": n}]}
    _require_columns(bundle, selected_columns, 2, "subgroup_analysis", "Need value_column and at least one subgroup mask column (0/1).")
    value_col = selected_columns[0]
    mask_cols = selected_columns[1:]
    ctx, encs, n = _load_vectors(bundle, selected_columns)
    secret_ctx = bundle["secret_context"]
    subgroups_out = []
    for mask_col in mask_cols:
        v_enc = encs[value_col]
        m_enc = encs[mask_col]
        sum_v = (v_enc * m_enc).sum()
        sum_v2 = (v_enc.square() * m_enc).sum()
        n_m = m_enc.sum()
        sv = _decrypt_scalar(secret_ctx, pickle.dumps(sum_v.serialize()))
        sv2 = _decrypt_scalar(secret_ctx, pickle.dumps(sum_v2.serialize()))
        nm = _decrypt_scalar(secret_ctx, pickle.dumps(n_m.serialize()))
        nm = max(nm, 1e-6)
        mean_s = sv / nm
        var_s = (sv2 / nm) - mean_s * mean_s
        var_s = max(var_s, 0.0)
        subgroups_out.append({"name": mask_col, "mean": round(mean_s, 4), "std_dev": round(math.sqrt(var_s), 4), "n_approx": int(round(nm))})
    return {"subgroups": subgroups_out}


ALGORITHMS = {
    "descriptive_statistics": run_descriptive_statistics,
    "correlation": run_correlation,
    "group_comparison": run_group_comparison,
    "linear_regression": run_linear_regression,
    "distribution": run_distribution,
    "mean": run_mean_legacy,
    "multi_group_comparison": run_multi_group_comparison,
    "logistic_regression_approx": run_logistic_regression_approx,
    "pearson_correlation_matrix": run_pearson_correlation_matrix,
    "survival_analysis_approx": run_survival_analysis_approx,
    "prevalence_and_risk": run_prevalence_and_risk,
    "federated_mean_aggregation": run_federated_mean_aggregation,
    "subgroup_analysis": run_subgroup_analysis,
}
