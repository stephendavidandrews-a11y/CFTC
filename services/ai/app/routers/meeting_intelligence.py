"""Meeting intelligence API — fetch structured meeting briefs."""

import json
import logging

from fastapi import APIRouter, Depends, HTTPException
from app.db import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/meeting-intelligence", tags=["meeting-intelligence"])


@router.get("/by-meeting/{meeting_id}")
def get_intelligence_by_meeting(meeting_id: str, db=Depends(get_db)):
    """Get the latest meeting intelligence for a tracker meeting_id."""
    row = db.execute(
        """
        SELECT * FROM meeting_intelligence
        WHERE meeting_id = ?
        ORDER BY version DESC
        LIMIT 1
    """,
        (meeting_id,),
    ).fetchone()

    if not row:
        raise HTTPException(404, detail="No intelligence found for this meeting")

    # Parse JSON fields
    json_fields = [
        "decisions_made",
        "non_decisions",
        "action_items_summary",
        "risks_surfaced",
        "briefing_required",
        "key_issues_discussed",
        "participant_positions",
        "dependencies_surfaced",
        "commitments_made",
        "recommended_next_move",
        "materials_referenced",
        "tags",
    ]

    result = dict(row)
    for field in json_fields:
        val = result.get(field)
        if val and isinstance(val, str):
            try:
                result[field] = json.loads(val)
            except (json.JSONDecodeError, TypeError):
                pass

    return result


@router.get("/by-communication/{communication_id}")
def get_intelligence_by_communication(communication_id: str, db=Depends(get_db)):
    """Get meeting intelligence by source communication_id."""
    row = db.execute(
        """
        SELECT * FROM meeting_intelligence
        WHERE communication_id = ?
        ORDER BY version DESC
        LIMIT 1
    """,
        (communication_id,),
    ).fetchone()

    if not row:
        raise HTTPException(404, detail="No intelligence found for this communication")

    json_fields = [
        "decisions_made",
        "non_decisions",
        "action_items_summary",
        "risks_surfaced",
        "briefing_required",
        "key_issues_discussed",
        "participant_positions",
        "dependencies_surfaced",
        "commitments_made",
        "recommended_next_move",
        "materials_referenced",
        "tags",
    ]

    result = dict(row)
    for field in json_fields:
        val = result.get(field)
        if val and isinstance(val, str):
            try:
                result[field] = json.loads(val)
            except (json.JSONDecodeError, TypeError):
                pass

    return result
