# SPDX-License-Identifier: Apache-2.0
"""Study, StudyDataset, StudyProtocol, Schema models."""
from datetime import datetime

from sqlmodel import Field, SQLModel


class Study(SQLModel, table=True):
    __tablename__ = "studies"
    id: int | None = Field(default=None, primary_key=True)
    name: str
    description: str
    protocol: str = "{}"
    status: str = "draft"
    threshold_n: int = 1
    threshold_t: int = 1
    public_key_fingerprint: str = ""
    combined_public_key: str = ""
    created_by: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class StudyDataset(SQLModel, table=True):
    __tablename__ = "study_datasets"
    id: int | None = Field(default=None, primary_key=True)
    study_id: int = Field(foreign_key="studies.id")
    dataset_name: str = ""
    institution_email: str = ""
    file_path: str = ""
    commitment_hash: str = ""
    columns: str = "[]"
    committed_at: datetime = Field(default_factory=datetime.utcnow)


class StudyProtocol(SQLModel, table=True):
    __tablename__ = "study_protocol"
    id: int | None = Field(default=None, primary_key=True)
    study_id: int = Field(foreign_key="studies.id", unique=True)
    protocol_version: str = "1.0"
    required_columns: str = "[]"
    minimum_rows: int = 1
    missing_value_strategy: str = "exclude"
    protocol_hash: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)
    finalized_at: datetime | None = None
    status: str = "draft"


class ProtocolColumn(SQLModel, table=True):
    __tablename__ = "protocol_columns"
    id: int | None = Field(default=None, primary_key=True)
    protocol_id: int = Field(foreign_key="study_protocol.id")
    column_name: str = ""
    aliases: str = "[]"
    data_type: str = "float"
    unit: str | None = None
    valid_range_min: float | None = None
    valid_range_max: float | None = None
    allowed_values: str | None = None
    required: bool = True
    description: str = ""


class SchemaSubmission(SQLModel, table=True):
    __tablename__ = "schema_submissions"
    id: int | None = Field(default=None, primary_key=True)
    study_id: int = Field(foreign_key="studies.id")
    institution_email: str = ""
    submitted_schema: str = "{}"
    mapping: str = "{}"
    fingerprint: str = "{}"
    compatibility_result: str = "{}"
    institution_signature: str = ""
    submitted_at: datetime = Field(default_factory=datetime.utcnow)
    signed_at: datetime | None = None


class SyntheticSubmission(SQLModel, table=True):
    __tablename__ = "synthetic_submissions"
    id: int | None = Field(default=None, primary_key=True)
    study_id: int = Field(foreign_key="studies.id")
    institution_email: str = ""
    file_path: str = ""
    validation_result: str = "{}"
    submitted_at: datetime = Field(default_factory=datetime.utcnow)
