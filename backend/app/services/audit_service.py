# SPDX-License-Identifier: Apache-2.0
"""Append-only audit trail with chained hashes."""
from __future__ import annotations

import json
from datetime import datetime

from sqlmodel import select

from app.config import INITIAL_HASH
from app.core.security import sha3_256_hex
from app.models import AuditLog
from app.services.integrity_service import get_deployment_integrity


def write_audit_log(
    session,
    study_id: int | None,
    action_type: str,
    actor_email: str,
    details: dict,
) -> None:
    """Append-only Audit Log: previous_hash chain, entry_hash = SHA3-256(...). Includes codebase_hash."""
    codebase_hash = get_deployment_integrity().get("codebase_hash", "unknown")
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
