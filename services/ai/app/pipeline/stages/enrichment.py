"""Haiku enrichment stage v2 — context-aware metadata extraction.

Pipeline position: speakers_confirmed → **enriching** → awaiting_association_review

Takes the full cleaned transcript with confirmed speaker identities AND
tracker registries (people, orgs, matters, directives) to produce:
- Summary and topic segments with per-segment intent classification
- Entity mentions with proposed tracker links and implicit reference resolution
- Matter and directive associations
- Intelligence flags for downstream extraction
- Sensitivity flags and quality signals

Unlike cleanup (which batches segments), enrichment sends the full
transcript in a single call since it needs holistic context.
"""

import json
import logging
import uuid

import httpx

from app.config import (
    load_policy,
    PROMPT_BASE_DIR,
    TRACKER_BASE_URL,
    TRACKER_USER,
    TRACKER_PASS,
)
from app.llm.client import call_llm

logger = logging.getLogger(__name__)

PROMPT_DIR = PROMPT_BASE_DIR / "haiku_enrichment"


# ---------------------------------------------------------------------------
# Tracker context fetching (reused from extraction_context)
# ---------------------------------------------------------------------------


async def _fetch_tracker_context() -> dict:
    """Fetch tracker context snapshot for enrichment registries."""
    url = f"{TRACKER_BASE_URL}/ai-context"
    try:
        auth = (TRACKER_USER, TRACKER_PASS) if TRACKER_USER else None
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(url, auth=auth)
            resp.raise_for_status()
            return resp.json()
    except (httpx.HTTPStatusError, httpx.ConnectError, httpx.TimeoutException) as e:
        logger.warning("Tracker context fetch failed for enrichment: %s", e)
        return {}


def _build_compact_registries(tracker_context: dict, policy: dict) -> dict:
    """Build compact registries from full tracker context for enrichment prompt."""
    enrichment_config = policy.get("enrichment", {})
    max_entries = enrichment_config.get("max_registry_entries", 500)

    registries = {}

    if enrichment_config.get("include_people_registry", True):
        people = tracker_context.get("people", [])
        registries["people_registry"] = [
            {
                "id": p.get("id"),
                "name": p.get("full_name", ""),
                "title": p.get("title", ""),
                "organization": p.get("org_name", ""),
            }
            for p in people[:max_entries]
        ]

    if enrichment_config.get("include_orgs_registry", True):
        orgs = tracker_context.get("organizations", [])
        registries["organizations_registry"] = [
            {
                "id": o.get("id"),
                "name": o.get("name", ""),
                "short_name": o.get("short_name", ""),
                "org_type": o.get("organization_type", ""),
            }
            for o in orgs[:max_entries]
        ]

    if enrichment_config.get("include_matters_list", True):
        matters = tracker_context.get("matters", [])
        registries["matters_list"] = [
            {
                "id": m.get("id"),
                "title": m.get("title", ""),
                "matter_type": m.get("matter_type", ""),
                "status": m.get("status", ""),
            }
            for m in matters[:max_entries]
        ]

    if enrichment_config.get("include_directives_list", True):
        directives = tracker_context.get("policy_directives", [])
        registries["directives_list"] = [
            {
                "id": d.get("id"),
                "directive_label": d.get("directive_label", ""),
                "source_document": d.get("source_document", ""),
                "implementation_status": d.get("implementation_status", ""),
            }
            for d in directives[:max_entries]
        ]

    return registries


# ---------------------------------------------------------------------------
# Prompt loading + payload building
# ---------------------------------------------------------------------------


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
    registries: dict,
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
                "text": seg.get("reviewed_text")
                or seg["cleaned_text"]
                or seg["raw_text"],
            }
            for seg in segments
        ],
        **registries,
    }
    return json.dumps(payload, ensure_ascii=False)


def _build_email_enrichment_payload(
    communication_id: str,
    participants: list[dict],
    messages: list[dict],
    attachments: list[dict],
    registries: dict,
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
        **registries,
    }
    return json.dumps(payload, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Response parsing
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Storage — v2 enrichment output
# ---------------------------------------------------------------------------

REVIEWABLE_ENTITY_TYPES = {"person", "organization"}


def _store_enrichment(
    db, communication_id: str, enrichment: dict, segments: list[dict]
):
    """Persist v2 enrichment results to the database.

    Stores:
    - Title on communication
    - Summary + topic segments (with intent) in topic_segments_json
    - Sensitivity flags on communication
    - Intelligence flags in intelligence_flags_json
    - Entity mentions in communication_entities (with proposed tracker links)
    - Matter associations in communication_matter_associations
    - Directive associations in communication_directive_associations
    - Segment metadata on transcript rows
    """
    # 1. Store title, summary, topics (with intent), quality
    title = enrichment.get("title", "")
    summary = enrichment.get("summary", "")
    topics = enrichment.get("topic_segments", enrichment.get("topics", []))
    quality = enrichment.get("quality_signals", {})

    topic_data = json.dumps(
        {
            "summary": summary,
            "topics": topics,
            "quality_signals": quality,
        },
        ensure_ascii=False,
    )

    db.execute(
        """
        UPDATE communications
        SET topic_segments_json = ?,
            title = COALESCE(NULLIF(?, ''), title),
            updated_at = datetime('now')
        WHERE id = ?
    """,
        (topic_data, title, communication_id),
    )

    if title:
        logger.info("[%s] Title set: %s", communication_id[:8], title)

    # 2. Store sensitivity flags
    sensitivity = enrichment.get("sensitivity_flags", {})
    active_flags = [
        flag
        for flag, is_set in sensitivity.items()
        if is_set and isinstance(is_set, bool)
    ]
    if active_flags:
        db.execute(
            """
            UPDATE communications
            SET sensitivity_flags = ?,
                updated_at = datetime('now')
            WHERE id = ?
        """,
            (json.dumps(active_flags), communication_id),
        )
        logger.info("[%s] Sensitivity flags: %s", communication_id[:8], active_flags)

    # 3. Store intelligence flags
    intelligence_flags = enrichment.get("intelligence_flags", [])
    if intelligence_flags:
        db.execute(
            """
            UPDATE communications
            SET intelligence_flags_json = ?,
                updated_at = datetime('now')
            WHERE id = ?
        """,
            (json.dumps(intelligence_flags, ensure_ascii=False), communication_id),
        )
        logger.info(
            "[%s] Intelligence flags: %d stored",
            communication_id[:8],
            len(intelligence_flags),
        )

    # 4. Store entity mentions with proposed tracker links
    entities = enrichment.get("entity_mentions", enrichment.get("entities", []))
    person_count = 0
    org_count = 0
    info_count = 0

    for ent in entities:
        mention_text = ent.get("mention_text", "")
        entity_type = ent.get("entity_type", "unknown")
        if not mention_text:
            continue

        # Determine tracker IDs from proposed match
        tracker_person_id = None
        tracker_org_id = None
        proposed_id = ent.get("proposed_tracker_id")

        if entity_type == "person" and proposed_id:
            tracker_person_id = proposed_id
            person_count += 1
        elif entity_type == "organization" and proposed_id:
            tracker_org_id = proposed_id
            org_count += 1
        elif entity_type not in REVIEWABLE_ENTITY_TYPES:
            info_count += 1

        # Confidence from Haiku (v1 hardcoded 0.8, v2 provides real values)
        confidence = ent.get("confidence", 0.8)

        # Auto-confirm non-reviewable entity types
        confirmed = 0
        if entity_type not in REVIEWABLE_ENTITY_TYPES:
            confirmed = 1  # regulation, legislation, case, concept — skip review

        # Context snippet: use resolution_reasoning if available, fall back to context
        context = ent.get("context_snippet", ent.get("context", ""))
        reasoning = ent.get("resolution_reasoning", "")
        if reasoning and context:
            context = f"{context} | Resolution: {reasoning}"
        elif reasoning:
            context = reasoning

        count = ent.get("mention_count", 1)

        # Find first transcript segment mentioning this entity
        first_transcript_id = None
        mention_lower = mention_text.lower()
        for seg in segments:
            seg_text = (seg.get("cleaned_text") or seg.get("raw_text") or "").lower()
            if mention_lower in seg_text:
                first_transcript_id = seg["id"]
                break

        db.execute(
            """
            INSERT INTO communication_entities
                (id, communication_id, mention_text, entity_type,
                 tracker_person_id, tracker_org_id,
                 proposed_name, proposed_title, proposed_org,
                 confidence, confirmed, mention_count,
                 first_mention_transcript_id, context_snippet)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                str(uuid.uuid4()),
                communication_id,
                mention_text,
                entity_type,
                tracker_person_id,
                tracker_org_id,
                ent.get("proposed_name") or ent.get("proposed_match_name"),
                ent.get("proposed_title"),
                ent.get("proposed_org"),
                confidence,
                confirmed,
                count,
                first_transcript_id,
                context[:500] if context else None,
            ),
        )

    # 5. Store matter associations
    matter_associations = enrichment.get("matter_associations", [])
    for ma in matter_associations:
        matter_id = ma.get("matter_id")
        if not matter_id:
            continue
        db.execute(
            """
            INSERT INTO communication_matter_associations
                (id, communication_id, matter_id, matter_title,
                 confidence, relevant_segments, reasoning,
                 confirmed, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, 0, datetime('now'))
        """,
            (
                str(uuid.uuid4()),
                communication_id,
                matter_id,
                ma.get("matter_title", ""),
                ma.get("confidence", 0.0),
                json.dumps(ma.get("relevant_segments", [])),
                ma.get("reasoning", ""),
            ),
        )

    # 6. Store directive associations
    directive_associations = enrichment.get("directive_associations", [])
    for da in directive_associations:
        directive_id = da.get("directive_id")
        if not directive_id:
            continue
        db.execute(
            """
            INSERT INTO communication_directive_associations
                (id, communication_id, directive_id, directive_label,
                 confidence, relevant_segments, reasoning,
                 confirmed, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, 0, datetime('now'))
        """,
            (
                str(uuid.uuid4()),
                communication_id,
                directive_id,
                da.get("directive_label", ""),
                da.get("confidence", 0.0),
                json.dumps(da.get("relevant_segments", [])),
                da.get("reasoning", ""),
            ),
        )

    # 7. Store segment metadata on transcript rows
    if topics and segments:
        for seg in segments:
            start = seg["start_time"]
            end = seg["end_time"]

            # Find overlapping topics and their intents
            seg_topics = []
            seg_intent = None
            for i, t in enumerate(topics):
                t_start = t.get("start_time", 0)
                t_end = t.get("end_time", 0)
                if t_start < end and t_end > start:
                    seg_topics.append(t.get("topic", ""))
                    if not seg_intent:
                        seg_intent = t.get("intent", "briefing")

            metadata = {
                "topics": seg_topics,
                "intent": seg_intent,
            }

            # Also store in enriched_text for backward compatibility
            db.execute(
                "UPDATE transcripts SET segment_metadata = ?, enriched_text = ? WHERE id = ?",
                (json.dumps(metadata), json.dumps(seg_topics), seg["id"]),
            )

    # db.commit()  # Orchestrator handles commit via savepoint release

    logger.info(
        "[%s] Enrichment v2 stored: summary=%d chars, %d topics, "
        "%d person entities (%d proposed), %d org entities (%d proposed), "
        "%d info entities (auto-confirmed), %d matter assocs, %d directive assocs, "
        "%d intelligence flags",
        communication_id[:8],
        len(summary),
        len(topics),
        sum(1 for e in entities if e.get("entity_type") == "person"),
        person_count,
        sum(1 for e in entities if e.get("entity_type") == "organization"),
        org_count,
        info_count,
        len(matter_associations),
        len(directive_associations),
        len(intelligence_flags),
    )


# ---------------------------------------------------------------------------
# Main stage entry point
# ---------------------------------------------------------------------------


async def run_enrichment_stage(db, communication_id: str) -> dict:
    """Run Haiku enrichment on the full transcript for a communication.

    v2: Fetches tracker context and passes registries to enrichment prompt
    for entity resolution, matter routing, and intelligence flagging.

    Returns summary dict with entity counts and total cost.
    Raises BudgetExceededError if budget is exhausted.
    """
    # Load config
    policy = load_policy()
    model_config = policy.get("model_config", {})
    haiku_model = model_config.get("haiku_model", "claude-haiku-4-5-20251001")
    prompt_version = model_config.get("active_prompt_versions", {}).get(
        "haiku_enrichment", "v2.0.0"
    )

    system_prompt = _load_system_prompt(prompt_version)

    # Fetch tracker context for registries
    tracker_context = await _fetch_tracker_context()
    registries = _build_compact_registries(tracker_context, policy)

    registry_stats = {k: len(v) for k, v in registries.items()}
    logger.info("[%s] Enrichment registries: %s", communication_id[:8], registry_stats)

    # Get communication metadata
    comm = db.execute(
        "SELECT duration_seconds, source_type FROM communications WHERE id = ?",
        (communication_id,),
    ).fetchone()
    duration = comm["duration_seconds"] if comm and comm["duration_seconds"] else 0.0
    source_type = comm["source_type"] if comm else "audio_upload"

    # Get confirmed participants
    participants = db.execute(
        """
        SELECT speaker_label, tracker_person_id, proposed_name,
               participant_email, header_role, participant_role
        FROM communication_participants
        WHERE communication_id = ?
        ORDER BY speaker_label
    """,
        (communication_id,),
    ).fetchall()

    # Branch on source_type for payload construction
    segments = []

    if source_type == "email":
        email_participants = [
            {
                "email": p["participant_email"],
                "person_id": p["tracker_person_id"],
                "name": p["proposed_name"] or p["participant_email"] or "unknown",
                "role": p["header_role"] or p["participant_role"],
            }
            for p in participants
        ]

        msg_rows = db.execute(
            """
            SELECT message_index, sender_email, sender_name, subject,
                   body_text, is_new, is_from_user
            FROM communication_messages
            WHERE communication_id = ?
            ORDER BY message_index
        """,
            (communication_id,),
        ).fetchall()

        if not msg_rows:
            logger.info("[%s] No email messages to enrich", communication_id[:8])
            return {"entities_found": 0, "topics_found": 0, "total_cost_usd": 0.0}

        att_rows = db.execute(
            """
            SELECT original_filename, mime_type, file_size_bytes, extracted_text
            FROM communication_artifacts
            WHERE communication_id = ?
        """,
            (communication_id,),
        ).fetchall()

        user_prompt = _build_email_enrichment_payload(
            communication_id,
            email_participants,
            [dict(r) for r in msg_rows],
            [dict(r) for r in att_rows],
            registries,
        )
    else:
        speakers = [
            {
                "label": p["speaker_label"],
                "person_id": p["tracker_person_id"],
                "name": p["proposed_name"]
                or p["tracker_person_id"]
                or p["speaker_label"],
            }
            for p in participants
        ]

        rows = db.execute(
            """
            SELECT id, speaker_label, start_time, end_time, raw_text, cleaned_text, reviewed_text
            FROM transcripts
            WHERE communication_id = ?
            ORDER BY start_time
        """,
            (communication_id,),
        ).fetchall()

        if not rows:
            logger.info("[%s] No transcript segments to enrich", communication_id[:8])
            return {"entities_found": 0, "topics_found": 0, "total_cost_usd": 0.0}

        segments = [dict(r) for r in rows]

        user_prompt = _build_enrichment_payload(
            communication_id,
            duration,
            speakers,
            segments,
            registries,
        )

    response = await call_llm(
        db=db,
        communication_id=communication_id,
        stage="enriching",
        model=haiku_model,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        max_tokens=64000,
        temperature=0.0,
    )

    # Parse and store
    enrichment = _parse_enrichment_response(response.text)

    # Persist enrichment raw output for debugging

    _enrich_seconds = (
        getattr(response, "_processing_seconds", 0)
        or (response.usage.input_tokens + response.usage.output_tokens) / 100
    )  # estimate
    db.execute(
        """
        INSERT INTO ai_extractions
            (id, communication_id, attempt_number, model_used, prompt_version,
             raw_output, input_tokens, output_tokens, processing_seconds, success)
        VALUES (?, ?, 0, ?, ?, ?, ?, ?, ?, ?)
    """,
        (
            str(uuid.uuid4()),
            communication_id,
            haiku_model,
            f"haiku_enrichment/{prompt_version}",
            response.text,
            response.usage.input_tokens,
            response.usage.output_tokens,
            _enrich_seconds,
            1 if enrichment else 0,
        ),
    )

    if enrichment:
        _store_enrichment(db, communication_id, enrichment, segments)
    else:
        logger.warning(
            "[%s] Enrichment parse failed — no data stored", communication_id[:8]
        )

    entities = enrichment.get("entity_mentions", enrichment.get("entities", []))
    topics = enrichment.get("topic_segments", enrichment.get("topics", []))
    summary = enrichment.get("summary", "")
    matter_assocs = enrichment.get("matter_associations", [])
    directive_assocs = enrichment.get("directive_associations", [])
    intel_flags = enrichment.get("intelligence_flags", [])

    logger.info(
        "[%s] Enrichment complete: %d entities, %d topics, %d matter assocs, "
        "%d directive assocs, %d intel flags, $%.4f",
        communication_id[:8],
        len(entities),
        len(topics),
        len(matter_assocs),
        len(directive_assocs),
        len(intel_flags),
        response.usage.cost_usd,
    )

    return {
        "entities_found": len(entities),
        "topics_found": len(topics),
        "matter_associations": len(matter_assocs),
        "directive_associations": len(directive_assocs),
        "intelligence_flags": len(intel_flags),
        "summary_length": len(summary),
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
        "total_cost_usd": round(response.usage.cost_usd, 6),
    }
