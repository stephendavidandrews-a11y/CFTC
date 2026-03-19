"""Participant review API — human gate for confirming email participant identities.

After email parsing + attachment processing, email communications enter
awaiting_participant_review (unless all participants are auto-confirmed).
This router provides endpoints to:
1. List communications needing participant review
2. Get participant details for a communication
3. Confirm/assign participants to tracker person IDs
4. Complete participant review (advances pipeline)

Pattern: mirrors speaker_review.py exactly.
"""
import json
import logging
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel

from app.db import get_db
from app.pipeline.orchestrator import cas_transition
from app.routers.events import publish_event

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/participant-review", tags=["participant-review"])

PARTICIPANT_REVIEW_STATES = {"awaiting_participant_review", "participant_review_in_progress"}


# -- Request/Response models --

class ConfirmParticipantRequest(BaseModel):
    participant_id: str
    tracker_person_id: str
    proposed_name: Optional[str] = None
    proposed_title: Optional[str] = None
    proposed_org: Optional[str] = None


class ParticipantInfo(BaseModel):
    id: str
    participant_email: Optional[str] = None
    proposed_name: Optional[str] = None
    proposed_title: Optional[str] = None
    proposed_org: Optional[str] = None
    header_role: Optional[str] = None
    participant_role: Optional[str] = None
    tracker_person_id: Optional[str] = None
    match_source: Optional[str] = None
    confirmed: bool = False


class ParticipantReviewDetail(BaseModel):
    communication_id: str
    processing_status: str
    original_filename: Optional[str] = None
    title: Optional[str] = None
    participants: list[ParticipantInfo]
    message_count: int = 0


# -- Endpoints --

@router.get("/queue")
async def get_participant_review_queue(db=Depends(get_db)):
    """List all email communications awaiting participant review."""
    rows = db.execute("""
        SELECT c.id, c.original_filename, c.title, c.processing_status,
               c.created_at, c.updated_at,
               (SELECT COUNT(*) FROM communication_participants cp
                WHERE cp.communication_id = c.id) as participant_count,
               (SELECT COUNT(*) FROM communication_participants cp
                WHERE cp.communication_id = c.id AND cp.confirmed = 1) as confirmed_count,
               (SELECT COUNT(*) FROM communication_messages cm
                WHERE cm.communication_id = c.id) as message_count
        FROM communications c
        WHERE c.processing_status IN ('awaiting_participant_review', 'participant_review_in_progress')
            AND c.source_type = 'email'
        ORDER BY c.created_at DESC
    """).fetchall()

    return {
        "items": [dict(r) for r in rows],
        "total": len(rows),
    }


@router.get("/{communication_id}")
async def get_participant_review_detail(communication_id: str, db=Depends(get_db)):
    """Get detailed participant information for review."""
    comm = db.execute(
        """SELECT id, processing_status, original_filename, title
           FROM communications WHERE id = ?""",
        (communication_id,),
    ).fetchone()
    if not comm:
        raise HTTPException(404, detail={"error_type": "not_found"})

    participants = db.execute("""
        SELECT id, participant_email, proposed_name, proposed_title,
               proposed_org, header_role, participant_role,
               tracker_person_id, match_source, confirmed
        FROM communication_participants
        WHERE communication_id = ?
        ORDER BY CASE header_role WHEN 'from' THEN 0 WHEN 'to' THEN 1 WHEN 'cc' THEN 2 ELSE 3 END
    """, (communication_id,)).fetchall()

    message_count = db.execute(
        "SELECT COUNT(*) as cnt FROM communication_messages WHERE communication_id = ?",
        (communication_id,),
    ).fetchone()["cnt"]

    return ParticipantReviewDetail(
        communication_id=communication_id,
        processing_status=comm["processing_status"],
        original_filename=comm["original_filename"],
        title=comm["title"],
        participants=[ParticipantInfo(**dict(p), confirmed=bool(p["confirmed"])) for p in participants],
        message_count=message_count,
    )


@router.post("/{communication_id}/confirm")
async def confirm_participant(
    communication_id: str,
    req: ConfirmParticipantRequest,
    db=Depends(get_db),
):
    """Confirm/assign a tracker person ID to an email participant."""
    _check_review_state(db, communication_id)
    _ensure_in_progress(db, communication_id)

    updated = db.execute("""
        UPDATE communication_participants
        SET tracker_person_id = ?,
            proposed_name = COALESCE(?, proposed_name),
            proposed_title = COALESCE(?, proposed_title),
            proposed_org = COALESCE(?, proposed_org),
            confirmed = 1, match_source = 'manual',
            updated_at = datetime('now')
        WHERE id = ? AND communication_id = ?
    """, (
        req.tracker_person_id, req.proposed_name, req.proposed_title,
        req.proposed_org, req.participant_id, communication_id,
    )).rowcount

    if updated == 0:
        raise HTTPException(404, detail={
            "error_type": "not_found",
            "message": f"Participant {req.participant_id} not found",
        })

    db.execute("""
        INSERT INTO review_action_log (id, actor, communication_id, action_type, details)
        VALUES (?, 'user', ?, 'confirm_participant', ?)
    """, (
        str(uuid.uuid4()), communication_id,
        json.dumps({"participant_id": req.participant_id, "tracker_person_id": req.tracker_person_id}),
    ))
    db.commit()

    return {"status": "ok", "participant_id": req.participant_id, "confirmed": True}


@router.post("/{communication_id}/complete")
async def complete_participant_review(
    communication_id: str,
    background_tasks: BackgroundTasks,
    db=Depends(get_db),
):
    """Complete participant review and advance the pipeline.

    All participants must be confirmed before completing.
    Transitions: participant_review_in_progress -> participants_confirmed
    """
    comm = db.execute(
        "SELECT processing_status FROM communications WHERE id = ?",
        (communication_id,),
    ).fetchone()
    if not comm:
        raise HTTPException(404, detail={"error_type": "not_found"})

    status = comm["processing_status"]
    if status not in PARTICIPANT_REVIEW_STATES:
        raise HTTPException(400, detail={
            "error_type": "invalid_state",
            "message": f"Communication not in participant review (current: {status})",
        })

    # Check all confirmed
    unconfirmed = db.execute("""
        SELECT id, participant_email FROM communication_participants
        WHERE communication_id = ? AND confirmed = 0
    """, (communication_id,)).fetchall()

    if unconfirmed:
        emails = [r["participant_email"] for r in unconfirmed]
        raise HTTPException(400, detail={
            "error_type": "validation_failure",
            "message": f"Unconfirmed participants remain: {emails}",
            "unconfirmed_participants": emails,
        })

    # Advance state
    if status == "awaiting_participant_review":
        cas_transition(db, communication_id, "awaiting_participant_review", "participant_review_in_progress")

    if not cas_transition(db, communication_id, "participant_review_in_progress", "participants_confirmed"):
        raise HTTPException(409, detail={"error_type": "conflict"})

    db.execute("""
        INSERT INTO review_action_log (id, actor, communication_id, action_type, old_state, new_state)
        VALUES (?, 'user', ?, 'complete_participant_review', 'participant_review_in_progress', 'participants_confirmed')
    """, (str(uuid.uuid4()), communication_id))
    db.commit()

    await publish_event("participant_review_complete", {
        "communication_id": communication_id,
        "status": "participants_confirmed",
    })

    background_tasks.add_task(_resume_pipeline, communication_id)

    return {"status": "participants_confirmed", "communication_id": communication_id}


@router.get("/{communication_id}/messages")
async def get_messages(communication_id: str, db=Depends(get_db)):
    """Get all email messages in the thread for review context."""
    rows = db.execute("""
        SELECT id, message_index, sender_email, sender_name,
               recipient_emails, cc_emails, timestamp, subject,
               body_text, is_new, is_from_user
        FROM communication_messages
        WHERE communication_id = ?
        ORDER BY message_index
    """, (communication_id,)).fetchall()

    return {"communication_id": communication_id, "messages": [dict(r) for r in rows], "total": len(rows)}


@router.get("/{communication_id}/artifacts")
async def get_artifacts(communication_id: str, db=Depends(get_db)):
    """Get all attachments for the communication."""
    rows = db.execute("""
        SELECT id, original_filename, mime_type, file_size_bytes,
               artifact_type, text_extraction_status, is_document_proposable,
               quarantine_reason
        FROM communication_artifacts
        WHERE communication_id = ?
        ORDER BY created_at
    """, (communication_id,)).fetchall()

    return {"communication_id": communication_id, "artifacts": [dict(r) for r in rows], "total": len(rows)}


# -- Helpers --

def _check_review_state(db, communication_id: str):
    row = db.execute(
        "SELECT processing_status FROM communications WHERE id = ?",
        (communication_id,),
    ).fetchone()
    if not row:
        raise HTTPException(404, detail={"error_type": "not_found"})
    if row["processing_status"] not in PARTICIPANT_REVIEW_STATES:
        raise HTTPException(400, detail={
            "error_type": "invalid_state",
            "message": f"Communication not in participant review (current: {row['processing_status']})",
        })


def _ensure_in_progress(db, communication_id: str):
    cas_transition(db, communication_id, "awaiting_participant_review", "participant_review_in_progress")


async def _resume_pipeline(communication_id: str):
    from app.pipeline.orchestrator import process_communication
    try:
        await process_communication(communication_id)
    except Exception as e:
        logger.exception("Pipeline resume failed for %s: %s", communication_id, e)
