# SPDX-License-Identifier: Apache-2.0
"""Job request, approve, reject, result, list."""
import json
import pickle
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request

from app.core.algorithms import ALGORITHM_REGISTRY
from app.core.security import rate_limit
from app.database import Session, engine
from app.models import Dataset, Job
from app.schemas import JobRequest
from app.services.he_service import run_computation
from sqlmodel import select

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/my/{requester_email}")
def jobs_my(requester_email: str):
    """All jobs for a researcher (all statuses)."""
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


@router.post("/request")
@rate_limit("30/hour")
def jobs_request(request: Request, body: JobRequest):
    """Create job. Algorithm must be in registry."""
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


@router.post("/{job_id}/approve")
@rate_limit("60/hour")
def jobs_approve(request: Request, job_id: int):
    """Run computation for job, store result_json."""
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
        if algorithm not in ALGORITHM_REGISTRY:
            raise HTTPException(status_code=400, detail="Algorithm not in approved registry")
        try:
            sel_cols = json.loads(getattr(job, "selected_columns", "[]") or "[]")
        except (json.JSONDecodeError, TypeError):
            sel_cols = []
        try:
            result_obj = run_computation(bundle, algorithm, sel_cols)
        except Exception:
            import logging
            logging.getLogger("securecollab").exception("HE computation failed for job %s", job_id)
            raise HTTPException(status_code=500, detail="Computation failed. Check algorithm and columns.")
        result_json_str = json.dumps(result_obj)
        job.status = "completed"
        job.result_json = result_json_str
        if isinstance(result_obj, dict) and "mean" in result_obj:
            job.result = float(result_obj["mean"])
        session.add(job)
        session.commit()
        session.refresh(job)
        return {"job_id": job.id, "status": "completed", "result": job.result, "result_json": result_obj}


@router.post("/{job_id}/reject")
def jobs_reject(job_id: int):
    """Set status=rejected."""
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


@router.get("/{job_id}/result")
def jobs_result(job_id: int):
    """Return job; if completed include result and result_json."""
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


@router.get("/pending/{owner_email}")
def jobs_pending_by_owner(owner_email: str):
    """Pending jobs for datasets owned by this owner."""
    with Session(engine) as session:
        stmt = select(Job).join(Dataset, Job.dataset_id == Dataset.id).where(
            Dataset.owner_email == owner_email, Job.status == "pending"
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
