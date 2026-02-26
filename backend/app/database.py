# SPDX-License-Identifier: Apache-2.0
"""DB connection and session management."""
from __future__ import annotations

from contextlib import contextmanager

from sqlalchemy import text
from sqlmodel import Session, create_engine

from app.config import SQLITE_URL
from app.models import (  # noqa: F401 – register all models with SQLModel.metadata
    AuditLog,
    Dataset,
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

connect_args = {"check_same_thread": False} if SQLITE_URL.startswith("sqlite") else {}
engine = create_engine(SQLITE_URL, connect_args=connect_args)


def get_session():
    """Yield a DB session (for FastAPI Depends)."""
    with Session(engine) as session:
        yield session


@contextmanager
def session_scope():
    """Context manager for use outside request handlers."""
    with Session(engine) as session:
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise


def create_db_and_tables():
    """Create all tables and optionally add missing columns (migration helper)."""
    from sqlmodel import SQLModel

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
