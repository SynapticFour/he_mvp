# SPDX-License-Identifier: Apache-2.0
"""Dataset upload, list, columns, accessible."""
import json
import uuid
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile

from app.config import (
    ALLOWED_UPLOAD_EXTENSIONS,
    CKKS_BYTES_PER_SLOT_HEURISTIC,
    MAX_UPLOAD_BYTES,
    MAX_UPLOAD_MB,
    UPLOADS_DIR,
)
from app.core.security import rate_limit, sanitize_text, secure_filename
from app.database import Session, engine
from app.models import Dataset, Job
from sqlmodel import select

router = APIRouter(tags=["datasets"])


@router.post("/upload")
@rate_limit("10/hour")
async def datasets_upload(
    request: Request,
    file: UploadFile = File(..., description="encrypted.bin"),
    name: str = Form(...),
    description: str = Form(...),
    owner_email: str = Form(...),
    organization: str = Form(""),
    columns: str = Form("[]"),
    declared_rows: str = Form(""),
):
    """Binary file + form fields. Max size, .bin only, path traversal prevention."""
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
    contents = await file.read()
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
    with Session(engine) as session:
        dataset = Dataset(
            name=name,
            description=description,
            file_path=str(file_path),
            owner_email=owner_email[:254],
            organization=organization or "",
            columns=columns_clean,
        )
        session.add(dataset)
        session.commit()
        session.refresh(dataset)
        return {"dataset_id": dataset.id}


@router.get("/{dataset_id}/columns")
def dataset_columns(dataset_id: int):
    """Return stored column names as array."""
    with Session(engine) as session:
        dataset = session.get(Dataset, dataset_id)
        if not dataset:
            raise HTTPException(status_code=404, detail="Dataset nicht gefunden")
        try:
            cols = json.loads(dataset.columns or "[]")
            return cols if isinstance(cols, list) else []
        except (json.JSONDecodeError, TypeError):
            return []


@router.get("")
def datasets_list():
    """All datasets with organization and columns (no file_path)."""
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


@router.get("/accessible/{requester_email}")
def datasets_accessible(requester_email: str):
    """All datasets for which this researcher has at least one completed job."""
    with Session(engine) as session:
        stmt = select(Dataset).join(Job, Job.dataset_id == Dataset.id).where(
            Job.requester_email == requester_email, Job.status == "completed"
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
