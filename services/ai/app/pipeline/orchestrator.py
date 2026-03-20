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

# Semaphores for resource gating
TRANSCRIPTION_SEMAPHORE = asyncio.Semaphore(1)   # Whisper is memory-heavy
LLM_SEMAPHORE = asyncio.Semaphore(3)             # Claude API calls can overlap

# Terminal states — pipeline stops here
TERMINAL_STATES = {"complete", "duplicate", "error", "paused_budget"}

# Human gate states — pipeline pauses for user action
HUMAN_GATE_STATES = {
    "awaiting_speaker_review",
    "awaiting_participant_review",
    "awaiting_entity_review",
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
    "enriching": "awaiting_entity_review",
    "awaiting_entity_review": "entity_review_in_progress",
    "entity_review_in_progress": "entities_confirmed",
    "entities_confirmed": "extracting",
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
    "enriching": "awaiting_entity_review",
    "awaiting_entity_review": "entity_review_in_progress",
    "entity_review_in_progress": "entities_confirmed",
    "entities_confirmed": "extracting",
    "extracting": "awaiting_bundle_review",
    "awaiting_bundle_review": "bundle_review_in_progress",
    "bundle_review_in_progress": "reviewed",
    "reviewed": "committing",
    "committing": "complete",
}

# Lock duration for processing
LOCK_DURATION_MINUTES = 10


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
    cursor = db.execute("""
        UPDATE communications
        SET processing_lock_token = ?,
            locked_at = ?,
            lock_expires_at = ?
        WHERE id = ?
        AND (processing_lock_token IS NULL OR lock_expires_at < ?)
    """, (token, now, expires, communication_id, now))
    db.commit()

    if cursor.rowcount == 1:
        return token
    return None


def release_processing_lock(db, communication_id: str, token: str):
    """Release a processing lock. Only succeeds if we hold the lock."""
    db.execute("""
        UPDATE communications
        SET processing_lock_token = NULL,
            locked_at = NULL,
            lock_expires_at = NULL
        WHERE id = ? AND processing_lock_token = ?
    """, (communication_id, token))
    db.commit()


def cas_transition(db, communication_id: str, expected_status: str,
                   next_status: str, error_message: str = None,
                   error_stage: str = None) -> bool:
    """
    Atomic compare-and-set status transition.
    Returns True if the transition succeeded, False if the status was already changed.
    """
    now = datetime.utcnow().isoformat()
    if next_status == "error":
        cursor = db.execute("""
            UPDATE communications
            SET processing_status = ?,
                error_message = ?,
                error_stage = ?,
                updated_at = ?
            WHERE id = ? AND processing_status = ?
        """, (next_status, error_message, error_stage, now,
              communication_id, expected_status))
    else:
        cursor = db.execute("""
            UPDATE communications
            SET processing_status = ?,
                error_message = NULL,
                error_stage = NULL,
                updated_at = ?
            WHERE id = ? AND processing_status = ?
        """, (next_status, now, communication_id, expected_status))
    db.commit()
    return cursor.rowcount == 1


def get_transitions_for_source(source_type: str) -> dict:
    """Return the valid transition map for a source type."""
    if source_type == "email":
        return EMAIL_TRANSITIONS
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

    db = db_factory() if db_factory else get_connection()
    try:
        # Acquire lock
        lock_token = acquire_processing_lock(db, communication_id)
        if not lock_token:
            logger.warning("Could not acquire lock for %s — skipping", communication_id)
            return

        try:
            while True:
                comm = db.execute(
                    "SELECT id, processing_status, source_type FROM communications WHERE id = ?",
                    (communication_id,)
                ).fetchone()

                if not comm:
                    logger.error("Communication %s not found", communication_id)
                    break

                status = comm["processing_status"]
                source_type = comm["source_type"]

                if status in TERMINAL_STATES:
                    logger.info("Communication %s in terminal state: %s", communication_id, status)
                    break

                if status in HUMAN_GATE_STATES:
                    await publish_event("communication_status", {
                        "communication_id": communication_id,
                        "status": status,
                    })
                    logger.info("Communication %s at human gate: %s", communication_id, status)
                    break

                transitions = get_transitions_for_source(source_type)
                next_status = transitions.get(status)
                if not next_status:
                    logger.warning("No transition from status %s for %s", status, communication_id)
                    break

                try:
                    # Run the stage handler
                    next_status = await run_stage(db, communication_id, status, source_type)

                    # CAS transition
                    if not cas_transition(db, communication_id, status, next_status):
                        logger.warning("CAS failed for %s: %s -> %s", communication_id, status, next_status)
                        break

                    await publish_event("communication_status", {
                        "communication_id": communication_id,
                        "status": next_status,
                        "previous_status": status,
                    })

                except Exception as e:
                    # Budget exhaustion → paused_budget (not error)
                    from app.llm.client import BudgetExceededError
                    if isinstance(e, BudgetExceededError):
                        logger.warning(
                            "Budget exceeded for %s at stage %s: %s",
                            communication_id, status, e,
                        )
                        cas_transition(
                            db, communication_id, status, "paused_budget",
                            error_message=str(e), error_stage=status,
                        )
                        await publish_event("communication_status", {
                            "communication_id": communication_id,
                            "status": "paused_budget",
                            "previous_status": status,
                            "error_message": str(e),
                        })
                        break

                    logger.error("Stage %s failed for %s: %s", status, communication_id, str(e))
                    cas_transition(
                        db, communication_id, status, "error",
                        error_message=str(e), error_stage=status
                    )
                    await publish_event("communication_status", {
                        "communication_id": communication_id,
                        "status": "error",
                        "previous_status": status,
                        "error_message": str(e),
                        "error_stage": status,
                    })
                    break

        finally:
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
        logger.info("[%s] All %d participants auto-confirmed -- skipping review",
                    communication_id[:8], result["total"])
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

    await publish_event("stage_progress", {
        "communication_id": communication_id,
        "stage": "preprocessing",
        "message": f"Normalizing {audio_row['original_filename']}...",
    })

    # Run preprocessing (synchronous, wrapped for async)
    loop = asyncio.get_event_loop()
    normalized_path, metadata = await loop.run_in_executor(
        None, preprocess_audio, original_path, communication_id
    )

    # Update audio_files with normalized path info
    import json
    db.execute("""
        UPDATE communications
        SET source_metadata = COALESCE(source_metadata, ?),
            updated_at = datetime('now')
        WHERE id = ?
    """, (json.dumps(metadata), communication_id))

    # If metadata contains a creation_time from the file, use it as captured_at
    creation_time = metadata.get("creation_time")
    if creation_time:
        try:
            from datetime import datetime as dt
            parsed = dt.fromisoformat(creation_time.replace("Z", "+00:00"))
            db.execute("""
                UPDATE audio_files
                SET captured_at = ?
                WHERE communication_id = ? AND format != 'wav_normalized'
            """, (parsed.isoformat(), communication_id))
            logger.info("[%s] Set captured_at from file metadata: %s",
                        communication_id[:8], parsed.isoformat())
        except (ValueError, TypeError) as e:
            logger.warning("[%s] Could not parse creation_time '%s': %s",
                           communication_id[:8], creation_time, e)

    db.commit()

    # Store the normalized path for downstream stages
    # We store it as a second audio_files record with format='wav_normalized'
    db.execute("""
        INSERT OR IGNORE INTO audio_files
            (id, communication_id, file_path, original_filename, format,
             file_size_bytes, created_at)
        VALUES (?, ?, ?, ?, 'wav_normalized', ?, datetime('now'))
    """, (
        str(uuid.uuid4()), communication_id,
        str(normalized_path), normalized_path.name,
        normalized_path.stat().st_size if normalized_path.exists() else None,
    ))
    db.commit()

    await publish_event("stage_progress", {
        "communication_id": communication_id,
        "stage": "preprocessing",
        "message": "Preprocessing complete",
        "normalized_path": str(normalized_path),
    })

    logger.info("[%s] Preprocessing complete: %s", communication_id[:8], normalized_path.name)
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

    await publish_event("stage_progress", {
        "communication_id": communication_id,
        "stage": "transcribing",
        "message": "Sending to transcription worker...",
    })

    result = await run_transcription_stage(db, communication_id, audio_path)

    await publish_event("stage_progress", {
        "communication_id": communication_id,
        "stage": "transcribing",
        "message": f"Transcription complete: {len(result.segments)} segments, "
                   f"{result.num_speakers} speakers, {result.duration:.0f}s",
    })

    return "cleaning"  # next state


async def _handle_cleanup(db, communication_id: str) -> str:
    """Run Haiku transcript cleanup (filler removal, punctuation, etc.)."""
    from app.pipeline.stages.cleanup import run_cleanup_stage

    await publish_event("stage_progress", {
        "communication_id": communication_id,
        "stage": "cleaning",
        "message": "Running Haiku transcript cleanup...",
    })

    result = await run_cleanup_stage(db, communication_id)

    await publish_event("stage_progress", {
        "communication_id": communication_id,
        "stage": "cleaning",
        "message": (
            f"Cleanup complete: {result['segments_cleaned']} segments, "
            f"${result['total_cost_usd']:.4f}"
        ),
    })

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

    await publish_event("stage_progress", {
        "communication_id": communication_id,
        "stage": "enriching",
        "message": "Running Haiku enrichment...",
    })

    result = await run_enrichment_stage(db, communication_id)

    await publish_event("stage_progress", {
        "communication_id": communication_id,
        "stage": "enriching",
        "message": (
            f"Enrichment complete: {result['entities_found']} entities, "
            f"{result['topics_found']} topics, ${result['total_cost_usd']:.4f}"
        ),
    })

    logger.info(
        "[%s] Enrichment stage done: %d entities, %d topics, $%.4f",
        communication_id[:8],
        result["entities_found"],
        result["topics_found"],
        result["total_cost_usd"],
    )
    return "awaiting_entity_review"  # next state


async def _handle_extraction(db, communication_id: str) -> str:
    """Run Sonnet extraction (structured intelligence proposals from transcript)."""
    from app.pipeline.stages.extraction import run_extraction_stage

    await publish_event("stage_progress", {
        "communication_id": communication_id,
        "stage": "extracting",
        "message": "Running Sonnet extraction...",
    })

    result = await run_extraction_stage(db, communication_id)

    escalation_note = ""
    if result.get("escalated"):
        escalation_note = f" (escalated to {result.get('model_used', 'Opus')})"

    await publish_event("stage_progress", {
        "communication_id": communication_id,
        "stage": "extracting",
        "message": (
            f"Extraction complete{escalation_note}: {result['bundles_created']} bundles, "
            f"{result['items_created']} items, "
            f"{result['items_suppressed']} suppressed, "
            f"${result['total_cost_usd']:.4f}"
        ),
    })

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

    await publish_event("stage_progress", {
        "communication_id": communication_id,
        "stage": "committing",
        "message": "Committing reviewed items to tracker...",
    })

    result = await commit_communication(db, communication_id)

    if not result.all_succeeded:
        # Partial failure — raise so orchestrator transitions to error
        failed_details = [
            f"{br.bundle_id[:8]}({br.error_type}: {br.error})"
            for br in result.bundle_results if not br.success
        ]
        raise RuntimeError(
            f"Commit partial failure: {result.bundles_failed} bundles failed "
            f"({result.bundles_committed} succeeded). "
            f"Failures: {'; '.join(failed_details)}"
        )

    await publish_event("stage_progress", {
        "communication_id": communication_id,
        "stage": "committing",
        "message": (
            f"Commit complete: {result.bundles_committed} bundles, "
            f"{result.total_records} records written"
        ),
    })

    logger.info(
        "[%s] Committing stage done: %d bundles committed, %d records, %d skipped",
        communication_id[:8],
        result.bundles_committed,
        result.total_records,
        result.bundles_skipped,
    )

    # Post-commit hook: generate meeting intelligence if a meeting was committed
    try:
        from app.pipeline.stages.meeting_intelligence import generate_meeting_intelligence
        intel = await generate_meeting_intelligence(db, communication_id)
        if intel:
            logger.info("[%s] Meeting intelligence generated successfully",
                        communication_id[:8])
    except Exception as e:
        # Meeting intelligence is non-critical -- log and continue
        logger.warning("[%s] Meeting intelligence generation failed (non-fatal): %s",
                       communication_id[:8], e)

    return "complete"  # next state
