"""Sonnet extraction stage — matter-centered intelligence extraction.

Pipeline position: entities_confirmed → **extracting** → awaiting_bundle_review

Takes confirmed speakers, cleaned transcript, enrichment data, and reviewed
entities. Fetches tracker context, builds a tiered prompt, calls Sonnet 4.6,
then runs a 7-step code post-processing pass before persisting review bundles.

Design contract: Phase 4A.1 revision memo (sections A-H).
"""

import json
import logging
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

import httpx
from pydantic import ValidationError

from app.config import load_policy, TRACKER_BASE_URL, TRACKER_USER, TRACKER_PASS, PROMPT_BASE_DIR
from app.llm.client import call_llm, BudgetExceededError, LLMError

from app.pipeline.stages.extraction_models import (
    ExtractionOutput,
    VALID_BUNDLE_TYPES,
    VALID_ITEM_TYPES,
    POLICY_TOGGLE_MAP,
)

logger = logging.getLogger(__name__)

PROMPT_DIR = PROMPT_BASE_DIR / "extraction"

MAX_EXTRACTION_ATTEMPTS = 3


# ═══════════════════════════════════════════════════════════════════════════
# 1. System prompt loading
# ═══════════════════════════════════════════════════════════════════════════

def _load_system_prompt(version: str) -> str:
    """Load the extraction system prompt for the given version."""
    prompt_path = PROMPT_DIR / f"{version}.md"
    if not prompt_path.exists():
        raise FileNotFoundError(f"Extraction prompt not found: {prompt_path}")
    return prompt_path.read_text(encoding="utf-8")


# ═══════════════════════════════════════════════════════════════════════════
# 2. Tracker context fetching
# ═══════════════════════════════════════════════════════════════════════════

async def _fetch_tracker_context() -> dict:
    """Fetch full tracker context snapshot from GET /tracker/ai-context.

    Returns the full untiered response. Raises on failure.
    """
    url = f"{TRACKER_BASE_URL}/ai-context"
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            auth = (TRACKER_USER, TRACKER_PASS) if TRACKER_USER and TRACKER_PASS else None
            resp = await client.get(url, auth=auth)
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPStatusError as e:
        raise RuntimeError(
            f"Tracker context fetch failed: HTTP {e.response.status_code}"
        ) from e
    except (httpx.ConnectError, httpx.TimeoutException) as e:
        raise RuntimeError(
            f"Tracker context fetch failed: {type(e).__name__}: {e}"
        ) from e


# ═══════════════════════════════════════════════════════════════════════════
# 3. Context tiering (H.1 rules)
# ═══════════════════════════════════════════════════════════════════════════

def _gather_tiering_signals(db, communication_id: str) -> dict:
    """Gather speaker/entity/identifier signals for tiering.

    Returns dict with speaker_person_ids, entity_person_ids,
    entity_org_ids, identifier_hits.
    """
    # Confirmed speaker tracker_person_ids
    speaker_rows = db.execute("""
        SELECT tracker_person_id FROM communication_participants
        WHERE communication_id = ? AND tracker_person_id IS NOT NULL
    """, (communication_id,)).fetchall()
    speaker_person_ids = {r["tracker_person_id"] for r in speaker_rows}

    # Confirmed entity tracker IDs (confirmed=1 or confirmed=0, not -1)
    entity_rows = db.execute("""
        SELECT tracker_person_id, tracker_org_id
        FROM communication_entities
        WHERE communication_id = ? AND confirmed != -1
    """, (communication_id,)).fetchall()
    entity_person_ids = {
        r["tracker_person_id"] for r in entity_rows
        if r["tracker_person_id"]
    }
    entity_org_ids = {
        r["tracker_org_id"] for r in entity_rows
        if r["tracker_org_id"]
    }

    # Identifier hits from enrichment topics and entities
    # (RIN, docket numbers, CFR citations mentioned in conversation)
    identifier_hits = {"rin": set(), "docket": set(), "cfr": set()}
    topic_row = db.execute(
        "SELECT topic_segments_json FROM communications WHERE id = ?",
        (communication_id,),
    ).fetchone()
    if topic_row and topic_row["topic_segments_json"]:
        try:
            topic_data = json.loads(topic_row["topic_segments_json"])
            # Scan topic descriptions and entity mentions for identifiers
            _scan_for_identifiers(
                json.dumps(topic_data, default=str), identifier_hits
            )
        except (json.JSONDecodeError, TypeError):
            pass

    # Also scan entity mention_text and context_snippet
    mention_rows = db.execute("""
        SELECT mention_text, context_snippet FROM communication_entities
        WHERE communication_id = ? AND confirmed != -1
    """, (communication_id,)).fetchall()
    for mr in mention_rows:
        text = (mr["mention_text"] or "") + " " + (mr["context_snippet"] or "")
        _scan_for_identifiers(text, identifier_hits)

    return {
        "speaker_person_ids": speaker_person_ids,
        "entity_person_ids": entity_person_ids,
        "entity_org_ids": entity_org_ids,
        "identifier_hits": identifier_hits,
    }


def _scan_for_identifiers(text: str, hits: dict):
    """Scan text for RIN (XXXX-XXXX), docket numbers, and CFR citations."""
    import re
    # RIN pattern: 4 digits, dash, 2-4 alphanum
    for m in re.finditer(r'\b(\d{4}-[A-Z0-9]{2,4})\b', text):
        hits["rin"].add(m.group(1))
    # Docket pattern
    for m in re.finditer(r'(?i)\bdocket\s*(?:no\.?\s*)?([A-Z0-9-]+)', text):
        hits["docket"].add(m.group(1))
    # CFR pattern: number CFR number
    for m in re.finditer(r'\b(\d+\s*CFR\s*(?:Part\s*)?\d+(?:\.\d+)?)\b', text, re.IGNORECASE):
        hits["cfr"].add(m.group(1))


def _tier_context(full_context: dict, signals: dict) -> dict:
    """Build tiered context from full tracker snapshot and tiering signals.

    Returns a dict with tier_1_matters, tier_2_matters, tier_1_meetings,
    people, organizations, standalone_tasks, and tier_stats.
    """
    sp_ids = signals["speaker_person_ids"]
    ep_ids = signals["entity_person_ids"]
    eo_ids = signals["entity_org_ids"]
    id_hits = signals["identifier_hits"]

    all_person_ids = sp_ids | ep_ids

    matters = full_context.get("matters", [])
    tier_1_matters = []
    tier_1_matter_ids = set()
    tier_2_matters = []

    for m in matters:
        is_tier_1 = False
        mid = m.get("id", "")

        # Speaker/entity is matter owner, supervisor, or next_step owner
        for field in ("assigned_to_person_id", "supervisor_person_id",
                      "next_step_assigned_to_person_id"):
            if m.get(field) in all_person_ids and m.get(field):
                is_tier_1 = True
                break

        # Speaker/entity is matter stakeholder
        if not is_tier_1:
            for stk in m.get("stakeholders", []):
                if stk.get("person_id") in all_person_ids:
                    is_tier_1 = True
                    break

        # Linked entity org is one of the matter's org roles
        if not is_tier_1 and eo_ids:
            for org_field in ("requesting_organization_id",
                              "client_organization_id",
                              "reviewing_organization_id",
                              "lead_external_org_id"):
                if m.get(org_field) in eo_ids:
                    is_tier_1 = True
                    break

        # Linked entity org in matter's organizations list
        if not is_tier_1 and eo_ids:
            for org in m.get("organizations", []):
                if org.get("organization_id") in eo_ids:
                    is_tier_1 = True
                    break

        # RIN match
        if not is_tier_1 and id_hits["rin"]:
            if m.get("rin") and m["rin"] in id_hits["rin"]:
                is_tier_1 = True

        # Docket match
        if not is_tier_1 and id_hits["docket"]:
            if m.get("docket_number") and m["docket_number"] in id_hits["docket"]:
                is_tier_1 = True

        # CFR match (partial — check if matter's cfr_citation contains any hit)
        if not is_tier_1 and id_hits["cfr"]:
            m_cfr = (m.get("cfr_citation") or "").lower()
            for cfr_hit in id_hits["cfr"]:
                if cfr_hit.lower() in m_cfr or m_cfr in cfr_hit.lower():
                    is_tier_1 = True
                    break

        if is_tier_1:
            tier_1_matters.append(m)
            tier_1_matter_ids.add(mid)
        else:
            # Build compact Tier 2 summary
            deadlines = [
                m.get(d) for d in
                ("work_deadline", "decision_deadline", "external_deadline")
                if m.get(d)
            ]
            nearest = min(deadlines) if deadlines else None
            tier_2_matters.append({
                "id": mid,
                "title": m.get("title", ""),
                "matter_type": m.get("matter_type", ""),
                "status": m.get("status", ""),
                "priority": m.get("priority", ""),
                "owner_name": m.get("owner_name", ""),
                "rin": m.get("rin"),
                "docket_number": m.get("docket_number"),
                "nearest_deadline": nearest,
                "tags": m.get("tags", []),
            })

    # Tier 1 meetings: involving speakers or linked to Tier 1 matters
    meetings = full_context.get("recent_meetings", [])
    tier_1_meetings = []
    for mtg in meetings:
        participants = mtg.get("participants", [])
        # We can't directly match person_ids from the meeting data since
        # ai-context returns full_name and meeting_role, not person_id
        # But meeting_matters gives us matter links
        matter_links = mtg.get("matter_links", [])
        if any(ml.get("matter_id") in tier_1_matter_ids for ml in matter_links):
            tier_1_meetings.append(mtg)
        # If we have speaker names, do a name match as best-effort
        # (person_ids aren't in the meeting participant data from ai-context)

    # People and orgs: always Tier 3 (full registry, already compact)
    people = full_context.get("people", [])
    orgs = full_context.get("organizations", [])
    standalone_tasks = full_context.get("standalone_tasks", [])

    tier_stats = {
        "tier_1_matter_count": len(tier_1_matters),
        "tier_2_matter_count": len(tier_2_matters),
        "tier_1_meeting_count": len(tier_1_meetings),
        "people_count": len(people),
        "org_count": len(orgs),
    }

    if len(tier_1_matters) > 30:
        logger.warning(
            "Tier 1 has %d matters (>30) — keeping all, conversation "
            "involves many connected workstreams",
            len(tier_1_matters),
        )

    return {
        "tier_1_matters": tier_1_matters,
        "tier_2_matters": tier_2_matters,
        "tier_1_meetings": tier_1_meetings,
        "people": people,
        "organizations": orgs,
        "standalone_tasks": standalone_tasks,
        "tier_stats": tier_stats,
    }


# ═══════════════════════════════════════════════════════════════════════════
# 4. User prompt construction
# ═══════════════════════════════════════════════════════════════════════════

def _build_user_prompt(
    db,
    communication_id: str,
    tiered_context: dict,
    policy: dict,
) -> str:
    """Build the complete user prompt for extraction."""
    sections = []

    # ── Communication data ──
    comm = db.execute("""
        SELECT id, source_type, original_filename, duration_seconds,
               topic_segments_json, sensitivity_flags, created_at
        FROM communications WHERE id = ?
    """, (communication_id,)).fetchone()

    # Get the best date for when this conversation actually occurred:
    # 1. Try to parse a date from the title/filename (e.g. "03-20 Meeting_..." or "2026-03-20...")
    # 2. captured_at from audio file metadata (embedded by recording device)
    # 3. Fall back to communications.created_at (DB insertion time)
    # Then convert from UTC to local timezone for correct relative date resolution.
    import re as _re
    title_date = None
    title_or_fn = comm["original_filename"] or ""
    # Also check the communication title
    title_row = db.execute("SELECT title FROM communications WHERE id = ?", (communication_id,)).fetchone()
    if title_row and title_row["title"]:
        title_or_fn = title_row["title"] + " " + title_or_fn
    # Try ISO date: 2026-03-20
    iso_match = _re.search(r"(20\d{2})-(\d{2})-(\d{2})", title_or_fn)
    if iso_match:
        title_date = f"{iso_match.group(1)}-{iso_match.group(2)}-{iso_match.group(3)}"
    else:
        # Try MM-DD pattern at start of title: "03-20 Meeting..."
        mmdd_match = _re.search(r"\b(\d{2})-(\d{2})\b", title_or_fn)
        if mmdd_match:
            from datetime import datetime as _dt2
            mm, dd = int(mmdd_match.group(1)), int(mmdd_match.group(2))
            if 1 <= mm <= 12 and 1 <= dd <= 31:
                year = _dt2.now().year
                title_date = f"{year}-{mm:02d}-{dd:02d}"

    captured_row = db.execute("""
        SELECT captured_at FROM audio_files
        WHERE communication_id = ? AND format != 'wav_normalized'
              AND captured_at IS NOT NULL
        LIMIT 1
    """, (communication_id,)).fetchone()
    raw_date = (
        title_date
        or (captured_row["captured_at"] if captured_row else None)
        or comm["created_at"]
    )
    # Convert UTC timestamp to local date
    from datetime import datetime as _dt, timezone as _tz
    from zoneinfo import ZoneInfo
    from app.config import LOCAL_TIMEZONE
    try:
        utc_dt = _dt.fromisoformat(raw_date.replace("Z", "+00:00"))
        if utc_dt.tzinfo is None:
            utc_dt = utc_dt.replace(tzinfo=_tz.utc)
        local_dt = utc_dt.astimezone(ZoneInfo(LOCAL_TIMEZONE))
        conversation_date = local_dt.strftime("%Y-%m-%d")
    except Exception:
        conversation_date = raw_date[:10] if raw_date else "unknown"

    sections.append("## Communication Data\n")
    source_type = comm["source_type"] or "audio_upload"

    sections.append(f"Communication ID: {communication_id}")
    sections.append(f"Source Type: {source_type}")
    sections.append(f"This conversation occurred on: {conversation_date}. Use this as the reference date for resolving all relative time expressions (e.g. 'tomorrow', 'next week', 'end of day').")
    if source_type != "email":
        sections.append(f"Duration: {comm['duration_seconds'] or 0} seconds")
    sections.append(f"Original Filename: {comm['original_filename'] or 'unknown'}")

    # Participants
    participants = db.execute("""
        SELECT speaker_label, tracker_person_id, proposed_name,
               proposed_title, proposed_org, participant_email,
               header_role, participant_role
        FROM communication_participants
        WHERE communication_id = ?
        ORDER BY speaker_label
    """, (communication_id,)).fetchall()

    if source_type == "email":
        participant_data = []
        for p in participants:
            participant_data.append({
                "email": p["participant_email"],
                "tracker_person_id": p["tracker_person_id"],
                "name": p["proposed_name"] or p["participant_email"],
                "title": p["proposed_title"],
                "org": p["proposed_org"],
                "role": p["header_role"] or p["participant_role"],
            })
        sections.append(f"\n### Participants (confirmed)\n```json\n{json.dumps(participant_data, indent=2)}\n```")
    else:
        speaker_data = []
        for p in participants:
            speaker_data.append({
                "label": p["speaker_label"],
                "tracker_person_id": p["tracker_person_id"],
                "name": p["proposed_name"] or p["speaker_label"],
                "title": p["proposed_title"],
                "org": p["proposed_org"],
            })
        sections.append(f"\n### Speakers (confirmed)\n```json\n{json.dumps(speaker_data, indent=2)}\n```")

    # Enrichment summary
    summary = None
    topics = []
    if comm["topic_segments_json"]:
        try:
            td = json.loads(comm["topic_segments_json"])
            summary = td.get("summary")
            topics = td.get("topics", [])
        except (json.JSONDecodeError, TypeError):
            pass

    if summary:
        sections.append(f"\n### Enrichment Summary\n{summary}")
    if topics:
        sections.append(f"\n### Topics\n```json\n{json.dumps(topics, indent=2)}\n```")

    # Confirmed entities
    entity_rows = db.execute("""
        SELECT mention_text, entity_type, tracker_person_id, tracker_org_id,
               proposed_name, confidence, confirmed, mention_count,
               context_snippet
        FROM communication_entities
        WHERE communication_id = ? AND confirmed != -1
        ORDER BY mention_count DESC
    """, (communication_id,)).fetchall()

    if entity_rows:
        entities = [dict(r) for r in entity_rows]
        sections.append(f"\n### Confirmed Entities\n```json\n{json.dumps(entities, indent=2, default=str)}\n```")

    # Sensitivity flags
    if comm["sensitivity_flags"]:
        sections.append(f"\n### Sensitivity Flags\n{comm['sensitivity_flags']}")

    # Full content: email messages or audio transcript
    if source_type == "email":
        # Email: include messages, attachments
        msg_rows = db.execute("""
            SELECT id, message_index, sender_email, sender_name,
                   recipient_emails, cc_emails, subject, body_text,
                   is_new, is_from_user, timestamp
            FROM communication_messages
            WHERE communication_id = ?
            ORDER BY message_index
        """, (communication_id,)).fetchall()

        # Build participant name lookup by email
        participant_names = {
            p["participant_email"]: (p["proposed_name"] or p["participant_email"])
            for p in participants
            if p["participant_email"]
        }

        message_data = []
        for msg in msg_rows:
            message_data.append({
                "message_id": msg["id"],
                "message_index": msg["message_index"],
                "sender_email": msg["sender_email"],
                "sender_name": participant_names.get(
                    msg["sender_email"], msg["sender_name"] or msg["sender_email"]
                ),
                "subject": msg["subject"],
                "body_text": msg["body_text"],
                "is_new": msg["is_new"],
                "is_from_user": msg["is_from_user"],
                "timestamp": msg["timestamp"],
            })
        sections.append(f"\n### Email Thread\n```json\n{json.dumps(message_data, indent=2)}\n```")

        # Include attachment summaries
        att_rows = db.execute("""
            SELECT original_filename, mime_type, file_size_bytes,
                   extracted_text, text_extraction_status
            FROM communication_artifacts
            WHERE communication_id = ?
        """, (communication_id,)).fetchall()

        if att_rows:
            att_data = []
            for att in att_rows:
                entry = {
                    "filename": att["original_filename"],
                    "mime_type": att["mime_type"],
                    "size_bytes": att["file_size_bytes"],
                    "extraction_status": att["text_extraction_status"],
                }
                if att["extracted_text"]:
                    entry["extracted_text_preview"] = att["extracted_text"][:3000]
                att_data.append(entry)
            sections.append(f"\n### Attachments\n```json\n{json.dumps(att_data, indent=2)}\n```")
    else:
        # Audio: include transcript segments
        segments = db.execute("""
            SELECT id, speaker_label, start_time, end_time,
                   cleaned_text, raw_text, reviewed_text
            FROM transcripts
            WHERE communication_id = ?
            ORDER BY start_time
        """, (communication_id,)).fetchall()

        # Build speaker name lookup
        speaker_names = {
            p["speaker_label"]: (p["proposed_name"] or p["speaker_label"])
            for p in participants
        }

        transcript_data = []
        for seg in segments:
            transcript_data.append({
                "segment_id": seg["id"],
                "speaker": seg["speaker_label"],
                "speaker_name": speaker_names.get(seg["speaker_label"], seg["speaker_label"]),
                "start": seg["start_time"],
                "end": seg["end_time"],
                "text": (seg["reviewed_text"] or seg["cleaned_text"] or seg["raw_text"] or ""),
            })
        sections.append(f"\n### Full Transcript\n```json\n{json.dumps(transcript_data, indent=2)}\n```")

    # ── Extraction policy (tell model what's disabled) ──
    extraction_policy = policy.get("extraction_policy", {})
    disabled_types = []
    for toggle, item_type in POLICY_TOGGLE_MAP.items():
        if not extraction_policy.get(toggle, True):
            disabled_types.append(item_type)

    if disabled_types:
        sections.append(
            "\n## Extraction Policy (current)\n"
            "The following proposal types are DISABLED. You should still "
            "reason about them and note observations in "
            "suppressed_observations, but do NOT include them in "
            "bundles[].items[]:\n"
            + "\n".join(f"- {t}" for t in disabled_types)
        )

    # ── Tiered tracker context ──
    sections.append("\n## Tracker Context\n")

    t1 = tiered_context["tier_1_matters"]
    t2 = tiered_context["tier_2_matters"]

    if t1:
        sections.append(
            f"### Priority Matters ({len(t1)} — full detail, likely relevant)\n"
            f"```json\n{json.dumps(t1, indent=2, default=str)}\n```"
        )
    else:
        sections.append(
            "### Priority Matters\nNo matters were pre-identified as relevant "
            "to this conversation's speakers or entities. Scan all matters "
            "below for topical relevance.\n"
        )

    if t2:
        sections.append(
            f"\n### Other Open Matters ({len(t2)} — summary, check for unexpected relevance)\n"
            f"```json\n{json.dumps(t2, indent=2, default=str)}\n```"
        )

    if tiered_context["tier_1_meetings"]:
        sections.append(
            f"\n### Recent Meetings ({len(tiered_context['tier_1_meetings'])})\n"
            f"```json\n{json.dumps(tiered_context['tier_1_meetings'], indent=2, default=str)}\n```"
        )

    sections.append(
        f"\n### People Registry ({len(tiered_context['people'])})\n"
        f"```json\n{json.dumps(tiered_context['people'], indent=2, default=str)}\n```"
    )
    sections.append(
        f"\n### Organizations Registry ({len(tiered_context['organizations'])})\n"
        f"```json\n{json.dumps(tiered_context['organizations'], indent=2, default=str)}\n```"
    )

    if tiered_context["standalone_tasks"]:
        sections.append(
            f"\n### Standalone Tasks ({len(tiered_context['standalone_tasks'])})\n"
            f"```json\n{json.dumps(tiered_context['standalone_tasks'], indent=2, default=str)}\n```"
        )

    # ── Final instruction ──
    if source_type == "email":
        sections.append(
            "\n## Instructions\n\n"
            "Analyze this email thread and extract actionable operational "
            "intelligence. Organize proposals into bundles grouped by the matter "
            "each set relates to. Follow all rules in your system prompt. "
            "Prefer fewer, higher-quality proposals. "
            "For source locators, use message_index and paragraph number "
            "instead of time-based references."
        )
    else:
        sections.append(
            "\n## Instructions\n\n"
            "Analyze this conversation and extract actionable operational "
            "intelligence. Organize proposals into bundles grouped by the matter "
            "each set relates to. Follow all rules in your system prompt. "
            "Prefer fewer, higher-quality proposals."
        )

    return "\n".join(sections)


# ═══════════════════════════════════════════════════════════════════════════
# 5. Response parsing
# ═══════════════════════════════════════════════════════════════════════════

def _parse_extraction_response(text: str) -> dict:
    """Parse extraction response, tolerating markdown fencing."""
    import logging as _log
    _log.getLogger(__name__).info("Raw LLM response (first 500 chars): %s", repr(text[:500]))
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines)

    return json.loads(cleaned)


# ═══════════════════════════════════════════════════════════════════════════
# 6. Post-processing (7-step pass)
# ═══════════════════════════════════════════════════════════════════════════

def _post_process(
    extraction: ExtractionOutput,
    full_context: dict,
    policy: dict,
    db,
    communication_id: str,
) -> dict:
    """Run the 7-step deterministic post-processing pass.

    Returns a dict with:
        bundles: list of validated bundles (ready for DB insert)
        post_processing_log: audit metadata
    """
    log = {
        "code_suppressed_items": [],
        "dedup_warnings": [],
        "invalid_references_cleaned": [],
        "tier_1_matter_count": 0,
        "tier_2_matter_count": 0,
        "token_truncation_occurred": False,
    }

    # Build lookup sets from full context for validation
    valid_person_ids = {p["id"] for p in full_context.get("people", [])}
    valid_org_ids = {o["id"] for o in full_context.get("organizations", [])}
    valid_matter_ids = {m["id"] for m in full_context.get("matters", [])}

    extraction_policy = policy.get("extraction_policy", {})
    routing_policy = policy.get("routing_policy", {})

    # Determine which item types are disabled
    disabled_types = set()
    for toggle, item_type in POLICY_TOGGLE_MAP.items():
        if not extraction_policy.get(toggle, True):
            disabled_types.add(item_type)

    # Track bundles for output
    processed_bundles = []

    for bundle in extraction.bundles:
        # ── Step 2: Validate entity references ──
        if bundle.target_matter_id and bundle.target_matter_id not in valid_matter_ids:
            log["invalid_references_cleaned"].append({
                "type": "matter_id",
                "value": bundle.target_matter_id,
                "bundle_title": bundle.target_matter_title,
            })
            logger.warning(
                "[%s] Invalid target_matter_id %s — clearing",
                communication_id[:8], bundle.target_matter_id,
            )
            bundle.target_matter_id = None
            bundle.bundle_type = "standalone"

        # Validate references inside items
        valid_items = []
        for item in bundle.items:
            pd = item.proposed_data
            cleaned_refs = False

            # Check person_id references
            for field in ("assigned_to_person_id", "person_id",
                          "decision_assigned_to_person_id",
                          "waiting_on_person_id"):
                val = pd.get(field)
                if val and val not in valid_person_ids:
                    log["invalid_references_cleaned"].append({
                        "type": field, "value": val,
                        "item_type": item.item_type,
                    })
                    pd[field] = None
                    cleaned_refs = True

            # Check org_id references
            for field in ("organization_id", "waiting_on_org_id",
                          "requesting_organization_id"):
                val = pd.get(field)
                if val and val not in valid_org_ids:
                    log["invalid_references_cleaned"].append({
                        "type": field, "value": val,
                        "item_type": item.item_type,
                    })
                    pd[field] = None
                    cleaned_refs = True

            # Check matter_id references in proposed_data
            for field in ("matter_id",):
                val = pd.get(field)
                if val and val not in valid_matter_ids:
                    log["invalid_references_cleaned"].append({
                        "type": field, "value": val,
                        "item_type": item.item_type,
                    })
                    pd[field] = None
                    cleaned_refs = True

            # Check participants in meeting_record
            if item.item_type == "meeting_record":
                for part in pd.get("participants", []):
                    pid = part.get("person_id")
                    if pid and pid not in valid_person_ids:
                        log["invalid_references_cleaned"].append({
                            "type": "meeting_participant.person_id",
                            "value": pid,
                        })
                        part["person_id"] = None
                for ml in pd.get("matter_links", []):
                    mid = ml.get("matter_id")
                    if mid and mid not in valid_matter_ids:
                        log["invalid_references_cleaned"].append({
                            "type": "meeting_link.matter_id",
                            "value": mid,
                        })
                        ml["matter_id"] = None

            if cleaned_refs:
                item.rationale += " [Note: some references were cleaned by post-processing.]"

            # ── Step 2b: Context note linked_entities validation ──
            if item.item_type == "context_note":
                linked_entities = pd.get("linked_entities", [])
                valid_linked = []
                for le in linked_entities:
                    etype = le.get("entity_type")
                    eid = le.get("entity_id")
                    valid = False
                    if etype == "person" and eid in valid_person_ids:
                        valid = True
                    elif etype == "organization" and eid in valid_org_ids:
                        valid = True
                    elif etype == "matter" and eid in valid_matter_ids:
                        valid = True
                    elif etype in ("meeting", "task", "document", "decision"):
                        valid = True  # Cannot validate these without extra queries
                    if valid:
                        valid_linked.append(le)
                    else:
                        log["invalid_references_cleaned"].append({
                            "type": f"linked_entity.{etype}",
                            "value": eid,
                            "item_type": "context_note",
                        })
                pd["linked_entities"] = valid_linked
                if not valid_linked and linked_entities:
                    item.rationale += " [Note: all linked entities had invalid IDs — note is unlinked.]"

                # Attribution enforcement
                posture = pd.get("posture", "factual")
                speaker = pd.get("speaker_attribution")
                if posture == "attributed_view" and not speaker:
                    item.rationale += " [WARNING: attributed_view without speaker_attribution — downgraded to tentative.]"
                    pd["posture"] = "tentative"
                if posture == "sensitive" and not speaker and not item.primary_excerpt:
                    pd["automation_hold"] = 1
                    item.rationale += " [Hold: sensitive note without speaker attribution or source excerpt.]"

            # ── Step 2c: Person detail update validation ──
            if item.item_type == "person_detail_update":
                target_person_id = pd.get("person_id")
                if target_person_id and target_person_id not in valid_person_ids:
                    # Downgrade to unlinked context_note
                    log["invalid_references_cleaned"].append({
                        "type": "person_detail_update.person_id",
                        "value": target_person_id,
                        "item_type": "person_detail_update",
                        "action": "downgraded_to_context_note",
                    })
                    item.item_type = "context_note"
                    fields = pd.get("fields", {})
                    person_name = pd.get("person_name", "unknown")
                    field_desc = ", ".join(f"{k}={v}" for k, v in fields.items())
                    pd.clear()
                    pd["title"] = f"Profile info for {person_name} (unverified person)"
                    pd["body"] = f"Extracted profile fields: {field_desc}. Person ID could not be verified."
                    pd["category"] = "people_insight"
                    pd["posture"] = "tentative"
                    pd["durability"] = "durable"
                    pd["sensitivity"] = "low"
                    item.rationale += " [Downgraded from person_detail_update: invalid person_id.]"

                # Confidence enforcement
                elif item.confidence < 0.70:
                    log["code_suppressed_items"].append({
                        "item_type": "person_detail_update",
                        "reason": f"confidence {item.confidence:.2f} < 0.70 threshold",
                        "person_id": target_person_id,
                        "fields": list(pd.get("fields", {}).keys()),
                    })
                    continue  # Skip this item
                elif item.confidence < 0.85:
                    pd["automation_hold"] = 1
                    item.rationale += f" [Hold: confidence {item.confidence:.2f} is below 0.85 threshold.]"

            # ── Step 3: Apply extraction_policy suppression ──
            if item.item_type in disabled_types:
                log["code_suppressed_items"].append({
                    "item_type": item.item_type,
                    "reason": f"propose_{item.item_type}s disabled in extraction_policy"
                              if item.item_type != "follow_up"
                              else "propose_follow_ups disabled in extraction_policy",
                    "confidence": item.confidence,
                    "source_excerpt": item.source_excerpt[:200],
                })
                continue  # Skip this item

            valid_items.append(item)

        # ── Step 3 (continued): Suppress new_matter bundles if disabled ──
        if bundle.bundle_type == "new_matter" and "new_matter" not in disabled_types:
            # new_matter bundle type needs propose_new_matters enabled
            pass  # It's enabled, proceed
        elif bundle.bundle_type == "new_matter":
            # new_matters disabled — redistribute items to standalone
            log["code_suppressed_items"].append({
                "item_type": "new_matter",
                "reason": "propose_new_matters disabled in extraction_policy",
                "items_redistributed_to": "standalone",
                "proposed_matter_title": bundle.target_matter_title,
            })
            bundle.bundle_type = "standalone"
            bundle.proposed_matter = None
            bundle.target_matter_id = None

        bundle.items = valid_items

        # Skip empty bundles
        if not valid_items:
            continue

        # ── Step 4: Apply routing_policy filters ──
        min_confidence = routing_policy.get("match_confidence_minimum", 0.7)
        if (bundle.bundle_type == "matter"
                and bundle.confidence < min_confidence
                and bundle.target_matter_id):
            logger.info(
                "[%s] Bundle confidence %.2f < threshold %.2f — "
                "demoting to standalone",
                communication_id[:8], bundle.confidence, min_confidence,
            )
            bundle.bundle_type = "standalone"
            bundle.target_matter_id = None

        if (bundle.bundle_type == "standalone"
                and not routing_policy.get("standalone_items_enabled", True)):
            log["code_suppressed_items"].append({
                "item_type": "standalone_bundle",
                "reason": "standalone_items_enabled is false",
            })
            continue

        processed_bundles.append(bundle)

    # ── Step 4 (continued): Cap new_matter bundles ──
    max_new = routing_policy.get("max_new_matters_per_communication", 5)
    new_matter_bundles = [b for b in processed_bundles if b.bundle_type == "new_matter"]
    if len(new_matter_bundles) > max_new:
        # Keep highest confidence, suppress the rest
        sorted_new = sorted(new_matter_bundles, key=lambda b: b.confidence, reverse=True)
        for excess in sorted_new[max_new:]:
            log["code_suppressed_items"].append({
                "item_type": "new_matter",
                "reason": f"Exceeds max_new_matters_per_communication ({max_new})",
                "proposed_matter_title": excess.target_matter_title,
            })
            processed_bundles.remove(excess)

    # ── Step 5: Deduplication warnings ──
    for bundle in processed_bundles:
        if not bundle.target_matter_id:
            continue

        # Check for duplicate tasks against existing open_tasks
        matter_ctx = None
        for m in full_context.get("matters", []):
            if m.get("id") == bundle.target_matter_id:
                matter_ctx = m
                break

        if not matter_ctx:
            continue

        existing_tasks = matter_ctx.get("open_tasks", [])
        existing_updates = matter_ctx.get("recent_updates", [])
        existing_stakeholders = [
            s.get("full_name", "").lower()
            for s in matter_ctx.get("stakeholders", [])
        ]

        for item in bundle.items:
            if item.item_type in ("task", "follow_up") and existing_tasks:
                item_title = item.proposed_data.get("title", "").lower()
                for et in existing_tasks:
                    if _fuzzy_title_match(item_title, et.get("title", "").lower()):
                        log["dedup_warnings"].append({
                            "item_type": item.item_type,
                            "proposed_title": item.proposed_data.get("title"),
                            "existing_title": et.get("title"),
                            "matter_id": bundle.target_matter_id,
                        })
                        item.rationale += (
                            f" [DEDUP WARNING: similar to existing task "
                            f"'{et.get('title')}']"
                        )
                        break

            elif item.item_type == "matter_update" and existing_updates:
                item_summary = item.proposed_data.get("summary", "").lower()
                for eu in existing_updates:
                    if _fuzzy_title_match(item_summary[:80], eu.get("summary", "").lower()[:80]):
                        log["dedup_warnings"].append({
                            "item_type": "matter_update",
                            "proposed_summary": item.proposed_data.get("summary", "")[:100],
                            "existing_summary": eu.get("summary", "")[:100],
                        })
                        item.rationale += " [DEDUP WARNING: similar to recent update]"
                        break

            elif item.item_type == "stakeholder_addition":
                person_name = item.proposed_data.get("person_name", "").lower()
                if person_name and person_name in existing_stakeholders:
                    log["code_suppressed_items"].append({
                        "item_type": "stakeholder_addition",
                        "reason": f"Person '{person_name}' already a stakeholder",
                    })
                    bundle.items.remove(item)

    # Remove bundles that became empty after dedup suppression
    processed_bundles = [b for b in processed_bundles if b.items]

    return {
        "bundles": processed_bundles,
        "post_processing_log": log,
    }


def _fuzzy_title_match(a: str, b: str) -> bool:
    """Simple fuzzy match: >60% word overlap."""
    if not a or not b:
        return False
    words_a = set(a.split())
    words_b = set(b.split())
    if not words_a or not words_b:
        return False
    overlap = len(words_a & words_b)
    shorter = min(len(words_a), len(words_b))
    return overlap / shorter > 0.6 if shorter > 0 else False


# ═══════════════════════════════════════════════════════════════════════════
# 7. Persistence: Store extraction + review bundles
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
        ent_rows = db.execute("""
            SELECT id, mention_text FROM communication_entities
            WHERE communication_id = ? AND confirmed != -1
        """, (communication_id,)).fetchall()
        for er in ent_rows:
            if er["mention_text"] and er["mention_text"].lower() in excerpt_lower:
                entity_refs.append(er["id"])

    if source_type == "email":
        # Email source locator: message_index based
        # Try to find the message that contains the excerpt
        message_index = None
        message_id = None
        if item.source_excerpt:
            msg_rows = db.execute("""
                SELECT id, message_index, body_text
                FROM communication_messages
                WHERE communication_id = ?
                ORDER BY message_index
            """, (communication_id,)).fetchall()
            for mr in msg_rows:
                if item.source_excerpt[:100].lower() in (mr["body_text"] or "").lower():
                    message_index = mr["message_index"]
                    message_id = mr["id"]
                    break

        evidence_list = item.get_evidence_list()

        return {
            "type": "email",
            "message_index": message_index,
            "message_id": message_id,
            "excerpt": item.primary_excerpt,
            "evidence": evidence_list,
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
                if time_range and t_start < time_range.end and t_end > time_range.start:
                    enrichment_topic = t.get("topic")
                    break
        except (json.JSONDecodeError, TypeError):
            pass

    # Build evidence array from all source_evidence pieces
    evidence_list = item.get_evidence_list()

    return {
        "type": "transcript",
        "segments": item.primary_segments,
        "time_range": {
            "start_seconds": item.primary_time_range.start if item.primary_time_range else (time_range.start if time_range else 0),
            "end_seconds": item.primary_time_range.end if item.primary_time_range else (time_range.end if time_range else 0),
        },
        "speaker_label": speaker_label,
        "speaker_name": speaker_name,
        "excerpt": item.primary_excerpt,
        "evidence": evidence_list,
        "entity_refs": entity_refs,
        "enrichment_topic": enrichment_topic,
    }


def _update_communication_title(db, communication_id: str, bundles: list):
    """Update the communication title from extracted meeting_record if the current
    title is generic (e.g., 'Test audio 3', UUID-like, or just a filename).
    
    Priority: first meeting_record title found, falling back to first bundle
    target_matter_title prefixed with 'Discussion: '.
    """
    current = db.execute(
        "SELECT title, original_filename FROM communications WHERE id = ?",
        (communication_id,),
    ).fetchone()
    if not current:
        return

    cur_title = (current["title"] or "").strip()
    orig_name = (current["original_filename"] or "").strip()

    # Heuristic: title is "generic" if it matches the filename, looks like a UUID,
    # starts with "Test audio", or is very short / empty
    import re
    is_generic = (
        not cur_title
        or cur_title == orig_name
        or cur_title.lower().startswith("test audio")
        or bool(re.match(r"^[0-9a-f]{8}-", cur_title))
        or len(cur_title) < 3
    )
    if not is_generic:
        return

    # Look for the best title from extraction results
    new_title = None
    for b in bundles:
        for item in b.items:
            if item.item_type == "meeting_record" and item.proposed_data.get("title"):
                new_title = item.proposed_data["title"]
                break
        if new_title:
            break

    # Fallback: use matter title from first matter-linked bundle
    if not new_title:
        for b in bundles:
            if b.target_matter_title:
                new_title = f"Discussion: {b.target_matter_title}"
                break

    if new_title and new_title != cur_title:
        db.execute(
            "UPDATE communications SET title = ?, updated_at = datetime('now') WHERE id = ?",
            (new_title, communication_id),
        )
        logger.info(
            "[%s] Communication title updated: '%s' -> '%s'",
            communication_id[:8], cur_title, new_title,
        )


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
    db.execute("""
        INSERT INTO ai_extractions
            (id, communication_id, attempt_number, model_used, prompt_version,
             system_prompt, user_prompt, raw_output, input_tokens, output_tokens,
             processing_seconds, tracker_context_snapshot,
             escalation_reason, success)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        extraction_id, communication_id, attempt_number,
        model_used, prompt_version,
        system_prompt, user_prompt, enriched_raw,
        usage_data.get("input_tokens", 0),
        usage_data.get("output_tokens", 0),
        usage_data.get("processing_seconds", 0),
        full_context_json,
        escalation_reason,
        1 if success else 0,
    ))

    # Insert review bundles and items
    bundles = processed["bundles"]
    for sort_idx, bundle in enumerate(bundles):
        bundle_id = str(uuid.uuid4())

        db.execute("""
            INSERT INTO review_bundles
                (id, communication_id, bundle_type, target_matter_id,
                 target_matter_title, proposed_matter_json, status,
                 confidence, rationale, intelligence_notes, sort_order)
            VALUES (?, ?, ?, ?, ?, ?, 'proposed', ?, ?, ?, ?)
        """, (
            bundle_id, communication_id, bundle.bundle_type,
            bundle.target_matter_id, bundle.target_matter_title,
            json.dumps(bundle.proposed_matter, default=str) if bundle.proposed_matter else None,
            bundle.confidence, bundle.rationale,
            bundle.intelligence_notes, sort_idx,
        ))

        for item_idx, item in enumerate(bundle.items):
            item_id = str(uuid.uuid4())
            source_locator = _build_source_locator(db, item, communication_id)

            db.execute("""
                INSERT INTO review_bundle_items
                    (id, bundle_id, item_type, status, proposed_data,
                     confidence, rationale, source_excerpt,
                     source_transcript_id, source_start_time, source_end_time,
                     source_locator_json, sort_order)
                VALUES (?, ?, ?, 'proposed', ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                item_id, bundle_id, item.item_type,
                json.dumps(item.proposed_data, ensure_ascii=False, default=str),
                item.confidence, item.rationale,
                item.primary_excerpt,
                item.primary_segments[0] if item.primary_segments else None,
                item.primary_time_range.start if item.primary_time_range else None,
                item.primary_time_range.end if item.primary_time_range else None,
                json.dumps(source_locator, ensure_ascii=False, default=str),
                item_idx,
            ))

    # Update communication title from meeting_record if current title is generic
    _update_communication_title(db, communication_id, bundles)

    db.commit()

    logger.info(
        "[%s] Extraction persisted: %d bundles, extraction_id=%s",
        communication_id[:8], len(bundles), extraction_id[:8],
    )
    return extraction_id


# ═══════════════════════════════════════════════════════════════════════════
# 8. Sonnet extraction with retry (internal helper)
# ═══════════════════════════════════════════════════════════════════════════

MAX_SONNET_ATTEMPTS = 3   # Sonnet self-correction retries (parse/validation)

async def _run_sonnet_extraction(
    db,
    communication_id: str,
    sonnet_model: str,
    system_prompt: str,
    user_prompt: str,
    full_context: dict,
    full_context_json: str,
    policy: dict,
    prompt_version: str,
) -> "ExtractionAttemptResult":
    """Run Sonnet extraction with up to MAX_SONNET_ATTEMPTS retries on
    parse/validation failures.

    Returns ExtractionAttemptResult (success or final failure).
    Raises BudgetExceededError (let orchestrator handle).
    """
    from app.pipeline.stages.escalation import (
        ExtractionAttemptResult, ExtractionFailureType,
    )

    last_error = None
    last_raw_output = None
    total_cost = 0.0

    for attempt in range(1, MAX_SONNET_ATTEMPTS + 1):
        try:
            prompt_for_attempt = user_prompt if attempt == 1 else (
                user_prompt + f"\n\n## Retry Note\n"
                f"Previous attempt failed to produce valid JSON. "
                f"Error: {last_error}\nReturn ONLY the JSON object."
            )

            response = await call_llm(
                db=db,
                communication_id=communication_id,
                stage="extracting",
                model=sonnet_model,
                system_prompt=system_prompt,
                user_prompt=prompt_for_attempt,
                max_tokens=16384,
                temperature=0.0,
            )
            total_cost += response.usage.cost_usd
            last_raw_output = response.text

            # Parse response
            raw_dict = _parse_extraction_response(response.text)
            extraction = ExtractionOutput(**raw_dict)

            # Post-process
            processed = _post_process(
                extraction, full_context, policy, db, communication_id,
            )

            logger.info(
                "[%s] Sonnet attempt %d succeeded: %d bundles, $%.4f",
                communication_id[:8], attempt,
                len(processed["bundles"]), response.usage.cost_usd,
            )

            return ExtractionAttemptResult(
                success=True,
                model=sonnet_model,
                attempt_number=attempt,
                raw_output=response.text,
                parsed_output=extraction,
                processed=processed,
                usage_data={
                    "input_tokens": response.usage.input_tokens,
                    "output_tokens": response.usage.output_tokens,
                    "processing_seconds": response.usage.processing_seconds,
                    "cost_usd": response.usage.cost_usd,
                    "total_cost_usd": total_cost,
                },
            )

        except json.JSONDecodeError as e:
            last_error = f"JSON parse error: {e}"
            logger.warning(
                "[%s] Sonnet attempt %d parse failed: %s",
                communication_id[:8], attempt, e,
            )
        except ValidationError as e:
            last_error = f"Validation error: {e.error_count()} errors"
            logger.warning(
                "[%s] Sonnet attempt %d validation failed: %s",
                communication_id[:8], attempt, e,
            )
        except BudgetExceededError:
            raise
        except LLMError as e:
            if not e.recoverable:
                raise
            last_error = str(e)
            logger.warning(
                "[%s] Sonnet attempt %d LLM error: %s",
                communication_id[:8], attempt, e,
            )

    # All Sonnet attempts failed
    failure_type = ExtractionFailureType.PARSE_FAILURE
    if last_error and "Validation" in last_error:
        failure_type = ExtractionFailureType.VALIDATION_FAILURE
    elif last_error and ("API" in last_error or "LLM" in last_error):
        failure_type = ExtractionFailureType.MODEL_API_FAILURE

    return ExtractionAttemptResult(
        success=False,
        model=sonnet_model,
        attempt_number=MAX_SONNET_ATTEMPTS,
        raw_output=last_raw_output,
        failure_type=failure_type,
        failure_detail=last_error,
        usage_data={"total_cost_usd": total_cost},
    )


# ═══════════════════════════════════════════════════════════════════════════
# 9. Opus escalation attempt (Original Phase 5)
# ═══════════════════════════════════════════════════════════════════════════

async def _run_opus_escalation(
    db,
    communication_id: str,
    opus_model: str,
    system_prompt: str,
    user_prompt: str,
    full_context: dict,
    full_context_json: str,
    policy: dict,
    prompt_version: str,
    sonnet_result: "ExtractionAttemptResult",
    triggers: list,
) -> "ExtractionAttemptResult":
    """Run Opus escalation extraction.

    Per 03_AI_BEHAVIOR.md §7C: Opus receives the same input as Sonnet
    plus Sonnet's complete output plus a meta-instruction.

    Returns ExtractionAttemptResult.
    Raises BudgetExceededError (let orchestrator handle).
    """
    from app.pipeline.stages.escalation import (
        ExtractionAttemptResult, ExtractionFailureType,
        build_opus_meta_instruction,
    )

    meta_instruction = build_opus_meta_instruction(triggers, sonnet_result)
    opus_prompt = user_prompt + "\n\n" + meta_instruction

    escalation_reason = ", ".join(t.value for t in triggers)

    try:
        response = await call_llm(
            db=db,
            communication_id=communication_id,
            stage="extracting_opus",
            model=opus_model,
            system_prompt=system_prompt,
            user_prompt=opus_prompt,
            max_tokens=16384,
            temperature=0.0,
        )

        # Parse
        raw_dict = _parse_extraction_response(response.text)
        extraction = ExtractionOutput(**raw_dict)

        # Post-process (same rules as Sonnet)
        processed = _post_process(
            extraction, full_context, policy, db, communication_id,
        )

        logger.info(
            "[%s] Opus escalation succeeded: %d bundles, $%.4f",
            communication_id[:8],
            len(processed["bundles"]), response.usage.cost_usd,
        )

        return ExtractionAttemptResult(
            success=True,
            model=opus_model,
            attempt_number=1,
            raw_output=response.text,
            parsed_output=extraction,
            processed=processed,
            triggers_detected=triggers,
            escalation_reason=escalation_reason,
            usage_data={
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
                "processing_seconds": response.usage.processing_seconds,
                "cost_usd": response.usage.cost_usd,
            },
        )

    except json.JSONDecodeError as e:
        logger.warning(
            "[%s] Opus escalation parse failed: %s",
            communication_id[:8], e,
        )
        return ExtractionAttemptResult(
            success=False,
            model=opus_model,
            attempt_number=1,
            failure_type=ExtractionFailureType.PARSE_FAILURE,
            failure_detail=f"Opus JSON parse error: {e}",
            triggers_detected=triggers,
            escalation_reason=escalation_reason,
        )
    except ValidationError as e:
        logger.warning(
            "[%s] Opus escalation validation failed: %s",
            communication_id[:8], e,
        )
        return ExtractionAttemptResult(
            success=False,
            model=opus_model,
            attempt_number=1,
            failure_type=ExtractionFailureType.VALIDATION_FAILURE,
            failure_detail=f"Opus validation error: {e.error_count()} errors",
            triggers_detected=triggers,
            escalation_reason=escalation_reason,
        )
    except BudgetExceededError:
        raise
    except LLMError as e:
        logger.warning(
            "[%s] Opus escalation LLM error: %s", communication_id[:8], e,
        )
        return ExtractionAttemptResult(
            success=False,
            model=opus_model,
            attempt_number=1,
            failure_type=ExtractionFailureType.MODEL_API_FAILURE,
            failure_detail=str(e),
            triggers_detected=triggers,
            escalation_reason=escalation_reason,
        )


# ═══════════════════════════════════════════════════════════════════════════
# 10. Main entry point — extraction with escalation (Phase 4B + Phase 5)
# ═══════════════════════════════════════════════════════════════════════════

async def run_extraction_stage(db, communication_id: str) -> dict:
    """Run extraction: Sonnet first, then Opus escalation if triggered.

    Flow (per 03_AI_BEHAVIOR.md §7 and 05_CONFIG_AND_BUILD_ORDER.md Phase 5):
      1. Run Sonnet extraction (up to MAX_SONNET_ATTEMPTS with self-correction)
      2. If Sonnet succeeds: check escalation triggers
         a. No triggers → persist Sonnet result → done
         b. Triggers fired + escalation enabled → run Opus → persist winner
      3. If Sonnet fails entirely: check if Opus escalation can salvage
         a. Escalation enabled → run Opus
         b. Escalation disabled or Opus also fails → terminal error

    Returns summary dict with bundle counts, cost, and escalation metadata.
    Raises BudgetExceededError if budget is exhausted.
    Raises RuntimeError for unrecoverable failures.
    """
    from app.pipeline.stages.escalation import (
        ExtractionFailureType,
        detect_triggers,
        decide_escalation,
    )
    from app.routers.events import publish_event

    policy = load_policy()
    model_config = policy.get("model_config", {})
    sonnet_model = model_config.get(
        "primary_extraction_model", "claude-sonnet-4-20250514"
    )
    opus_model = model_config.get("escalation_model", "claude-opus-4-6")
    prompt_version = model_config.get("active_prompt_versions", {}).get(
        "extraction", "v1.0.0"
    )

    # Load system prompt
    system_prompt = _load_system_prompt(prompt_version)

    # Fetch full tracker context
    full_context = await _fetch_tracker_context()
    full_context_json = json.dumps(full_context, ensure_ascii=False, default=str)

    # Gather tiering signals and build tiered context
    signals = _gather_tiering_signals(db, communication_id)
    tiered = _tier_context(full_context, signals)

    logger.info(
        "[%s] Context tiered: %d T1 matters, %d T2 matters, %d meetings",
        communication_id[:8],
        tiered["tier_stats"]["tier_1_matter_count"],
        tiered["tier_stats"]["tier_2_matter_count"],
        tiered["tier_stats"]["tier_1_meeting_count"],
    )

    # Build user prompt
    user_prompt = _build_user_prompt(db, communication_id, tiered, policy)

    # ── Step 1: Sonnet extraction ──
    sonnet_result = await _run_sonnet_extraction(
        db, communication_id, sonnet_model, system_prompt, user_prompt,
        full_context, full_context_json, policy, prompt_version,
    )

    # ── Step 2: Check escalation triggers (Original Phase 5) ──
    triggers = detect_triggers(sonnet_result, db, communication_id, policy)
    escalation_decision = decide_escalation(triggers, db, policy)

    # Log the decision
    if triggers:
        logger.info(
            "[%s] Escalation triggers: [%s] — decision: %s",
            communication_id[:8],
            ", ".join(t.value for t in triggers),
            escalation_decision.reason,
        )

    # ── Step 3: Persist Sonnet result (always, for audit trail) ──
    sonnet_extraction_id = None
    if sonnet_result.success:
        sonnet_extraction_id = _persist_extraction(
            db=db,
            communication_id=communication_id,
            extraction=sonnet_result.parsed_output,
            processed=sonnet_result.processed,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            full_context_json=full_context_json,
            raw_output=sonnet_result.raw_output,
            attempt_number=sonnet_result.attempt_number,
            model_used=sonnet_model,
            prompt_version=prompt_version,
            usage_data=sonnet_result.usage_data or {},
            escalation_reason=None,
            success=not escalation_decision.should_escalate,
        )

    # ── Step 4: Opus escalation if warranted ──
    opus_result = None
    final_extraction_id = sonnet_extraction_id

    if escalation_decision.should_escalate:
        await publish_event("stage_progress", {
            "communication_id": communication_id,
            "stage": "extracting",
            "message": f"Escalating to Opus ({escalation_decision.reason})...",
        })

        opus_result = await _run_opus_escalation(
            db, communication_id, opus_model, system_prompt, user_prompt,
            full_context, full_context_json, policy, prompt_version,
            sonnet_result, triggers,
        )

        if opus_result.success:
            # Clear Sonnet bundles — Opus output supersedes
            if sonnet_result.success:
                _clear_bundles_for_communication(db, communication_id)

            # Persist Opus result as the authoritative extraction
            opus_attempt = (sonnet_result.attempt_number + 1) if sonnet_result.success else (MAX_SONNET_ATTEMPTS + 1)
            final_extraction_id = _persist_extraction(
                db=db,
                communication_id=communication_id,
                extraction=opus_result.parsed_output,
                processed=opus_result.processed,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                full_context_json=full_context_json,
                raw_output=opus_result.raw_output,
                attempt_number=opus_attempt,
                model_used=opus_model,
                prompt_version=prompt_version,
                usage_data=opus_result.usage_data or {},
                escalation_reason=opus_result.escalation_reason,
                success=True,
            )
            logger.info(
                "[%s] Opus escalation succeeded — using Opus bundles",
                communication_id[:8],
            )
        else:
            # Opus failed — fall back to Sonnet if available
            if sonnet_result.success:
                # Mark Sonnet extraction as the final success
                db.execute("""
                    UPDATE ai_extractions SET success = 1
                    WHERE id = ? AND communication_id = ?
                """, (sonnet_extraction_id, communication_id))
                db.commit()
                logger.warning(
                    "[%s] Opus escalation failed — falling back to Sonnet result",
                    communication_id[:8],
                )
            else:
                # Both failed — persist Opus failure for audit, then error
                _persist_failed_extraction(
                    db, communication_id, opus_model, opus_result,
                    prompt_version, full_context_json,
                )
                raise RuntimeError(
                    f"Extraction failed: Sonnet ({sonnet_result.failure_detail}) "
                    f"and Opus escalation ({opus_result.failure_detail})"
                )

    elif escalation_decision.blocked_by_budget:
        # Escalation warranted but budget blocked
        if not sonnet_result.success:
            raise BudgetExceededError(0, 0)  # Let orchestrator handle
        logger.warning(
            "[%s] Escalation blocked by budget — using Sonnet result",
            communication_id[:8],
        )

    elif not sonnet_result.success:
        # No escalation available, Sonnet failed
        _persist_failed_extraction(
            db, communication_id, sonnet_model, sonnet_result,
            prompt_version, full_context_json,
        )
        raise RuntimeError(
            f"Extraction failed after {MAX_SONNET_ATTEMPTS} Sonnet attempts "
            f"(escalation {'disabled' if escalation_decision.blocked_by_config else 'not triggered'}): "
            f"{sonnet_result.failure_detail}"
        )

    # ── Step 5: Build return summary ──
    winner = opus_result if (opus_result and opus_result.success) else sonnet_result
    bundles = winner.processed["bundles"]
    total_items = sum(len(b.items) for b in bundles)
    pp_log = winner.processed["post_processing_log"]

    sonnet_cost = (sonnet_result.usage_data or {}).get("total_cost_usd", 0)
    opus_cost = (opus_result.usage_data or {}).get("cost_usd", 0) if opus_result else 0

    logger.info(
        "[%s] Extraction stage complete: %d bundles, %d items, "
        "model=%s, escalated=%s, cost=$%.4f",
        communication_id[:8], len(bundles), total_items,
        winner.model.split("-")[1],
        bool(opus_result and opus_result.success),
        sonnet_cost + opus_cost,
    )

    return {
        "extraction_id": final_extraction_id,
        "bundles_created": len(bundles),
        "items_created": total_items,
        "items_suppressed": len(pp_log["code_suppressed_items"]),
        "dedup_warnings": len(pp_log["dedup_warnings"]),
        "invalid_refs_cleaned": len(pp_log["invalid_references_cleaned"]),
        "input_tokens": (winner.usage_data or {}).get("input_tokens", 0),
        "output_tokens": (winner.usage_data or {}).get("output_tokens", 0),
        "total_cost_usd": round(sonnet_cost + opus_cost, 6),
        "attempt_number": winner.attempt_number,
        "tier_stats": tiered["tier_stats"],
        "escalated": bool(opus_result and opus_result.success),
        "escalation_triggers": [t.value for t in triggers] if triggers else [],
        "escalation_decision": escalation_decision.reason if triggers else None,
        "model_used": winner.model,
    }


# ═══════════════════════════════════════════════════════════════════════════
# 11. Helpers: bundle cleanup and failed extraction persistence
# ═══════════════════════════════════════════════════════════════════════════

def _clear_bundles_for_communication(db, communication_id: str):
    """Remove Sonnet-generated bundles/items before Opus re-persist.

    Only clears bundles still in 'proposed' status (not yet reviewed).
    """
    bundle_ids = [
        r["id"] for r in db.execute(
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
            communication_id[:8], len(bundle_ids),
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
    db.execute("""
        INSERT INTO ai_extractions
            (id, communication_id, attempt_number, model_used, prompt_version,
             raw_output, escalation_reason, success,
             tracker_context_snapshot)
        VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?)
    """, (
        extraction_id, communication_id,
        result.attempt_number, model, prompt_version,
        result.raw_output or f"[FAILED: {result.failure_detail}]",
        result.escalation_reason,
        full_context_json,
    ))
    db.commit()
