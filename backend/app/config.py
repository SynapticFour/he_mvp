# SPDX-License-Identifier: Apache-2.0
"""All configuration via environment variables (12-factor). No hardcoded values."""
from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Database
    database_url: str = Field(default="sqlite:///./secure_collab.db", description="Database URL")

    # Storage
    upload_dir: str = Field(default="./uploads", description="Base directory for uploads")
    max_upload_size_mb: int = Field(default=500, ge=1, le=2000, description="Max upload size in MB")

    # Security — required in production; set in .env
    secret_key: str = Field(default="dev-secret-key-change-in-production", min_length=16)

    # CORS
    allowed_origins: list[str] = Field(
        default=["http://localhost:3000"],
        description="Allowed CORS origins",
    )

    # Computation
    max_concurrent_computations: int = Field(default=3, ge=1, le=32)

    # Integrity
    compute_codebase_hash_on_startup: bool = Field(default=True, description="Compute codebase hash at startup")

    # Optional: Blockchain anchoring (Phase 1)
    polygon_rpc_url: str | None = Field(default=None, description="Polygon RPC URL for anchoring")
    polygon_private_key: str | None = Field(default=None, description="Private key for anchoring (never commit)")

    # Derived / internal
    @property
    def upload_dir_path(self) -> Path:
        return Path(self.upload_dir)

    @property
    def studies_upload_dir_path(self) -> Path:
        return self.upload_dir_path / "studies"

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024

    @property
    def production(self) -> bool:
        return self.secret_key != "dev-secret-key-change-in-production"


settings = Settings()

# Backward-compatible names for existing imports
UPLOADS_DIR = settings.upload_dir_path
STUDIES_UPLOADS_DIR = settings.studies_upload_dir_path
MAX_UPLOAD_MB = settings.max_upload_size_mb
MAX_UPLOAD_BYTES = settings.max_upload_bytes
SQLITE_URL = settings.database_url
MAX_CONCURRENT_COMPUTATIONS = settings.max_concurrent_computations
PRODUCTION = settings.production
ALLOWED_UPLOAD_EXTENSIONS = {".bin"}
CKKS_BYTES_PER_SLOT_HEURISTIC = 8000
INITIAL_HASH = "0" * 64
