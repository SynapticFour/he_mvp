# SPDX-License-Identifier: Apache-2.0
"""Job, JobApproval, JobDecryptionShare models."""
from datetime import datetime

from sqlmodel import Field, SQLModel


class Job(SQLModel, table=True):
    __tablename__ = "jobs"
    id: int | None = Field(default=None, primary_key=True)
    dataset_id: int | None = Field(default=None, foreign_key="datasets.id")
    study_id: int | None = Field(default=None, foreign_key="studies.id")
    requester_email: str
    computation_type: str = "mean"
    algorithm: str = "mean"
    selected_columns: str = "[]"
    parameters: str = "{}"
    status: str = "pending"
    result: float | None = None
    result_json: str | None = None
    result_commitment: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class JobApproval(SQLModel, table=True):
    __tablename__ = "job_approvals"
    id: int | None = Field(default=None, primary_key=True)
    job_id: int = Field(foreign_key="jobs.id")
    institution_email: str = ""
    approved_at: datetime = Field(default_factory=datetime.utcnow)


class JobDecryptionShare(SQLModel, table=True):
    __tablename__ = "job_decryption_shares"
    id: int | None = Field(default=None, primary_key=True)
    job_id: int = Field(foreign_key="jobs.id")
    institution_email: str = ""
    decryption_share: str = ""
    submitted_at: datetime = Field(default_factory=datetime.utcnow)
