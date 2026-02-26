# SPDX-License-Identifier: Apache-2.0
"""Schema validation and protocol hash."""
from __future__ import annotations

import json


def protocol_payload_for_hash(
    required_columns: list[dict],
    minimum_rows: int,
    missing_value_strategy: str,
) -> str:
    """Canonical JSON for protocol hash (sorted keys)."""
    payload = {
        "required_columns": sorted(required_columns, key=lambda c: c.get("name", "")),
        "minimum_rows": minimum_rows,
        "missing_value_strategy": missing_value_strategy,
    }
    return json.dumps(payload, sort_keys=True)


def check_schema_compatibility(
    required_columns: list[dict],
    local_schema: dict,
    proposed_mapping: dict,
) -> dict:
    """
    Prüft ob das vorgeschlagene Mapping alle required columns abdeckt und Typen/Ranges passen.
    Gibt {compatible: bool, approved_mappings: [], issues: [], warnings: []} zurück.
    """
    issues: list[str] = []
    warnings: list[str] = []
    approved_mappings: list[dict] = []
    columns = local_schema.get("columns") or []
    local_by_name = {c.get("name", ""): c for c in columns if isinstance(c, dict)}
    canonical_names = {c.get("name", ""): c for c in required_columns if isinstance(c, dict)}
    reverse_mapping = {v: k for k, v in proposed_mapping.items() if isinstance(v, str) and isinstance(k, str)}
    for col_def in required_columns:
        if not isinstance(col_def, dict):
            continue
        canonical = col_def.get("name", "")
        aliases = col_def.get("aliases") or []
        required = col_def.get("required", True)
        data_type = col_def.get("data_type", "float")
        valid_min = col_def.get("valid_range_min") if col_def.get("valid_range_min") is not None else (col_def.get("valid_range") or [None, None])[0]
        valid_max = col_def.get("valid_range_max") if col_def.get("valid_range_max") is not None else (col_def.get("valid_range") or [None, None])[1]
        local_name = reverse_mapping.get(canonical) or proposed_mapping.get(canonical)
        if not local_name:
            for a in aliases:
                if a in proposed_mapping and proposed_mapping[a] == canonical:
                    local_name = a
                    break
                if a in reverse_mapping and reverse_mapping[a] == canonical:
                    local_name = a
                    break
        if not local_name:
            if required:
                issues.append(f"Required column '{canonical}' has no mapping from local schema.")
            continue
        approved_mappings.append({"local": local_name, "canonical": canonical})
        local_col = local_by_name.get(local_name)
        if not local_col:
            warnings.append(f"Local column '{local_name}' not found in submitted schema.")
            continue
        local_type = (local_col.get("type") or "float").lower()
        type_ok = data_type == local_type or (
            data_type in ("float", "integer") and local_type in ("float", "integer")
        )
        if not type_ok:
            issues.append(f"Column '{canonical}': type mismatch (protocol: {data_type}, local: {local_type}).")
        sample_range = local_col.get("sample_range") if isinstance(local_col.get("sample_range"), list) else None
        if sample_range and valid_min is not None and len(sample_range) >= 1 and sample_range[0] is not None:
            if sample_range[0] < valid_min:
                issues.append(f"Column '{canonical}': sample min {sample_range[0]} below protocol min {valid_min}.")
        if sample_range and valid_max is not None and len(sample_range) >= 2 and sample_range[1] is not None:
            if sample_range[1] > valid_max:
                issues.append(f"Column '{canonical}': sample max {sample_range[1]} above protocol max {valid_max}.")
    for local_name, canonical in proposed_mapping.items():
        if canonical not in canonical_names and canonical not in [c.get("name") for c in required_columns]:
            warnings.append(f"Mapping {local_name} -> {canonical}: '{canonical}' not in protocol.")
    compatible = len(issues) == 0
    return {
        "compatible": compatible,
        "approved_mappings": approved_mappings,
        "issues": issues,
        "warnings": warnings,
    }
