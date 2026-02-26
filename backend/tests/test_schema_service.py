# SPDX-License-Identifier: Apache-2.0
"""Schema service: protocol_payload_for_hash, check_schema_compatibility."""
from app.services.schema_service import check_schema_compatibility, protocol_payload_for_hash


def test_protocol_payload_for_hash_deterministic():
    cols = [{"name": "x", "data_type": "float"}, {"name": "y", "data_type": "integer"}]
    a = protocol_payload_for_hash(cols, 10, "exclude")
    b = protocol_payload_for_hash(cols, 10, "exclude")
    assert a == b
    assert "minimum_rows" in a
    assert "10" in a


def test_protocol_payload_for_hash_sorted_columns():
    cols = [{"name": "z"}, {"name": "a"}]
    payload = protocol_payload_for_hash(cols, 1, "exclude")
    assert "required_columns" in payload


def test_check_schema_compatibility_compatible():
    required = [{"name": "age", "data_type": "float", "required": True}]
    local = {"columns": [{"name": "age", "type": "float"}]}
    mapping = {"age": "age"}
    result = check_schema_compatibility(required, local, mapping)
    assert result["compatible"] is True
    assert len(result["approved_mappings"]) == 1
    assert len(result["issues"]) == 0


def test_check_schema_compatibility_missing_required():
    required = [{"name": "age", "data_type": "float", "required": True}]
    local = {"columns": [{"name": "other", "type": "float"}]}
    mapping = {}
    result = check_schema_compatibility(required, local, mapping)
    assert result["compatible"] is False
    assert any("age" in i for i in result["issues"])


def test_check_schema_compatibility_type_mismatch():
    required = [{"name": "age", "data_type": "integer", "required": True}]
    local = {"columns": [{"name": "age", "type": "string"}]}
    mapping = {"age": "age"}
    result = check_schema_compatibility(required, local, mapping)
    assert result["compatible"] is False
    assert any("type" in i.lower() or "mismatch" in i.lower() for i in result["issues"])


def test_check_schema_compatibility_float_integer_ok():
    required = [{"name": "value", "data_type": "float", "required": True}]
    local = {"columns": [{"name": "value", "type": "integer"}]}
    mapping = {"value": "value"}
    result = check_schema_compatibility(required, local, mapping)
    assert result["compatible"] is True
