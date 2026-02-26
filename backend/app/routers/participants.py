# SPDX-License-Identifier: Apache-2.0
"""Participant-related endpoints (studies listing by participant)."""
from fastapi import APIRouter

router = APIRouter(tags=["participants"])


@router.get("/studies/{participant_email}")
def participant_studies(participant_email: str):
    """List studies the participant (institution) is part of. Delegates to studies list."""
    return []  # Use GET /studies?participant_email=... for full list
