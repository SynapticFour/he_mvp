# SPDX-License-Identifier: Apache-2.0
"""Audit service: write_audit_log."""
from app.database import Session, engine, create_db_and_tables
from app.services.audit_service import write_audit_log


def test_write_audit_log():
    create_db_and_tables()
    with Session(engine) as session:
        write_audit_log(
            session,
            study_id=None,
            action_type="test_action",
            actor_email="test@example.com",
            details={"key": "value"},
        )
        session.commit()
    with Session(engine) as session:
        from app.models import AuditLog
        from sqlmodel import select
        logs = list(session.exec(select(AuditLog).where(AuditLog.action_type == "test_action")).all())
        assert len(logs) >= 1
        assert logs[0].actor_email == "test@example.com"
        assert "codebase_hash" in (logs[0].details or "")
