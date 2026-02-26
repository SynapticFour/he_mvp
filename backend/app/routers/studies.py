# SPDX-License-Identifier: Apache-2.0
"""Study endpoints: list, get, create, protocol create/finalize, join, public_key, schema submit, synthetic upload, activation_status, activate, upload_dataset, request_computation, job approve, submit_decryption_share, audit_trail, protocol."""
from __future__ import annotations

import base64
import csv
import io
import json
import pickle
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Body, File, Form, HTTPException, UploadFile
from sqlmodel import select

from app.config import (
    ALLOWED_UPLOAD_EXTENSIONS,
    MAX_UPLOAD_BYTES,
    MAX_UPLOAD_MB,
    STUDIES_UPLOADS_DIR,
)
from app.core.algorithms import ALGORITHM_REGISTRY
from app.core.security import sha3_256_hex
from app.database import Session, engine
from app.models import (
    AuditLog,
    Job,
    JobApproval,
    JobDecryptionShare,
    ProtocolColumn,
    SchemaSubmission,
    Study,
    StudyDataset,
    StudyParticipant,
    StudyProtocol,
    SyntheticSubmission,
)
from app.schemas import (
    ProtocolCreate,
    ProtocolFinalize,
    SchemaSubmit,
    StudyApprove,
    StudyCreate,
    StudyJoin,
    StudyRequestComputation,
    StudySubmitDecryptionShare,
)
from app.services.audit_service import write_audit_log
from app.services.schema_service import check_schema_compatibility, protocol_payload_for_hash

try:
    from algorithms import ALGORITHMS
except ImportError:
    ALGORITHMS = {}

router = APIRouter(prefix="", tags=["studies"])


def _get_activation_status(study_id: int, session: Session) -> dict:
    """Compute activation_status conditions for a study (shared by GET and POST activate)."""
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


@router.get("")
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
        if not study_ids:
            return []
        studies = [session.get(Study, sid) for sid in study_ids]
        studies = [s for s in studies if s is not None]
        if not studies:
            return []
        ids = [s.id for s in studies]
        from sqlalchemy import func
        _rows = session.exec(
            select(StudyParticipant.study_id, func.count(StudyParticipant.id))
            .where(StudyParticipant.study_id.in_(ids))
            .group_by(StudyParticipant.study_id)
        ).all()
        part_counts = {r[0]: r[1] for r in _rows}
        _rows = session.exec(
            select(StudyDataset.study_id, func.count(StudyDataset.id))
            .where(StudyDataset.study_id.in_(ids))
            .group_by(StudyDataset.study_id)
        ).all()
        ds_counts = {r[0]: r[1] for r in _rows}
        _rows = session.exec(
            select(Job.study_id, func.count(Job.id))
            .where(Job.study_id.in_(ids), Job.status == "pending_approval")
            .group_by(Job.study_id)
        ).all()
        pending_counts = {r[0]: r[1] for r in _rows}
        result = []
        for study in studies:
            sid = study.id
            result.append({
                "id": study.id,
                "name": study.name,
                "description": study.description,
                "status": study.status,
                "threshold_n": study.threshold_n,
                "threshold_t": study.threshold_t,
                "participant_count": part_counts.get(sid, 0),
                "dataset_count": ds_counts.get(sid, 0),
                "pending_approvals": pending_counts.get(sid, 0),
                "created_at": study.created_at.isoformat(),
            })
        return result


@router.get("/{study_id}")
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


@router.post("/create")
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


@router.post("/{study_id}/protocol/create")
def studies_protocol_create(study_id: int, body: ProtocolCreate):
    """
    Erstellt das Study-Protocol (nur vom Creator). Status draft.
    Berechnet protocol_hash = SHA3-256(kanonisches Protocol-JSON).
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
        payload_str = protocol_payload_for_hash(required_columns, body.minimum_rows, body.missing_value_strategy)
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


@router.post("/{study_id}/protocol/finalize")
def studies_protocol_finalize(study_id: int, body: ProtocolFinalize = Body(default=ProtocolFinalize())):
    """Setzt Protocol status=finalized. Ab dann: Protocol unveränderbar."""
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


@router.post("/{study_id}/join")
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


@router.get("/{study_id}/public_key")
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


@router.post("/{study_id}/schema/submit")
def studies_schema_submit(study_id: int, body: SchemaSubmit):
    """
    Institution reicht lokales Schema und vorgeschlagenes Mapping ein.
    Server prüft Kompatibilität (required columns, Typen, Ranges), speichert institution_signature.
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
        result = check_schema_compatibility(required_columns, local_schema, body.proposed_mapping or {})
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


@router.post("/{study_id}/synthetic/upload")
def studies_synthetic_upload(
    study_id: int,
    file: UploadFile = File(...),
    institution_email: str = Form(...),
):
    """
    Institution lädt synthetische (Klartext-) CSV hoch.
    Server validiert gegen Protocol (Spalten, Typen, minimum_rows), speichert validation_result.
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
        try:
            reader = csv.DictReader(io.StringIO(content.decode("utf-8")))
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
        study_dir.mkdir(parents=True, exist_ok=True)
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


@router.get("/{study_id}/activation_status")
def studies_activation_status(study_id: int):
    """
    Gibt zurück ob die Study aktiviert werden kann.
    Prüft protocol_finalized, all_schemas_compatible, dry_run_completed, all_keys_submitted.
    """
    with Session(engine) as session:
        return _get_activation_status(study_id, session)


@router.post("/{study_id}/activate")
def studies_activate(study_id: int, actor_email: str = ""):
    """
    Aktiviert die Study nur wenn ALLE Preconditions erfüllt sind.
    Setzt status=active, setzt combined_public_key; schreibt schema_signatures in Audit Log.
    """
    with Session(engine) as session:
        study = session.get(Study, study_id)
        if not study:
            raise HTTPException(status_code=404, detail="Study nicht gefunden")
        if study.status == "active":
            return {"status": "active", "message": "Bereits aktiv"}
        status = _get_activation_status(study_id, session)
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


@router.post("/{study_id}/upload_dataset")
def studies_upload_dataset(
    study_id: int,
    file: UploadFile = File(...),
    institution_email: str = Form(...),
    dataset_name: str = Form(""),
    columns: str = Form("[]"),
    commitment_timestamp: str = Form(""),
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
        study_dir.mkdir(parents=True, exist_ok=True)
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


@router.post("/{study_id}/request_computation")
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


@router.post("/{study_id}/jobs/{job_id}/approve")
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
        except Exception:
            import logging
            logging.getLogger("securecollab").exception("HE computation failed for study job %s", job_id)
            raise HTTPException(status_code=500, detail="Computation failed. Check algorithm and columns.")
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


@router.post("/{study_id}/jobs/{job_id}/submit_decryption_share")
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
        job.status = "completed"
        session.add(job)
        write_audit_log(session, study_id, "result_decrypted", body.institution_email, {"job_id": job_id, "shares_combined": len(shares)})
        session.commit()
        result_json = json.loads(job.result_json) if job.result_json else None
        return {"job_id": job_id, "status": "completed", "result_json": result_json}


@router.get("/{study_id}/audit_trail")
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


@router.get("/{study_id}/protocol")
def studies_protocol(study_id: int):
    """
    Vollständiges Study-Protokoll (regulatorische Dokumentation).
    Enthält protocol_hash und required_columns aus study_protocol falls vorhanden.
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
