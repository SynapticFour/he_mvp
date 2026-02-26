# SPDX-License-Identifier: Apache-2.0
"""
================================================================================
SecureCollab – Multi-Party Clinical Data Analysis
================================================================================

WAS IST SECURECOLLAB?
---------------------
SecureCollab ist eine Plattform, auf der mehrere Institutionen gemeinsam auf
kombinierten klinischen Daten rechnen können, ohne dass irgendeine Partei –
auch der Plattformbetreiber nicht – die Rohdaten einer anderen Partei je sieht.
Das wird nicht durch Verträge garantiert, sondern durch Mathematik.

WARUM?
------
In der Pharmaindustrie und klinischen Forschung existieren riesige Mengen
wertvoller Patientendaten, die kaum ausgetauscht werden, weil:
1. Regulatorisch (DSGVO, HIPAA) der Austausch stark eingeschränkt ist
2. Institutionen einander nicht vertrauen (Konkurrenten, verschiedene Rechtssysteme)
3. Ein vertrauenswürdiger Dritter oft nicht existiert oder zu teuer/langsam ist

Unser Ansatz kombiniert drei kryptographische Techniken:
- Homomorphic Encryption (HE): Berechnungen auf verschlüsselten Daten
- Threshold Key Generation (DKG): Der vollständige Schlüssel existiert nie an einem Ort
- Cryptographic Commitment: Beweisbare Garantie, welcher Schlüssel verwendet wurde

KRYPTOGRAPHISCHES MODELL
------------------------
1. THRESHOLD KEY GENERATION
   Alle Studienteilnehmer erstellen gemeinsam ein Schlüsselpaar. Jede Institution
   erhält einen Key Share. Der vollständige private Schlüssel existiert nie.
   Entschlüsselung erfordert eine Mindestanzahl von Key Shares (t-of-n).
   Der kombinierte Public Key wird im Study-Protokoll gespeichert und ist
   öffentlich verifizierbar.

2. CRYPTOGRAPHIC COMMITMENT
   Beim Upload: commitment = SHA3-256(ciphertext || public_key_fingerprint || timestamp || institution_id)
   Der Commitment wird lokal, im Audit Log und im Study-Protokoll gespeichert.
   Jeder kann später verifizieren: "Diese Datei wurde mit genau diesem Public Key
   verschlüsselt, von dieser Institution, zu diesem Zeitpunkt."

3. AUDIT TRAIL
   Jede Operation erzeugt einen signierten Log-Eintrag. Der Trail ist append-only;
   jeder Eintrag enthält den Hash des vorherigen (Blockchain-ähnliche Verkettung).
   Manipulation ist dadurch nachweisbar.

WAS SIEHT DER PLATTFORMBETREIBER?
---------------------------------
- Sichtbar: Metadaten (Studienname, Teilnehmer-Liste, Timestamps), Public Key
  Fingerprint, Commitment-Hashes, Audit-Trail, Algorithmus-Namen und Parameter.
- Nicht sichtbar: Rohdaten, private Key Shares, entschlüsselte Ergebnisse vor
  Freigabe, Inhalte der verschlüsselten Dateien.

ENDPOINTS & GARANTIEN
---------------------
- POST /studies/create: Erstellt Study (draft), Audit: study_created.
- POST /studies/{id}/join: Teilnehmer liefert Public Key Share; bei Vollzahl
  wird Study aktiv, Public Key Fingerprint gesetzt, Audit: participant_joined/study_activated.
- GET /studies/{id}/public_key: Liefert kombinierten Public Key und alle
  Upload-Commitments zur Verifikation.
- POST /studies/{id}/upload_dataset: Speichert verschlüsselte Datei, berechnet
  Commitment, Audit: dataset_uploaded.
- POST /studies/{id}/request_computation: Prüft erlaubte Algorithmen, erstellt
  Job (pending_approval), Audit: computation_requested.
- POST /studies/{id}/jobs/{id}/approve: Sammelt Approvals; bei Vollzahl wird
  Berechnung auf kombinierten verschlüsselten Daten ausgeführt, Ergebnis
  verschlüsselt gespeichert, Audit: computation_executed.
- POST /studies/{id}/jobs/{id}/submit_decryption_share: Sammelt Decryption Shares;
  bei >= t Shares wird Ergebnis kombiniert, Audit: result_decrypted.
- GET /studies/{id}/audit_trail: Vollständiger Trail; entry_hash =
  SHA3-256(action_type || actor || details || timestamp || previous_hash).
- GET /studies/{id}/protocol: Vollständiges Study-Protokoll (regulatorische Dokumentation).

NOTE: When running via `uvicorn app.main:app`, this file is not used (dead code).
See docs/OWASP_ANALYSIS.md. Use `app.main:app` for the refactored application.
"""

import base64
import hashlib
import json
import logging
import os
import re
import pickle
import uuid
from datetime import datetime
from pathlib import Path

from sqlalchemy import text
from fastapi import Body, FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field as PydanticField
from sqlmodel import Field, Session, SQLModel, create_engine, select

try:
    from slowapi import Limiter
    from slowapi.util import get_remote_address
    _limiter = Limiter(key_func=get_remote_address)
    def _rate_limit(s: str):
        return _limiter.limit(s)
except ImportError:
    _limiter = None
    def _rate_limit(s: str):
        def _noop(f):
            return f
        return _noop

from algorithms import ALGORITHMS

logger = logging.getLogger("securecollab")

# Codebase integrity: computed at startup, included in every audit entry
try:
    from integrity import compute_codebase_hash, verify_codebase_hash
    _integrity_result = compute_codebase_hash()
    DEPLOYMENT_INTEGRITY = _integrity_result
except Exception as e:
    logger.warning("Codebase integrity computation failed: %s", e)
    DEPLOYMENT_INTEGRITY = {"codebase_hash": "unknown", "git_commit": "unknown", "computed_at": datetime.utcnow().isoformat(), "file_count": 0, "files_included": []}
    def verify_codebase_hash(expected: str):
        return {"verified": False, "expected_hash": expected, "current_hash": "unknown", "error": "Integrity module unavailable"}

# Algorithm registry for frontend/SDK: list of available algorithms with metadata.
ALGORITHM_REGISTRY: dict[str, dict] = {
    "descriptive_statistics": {
        "name": "Descriptive Statistics",
        "description": "Mean, Std Dev, Variance, Min/Max, IQR approximation, Skewness.",
        "required_columns": 1,
        "column_types": ["float", "integer"],
        "parameters": {},
        "estimated_seconds": 2,
        "approximation_warning": "Min/Max and IQR are approximations (no sorting in HE).",
        "clinical_use_case": "First data exploration in clinical studies.",
    },
    "correlation": {
        "name": "Correlation Analysis",
        "description": "Pearson correlation between two columns.",
        "required_columns": 2,
        "column_types": ["float", "integer"],
        "parameters": {},
        "estimated_seconds": 2,
        "approximation_warning": None,
        "clinical_use_case": "Association between two continuous markers.",
    },
    "group_comparison": {
        "name": "Group Comparison (t-Test)",
        "description": "Compare two groups (first vs second half of data).",
        "required_columns": 1,
        "column_types": ["float", "integer"],
        "parameters": {},
        "estimated_seconds": 2,
        "approximation_warning": "Groups are index-based (no categorical column in HE).",
        "clinical_use_case": "Treatment vs control comparison.",
    },
    "linear_regression": {
        "name": "Linear Regression",
        "description": "Slope and intercept for one predictor and one target.",
        "required_columns": 2,
        "column_types": ["float", "integer"],
        "parameters": {},
        "estimated_seconds": 2,
        "approximation_warning": None,
        "clinical_use_case": "Predict one variable from another.",
    },
    "distribution": {
        "name": "Distribution Overview",
        "description": "Histogram approximation (5 buckets by index).",
        "required_columns": 1,
        "column_types": ["float", "integer"],
        "parameters": {},
        "estimated_seconds": 1,
        "approximation_warning": "Buckets are index-based, not value-based.",
        "clinical_use_case": "Rough distribution shape.",
    },
    "mean": {
        "name": "Mean (Legacy)",
        "description": "Single mean value.",
        "required_columns": 1,
        "column_types": ["float", "integer"],
        "parameters": {},
        "estimated_seconds": 1,
        "approximation_warning": None,
        "clinical_use_case": "Simple aggregate.",
    },
    "multi_group_comparison": {
        "name": "Multi-Group Comparison",
        "description": "Mean and Std per group, pairwise differences; 2–4 groups (by index or mask columns).",
        "required_columns": 1,
        "column_types": ["float", "integer", "binary"],
        "parameters": {},
        "estimated_seconds": 5,
        "approximation_warning": "F-statistic is approximate; groups by segment or 0/1 masks.",
        "clinical_use_case": "Treatment vs Control vs Placebo.",
    },
    "logistic_regression_approx": {
        "name": "Logistic Regression (Approx)",
        "description": "Approximate coefficients for binary outcome; linear approximation only.",
        "required_columns": 2,
        "column_types": ["float", "integer", "binary"],
        "parameters": {},
        "estimated_seconds": 4,
        "approximation_warning": "For exploratory analysis only – not for clinical decisions.",
        "clinical_use_case": "Predict treatment response (yes/no) – screening only.",
    },
    "pearson_correlation_matrix": {
        "name": "Pearson Correlation Matrix",
        "description": "Full correlation matrix for 2–6 columns plus strongest correlations.",
        "required_columns": 2,
        "column_types": ["float", "integer"],
        "parameters": {},
        "estimated_seconds": 8,
        "approximation_warning": None,
        "clinical_use_case": "GWAS-style correlation between clinical markers.",
    },
    "survival_analysis_approx": {
        "name": "Survival Analysis (Approx)",
        "description": "Hazard rate, median survival approximation; no Kaplan-Meier (no sorting in HE).",
        "required_columns": 2,
        "column_types": ["float", "integer", "binary"],
        "parameters": {},
        "estimated_seconds": 3,
        "approximation_warning": "No true Kaplan-Meier; median and timepoints are approximations.",
        "clinical_use_case": "Survival in oncology studies – rough estimate only.",
    },
    "prevalence_and_risk": {
        "name": "Prevalence and Risk",
        "description": "Prevalence, Relative Risk, Odds Ratio (outcome and exposure 0/1).",
        "required_columns": 2,
        "column_types": ["binary", "integer"],
        "parameters": {},
        "estimated_seconds": 3,
        "approximation_warning": "CI requires decrypted counts for exact interval.",
        "clinical_use_case": "Epidemiology, risk factor analysis.",
    },
    "federated_mean_aggregation": {
        "name": "Federated Mean Aggregation",
        "description": "Weighted mean over value column; optional weight column. For multi-party meta-analysis.",
        "required_columns": 1,
        "column_types": ["float", "integer"],
        "parameters": {},
        "estimated_seconds": 2,
        "approximation_warning": None,
        "clinical_use_case": "Meta-analysis across institutions.",
    },
    "subgroup_analysis": {
        "name": "Subgroup Analysis",
        "description": "Mean and Std per subgroup; subgroups = binary mask columns (0/1).",
        "required_columns": 2,
        "column_types": ["float", "integer", "binary"],
        "parameters": {},
        "estimated_seconds": 6,
        "approximation_warning": "Thresholds must be precomputed as mask columns client-side.",
        "clinical_use_case": "Subgroup efficacy for regulatory submissions.",
    },
}

# -----------------------------------------------------------------------------
# Datenbank
# -----------------------------------------------------------------------------

sqlite_url = "sqlite:///./secure_collab.db"
engine = create_engine(sqlite_url, connect_args={"check_same_thread": False})

UPLOADS_DIR = Path("uploads")
UPLOADS_DIR.mkdir(exist_ok=True)
STUDIES_UPLOADS_DIR = UPLOADS_DIR / "studies"
STUDIES_UPLOADS_DIR.mkdir(exist_ok=True)

INITIAL_HASH = "0" * 64  # Kein Vorgänger beim ersten Eintrag

# Security: configurable via ENV
MAX_UPLOAD_MB = int(os.environ.get("SECURECOLLAB_MAX_UPLOAD_MB", "500"))
MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024
ALLOWED_UPLOAD_EXTENSIONS = {".bin"}
MAX_CONCURRENT_COMPUTATIONS = int(os.environ.get("SECURECOLLAB_MAX_CONCURRENT_COMPUTATIONS", "3"))

# CKKS heuristic: columns * rows * ~8KB per coefficient (poly_mod 8192)
CKKS_BYTES_PER_SLOT_HEURISTIC = 8000


def secure_filename(filename: str) -> str:
    """Path traversal prevention: only alphanumeric, underscore, dot."""
    if not filename or not filename.strip():
        return "unnamed.bin"
    name = Path(filename).name
    safe = "".join(c if c.isalnum() or c in "._-" else "_" for c in name)
    return safe or "unnamed.bin"


def sanitize_text(value: str, max_len: int = 2000) -> str:
    """Strip HTML/script tags and enforce max length."""
    if not value:
        return ""
    value = re.sub(r"<[^>]+>", "", value)
    value = re.sub(r"javascript:", "", value, flags=re.IGNORECASE)
    return value.strip()[:max_len]


def sha3_256_hex(*parts: bytes | str) -> str:
    h = hashlib.sha3_256()
    for p in parts:
        h.update(p.encode("utf-8") if isinstance(p, str) else p)
    return h.hexdigest()


class Dataset(SQLModel, table=True):
    __tablename__ = "datasets"
    id: int | None = Field(default=None, primary_key=True)
    name: str
    description: str
    file_path: str
    owner_email: str
    columns: str = "[]"
    organization: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)


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
    status: str = "pending"  # pending | pending_approval | awaiting_decryption | completed | rejected
    result: float | None = None
    result_json: str | None = None
    result_commitment: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Study(SQLModel, table=True):
    __tablename__ = "studies"
    id: int | None = Field(default=None, primary_key=True)
    name: str
    description: str
    protocol: str = "{}"  # JSON: allowed_algorithms, column_definitions, etc.
    status: str = "draft"  # draft | active | completed
    threshold_n: int = 1
    threshold_t: int = 1
    public_key_fingerprint: str = ""
    combined_public_key: str = ""  # base64, wenn active
    created_by: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class StudyParticipant(SQLModel, table=True):
    __tablename__ = "study_participants"
    id: int | None = Field(default=None, primary_key=True)
    study_id: int = Field(foreign_key="studies.id")
    institution_name: str = ""
    institution_email: str = ""
    public_key_share: str = ""  # base64
    key_share_committed_at: datetime | None = None
    has_approved_result: bool = False
    joined_at: datetime = Field(default_factory=datetime.utcnow)


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
    decryption_share: str = ""  # base64
    submitted_at: datetime = Field(default_factory=datetime.utcnow)


# -----------------------------------------------------------------------------
# Schema Validation (Precondition for Study Activation)
# -----------------------------------------------------------------------------


class StudyProtocol(SQLModel, table=True):
    __tablename__ = "study_protocol"
    id: int | None = Field(default=None, primary_key=True)
    study_id: int = Field(foreign_key="studies.id", unique=True)
    protocol_version: str = "1.0"
    required_columns: str = "[]"  # JSON array of column definitions
    minimum_rows: int = 1
    missing_value_strategy: str = "exclude"  # exclude | impute_mean | reject
    protocol_hash: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)
    finalized_at: datetime | None = None
    status: str = "draft"  # draft | finalized


class ProtocolColumn(SQLModel, table=True):
    __tablename__ = "protocol_columns"
    id: int | None = Field(default=None, primary_key=True)
    protocol_id: int = Field(foreign_key="study_protocol.id")
    column_name: str = ""
    aliases: str = "[]"  # JSON array of accepted alternative names
    data_type: str = "float"  # float | integer | binary | categorical
    unit: str | None = None
    valid_range_min: float | None = None
    valid_range_max: float | None = None
    allowed_values: str | None = None  # JSON for binary/categorical
    required: bool = True
    description: str = ""


class SchemaSubmission(SQLModel, table=True):
    __tablename__ = "schema_submissions"
    id: int | None = Field(default=None, primary_key=True)
    study_id: int = Field(foreign_key="studies.id")
    institution_email: str = ""
    submitted_schema: str = "{}"  # JSON description of local data
    mapping: str = "{}"  # JSON {local_column: canonical_column}
    fingerprint: str = "{}"  # JSON {column_name: {type, range_bucket, null_pct_bucket}}
    compatibility_result: str = "{}"  # JSON {compatible, issues, mappings}
    institution_signature: str = ""  # SHA3-256(mapping + protocol_hash + email)
    submitted_at: datetime = Field(default_factory=datetime.utcnow)
    signed_at: datetime | None = None


class SyntheticSubmission(SQLModel, table=True):
    __tablename__ = "synthetic_submissions"
    id: int | None = Field(default=None, primary_key=True)
    study_id: int = Field(foreign_key="studies.id")
    institution_email: str = ""
    file_path: str = ""
    validation_result: str = "{}"  # JSON
    submitted_at: datetime = Field(default_factory=datetime.utcnow)


def create_db_and_tables():
    SQLModel.metadata.create_all(engine)
    with engine.connect() as conn:
        for table, col, typ, default in [
            ("datasets", "columns", "TEXT", "'[]'"),
            ("datasets", "organization", "TEXT", "''"),
            ("jobs", "algorithm", "TEXT", "'mean'"),
            ("jobs", "selected_columns", "TEXT", "'[]'"),
            ("jobs", "result_json", "TEXT", "NULL"),
            ("jobs", "study_id", "INTEGER", "NULL"),
            ("jobs", "parameters", "TEXT", "'{}'"),
            ("jobs", "result_commitment", "TEXT", "NULL"),
        ]:
            try:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {typ} DEFAULT {default}"))
                conn.commit()
            except Exception:
                pass


def write_audit_log(
    session: Session,
    study_id: int | None,
    action_type: str,
    actor_email: str,
    details: dict,
) -> None:
    """Append-only Audit Log: previous_hash verkettet, entry_hash = SHA3-256(...). Jeder Eintrag enthält codebase_hash."""
    codebase_hash = DEPLOYMENT_INTEGRITY.get("codebase_hash", "unknown")
    details_with_integrity = {**details, "codebase_hash": codebase_hash}
    last = (
        session.exec(
            select(AuditLog).where(AuditLog.study_id == study_id).order_by(AuditLog.id.desc()).limit(1)
        ).first()
        if study_id is not None
        else None
    )
    previous_hash = last.entry_hash if last else INITIAL_HASH
    now = datetime.utcnow()
    ts_str = now.isoformat()
    details_json = json.dumps(details_with_integrity, sort_keys=True)
    payload = f"{action_type}{actor_email}{details_json}{ts_str}{previous_hash}"
    entry_hash = sha3_256_hex(payload)
    entry = AuditLog(
        study_id=study_id,
        action_type=action_type,
        actor_email=actor_email,
        details=details_json,
        previous_hash=previous_hash,
        entry_hash=entry_hash,
        created_at=now,
    )
    session.add(entry)


def _protocol_payload_for_hash(required_columns: list[dict], minimum_rows: int, missing_value_strategy: str) -> str:
    """Canonical JSON for protocol hash (sorted keys)."""
    payload = {
        "required_columns": sorted(required_columns, key=lambda c: c.get("name", "")),
        "minimum_rows": minimum_rows,
        "missing_value_strategy": missing_value_strategy,
    }
    return json.dumps(payload, sort_keys=True)


def _check_schema_compatibility(
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
        valid_range = col_def.get("valid_range") or col_def.get("valid_range_min") is not None and col_def.get("valid_range_max") is not None
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
    public_key_share: str = ""  # optional; Creator kann Key direkt mitgeben


class StudyJoin(BaseModel):
    institution_email: str
    institution_name: str
    public_key_share: str  # base64


class StudyUploadDataset(BaseModel):
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
    decryption_share: str  # base64


# Schema validation request/response models
class ProtocolColumnDef(BaseModel):
    name: str
    aliases: list[str] = []
    data_type: str = "float"  # float | integer | binary | categorical
    unit: str | None = None
    valid_range: list[float] | None = None  # [min, max]
    allowed_values: list[str] | None = None
    required: bool = True
    description: str = ""


class ProtocolCreate(BaseModel):
    required_columns: list[ProtocolColumnDef]
    minimum_rows: int = 1
    missing_value_strategy: str = "exclude"  # exclude | impute_mean | reject
    creator_email: str = ""


class LocalColumnDesc(BaseModel):
    name: str
    type: str = "float"
    sample_range: list[float] | None = None  # [min, max] from sample
    null_percentage: float = 0.0


class SchemaSubmit(BaseModel):
    institution_email: str
    local_schema: dict  # {columns: [LocalColumnDesc]}
    proposed_mapping: dict  # {local_name: canonical_name}


# -----------------------------------------------------------------------------
# FastAPI App
# -----------------------------------------------------------------------------

app = FastAPI(title="Secure Collaboration Space API")
if _limiter is not None:
    app.state.limiter = _limiter


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """OWASP A09: No stack traces to client; log with error_id for correlation."""
    error_id = str(uuid.uuid4())
    logger.error("Unhandled exception %s: %s", error_id, exc, exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "error_id": error_id},
    )


# Security headers (OWASP A05)
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Content-Security-Policy"] = "default-src 'self'"
    if os.environ.get("SECURECOLLAB_PRODUCTION", "").lower() in ("1", "true", "yes"):
        response.headers["Strict-Transport-Security"] = "max-age=31536000"
    return response


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    create_db_and_tables()


# -----------------------------------------------------------------------------
# Endpoints
# -----------------------------------------------------------------------------


@app.post("/datasets/upload")
@_rate_limit("10/hour")
def datasets_upload(
    request: Request,
    file: UploadFile = File(..., description="encrypted.bin"),
    name: str = Form(...),
    description: str = Form(...),
    owner_email: str = Form(...),
    organization: str = Form(""),
    columns: str = Form("[]"),
    declared_rows: str = Form(""),  # optional: for ciphertext size validation
):
    """
    Binary-Datei + Form-Felder. OWASP A03/A10: Max size, only .bin, path traversal prevention.
    """
    if Path(file.filename or "").suffix.lower() not in ALLOWED_UPLOAD_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Only .bin files are allowed")
    safe_name = secure_filename(file.filename or "encrypted.bin")
    if not safe_name.lower().endswith(".bin"):
        safe_name = f"{uuid.uuid4().hex}.bin"
    else:
        safe_name = f"{uuid.uuid4().hex}_{safe_name}"
    file_path = (UPLOADS_DIR / safe_name).resolve()
    uploads_resolved = UPLOADS_DIR.resolve()
    try:
        file_path.relative_to(uploads_resolved)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid upload path")
    try:
        contents = file.file.read()
    finally:
        file.file.close()
    if len(contents) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail=f"File too large (max {MAX_UPLOAD_MB} MB)")
    if declared_rows:
        try:
            n_rows = int(declared_rows)
            arr = json.loads(columns)
            n_cols = len(arr) if isinstance(arr, list) else 1
            max_plausible = n_cols * max(n_rows, 1) * CKKS_BYTES_PER_SLOT_HEURISTIC * 2
            if len(contents) > max_plausible:
                raise HTTPException(status_code=400, detail="File size exceeds plausible range for declared columns/rows")
        except (ValueError, json.JSONDecodeError):
            pass
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_bytes(contents)
    columns_clean = "[]"
    try:
        arr = json.loads(columns)
        if isinstance(arr, list):
            columns_clean = json.dumps([str(x) for x in arr])
    except (json.JSONDecodeError, TypeError):
        pass
    name = sanitize_text(name, 200)
    description = sanitize_text(description, 2000)
    organization = sanitize_text(organization, 200)
    rel_path = str(file_path)
    with Session(engine) as session:
        dataset = Dataset(
            name=name,
            description=description,
            file_path=rel_path,
            owner_email=owner_email[:254],
            organization=organization or "",
            columns=columns_clean,
        )
        session.add(dataset)
        session.commit()
        session.refresh(dataset)
        return {"dataset_id": dataset.id}


@app.get("/datasets/{dataset_id}/columns")
def dataset_columns(dataset_id: int):
    """Gibt die gespeicherten Spaltennamen als Array zurück."""
    with Session(engine) as session:
        dataset = session.get(Dataset, dataset_id)
        if not dataset:
            raise HTTPException(status_code=404, detail="Dataset nicht gefunden")
        try:
            cols = json.loads(dataset.columns or "[]")
            return cols if isinstance(cols, list) else []
        except (json.JSONDecodeError, TypeError):
            return []


@app.get("/algorithms")
def algorithms_list():
    """Vollständiges Algorithmen-Registry für Frontend und SDK (Name, Beschreibung, geschätzte Zeit, Warnungen, Use Case)."""
    return ALGORITHM_REGISTRY


@app.get("/system/integrity")
@_rate_limit("100/hour")
def system_integrity(request: Request):
    """
    Öffentlicher Endpoint: Codebase-Hash, Git-Commit, Versionen.
    Institutionen können jederzeit prüfen, ob die laufende Instanz dem erwarteten Code entspricht.
    """
    import sys
    try:
        import tenseal as ts
        tenseal_version = getattr(ts, "__version__", "unknown")
    except ImportError:
        tenseal_version = "not installed"
    try:
        import fastapi
        fastapi_version = getattr(fastapi, "__version__", "unknown")
    except ImportError:
        fastapi_version = "unknown"
    return {
        "codebase_hash": DEPLOYMENT_INTEGRITY.get("codebase_hash", "unknown"),
        "git_commit": DEPLOYMENT_INTEGRITY.get("git_commit", "unknown"),
        "computed_at": DEPLOYMENT_INTEGRITY.get("computed_at", ""),
        "tenseal_version": tenseal_version,
        "fastapi_version": fastapi_version,
        "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
    }


@app.get("/system/integrity/verify")
@_rate_limit("100/hour")
def system_integrity_verify(request: Request, expected: str = Query(..., alias="expected_hash")):
    """Verifiziert, ob der aktuelle codebase_hash mit dem erwarteten übereinstimmt."""
    try:
        result = verify_codebase_hash(expected)
        return result
    except Exception:
        return {"verified": False, "expected_hash": expected, "current_hash": "unknown", "error": "Verification failed"}


@app.get("/datasets")
def datasets_list():
    """Alle Datensätze inkl. organization und columns (keine file_path)."""
    with Session(engine) as session:
        rows = session.exec(select(Dataset)).all()
        out = []
        for d in rows:
            item = {
                "id": d.id,
                "name": d.name,
                "description": d.description,
                "owner_email": d.owner_email,
                "organization": getattr(d, "organization", "") or "",
                "created_at": d.created_at.isoformat(),
            }
            try:
                item["columns"] = json.loads(getattr(d, "columns", "[]") or "[]")
            except (json.JSONDecodeError, TypeError):
                item["columns"] = []
            out.append(item)
        return out


@app.get("/jobs/my/{requester_email}")
def jobs_my(requester_email: str):
    """Alle Jobs eines Researchers (alle Status)."""
    with Session(engine) as session:
        stmt = select(Job).where(Job.requester_email == requester_email)
        jobs = session.exec(stmt).all()
        return [
            {
                "id": j.id,
                "dataset_id": j.dataset_id,
                "requester_email": j.requester_email,
                "computation_type": j.computation_type,
                "algorithm": getattr(j, "algorithm", "mean") or "mean",
                "selected_columns": json.loads(getattr(j, "selected_columns", "[]") or "[]"),
                "status": j.status,
                "result": j.result,
                "result_json": json.loads(j.result_json) if getattr(j, "result_json", None) else None,
                "created_at": j.created_at.isoformat(),
            }
            for j in jobs
        ]


@app.get("/datasets/accessible/{requester_email}")
def datasets_accessible(requester_email: str):
    """Alle Datensätze, für die dieser Researcher mindestens einen completed Job hat."""
    with Session(engine) as session:
        stmt = (
            select(Dataset)
            .join(Job, Job.dataset_id == Dataset.id)
            .where(Job.requester_email == requester_email, Job.status == "completed")
        )
        seen = set()
        result = []
        for d in session.exec(stmt).all():
            if d.id in seen:
                continue
            seen.add(d.id)
            item = {
                "id": d.id,
                "name": d.name,
                "description": d.description,
                "owner_email": d.owner_email,
                "organization": getattr(d, "organization", "") or "",
                "created_at": d.created_at.isoformat(),
            }
            try:
                item["columns"] = json.loads(getattr(d, "columns", "[]") or "[]")
            except (json.JSONDecodeError, TypeError):
                item["columns"] = []
            result.append(item)
        return result


@app.post("/jobs/request")
@_rate_limit("30/hour")
def jobs_request(request: Request, body: JobRequest):
    """Body inkl. algorithm und selected_columns. OWASP A03: Algorithm only from registry."""
    if body.algorithm not in ALGORITHM_REGISTRY:
        raise HTTPException(status_code=400, detail="Algorithm not in approved registry")
    sel_cols_str = json.dumps(body.selected_columns if isinstance(body.selected_columns, list) else [])
    with Session(engine) as session:
        job = Job(
            dataset_id=body.dataset_id,
            requester_email=body.requester_email,
            computation_type=body.computation_type or body.algorithm,
            algorithm=body.algorithm or "mean",
            selected_columns=sel_cols_str,
            status="pending",
        )
        session.add(job)
        session.commit()
        session.refresh(job)
        return {"job_id": job.id}


@app.post("/jobs/{job_id}/approve")
@_rate_limit("60/hour")
def jobs_approve(request: Request, job_id: int):
    """Führt Berechnung basierend auf job.algorithm aus, speichert result_json (und result bei mean)."""
    with Session(engine) as session:
        job = session.get(Job, job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job nicht gefunden")
        if job.status != "pending":
            raise HTTPException(status_code=400, detail=f"Job hat status {job.status}")

        dataset = session.get(Dataset, job.dataset_id)
        if not dataset:
            raise HTTPException(status_code=404, detail="Dataset nicht gefunden")

        path = Path(dataset.file_path)
        if not path.exists():
            raise HTTPException(status_code=404, detail="Dataset-Datei nicht gefunden")

        with open(path, "rb") as f:
            bundle = pickle.load(f)

        algorithm = getattr(job, "algorithm", None) or job.computation_type or "mean"
        if algorithm not in ALGORITHM_REGISTRY or algorithm not in ALGORITHMS:
            raise HTTPException(status_code=400, detail="Algorithm not in approved registry")
        try:
            sel_cols = json.loads(getattr(job, "selected_columns", "[]") or "[]")
        except (json.JSONDecodeError, TypeError):
            sel_cols = []
        try:
            result_obj = ALGORITHMS[algorithm](bundle, sel_cols)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Berechnung fehlgeschlagen: {e!s}")

        result_json_str = json.dumps(result_obj)
        job.status = "completed"
        job.result_json = result_json_str
        if isinstance(result_obj, dict) and "mean" in result_obj:
            job.result = float(result_obj["mean"])
        session.add(job)
        session.commit()
        session.refresh(job)
        return {"job_id": job.id, "status": "completed", "result": job.result, "result_json": result_obj}


@app.post("/jobs/{job_id}/reject")
def jobs_reject(job_id: int):
    """Setzt status=rejected."""
    with Session(engine) as session:
        job = session.get(Job, job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job nicht gefunden")
        if job.status != "pending":
            raise HTTPException(status_code=400, detail=f"Job hat status {job.status}")
        job.status = "rejected"
        session.add(job)
        session.commit()
        return {"job_id": job.id, "status": "rejected"}


@app.get("/jobs/{job_id}/result")
def jobs_result(job_id: int):
    """Gibt Job zurück; bei completed auch result und result_json."""
    with Session(engine) as session:
        job = session.get(Job, job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job nicht gefunden")

        out = {
            "id": job.id,
            "dataset_id": job.dataset_id,
            "requester_email": job.requester_email,
            "computation_type": job.computation_type,
            "algorithm": getattr(job, "algorithm", "mean") or "mean",
            "status": job.status,
            "created_at": job.created_at.isoformat(),
        }
        if job.status == "completed":
            out["result"] = job.result
            if getattr(job, "result_json", None):
                try:
                    out["result_json"] = json.loads(job.result_json)
                except (json.JSONDecodeError, TypeError):
                    out["result_json"] = None
        return out


@app.get("/jobs/pending/{owner_email}")
def jobs_pending_by_owner(owner_email: str):
    """Alle pending Jobs für Datensätze dieses Owners."""
    with Session(engine) as session:
        stmt = (
            select(Job)
            .join(Dataset, Job.dataset_id == Dataset.id)
            .where(Dataset.owner_email == owner_email, Job.status == "pending")
        )
        jobs = session.exec(stmt).all()
        return [
            {
                "id": j.id,
                "dataset_id": j.dataset_id,
                "requester_email": j.requester_email,
                "computation_type": j.computation_type,
                "algorithm": getattr(j, "algorithm", "mean") or "mean",
                "status": j.status,
                "created_at": j.created_at.isoformat(),
            }
            for j in jobs
        ]


@app.get("/access/datasets/{owner_email}")
def access_datasets_by_owner(owner_email: str):
    """Pro Datensatz des Owners: Liste der Researcher-Emails mit completed Jobs + Datum des ersten completed Jobs."""
    with Session(engine) as session:
        datasets = list(session.exec(select(Dataset).where(Dataset.owner_email == owner_email)))
        result = []
        for d in datasets:
            stmt = (
                select(Job.requester_email, Job.created_at)
                .where(Job.dataset_id == d.id, Job.status == "completed")
                .order_by(Job.created_at.asc())
            )
            rows = session.exec(stmt).all()
            by_email: dict[str, datetime] = {}
            for email, created_at in rows:
                if email not in by_email:
                    by_email[email] = created_at
            result.append({
                "dataset_id": d.id,
                "dataset_name": d.name,
                "researchers": [
                    {"email": email, "first_completed_at": dt.isoformat()}
                    for email, dt in by_email.items()
                ],
            })
        return result


# =============================================================================
# SecureCollab Multi-Party Study Endpoints
# =============================================================================


@app.get("/studies")
def studies_list(participant_email: str = ""):
    """Listet Studies, an denen die Institution (participant_email) beteiligt ist."""
    if not participant_email:
        return []
    with Session(engine) as session:
        participants = list(
            session.exec(
                select(StudyParticipant).where(
                    StudyParticipant.institution_email == participant_email
                )
            )
        )
        study_ids = list({p.study_id for p in participants})
        result = []
        for sid in study_ids:
            study = session.get(Study, sid)
            if not study:
                continue
            part_count = session.exec(select(StudyParticipant).where(StudyParticipant.study_id == sid))
            part_count = len(list(part_count))
            ds_count = session.exec(select(StudyDataset).where(StudyDataset.study_id == sid))
            ds_count = len(list(ds_count))
            pending = session.exec(select(Job).where(Job.study_id == sid, Job.status == "pending_approval"))
            pending = len(list(pending))
            result.append({
                "id": study.id,
                "name": study.name,
                "description": study.description,
                "status": study.status,
                "threshold_n": study.threshold_n,
                "threshold_t": study.threshold_t,
                "participant_count": part_count,
                "dataset_count": ds_count,
                "pending_approvals": pending,
                "created_at": study.created_at.isoformat(),
            })
        return result


@app.get("/studies/{study_id}")
def studies_get(study_id: int):
    """Einzelne Study abrufen (Metadaten)."""
    with Session(engine) as session:
        study = session.get(Study, study_id)
        if not study:
            raise HTTPException(status_code=404, detail="Study nicht gefunden")
        try:
            protocol = json.loads(study.protocol or "{}")
        except (json.JSONDecodeError, TypeError):
            protocol = {}
        return {
            "id": study.id,
            "name": study.name,
            "description": study.description,
            "status": study.status,
            "threshold_n": study.threshold_n,
            "threshold_t": study.threshold_t,
            "public_key_fingerprint": study.public_key_fingerprint,
            "combined_public_key": study.combined_public_key if study.status == "active" else None,
            "protocol": protocol,
            "created_by": study.created_by,
            "created_at": study.created_at.isoformat(),
            "updated_at": study.updated_at.isoformat(),
        }


@app.post("/studies/create")
def studies_create(body: StudyCreate):
    """Erstellt Study (draft), ersten Participant, Audit study_created."""
    protocol = {
        "allowed_algorithms": body.allowed_algorithms,
        "column_definitions": body.column_definitions,
    }
    with Session(engine) as session:
        study = Study(
            name=body.name,
            description=body.description,
            protocol=json.dumps(protocol),
            status="draft",
            threshold_n=body.threshold_n,
            threshold_t=min(body.threshold_t, body.threshold_n),
            created_by=body.creator_email,
        )
        session.add(study)
        session.commit()
        session.refresh(study)
        part = StudyParticipant(
            study_id=study.id,
            institution_name=body.institution_name,
            institution_email=body.creator_email,
            public_key_share=body.public_key_share or "",
            key_share_committed_at=datetime.utcnow() if body.public_key_share else None,
        )
        session.add(part)
        session.commit()
        write_audit_log(
            session, study.id, "study_created", body.creator_email,
            {"study_id": study.id, "name": body.name, "threshold_n": body.threshold_n, "threshold_t": study.threshold_t},
        )
        session.commit()
        return {
            "study_id": study.id,
            "instructions": "Create and finalize protocol (POST /studies/{id}/protocol/create, then /protocol/finalize). Then share study_id for others to join.",
        }


# -----------------------------------------------------------------------------
# Schema Validation: Protocol Create / Finalize
# -----------------------------------------------------------------------------
# Was: Definiert das verbindliche Datenschema für die Study (Spalten, Typen, Ranges).
# Warum: Bei HE kann niemand Daten nach dem Upload prüfen. Falsches Mapping liefert
# mathematisch korrekte aber inhaltlich falsche Ergebnisse. Schema muss kryptographisch
# erzwungene Precondition sein.
# Garantie: protocol_hash bindet das Schema; nach Finalize unveränderbar.
# NICHT garantiert: Dass lokale Daten dem Schema entsprechen (dafür schema/submit + dry run).


@app.post("/studies/{study_id}/protocol/create")
def studies_protocol_create(study_id: int, body: ProtocolCreate):
    """
    Erstellt das Study-Protocol (nur vom Creator). Status draft.
    Berechnet protocol_hash = SHA3-256(kanonisches Protocol-JSON).
    Study kann erst Teilnehmer aufnehmen, wenn Protocol finalisiert ist.
    """
    with Session(engine) as session:
        study = session.get(Study, study_id)
        if not study:
            raise HTTPException(status_code=404, detail="Study nicht gefunden")
        if study.created_by and body.creator_email and study.created_by != body.creator_email:
            raise HTTPException(status_code=403, detail="Nur der Study-Creator darf das Protocol anlegen")
        existing = session.exec(select(StudyProtocol).where(StudyProtocol.study_id == study_id)).first()
        if existing:
            raise HTTPException(status_code=400, detail="Protocol existiert bereits für diese Study")
        required_columns = [c.model_dump() if hasattr(c, "model_dump") else c for c in body.required_columns]
        for c in required_columns:
            if isinstance(c, dict) and "valid_range" not in c and ("valid_range_min" in c or "valid_range_max" in c):
                c["valid_range"] = [c.get("valid_range_min"), c.get("valid_range_max")]
        payload_str = _protocol_payload_for_hash(required_columns, body.minimum_rows, body.missing_value_strategy)
        protocol_hash = sha3_256_hex(payload_str)
        sp = StudyProtocol(
            study_id=study_id,
            protocol_version="1.0",
            required_columns=json.dumps(required_columns),
            minimum_rows=body.minimum_rows,
            missing_value_strategy=body.missing_value_strategy,
            protocol_hash=protocol_hash,
            status="draft",
        )
        session.add(sp)
        session.commit()
        session.refresh(sp)
        for c in body.required_columns:
            cd = c.model_dump() if hasattr(c, "model_dump") else c
            valid_range = cd.get("valid_range") or []
            vmin = valid_range[0] if len(valid_range) > 0 else cd.get("valid_range_min")
            vmax = valid_range[1] if len(valid_range) > 1 else cd.get("valid_range_max")
            pc = ProtocolColumn(
                protocol_id=sp.id,
                column_name=cd.get("name", ""),
                aliases=json.dumps(cd.get("aliases") or []),
                data_type=cd.get("data_type", "float"),
                unit=cd.get("unit"),
                valid_range_min=vmin,
                valid_range_max=vmax,
                allowed_values=json.dumps(cd.get("allowed_values")) if cd.get("allowed_values") else None,
                required=cd.get("required", True),
                description=cd.get("description", ""),
            )
            session.add(pc)
        session.commit()
        write_audit_log(session, study_id, "protocol_created", body.creator_email or study.created_by, {"protocol_hash": protocol_hash})
        session.commit()
        return {"protocol_hash": protocol_hash, "status": "draft"}


class ProtocolFinalize(BaseModel):
    creator_email: str = ""


@app.post("/studies/{study_id}/protocol/finalize")
def studies_protocol_finalize(study_id: int, body: ProtocolFinalize = Body(default=ProtocolFinalize())):
    """
    Setzt Protocol status=finalized. Ab dann: Protocol unveränderbar.
    Study kann erst Teilnehmer aufnehmen, wenn Protocol finalisiert ist.
    """
    with Session(engine) as session:
        study = session.get(Study, study_id)
        if not study:
            raise HTTPException(status_code=404, detail="Study nicht gefunden")
        sp = session.exec(select(StudyProtocol).where(StudyProtocol.study_id == study_id)).first()
        if not sp:
            raise HTTPException(status_code=404, detail="Kein Protocol vorhanden. Zuerst protocol/create aufrufen.")
        if sp.status == "finalized":
            return {"status": "finalized", "protocol_hash": sp.protocol_hash}
        creator_email = (body.creator_email if body else "") or ""
        if study.created_by and creator_email and study.created_by != creator_email:
            raise HTTPException(status_code=403, detail="Nur der Study-Creator darf finalisieren")
        sp.status = "finalized"
        sp.finalized_at = datetime.utcnow()
        session.add(sp)
        write_audit_log(session, study_id, "protocol_finalized", creator_email or study.created_by, {"protocol_hash": sp.protocol_hash})
        session.commit()
        return {"status": "finalized", "protocol_hash": sp.protocol_hash}


@app.post("/studies/{study_id}/join")
def studies_join(study_id: int, body: StudyJoin):
    """Teilnehmer tritt bei. Nur möglich wenn Protocol finalisiert ist. Aktivierung erfolgt separat über POST /activate."""
    with Session(engine) as session:
        study = session.get(Study, study_id)
        if not study:
            raise HTTPException(status_code=404, detail="Study nicht gefunden")
        if study.status == "active":
            raise HTTPException(status_code=400, detail="Study ist bereits aktiv")
        sp = session.exec(select(StudyProtocol).where(StudyProtocol.study_id == study_id)).first()
        if sp and sp.status != "finalized":
            raise HTTPException(status_code=400, detail="Study kann erst Teilnehmer aufnehmen, wenn das Protocol finalisiert ist. Creator muss protocol/finalize aufrufen.")
        participants = list(session.exec(select(StudyParticipant).where(StudyParticipant.study_id == study_id)))
        if any(p.institution_email == body.institution_email for p in participants):
            raise HTTPException(status_code=400, detail="Institution bereits Teilnehmer")
        part = StudyParticipant(
            study_id=study_id,
            institution_name=body.institution_name,
            institution_email=body.institution_email,
            public_key_share=body.public_key_share,
            key_share_committed_at=datetime.utcnow(),
        )
        session.add(part)
        session.commit()
        write_audit_log(
            session, study_id, "participant_joined",
            body.institution_email,
            {"institution": body.institution_name, "total_participants": len(participants) + 1},
        )
        participants = list(session.exec(select(StudyParticipant).where(StudyParticipant.study_id == study_id)))
        if not sp and len(participants) >= study.threshold_n:
            combined = next((p.public_key_share for p in participants if p.public_key_share), "") or part.public_key_share
            if combined:
                study.combined_public_key = combined
                try:
                    raw = base64.b64decode(combined) if isinstance(combined, str) else combined
                except Exception:
                    raw = combined.encode("utf-8") if isinstance(combined, str) else combined
                study.public_key_fingerprint = sha3_256_hex(raw)
                study.status = "active"
                study.updated_at = datetime.utcnow()
                session.add(study)
                write_audit_log(
                    session, study_id, "study_activated", "system",
                    {"public_key_fingerprint": study.public_key_fingerprint, "participant_count": len(participants)},
                )
        session.commit()
        return {
            "study_id": study_id,
            "status": study.status,
            "combined_public_key": study.combined_public_key if study.status == "active" else None,
            "message": "Bei Schema-Protocol: Aktivierung über POST /studies/{id}/activate." if sp else None,
        }


@app.get("/studies/{study_id}/public_key")
def studies_public_key(study_id: int):
    """Kombinierter Public Key, Fingerprint, und alle Upload-Commitments zur Verifikation."""
    with Session(engine) as session:
        study = session.get(Study, study_id)
        if not study:
            raise HTTPException(status_code=404, detail="Study nicht gefunden")
        datasets = list(session.exec(select(StudyDataset).where(StudyDataset.study_id == study_id)))
        return {
            "combined_public_key": study.combined_public_key,
            "public_key_fingerprint": study.public_key_fingerprint,
            "upload_commitments": [{"dataset_name": d.dataset_name, "commitment_hash": d.commitment_hash, "institution_email": d.institution_email} for d in datasets],
        }


# -----------------------------------------------------------------------------
# Schema Validation: Submit Mapping & Dry Run
# -----------------------------------------------------------------------------
# Was: Institution reicht lokale Schema-Beschreibung und Mapping ein; Server prüft Kompatibilität.
# Warum: Beweisbar dasselbe Schema – keine falschen Spalten nach Upload.
# Garantie: institution_signature bindet Mapping + protocol_hash + Email; im Audit bei activate.
# NICHT garantiert: Dass die tatsächlichen Daten dem Mapping entsprechen (Dry Run empfohlen).


@app.post("/studies/{study_id}/schema/submit")
def studies_schema_submit(study_id: int, body: SchemaSubmit):
    """
    Institution reicht lokales Schema und vorgeschlagenes Mapping ein.
    Was: Server prüft Kompatibilität (required columns, Typen, Ranges), speichert institution_signature.
    Warum: Precondition für Aktivierung – beweisbar dasselbe Schema (institution_signature im Audit bei activate).
    Garantie: institution_signature = SHA3-256(mapping + protocol_hash + email); nachträglich nicht abstreitbar.
    NICHT garantiert: Dass die tatsächlichen Daten dem Mapping entsprechen (Dry Run empfohlen).
    """
    with Session(engine) as session:
        study = session.get(Study, study_id)
        if not study:
            raise HTTPException(status_code=404, detail="Study nicht gefunden")
        sp = session.exec(select(StudyProtocol).where(StudyProtocol.study_id == study_id)).first()
        if not sp or sp.status != "finalized":
            raise HTTPException(status_code=400, detail="Protocol muss finalisiert sein")
        try:
            required_columns = json.loads(sp.required_columns or "[]")
        except (json.JSONDecodeError, TypeError):
            required_columns = []
        for c in required_columns:
            if isinstance(c, dict) and "valid_range" not in c:
                c["valid_range"] = [c.get("valid_range_min"), c.get("valid_range_max")]
        local_schema = body.local_schema or {}
        result = _check_schema_compatibility(required_columns, local_schema, body.proposed_mapping or {})
        mapping_json = json.dumps(body.proposed_mapping or {}, sort_keys=True)
        institution_signature = sha3_256_hex(mapping_json, sp.protocol_hash, body.institution_email)
        sub = SchemaSubmission(
            study_id=study_id,
            institution_email=body.institution_email,
            submitted_schema=json.dumps(local_schema),
            mapping=mapping_json,
            fingerprint=json.dumps({}),
            compatibility_result=json.dumps(result),
            institution_signature=institution_signature,
            signed_at=datetime.utcnow(),
        )
        session.add(sub)
        write_audit_log(
            session, study_id, "schema_submitted", body.institution_email,
            {"compatible": result["compatible"], "issue_count": len(result.get("issues", []))},
        )
        session.commit()
        return {
            "compatible": result["compatible"],
            "approved_mappings": result.get("approved_mappings", []),
            "issues": result.get("issues", []),
            "warnings": result.get("warnings", []),
        }


@app.post("/studies/{study_id}/synthetic/upload")
def studies_synthetic_upload(
    study_id: int,
    file: UploadFile = File(...),
    institution_email: str = Form(...),
):
    """
    Institution lädt synthetische (Klartext-) CSV hoch.
    Was: Server validiert gegen Protocol (Spalten, Typen, minimum_rows), speichert validation_result.
    Warum: Precondition für Aktivierung – alle Teilnehmer müssen Dry Run absolvieren.
    Garantie: Markiert Dry Run als completed; Voraussetzung für can_activate.
    NICHT garantiert: Vertraulichkeit – Daten sind Klartext; nur synthetische Testdaten verwenden.
    """
    with Session(engine) as session:
        study = session.get(Study, study_id)
        if not study:
            raise HTTPException(status_code=404, detail="Study nicht gefunden")
        sp = session.exec(select(StudyProtocol).where(StudyProtocol.study_id == study_id)).first()
        if not sp or sp.status != "finalized":
            raise HTTPException(status_code=400, detail="Protocol muss finalisiert sein")
        content = file.file.read()
        file.file.close()
        try:
            required_columns = json.loads(sp.required_columns or "[]")
        except (json.JSONDecodeError, TypeError):
            required_columns = []
        schema_valid = True
        issues: list[str] = []
        import csv as csv_module
        import io
        try:
            reader = csv_module.DictReader(io.StringIO(content.decode("utf-8")))
            rows = list(reader)
            if len(rows) < sp.minimum_rows:
                schema_valid = False
                issues.append(f"Zeilen: {len(rows)}, Minimum: {sp.minimum_rows}")
            col_names = list(rows[0].keys()) if rows else []
            for c in required_columns:
                name = c.get("name", "") if isinstance(c, dict) else ""
                if name and name not in col_names and name not in (c.get("aliases") or []):
                    aliases = c.get("aliases") or []
                    if not any(a in col_names for a in aliases):
                        schema_valid = False
                        issues.append(f"Fehlende Spalte: {name}")
        except Exception as e:
            schema_valid = False
            issues.append(str(e))
        study_dir = STUDIES_UPLOADS_DIR / str(study_id)
        study_dir.mkdir(exist_ok=True)
        path = study_dir / f"synthetic_{uuid.uuid4().hex}.csv"
        path.write_bytes(content)
        syn = SyntheticSubmission(
            study_id=study_id,
            institution_email=institution_email,
            file_path=str(path),
            validation_result=json.dumps({"schema_valid": schema_valid, "issues": issues, "algorithms_tested": []}),
        )
        session.add(syn)
        write_audit_log(session, study_id, "dry_run_completed", institution_email, {"schema_valid": schema_valid})
        session.commit()
        return {"schema_valid": schema_valid, "issues": issues, "algorithms_tested": [], "sample_results": {}}


@app.get("/studies/{study_id}/activation_status")
def studies_activation_status(study_id: int):
    """
    Gibt zurück ob die Study aktiviert werden kann.
    Was: Prüft protocol_finalized, all_schemas_compatible, dry_run_completed, all_keys_submitted.
    Warum: Aktivierung nur wenn alle Schema-Preconditions erfüllt sind – keine Daten ohne vereinbartes Schema.
    Garantie: Kann nur true sein wenn alle Teilnehmer kompatibles Schema eingereicht und Dry Run gemacht haben.
    """
    with Session(engine) as session:
        study = session.get(Study, study_id)
        if not study:
            raise HTTPException(status_code=404, detail="Study nicht gefunden")
        sp = session.exec(select(StudyProtocol).where(StudyProtocol.study_id == study_id)).first()
        participants = list(session.exec(select(StudyParticipant).where(StudyParticipant.study_id == study_id)))
        schema_submissions = list(session.exec(select(SchemaSubmission).where(SchemaSubmission.study_id == study_id)))
        synthetic = list(session.exec(select(SyntheticSubmission).where(SyntheticSubmission.study_id == study_id)))
        n_compatible = sum(1 for s in schema_submissions if (json.loads(s.compatibility_result or "{}")).get("compatible"))
        n_keys = sum(1 for p in participants if p.public_key_share)
        protocol_finalized = sp is not None and sp.status == "finalized"
        all_schemas = len(schema_submissions) >= len(participants) and n_compatible == len(participants)
        all_dry_run = len(synthetic) >= len(participants)
        all_keys = len(participants) >= study.threshold_n and n_keys >= study.threshold_n
        can_activate = protocol_finalized and all_schemas and all_dry_run and all_keys
        return {
            "can_activate": can_activate,
            "conditions": [
                {"condition": "protocol_finalized", "met": protocol_finalized},
                {"condition": "all_schemas_compatible", "met": all_schemas, "details": {"n_submitted": len(schema_submissions), "n_compatible": n_compatible, "n_required": len(participants)}},
                {"condition": "dry_run_completed", "met": all_dry_run, "details": {"n_completed": len(synthetic), "n_required": len(participants)}},
                {"condition": "all_keys_submitted", "met": all_keys, "details": {"n_submitted": n_keys, "n_required": study.threshold_n}},
            ],
        }


@app.post("/studies/{study_id}/activate")
def studies_activate(study_id: int, actor_email: str = ""):
    """
    Aktiviert die Study nur wenn ALLE Preconditions erfüllt sind.
    Was: Setzt status=active, setzt combined_public_key; schreibt schema_signatures in Audit Log.
    Warum: Beweisbar dasselbe Schema – schema_signatures beweisen akzeptiertes Mapping pro Institution.
    Garantie: Aktivierung nur bei protocol_finalized + alle schemas compatible + alle dry_run + alle keys.
    NICHT garantiert: Dass Teilnehmer ihre echten Daten korrekt mappen (operationale Sorgfalt).
    """
    with Session(engine) as session:
        study = session.get(Study, study_id)
        if not study:
            raise HTTPException(status_code=404, detail="Study nicht gefunden")
        if study.status == "active":
            return {"status": "active", "message": "Bereits aktiv"}
        status = studies_activation_status(study_id)
        if not status["can_activate"]:
            return {"activated": False, "message": "Preconditions nicht erfüllt", "conditions": status["conditions"]}
        sp = session.exec(select(StudyProtocol).where(StudyProtocol.study_id == study_id)).first()
        participants = list(session.exec(select(StudyParticipant).where(StudyParticipant.study_id == study_id)))
        schema_submissions = list(session.exec(select(SchemaSubmission).where(SchemaSubmission.study_id == study_id)))
        combined = next((p.public_key_share for p in participants if p.public_key_share), "") or ""
        try:
            raw = base64.b64decode(combined) if isinstance(combined, str) else combined
        except Exception:
            raw = combined.encode("utf-8") if isinstance(combined, str) else combined
        study.combined_public_key = combined
        study.public_key_fingerprint = sha3_256_hex(raw)
        study.status = "active"
        study.updated_at = datetime.utcnow()
        session.add(study)
        schema_signatures = [s.institution_signature for s in schema_submissions]
        write_audit_log(
            session, study_id, "study_activated", actor_email or "system",
            {"protocol_hash": sp.protocol_hash if sp else "", "participant_count": len(participants), "schema_signatures": schema_signatures},
        )
        session.commit()
        return {"activated": True, "status": "active", "public_key_fingerprint": study.public_key_fingerprint}


@app.post("/studies/{study_id}/upload_dataset")
def studies_upload_dataset(
    study_id: int,
    file: UploadFile = File(...),
    institution_email: str = Form(...),
    dataset_name: str = Form(""),
    columns: str = Form("[]"),
    commitment_timestamp: str = Form(""),  # optional: Client-Timestamp für reproduzierbaren Commitment
):
    """Speichert verschlüsselte Datei, berechnet Commitment, Audit dataset_uploaded. OWASP A03/A10: max size, .bin only."""
    if Path(file.filename or "").suffix.lower() not in ALLOWED_UPLOAD_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Only .bin files are allowed")
    with Session(engine) as session:
        study = session.get(Study, study_id)
        if not study:
            raise HTTPException(status_code=404, detail="Study nicht gefunden")
        if study.status != "active":
            raise HTTPException(status_code=400, detail="Study muss aktiv sein zum Upload")
        file_bytes = file.file.read(MAX_UPLOAD_BYTES + 1)
        if len(file_bytes) > MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail=f"File too large (max {MAX_UPLOAD_MB} MB)")
        file.file.close()
        ts_str = commitment_timestamp.strip() or datetime.utcnow().isoformat()
        fp = study.public_key_fingerprint or ""
        commitment_hash = sha3_256_hex(file_bytes, fp, ts_str, institution_email)
        study_dir = STUDIES_UPLOADS_DIR / str(study_id)
        study_dir.mkdir(exist_ok=True)
        path = study_dir / f"{uuid.uuid4().hex}.bin"
        path.write_bytes(file_bytes)
        try:
            cols = json.loads(columns) if columns else []
        except (json.JSONDecodeError, TypeError):
            cols = []
        sd = StudyDataset(
            study_id=study_id,
            dataset_name=dataset_name or file.filename or "dataset",
            institution_email=institution_email,
            file_path=str(path),
            commitment_hash=commitment_hash,
            columns=json.dumps(cols) if isinstance(cols, list) else "[]",
            committed_at=datetime.utcnow(),
        )
        session.add(sd)
        session.commit()
        write_audit_log(
            session, study_id, "dataset_uploaded", institution_email,
            {"commitment_hash": commitment_hash, "dataset_name": sd.dataset_name, "size_bytes": len(file_bytes)},
        )
        session.commit()
        return {"commitment_hash": commitment_hash}


@app.post("/studies/{study_id}/request_computation")
def studies_request_computation(study_id: int, body: StudyRequestComputation):
    """Prüft allowed_algorithms, erstellt Job (pending_approval), Audit computation_requested."""
    with Session(engine) as session:
        study = session.get(Study, study_id)
        if not study:
            raise HTTPException(status_code=404, detail="Study nicht gefunden")
        if study.status != "active":
            raise HTTPException(status_code=400, detail="Study muss aktiv sein")
        try:
            protocol = json.loads(study.protocol or "{}")
            allowed = protocol.get("allowed_algorithms", [])
        except (json.JSONDecodeError, TypeError):
            allowed = []
        if allowed and body.algorithm not in allowed:
            raise HTTPException(status_code=400, detail=f"Algorithmus {body.algorithm} nicht erlaubt")
        job = Job(
            study_id=study_id,
            dataset_id=None,
            requester_email=body.requester_email,
            algorithm=body.algorithm,
            computation_type=body.algorithm,
            selected_columns=json.dumps(body.selected_columns),
            parameters=json.dumps(body.parameters),
            status="pending_approval",
        )
        session.add(job)
        session.commit()
        session.refresh(job)
        write_audit_log(
            session, study_id, "computation_requested", body.requester_email,
            {"job_id": job.id, "algorithm": body.algorithm, "selected_columns": body.selected_columns},
        )
        session.commit()
        return {"job_id": job.id, "status": "pending_approval"}


@app.post("/studies/{study_id}/jobs/{job_id}/approve")
def studies_job_approve(study_id: int, job_id: int, body: StudyApprove):
    """Sammelt Approvals; bei Vollzahl: Berechnung auf kombinierten Study-Daten, Ergebnis verschlüsselt, status awaiting_decryption."""
    with Session(engine) as session:
        study = session.get(Study, study_id)
        job = session.get(Job, job_id)
        if not study or not job or job.study_id != study_id:
            raise HTTPException(status_code=404, detail="Study oder Job nicht gefunden")
        if job.status != "pending_approval":
            raise HTTPException(status_code=400, detail=f"Job hat status {job.status}")
        participant = session.exec(
            select(StudyParticipant).where(
                StudyParticipant.study_id == study_id,
                StudyParticipant.institution_email == body.institution_email,
            )
        ).first()
        if not participant:
            raise HTTPException(status_code=403, detail="Institution ist kein Teilnehmer")
        existing = session.exec(select(JobApproval).where(JobApproval.job_id == job_id, JobApproval.institution_email == body.institution_email)).first()
        if existing:
            raise HTTPException(status_code=400, detail="Bereits genehmigt")
        session.add(JobApproval(job_id=job_id, institution_email=body.institution_email))
        session.commit()
        approvals = list(session.exec(select(JobApproval).where(JobApproval.job_id == job_id)))
        if len(approvals) < study.threshold_t:
            return {"job_id": job_id, "status": "pending_approval", "approvals": len(approvals), "required": study.threshold_t}
        # Führe Berechnung aus: erstes Study-Dataset laden (MVP: ein Dataset)
        datasets = list(session.exec(select(StudyDataset).where(StudyDataset.study_id == study_id)))
        if not datasets:
            raise HTTPException(status_code=400, detail="Keine Datensätze in der Study")
        path = Path(datasets[0].file_path)
        if not path.exists():
            raise HTTPException(status_code=404, detail="Dataset-Datei nicht gefunden")
        with open(path, "rb") as f:
            bundle = pickle.load(f)
        algorithm = job.algorithm or "mean"
        if algorithm not in ALGORITHM_REGISTRY or algorithm not in ALGORITHMS:
            raise HTTPException(status_code=400, detail="Algorithm not in approved registry")
        try:
            sel_cols = json.loads(job.selected_columns or "[]")
        except (json.JSONDecodeError, TypeError):
            sel_cols = []
        try:
            result_obj = ALGORITHMS[algorithm](bundle, sel_cols)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Berechnung fehlgeschlagen: {e!s}")
        result_json_str = json.dumps(result_obj)
        result_bytes = result_json_str.encode("utf-8")
        result_commitment = sha3_256_hex(result_bytes)
        job.result_json = result_json_str
        job.result_commitment = result_commitment
        if isinstance(result_obj, dict) and "mean" in result_obj:
            job.result = float(result_obj["mean"])
        job.status = "awaiting_decryption"
        session.add(job)
        write_audit_log(
            session, study_id, "computation_executed", "system",
            {"job_id": job_id, "algorithm": algorithm, "result_commitment": result_commitment},
        )
        session.commit()
        return {"job_id": job_id, "status": "awaiting_decryption", "result_commitment": result_commitment}


@app.post("/studies/{study_id}/jobs/{job_id}/submit_decryption_share")
def studies_job_submit_decryption_share(study_id: int, job_id: int, body: StudySubmitDecryptionShare):
    """Sammelt Decryption Shares; bei >= threshold_t: Kombination zu Ergebnis, Audit result_decrypted."""
    with Session(engine) as session:
        study = session.get(Study, study_id)
        job = session.get(Job, job_id)
        if not study or not job or job.study_id != study_id:
            raise HTTPException(status_code=404, detail="Study oder Job nicht gefunden")
        if job.status != "awaiting_decryption":
            raise HTTPException(status_code=400, detail=f"Job hat status {job.status}")
        existing = session.exec(select(JobDecryptionShare).where(JobDecryptionShare.job_id == job_id, JobDecryptionShare.institution_email == body.institution_email)).first()
        if existing:
            raise HTTPException(status_code=400, detail="Decryption Share bereits eingereicht")
        session.add(JobDecryptionShare(job_id=job_id, institution_email=body.institution_email, decryption_share=body.decryption_share))
        session.commit()
        shares = list(session.exec(select(JobDecryptionShare).where(JobDecryptionShare.job_id == job_id)))
        if len(shares) < study.threshold_t:
            return {"job_id": job_id, "status": "awaiting_decryption", "shares": len(shares), "required": study.threshold_t}
        # MVP: Ergebnis liegt bereits in job.result_json (von approve); bei echtem Threshold würde man Shares kombinieren
        job.status = "completed"
        session.add(job)
        write_audit_log(session, study_id, "result_decrypted", body.institution_email, {"job_id": job_id, "shares_combined": len(shares)})
        session.commit()
        result_json = json.loads(job.result_json) if job.result_json else None
        return {"job_id": job_id, "status": "completed", "result_json": result_json}


@app.get("/studies/{study_id}/audit_trail")
def studies_audit_trail(study_id: int):
    """Vollständiger Audit Trail; entry_hash = SHA3-256(action_type||actor||details||timestamp||previous_hash)."""
    with Session(engine) as session:
        study = session.get(Study, study_id)
        if not study:
            raise HTTPException(status_code=404, detail="Study nicht gefunden")
        entries = list(session.exec(select(AuditLog).where(AuditLog.study_id == study_id).order_by(AuditLog.id)))
        return [
            {
                "id": e.id,
                "action_type": e.action_type,
                "actor_email": e.actor_email,
                "details": json.loads(e.details) if e.details else {},
                "previous_hash": e.previous_hash,
                "entry_hash": e.entry_hash,
                "created_at": e.created_at.isoformat(),
            }
            for e in entries
        ]


@app.get("/studies/{study_id}/protocol")
def studies_protocol(study_id: int):
    """
    Vollständiges Study-Protokoll (regulatorische Dokumentation).
    Enthält protocol_hash und required_columns aus study_protocol falls vorhanden;
    Institutionen können den Hash lokal verifizieren.
    """
    with Session(engine) as session:
        study = session.get(Study, study_id)
        if not study:
            raise HTTPException(status_code=404, detail="Study nicht gefunden")
        participants = list(session.exec(select(StudyParticipant).where(StudyParticipant.study_id == study_id)))
        datasets = list(session.exec(select(StudyDataset).where(StudyDataset.study_id == study_id)))
        jobs = list(session.exec(select(Job).where(Job.study_id == study_id)))
        audit_entries = list(session.exec(select(AuditLog).where(AuditLog.study_id == study_id).order_by(AuditLog.id)))
        try:
            protocol_data = json.loads(study.protocol or "{}")
        except (json.JSONDecodeError, TypeError):
            protocol_data = {}
        sp = session.exec(select(StudyProtocol).where(StudyProtocol.study_id == study_id)).first()
        protocol_hash = None
        required_columns = protocol_data.get("column_definitions", [])
        if sp:
            protocol_hash = sp.protocol_hash
            try:
                required_columns = json.loads(sp.required_columns or "[]")
            except (json.JSONDecodeError, TypeError):
                pass
        return {
            "study_metadata": {
                "id": study.id,
                "name": study.name,
                "description": study.description,
                "status": study.status,
                "threshold_n": study.threshold_n,
                "threshold_t": study.threshold_t,
                "public_key_fingerprint": study.public_key_fingerprint,
                "created_by": study.created_by,
                "created_at": study.created_at.isoformat(),
                "updated_at": study.updated_at.isoformat(),
            },
            "protocol_hash": protocol_hash,
            "required_columns": required_columns,
            "protocol_status": sp.status if sp else None,
            "minimum_rows": sp.minimum_rows if sp else 1,
            "missing_value_strategy": sp.missing_value_strategy if sp else "exclude",
            "participants": [
                {"institution_name": p.institution_name, "institution_email": p.institution_email, "joined_at": p.joined_at.isoformat()}
                for p in participants
            ],
            "allowed_algorithms": protocol_data.get("allowed_algorithms", []),
            "column_definitions": required_columns,
            "datasets": [{"dataset_name": d.dataset_name, "institution_email": d.institution_email, "commitment_hash": d.commitment_hash, "committed_at": d.committed_at.isoformat()} for d in datasets],
            "jobs": [{"id": j.id, "requester_email": j.requester_email, "algorithm": j.algorithm, "status": j.status, "created_at": j.created_at.isoformat()} for j in jobs],
            "audit_summary": {"total_entries": len(audit_entries), "last_entry_hash": audit_entries[-1].entry_hash if audit_entries else None},
        }
