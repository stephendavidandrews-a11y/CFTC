"""Shared helpers for review-stage routers.

Used by speaker_review.py, entity_review.py, and participant_review.py.
Each review stage has the same check-state / ensure-in-progress / resume
pattern, parameterized by the stage's valid states and transition names.
"""

import logging

from fastapi import HTTPException

from app.pipeline.orchestrator import cas_transition

logger = logging.getLogger(__name__)


def check_review_state(db, communication_id: str, valid_states: set, stage_name: str):
    """Verify communication is in a valid review state.

    Raises HTTPException 404 if not found, 400 if wrong state.
    """
    row = db.execute(
        "SELECT processing_status FROM communications WHERE id = ?",
        (communication_id,),
    ).fetchone()
    if not row:
        raise HTTPException(404, detail={"error_type": "not_found"})
    if row["processing_status"] not in valid_states:
        raise HTTPException(
            400,
            detail={
                "error_type": "invalid_state",
                "message": f"Communication not in {stage_name} (current: {row['processing_status']})",
            },
        )


def ensure_in_progress(db, communication_id: str, from_state: str, to_state: str):
    """Auto-transition from awaiting to in_progress on first interaction."""
    cas_transition(db, communication_id, from_state, to_state)


async def resume_pipeline(communication_id: str):
    """Resume pipeline processing after human gate completion."""
    from app.pipeline.orchestrator import process_communication

    try:
        await process_communication(communication_id)
    except Exception as e:
        logger.exception("Pipeline resume failed for %s: %s", communication_id, e)
