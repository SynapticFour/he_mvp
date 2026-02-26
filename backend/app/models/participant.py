# SPDX-License-Identifier: Apache-2.0
"""Study participant model."""
from datetime import datetime

from sqlmodel import Field, SQLModel


class StudyParticipant(SQLModel, table=True):
    __tablename__ = "study_participants"
    id: int | None = Field(default=None, primary_key=True)
    study_id: int = Field(foreign_key="studies.id")
    institution_name: str = ""
    institution_email: str = ""
    public_key_share: str = ""
    key_share_committed_at: datetime | None = None
    has_approved_result: bool = False
    joined_at: datetime = Field(default_factory=datetime.utcnow)
