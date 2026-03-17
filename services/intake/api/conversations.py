"""Conversation API endpoints."""

import logging

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from db.connection import get_connection

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/conversations", tags=["conversations"])


class TranscriptEdit(BaseModel):
    text: str


@router.get("")
def list_conversations(
    status: str | None = None,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    """List conversations with optional status filter."""
    conn = get_connection()
    try:
        query = "SELECT * FROM conversations"
        params = []
        if status:
            query += " WHERE processing_status = ?"
            params.append(status)
        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


@router.get("/queue-counts")
def get_queue_counts():
    """Return counts for each processing status."""
    conn = get_connection()
    try:
        counts = {}
        for row in conn.execute(
            "SELECT processing_status, COUNT(*) as cnt FROM conversations GROUP BY processing_status"
        ).fetchall():
            counts[row["processing_status"]] = row["cnt"]
        return counts
    finally:
        conn.close()


@router.get("/{conversation_id}")
def get_conversation(conversation_id: str):
    """Get full conversation detail — transcript + speaker mappings + audio."""
    conn = get_connection()
    try:
        conv = conn.execute(
            "SELECT * FROM conversations WHERE id = ?", (conversation_id,)
        ).fetchone()
        if not conv:
            raise HTTPException(status_code=404, detail="Conversation not found")

        # Transcript segments with confirmed speaker mappings
        segments = conn.execute(
            """SELECT t.*, sm.tracker_person_id, sm.confirmed as speaker_confirmed
               FROM transcripts t
               LEFT JOIN speaker_mappings sm
                   ON sm.conversation_id = t.conversation_id
                   AND sm.speaker_label = t.speaker_label
                   AND sm.confirmed = 1
               WHERE t.conversation_id = ?
               ORDER BY t.start_time""",
            (conversation_id,),
        ).fetchall()

        audio = conn.execute(
            "SELECT * FROM audio_files WHERE conversation_id = ?",
            (conversation_id,),
        ).fetchone()

        return {
            "conversation": dict(conv),
            "transcript": [dict(s) for s in segments],
            "audio": dict(audio) if audio else None,
        }
    finally:
        conn.close()


@router.get("/{conversation_id}/speaker-matches")
def get_speaker_matches(conversation_id: str):
    """Return speaker mappings for speaker review UI."""
    conn = get_connection()
    try:
        rows = conn.execute(
            """SELECT sm.*
               FROM speaker_mappings sm
               WHERE sm.conversation_id = ?
               ORDER BY sm.speaker_label""",
            (conversation_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


@router.patch("/transcripts/{transcript_id}")
def edit_transcript(transcript_id: str, body: TranscriptEdit):
    """Edit a transcript segment's text."""
    conn = get_connection()
    try:
        seg = conn.execute(
            "SELECT * FROM transcripts WHERE id = ?", (transcript_id,)
        ).fetchone()
        if not seg:
            raise HTTPException(status_code=404, detail="Transcript segment not found")

        if not dict(seg).get("original_text"):
            conn.execute(
                "UPDATE transcripts SET original_text = text WHERE id = ?",
                (transcript_id,),
            )

        conn.execute(
            "UPDATE transcripts SET text = ?, user_corrected = 1 WHERE id = ?",
            (body.text, transcript_id),
        )
        conn.commit()
        return {"status": "ok", "transcript_id": transcript_id}
    finally:
        conn.close()


@router.post("/{conversation_id}/confirm-speakers")
def confirm_speakers(conversation_id: str):
    """Confirm speaker assignments. Marks conversation as completed."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT processing_status FROM conversations WHERE id = ?",
            (conversation_id,),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Conversation not found")

        conn.execute(
            """UPDATE conversations
               SET speakers_confirmed = 1,
                   processing_status = 'completed',
                   updated_at = datetime('now')
               WHERE id = ?""",
            (conversation_id,),
        )
        conn.commit()
        logger.info(f"Speakers confirmed for {conversation_id[:8]}")
        return {"status": "ok", "conversation_id": conversation_id}
    finally:
        conn.close()


@router.patch("/{conversation_id}/discard")
def discard_conversation(conversation_id: str):
    """Discard a conversation."""
    conn = get_connection()
    try:
        conn.execute(
            """UPDATE conversations
               SET processing_status = 'discarded',
                   updated_at = datetime('now')
               WHERE id = ?""",
            (conversation_id,),
        )
        conn.commit()
        return {"status": "ok", "conversation_id": conversation_id, "discarded": True}
    finally:
        conn.close()
