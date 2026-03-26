"""Extraction v3 runtime helpers and offline runner.

This module intentionally does not wire v3 into the live pipeline yet.
It provides:
1. Communication-packet builders for v3 prompt inputs
2. Deterministic resolution and routing between pass 1 and pass 2
3. A thin offline two-pass runner for evaluation
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Iterable, Optional

from app.config import PROMPT_BASE_DIR, load_policy
from app.pipeline.stages.extraction_v3_models import (
    CommunicationUnderstandingOutput,
    MATCHABLE_RECORD_TYPE_VALUES,
    Pass1Observation,
    PERSON_DETAIL_ALLOWED_FIELDS,
    RecordMatch,
    RecordMatches,
    ResolvedOrganization,
    ResolvedPerson,
    RoutingResolutionPackage,
    MatterRoutingAssessment,
    V3ExtractionOutput,
)

logger = logging.getLogger(__name__)

PROMPT_DIR = PROMPT_BASE_DIR / "extraction"
PASS1_PROMPT_NAME = "v3_0_0_pass1"
PASS2_PROMPT_NAME = "v3_0_0_pass2"
MAX_V3_ATTEMPTS = 2

_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")
_COMMUNICATION_KIND_ALIASES = {
    "audio_upload": "audio",
}
_OBSERVATION_TYPE_ALIASES = {
    "person_memory": "person_memory_signal",
    "institutional_memory": "institutional_memory_signal",
}
_DIRECTNESS_ALIASES = {
    "explicit_statement": "direct_statement",
    "explicit_commitment": "direct_commitment",
    "explicit_request": "direct_request",
}
_DURABILITY_ALIASES = {
    "temporary": "working",
    "long_term": "durable",
}
_MEMORY_VALUE_ALIASES = {
    "medium_high": "high",
    "moderate": "medium",
}
_PASS1_SUBTYPE_ALIASES = {
    "person_memory_signal": {
        "role": "biography",
        "title": "biography",
        "background": "biography",
        "management_style": "management_guidance",
    },
    "institutional_memory_signal": {
        "agency_culture": "process_norm",
        "office_culture": "process_norm",
        "operating_preference": "leadership_preference",
        "org_fact": "organization_fact",
    },
}


def _load_prompt(prompt_name: str) -> str:
    """Load a versioned v3 prompt by file stem or filename."""
    filename = prompt_name if prompt_name.endswith(".md") else f"{prompt_name}.md"
    path = PROMPT_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f"v3 extraction prompt not found: {path}")
    return path.read_text(encoding="utf-8")


def _parse_json_response(text: str) -> dict[str, Any]:
    """Parse an LLM JSON response, tolerating markdown fences."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines)
    return json.loads(cleaned)


def _normalize_pass1_payload(parsed: dict[str, Any]) -> dict[str, Any]:
    """Normalize common pass-1 alias labels before strict validation."""
    kind = parsed.get("communication_kind")
    if kind in _COMMUNICATION_KIND_ALIASES:
        parsed["communication_kind"] = _COMMUNICATION_KIND_ALIASES[kind]

    for observation in parsed.get("observations", []):
        obs_type = observation.get("observation_type")
        if obs_type in _OBSERVATION_TYPE_ALIASES:
            obs_type = _OBSERVATION_TYPE_ALIASES[obs_type]
            observation["observation_type"] = obs_type

        subtype = observation.get("observation_subtype")
        if (
            obs_type in _PASS1_SUBTYPE_ALIASES
            and subtype in _PASS1_SUBTYPE_ALIASES[obs_type]
        ):
            observation["observation_subtype"] = _PASS1_SUBTYPE_ALIASES[obs_type][
                subtype
            ]

        directness = observation.get("directness")
        if directness in _DIRECTNESS_ALIASES:
            observation["directness"] = _DIRECTNESS_ALIASES[directness]

        durability = observation.get("durability")
        if durability in _DURABILITY_ALIASES:
            observation["durability"] = _DURABILITY_ALIASES[durability]

        memory_value = observation.get("memory_value")
        if memory_value in _MEMORY_VALUE_ALIASES:
            observation["memory_value"] = _MEMORY_VALUE_ALIASES[memory_value]

    return parsed


def _normalize_pass2_payload(parsed: dict[str, Any]) -> dict[str, Any]:
    """Normalize minor pass-2 field-name drift before strict validation."""
    for bundle in parsed.get("bundles", []):
        for item in bundle.get("items", []):
            data = item.get("proposed_data")
            if not isinstance(data, dict):
                continue

            if item.get("item_type") == "context_note":
                if "body" not in data and "content" in data:
                    data["body"] = data.pop("content")
                data.pop("tags", None)

            if item.get("item_type") == "person_detail_update":
                fields = data.get("fields")
                if not isinstance(fields, dict):
                    fields = {}
                moved = {}
                for key in list(data.keys()):
                    if key in PERSON_DETAIL_ALLOWED_FIELDS:
                        moved[key] = data.pop(key)
                if moved:
                    fields = {**fields, **moved}
                if fields:
                    data["fields"] = fields

    return parsed


def _normalize_text(value: Optional[str]) -> str:
    """Normalize text for exact-ish matching."""
    if not value:
        return ""
    normalized = _NON_ALNUM_RE.sub(" ", value.lower()).strip()
    return " ".join(normalized.split())


def _token_set(value: Optional[str]) -> set[str]:
    """Return non-trivial normalized tokens."""
    return {token for token in _normalize_text(value).split() if len(token) > 2}


def _json_block(data: Any) -> str:
    """Format data as pretty JSON for prompts."""
    return (
        f"```json\n{json.dumps(data, indent=2, ensure_ascii=False, default=str)}\n```"
    )


def _preferred_message_text(message: dict[str, Any]) -> tuple[str, str]:
    """Choose the best available email text for prompting."""
    if message.get("enriched_text"):
        return message["enriched_text"], "enriched_text"
    if message.get("body_text"):
        return message["body_text"], "body_text"
    return "", "none"


def _preferred_transcript_text(segment: dict[str, Any]) -> tuple[str, str]:
    """Choose the best available transcript text for prompting."""
    if segment.get("enriched_text"):
        return segment["enriched_text"], "enriched_text"
    if segment.get("cleaned_text"):
        return segment["cleaned_text"], "cleaned_text"
    if segment.get("raw_text"):
        return segment["raw_text"], "raw_text"
    return "", "none"


def _scan_for_identifiers(text: str, hits: dict[str, set[str]]):
    """Scan text for RINs, docket numbers, and CFR citations."""
    for match in re.finditer(r"\b(\d{4}-[A-Z0-9]{2,4})\b", text):
        hits["rin"].add(match.group(1))
    for match in re.finditer(r"(?i)\bdocket\s*(?:no\.?\s*)?([A-Z0-9-]+)", text):
        hits["docket"].add(match.group(1))
    for match in re.finditer(
        r"\b(\d+\s*CFR\s*(?:Part\s*)?\d+(?:\.\d+)?)\b", text, re.IGNORECASE
    ):
        hits["cfr"].add(match.group(1))


def gather_v3_routing_seeds(db, communication_id: str) -> dict[str, Any]:
    """Gather deterministic routing seeds from reviewed participants/entities."""
    speaker_rows = db.execute(
        """
        SELECT tracker_person_id
        FROM communication_participants
        WHERE communication_id = ? AND tracker_person_id IS NOT NULL
        """,
        (communication_id,),
    ).fetchall()
    speaker_person_ids = {
        row["tracker_person_id"] for row in speaker_rows if row["tracker_person_id"]
    }

    entity_rows = db.execute(
        """
        SELECT tracker_person_id, tracker_org_id, mention_text, context_snippet
        FROM communication_entities
        WHERE communication_id = ? AND confirmed != -1
        """,
        (communication_id,),
    ).fetchall()
    entity_person_ids = {
        row["tracker_person_id"] for row in entity_rows if row["tracker_person_id"]
    }
    entity_org_ids = {
        row["tracker_org_id"] for row in entity_rows if row["tracker_org_id"]
    }

    identifier_hits = {"rin": set(), "docket": set(), "cfr": set()}
    topic_row = db.execute(
        "SELECT topic_segments_json FROM communications WHERE id = ?",
        (communication_id,),
    ).fetchone()
    if topic_row and topic_row["topic_segments_json"]:
        try:
            topic_data = json.loads(topic_row["topic_segments_json"])
            _scan_for_identifiers(json.dumps(topic_data, default=str), identifier_hits)
        except (json.JSONDecodeError, TypeError):
            pass

    for row in entity_rows:
        text = f"{row['mention_text'] or ''} {row['context_snippet'] or ''}"
        _scan_for_identifiers(text, identifier_hits)

    return {
        "speaker_person_ids": speaker_person_ids,
        "entity_person_ids": entity_person_ids,
        "entity_org_ids": entity_org_ids,
        "identifier_hits": identifier_hits,
    }


def _build_communication_packet(db, communication_id: str) -> dict[str, Any]:
    """Build the shared prompt-input packet for pass 1 and pass 2."""
    communication = db.execute(
        """
        SELECT id, source_type, original_filename, title, duration_seconds,
               topic_segments_json, sensitivity_flags, created_at
        FROM communications
        WHERE id = ?
        """,
        (communication_id,),
    ).fetchone()
    if communication is None:
        raise ValueError(f"Communication not found: {communication_id}")

    communication_dict = dict(communication)
    source_type = communication_dict.get("source_type") or "audio"

    participants = [
        dict(row)
        for row in db.execute(
            """
            SELECT speaker_label, tracker_person_id, proposed_name, proposed_title,
                   proposed_org, proposed_org_id, participant_email,
                   header_role, participant_role, confirmed
            FROM communication_participants
            WHERE communication_id = ?
            ORDER BY speaker_label, participant_email
            """,
            (communication_id,),
        ).fetchall()
    ]

    entities = [
        dict(row)
        for row in db.execute(
            """
            SELECT mention_text, entity_type, tracker_person_id, tracker_org_id,
                   proposed_name, proposed_title, proposed_org,
                   confidence, confirmed, mention_count, context_snippet
            FROM communication_entities
            WHERE communication_id = ? AND confirmed != -1
            ORDER BY mention_count DESC, mention_text
            """,
            (communication_id,),
        ).fetchall()
    ]

    enrichment_summary = None
    topics = []
    if communication_dict.get("topic_segments_json"):
        try:
            topic_data = json.loads(communication_dict["topic_segments_json"])
            enrichment_summary = topic_data.get("summary")
            topics = topic_data.get("topics", [])
        except (json.JSONDecodeError, TypeError, AttributeError):
            pass

    if source_type == "email":
        messages = []
        for row in db.execute(
            """
                SELECT id, message_index, sender_email, sender_name,
                       recipient_emails, cc_emails, timestamp,
                       subject, body_text, enriched_text, is_new, is_from_user
                FROM communication_messages
                WHERE communication_id = ?
                ORDER BY message_index
                """,
            (communication_id,),
        ).fetchall():
            message = dict(row)
            prompt_text, prompt_text_source = _preferred_message_text(message)
            messages.append(
                {
                    "id": message["id"],
                    "message_index": message["message_index"],
                    "sender_email": message["sender_email"],
                    "sender_name": message["sender_name"],
                    "recipient_emails": message["recipient_emails"],
                    "cc_emails": message["cc_emails"],
                    "timestamp": message["timestamp"],
                    "subject": message["subject"],
                    "is_new": message["is_new"],
                    "is_from_user": message["is_from_user"],
                    "text": prompt_text,
                    "text_source": prompt_text_source,
                }
            )
        attachments = [
            dict(row)
            for row in db.execute(
                """
                SELECT id, message_id, original_filename, mime_type,
                       file_size_bytes, extracted_text, text_extraction_status
                FROM communication_artifacts
                WHERE communication_id = ?
                ORDER BY original_filename
                """,
                (communication_id,),
            ).fetchall()
        ]
        content = {"kind": "email", "messages": messages, "attachments": attachments}
    else:
        transcripts = []
        for row in db.execute(
            """
                SELECT id, speaker_label, start_time, end_time,
                       cleaned_text, raw_text, enriched_text, confidence
                FROM transcripts
                WHERE communication_id = ?
                ORDER BY start_time
                """,
            (communication_id,),
        ).fetchall():
            transcript = dict(row)
            prompt_text, prompt_text_source = _preferred_transcript_text(transcript)
            transcripts.append(
                {
                    "id": transcript["id"],
                    "speaker_label": transcript["speaker_label"],
                    "start_time": transcript["start_time"],
                    "end_time": transcript["end_time"],
                    "confidence": transcript["confidence"],
                    "text": prompt_text,
                    "text_source": prompt_text_source,
                }
            )
        content = {"kind": "audio", "transcripts": transcripts}

    return {
        "communication": communication_dict,
        "participants": participants,
        "entities": entities,
        "enrichment_summary": enrichment_summary,
        "topics": topics,
        "content": content,
    }


def build_v3_pass1_user_prompt(db, communication_id: str) -> str:
    """Build the pass 1 prompt input."""
    packet = _build_communication_packet(db, communication_id)
    sections = [
        "## Communication",
        _json_block(packet["communication"]),
        "## Participants",
        _json_block(packet["participants"]),
        "## Confirmed Entities",
        _json_block(packet["entities"]),
        "## Enrichment Summary",
        packet["enrichment_summary"] or "None",
        "## Topics",
        _json_block(packet["topics"]),
        "## Content",
        _json_block(packet["content"]),
        "Return ONLY the JSON object described by the system prompt.",
    ]
    return "\n\n".join(sections)


def build_v3_pass2_user_prompt(
    db,
    communication_id: str,
    pass1_output: CommunicationUnderstandingOutput,
    routing_package: RoutingResolutionPackage,
) -> str:
    """Build the pass 2 prompt input."""
    packet = _build_communication_packet(db, communication_id)
    sections = [
        "## Communication",
        _json_block(packet["communication"]),
        "## Content",
        _json_block(packet["content"]),
        "## Pass 1 Output",
        _json_block(pass1_output.model_dump()),
        "## Routing And Resolution Package",
        _json_block(routing_package.model_dump()),
        "## Relevant Tracker Context",
        _json_block(routing_package.relevant_tracker_context),
        "Return ONLY the JSON object described by the system prompt.",
    ]
    return "\n\n".join(sections)


def _resolve_person_name(
    name: str, people: list[dict[str, Any]]
) -> tuple[Optional[str], float, str]:
    """Resolve a person name against tracker people."""
    if not name:
        return None, 0.0, "no_name"

    target = _normalize_text(name)
    exact_matches = [
        person
        for person in people
        if _normalize_text(person.get("full_name")) == target
    ]
    if len(exact_matches) == 1:
        return exact_matches[0]["id"], 0.95, "exact_name"
    return None, 0.0, "unresolved"


def _resolve_org_name(
    name: str, organizations: list[dict[str, Any]]
) -> tuple[Optional[str], float, str]:
    """Resolve an organization name or short name against tracker organizations."""
    if not name:
        return None, 0.0, "no_name"

    target = _normalize_text(name)
    exact_matches = [
        organization
        for organization in organizations
        if target
        in {
            _normalize_text(organization.get("name")),
            _normalize_text(organization.get("short_name")),
        }
    ]
    if len(exact_matches) == 1:
        return exact_matches[0]["id"], 0.95, "exact_name"
    return None, 0.0, "unresolved"


def _dedupe_resolved_people(
    pass1_output: CommunicationUnderstandingOutput,
    people: list[dict[str, Any]],
) -> list[ResolvedPerson]:
    """Resolve and dedupe people referenced in pass 1."""
    seen_ids: set[str] = set()
    resolved: list[ResolvedPerson] = []

    def add_candidate(
        name: Optional[str],
        tracker_person_id: Optional[str],
        source: str,
        confidence: float,
    ):
        if tracker_person_id:
            person = next(
                (entry for entry in people if entry["id"] == tracker_person_id), None
            )
            display_name = name or (person or {}).get("full_name")
            if person and display_name and tracker_person_id not in seen_ids:
                seen_ids.add(tracker_person_id)
                resolved.append(
                    ResolvedPerson(
                        name=display_name,
                        tracker_person_id=tracker_person_id,
                        resolution_confidence=max(confidence, 0.99),
                        source=source,
                    )
                )
                return

        if not name:
            return

        resolved_id, resolved_confidence, resolved_source = _resolve_person_name(
            name, people
        )
        if resolved_id and resolved_id not in seen_ids:
            seen_ids.add(resolved_id)
            resolved.append(
                ResolvedPerson(
                    name=name,
                    tracker_person_id=resolved_id,
                    resolution_confidence=resolved_confidence,
                    source=resolved_source,
                )
            )

    for participant in pass1_output.participants:
        add_candidate(
            participant.display_name,
            participant.tracker_person_id,
            "participant",
            participant.confidence,
        )

    for observation in pass1_output.observations:
        for speaker_ref in observation.speaker_refs:
            add_candidate(
                speaker_ref.name,
                speaker_ref.tracker_person_id,
                "observation_speaker",
                observation.confidence,
            )
        for entity_ref in observation.entity_refs:
            if entity_ref.entity_type == "person":
                add_candidate(
                    entity_ref.name,
                    entity_ref.tracker_id,
                    "observation_entity",
                    observation.confidence,
                )

    return resolved


def _dedupe_resolved_organizations(
    pass1_output: CommunicationUnderstandingOutput,
    organizations: list[dict[str, Any]],
) -> list[ResolvedOrganization]:
    """Resolve and dedupe organizations referenced in pass 1."""
    seen_ids: set[str] = set()
    resolved: list[ResolvedOrganization] = []

    def add_candidate(
        name: Optional[str],
        tracker_org_id: Optional[str],
        source: str,
        confidence: float,
    ):
        if tracker_org_id:
            organization = next(
                (entry for entry in organizations if entry["id"] == tracker_org_id),
                None,
            )
            display_name = name or (organization or {}).get("name")
            if organization and display_name and tracker_org_id not in seen_ids:
                seen_ids.add(tracker_org_id)
                resolved.append(
                    ResolvedOrganization(
                        name=display_name,
                        tracker_org_id=tracker_org_id,
                        resolution_confidence=max(confidence, 0.99),
                        source=source,
                    )
                )
                return

        if not name:
            return

        resolved_id, resolved_confidence, resolved_source = _resolve_org_name(
            name, organizations
        )
        if resolved_id and resolved_id not in seen_ids:
            seen_ids.add(resolved_id)
            resolved.append(
                ResolvedOrganization(
                    name=name,
                    tracker_org_id=resolved_id,
                    resolution_confidence=resolved_confidence,
                    source=resolved_source,
                )
            )

    for participant in pass1_output.participants:
        add_candidate(
            participant.organization_name,
            participant.tracker_org_id,
            "participant",
            participant.confidence,
        )

    for observation in pass1_output.observations:
        for entity_ref in observation.entity_refs:
            if entity_ref.entity_type == "organization":
                add_candidate(
                    entity_ref.name,
                    entity_ref.tracker_id,
                    "observation_entity",
                    observation.confidence,
                )

    return resolved


def _index_full_context(
    full_context: dict[str, Any],
) -> dict[str, dict[str, dict[str, Any]]]:
    """Index tracker context records by type and id."""
    matters = {matter["id"]: dict(matter) for matter in full_context.get("matters", [])}
    people = {person["id"]: dict(person) for person in full_context.get("people", [])}
    organizations = {
        organization["id"]: dict(organization)
        for organization in full_context.get("organizations", [])
    }
    meetings = {
        meeting["id"]: dict(meeting)
        for meeting in full_context.get("recent_meetings", [])
    }

    tasks: dict[str, dict[str, Any]] = {}
    decisions: dict[str, dict[str, Any]] = {}
    documents: dict[str, dict[str, Any]] = {}

    for matter in full_context.get("matters", []):
        matter_id = matter["id"]
        for task in matter.get("open_tasks", []):
            task_copy = dict(task)
            task_copy.setdefault("matter_id", matter_id)
            tasks[task_copy["id"]] = task_copy
        for decision in matter.get("open_decisions", []):
            decision_copy = dict(decision)
            decision_copy.setdefault("matter_id", matter_id)
            decisions[decision_copy["id"]] = decision_copy
        for document in matter.get("documents", []):
            document_copy = dict(document)
            document_copy.setdefault("matter_id", matter_id)
            documents[document_copy["id"]] = document_copy

    for task in full_context.get("standalone_tasks", []):
        task_copy = dict(task)
        task_copy.setdefault("matter_id", None)
        tasks[task_copy["id"]] = task_copy

    return {
        "person": people,
        "organization": organizations,
        "matter": matters,
        "task": tasks,
        "decision": decisions,
        "document": documents,
        "meeting": meetings,
    }


def _add_record_match(
    target: dict[tuple[str, str], RecordMatch],
    observation_id: str,
    record_id: str,
    score: float,
    reason: str,
):
    """Add the highest-scoring record match for an observation/record pair."""
    key = (observation_id, record_id)
    existing = target.get(key)
    if existing is None or score > existing.match_score:
        target[key] = RecordMatch(
            observation_id=observation_id,
            record_id=record_id,
            match_score=score,
            match_reason=reason,
        )


def _observation_text(observation: Pass1Observation) -> str:
    """Build a text blob for lightweight title matching."""
    hint_values = " ".join(str(value) for value in observation.field_hints.values())
    return _normalize_text(f"{observation.summary} {hint_values}")


def _maybe_add_title_based_matches(
    observation: Pass1Observation,
    records: dict[str, dict[str, Any]],
    match_store: dict[tuple[str, str], RecordMatch],
    minimum_overlap: float,
):
    """Add lightweight text matches against existing task/decision/document titles."""
    observation_tokens = _token_set(_observation_text(observation))
    if len(observation_tokens) < 2:
        return

    for record_id, record in records.items():
        title_tokens = _token_set(record.get("title"))
        if len(title_tokens) < 2:
            continue
        overlap = len(title_tokens & observation_tokens) / len(title_tokens)
        if overlap >= minimum_overlap:
            score = min(0.85, 0.45 + overlap * 0.4)
            _add_record_match(
                match_store,
                observation.id,
                record_id,
                score,
                f"title overlap with existing record '{record.get('title')}'",
            )


def _build_record_matches(
    pass1_output: CommunicationUnderstandingOutput,
    full_context: dict[str, Any],
) -> RecordMatches:
    """Build deterministic record matches from pass 1 references and tracker context."""
    indices = _index_full_context(full_context)
    grouped: dict[str, dict[tuple[str, str], RecordMatch]] = {
        record_type: {} for record_type in MATCHABLE_RECORD_TYPE_VALUES
    }

    for observation in pass1_output.observations:
        for candidate in observation.candidate_record_refs:
            if candidate.record_type not in MATCHABLE_RECORD_TYPE_VALUES:
                continue
            if candidate.record_id not in indices[candidate.record_type]:
                continue
            _add_record_match(
                grouped[candidate.record_type],
                observation.id,
                candidate.record_id,
                candidate.score,
                candidate.reason,
            )

        for candidate in observation.candidate_matter_refs:
            if candidate.matter_id in indices["matter"]:
                _add_record_match(
                    grouped["matter"],
                    observation.id,
                    candidate.matter_id,
                    candidate.score,
                    candidate.reason,
                )

        if observation.observation_type == "task_signal":
            _maybe_add_title_based_matches(
                observation, indices["task"], grouped["task"], minimum_overlap=0.6
            )
        elif observation.observation_type == "decision_signal":
            _maybe_add_title_based_matches(
                observation,
                indices["decision"],
                grouped["decision"],
                minimum_overlap=0.6,
            )
        elif observation.observation_type == "document_signal":
            _maybe_add_title_based_matches(
                observation,
                indices["document"],
                grouped["document"],
                minimum_overlap=0.7,
            )

    return RecordMatches(
        tasks=list(grouped["task"].values()),
        decisions=list(grouped["decision"].values()),
        people=list(grouped["person"].values()),
        organizations=list(grouped["organization"].values()),
        documents=list(grouped["document"].values()),
        matters=list(grouped["matter"].values()),
        meetings=list(grouped["meeting"].values()),
    )


def _compute_seed_matter_hits(
    full_context: dict[str, Any],
    routing_seeds: dict[str, Any],
) -> dict[str, list[str]]:
    """Find matters implicated by participants, entities, and identifiers."""
    speaker_person_ids = routing_seeds.get("speaker_person_ids", set())
    entity_person_ids = routing_seeds.get("entity_person_ids", set())
    entity_org_ids = routing_seeds.get("entity_org_ids", set())
    identifier_hits = routing_seeds.get(
        "identifier_hits", {"rin": set(), "docket": set(), "cfr": set()}
    )

    people_ids = set(speaker_person_ids) | set(entity_person_ids)
    seed_hits: dict[str, list[str]] = {}

    for matter in full_context.get("matters", []):
        reasons: list[str] = []

        for field in (
            "assigned_to_person_id",
            "supervisor_person_id",
            "next_step_assigned_to_person_id",
        ):
            if matter.get(field) in people_ids and matter.get(field):
                reasons.append(f"{field} overlaps a confirmed participant/entity")

        for stakeholder in matter.get("stakeholders", []):
            if stakeholder.get("person_id") in people_ids and stakeholder.get(
                "person_id"
            ):
                reasons.append(
                    "confirmed participant/entity is already a matter stakeholder"
                )

        for field in (
            "requesting_organization_id",
            "client_organization_id",
            "reviewing_organization_id",
            "lead_external_org_id",
        ):
            if matter.get(field) in entity_org_ids and matter.get(field):
                reasons.append(f"{field} overlaps a confirmed organization")

        for organization in matter.get("organizations", []):
            if organization.get(
                "organization_id"
            ) in entity_org_ids and organization.get("organization_id"):
                reasons.append("confirmed organization is already linked to the matter")

        if matter.get("rin") and matter["rin"] in identifier_hits.get("rin", set()):
            reasons.append("RIN mentioned in the communication matches this matter")
        if matter.get("docket_number") and matter[
            "docket_number"
        ] in identifier_hits.get("docket", set()):
            reasons.append(
                "docket number mentioned in the communication matches this matter"
            )

        matter_cfr = _normalize_text(matter.get("cfr_citation"))
        for cfr_hit in identifier_hits.get("cfr", set()):
            if matter_cfr and _normalize_text(cfr_hit) in matter_cfr:
                reasons.append(
                    "CFR citation mentioned in the communication matches this matter"
                )
                break

        if reasons:
            seed_hits[matter["id"]] = reasons

    return seed_hits


def _score_matter_candidates(
    pass1_output: CommunicationUnderstandingOutput,
    full_context: dict[str, Any],
    routing_seeds: dict[str, Any],
    record_matches: RecordMatches,
) -> tuple[dict[str, float], dict[str, list[str]]]:
    """Score candidate matters using pass 1 observations and deterministic hits."""
    matter_scores: dict[str, float] = {}
    matter_basis: dict[str, list[str]] = {}
    matters_by_id = {matter["id"]: matter for matter in full_context.get("matters", [])}
    seed_hits = _compute_seed_matter_hits(full_context, routing_seeds)

    def add_score(matter_id: str, amount: float, reason: str):
        if matter_id not in matters_by_id:
            return
        matter_scores[matter_id] = matter_scores.get(matter_id, 0.0) + amount
        matter_basis.setdefault(matter_id, []).append(reason)

    for matter_id, reasons in seed_hits.items():
        for reason in reasons:
            add_score(matter_id, 0.35, reason)

    for observation in pass1_output.observations:
        for candidate in observation.candidate_matter_refs:
            add_score(
                candidate.matter_id,
                candidate.score,
                f"pass1 candidate matter ref: {candidate.reason}",
            )

        observation_text_tokens = _token_set(_observation_text(observation))
        for matter in full_context.get("matters", []):
            title_tokens = _token_set(matter.get("title"))
            if len(title_tokens) >= 2:
                overlap = len(title_tokens & observation_text_tokens) / len(
                    title_tokens
                )
                if overlap >= 0.8:
                    add_score(
                        matter["id"],
                        0.25,
                        "observation text strongly overlaps the matter title",
                    )

    indices = _index_full_context(full_context)
    for match in record_matches.tasks:
        task = indices["task"].get(match.record_id)
        if task and task.get("matter_id"):
            add_score(
                task["matter_id"],
                0.8 * match.match_score,
                "matched open task already linked to the matter",
            )

    for match in record_matches.decisions:
        decision = indices["decision"].get(match.record_id)
        if decision and decision.get("matter_id"):
            add_score(
                decision["matter_id"],
                0.8 * match.match_score,
                "matched open decision already linked to the matter",
            )

    for match in record_matches.documents:
        document = indices["document"].get(match.record_id)
        if document and document.get("matter_id"):
            add_score(
                document["matter_id"],
                0.8 * match.match_score,
                "matched document already linked to the matter",
            )

    return matter_scores, matter_basis


def _is_new_matter_candidate(
    pass1_output: CommunicationUnderstandingOutput, matter_scores: dict[str, float]
) -> bool:
    """Heuristic for likely new workstreams when nothing routes cleanly."""
    if matter_scores:
        return False

    durable_operational_signals = [
        observation
        for observation in pass1_output.observations
        if observation.observation_type
        in {"task_signal", "decision_signal", "matter_signal", "document_signal"}
        and observation.durability != "ephemeral"
    ]
    return len(durable_operational_signals) >= 2


def _build_matter_routing_assessment(
    pass1_output: CommunicationUnderstandingOutput,
    full_context: dict[str, Any],
    routing_seeds: dict[str, Any],
    record_matches: RecordMatches,
) -> MatterRoutingAssessment:
    """Classify matter routing using deterministic scores."""
    matter_scores, matter_basis = _score_matter_candidates(
        pass1_output, full_context, routing_seeds, record_matches
    )
    ranked = sorted(matter_scores.items(), key=lambda item: item[1], reverse=True)
    new_matter_candidate = _is_new_matter_candidate(pass1_output, matter_scores)

    if not ranked:
        if new_matter_candidate:
            return MatterRoutingAssessment(
                routing_confidence="new_matter_candidate",
                routing_basis=["no existing matter cleared the routing threshold"],
                new_matter_candidate=True,
            )
        return MatterRoutingAssessment(
            routing_confidence="standalone",
            routing_basis=[],
            standalone_reason="No existing matter scored above the routing threshold.",
            new_matter_candidate=False,
        )

    primary_matter_id, primary_score = ranked[0]
    secondary_candidates = [
        matter_id for matter_id, score in ranked[1:] if score >= 0.9
    ]
    second_score = ranked[1][1] if len(ranked) > 1 else 0.0

    if primary_score >= 1.5 and primary_score >= second_score + 0.35:
        confidence = "high"
    elif (
        primary_score >= 0.9
        and secondary_candidates
        and second_score >= primary_score * 0.8
    ):
        confidence = "multi"
    elif primary_score >= 0.9:
        confidence = "medium"
    elif new_matter_candidate:
        return MatterRoutingAssessment(
            routing_confidence="new_matter_candidate",
            routing_basis=[
                "existing matches were weaker than the new-matter threshold"
            ],
            new_matter_candidate=True,
        )
    else:
        return MatterRoutingAssessment(
            routing_confidence="standalone",
            routing_basis=[],
            standalone_reason="Existing matter matches were too weak to route confidently.",
            new_matter_candidate=False,
        )

    basis = list(dict.fromkeys(matter_basis.get(primary_matter_id, [])))
    return MatterRoutingAssessment(
        primary_matter_id=primary_matter_id,
        secondary_matter_ids=secondary_candidates if confidence == "multi" else [],
        routing_confidence=confidence,
        routing_basis=basis[:6],
        new_matter_candidate=new_matter_candidate,
    )


def _select_records_by_ids(
    index: dict[str, dict[str, Any]], ids: Iterable[str]
) -> list[dict[str, Any]]:
    """Select indexed records by id, preserving uniqueness and order."""
    seen: set[str] = set()
    records: list[dict[str, Any]] = []
    for record_id in ids:
        if record_id in seen or record_id not in index:
            continue
        seen.add(record_id)
        records.append(index[record_id])
    return records


def _build_relevant_tracker_context(
    full_context: dict[str, Any],
    routing_assessment: MatterRoutingAssessment,
    record_matches: RecordMatches,
    resolved_people: list[ResolvedPerson],
    resolved_organizations: list[ResolvedOrganization],
) -> dict[str, Any]:
    """Narrow tracker context for pass 2."""
    indices = _index_full_context(full_context)
    matter_ids: list[str] = []
    if routing_assessment.primary_matter_id:
        matter_ids.append(routing_assessment.primary_matter_id)
    matter_ids.extend(routing_assessment.secondary_matter_ids)

    matched_task_ids = [match.record_id for match in record_matches.tasks]
    matched_decision_ids = [match.record_id for match in record_matches.decisions]
    matched_document_ids = [match.record_id for match in record_matches.documents]
    matched_meeting_ids = [match.record_id for match in record_matches.meetings]

    people_ids = [person.tracker_person_id for person in resolved_people]
    organization_ids = [
        organization.tracker_org_id for organization in resolved_organizations
    ]

    return {
        "matters": _select_records_by_ids(indices["matter"], matter_ids),
        "matched_tasks": _select_records_by_ids(indices["task"], matched_task_ids),
        "matched_decisions": _select_records_by_ids(
            indices["decision"], matched_decision_ids
        ),
        "matched_documents": _select_records_by_ids(
            indices["document"], matched_document_ids
        ),
        "recent_meetings": _select_records_by_ids(
            indices["meeting"], matched_meeting_ids
        ),
        "people": _select_records_by_ids(indices["person"], people_ids),
        "organizations": _select_records_by_ids(
            indices["organization"], organization_ids
        ),
    }


def build_routing_resolution_package_from_context(
    communication_id: str,
    pass1_output: CommunicationUnderstandingOutput,
    full_context: dict[str, Any],
    routing_seeds: Optional[dict[str, Any]] = None,
) -> RoutingResolutionPackage:
    """Pure deterministic routing package builder."""
    routing_seeds = routing_seeds or {
        "speaker_person_ids": set(),
        "entity_person_ids": set(),
        "entity_org_ids": set(),
        "identifier_hits": {"rin": set(), "docket": set(), "cfr": set()},
    }
    people = full_context.get("people", [])
    organizations = full_context.get("organizations", [])

    resolved_people = _dedupe_resolved_people(pass1_output, people)
    resolved_organizations = _dedupe_resolved_organizations(pass1_output, organizations)
    record_matches = _build_record_matches(pass1_output, full_context)
    matter_routing = _build_matter_routing_assessment(
        pass1_output, full_context, routing_seeds, record_matches
    )
    relevant_tracker_context = _build_relevant_tracker_context(
        full_context,
        matter_routing,
        record_matches,
        resolved_people,
        resolved_organizations,
    )

    return RoutingResolutionPackage(
        communication_id=communication_id,
        resolved_people=resolved_people,
        resolved_organizations=resolved_organizations,
        matter_routing=matter_routing,
        record_matches=record_matches,
        relevant_tracker_context=relevant_tracker_context,
    )


def build_routing_resolution_package(
    db,
    communication_id: str,
    pass1_output: CommunicationUnderstandingOutput,
    full_context: dict[str, Any],
) -> RoutingResolutionPackage:
    """DB-aware deterministic routing package builder."""
    routing_seeds = gather_v3_routing_seeds(db, communication_id)
    return build_routing_resolution_package_from_context(
        communication_id=communication_id,
        pass1_output=pass1_output,
        full_context=full_context,
        routing_seeds=routing_seeds,
    )


async def _call_v3_json_model(
    db,
    communication_id: str,
    stage: str,
    model: str,
    system_prompt: str,
    user_prompt: str,
    output_model,
    max_tokens: int = 8192,
) -> tuple[Any, str, dict[str, Any]]:
    """Call the shared LLM client and validate JSON into a pydantic model."""
    from pydantic import ValidationError
    from app.llm.client import call_llm, LLMError

    last_error: Optional[str] = None
    for attempt in range(1, MAX_V3_ATTEMPTS + 1):
        prompt_for_attempt = (
            user_prompt
            if attempt == 1
            else (
                user_prompt
                + "\n\n## Retry Note\n"
                + f"Previous attempt failed validation or JSON parsing: {last_error}\n"
                + "Return ONLY the JSON object."
            )
        )
        try:
            response = await call_llm(
                db=db,
                communication_id=communication_id,
                stage=stage,
                model=model,
                system_prompt=system_prompt,
                user_prompt=prompt_for_attempt,
                max_tokens=max_tokens,
                temperature=0.0,
            )
            parsed = _parse_json_response(response.text)
            if output_model is CommunicationUnderstandingOutput:
                parsed = _normalize_pass1_payload(parsed)
            elif output_model is V3ExtractionOutput:
                parsed = _normalize_pass2_payload(parsed)
            validated = output_model(**parsed)
            usage = {
                "model": model,
                "attempt": attempt,
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
                "cost_usd": response.usage.cost_usd,
                "processing_seconds": response.usage.processing_seconds,
            }
            return validated, response.text, usage
        except (json.JSONDecodeError, ValidationError, LLMError) as exc:
            last_error = str(exc)
            if attempt == MAX_V3_ATTEMPTS:
                raise RuntimeError(
                    f"{stage} failed after {attempt} attempts: {exc}"
                ) from exc

    raise RuntimeError(f"{stage} failed unexpectedly")


async def run_v3_extraction_offline(
    db,
    communication_id: str,
    *,
    pass1_model: Optional[str] = None,
    pass2_model: Optional[str] = None,
    full_context: Optional[dict[str, Any]] = None,
    pass1_prompt_name: str = PASS1_PROMPT_NAME,
    pass2_prompt_name: str = PASS2_PROMPT_NAME,
) -> dict[str, Any]:
    """Run the two-pass v3 flow without touching review bundles or writeback."""
    policy = load_policy()
    default_model = policy.get("model_config", {}).get(
        "primary_extraction_model",
        "claude-sonnet-4-20250514",
    )
    pass1_model = pass1_model or default_model
    pass2_model = pass2_model or default_model

    if full_context is None:
        from app.pipeline.stages.extraction import _fetch_tracker_context

        full_context = await _fetch_tracker_context()

    pass1_system_prompt = _load_prompt(pass1_prompt_name)
    pass2_system_prompt = _load_prompt(pass2_prompt_name)
    pass1_user_prompt = build_v3_pass1_user_prompt(db, communication_id)

    pass1_output, pass1_raw, pass1_usage = await _call_v3_json_model(
        db=db,
        communication_id=communication_id,
        stage="extracting_v3_pass1",
        model=pass1_model,
        system_prompt=pass1_system_prompt,
        user_prompt=pass1_user_prompt,
        output_model=CommunicationUnderstandingOutput,
    )

    routing_package = build_routing_resolution_package(
        db, communication_id, pass1_output, full_context
    )
    pass2_user_prompt = build_v3_pass2_user_prompt(
        db, communication_id, pass1_output, routing_package
    )

    pass2_output, pass2_raw, pass2_usage = await _call_v3_json_model(
        db=db,
        communication_id=communication_id,
        stage="extracting_v3_pass2",
        model=pass2_model,
        system_prompt=pass2_system_prompt,
        user_prompt=pass2_user_prompt,
        output_model=V3ExtractionOutput,
    )

    return {
        "communication_id": communication_id,
        "prompts": {
            "pass1": f"{pass1_prompt_name}.md"
            if not pass1_prompt_name.endswith(".md")
            else pass1_prompt_name,
            "pass2": f"{pass2_prompt_name}.md"
            if not pass2_prompt_name.endswith(".md")
            else pass2_prompt_name,
        },
        "models": {"pass1": pass1_model, "pass2": pass2_model},
        "usage": {"pass1": pass1_usage, "pass2": pass2_usage},
        "pass1": pass1_output.model_dump(),
        "routing": routing_package.model_dump(),
        "pass2": pass2_output.model_dump(),
        "raw_outputs": {"pass1": pass1_raw, "pass2": pass2_raw},
    }
