# SPDX-License-Identifier: Apache-2.0
"""Audit log model."""
from datetime import datetime

from sqlmodel import Field, SQLModel

from app.config import INITIAL_HASH


class AuditLog(SQLModel, table=True):
    __tablename__ = "audit_log"
    id: int | None = Field(default=None, primary_key=True)
    study_id: int | None = Field(default=None, foreign_key="studies.id")
    action_type: str = ""
    actor_email: str = ""
    details: str = "{}"
    previous_hash: str = INITIAL_HASH
    entry_hash: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)
