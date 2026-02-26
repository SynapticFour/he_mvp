# SPDX-License-Identifier: Apache-2.0
"""Pydantic request/response schemas."""
from pydantic import BaseModel, Field as PydanticField


class JobRequest(BaseModel):
    dataset_id: int
    requester_email: str = PydanticField(..., max_length=254)
    computation_type: str = "mean"
    algorithm: str = "mean"
    selected_columns: list[str] = []


class StudyCreate(BaseModel):
    name: str = PydanticField(..., max_length=200)
    description: str = PydanticField("", max_length=2000)
    creator_email: str = PydanticField(..., max_length=254)
    institution_name: str = PydanticField(..., max_length=200)
    threshold_t: int = 1
    threshold_n: int = 1
    allowed_algorithms: list[str] = []
    column_definitions: dict | list = []
    public_key_share: str = ""


class StudyJoin(BaseModel):
    institution_email: str
    institution_name: str
    public_key_share: str


class StudyUploadDatasetForm(BaseModel):
    institution_email: str
    dataset_name: str
    columns: list[str] = []


class StudyRequestComputation(BaseModel):
    requester_email: str
    algorithm: str
    selected_columns: list[str] = []
    parameters: dict = {}


class StudyApprove(BaseModel):
    institution_email: str


class StudySubmitDecryptionShare(BaseModel):
    institution_email: str
    decryption_share: str


class ProtocolColumnDef(BaseModel):
    name: str
    aliases: list[str] = []
    data_type: str = "float"
    unit: str | None = None
    valid_range: list[float] | None = None
    allowed_values: list[str] | None = None
    required: bool = True
    description: str = ""


class ProtocolCreate(BaseModel):
    required_columns: list[ProtocolColumnDef]
    minimum_rows: int = 1
    missing_value_strategy: str = "exclude"
    creator_email: str = ""


class LocalColumnDesc(BaseModel):
    name: str
    type: str = "float"
    sample_range: list[float] | None = None
    null_percentage: float = 0.0


class SchemaSubmit(BaseModel):
    institution_email: str
    local_schema: dict
    proposed_mapping: dict


class ProtocolFinalize(BaseModel):
    creator_email: str = ""
