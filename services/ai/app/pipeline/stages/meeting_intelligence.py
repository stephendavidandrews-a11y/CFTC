"""Meeting intelligence generator -- produces structured operating briefs.

Post-commit hook: after a meeting_record is committed to the tracker,
this module generates a structured meeting summary and writes it to the
meeting_intelligence table in the AI DB.

Tier gating:
- CORE (Haiku): short 1:1s, routine syncs (<20min, <=2 people, no external/boss)
- FULL (Sonnet): multi-party, congressional, interagency, boss-present, external
"""

import json
import logging
import uuid

from app.config import PROMPT_BASE_DIR, load_policy
from app.llm.client import call_llm, LLMResponse

logger = logging.getLogger(__name__)

PROMPT_DIR = PROMPT_BASE_DIR / "meeting_intelligence"

# --- Tier gating ---

FULL_TIER_MEETING_TYPES = {
    "leadership meeting",
    "interagency meeting",
    "Hill meeting",
    "briefing",
    "industry meeting",
    "commissioner office",
    "client meeting",
    "check-in",
}


def determine_tier(
    duration_seconds: float | None,
    participant_count: int,
    meeting_type: str | None,
    boss_attends: bool,
    external_parties: bool,
) -> str:
    """Returns 'full' if ANY escalation signal is present, else 'core'."""
    if duration_seconds and duration_seconds >= 1200:
        return "full"
    if participant_count >= 3:
        return "full"
    if meeting_type and meeting_type.lower() in FULL_TIER_MEETING_TYPES:
        return "full"
    if boss_attends:
        return "full"
    if external_parties:
        return "full"
    return "core"


# --- Prompt loading ---


def _load_prompt(version: str) -> str:
    prompt_path = PROMPT_DIR / f"{version}.md"
    if not prompt_path.exists():
        raise FileNotFoundError(f"Meeting intelligence prompt not found: {prompt_path}")
    return prompt_path.read_text(encoding="utf-8")


# --- Context assembly ---


def _build_user_prompt(
    db,
    communication_id: str,
    meeting_data: dict,
    committed_items: list[dict],
    tier: str,
) -> str:
    sections = []

    sections.append(f"## Tier: {tier.upper()}\n")

    # Meeting metadata
    sections.append("## Meeting Record\n")
    sections.append(f"Title: {meeting_data.get('title', 'Untitled')}")
    sections.append(f"Date/Time: {meeting_data.get('date_time_start', 'Unknown')}")
    if meeting_data.get("date_time_end"):
        sections.append(f"End: {meeting_data['date_time_end']}")
    if meeting_data.get("meeting_type"):
        sections.append(f"Type: {meeting_data['meeting_type']}")
    if meeting_data.get("purpose"):
        sections.append(f"Purpose: {meeting_data['purpose']}")
    sections.append(
        f"Boss attends: {'yes' if meeting_data.get('boss_attends') else 'no'}"
    )
    sections.append(
        f"External parties: {'yes' if meeting_data.get('external_parties_attend') else 'no'}"
    )

    # Participants
    participants = db.execute(
        """
        SELECT cp.speaker_label, cp.proposed_name, cp.proposed_title,
               cp.proposed_org, cp.participant_role
        FROM communication_participants cp
        WHERE cp.communication_id = ?
        ORDER BY cp.speaker_label
    """,
        (communication_id,),
    ).fetchall()

    if participants:
        sections.append("\n## Participants\n")
        for p in participants:
            name = p["proposed_name"] or p["speaker_label"]
            title = p["proposed_title"] or ""
            org = p["proposed_org"] or ""
            role = p["participant_role"] or ""
            line = f"- {name}"
            if title:
                line += f", {title}"
            if org:
                line += f" ({org})"
            if role:
                line += f" [{role}]"
            sections.append(line)

    # Committed items
    if committed_items:
        sections.append("\n## Items Committed to Tracker\n")
        sections.append(
            "These items were extracted from this conversation and have been "
            "confirmed and written to the tracking system:\n"
        )
        for item in committed_items:
            sections.append(f"### {item['item_type']}: {item.get('title', 'Untitled')}")
            data = item.get("proposed_data", {})
            if isinstance(data, str):
                try:
                    data = json.loads(data)
                except (json.JSONDecodeError, TypeError):
                    data = {}
            for key in (
                "title",
                "summary",
                "description",
                "status",
                "due_date",
                "assigned_to_person_id",
                "priority",
                "decision_result",
                "update_type",
                "readout_summary",
            ):
                val = data.get(key)
                if val:
                    sections.append(f"  {key}: {val}")
            sections.append("")

    # Full transcript
    segments = db.execute(
        """
        SELECT speaker_label, start_time, end_time,
               reviewed_text, cleaned_text, raw_text
        FROM transcripts
        WHERE communication_id = ?
        ORDER BY start_time
    """,
        (communication_id,),
    ).fetchall()

    if segments:
        speaker_names = {
            p["speaker_label"]: (p["proposed_name"] or p["speaker_label"])
            for p in participants
        }

        sections.append("\n## Full Transcript\n")
        for seg in segments:
            name = speaker_names.get(seg["speaker_label"], seg["speaker_label"])
            text = seg["reviewed_text"] or seg["cleaned_text"] or seg["raw_text"] or ""
            start = seg["start_time"] or 0
            end = seg["end_time"] or 0
            sections.append(f"[{start:.1f}-{end:.1f}] {name}: {text}")

    return "\n".join(sections)


# --- Committed items retrieval ---


def _get_committed_items(db, communication_id: str) -> list[dict]:
    rows = db.execute(
        """
        SELECT rbi.item_type, rbi.proposed_data, rbi.rationale, rbi.status
        FROM review_bundle_items rbi
        JOIN review_bundles rb ON rbi.bundle_id = rb.id
        WHERE rb.communication_id = ?
          AND rbi.status IN ('accepted', 'edited')
        ORDER BY rb.sort_order, rbi.sort_order
    """,
        (communication_id,),
    ).fetchall()

    items = []
    for row in rows:
        data = row["proposed_data"]
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except (json.JSONDecodeError, TypeError):
                data = {}
        items.append(
            {
                "item_type": row["item_type"],
                "proposed_data": data,
                "rationale": row["rationale"],
                "title": data.get("title", ""),
            }
        )
    return items


def _get_meeting_data_from_committed(db, communication_id: str) -> dict | None:
    row = db.execute(
        """
        SELECT rbi.proposed_data
        FROM review_bundle_items rbi
        JOIN review_bundles rb ON rbi.bundle_id = rb.id
        WHERE rb.communication_id = ?
          AND rbi.item_type = 'meeting_record'
          AND rbi.status IN ('accepted', 'edited')
        LIMIT 1
    """,
        (communication_id,),
    ).fetchone()

    if not row:
        return None

    data = row["proposed_data"]
    if isinstance(data, str):
        try:
            return json.loads(data)
        except (json.JSONDecodeError, TypeError):
            return None
    return data


# --- Main generation ---


async def generate_meeting_intelligence(
    db,
    communication_id: str,
    prompt_version: str = "v1.0.0",
) -> dict | None:
    """Generate structured meeting intelligence for a committed meeting.

    Returns the intelligence dict if generated, None if no meeting_record found.
    """
    meeting_data = _get_meeting_data_from_committed(db, communication_id)
    if not meeting_data:
        logger.info(
            "[%s] No meeting_record found -- skipping intelligence generation",
            communication_id[:8],
        )
        return None

    # Get the tracker meeting_id from writebacks
    wb_row = db.execute(
        """
        SELECT tw.target_record_id
        FROM tracker_writebacks tw
        WHERE tw.communication_id = ?
          AND tw.target_table = 'meetings'
        LIMIT 1
    """,
        (communication_id,),
    ).fetchone()

    meeting_id = wb_row["target_record_id"] if wb_row else None
    if not meeting_id:
        logger.warning(
            "[%s] Meeting committed but no tracker meeting_id in writebacks",
            communication_id[:8],
        )
        return None

    # Duration and participant count for tier gating
    comm = db.execute(
        "SELECT duration_seconds FROM communications WHERE id = ?", (communication_id,)
    ).fetchone()
    duration = comm["duration_seconds"] if comm else None

    participant_count = db.execute(
        "SELECT COUNT(*) as cnt FROM communication_participants WHERE communication_id = ?",
        (communication_id,),
    ).fetchone()["cnt"]

    tier = determine_tier(
        duration_seconds=duration,
        participant_count=participant_count,
        meeting_type=meeting_data.get("meeting_type"),
        boss_attends=bool(meeting_data.get("boss_attends")),
        external_parties=bool(meeting_data.get("external_parties_attend")),
    )

    logger.info(
        "[%s] Generating %s-tier meeting intelligence for meeting %s",
        communication_id[:8],
        tier.upper(),
        meeting_id[:8],
    )

    committed_items = _get_committed_items(db, communication_id)

    system_prompt = _load_prompt(prompt_version)
    user_prompt = _build_user_prompt(
        db,
        communication_id,
        meeting_data,
        committed_items,
        tier,
    )

    # Model selection by tier
    policy = load_policy()
    model_config = policy.get("model_config", {})
    if tier == "core":
        model = model_config.get("haiku_model", "claude-haiku-4-5-20251001")
        max_tokens = 4096
    else:
        model = model_config.get("primary_extraction_model", "claude-sonnet-4-20250514")
        max_tokens = 16384

    response: LLMResponse = await call_llm(
        db=db,
        communication_id=communication_id,
        stage="meeting_intelligence",
        model=model,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        max_tokens=max_tokens,
        temperature=0.1,
    )

    # Parse JSON response
    raw_text = response.text.strip()
    if raw_text.startswith("```"):
        lines = raw_text.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        raw_text = "\n".join(lines)

    try:
        intelligence = json.loads(raw_text)
    except json.JSONDecodeError as e:
        logger.error(
            "[%s] Failed to parse meeting intelligence JSON: %s\nRaw: %s",
            communication_id[:8],
            e,
            raw_text[:500],
        )
        return None

    # Store to DB
    intel_id = str(uuid.uuid4())
    _store_intelligence(
        db,
        intel_id,
        meeting_id,
        communication_id,
        tier,
        intelligence,
        response,
        prompt_version,
    )

    logger.info(
        "[%s] Meeting intelligence generated: tier=%s, meeting=%s, "
        "$%.4f (%d in + %d out tokens)",
        communication_id[:8],
        tier,
        meeting_id[:8],
        response.usage.cost_usd,
        response.usage.input_tokens,
        response.usage.output_tokens,
    )

    return intelligence


def _safe_text(val, default=""):
    """Ensure a value is a string suitable for SQLite TEXT column."""
    if val is None:
        return default if default else None
    if isinstance(val, (dict, list)):
        return json.dumps(val, default=str)
    return str(val)


def _store_intelligence(
    db, intel_id, meeting_id, communication_id, tier, intel, response, prompt_version
):
    layer1 = intel.get("layer_1_skim", {})
    layer2 = intel.get("layer_2_operating")
    layer3 = intel.get("layer_3_record")
    closing = intel.get("closing_block", {})

    db.execute(
        """
        INSERT INTO meeting_intelligence (
            id, meeting_id, communication_id, version, tier,
            executive_summary,
            decisions_made, non_decisions,
            action_items_summary, risks_surfaced, briefing_required,
            key_issues_discussed, participant_positions,
            dependencies_surfaced, what_changed_in_matter,
            commitments_made, recommended_next_move,
            purpose_and_context, materials_referenced,
            detailed_notes, tags,
            why_this_meeting_mattered, what_changed,
            what_i_need_to_do, what_boss_needs_to_know, what_can_wait,
            generated_by, prompt_version,
            input_tokens, output_tokens, cost_usd,
            created_at, updated_at
        ) VALUES (
            ?, ?, ?, 1, ?,
            ?,
            ?, ?,
            ?, ?, ?,
            ?, ?,
            ?, ?,
            ?, ?,
            ?, ?,
            ?, ?,
            ?, ?,
            ?, ?, ?,
            ?, ?,
            ?, ?, ?,
            datetime('now'), datetime('now')
        )
    """,
        (
            intel_id,
            meeting_id,
            communication_id,
            tier,
            _safe_text(layer1.get("executive_summary", "")),
            json.dumps(layer1.get("decisions_made", []), default=str),
            json.dumps(layer1.get("non_decisions", []), default=str),
            json.dumps(layer1.get("action_items_summary", []), default=str),
            json.dumps(layer1.get("risks_surfaced", []), default=str),
            json.dumps(layer1.get("briefing_required", {}), default=str),
            json.dumps(layer2.get("key_issues_discussed", []), default=str)
            if layer2
            else None,
            json.dumps(layer2.get("participant_positions", []), default=str)
            if layer2
            else None,
            json.dumps(layer2.get("dependencies_surfaced", []), default=str)
            if layer2
            else None,
            _safe_text(layer2.get("what_changed_in_matter")) if layer2 else None,
            json.dumps(layer2.get("commitments_made", []), default=str)
            if layer2
            else None,
            json.dumps(layer2.get("recommended_next_move", {}), default=str)
            if layer2
            else None,
            _safe_text(layer3.get("purpose_and_context")) if layer3 else None,
            json.dumps(layer3.get("materials_referenced", []), default=str)
            if layer3
            else None,
            _safe_text(layer3.get("detailed_notes")) if layer3 else None,
            json.dumps(layer3.get("tags", []), default=str) if layer3 else None,
            _safe_text(closing.get("why_this_meeting_mattered", "")),
            _safe_text(closing.get("what_changed", "")),
            _safe_text(closing.get("what_i_need_to_do", "")),
            _safe_text(closing.get("what_boss_needs_to_know", "")),
            _safe_text(closing.get("what_can_wait", "")),
            response.usage.model,
            prompt_version,
            response.usage.input_tokens,
            response.usage.output_tokens,
            response.usage.cost_usd,
        ),
    )
    db.commit()
