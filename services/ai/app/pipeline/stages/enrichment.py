"""Haiku enrichment stage — extracts structured metadata from cleaned transcript.

Pipeline position: speakers_confirmed → **enriching** → awaiting_entity_review

Takes the full cleaned transcript with confirmed speaker identities and
produces: summary, topic segments, entity mentions, sensitivity flags,
and quality signals. Runs AFTER speaker review because enrichment needs
to know who said what.

Unlike cleanup (which batches segments), enrichment sends the full
transcript in a single call since it needs holistic context for
summary, topic segmentation, and cross-reference detection.
"""

import json
import logging
import uuid

from app.config import load_policy, PROMPT_BASE_DIR
from app.llm.client import call_llm

logger = logging.getLogger(__name__)

PROMPT_DIR = PROMPT_BASE_DIR / "haiku_enrichment"


def _load_system_prompt(version: str) -> str:
    """Load the enrichment system prompt for the given version."""
    prompt_path = PROMPT_DIR / f"{version}.md"
    if not prompt_path.exists():
        raise FileNotFoundError(f"Enrichment prompt not found: {prompt_path}")
    return prompt_path.read_text(encoding="utf-8")


def _build_enrichment_payload(
    communication_id: str,
    duration: float,
    speakers: list[dict],
    segments: list[dict],
) -> str:
    """Build the user prompt payload for enrichment (audio)."""
    payload = {
        "communication_id": communication_id,
        "duration_seconds": duration,
        "speakers": speakers,
        "segments": [
            {
                "speaker": seg["speaker_label"],
                "start": seg["start_time"],
                "end": seg["end_time"],
                "text": seg.get("reviewed_text") or seg["cleaned_text"] or seg["raw_text"],
            }
            for seg in segments
        ],
    }
    return json.dumps(payload, ensure_ascii=False)


def _build_email_enrichment_payload(
    communication_id: str,
    participants: list[dict],
    messages: list[dict],
    attachments: list[dict],
) -> str:
    """Build the user prompt payload for enrichment (email)."""
    payload = {
        "communication_id": communication_id,
        "source_type": "email",
        "participants": participants,
        "messages": [
            {
                "message_index": msg["message_index"],
                "sender_email": msg.get("sender_email"),
                "sender_name": msg.get("sender_name"),
                "subject": msg.get("subject"),
                "body_text": msg["body_text"],
                "is_new": msg["is_new"],
                "is_from_user": msg.get("is_from_user", 0),
            }
            for msg in messages
        ],
        "attachments": [
            {
                "filename": att["original_filename"],
                "mime_type": att["mime_type"],
                "size_bytes": att["file_size_bytes"],
                "extracted_text_preview": (att.get("extracted_text") or "")[:2000],
            }
            for att in attachments
        ],
    }
    return json.dumps(payload, ensure_ascii=False)


def _parse_enrichment_response(text: str) -> dict:
    """Parse Haiku's enrichment response JSON.

    Tolerates markdown fencing. Returns empty dict on parse failure.
    """
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines)

    try:
        result = json.loads(cleaned)
    except json.JSONDecodeError as e:
        logger.warning("Enrichment response JSON parse failed: %s", e)
        return {}

    if not isinstance(result, dict):
        logger.warning("Enrichment response is not a dict: %s", type(result).__name__)
        return {}

    return result


def _store_enrichment(db, communication_id: str, enrichment: dict, segments: list[dict]):
    """Persist enrichment results to the database.

    Stores:
    - Summary + topic segments on communication record (topic_segments_json)
    - Sensitivity flags on communication (sensitivity_flags)
    - Entity mentions in communication_entities table
    - Enriched text annotation on transcript rows
    """
    # 1. Store summary, topics, quality, and title on communication
    title = enrichment.get("title", "")
    summary = enrichment.get("summary", "")
    topics = enrichment.get("topics", [])
    quality = enrichment.get("quality_signals", {})

    topic_data = json.dumps({
        "summary": summary,
        "topics": topics,
        "quality_signals": quality,
    }, ensure_ascii=False)

    db.execute("""
        UPDATE communications
        SET topic_segments_json = ?,
            title = COALESCE(NULLIF(?, ''), title),
            updated_at = datetime('now')
        WHERE id = ?
    """, (topic_data, title, communication_id))

    if title:
        logger.info("[%s] Title set: %s", communication_id[:8], title)

    # 2. Store sensitivity flags
    sensitivity = enrichment.get("sensitivity_flags", {})
    active_flags = [
        flag for flag, is_set in sensitivity.items()
        if is_set and isinstance(is_set, bool)
    ]
    if active_flags:
        db.execute("""
            UPDATE communications
            SET sensitivity_flags = ?,
                updated_at = datetime('now')
            WHERE id = ?
        """, (json.dumps(active_flags), communication_id))
        logger.info(
            "[%s] Sensitivity flags: %s",
            communication_id[:8], active_flags,
        )

    # 3. Store entity mentions
    entities = enrichment.get("entities", [])
    for ent in entities:
        mention_text = ent.get("mention_text", "")
        entity_type = ent.get("entity_type", "unknown")
        context = ent.get("context", "")
        count = ent.get("mention_count", 1)

        if not mention_text:
            continue

        # Find the first transcript segment that mentions this entity
        first_transcript_id = None
        mention_lower = mention_text.lower()
        for seg in segments:
            seg_text = (seg.get("cleaned_text") or seg.get("raw_text") or "").lower()
            if mention_lower in seg_text:
                first_transcript_id = seg["id"]
                break

        db.execute("""
            INSERT INTO communication_entities
                (id, communication_id, mention_text, entity_type,
                 confidence, confirmed, mention_count,
                 first_mention_transcript_id, context_snippet)
            VALUES (?, ?, ?, ?, ?, 0, ?, ?, ?)
        """, (
            str(uuid.uuid4()), communication_id, mention_text,
            entity_type, 0.8, count, first_transcript_id,
            context[:500] if context else None,
        ))

    # 4. Store enriched text annotation on transcript segments
    # For now, store the summary as enriched_text on each segment
    # (future: per-segment topic tags)
    if topics:
        for seg in segments:
            start = seg["start_time"]
            end = seg["end_time"]
            # Find which topics overlap this segment
            seg_topics = []
            for t in topics:
                t_start = t.get("start_time", 0)
                t_end = t.get("end_time", 0)
                if t_start < end and t_end > start:
                    seg_topics.append(t.get("topic", ""))
            if seg_topics:
                db.execute(
                    "UPDATE transcripts SET enriched_text = ? WHERE id = ?",
                    (json.dumps(seg_topics), seg["id"]),
                )

    db.commit()

    logger.info(
        "[%s] Enrichment stored: summary=%d chars, %d topics, %d entities, flags=%s",
        communication_id[:8], len(summary), len(topics), len(entities),
        active_flags or "none",
    )


async def run_enrichment_stage(db, communication_id: str) -> dict:
    """Run Haiku enrichment on the full transcript for a communication.

    Returns summary dict with entity counts and total cost.
    Raises BudgetExceededError if budget is exhausted.
    """
    # Load config
    policy = load_policy()
    model_config = policy.get("model_config", {})
    haiku_model = model_config.get("haiku_model", "claude-haiku-4-5-20251001")
    prompt_version = model_config.get("active_prompt_versions", {}).get(
        "haiku_enrichment", "v1.0.0"
    )

    system_prompt = _load_system_prompt(prompt_version)

    # Get communication metadata
    comm = db.execute(
        "SELECT duration_seconds, source_type FROM communications WHERE id = ?",
        (communication_id,),
    ).fetchone()
    duration = comm["duration_seconds"] if comm and comm["duration_seconds"] else 0.0
    source_type = comm["source_type"] if comm else "audio_upload"

    # Get confirmed participants
    participants = db.execute("""
        SELECT speaker_label, tracker_person_id, proposed_name,
               participant_email, header_role, participant_role
        FROM communication_participants
        WHERE communication_id = ?
        ORDER BY speaker_label
    """, (communication_id,)).fetchall()

    # Branch on source_type for payload construction
    segments = []  # Will be populated for audio path

    if source_type == "email":
        # Email path: use messages + attachments instead of transcript
        email_participants = [
            {
                "email": p["participant_email"],
                "person_id": p["tracker_person_id"],
                "name": p["proposed_name"] or p["participant_email"] or "unknown",
                "role": p["header_role"] or p["participant_role"],
            }
            for p in participants
        ]

        msg_rows = db.execute("""
            SELECT message_index, sender_email, sender_name, subject,
                   body_text, is_new, is_from_user
            FROM communication_messages
            WHERE communication_id = ?
            ORDER BY message_index
        """, (communication_id,)).fetchall()

        if not msg_rows:
            logger.info("[%s] No email messages to enrich", communication_id[:8])
            return {"entities_found": 0, "topics_found": 0, "total_cost_usd": 0.0}

        att_rows = db.execute("""
            SELECT original_filename, mime_type, file_size_bytes, extracted_text
            FROM communication_artifacts
            WHERE communication_id = ?
        """, (communication_id,)).fetchall()

        user_prompt = _build_email_enrichment_payload(
            communication_id, email_participants,
            [dict(r) for r in msg_rows], [dict(r) for r in att_rows],
        )
    else:
        # Audio path: use transcript segments
        speakers = [
            {
                "label": p["speaker_label"],
                "person_id": p["tracker_person_id"],
                "name": p["proposed_name"] or p["tracker_person_id"] or p["speaker_label"],
            }
            for p in participants
        ]

        rows = db.execute("""
            SELECT id, speaker_label, start_time, end_time, raw_text, cleaned_text, reviewed_text
            FROM transcripts
            WHERE communication_id = ?
            ORDER BY start_time
        """, (communication_id,)).fetchall()

        if not rows:
            logger.info("[%s] No transcript segments to enrich", communication_id[:8])
            return {"entities_found": 0, "topics_found": 0, "total_cost_usd": 0.0}

        segments = [dict(r) for r in rows]

        user_prompt = _build_enrichment_payload(
            communication_id, duration, speakers, segments
        )

    response = await call_llm(
        db=db,
        communication_id=communication_id,
        stage="enriching",
        model=haiku_model,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        max_tokens=4096,
        temperature=0.0,
    )

    # Parse and store
    enrichment = _parse_enrichment_response(response.text)

    if enrichment:
        # For email source, segments list is empty -- pass empty list to _store_enrichment
        _store_enrichment(db, communication_id, enrichment, segments)
    else:
        logger.warning("[%s] Enrichment parse failed — no data stored", communication_id[:8])

    entities = enrichment.get("entities", [])
    topics = enrichment.get("topics", [])
    summary = enrichment.get("summary", "")

    logger.info(
        "[%s] Enrichment complete: %d entities, %d topics, summary=%d chars, $%.4f",
        communication_id[:8], len(entities), len(topics), len(summary),
        response.usage.cost_usd,
    )

    return {
        "entities_found": len(entities),
        "topics_found": len(topics),
        "summary_length": len(summary),
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
        "total_cost_usd": round(response.usage.cost_usd, 6),
    }
