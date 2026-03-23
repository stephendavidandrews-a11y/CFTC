"""Pipeline API — upload, manual processing, and status."""

import logging
import os
import threading
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, HTTPException, UploadFile, File, Form

from config import INBOX_PI, INBOX_PLAUD, INBOX_PHONE, SUPPORTED_FORMATS
from db.connection import get_connection
from voice.pipeline.processor import process_conversation, process_pending

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/pipeline", tags=["pipeline"])

INBOX_SOURCES = {
    "pi": INBOX_PI,
    "plaud": INBOX_PLAUD,
    "phone": INBOX_PHONE,
}


@router.post("/upload")
async def upload_recording(
    file: UploadFile = File(...),
    source: str = Form("phone"),
    note: str = Form(None),
):
    """Upload an audio recording and trigger processing."""
    if source not in INBOX_SOURCES:
        raise HTTPException(400, f"Invalid source. Use: {sorted(INBOX_SOURCES.keys())}")

    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in SUPPORTED_FORMATS:
        raise HTTPException(400, f"Unsupported format '{ext}'")

    max_size = 200 * 1024 * 1024
    contents = await file.read()
    if len(contents) > max_size:
        raise HTTPException(413, f"File too large ({len(contents) / 1024 / 1024:.1f}MB). Max: 200MB")

    inbox_dir = INBOX_SOURCES[source]
    inbox_dir.mkdir(parents=True, exist_ok=True)

    safe_name = file.filename.replace("/", "_").replace("\\", "_")
    dest = inbox_dir / safe_name
    if dest.exists():
        stem, suffix = dest.stem, dest.suffix
        counter = 1
        while dest.exists():
            dest = inbox_dir / f"{stem}_{counter}{suffix}"
            counter += 1

    dest.write_bytes(contents)
    logger.info("Uploaded %s (%d bytes) to %s", safe_name, len(contents), dest)

    conversation_id = str(uuid.uuid4())
    audio_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    conn = get_connection()
    try:
        conn.execute(
            """INSERT INTO conversations (id, source, file_path, processing_status, title, created_at)
               VALUES (?, ?, ?, 'pending', ?, ?)""",
            (conversation_id, source, str(dest), note, now),
        )
        conn.execute(
            """INSERT INTO audio_files (id, conversation_id, file_path, original_filename,
               source, format, file_size_bytes, captured_at, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (audio_id, conversation_id, str(dest), safe_name,
             source, ext.lstrip("."), len(contents), now, now),
        )
        conn.commit()
    except Exception as e:
        conn.rollback()
        if dest.exists():
            dest.unlink()
        raise HTTPException(500, f"Failed to register upload: {e}")
    finally:
        conn.close()

    t = threading.Thread(target=process_conversation, args=(conversation_id,), daemon=True)
    t.start()

    return {
        "status": "uploaded",
        "conversation_id": conversation_id,
        "filename": safe_name,
        "processing": "started",
    }


@router.post("/process-pending")
async def process_all_pending(background_tasks: BackgroundTasks):
    """Process all pending conversations in background."""
    conn = get_connection()
    try:
        count = conn.execute(
            "SELECT count(*) as n FROM conversations WHERE processing_status = 'pending'"
        ).fetchone()["n"]
    finally:
        conn.close()

    if count == 0:
        return {"status": "no_pending_conversations"}

    background_tasks.add_task(process_pending)
    return {"status": "processing_started", "pending_count": count}


@router.post("/process/{conversation_id}")
async def process_single(conversation_id: str, background_tasks: BackgroundTasks):
    """Trigger processing for a specific conversation."""
    background_tasks.add_task(process_conversation, conversation_id)
    return {"status": "processing_started", "conversation_id": conversation_id}


@router.get("/status")
async def pipeline_status():
    """Get pipeline processing status summary."""
    conn = get_connection()
    try:
        status_counts = {}
        for row in conn.execute(
            "SELECT processing_status, count(*) as n FROM conversations GROUP BY processing_status"
        ).fetchall():
            status_counts[row["processing_status"]] = row["n"]

        total_profiles = conn.execute("SELECT count(DISTINCT tracker_person_id) as n FROM speaker_voice_profiles").fetchone()["n"]

        return {
            "conversations": status_counts,
            "voice_profiles": total_profiles,
        }
    finally:
        conn.close()
