"""
Pipeline orchestrator — state machine dispatcher for communication processing.

Uses compare-and-set (CAS) transitions to prevent duplicate stage execution.
Uses processing lock tokens to prevent concurrent processing of the same communication.

Phase 1: preprocessing and transcribing stages are wired to real handlers.
Phase 2: cleaning (Haiku cleanup) and enriching (Haiku enrichment) with budget enforcement.
Phase 3: entity review gate (human review of enrichment entities).
Phase 4: extracting (Sonnet extraction with tiered context, config-driven suppression).
Phase 5: Opus escalation (automatic retry with Opus on quality triggers).
Phase 6 (partial): committing (tracker writeback of reviewed bundles).
"""

import asyncio
import uuid
import logging
from datetime import datetime, timedelta
from pathlib import Path

from app.routers.events import publish_event

logger = logging.getLogger(__name__)


def _log_error(
    db,
    communication_id: str,
    error_stage: str,
    error_message: str,
    target_state: str = "error",
):
    """Persist error to communication_error_log and send notification."""
    try:
        db.execute(
            "INSERT INTO communication_error_log (communication_id, error_stage, error_message) "
            "VALUES (?, ?, ?)",
            (
                communication_id,
                error_stage,
                error_message[:2000] if error_message else None,
            ),
        )
        db.commit()
    except Exception as log_err:
        logger.warning(
            "Failed to write error log for %s: %s", communication_id, log_err
        )

    # Send notification (non-blocking, debounced)
    try:
        title_row = db.execute(
            "SELECT title FROM communications WHERE id = ?", (communication_id,)
        ).fetchone()
        title = title_row["title"] if title_row else None
        from app.notifications import notify_pipeline_error

        notify_pipeline_error(
            communication_id, title, error_stage, error_message or "", target_state
        )
    except Exception as notif_err:
        logger.warning(
            "Failed to send error notification for %s: %s",
            communication_id[:8],
            notif_err,
        )


# Semaphores for resource gating
TRANSCRIPTION_SEMAPHORE = asyncio.Semaphore(1)  # Whisper is memory-heavy
LLM_SEMAPHORE = asyncio.Semaphore(3)  # Claude API calls can overlap

# Terminal states — pipeline stops here
TERMINAL_STATES = {
    "complete",
    "duplicate",
    "error",
    "paused_budget",
    "waiting_for_api",
    "awaiting_tracker",
}

# Human gate states — pipeline pauses for user action
HUMAN_GATE_STATES = {
    "awaiting_speaker_review",
    "awaiting_participant_review",
    "awaiting_association_review",
    "awaiting_bundle_review",
}

# Valid transitions: current_status -> next_status
# Audio pipeline
AUDIO_TRANSITIONS = {
    "pending": "preprocessing",
    "preprocessing": "transcribing",
    "transcribing": "cleaning",
    "cleaning": "awaiting_speaker_review",
    "awaiting_speaker_review": "speaker_review_in_progress",
    "speaker_review_in_progress": "speakers_confirmed",
    "speakers_confirmed": "enriching",
    "enriching": "awaiting_association_review",
    "awaiting_association_review": "association_review_in_progress",
    "association_review_in_progress": "associations_confirmed",
    "associations_confirmed": "extracting",
    "extracting": "awaiting_bundle_review",
    "awaiting_bundle_review": "bundle_review_in_progress",
    "bundle_review_in_progress": "reviewed",
    "reviewed": "committing",
    "committing": "complete",
}

# Email pipeline
EMAIL_TRANSITIONS = {
    "pending": "parsing",
    "parsing": "processing_attachments",
    "processing_attachments": "awaiting_participant_review",
    "awaiting_participant_review": "participants_confirmed",
    "participants_confirmed": "enriching",
    "enriching": "awaiting_association_review",
    "awaiting_association_review": "association_review_in_progress",
    "association_review_in_progress": "associations_confirmed",
    "associations_confirmed": "extracting",
    "extracting": "awaiting_bundle_review",
    "awaiting_bundle_review": "bundle_review_in_progress",
    "bundle_review_in_progress": "reviewed",
    "reviewed": "committing",
    "committing": "complete",
}


# Federal Register pipeline — shorter, no transcription/speaker/entity review
FR_TRANSITIONS = {
    "pending": "fetching_text",
    "fetching_text": "extracting",
    "extracting": "awaiting_bundle_review",
    "awaiting_bundle_review": "bundle_review_in_progress",
    "bundle_review_in_progress": "reviewed",
    "reviewed": "committing",
    "committing": "complete",
}

# Lock duration for processing
LOCK_DURATION_MINUTES = 15  # Increased from 10; renewal heartbeat extends lease

# Lock renewal interval (seconds) — must be well under LOCK_DURATION_MINUTES
LOCK_RENEWAL_INTERVAL = 300  # 5 minutes


def acquire_processing_lock(db, communication_id: str) -> str | None:
    """
    Attempt to acquire a processing lock for a communication.
    Returns the lock token if acquired, None if already locked.
    Uses atomic CAS to prevent races.
    """
    token = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    expires = (datetime.utcnow() + timedelta(minutes=LOCK_DURATION_MINUTES)).isoformat()

    # Acquire only if not locked or lock is expired
    cursor = db.execute(
        """
        UPDATE communications
        SET processing_lock_token = ?,
            locked_at = ?,
            lock_expires_at = ?
        WHERE id = ?
        AND (processing_lock_token IS NULL OR lock_expires_at < ?)
    """,
        (token, now, expires, communication_id, now),
    )
    db.commit()

    if cursor.rowcount == 1:
        return token
    return None


def release_processing_lock(db, communication_id: str, token: str):
    """Release a processing lock. Only succeeds if we hold the lock."""
    db.execute(
        """
        UPDATE communications
        SET processing_lock_token = NULL,
            locked_at = NULL,
            lock_expires_at = NULL
        WHERE id = ? AND processing_lock_token = ?
    """,
        (communication_id, token),
    )
    db.commit()


def renew_processing_lock(db, communication_id: str, token: str) -> bool:
    """Extend the lock lease by LOCK_DURATION_MINUTES from now.

    Returns True if renewal succeeded (we still hold the lock).
    Returns False if the lock was stolen or released.
    """
    new_expires = (
        datetime.utcnow() + timedelta(minutes=LOCK_DURATION_MINUTES)
    ).isoformat()
    cursor = db.execute(
        """
        UPDATE communications
        SET lock_expires_at = ?
        WHERE id = ? AND processing_lock_token = ?
    """,
        (new_expires, communication_id, token),
    )
    db.commit()
    return cursor.rowcount == 1


async def _lock_renewal_task(communication_id: str, token: str, db_factory):
    """Background coroutine that renews the processing lock every LOCK_RENEWAL_INTERVAL seconds.

    Runs until cancelled. If renewal fails (lock stolen), logs a warning.
    The main processing loop will detect the stale lock on its next CAS attempt.
    """
    while True:
        await asyncio.sleep(LOCK_RENEWAL_INTERVAL)
        try:
            db = db_factory()
            try:
                renewed = renew_processing_lock(db, communication_id, token)
                if renewed:
                    logger.debug(
                        "Lock renewed for %s (token %s)",
                        communication_id[:8],
                        token[:8],
                    )
                else:
                    logger.warning(
                        "Lock renewal FAILED for %s — lock may have been stolen",
                        communication_id[:8],
                    )
                    return  # Stop renewing; processing loop will detect
            finally:
                db.close()
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.warning("Lock renewal error for %s: %s", communication_id[:8], e)


def cas_transition(
    db,
    communication_id: str,
    expected_status: str,
    next_status: str,
    error_message: str = None,
    error_stage: str = None,
) -> bool:
    """
    Atomic compare-and-set status transition.
    Returns True if the transition succeeded, False if the status was already changed.
    """
    now = datetime.utcnow().isoformat()
    # States that preserve error_message/error_stage (for targeted retry/resume)
    _error_like_states = {
        "error",
        "paused_budget",
        "waiting_for_api",
        "awaiting_tracker",
    }
    if next_status in _error_like_states:
        cursor = db.execute(
            """
            UPDATE communications
            SET processing_status = ?,
                error_message = ?,
                error_stage = ?,
                updated_at = ?
            WHERE id = ? AND processing_status = ?
        """,
            (
                next_status,
                error_message,
                error_stage,
                now,
                communication_id,
                expected_status,
            ),
        )
    else:
        cursor = db.execute(
            """
            UPDATE communications
            SET processing_status = ?,
                error_message = NULL,
                error_stage = NULL,
                updated_at = ?
            WHERE id = ? AND processing_status = ?
        """,
            (next_status, now, communication_id, expected_status),
        )
    db.commit()
    return cursor.rowcount == 1


def get_transitions_for_source(source_type: str) -> dict:
    """Return the valid transition map for a source type."""
    if source_type == "email":
        return EMAIL_TRANSITIONS
    if source_type == "federal_register":
        return FR_TRANSITIONS
    return AUDIO_TRANSITIONS


async def process_communication(communication_id: str, db_factory=None):
    """
    Run automated pipeline stages until hitting a human gate, terminal state, or error.

    This is the core state machine dispatcher. It:
    1. Acquires a processing lock
    2. Reads current status
    3. Executes the appropriate stage handler
    4. Advances status via CAS
    5. Publishes SSE events
    6. Continues until a gate or terminal state
    """
    from app.db import get_connection

    _db_factory = db_factory or get_connection
    db = _db_factory()
    try:
        # Acquire lock
        lock_token = acquire_processing_lock(db, communication_id)
        if not lock_token:
            logger.warning("Could not acquire lock for %s — skipping", communication_id)
            return

        # Start lock renewal heartbeat
        renewal_task = asyncio.create_task(
            _lock_renewal_task(communication_id, lock_token, _db_factory)
        )
        logger.debug("Lock renewal task started for %s", communication_id[:8])

        try:
            stage_retries = 0  # Reset on each new stage; tracks recoverable LLM retries
            prev_stage = None

            while True:
                comm = db.execute(
                    "SELECT id, processing_status, source_type FROM communications WHERE id = ?",
                    (communication_id,),
                ).fetchone()

                if not comm:
                    logger.error("Communication %s not found", communication_id)
                    break

                status = comm["processing_status"]
                source_type = comm["source_type"]

                if status in TERMINAL_STATES:
                    logger.info(
                        "Communication %s in terminal state: %s",
                        communication_id,
                        status,
                    )
                    break

                if status in HUMAN_GATE_STATES:
                    await publish_event(
                        "communication_status",
                        {
                            "communication_id": communication_id,
                            "status": status,
                        },
                    )
                    logger.info(
                        "Communication %s at human gate: %s", communication_id, status
                    )
                    break

                transitions = get_transitions_for_source(source_type)
                next_status = transitions.get(status)
                if not next_status:
                    logger.warning(
                        "No transition from status %s for %s", status, communication_id
                    )
                    break

                # Reset retry counter when stage changes
                if status != prev_stage:
                    stage_retries = 0
                    prev_stage = status

                try:
                    # Savepoint: all stage writes can be rolled back on failure
                    savepoint_name = "stage_%s" % status.replace("-", "_")
                    db.execute("SAVEPOINT %s" % savepoint_name)

                    # Run the stage handler
                    next_status = await run_stage(
                        db, communication_id, status, source_type
                    )

                    # Release savepoint (merge stage writes into main transaction)
                    # Note: stages may call db.commit() internally (e.g. LLM usage tracking),
                    # which releases all savepoints. This is safe — data is already persisted.
                    try:
                        db.execute("RELEASE SAVEPOINT %s" % savepoint_name)
                    except Exception:
                        # Savepoint already released by an internal commit — data is safe
                        db.commit()  # Ensure any uncommitted stage writes are persisted

                    # CAS transition
                    if not cas_transition(db, communication_id, status, next_status):
                        logger.warning(
                            "CAS failed for %s: %s -> %s",
                            communication_id,
                            status,
                            next_status,
                        )
                        break

                    await publish_event(
                        "communication_status",
                        {
                            "communication_id": communication_id,
                            "status": next_status,
                            "previous_status": status,
                        },
                    )

                except Exception as e:
                    # Roll back partial stage writes before handling the error
                    try:
                        db.execute("ROLLBACK TO SAVEPOINT %s" % savepoint_name)
                        db.execute("RELEASE SAVEPOINT %s" % savepoint_name)
                        logger.debug(
                            "Rolled back savepoint %s for %s",
                            savepoint_name,
                            communication_id[:8],
                        )
                    except Exception as rb_err:
                        # Savepoint gone (stage committed) — data already persisted, nothing to roll back
                        logger.debug(
                            "Savepoint %s already released for %s (stage committed internally)",
                            savepoint_name,
                            communication_id[:8],
                        )

                    # Budget exhaustion → paused_budget (not error)
                    from app.llm.client import BudgetExceededError, LLMError

                    if isinstance(e, BudgetExceededError):
                        logger.warning(
                            "Budget exceeded for %s at stage %s: %s",
                            communication_id,
                            status,
                            e,
                        )
                        _log_error(
                            db, communication_id, status, str(e), "paused_budget"
                        )
                        cas_transition(
                            db,
                            communication_id,
                            status,
                            "paused_budget",
                            error_message=str(e),
                            error_stage=status,
                        )
                        await publish_event(
                            "communication_status",
                            {
                                "communication_id": communication_id,
                                "status": "paused_budget",
                                "previous_status": status,
                                "error_message": str(e),
                            },
                        )
                        break

                    # Recoverable LLM errors → retry with backoff (4B)
                    if isinstance(e, LLMError) and e.recoverable:
                        stage_retries += 1
                        if stage_retries <= 3:
                            wait = [30, 60, 120][min(stage_retries - 1, 2)]
                            logger.warning(
                                "Recoverable LLM error for %s at %s (attempt %d/3, "
                                "retrying in %ds): %s",
                                communication_id[:8],
                                status,
                                stage_retries,
                                wait,
                                e,
                            )
                            await asyncio.sleep(wait)
                            continue  # Re-enter the while loop at the same stage

                    # LLM connection error (retries exhausted) → waiting_for_api
                    if isinstance(e, LLMError) and e.error_type in (
                        "connection_error",
                        "rate_limit",
                    ):
                        logger.warning(
                            "LLM unavailable for %s at %s (retries exhausted) — deferring",
                            communication_id[:8],
                            status,
                        )
                        _log_error(
                            db, communication_id, status, str(e), "waiting_for_api"
                        )
                        cas_transition(
                            db,
                            communication_id,
                            status,
                            "waiting_for_api",
                            error_message=str(e),
                            error_stage=status,
                        )
                        await publish_event(
                            "communication_status",
                            {
                                "communication_id": communication_id,
                                "status": "waiting_for_api",
                                "previous_status": status,
                            },
                        )
                        break

                    # Tracker connection error → awaiting_tracker
                    from app.writeback.tracker_client import TrackerBatchError

                    if (
                        isinstance(e, TrackerBatchError)
                        and e.error_type == "connection_error"
                    ):
                        logger.warning(
                            "Tracker unavailable for %s at %s — deferring",
                            communication_id[:8],
                            status,
                        )
                        _log_error(
                            db, communication_id, status, str(e), "awaiting_tracker"
                        )
                        cas_transition(
                            db,
                            communication_id,
                            status,
                            "awaiting_tracker",
                            error_message=str(e),
                            error_stage=status,
                        )
                        await publish_event(
                            "communication_status",
                            {
                                "communication_id": communication_id,
                                "status": "awaiting_tracker",
                                "previous_status": status,
                            },
                        )
                        break

                    # Non-recoverable error
                    logger.error(
                        "Stage %s failed for %s: %s", status, communication_id, str(e)
                    )
                    _log_error(db, communication_id, status, str(e))
                    cas_transition(
                        db,
                        communication_id,
                        status,
                        "error",
                        error_message=str(e),
                        error_stage=status,
                    )
                    await publish_event(
                        "communication_status",
                        {
                            "communication_id": communication_id,
                            "status": "error",
                            "previous_status": status,
                            "error_message": str(e),
                            "error_stage": status,
                        },
                    )
                    break

        finally:
            # Cancel lock renewal heartbeat
            renewal_task.cancel()
            try:
                await renewal_task
            except asyncio.CancelledError:
                pass
            logger.debug("Lock renewal task stopped for %s", communication_id[:8])
            release_processing_lock(db, communication_id, lock_token)
    finally:
        db.close()


async def run_stage(db, communication_id: str, status: str, source_type: str) -> str:
    """
    Execute the handler for a given pipeline stage.
    Returns the next status after successful execution.

    Phase 1: preprocessing and transcribing.
    Phase 2: cleaning (Haiku cleanup) and enriching (Haiku enrichment).
    Phase 4B: extracting (Sonnet extraction).
    Later phases remain stubbed.
    """
    transitions = get_transitions_for_source(source_type)
    next_status = transitions.get(status)

    # ── Phase 1: Real handlers ──

    if status == "preprocessing":
        return await _handle_preprocessing(db, communication_id)

    if status == "transcribing":
        async with TRANSCRIPTION_SEMAPHORE:
            return await _handle_transcription(db, communication_id)

    # ── Phase 2: Haiku cleanup and enrichment ──

    if status == "cleaning":
        return await _handle_cleanup(db, communication_id)

    if status == "enriching":
        return await _handle_enrichment(db, communication_id)

    # ── Phase 4 + 5: Sonnet extraction + Opus escalation ──

    if status == "extracting":
        async with LLM_SEMAPHORE:
            return await _handle_extraction(db, communication_id)

    # ── Phase 6 (partial): Tracker writeback ──

    if status == "committing":
        return await _handle_committing(db, communication_id)

    # ── Phase 7: Email pipeline stages ──

    if status == "parsing":
        return await _handle_email_parsing(db, communication_id)

    if status == "processing_attachments":
        return await _handle_attachment_processing(db, communication_id)

    # ── Future phases: stubs ──

    logger.info("Stage stub: %s -> %s for %s", status, next_status, communication_id)
    return next_status


async def _handle_email_parsing(db, communication_id: str) -> str:
    """Parse email file into messages, attachments, and metadata."""
    from app.pipeline.stages.email_parser import run_email_parsing_stage

    result = await run_email_parsing_stage(db, communication_id)

    if result.get("is_duplicate"):
        logger.info("[%s] Email is duplicate -- terminal state", communication_id[:8])
        return "duplicate"

    return "processing_attachments"


async def _handle_attachment_processing(db, communication_id: str) -> str:
    """Extract text from attachments and resolve email participants."""
    from app.pipeline.stages.attachment_extractor import run_attachment_extraction_stage
    from app.pipeline.stages.participant_resolver import resolve_participants

    # Step 1: Extract text from attachments
    await run_attachment_extraction_stage(db, communication_id)

    # Step 2: Resolve participants
    result = await resolve_participants(db, communication_id)

    # If all participants are auto-confirmed, skip participant review
    if result["all_confirmed"]:
        logger.info(
            "[%s] All %d participants auto-confirmed -- skipping review",
            communication_id[:8],
            result["total"],
        )
        return "participants_confirmed"

    return "awaiting_participant_review"


async def _handle_preprocessing(db, communication_id: str) -> str:
    """Run audio preprocessing: normalize to 16kHz mono PCM WAV."""
    from app.pipeline.stages.preprocessing import preprocess_audio

    # Find the original audio file
    audio_row = db.execute(
        "SELECT file_path, original_filename FROM audio_files WHERE communication_id = ? LIMIT 1",
        (communication_id,),
    ).fetchone()
    if not audio_row:
        raise RuntimeError(f"No audio file found for communication {communication_id}")

    original_path = Path(audio_row["file_path"])
    if not original_path.exists():
        raise FileNotFoundError(f"Audio file not found on disk: {original_path}")

    await publish_event(
        "stage_progress",
        {
            "communication_id": communication_id,
            "stage": "preprocessing",
            "message": f"Normalizing {audio_row['original_filename']}...",
        },
    )

    # Run preprocessing (synchronous, wrapped for async)
    loop = asyncio.get_event_loop()
    normalized_path, metadata = await loop.run_in_executor(
        None, preprocess_audio, original_path, communication_id
    )

    # Update audio_files with normalized path info
    import json

    db.execute(
        """
        UPDATE communications
        SET source_metadata = COALESCE(source_metadata, ?),
            updated_at = datetime('now')
        WHERE id = ?
    """,
        (json.dumps(metadata), communication_id),
    )
    db.commit()

    # Store the normalized path for downstream stages
    # We store it as a second audio_files record with format='wav_normalized'
    db.execute(
        """
        INSERT OR IGNORE INTO audio_files
            (id, communication_id, file_path, original_filename, format,
             file_size_bytes, created_at)
        VALUES (?, ?, ?, ?, 'wav_normalized', ?, datetime('now'))
    """,
        (
            str(uuid.uuid4()),
            communication_id,
            str(normalized_path),
            normalized_path.name,
            normalized_path.stat().st_size if normalized_path.exists() else None,
        ),
    )
    db.commit()

    await publish_event(
        "stage_progress",
        {
            "communication_id": communication_id,
            "stage": "preprocessing",
            "message": "Preprocessing complete",
            "normalized_path": str(normalized_path),
        },
    )

    logger.info(
        "[%s] Preprocessing complete: %s", communication_id[:8], normalized_path.name
    )
    return "transcribing"  # next state


async def _handle_transcription(db, communication_id: str) -> str:
    """Run transcription via native worker (Whisper + pyannote on Mac Mini GPU)."""
    from app.pipeline.stages.transcription import run_transcription_stage

    # Find the normalized WAV (prefer wav_normalized, fall back to original)
    normalized_row = db.execute(
        "SELECT file_path FROM audio_files WHERE communication_id = ? AND format = 'wav_normalized' LIMIT 1",
        (communication_id,),
    ).fetchone()

    if normalized_row:
        audio_path = Path(normalized_row["file_path"])
    else:
        # Fall back to original file
        audio_row = db.execute(
            "SELECT file_path FROM audio_files WHERE communication_id = ? LIMIT 1",
            (communication_id,),
        ).fetchone()
        if not audio_row:
            raise RuntimeError(f"No audio file for communication {communication_id}")
        audio_path = Path(audio_row["file_path"])

    if not audio_path.exists():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    await publish_event(
        "stage_progress",
        {
            "communication_id": communication_id,
            "stage": "transcribing",
            "message": "Sending to transcription worker...",
        },
    )

    result = await run_transcription_stage(db, communication_id, audio_path)

    await publish_event(
        "stage_progress",
        {
            "communication_id": communication_id,
            "stage": "transcribing",
            "message": f"Transcription complete: {len(result.segments)} segments, "
            f"{result.num_speakers} speakers, {result.duration:.0f}s",
        },
    )

    return "cleaning"  # next state


async def _handle_cleanup(db, communication_id: str) -> str:
    """Run Haiku transcript cleanup (filler removal, punctuation, etc.)."""
    from app.pipeline.stages.cleanup import run_cleanup_stage

    await publish_event(
        "stage_progress",
        {
            "communication_id": communication_id,
            "stage": "cleaning",
            "message": "Running Haiku transcript cleanup...",
        },
    )

    result = await run_cleanup_stage(db, communication_id)

    await publish_event(
        "stage_progress",
        {
            "communication_id": communication_id,
            "stage": "cleaning",
            "message": (
                f"Cleanup complete: {result['segments_cleaned']} segments, "
                f"${result['total_cost_usd']:.4f}"
            ),
        },
    )

    logger.info(
        "[%s] Cleanup stage done: %d segments cleaned, $%.4f",
        communication_id[:8],
        result["segments_cleaned"],
        result["total_cost_usd"],
    )
    return "awaiting_speaker_review"  # next state


async def _handle_enrichment(db, communication_id: str) -> str:
    """Run Haiku enrichment (summary, topics, entities, sensitivity flags)."""
    from app.pipeline.stages.enrichment import run_enrichment_stage

    await publish_event(
        "stage_progress",
        {
            "communication_id": communication_id,
            "stage": "enriching",
            "message": "Running Haiku enrichment...",
        },
    )

    result = await run_enrichment_stage(db, communication_id)

    await publish_event(
        "stage_progress",
        {
            "communication_id": communication_id,
            "stage": "enriching",
            "message": (
                f"Enrichment complete: {result['entities_found']} entities, "
                f"{result['topics_found']} topics, ${result['total_cost_usd']:.4f}"
            ),
        },
    )

    logger.info(
        "[%s] Enrichment stage done: %d entities, %d topics, $%.4f",
        communication_id[:8],
        result["entities_found"],
        result["topics_found"],
        result["total_cost_usd"],
    )
    return "awaiting_association_review"  # next state


async def _handle_extraction(db, communication_id: str) -> str:
    """Run Sonnet extraction (structured intelligence proposals from transcript)."""
    from app.pipeline.stages.extraction import run_extraction_stage

    await publish_event(
        "stage_progress",
        {
            "communication_id": communication_id,
            "stage": "extracting",
            "message": "Running Sonnet extraction...",
        },
    )

    result = await run_extraction_stage(db, communication_id)

    escalation_note = ""
    if result.get("escalated"):
        escalation_note = f" (escalated to {result.get('model_used', 'Opus')})"

    await publish_event(
        "stage_progress",
        {
            "communication_id": communication_id,
            "stage": "extracting",
            "message": (
                f"Extraction complete{escalation_note}: {result['bundles_created']} bundles, "
                f"{result['items_created']} items, "
                f"{result['items_suppressed']} suppressed, "
                f"${result['total_cost_usd']:.4f}"
            ),
        },
    )

    logger.info(
        "[%s] Extraction stage done: %d bundles, %d items, %d suppressed, "
        "escalated=%s, $%.4f",
        communication_id[:8],
        result["bundles_created"],
        result["items_created"],
        result["items_suppressed"],
        result.get("escalated", False),
        result["total_cost_usd"],
    )
    return "awaiting_bundle_review"  # next state


async def _handle_committing(db, communication_id: str) -> str:
    """Run tracker writeback — commit all accepted/edited items to tracker via batch API."""
    from app.writeback.committer import commit_communication
    from app.writeback.tracker_client import TrackerBatchError

    # Pre-commit health check: verify tracker is reachable before starting
    import httpx
    from app.config import TRACKER_BASE_URL

    try:
        async with httpx.AsyncClient(timeout=5.0) as hc:
            health_url = (
                TRACKER_BASE_URL.rstrip("/").rsplit("/tracker", 1)[0]
                + "/tracker/health"
            )
            resp = await hc.get(health_url)
        if resp.status_code != 200:
            raise TrackerBatchError(
                0,
                "connection_error",
                "Pre-commit health check: tracker returned %d" % resp.status_code,
            )
    except (httpx.ConnectError, httpx.TimeoutException, OSError) as e:
        raise TrackerBatchError(
            0,
            "connection_error",
            "Pre-commit health check: tracker unreachable — %s" % e,
        )

    await publish_event(
        "stage_progress",
        {
            "communication_id": communication_id,
            "stage": "committing",
            "message": "Committing reviewed items to tracker...",
        },
    )

    result = await commit_communication(db, communication_id)

    if not result.all_succeeded:
        # Partial failure — raise so orchestrator transitions to error
        failed_details = [
            f"{br.bundle_id[:8]}({br.error_type}: {br.error})"
            for br in result.bundle_results
            if not br.success
        ]
        raise RuntimeError(
            f"Commit partial failure: {result.bundles_failed} bundles failed "
            f"({result.bundles_committed} succeeded). "
            f"Failures: {'; '.join(failed_details)}"
        )

    await publish_event(
        "stage_progress",
        {
            "communication_id": communication_id,
            "stage": "committing",
            "message": (
                f"Commit complete: {result.bundles_committed} bundles, "
                f"{result.total_records} records written"
            ),
        },
    )

    logger.info(
        "[%s] Committing stage done: %d bundles committed, %d records, %d skipped",
        communication_id[:8],
        result.bundles_committed,
        result.total_records,
        result.bundles_skipped,
    )
    return "complete"  # next state
