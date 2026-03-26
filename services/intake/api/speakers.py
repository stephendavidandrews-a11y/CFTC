"""Speaker review + assignment API endpoints.

Speaker identity (name, role, org) is owned by the Tracker service.
This API handles assignment of tracker_person_ids to speaker labels,
voiceprint promotion, and segment reassignment.
"""

import logging
import uuid

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from db.connection import get_connection
from voice.speakers.resolver import (
    promote_voice_sample,
    get_suggestions_for_conversation,
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["speakers"])


# ── Request Models ──


class AssignSpeakerRequest(BaseModel):
    conversation_id: str
    speaker_label: str
    tracker_person_id: str


class MergeSpeakersRequest(BaseModel):
    conversation_id: str
    from_label: str
    to_label: str


class ReassignSegmentRequest(BaseModel):
    transcript_segment_id: str
    new_speaker_label: str


# ── Speaker Assignment ──


@router.post("/correct-speaker")
def assign_speaker(req: AssignSpeakerRequest):
    """Assign a Tracker person to a speaker label in a conversation.

    Updates transcripts, creates/updates speaker_mapping, promotes voiceprint.
    """
    conn = get_connection()
    try:
        # Update transcript segments
        conn.execute(
            "UPDATE transcripts SET speaker_id = ? WHERE conversation_id = ? AND speaker_label = ?",
            (req.tracker_person_id, req.conversation_id, req.speaker_label),
        )

        # Upsert speaker mapping
        existing_mapping = conn.execute(
            """SELECT id FROM speaker_mappings
               WHERE conversation_id = ? AND speaker_label = ?""",
            (req.conversation_id, req.speaker_label),
        ).fetchone()

        if existing_mapping:
            conn.execute(
                """UPDATE speaker_mappings
                   SET tracker_person_id = ?, confidence = 1.0, method = 'manual',
                       confirmed = 1, updated_at = datetime('now')
                   WHERE id = ?""",
                (req.tracker_person_id, existing_mapping["id"]),
            )
        else:
            conn.execute(
                """INSERT INTO speaker_mappings
                   (id, conversation_id, speaker_label, tracker_person_id,
                    confidence, method, confirmed)
                   VALUES (?, ?, ?, ?, 1.0, 'manual', 1)""",
                (
                    str(uuid.uuid4()),
                    req.conversation_id,
                    req.speaker_label,
                    req.tracker_person_id,
                ),
            )

        # Promote voice sample to speaker profile
        promote_voice_sample(
            conn, req.conversation_id, req.speaker_label, req.tracker_person_id
        )

        conn.commit()
        logger.info(
            f"Assigned {req.speaker_label} -> person {req.tracker_person_id[:8]} in {req.conversation_id[:8]}"
        )
        return {"status": "ok", "tracker_person_id": req.tracker_person_id}
    finally:
        conn.close()


@router.post("/merge-speakers")
def merge_speakers(req: MergeSpeakersRequest):
    """Merge two speaker labels in a conversation."""
    conn = get_connection()
    try:
        count = conn.execute(
            "SELECT COUNT(*) as cnt FROM transcripts WHERE conversation_id = ? AND speaker_label = ?",
            (req.conversation_id, req.from_label),
        ).fetchone()["cnt"]
        if count == 0:
            raise HTTPException(
                404, f"No segments with speaker_label '{req.from_label}'"
            )

        conn.execute(
            "UPDATE transcripts SET speaker_label = ? WHERE conversation_id = ? AND speaker_label = ?",
            (req.to_label, req.conversation_id, req.from_label),
        )

        # Update any speaker mappings
        conn.execute(
            "UPDATE speaker_mappings SET speaker_label = ? WHERE conversation_id = ? AND speaker_label = ?",
            (req.to_label, req.conversation_id, req.from_label),
        )

        conn.commit()
        logger.info(
            f"Merged {req.from_label} -> {req.to_label} in {req.conversation_id[:8]} ({count} segments)"
        )
        return {"status": "ok", "segments_updated": count}
    finally:
        conn.close()


@router.post("/reassign-segment")
def reassign_segment(req: ReassignSegmentRequest):
    """Reassign a single transcript segment to a different speaker label."""
    conn = get_connection()
    try:
        seg = conn.execute(
            "SELECT id FROM transcripts WHERE id = ?",
            (req.transcript_segment_id,),
        ).fetchone()
        if not seg:
            raise HTTPException(404, "Transcript segment not found")

        conn.execute(
            "UPDATE transcripts SET speaker_label = ?, speaker_id = NULL WHERE id = ?",
            (req.new_speaker_label, req.transcript_segment_id),
        )
        conn.commit()
        return {"status": "ok"}
    finally:
        conn.close()


@router.get("/speaker-suggestions/{conversation_id}")
def get_speaker_suggestions(conversation_id: str):
    """Get voiceprint-based speaker suggestions for a conversation.

    Returns { speaker_label: [{ tracker_person_id, confidence, method }] }
    Person names must be resolved by the frontend via the Tracker API.
    """
    return get_suggestions_for_conversation(conversation_id)
