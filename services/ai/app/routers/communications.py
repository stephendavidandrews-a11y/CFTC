"""Communications API — audio upload, list, detail, status.

Provides the core ingestion path for audio into the AI pipeline.
Both file watcher and direct upload converge on the same create_communication() logic.
"""
import json
import logging
import shutil
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.config import AI_UPLOAD_DIR
from app.db import get_db
from app.pipeline.stages.preprocessing import ACCEPTED_FORMATS, get_audio_metadata
from app.routers.events import publish_event

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/communications", tags=["communications"])

# Max upload size: 200 MB (enforced by nginx, but also checked here)
MAX_UPLOAD_BYTES = 200 * 1024 * 1024


# ── Helpers ──

def _parse_flags(d: dict) -> dict:
    """Deserialize JSON string fields before Pydantic model construction."""
    sf = d.get("sensitivity_flags")
    if isinstance(sf, str):
        try:
            d["sensitivity_flags"] = json.loads(sf)
        except (json.JSONDecodeError, TypeError):
            d["sensitivity_flags"] = None
    sm = d.get("source_metadata")
    if isinstance(sm, str):
        try:
            d["source_metadata"] = json.loads(sm)
        except (json.JSONDecodeError, TypeError):
            d["source_metadata"] = None
    return d


# ── Response models ──

class CommunicationSummary(BaseModel):
    id: str
    source_type: str
    original_filename: Optional[str] = None
    title: Optional[str] = None
    processing_status: str
    duration_seconds: Optional[float] = None
    sensitivity_flags: Optional[list] = None
    error_message: Optional[str] = None
    error_stage: Optional[str] = None
    archived_at: Optional[str] = None
    created_at: str
    updated_at: str


class CommunicationDetail(BaseModel):
    id: str
    source_type: str
    source_path: Optional[str] = None
    original_filename: Optional[str] = None
    title: Optional[str] = None
    processing_status: str
    duration_seconds: Optional[float] = None
    sensitivity_flags: Optional[str] = None
    error_message: Optional[str] = None
    error_stage: Optional[str] = None
    source_metadata: Optional[dict] = None
    created_at: str
    updated_at: str
    audio_files: list[dict] = []
    participants: list[dict] = []
    transcript_count: int = 0
    messages: list[dict] = []
    artifacts: list[dict] = []


class CommunicationListResponse(BaseModel):
    items: list[CommunicationSummary]
    total: int
    offset: int
    limit: int


# ── Ingestion helpers ──

def create_communication(
    db,
    original_path: Path,
    source_type: str = "audio_upload",
    title: str | None = None,
    sensitivity_flags: str | None = None,
    source_metadata: dict | None = None,
) -> str:
    """Create a communication + audio_files record for an ingested audio file.

    This is the single convergence point for both upload and watcher paths.
    Returns the new communication ID.
    """
    comm_id = str(uuid.uuid4())
    audio_id = str(uuid.uuid4())

    # Get file metadata
    file_size = original_path.stat().st_size if original_path.exists() else None
    original_filename = original_path.name

    # Persist original to uploads/<comm_id>/original/<filename>
    storage_dir = AI_UPLOAD_DIR / comm_id / "original"
    storage_dir.mkdir(parents=True, exist_ok=True)
    stored_path = storage_dir / original_filename

    if original_path != stored_path:
        shutil.copy2(str(original_path), str(stored_path))

    # Get audio metadata (duration, codec, etc.) before we know the full probe
    meta = get_audio_metadata(original_path)
    duration = meta.get("duration_seconds")

    db.execute("""
        INSERT INTO communications
            (id, source_type, source_path, original_filename, title,
             processing_status, duration_seconds, sensitivity_flags,
             source_metadata, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, 'pending', ?, ?, ?, datetime('now'), datetime('now'))
    """, (
        comm_id, source_type, str(stored_path), original_filename,
        title, duration, sensitivity_flags,
        json.dumps(source_metadata) if source_metadata else json.dumps(meta),
    ))

    db.execute("""
        INSERT INTO audio_files
            (id, communication_id, file_path, original_filename,
             format, duration_seconds, file_size_bytes, captured_at, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
    """, (
        audio_id, comm_id, str(stored_path), original_filename,
        original_path.suffix.lstrip(".").lower(), duration, file_size,
    ))

    db.commit()

    logger.info(
        "Created communication %s from %s (%.1f MB, %s)",
        comm_id[:8], original_filename,
        (file_size or 0) / 1024 / 1024,
        source_type,
    )
    return comm_id


# ── API endpoints ──

@router.post("/audio-upload")
async def upload_audio(
    background_tasks: BackgroundTasks,
    db=Depends(get_db),
    audio: UploadFile = File(...),
    title: Optional[str] = Form(None),
    source_type: str = Form("audio_upload"),
    sensitivity_flags: Optional[str] = Form(None),
):
    """Upload an audio file to create a new communication.

    The file is saved, a communication record is created,
    and the pipeline is kicked off in the background.

    Accepted formats: wav, flac, mp3, m4a, mp4, aac, ogg, opus, wma, webm
    """
    # Validate format
    filename = audio.filename or "unknown"
    suffix = Path(filename).suffix.lower()
    if suffix not in ACCEPTED_FORMATS:
        raise HTTPException(
            status_code=400,
            detail={
                "error_type": "validation_failure",
                "message": f"Unsupported audio format: {suffix}",
                "accepted_formats": sorted(ACCEPTED_FORMATS),
            },
        )

    # Read and validate size
    content = await audio.read()
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail={
                "error_type": "validation_failure",
                "message": f"File too large: {len(content)} bytes (max {MAX_UPLOAD_BYTES})",
            },
        )
    if len(content) == 0:
        raise HTTPException(
            status_code=400,
            detail={
                "error_type": "validation_failure",
                "message": "Empty file",
            },
        )

    # Save to temp location, then create communication
    temp_dir = AI_UPLOAD_DIR / "_incoming"
    temp_dir.mkdir(parents=True, exist_ok=True)
    temp_path = temp_dir / f"{uuid.uuid4()}{suffix}"

    try:
        with open(temp_path, "wb") as f:
            f.write(content)

        comm_id = create_communication(
            db=db,
            original_path=temp_path,
            source_type=source_type,
            title=title,
            sensitivity_flags=sensitivity_flags,
            source_metadata={"upload_filename": filename, "upload_size": len(content)},
        )
    finally:
        # Clean up temp file (original is now copied to uploads/<comm_id>/original/)
        if temp_path.exists():
            temp_path.unlink()

    # Kick off pipeline processing in background
    background_tasks.add_task(_start_pipeline, comm_id)

    await publish_event("communication_created", {
        "communication_id": comm_id,
        "source_type": source_type,
        "filename": filename,
    })

    return {
        "communication_id": comm_id,
        "status": "pending",
        "message": "Audio uploaded. Pipeline processing started.",
    }


ACCEPTED_EMAIL_FORMATS = {".eml", ".msg"}


@router.post("/email-upload")
async def upload_email(
    background_tasks: BackgroundTasks,
    db=Depends(get_db),
    email_file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    sensitivity_flags: Optional[str] = Form(None),
):
    """Upload an email file (.eml or .msg) to create a new communication.

    The file is saved, a communication record is created,
    and the email pipeline is kicked off in the background.
    """
    filename = email_file.filename or "unknown.eml"
    suffix = Path(filename).suffix.lower()
    if suffix not in ACCEPTED_EMAIL_FORMATS:
        raise HTTPException(
            status_code=400,
            detail={
                "error_type": "validation_failure",
                "message": f"Unsupported email format: {suffix}",
                "accepted_formats": sorted(ACCEPTED_EMAIL_FORMATS),
            },
        )

    content = await email_file.read()
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail={
                "error_type": "validation_failure",
                "message": f"File too large: {len(content)} bytes (max {MAX_UPLOAD_BYTES})",
            },
        )
    if len(content) == 0:
        raise HTTPException(
            status_code=400,
            detail={"error_type": "validation_failure", "message": "Empty file"},
        )

    # Save to storage
    comm_id = str(uuid.uuid4())
    storage_dir = AI_UPLOAD_DIR / comm_id / "original"
    storage_dir.mkdir(parents=True, exist_ok=True)
    stored_path = storage_dir / filename
    stored_path.write_bytes(content)

    # Quick subject extraction for title
    if not title and suffix == ".eml":
        try:
            import email as email_mod
            msg = email_mod.message_from_bytes(content, policy=email_mod.policy.default)
            title = str(msg.get("Subject", "")) or None
        except Exception:
            pass

    db.execute("""
        INSERT INTO communications
            (id, source_type, source_path, original_filename, title,
             processing_status, sensitivity_flags,
             source_metadata, created_at, updated_at)
        VALUES (?, 'email', ?, ?, ?, 'pending', ?, ?, datetime('now'), datetime('now'))
    """, (
        comm_id, str(stored_path), filename,
        title, sensitivity_flags,
        json.dumps({"upload_filename": filename, "upload_size": len(content)}),
    ))
    db.commit()

    logger.info("Created email communication %s from %s (%.1f KB)",
               comm_id[:8], filename, len(content) / 1024)

    background_tasks.add_task(_start_pipeline, comm_id)

    await publish_event("communication_created", {
        "communication_id": comm_id,
        "source_type": "email",
        "filename": filename,
    })

    return {
        "communication_id": comm_id,
        "status": "pending",
        "message": "Email uploaded. Pipeline processing started.",
    }


@router.get("", response_model=CommunicationListResponse)
async def list_communications(
    db=Depends(get_db),
    offset: int = 0,
    limit: int = 50,
    status: Optional[str] = None,
    source_type: Optional[str] = None,
    include_archived: bool = False,
):
    """List communications with optional filtering."""
    where_clauses = []
    params = []
    if not include_archived:
        where_clauses.append("archived_at IS NULL")
    if status:
        where_clauses.append("processing_status = ?")
        params.append(status)
    if source_type:
        where_clauses.append("source_type = ?")
        params.append(source_type)

    where_sql = ""
    if where_clauses:
        where_sql = "WHERE " + " AND ".join(where_clauses)

    # Total count
    total = db.execute(
        f"SELECT COUNT(*) as cnt FROM communications {where_sql}",
        params,
    ).fetchone()["cnt"]

    # Paginated results
    rows = db.execute(
        f"""SELECT id, source_type, original_filename, title,
                processing_status, duration_seconds, sensitivity_flags,
                error_message, error_stage, archived_at, created_at, updated_at
            FROM communications {where_sql}
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?""",
        params + [limit, offset],
    ).fetchall()

    return CommunicationListResponse(
        items=[CommunicationSummary(**_parse_flags(dict(r))) for r in rows],
        total=total,
        offset=offset,
        limit=limit,
    )


@router.get("/{communication_id}", response_model=CommunicationDetail)
async def get_communication(communication_id: str, db=Depends(get_db)):
    """Get detailed communication info including audio files and participants."""
    row = db.execute(
        """SELECT id, source_type, source_path, original_filename, title,
                processing_status, duration_seconds, sensitivity_flags,
                error_message, error_stage, source_metadata, created_at, updated_at
            FROM communications WHERE id = ?""",
        (communication_id,),
    ).fetchone()

    if not row:
        raise HTTPException(404, detail={"error_type": "not_found", "message": "Communication not found"})

    data = _parse_flags(dict(row))

    # Get audio files
    audio_rows = db.execute(
        """SELECT id, file_path, original_filename, format,
                duration_seconds, file_size_bytes, captured_at, created_at
            FROM audio_files WHERE communication_id = ?""",
        (communication_id,),
    ).fetchall()
    data["audio_files"] = [dict(r) for r in audio_rows]

    # Get participants
    part_rows = db.execute(
        """SELECT id, speaker_label, tracker_person_id, proposed_name,
                proposed_title, proposed_org, participant_role,
                confirmed, voiceprint_confidence, voiceprint_method,
                created_at, updated_at
            FROM communication_participants WHERE communication_id = ?
            ORDER BY speaker_label""",
        (communication_id,),
    ).fetchall()
    data["participants"] = [dict(r) for r in part_rows]

    # Transcript count
    data["transcript_count"] = db.execute(
        "SELECT COUNT(*) as cnt FROM transcripts WHERE communication_id = ?",
        (communication_id,),
    ).fetchone()["cnt"]

    # Get messages (email)
    msg_rows = db.execute(
        """SELECT id, message_index, sender_email, sender_name, subject,
                is_new, is_from_user, timestamp
            FROM communication_messages WHERE communication_id = ?
            ORDER BY message_index""",
        (communication_id,),
    ).fetchall()
    data["messages"] = [dict(r) for r in msg_rows]

    # Get artifacts (email attachments)
    art_rows = db.execute(
        """SELECT id, original_filename, mime_type, file_size_bytes,
                text_extraction_status, is_document_proposable, quarantine_reason
            FROM communication_artifacts WHERE communication_id = ?""",
        (communication_id,),
    ).fetchall()
    data["artifacts"] = [dict(r) for r in art_rows]

    return CommunicationDetail(**data)


@router.post("/{communication_id}/retry")
async def retry_communication(
    communication_id: str,
    background_tasks: BackgroundTasks,
    db=Depends(get_db),
):
    """Retry a failed or budget-paused communication from its error stage.

    Accepts communications in 'error' or 'paused_budget' state.
    For paused_budget: resumes from the stage that was blocked by the budget.
    For error: resumes from the stage that failed.
    """
    row = db.execute(
        "SELECT processing_status, error_stage FROM communications WHERE id = ?",
        (communication_id,),
    ).fetchone()
    if not row:
        raise HTTPException(404, detail={"error_type": "not_found"})

    retryable_states = {"error", "paused_budget"}
    if row["processing_status"] not in retryable_states:
        raise HTTPException(
            400,
            detail={
                "error_type": "invalid_state",
                "message": f"Can only retry from error or paused_budget state, current: {row['processing_status']}",
            },
        )

    # Reset to the stage that failed/paused
    retry_from = row["error_stage"] or "pending"
    previous_state = row["processing_status"]
    db.execute("""
        UPDATE communications
        SET processing_status = ?, error_message = NULL, error_stage = NULL,
            updated_at = datetime('now')
        WHERE id = ?
    """, (retry_from, communication_id))
    db.commit()

    background_tasks.add_task(_start_pipeline, communication_id)

    await publish_event("communication_retry", {
        "communication_id": communication_id,
        "retry_from": retry_from,
        "previous_state": previous_state,
    })

    return {"status": "retrying", "from_stage": retry_from, "previous_state": previous_state}


@router.post("/{communication_id}/undo")
async def undo_communication_endpoint(
    communication_id: str,
    db=Depends(get_db),
    force: bool = False,
):
    """Reverse all tracker writebacks for a committed communication.

    Phase 6.3 — Undo API (02_PIPELINE_ARCHITECTURE.md §4D, §5I).

    Reverses insert writebacks (deletes tracker records) and update writebacks
    (restores previous_data). Detects conflicts where tracker records have been
    modified since commit.

    Query params:
        force: If true, override conflicts and undo anyway (default: false)

    Returns:
        UndoResult with per-writeback outcomes, conflict details, and status.
    """
    from app.writeback.undo import undo_communication, UndoError, UndoErrorType

    try:
        result = await undo_communication(db, communication_id, force=force)
    except UndoError as e:
        status_map = {
            UndoErrorType.INVALID_COMMUNICATION: 404,
            UndoErrorType.NOT_UNDOABLE_STATE: 400,
            UndoErrorType.NO_WRITEBACKS: 400,
            UndoErrorType.ALREADY_REVERSED: 400,
            UndoErrorType.CONFLICT_DETECTED: 409,
            UndoErrorType.FORCE_NOT_ALLOWED: 403,
            UndoErrorType.TRACKER_ERROR: 502,
            UndoErrorType.PARTIAL_FAILURE: 500,
        }
        raise HTTPException(
            status_code=status_map.get(e.error_type, 500),
            detail={
                "error_type": e.error_type.value,
                "message": e.message,
                **e.details,
            },
        )

    # If conflict detected (not raised as exception), return 409 with details
    if not result.success and result.error_type == UndoErrorType.CONFLICT_DETECTED:
        raise HTTPException(
            status_code=409,
            detail={
                "error_type": "conflict_detected",
                "message": result.error,
                "conflict_count": result.conflict_count,
                "conflicts": [
                    {
                        "writeback_id": c.writeback_id,
                        "target_table": c.target_table,
                        "target_record_id": c.target_record_id,
                        "write_type": c.write_type,
                        "field_name": c.field_name,
                        "written_value": str(c.written_value)[:200],
                        "current_value": str(c.current_value)[:200],
                    }
                    for c in result.conflicts
                ],
            },
        )

    # Partial failure
    if not result.success:
        raise HTTPException(
            status_code=500,
            detail={
                "error_type": result.error_type.value if result.error_type else "partial_failure",
                "message": result.error,
                "reversed_count": result.reversed_count,
                "total_writebacks": result.total_writebacks,
            },
        )

    # Success
    await publish_event("communication_undo", {
        "communication_id": communication_id,
        "reversed_count": result.reversed_count,
        "skipped_count": result.skipped_count,
        "forced": result.forced,
    })

    return {
        "status": "undone",
        "communication_id": communication_id,
        "reversed_count": result.reversed_count,
        "skipped_count": result.skipped_count,
        "total_writebacks": result.total_writebacks,
        "forced": result.forced,
        "new_status": "bundle_review_in_progress",
    }


@router.post("/{communication_id}/archive")
async def archive_communication(communication_id: str, db=Depends(get_db)):
    """Archive a communication (soft-delete). Hides from default list view."""
    row = db.execute(
        "SELECT processing_status, archived_at FROM communications WHERE id = ?",
        (communication_id,),
    ).fetchone()
    if not row:
        raise HTTPException(404, detail={"error_type": "not_found"})
    if row["archived_at"]:
        return {"status": "already_archived", "communication_id": communication_id}

    db.execute(
        "UPDATE communications SET archived_at = datetime('now'), updated_at = datetime('now') WHERE id = ?",
        (communication_id,),
    )
    db.commit()
    logger.info("Archived communication %s", communication_id[:8])

    await publish_event("communication_archived", {"communication_id": communication_id})
    return {"status": "archived", "communication_id": communication_id}


@router.post("/{communication_id}/unarchive")
async def unarchive_communication(communication_id: str, db=Depends(get_db)):
    """Restore an archived communication."""
    row = db.execute(
        "SELECT archived_at FROM communications WHERE id = ?",
        (communication_id,),
    ).fetchone()
    if not row:
        raise HTTPException(404, detail={"error_type": "not_found"})

    db.execute(
        "UPDATE communications SET archived_at = NULL, updated_at = datetime('now') WHERE id = ?",
        (communication_id,),
    )
    db.commit()
    logger.info("Unarchived communication %s", communication_id[:8])
    return {"status": "unarchived", "communication_id": communication_id}


@router.delete("/{communication_id}")
async def delete_communication(communication_id: str, db=Depends(get_db)):
    """Permanently delete a communication and all associated data + files."""
    row = db.execute(
        "SELECT id, source_path FROM communications WHERE id = ?",
        (communication_id,),
    ).fetchone()
    if not row:
        raise HTTPException(404, detail={"error_type": "not_found"})

    # Delete child records (order matters for foreign keys)
    child_tables = [
        "transcript_corrections",
        "transcripts",
        "voice_samples",
        "voiceprint_match_log",
        "review_action_log",
        "review_bundles",
        "commit_batches",
        "tracker_writebacks",
        "communication_entities",
        "communication_participants",
        "audio_files",
        "ai_extractions",
        "extraction_bundles",
        "extraction_items",
        "writeback_log",
        "communication_messages",
        "communication_artifacts",
        "llm_usage",
    ]
    for table in child_tables:
        try:
            db.execute(f"DELETE FROM {table} WHERE communication_id = ?", (communication_id,))
        except Exception:
            pass  # Table may not exist yet

    db.execute("DELETE FROM communications WHERE id = ?", (communication_id,))
    db.commit()

    # Clean up files on disk
    storage_dir = AI_UPLOAD_DIR / communication_id
    if storage_dir.exists():
        shutil.rmtree(str(storage_dir), ignore_errors=True)

    logger.info("Deleted communication %s and all associated data", communication_id[:8])

    await publish_event("communication_deleted", {"communication_id": communication_id})
    return {"status": "deleted", "communication_id": communication_id}


MIME_MAP = {
    ".wav": "audio/wav", ".flac": "audio/flac", ".mp3": "audio/mpeg",
    ".m4a": "audio/mp4", ".mp4": "audio/mp4", ".aac": "audio/aac",
    ".ogg": "audio/ogg", ".opus": "audio/opus", ".wma": "audio/x-ms-wma",
    ".webm": "audio/webm",
}


@router.get("/{communication_id}/audio")
async def stream_audio(communication_id: str, request: Request, db=Depends(get_db)):
    """Stream audio file with Range header support for seeking.

    Serves the normalized WAV (preferred) or original audio file.
    Supports HTTP Range requests (206 Partial Content) for audio scrubbing.
    """
    # Find audio file: prefer wav_normalized, fall back to original
    audio_row = db.execute(
        "SELECT file_path, format FROM audio_files WHERE communication_id = ? AND format = 'wav_normalized' LIMIT 1",
        (communication_id,),
    ).fetchone()
    if not audio_row:
        audio_row = db.execute(
            "SELECT file_path, format FROM audio_files WHERE communication_id = ? LIMIT 1",
            (communication_id,),
        ).fetchone()

    if not audio_row:
        raise HTTPException(404, detail={"error_type": "not_found", "message": "No audio file found"})

    file_path = Path(audio_row["file_path"])
    if not file_path.exists():
        raise HTTPException(404, detail={"error_type": "not_found", "message": "Audio file missing from disk"})

    file_size = file_path.stat().st_size
    suffix = file_path.suffix.lower()
    content_type = MIME_MAP.get(suffix, "application/octet-stream")

    range_header = request.headers.get("range")

    if range_header:
        # Parse Range: bytes=start-end
        try:
            range_spec = range_header.replace("bytes=", "").strip()
            parts = range_spec.split("-")
            start = int(parts[0]) if parts[0] else 0
            end = int(parts[1]) if parts[1] else file_size - 1
        except (ValueError, IndexError):
            start, end = 0, file_size - 1

        start = max(0, min(start, file_size - 1))
        end = max(start, min(end, file_size - 1))
        content_length = end - start + 1

        def iter_range():
            chunk_size = 64 * 1024  # 64KB chunks
            with open(file_path, "rb") as f:
                f.seek(start)
                remaining = content_length
                while remaining > 0:
                    read_size = min(chunk_size, remaining)
                    data = f.read(read_size)
                    if not data:
                        break
                    remaining -= len(data)
                    yield data

        return StreamingResponse(
            iter_range(),
            status_code=206,
            media_type=content_type,
            headers={
                "Content-Range": f"bytes {start}-{end}/{file_size}",
                "Accept-Ranges": "bytes",
                "Content-Length": str(content_length),
                "Cache-Control": "no-cache",
            },
        )
    else:
        # Full file response
        def iter_full():
            chunk_size = 64 * 1024
            with open(file_path, "rb") as f:
                while True:
                    data = f.read(chunk_size)
                    if not data:
                        break
                    yield data

        return StreamingResponse(
            iter_full(),
            media_type=content_type,
            headers={
                "Accept-Ranges": "bytes",
                "Content-Length": str(file_size),
                "Cache-Control": "no-cache",
            },
        )


async def _start_pipeline(communication_id: str):
    """Start the pipeline processor for a communication."""
    from app.pipeline.orchestrator import process_communication
    try:
        await process_communication(communication_id)
    except Exception as e:
        logger.exception("Pipeline failed for %s: %s", communication_id, e)
