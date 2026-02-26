# SPDX-License-Identifier: Apache-2.0
"""Config and settings tests."""
import pytest

from app.config import (
    ALLOWED_UPLOAD_EXTENSIONS,
    CKKS_BYTES_PER_SLOT_HEURISTIC,
    INITIAL_HASH,
    MAX_UPLOAD_BYTES,
    MAX_UPLOAD_MB,
    STUDIES_UPLOADS_DIR,
    UPLOADS_DIR,
    settings,
)


def test_settings_exists():
    assert settings is not None
    assert hasattr(settings, "database_url")
    assert hasattr(settings, "upload_dir")
    assert hasattr(settings, "max_upload_size_mb")


def test_settings_upload_paths():
    assert settings.upload_dir_path == UPLOADS_DIR
    assert settings.studies_upload_dir_path == STUDIES_UPLOADS_DIR
    assert "studies" in str(settings.studies_upload_dir_path)


def test_settings_max_upload_bytes():
    assert settings.max_upload_bytes == MAX_UPLOAD_BYTES
    assert MAX_UPLOAD_BYTES == MAX_UPLOAD_MB * 1024 * 1024


def test_backward_compat_constants():
    assert ALLOWED_UPLOAD_EXTENSIONS == {".bin"}
    assert CKKS_BYTES_PER_SLOT_HEURISTIC == 8000
    assert INITIAL_HASH == "0" * 64
    assert len(INITIAL_HASH) == 64


def test_settings_production_property():
    # Default dev secret key -> production is False
    assert isinstance(settings.production, bool)
