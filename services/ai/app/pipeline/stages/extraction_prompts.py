"""Prompt assembly for extraction.

Loads system prompt templates and builds the full user prompt
from communication data, tracker context, and policy toggles.
"""

import json
import logging

from app.config import PROMPT_BASE_DIR
from app.pipeline.stages.extraction_models import POLICY_TOGGLE_MAP

logger = logging.getLogger(__name__)

PROMPT_DIR = PROMPT_BASE_DIR / "extraction"

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
    comm = db.execute(
        """
        SELECT id, source_type, original_filename, duration_seconds,
               topic_segments_json, sensitivity_flags, created_at
        FROM communications WHERE id = ?
    """,
        (communication_id,),
    ).fetchone()

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
    participants = db.execute(
        """
        SELECT speaker_label, tracker_person_id, proposed_name,
               proposed_title, proposed_org, participant_email,
               header_role, participant_role
        FROM communication_participants
        WHERE communication_id = ?
        ORDER BY speaker_label
    """,
        (communication_id,),
    ).fetchall()

    if source_type == "email":
        participant_data = []
        for p in participants:
            participant_data.append(
                {
                    "email": p["participant_email"],
                    "tracker_person_id": p["tracker_person_id"],
                    "name": p["proposed_name"] or p["participant_email"],
                    "title": p["proposed_title"],
                    "org": p["proposed_org"],
                    "role": p["header_role"] or p["participant_role"],
                }
            )
        sections.append(
            f"\n### Participants (confirmed)\n```json\n{json.dumps(participant_data, indent=2)}\n```"
        )
    else:
        speaker_data = []
        for p in participants:
            speaker_data.append(
                {
                    "label": p["speaker_label"],
                    "tracker_person_id": p["tracker_person_id"],
                    "name": p["proposed_name"] or p["speaker_label"],
                    "title": p["proposed_title"],
                    "org": p["proposed_org"],
                }
            )
        sections.append(
            f"\n### Speakers (confirmed)\n```json\n{json.dumps(speaker_data, indent=2)}\n```"
        )

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
    entity_rows = db.execute(
        """
        SELECT mention_text, entity_type, tracker_person_id, tracker_org_id,
               proposed_name, confidence, confirmed, mention_count,
               context_snippet
        FROM communication_entities
        WHERE communication_id = ? AND confirmed != -1
        ORDER BY mention_count DESC
    """,
        (communication_id,),
    ).fetchall()

    if entity_rows:
        entities = [dict(r) for r in entity_rows]
        enrich_parts.append(
            f"### Confirmed Entities\n```json\n{json.dumps(entities, indent=2, default=str)}\n```"
        )

    # Sensitivity flags
    if comm["sensitivity_flags"]:
        enrich_parts.append(f"### Sensitivity Flags\n{comm['sensitivity_flags']}")

    if enrich_parts:
        sections.append(_wrap("enrichment", "\n\n".join(enrich_parts)))

    # Full content: email messages or audio transcript
    if source_type == "email":
        msg_rows = db.execute(
            """
            SELECT id, message_index, sender_email, sender_name,
                   recipient_emails, cc_emails, subject, body_text,
                   is_new, is_from_user, timestamp
            FROM communication_messages
            WHERE communication_id = ?
            ORDER BY message_index
        """,
            (communication_id,),
        ).fetchall()

        participant_names = {
            p["participant_email"]: (p["proposed_name"] or p["participant_email"])
            for p in participants
            if p["participant_email"]
        }

        message_data = []
        for msg in msg_rows:
            message_data.append(
                {
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
                }
            )
        content_parts = [f"```json\n{json.dumps(message_data, indent=2)}\n```"]

        att_rows = db.execute(
            """
            SELECT original_filename, mime_type, file_size_bytes,
                   extracted_text, text_extraction_status
            FROM communication_artifacts
            WHERE communication_id = ?
        """,
            (communication_id,),
        ).fetchall()

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
            content_parts.append(
                f"### Attachments\n```json\n{json.dumps(att_data, indent=2)}\n```"
            )

        sections.append(_wrap("email_thread", "\n\n".join(content_parts)))
    else:
        segments = db.execute(
            """
            SELECT id, speaker_label, start_time, end_time,
                   reviewed_text, cleaned_text, raw_text
            FROM transcripts
            WHERE communication_id = ?
            ORDER BY start_time
        """,
            (communication_id,),
        ).fetchall()

        speaker_names = {
            p["speaker_label"]: (p["proposed_name"] or p["speaker_label"])
            for p in participants
        }

        transcript_data = []
        for seg in segments:
            transcript_data.append(
                {
                    "segment_id": seg["id"],
                    "speaker": seg["speaker_label"],
                    "speaker_name": speaker_names.get(
                        seg["speaker_label"], seg["speaker_label"]
                    ),
                    "start": seg["start_time"],
                    "end": seg["end_time"],
                    "text": (
                        seg["reviewed_text"]
                        or seg["cleaned_text"]
                        or seg["raw_text"]
                        or ""
                    ),
                }
            )
        sections.append(
            _wrap(
                "transcript", f"```json\n{json.dumps(transcript_data, indent=2)}\n```"
            )
        )

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
            "bundles[].items[]:\n" + "\n".join(f"- {t}" for t in disabled_types)
        )
        sections.append(_wrap("extraction_policy", policy_content))

    # ── Segment intents (from enrichment v2) ──
    segment_intents = tiered_context.get("segment_intents", [])
    if segment_intents:
        intent_guidance = {
            "casual": "Prioritize: person_detail_update, context_note (people_insight, relationship_dynamic). De-prioritize: task, decision (unless explicitly stated).",
            "planning": "Prioritize: task, meeting_record, follow_up. Standard: context_note, matter_update.",
            "decision": "Prioritize: decision, matter_update, status_change. Standard: context_note.",
            "strategic": "Prioritize: context_note (strategic_context, political), directive_update. Standard: matter_update.",
            "briefing": "Prioritize: context_note (process_note), matter_update. Standard: task.",
            "policy": "Prioritize: context_note (policy_operating_rule), directive_update, matter_update.",
            "negotiation": "Prioritize: context_note (strategic_context), task, decision.",
        }
        intent_lines = []
        for seg in segment_intents:
            intent = seg.get("intent", "briefing")
            guidance = intent_guidance.get(intent, "")
            intent_lines.append(
                f"Segment {seg['index']} ({seg.get('topic', '')}) — intent: {intent}\n  → {guidance}"
            )
        sections.append(
            _wrap(
                "segment_intents",
                "Per-segment intent classification from enrichment (confirmed by reviewer). "
                "Use these to weight your extraction priorities for each part of the conversation.\n\n"
                + "\n\n".join(intent_lines),
            )
        )

    # ── Intelligence flags (from enrichment v2) ──
    intelligence_flags = tiered_context.get("intelligence_flags", [])
    if intelligence_flags:
        flag_lines = []
        for flag in intelligence_flags:
            about = ""
            if flag.get("about_entity"):
                about = f" about {flag['about_entity'].get('name', 'unknown')}"
            flag_lines.append(
                f"- [{flag.get('flag_type', 'unknown')}]{about}: {flag.get('hint', '')}"
            )
        sections.append(
            _wrap(
                "intelligence_flags",
                "DO NOT MISS these observations flagged by enrichment. "
                "Each flag indicates something noteworthy that should be extracted "
                "as a context_note, person_detail_update, or other appropriate item type.\n\n"
                + "\n".join(flag_lines),
            )
        )

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

    # Tier 1 directives
    t1_directives = tiered_context.get("tier_1_directives", [])
    if t1_directives:
        ctx_parts.append(
            f"### Policy Directives ({len(t1_directives)} — relevant to this conversation)\n"
            f"```json\n{json.dumps(t1_directives, indent=2, default=str)}\n```"
        )

    # Tiered people
    t1_people = tiered_context.get("tier_1_people", [])
    t2_people = tiered_context.get("tier_2_people", [])
    if t1_people:
        ctx_parts.append(
            f"### Relevant People ({len(t1_people)} — full detail)\n"
            f"```json\n{json.dumps(t1_people, indent=2, default=str)}\n```"
        )
    if t2_people:
        ctx_parts.append(
            f"### Other People ({len(t2_people)} — compact)\n"
            f"```json\n{json.dumps(t2_people, indent=2, default=str)}\n```"
        )

    # Tiered orgs
    t1_orgs = tiered_context.get("tier_1_orgs", [])
    t2_orgs = tiered_context.get("tier_2_orgs", [])
    if t1_orgs:
        ctx_parts.append(
            f"### Relevant Organizations ({len(t1_orgs)} — full detail)\n"
            f"```json\n{json.dumps(t1_orgs, indent=2, default=str)}\n```"
        )
    if t2_orgs:
        ctx_parts.append(
            f"### Other Organizations ({len(t2_orgs)} — compact)\n"
            f"```json\n{json.dumps(t2_orgs, indent=2, default=str)}\n```"
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
