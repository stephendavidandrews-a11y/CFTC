"""Sonnet extraction stage — matter-centered intelligence extraction.

Pipeline position: entities_confirmed → **extracting** → awaiting_bundle_review

Takes confirmed speakers, cleaned transcript, enrichment data, and reviewed
entities. Fetches tracker context, builds a tiered prompt, calls Sonnet 4.6,
then runs a 7-step code post-processing pass before persisting review bundles.

Design contract: Phase 4A.1 revision memo (sections A-H).
"""

import json
import logging
import uuid
from typing import Optional

import httpx
from pydantic import ValidationError

from app.config import load_policy, TRACKER_BASE_URL, TRACKER_USER, TRACKER_PASS, PROMPT_BASE_DIR
from app.llm.client import call_llm, BudgetExceededError, LLMError

from app.pipeline.stages.extraction_models import (
    ExtractionOutput,
    POLICY_TOGGLE_MAP,
    TASK_UPDATE_ALLOWED_FIELDS,
    DECISION_UPDATE_ALLOWED_FIELDS,
)

logger = logging.getLogger(__name__)

PROMPT_DIR = PROMPT_BASE_DIR / "extraction"

MAX_EXTRACTION_ATTEMPTS = 3


# ═══════════════════════════════════════════════════════════════════════════
# 1. System prompt loading
# ═══════════════════════════════════════════════════════════════════════════

def _load_system_prompt(version: str) -> str:
    """Load the extraction system prompt for the given version.

    Version strings use dots (e.g. "v2.0.0") but prompt filenames use
    underscores (e.g. "v2_0_0.md").
    """
    filename = version.replace(".", "_") + ".md"
    prompt_path = PROMPT_DIR / filename
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
        auth = (TRACKER_USER, TRACKER_PASS) if TRACKER_USER else None
        async with httpx.AsyncClient(timeout=30.0) as client:
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
                # stakeholder data from ai-context uses full_name, we need
                # to check by person_id in the matter_people join
                pass

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
                # org data from ai-context doesn't include organization_id
                # directly — it has 'name' and 'organization_role'
                pass

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
    model_name = policy.get("model_config", {}).get("primary_extraction_model", "")
    use_xml = model_name.startswith("claude-")

    def _wrap(tag: str, content: str) -> str:
        if use_xml:
            return f"<{tag}>\n{content}\n</{tag}>"
        return f"## {tag.replace('_', ' ').title()}\n{content}"

    sections = []

    # ── Communication data ──
    comm = db.execute("""
        SELECT id, source_type, original_filename, duration_seconds,
               topic_segments_json, sensitivity_flags, created_at
        FROM communications WHERE id = ?
    """, (communication_id,)).fetchone()

    source_type = comm["source_type"] or "audio_upload"

    # Communication metadata section
    comm_lines = [
        f"Communication ID: {communication_id}",
        f"Source Type: {source_type}",
        f"Date: {comm['created_at']}",
    ]
    if source_type != "email":
        comm_lines.append(f"Duration: {comm['duration_seconds'] or 0} seconds")
    comm_lines.append(f"Original Filename: {comm['original_filename'] or 'unknown'}")
    sections.append(_wrap("communication_data", "\n".join(comm_lines)))

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

    # Enrichment section
    enrich_parts = []
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
        enrich_parts.append(f"### Enrichment Summary\n{summary}")
    if topics:
        enrich_parts.append(f"### Topics\n```json\n{json.dumps(topics, indent=2)}\n```")

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
        enrich_parts.append(f"### Confirmed Entities\n```json\n{json.dumps(entities, indent=2, default=str)}\n```")

    # Sensitivity flags
    if comm["sensitivity_flags"]:
        enrich_parts.append(f"### Sensitivity Flags\n{comm['sensitivity_flags']}")

    if enrich_parts:
        sections.append(_wrap("enrichment", "\n\n".join(enrich_parts)))

    # Full content: email messages or audio transcript
    if source_type == "email":
        msg_rows = db.execute("""
            SELECT id, message_index, sender_email, sender_name,
                   recipient_emails, cc_emails, subject, body_text,
                   is_new, is_from_user, timestamp
            FROM communication_messages
            WHERE communication_id = ?
            ORDER BY message_index
        """, (communication_id,)).fetchall()

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
        content_parts = [f"```json\n{json.dumps(message_data, indent=2)}\n```"]

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
            content_parts.append(f"### Attachments\n```json\n{json.dumps(att_data, indent=2)}\n```")

        sections.append(_wrap("email_thread", "\n\n".join(content_parts)))
    else:
        segments = db.execute("""
            SELECT id, speaker_label, start_time, end_time,
                   cleaned_text, raw_text
            FROM transcripts
            WHERE communication_id = ?
            ORDER BY start_time
        """, (communication_id,)).fetchall()

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
                "text": seg["cleaned_text"] or seg["raw_text"] or "",
            })
        sections.append(_wrap("transcript", f"```json\n{json.dumps(transcript_data, indent=2)}\n```"))

    # ── Extraction policy (tell model what's disabled) ──
    extraction_policy = policy.get("extraction_policy", {})
    disabled_types = []
    for toggle, item_type in POLICY_TOGGLE_MAP.items():
        if not extraction_policy.get(toggle, True):
            disabled_types.append(item_type)

    if disabled_types:
        policy_content = (
            "The following proposal types are DISABLED. You should still "
            "reason about them and note observations in "
            "suppressed_observations, but do NOT include them in "
            "bundles[].items[]:\n"
            + "\n".join(f"- {t}" for t in disabled_types)
        )
        sections.append(_wrap("extraction_policy", policy_content))

    # ── Tiered tracker context ──
    t1 = tiered_context["tier_1_matters"]
    t2 = tiered_context["tier_2_matters"]
    ctx_parts = []

    if t1:
        ctx_parts.append(
            f"### Priority Matters ({len(t1)} — full detail, likely relevant)\n"
            f"```json\n{json.dumps(t1, indent=2, default=str)}\n```"
        )
    else:
        ctx_parts.append(
            "### Priority Matters\nNo matters were pre-identified as relevant "
            "to this conversation's speakers or entities. Scan all matters "
            "below for topical relevance."
        )

    if t2:
        ctx_parts.append(
            f"### Other Open Matters ({len(t2)} — summary, check for unexpected relevance)\n"
            f"```json\n{json.dumps(t2, indent=2, default=str)}\n```"
        )

    if tiered_context["tier_1_meetings"]:
        ctx_parts.append(
            f"### Recent Meetings ({len(tiered_context['tier_1_meetings'])})\n"
            f"```json\n{json.dumps(tiered_context['tier_1_meetings'], indent=2, default=str)}\n```"
        )

    ctx_parts.append(
        f"### People Registry ({len(tiered_context['people'])})\n"
        f"```json\n{json.dumps(tiered_context['people'], indent=2, default=str)}\n```"
    )
    ctx_parts.append(
        f"### Organizations Registry ({len(tiered_context['organizations'])})\n"
        f"```json\n{json.dumps(tiered_context['organizations'], indent=2, default=str)}\n```"
    )

    if tiered_context["standalone_tasks"]:
        ctx_parts.append(
            f"### Standalone Tasks ({len(tiered_context['standalone_tasks'])})\n"
            f"```json\n{json.dumps(tiered_context['standalone_tasks'], indent=2, default=str)}\n```"
        )

    sections.append(_wrap("tracker_context", "\n\n".join(ctx_parts)))

    # ── Final instruction ──
    if source_type == "email":
        instr = (
            "Analyze this email thread and extract actionable operational "
            "intelligence. Organize proposals into bundles grouped by the matter "
            "each set relates to. Follow all rules in your system prompt. "
            "Prefer fewer, higher-quality proposals. "
            "For source locators, use message_index and paragraph number "
            "instead of time-based references."
        )
    else:
        instr = (
            "Analyze this conversation and extract actionable operational "
            "intelligence. Organize proposals into bundles grouped by the matter "
            "each set relates to. Follow all rules in your system prompt. "
            "Prefer fewer, higher-quality proposals."
        )
    sections.append(_wrap("instructions", instr))

    return "\n".join(sections)


# ═══════════════════════════════════════════════════════════════════════════
# 5. Response parsing
# ═══════════════════════════════════════════════════════════════════════════

def _parse_extraction_response(text: str) -> dict:
    """Parse Sonnet's extraction response, tolerating markdown fencing."""
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

def _resolve_name_to_id(name: str, registry: list, name_field: str, id_field: str = "id") -> str | None:
    """Case-insensitive exact match of name against a registry list.

    Returns the id if exactly one match, else None.
    """
    if not name:
        return None
    name_lower = name.strip().lower()
    matches = [
        entry[id_field] for entry in registry
        if (entry.get(name_field) or "").strip().lower() == name_lower
    ]
    if len(matches) == 1:
        return matches[0]
    return None


def _resolve_entity_names(extraction: "ExtractionOutput", full_context: dict) -> list[str]:
    """Step 1.5: Resolve name-based references to UUIDs.

    Checks item-level name fallbacks AND proposed_data name companions.
    Returns a list of resolution log entries.
    """
    people = full_context.get("people", [])
    orgs = full_context.get("organizations", [])
    matters = full_context.get("matters", [])
    resolution_log = []

    # Name → ID resolution mappings
    PERSON_PAIRS = [
        ("assigned_to_person_id", "assigned_to_name"),
        ("waiting_on_person_id", "waiting_on_name"),
        ("decision_assigned_to_person_id", "decision_assigned_to_name"),
        ("person_id", "person_name"),
        ("delegated_by_person_id", "delegated_by_name"),
        ("supervising_person_id", "supervising_name"),
    ]
    ORG_PAIRS = [
        ("organization_id", "organization_name_ref"),
        ("organization_id", "organization_name"),
        ("waiting_on_org_id", "waiting_on_org_name"),
        ("requesting_organization_id", "requesting_organization_name"),
    ]

    for bundle in extraction.bundles:
        # Resolve bundle-level target_matter_id from target_matter_title
        if not bundle.target_matter_id and bundle.target_matter_title:
            for m in matters:
                if _fuzzy_title_match(
                    bundle.target_matter_title.lower(),
                    (m.get("title") or "").lower(),
                ):
                    bundle.target_matter_id = m["id"]
                    bundle.bundle_type = "matter"
                    resolution_log.append(
                        f"Bundle matter resolved: '{bundle.target_matter_title}' -> {m['id'][:8]}"
                    )
                    break

        for item in bundle.items:
            pd = item.proposed_data

            # Item-level name fallbacks
            for id_field, name_field in PERSON_PAIRS:
                name_val = getattr(item, name_field, None) or pd.get(name_field)
                id_val = pd.get(id_field)
                if name_val and not id_val:
                    resolved = _resolve_name_to_id(name_val, people, "full_name")
                    if resolved:
                        pd[id_field] = resolved
                        item.rationale += f" [Name resolved: {name_field} '{name_val}' -> UUID]"
                        resolution_log.append(f"Person resolved: '{name_val}' -> {resolved[:8]}")
                    else:
                        item.rationale += f" [Name unresolved: {name_field} '{name_val}' — no match in context]"
                        resolution_log.append(f"Person unresolved: '{name_val}'")

            for id_field, name_field in ORG_PAIRS:
                name_val = getattr(item, name_field, None) or pd.get(name_field)
                id_val = pd.get(id_field)
                if name_val and not id_val:
                    resolved = _resolve_name_to_id(name_val, orgs, "name")
                    if resolved:
                        pd[id_field] = resolved
                        item.rationale += f" [Org resolved: '{name_val}' -> UUID]"
                        resolution_log.append(f"Org resolved: '{name_val}' -> {resolved[:8]}")
                    else:
                        resolution_log.append(f"Org unresolved: '{name_val}'")

            # Resolve linked_entities on context_note items
            if item.item_type == "context_note":
                for le in pd.get("linked_entities", []):
                    if le.get("entity_id"):
                        continue
                    etype = le.get("entity_type", "")
                    ename = le.get("entity_name", "")
                    if etype == "person":
                        resolved = _resolve_name_to_id(ename, people, "full_name")
                    elif etype == "organization":
                        resolved = _resolve_name_to_id(ename, orgs, "name")
                    elif etype == "matter":
                        resolved = _resolve_name_to_id(ename, matters, "title")
                    else:
                        resolved = None
                    if resolved:
                        le["entity_id"] = resolved
                        resolution_log.append(
                            f"Linked entity resolved: {etype} '{ename}' -> {resolved[:8]}"
                        )

            # Resolve meeting_record participant names
            if item.item_type == "meeting_record":
                for part in pd.get("participants", []):
                    if not part.get("person_id") and part.get("person_name"):
                        resolved = _resolve_name_to_id(
                            part["person_name"], people, "full_name"
                        )
                        if resolved:
                            part["person_id"] = resolved

    return resolution_log


def _validate_tracks_task_refs(extraction: "ExtractionOutput") -> list[str]:
    """Validate $ref: references between items in the same bundle.

    Returns list of warning messages.
    """
    warnings = []
    for bundle in extraction.bundles:
        # Build client_id index for this bundle
        client_ids = {
            item.client_id for item in bundle.items if item.client_id
        }
        for item in bundle.items:
            ref = item.proposed_data.get("tracks_task_ref")
            if ref and isinstance(ref, str) and ref.startswith("$ref:"):
                ref_id = ref[5:]
                if ref_id not in client_ids:
                    warnings.append(
                        f"Item '{item.proposed_data.get('title', '?')}' "
                        f"references unknown client_id '{ref_id}' — cleared"
                    )
                    item.proposed_data["tracks_task_ref"] = None
    return warnings


def _validate_update_items(
    extraction: "ExtractionOutput", full_context: dict,
) -> list[str]:
    """Validate task_update, decision_update, and org_detail_update items.

    Logs warnings but does NOT remove items — lets them go to review.
    Returns list of warning messages.
    """
    warnings = []

    # Build lookup structures
    all_task_ids = set()
    all_decision_ids = set()
    for m in full_context.get("matters", []):
        for t in m.get("open_tasks", []):
            all_task_ids.add(t.get("id"))
        for d in m.get("open_decisions", m.get("decisions", [])):
            all_decision_ids.add(d.get("id"))
    for t in full_context.get("standalone_tasks", []):
        all_task_ids.add(t.get("id"))
    all_task_ids.discard(None)
    all_decision_ids.discard(None)

    valid_org_ids = {o["id"] for o in full_context.get("organizations", [])}

    for bundle in extraction.bundles:
        for item in bundle.items:
            pd = item.proposed_data

            if item.item_type == "task_update":
                tid = pd.get("existing_task_id")
                if not tid:
                    w = "task_update missing existing_task_id"
                    warnings.append(w)
                    item.rationale += f" [VALIDATION: {w}]"
                elif tid not in all_task_ids:
                    w = f"task_update references unknown task {tid[:8] if tid else '?'}"
                    warnings.append(w)
                    item.rationale += f" [VALIDATION: {w}]"

                changes = pd.get("changes", {})
                if not changes:
                    w = "task_update has empty changes"
                    warnings.append(w)
                    item.rationale += f" [VALIDATION: {w}]"
                else:
                    bad_fields = set(changes.keys()) - TASK_UPDATE_ALLOWED_FIELDS
                    if bad_fields:
                        w = f"task_update has disallowed fields: {bad_fields}"
                        warnings.append(w)
                        item.rationale += f" [VALIDATION: {w}]"

                if not pd.get("change_summary"):
                    w = "task_update missing change_summary"
                    warnings.append(w)
                    item.rationale += f" [VALIDATION: {w}]"

            elif item.item_type == "decision_update":
                did = pd.get("existing_decision_id")
                if not did:
                    w = "decision_update missing existing_decision_id"
                    warnings.append(w)
                    item.rationale += f" [VALIDATION: {w}]"
                elif did not in all_decision_ids:
                    w = f"decision_update references unknown decision {did[:8] if did else '?'}"
                    warnings.append(w)
                    item.rationale += f" [VALIDATION: {w}]"

                changes = pd.get("changes", {})
                if not changes:
                    w = "decision_update has empty changes"
                    warnings.append(w)
                    item.rationale += f" [VALIDATION: {w}]"
                else:
                    bad_fields = set(changes.keys()) - DECISION_UPDATE_ALLOWED_FIELDS
                    if bad_fields:
                        w = f"decision_update has disallowed fields: {bad_fields}"
                        warnings.append(w)
                        item.rationale += f" [VALIDATION: {w}]"

                if not pd.get("change_summary"):
                    w = "decision_update missing change_summary"
                    warnings.append(w)
                    item.rationale += f" [VALIDATION: {w}]"

            elif item.item_type == "org_detail_update":
                oid = pd.get("existing_org_id")
                if not oid:
                    w = "org_detail_update missing existing_org_id"
                    warnings.append(w)
                    item.rationale += f" [VALIDATION: {w}]"
                elif oid not in valid_org_ids:
                    w = f"org_detail_update references unknown org {oid[:8] if oid else '?'}"
                    warnings.append(w)
                    item.rationale += f" [VALIDATION: {w}]"

                changes = pd.get("changes", {})
                if not changes:
                    w = "org_detail_update has empty changes"
                    warnings.append(w)
                    item.rationale += f" [VALIDATION: {w}]"
                elif set(changes.keys()) - {"jurisdiction"}:
                    w = f"org_detail_update can only change jurisdiction, got: {set(changes.keys())}"
                    warnings.append(w)
                    item.rationale += f" [VALIDATION: {w}]"

                if not pd.get("change_summary"):
                    w = "org_detail_update missing change_summary"
                    warnings.append(w)
                    item.rationale += f" [VALIDATION: {w}]"

    return warnings


def _convert_legacy_follow_ups(extraction: "ExtractionOutput") -> int:
    """Convert legacy item_type='follow_up' to task with task_mode='follow_up'.

    Returns count of items converted.
    """
    count = 0
    for bundle in extraction.bundles:
        for item in bundle.items:
            if item.item_type == "follow_up":
                item.item_type = "task"
                if "task_mode" not in item.proposed_data:
                    item.proposed_data["task_mode"] = "follow_up"
                item.rationale += " [Converted from legacy follow_up item type]"
                count += 1
    return count


def _post_process(
    extraction: ExtractionOutput,
    full_context: dict,
    policy: dict,
    db,
    communication_id: str,
) -> dict:
    """Run the post-processing pass.

    Returns a dict with:
        bundles: list of validated bundles (ready for DB insert)
        post_processing_log: audit metadata
    """
    log = {
        "code_suppressed_items": [],
        "dedup_warnings": [],
        "invalid_references_cleaned": [],
        "name_resolutions": [],
        "update_validation_warnings": [],
        "ref_validation_warnings": [],
        "legacy_follow_up_conversions": 0,
        "tier_1_matter_count": 0,
        "tier_2_matter_count": 0,
        "token_truncation_occurred": False,
    }

    # ── Step 0: Convert legacy follow_up item types ──
    log["legacy_follow_up_conversions"] = _convert_legacy_follow_ups(extraction)

    # ── Step 1.5: Resolve entity names to UUIDs ──
    log["name_resolutions"] = _resolve_entity_names(extraction, full_context)

    # ── Step 1.7: Validate $ref: references between items ──
    log["ref_validation_warnings"] = _validate_tracks_task_refs(extraction)

    # ── Step 1.8: Validate update item types ──
    log["update_validation_warnings"] = _validate_update_items(extraction, full_context)

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

            # ── Step 3: Apply extraction_policy suppression ──
            if item.item_type in disabled_types:
                log["code_suppressed_items"].append({
                    "item_type": item.item_type,
                    "reason": f"propose_{item.item_type}s disabled in extraction_policy",
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
            if item.item_type == "task" and existing_tasks:
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
                item.source_excerpt,
                item.source_segments[0] if item.source_segments else None,
                item.source_time_range.start,
                item.source_time_range.end,
                json.dumps(source_locator, ensure_ascii=False, default=str),
                item_idx,
            ))

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
                max_tokens=8192,
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
            max_tokens=8192,
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
