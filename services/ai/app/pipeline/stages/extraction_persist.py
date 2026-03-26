"""Persistence layer for extraction results.

Writes extraction output, review bundles, and source locators to the AI database.
Also handles bundle cleanup and failed extraction recording.
"""

from typing import Optional
import json
import logging
import uuid

from app.pipeline.stages.extraction_models import ExtractionOutput

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════


def _build_source_locator(db, item, communication_id: str) -> dict:
    """Build canonical source_locator_json from model output."""
    # Detect source type
    comm_row = db.execute(
        "SELECT source_type, topic_segments_json FROM communications WHERE id = ?",
        (communication_id,),
    ).fetchone()
    source_type = comm_row["source_type"] if comm_row else "audio_upload"

    # Resolve entity refs by matching excerpt against confirmed entities
    entity_refs = []
    excerpt_lower = (item.source_excerpt or "").lower()
    if excerpt_lower:
        ent_rows = db.execute(
            """
            SELECT id, mention_text FROM communication_entities
            WHERE communication_id = ? AND confirmed != -1
        """,
            (communication_id,),
        ).fetchall()
        for er in ent_rows:
            if er["mention_text"] and er["mention_text"].lower() in excerpt_lower:
                entity_refs.append(er["id"])

    if source_type == "email":
        # Email source locator: message_index based
        # Try to find the message that contains the excerpt
        message_index = None
        message_id = None
        if item.source_excerpt:
            msg_rows = db.execute(
                """
                SELECT id, message_index, body_text
                FROM communication_messages
                WHERE communication_id = ?
                ORDER BY message_index
            """,
                (communication_id,),
            ).fetchall()
            for mr in msg_rows:
                if item.source_excerpt[:100].lower() in (mr["body_text"] or "").lower():
                    message_index = mr["message_index"]
                    message_id = mr["id"]
                    break

        return {
            "type": "email",
            "message_index": message_index,
            "message_id": message_id,
            "excerpt": item.source_excerpt,
            "entity_refs": entity_refs,
        }

    # Audio source locator: transcript segment based
    seg_ids = item.source_segments
    time_range = item.source_time_range

    # Resolve speaker from first segment
    speaker_label = None
    speaker_name = None
    if seg_ids:
        seg_row = db.execute(
            "SELECT speaker_label FROM transcripts WHERE id = ?",
            (seg_ids[0],),
        ).fetchone()
        if seg_row:
            speaker_label = seg_row["speaker_label"]
            # Resolve name
            part_row = db.execute(
                """SELECT proposed_name FROM communication_participants
                   WHERE communication_id = ? AND speaker_label = ?""",
                (communication_id, speaker_label),
            ).fetchone()
            if part_row:
                speaker_name = part_row["proposed_name"]

    # Resolve enrichment topic by time overlap
    enrichment_topic = None
    if comm_row and comm_row["topic_segments_json"]:
        try:
            td = json.loads(comm_row["topic_segments_json"])
            for t in td.get("topics", []):
                t_start = t.get("start_time", 0)
                t_end = t.get("end_time", 0)
                if t_start < time_range.end and t_end > time_range.start:
                    enrichment_topic = t.get("topic")
                    break
        except (json.JSONDecodeError, TypeError):
            pass

    return {
        "type": "transcript",
        "segments": seg_ids,
        "time_range": {
            "start_seconds": time_range.start,
            "end_seconds": time_range.end,
        },
        "speaker_label": speaker_label,
        "speaker_name": speaker_name,
        "excerpt": item.source_excerpt,
        "entity_refs": entity_refs,
        "enrichment_topic": enrichment_topic,
    }


def _persist_extraction(
    db,
    communication_id: str,
    extraction: ExtractionOutput,
    processed: dict,
    system_prompt: str,
    user_prompt: str,
    full_context_json: str,
    raw_output: str,
    attempt_number: int,
    model_used: str,
    prompt_version: str,
    usage_data: dict,
    escalation_reason: Optional[str] = None,
    success: bool = True,
) -> str:
    """Persist extraction record, review bundles, and review bundle items.

    Returns the extraction ID.
    """
    extraction_id = str(uuid.uuid4())
    post_log = processed["post_processing_log"]

    # Append post-processing metadata to raw output
    try:
        raw_json = json.loads(raw_output)
    except json.JSONDecodeError:
        raw_json = {"_raw_text": raw_output}
    raw_json["_post_processing"] = post_log
    enriched_raw = json.dumps(raw_json, ensure_ascii=False, default=str)

    # Insert ai_extractions record
    db.execute(
        """
        INSERT INTO ai_extractions
            (id, communication_id, attempt_number, model_used, prompt_version,
             system_prompt, user_prompt, raw_output, input_tokens, output_tokens,
             processing_seconds, tracker_context_snapshot,
             escalation_reason, success)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """,
        (
            extraction_id,
            communication_id,
            attempt_number,
            model_used,
            prompt_version,
            system_prompt,
            user_prompt,
            enriched_raw,
            usage_data.get("input_tokens", 0),
            usage_data.get("output_tokens", 0),
            usage_data.get("processing_seconds", 0),
            full_context_json,
            escalation_reason,
            1 if success else 0,
        ),
    )

    # Insert review bundles and items
    bundles = processed["bundles"]
    for sort_idx, bundle in enumerate(bundles):
        bundle_id = str(uuid.uuid4())

        db.execute(
            """
            INSERT INTO review_bundles
                (id, communication_id, bundle_type, target_matter_id,
                 target_matter_title, proposed_matter_json, status,
                 confidence, rationale, intelligence_notes, sort_order)
            VALUES (?, ?, ?, ?, ?, ?, 'proposed', ?, ?, ?, ?)
        """,
            (
                bundle_id,
                communication_id,
                bundle.bundle_type,
                bundle.target_matter_id,
                bundle.target_matter_title,
                json.dumps(bundle.proposed_matter, default=str)
                if bundle.proposed_matter
                else None,
                bundle.confidence,
                bundle.rationale,
                bundle.intelligence_notes,
                sort_idx,
            ),
        )

        for item_idx, item in enumerate(bundle.items):
            item_id = str(uuid.uuid4())
            source_locator = _build_source_locator(db, item, communication_id)

            db.execute(
                """
                INSERT INTO review_bundle_items
                    (id, bundle_id, item_type, status, proposed_data,
                     confidence, rationale, source_excerpt,
                     source_transcript_id, source_start_time, source_end_time,
                     source_locator_json, sort_order)
                VALUES (?, ?, ?, 'proposed', ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    item_id,
                    bundle_id,
                    item.item_type,
                    json.dumps(item.proposed_data, ensure_ascii=False, default=str),
                    item.confidence,
                    item.rationale,
                    item.source_excerpt,
                    item.source_segments[0] if item.source_segments else None,
                    item.source_time_range.start,
                    item.source_time_range.end,
                    json.dumps(source_locator, ensure_ascii=False, default=str),
                    item_idx,
                ),
            )

    db.commit()

    logger.info(
        "[%s] Extraction persisted: %d bundles, extraction_id=%s",
        communication_id[:8],
        len(bundles),
        extraction_id[:8],
    )
    return extraction_id


# ═══════════════════════════════════════════════════════════════════════════


def _clear_bundles_for_communication(db, communication_id: str):
    """Remove Sonnet-generated bundles/items before Opus re-persist.

    Only clears bundles still in 'proposed' status (not yet reviewed).
    """
    bundle_ids = [
        r["id"]
        for r in db.execute(
            "SELECT id FROM review_bundles WHERE communication_id = ? AND status = 'proposed'",
            (communication_id,),
        ).fetchall()
    ]
    for bid in bundle_ids:
        db.execute("DELETE FROM review_bundle_items WHERE bundle_id = ?", (bid,))
    db.execute(
        "DELETE FROM review_bundles WHERE communication_id = ? AND status = 'proposed'",
        (communication_id,),
    )
    db.commit()
    if bundle_ids:
        logger.info(
            "[%s] Cleared %d Sonnet bundles for Opus replacement",
            communication_id[:8],
            len(bundle_ids),
        )


def _persist_failed_extraction(
    db,
    communication_id: str,
    model: str,
    result: "ExtractionAttemptResult",
    prompt_version: str,
    full_context_json: str,
):
    """Persist a failed extraction attempt for audit trail."""
    extraction_id = str(uuid.uuid4())
    db.execute(
        """
        INSERT INTO ai_extractions
            (id, communication_id, attempt_number, model_used, prompt_version,
             raw_output, escalation_reason, success,
             tracker_context_snapshot)
        VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?)
    """,
        (
            extraction_id,
            communication_id,
            result.attempt_number,
            model,
            prompt_version,
            result.raw_output or f"[FAILED: {result.failure_detail}]",
            result.escalation_reason,
            full_context_json,
        ),
    )
    db.commit()
