# SPDX-License-Identifier: Apache-2.0
"""FastAPI app factory. Thin layer: security middleware + routers only."""
from fastapi import FastAPI

from app.config import settings
from app.core.algorithms import ALGORITHM_REGISTRY
from app.core.security import add_security_middleware, get_limiter
from app.database import Session, create_db_and_tables, engine
from app.models import Dataset, Job
from app.routers import datasets, jobs, participants, studies, system
from sqlmodel import select


def create_app() -> FastAPI:
    app = FastAPI(title="SecureCollab API", version="0.1.0")
    limiter = get_limiter()
    if limiter is not None:
        app.state.limiter = limiter

    add_security_middleware(app)

    @app.on_event("startup")
    def on_startup():
        settings.upload_dir_path.mkdir(parents=True, exist_ok=True)
        settings.studies_upload_dir_path.mkdir(parents=True, exist_ok=True)
        create_db_and_tables()
        if settings.compute_codebase_hash_on_startup:
            from app.services.integrity_service import get_deployment_integrity
            get_deployment_integrity()

    app.include_router(studies.router, prefix="/studies")
    app.include_router(datasets.router, prefix="/datasets")
    app.include_router(jobs.router, prefix="/jobs")
    app.include_router(system.router, prefix="/system")
    app.include_router(participants.router, prefix="/participants")

    @app.get("/algorithms")
    def algorithms_list():
        """Full algorithm registry for frontend and SDK."""
        return ALGORITHM_REGISTRY

    @app.get("/access/datasets/{owner_email}")
    def access_datasets_by_owner(owner_email: str):
        """Per dataset of owner: list of researcher emails with completed jobs + first completed date."""
        with Session(engine) as session:
            datasets_list = list(session.exec(select(Dataset).where(Dataset.owner_email == owner_email)))
            result = []
            for d in datasets_list:
                stmt = (
                    select(Job.requester_email, Job.created_at)
                    .where(Job.dataset_id == d.id, Job.status == "completed")
                    .order_by(Job.created_at.asc())
                )
                rows = session.exec(stmt).all()
                by_email = {}
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

    return app


app = create_app()
