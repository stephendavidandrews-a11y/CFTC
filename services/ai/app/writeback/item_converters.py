"""Convert reviewed bundle items to tracker batch operations.

Each converter function takes (item_dict, bundle_dict, refs_dict) and returns
a list of (operation_dict, source_item_id) tuples.

The refs dict is mutable — converters register forward references for
entities they create (new orgs, new people, new matters) so that later
items can use $ref: references.

Convention:
- refs["$matter"] = client_id for the bundle's target matter (new_matter bundles)
- refs["person:<full_name>"] = client_id for newly created people
- refs["org:<name>"] = client_id for newly created organizations

v2 additions: task_update, decision_update, org_detail_update, context_note,
person_detail_update converters. convert_task handles tracks_task_ref and
trigger_description. convert_follow_up removed (follow_ups are now tasks
with task_mode: "follow_up").
"""

import json
import logging

logger = logging.getLogger(__name__)


# Fields on the people table that person_detail_update can write
PEOPLE_TABLE_FIELDS = {
    "relationship_category",
    "email",
    "phone",
    "assistant_name",
    "assistant_contact",
    "substantive_areas",
    "manager_person_id",
}


def _external_refs(communication_id: str, bundle_id: str, item_id: str) -> str:
    """Standard external_refs JSON for all AI-created records."""
    return json.dumps(
        {
            "ai_communication_id": communication_id,
            "ai_bundle_id": bundle_id,
            "ai_bundle_item_id": item_id,
        }
    )


def _resolve_matter_id(bundle: dict, refs: dict) -> str | None:
    """Resolve the matter_id for items in this bundle."""
    if bundle["bundle_type"] == "matter":
        return bundle["target_matter_id"]
    elif bundle["bundle_type"] == "new_matter" and "$matter" in refs:
        return f"$ref:{refs['$matter']}"
    return None


def _resolve_ref(value: str | None, refs: dict, prefix: str) -> str | None:
    """Resolve a value that might be a forward reference."""
    if not value:
        return None
    key = f"{prefix}:{value}"
    if key in refs:
        return f"$ref:{refs[key]}"
    return value


# ═══════════════════════════════════════════════════════════════════════════
# Bundle-level converters
# ═══════════════════════════════════════════════════════════════════════════


# Fields that belong on extension tables, not the base matters table
_RULEMAKING_FIELDS = {
    "regulatory_stage", "workflow_status", "rin", "current_comment_period_closes",
    "federal_register_citation", "unified_agenda_priority", "cfr_citation",
    "docket_number", "fr_doc_number", "interagency_role", "is_petition",
    "petition_disposition", "review_trigger",
}
_GUIDANCE_FIELDS = {
    "instrument_type", "published_in_fr", "cftc_letter_number", "request_date",
    "requestor_name", "requestor_organization_id", "requestor_counsel",
    "issuing_office_id", "signatory_person_id", "staff_contact_person_id",
    "cea_provisions", "cfr_provisions", "legal_question", "conditions_summary",
    "amends_matter_id", "prior_letter_number", "workflow_status",
    "issuance_date", "expiration_date",
}
_ENFORCEMENT_FIELDS = {
    "requesting_division_id", "enforcement_reference", "legal_issue_type",
    "support_type", "litigation_stage", "court_or_forum", "deadline_source",
    "workflow_status", "privilege_flags", "is_confidential",
}

_TYPE_TO_TABLE = {
    "rulemaking": ("matter_rulemaking", _RULEMAKING_FIELDS),
    "guidance": ("matter_guidance", _GUIDANCE_FIELDS),
    "enforcement": ("matter_enforcement", _ENFORCEMENT_FIELDS),
}


def _build_extension_op(proposed: dict, matter_type: str, matter_client_id: str, bundle: dict) -> dict | None:
    """Build an INSERT op for the type-specific extension table, if applicable."""
    mapping = _TYPE_TO_TABLE.get(matter_type)
    if not mapping:
        return None  # congressional, briefing, etc. have no extension table

    table, fields = mapping
    ext_data = {k: proposed.get(k) for k in fields if proposed.get(k) is not None}
    if not ext_data:
        # Even with no explicit fields, create the extension row for integrity
        ext_data = {}

    ext_data["matter_id"] = f"$ref:{matter_client_id}"

    return {
        "op": "insert",
        "table": table,
        "data": ext_data,
    }


def convert_new_matter_bundle(
    bundle: dict, refs: dict
) -> list[tuple[dict, str | None]]:
    """Convert a new_matter bundle's proposed_matter to a matters INSERT.

    This is the first operation in a new_matter bundle's batch.
    Returns list of (op_dict, None) tuples — None item_id because this is
    bundle-level.  May emit a second INSERT for the type-specific extension
    table (matter_rulemaking, matter_guidance, or matter_enforcement).
    """
    proposed = bundle.get("proposed_matter")
    if not proposed:
        return []

    client_id = f"new-matter-{bundle['id']}"
    refs["$matter"] = client_id

    op = {
        "op": "insert",
        "table": "matters",
        "client_id": client_id,
        "data": {
            "title": proposed.get("title"),
            "matter_type": proposed.get("matter_type"),
            "description": proposed.get("description"),
            "status": proposed.get("status", "new intake"),
            "priority": proposed.get("priority"),
            "sensitivity": proposed.get("sensitivity"),
            "blocker": proposed.get("blocker"),
            "next_step": proposed.get("next_step"),
            "source": "ai",
            "source_id": bundle["id"],
            "ai_confidence": bundle.get("confidence"),
            "automation_hold": 1,
            "external_refs": json.dumps(
                {
                    "ai_communication_id": bundle.get(
                        "communication_id",
                        # communication_id not on the tree dict, injected by committer
                        "",
                    ),
                    "ai_bundle_id": bundle["id"],
                }
            ),
        },
    }
    # Remove None values — tracker schema may reject NULLs for some columns
    op["data"] = {k: v for k, v in op["data"].items() if v is not None}

    ops = [(op, None)]

    # After the base matter op, check if we need an extension table insert
    matter_type = proposed.get("matter_type")
    ext_op = _build_extension_op(proposed, matter_type, client_id, bundle)
    if ext_op:
        ops.append((ext_op, None))

    return ops


# ═══════════════════════════════════════════════════════════════════════════
# Item-level converters
# ═══════════════════════════════════════════════════════════════════════════


def convert_new_organization(
    item: dict, bundle: dict, refs: dict
) -> list[tuple[dict, str]]:
    data = item["proposed_data"]
    client_id = f"new-org-{item['id']}"
    name = data.get("name", "")
    refs[f"org:{name}"] = client_id

    op = {
        "op": "insert",
        "table": "organizations",
        "client_id": client_id,
        "data": {
            "name": name,
            "organization_type": data.get("organization_type"),
            "jurisdiction": data.get("jurisdiction"),
            "notes": data.get("notes"),
            "is_active": 1,
            "source": "ai",
            "source_id": item["id"],
            "external_refs": _external_refs(
                bundle.get("_communication_id", ""), bundle["id"], item["id"]
            ),
        },
    }
    op["data"] = {k: v for k, v in op["data"].items() if v is not None}
    return [(op, item["id"])]


def convert_new_person(item: dict, bundle: dict, refs: dict) -> list[tuple[dict, str]]:
    data = item["proposed_data"]
    client_id = f"new-person-{item['id']}"
    full_name = data.get("full_name", "")
    refs[f"person:{full_name}"] = client_id

    op_data = {
        "full_name": full_name,
        "title": data.get("title"),
        "organization_id": _resolve_ref(data.get("organization_id"), refs, "org")
        or _resolve_ref(data.get("organization_name"), refs, "org"),
        "email": data.get("email"),
        "phone": data.get("phone"),
        "relationship_category": data.get("relationship_category"),
        "substantive_areas": data.get("substantive_areas"),
        "is_active": 1,
        "source": "ai",
        "source_id": item["id"],
        "external_refs": _external_refs(
            bundle.get("_communication_id", ""), bundle["id"], item["id"]
        ),
    }
    op_data = {k: v for k, v in op_data.items() if v is not None}

    return [
        (
            {
                "op": "insert",
                "table": "people",
                "client_id": client_id,
                "data": op_data,
            },
            item["id"],
        )
    ]


def convert_task(item: dict, bundle: dict, refs: dict) -> list[tuple[dict, str]]:
    data = item["proposed_data"]
    matter_id = data.get("matter_id") or _resolve_matter_id(bundle, refs)

    op_data = {
        "title": data["title"],
        "matter_id": matter_id,
        "description": data.get("description"),
        "task_type": data.get("task_type"),
        "status": data.get("status", "not started"),
        "task_mode": data.get("task_mode"),
        "priority": data.get("priority"),
        "assigned_to_person_id": _resolve_ref(data.get("assigned_to"), refs, "person")
        or data.get("assigned_to_person_id"),
        "delegated_by_person_id": data.get("delegated_by_person_id"),
        "supervising_person_id": data.get("supervising_person_id"),
        "waiting_on_person_id": data.get("waiting_on_person_id"),
        "waiting_on_org_id": data.get("waiting_on_org_id"),
        "waiting_on_description": data.get("waiting_on_description"),
        "trigger_description": data.get("trigger_description"),
        "expected_output": data.get("expected_output"),
        "due_date": data.get("due_date"),
        "deadline_type": data.get("deadline_type"),
        "next_follow_up_date": data.get("next_follow_up_date"),
        "source": "ai",
        "source_id": item["id"],
        "ai_confidence": item.get("confidence"),
        "automation_hold": 1,
        "external_refs": _external_refs(
            bundle.get("_communication_id", ""), bundle["id"], item["id"]
        ),
    }

    # Handle tracks_task_ref ($ref: syntax — batch endpoint resolves)
    tracks_ref = data.get("tracks_task_ref")
    if tracks_ref and isinstance(tracks_ref, str) and tracks_ref.startswith("$ref:"):
        op_data["tracks_task_id"] = tracks_ref

    op_data = {k: v for k, v in op_data.items() if v is not None}

    op = {
        "op": "insert",
        "table": "tasks",
        "data": op_data,
    }

    # If this task has a _client_id (set by committer for paired-task resolution),
    # add it to the batch op so $ref: references from follow_up tasks resolve
    client_id = data.get("_client_id")
    if client_id:
        op["client_id"] = client_id

    return [(op, item["id"])]


def convert_task_update(item: dict, bundle: dict, refs: dict) -> list[tuple[dict, str]]:
    """Produce a batch update operation for an existing task."""
    data = item["proposed_data"]
    task_id = data.get("existing_task_id")
    changes = data.get("changes", {})

    if not changes or not task_id:
        return []

    # Resolve any person/org references in changes
    for field in ("assigned_to_person_id", "waiting_on_person_id"):
        val = changes.get(field)
        if val:
            resolved = _resolve_ref(val, refs, "person")
            if resolved:
                changes[field] = resolved

    for field in ("waiting_on_org_id",):
        val = changes.get(field)
        if val:
            resolved = _resolve_ref(val, refs, "org")
            if resolved:
                changes[field] = resolved

    return [
        (
            {
                "op": "update",
                "table": "tasks",
                "record_id": task_id,
                "data": changes,
            },
            item["id"],
        )
    ]


def convert_decision(item: dict, bundle: dict, refs: dict) -> list[tuple[dict, str]]:
    data = item["proposed_data"]
    matter_id = data.get("matter_id") or _resolve_matter_id(bundle, refs)

    op_data = {
        "title": data["title"],
        "matter_id": matter_id,
        "decision_type": data.get("decision_type"),
        "status": data.get("status"),
        "decision_assigned_to_person_id": data.get("decision_assigned_to_person_id"),
        "decision_due_date": data.get("decision_due_date"),
        "options_summary": data.get("options_summary"),
        "recommended_option": data.get("recommended_option"),
        "decision_result": data.get("decision_result"),
        "made_at": data.get("made_at"),
        "notes": data.get("notes"),
        "source": "ai",
        "source_id": item["id"],
        "ai_confidence": item.get("confidence"),
        "automation_hold": 1,
        "external_refs": _external_refs(
            bundle.get("_communication_id", ""), bundle["id"], item["id"]
        ),
    }
    op_data = {k: v for k, v in op_data.items() if v is not None}

    return [
        (
            {
                "op": "insert",
                "table": "decisions",
                "data": op_data,
            },
            item["id"],
        )
    ]


def convert_decision_update(
    item: dict, bundle: dict, refs: dict
) -> list[tuple[dict, str]]:
    """Produce a batch update operation for an existing decision."""
    data = item["proposed_data"]
    decision_id = data.get("existing_decision_id")
    changes = data.get("changes", {})

    if not changes or not decision_id:
        return []

    for field in ("decision_assigned_to_person_id",):
        val = changes.get(field)
        if val:
            resolved = _resolve_ref(val, refs, "person")
            if resolved:
                changes[field] = resolved

    return [
        (
            {
                "op": "update",
                "table": "decisions",
                "record_id": decision_id,
                "data": changes,
            },
            item["id"],
        )
    ]


def convert_matter_update(
    item: dict, bundle: dict, refs: dict
) -> list[tuple[dict, str]]:
    data = item["proposed_data"]
    matter_id = data.get("matter_id") or _resolve_matter_id(bundle, refs)

    op_data = {
        "matter_id": matter_id,
        "update_type": data.get("update_type"),
        "summary": data["summary"],
    }
    op_data = {k: v for k, v in op_data.items() if v is not None}

    return [
        (
            {
                "op": "insert",
                "table": "matter_updates",
                "data": op_data,
            },
            item["id"],
        )
    ]


def convert_status_change(
    item: dict, bundle: dict, refs: dict
) -> list[tuple[dict, str]]:
    data = item["proposed_data"]
    matter_id = data.get("matter_id") or _resolve_matter_id(bundle, refs)

    if not matter_id:
        logger.warning(
            "status_change item %s has no matter_id — skipping", item["id"][:8]
        )
        return []

    update_data = {}
    field = data.get("field", "status")
    new_value = data.get("new_value")
    if field and new_value:
        update_data[field] = new_value

    if not update_data:
        return []

    # Route to extension table if the field lives there
    target_table = data.get("target_table", "matters")
    if target_table not in ("matters", "matter_rulemaking", "matter_guidance", "matter_enforcement"):
        target_table = "matters"

    return [
        (
            {
                "op": "update",
                "table": target_table,
                "record_id": matter_id,
                "data": update_data,
            },
            item["id"],
        )
    ]


def convert_meeting_record(
    item: dict, bundle: dict, refs: dict
) -> list[tuple[dict, str]]:
    """Compound: 1 item → meeting INSERT + participant INSERTs + matter link INSERTs."""
    data = item["proposed_data"]
    meeting_client_id = f"meeting-{item['id']}"
    comm_id = bundle.get("_communication_id", "")

    ops = []

    # Op 1: INSERT meeting
    meeting_data = {
        "title": data["title"],
        "meeting_type": data.get("meeting_type"),
        "date_time_start": data.get("date") or data.get("date_time_start"),
        "date_time_end": data.get("date_time_end"),
        "purpose": data.get("purpose"),
        "readout_summary": data.get("readout_summary"),
        "boss_attends": 1 if data.get("boss_attends") else 0,
        "source": "ai",
        "source_id": item["id"],
        "external_refs": _external_refs(comm_id, bundle["id"], item["id"]),
    }
    meeting_data = {k: v for k, v in meeting_data.items() if v is not None}

    ops.append(
        (
            {
                "op": "insert",
                "table": "meetings",
                "client_id": meeting_client_id,
                "data": meeting_data,
            },
            item["id"],
        )
    )

    # Op 2+: INSERT meeting_participants
    for p in data.get("participants", data.get("attendees", [])):
        if isinstance(p, str):
            # Simple person_id string
            person_id = _resolve_ref(p, refs, "person") or p
            part_data = {
                "meeting_id": f"$ref:{meeting_client_id}",
                "person_id": person_id,
                "attended": 1,
            }
        else:
            # Dict with details
            person_id = _resolve_ref(
                p.get("person_id") or p.get("person_name"), refs, "person"
            ) or p.get("person_id")
            if not person_id:
                continue
            part_data = {
                "meeting_id": f"$ref:{meeting_client_id}",
                "person_id": person_id,
                "meeting_role": p.get("meeting_role"),
                "attended": 1 if p.get("attended", True) else 0,
                "key_contribution_summary": p.get("key_contribution_summary"),
                "stance_summary": p.get("stance_summary"),
            }

        part_data = {k: v for k, v in part_data.items() if v is not None}
        ops.append(
            (
                {
                    "op": "insert",
                    "table": "meeting_participants",
                    "data": part_data,
                },
                item["id"],
            )
        )

    # Op 3+: INSERT meeting_matters
    matter_id = _resolve_matter_id(bundle, refs)
    if matter_id:
        ops.append(
            (
                {
                    "op": "insert",
                    "table": "meeting_matters",
                    "data": {
                        "meeting_id": f"$ref:{meeting_client_id}",
                        "matter_id": matter_id,
                        "relationship_type": "primary topic",
                    },
                },
                item["id"],
            )
        )

    for ml in data.get("matter_links", []):
        link_matter_id = ml.get("matter_id")
        if link_matter_id and link_matter_id != matter_id:
            ops.append(
                (
                    {
                        "op": "insert",
                        "table": "meeting_matters",
                        "data": {
                            "meeting_id": f"$ref:{meeting_client_id}",
                            "matter_id": link_matter_id,
                            "relationship_type": ml.get(
                                "relationship_type", "secondary topic"
                            ),
                        },
                    },
                    item["id"],
                )
            )

    return ops


def convert_stakeholder_addition(
    item: dict, bundle: dict, refs: dict
) -> list[tuple[dict, str]]:
    data = item["proposed_data"]
    matter_id = data.get("matter_id") or _resolve_matter_id(bundle, refs)

    if not matter_id:
        logger.warning(
            "stakeholder_addition item %s has no matter_id — skipping", item["id"][:8]
        )
        return []

    # Determine if org or person stakeholder
    org_id = data.get("organization_id") or _resolve_ref(
        data.get("organization_name"), refs, "org"
    )
    person_id = data.get("person_id") or _resolve_ref(
        data.get("person_name"), refs, "person"
    )

    if org_id and not person_id:
        op_data = {
            "matter_id": matter_id,
            "organization_id": org_id,
            "organization_role": data.get("role") or data.get("matter_role"),
            "notes": data.get("rationale_detail") or data.get("notes"),
        }
        op_data = {k: v for k, v in op_data.items() if v is not None}
        return [
            (
                {
                    "op": "insert",
                    "table": "matter_organizations",
                    "data": op_data,
                },
                item["id"],
            )
        ]

    if person_id:
        op_data = {
            "matter_id": matter_id,
            "person_id": person_id,
            "matter_role": data.get("role") or data.get("matter_role"),
            "engagement_level": data.get("engagement_level") or data.get("stance"),
            "notes": data.get("rationale_detail") or data.get("notes"),
        }
        op_data = {k: v for k, v in op_data.items() if v is not None}
        return [
            (
                {
                    "op": "insert",
                    "table": "matter_people",
                    "data": op_data,
                },
                item["id"],
            )
        ]

    logger.warning(
        "stakeholder_addition item %s has no person or org — skipping", item["id"][:8]
    )
    return []


def convert_document(item: dict, bundle: dict, refs: dict) -> list[tuple[dict, str]]:
    data = item["proposed_data"]
    matter_id = data.get("matter_id") or _resolve_matter_id(bundle, refs)

    op_data = {
        "title": data["title"],
        "matter_id": matter_id,
        "document_type": data.get("document_type"),
        "status": data.get("status", "drafting"),
        "assigned_to_person_id": data.get("assigned_to_person_id"),
        "due_date": data.get("due_date"),
        "summary": data.get("summary"),
        "notes": data.get("notes"),
        "source": "ai",
        "source_id": item["id"],
        "external_refs": _external_refs(
            bundle.get("_communication_id", ""), bundle["id"], item["id"]
        ),
    }
    op_data = {k: v for k, v in op_data.items() if v is not None}

    return [
        (
            {
                "op": "insert",
                "table": "documents",
                "data": op_data,
            },
            item["id"],
        )
    ]


def convert_context_note(
    item: dict, bundle: dict, refs: dict
) -> list[tuple[dict, str]]:
    """Compound: 1 item -> context_note INSERT + context_note_links INSERTs."""
    data = item["proposed_data"]
    matter_id = data.get("matter_id") or _resolve_matter_id(bundle, refs)
    note_client_id = f"ctx-note-{item['id']}"

    op_data = {
        "title": data.get("title"),
        "matter_id": matter_id,
        "category": data.get("category"),
        "body": data.get("body"),
        "posture": data.get("posture"),
        "speaker_attribution": data.get("speaker_attribution"),
        "durability": data.get("durability", "durable"),
        "sensitivity": data.get("sensitivity", "low"),
        "effective_date": data.get("effective_date"),
        "stale_after": data.get("stale_after"),
        "source": "ai",
        "source_id": item["id"],
        "ai_confidence": item.get("confidence"),
        "external_refs": _external_refs(
            bundle.get("_communication_id", ""), bundle["id"], item["id"]
        ),
    }
    op_data = {k: v for k, v in op_data.items() if v is not None}

    ops = [
        (
            {
                "op": "insert",
                "table": "context_notes",
                "client_id": note_client_id,
                "data": op_data,
            },
            item["id"],
        )
    ]

    # Insert linked entities into context_note_links join table
    for le in data.get("linked_entities", []):
        entity_id = le.get("entity_id")
        if not entity_id:
            continue
        link_data = {
            "context_note_id": f"$ref:{note_client_id}",
            "entity_type": le.get("entity_type"),
            "entity_id": entity_id,
            "relationship_role": le.get("relationship_role"),
        }
        link_data = {k: v for k, v in link_data.items() if v is not None}
        ops.append(
            (
                {
                    "op": "insert",
                    "table": "context_note_links",
                    "data": link_data,
                },
                item["id"],
            )
        )

    return ops


def convert_person_detail_update(
    item: dict, bundle: dict, refs: dict
) -> list[tuple[dict, str]]:
    """Split fields into person_profiles (biographical) and people table updates."""
    data = item["proposed_data"]
    person_id = data.get("person_id")

    if not person_id:
        logger.warning(
            "person_detail_update item %s has no person_id — skipping", item["id"][:8]
        )
        return []

    fields = data.get("fields", {})
    profile_fields = {k: v for k, v in fields.items() if k not in PEOPLE_TABLE_FIELDS}
    people_fields = {k: v for k, v in fields.items() if k in PEOPLE_TABLE_FIELDS}

    ops = []

    # Profile update (person_profiles table, upsert by person_id)
    if profile_fields:
        ops.append(
            (
                {
                    "op": "insert",
                    "table": "person_profiles",
                    "data": {
                        "person_id": person_id,
                        **profile_fields,
                    },
                    "_meta": {
                        "upsert_by": "person_id",
                    },
                },
                item["id"],
            )
        )

    # People table update (only for fields currently unset)
    if people_fields:
        ops.append(
            (
                {
                    "op": "update",
                    "table": "people",
                    "record_id": person_id,
                    "data": people_fields,
                },
                item["id"],
            )
        )

    return ops


def convert_org_detail_update(
    item: dict, bundle: dict, refs: dict
) -> list[tuple[dict, str]]:
    """Produce a batch update operation for an existing organization."""
    data = item["proposed_data"]
    org_id = data.get("existing_org_id")
    changes = data.get("changes", {})

    if not changes or not org_id:
        return []

    return [
        (
            {
                "op": "update",
                "table": "organizations",
                "record_id": org_id,
                "data": changes,
            },
            item["id"],
        )
    ]


# ═══════════════════════════════════════════════════════════════════════════
# Dispatcher
# ═══════════════════════════════════════════════════════════════════════════


def convert_directive_update(
    item: dict, bundle: dict, refs: dict
) -> list[tuple[dict, str]]:
    """Convert a directive_update item to tracker batch operations.

    Produces:
    1. UPDATE on policy_directives with changes dict
    2. INSERT into directive_matters for each new matter link
    """
    data = item["proposed_data"]
    directive_id = data.get("directive_id")
    changes = data.get("changes", {})
    item_id = item["id"]

    if not directive_id:
        logger.warning("directive_update missing directive_id, skipping")
        return []

    ops = []

    # Op 1: Update directive fields
    if changes:
        update_data = {}
        for field in (
            "implementation_status",
            "implementation_notes",
            "target_date",
            "completed_date",
            "notes",
        ):
            if field in changes:
                update_data[field] = changes[field]

        if update_data:
            update_data["source"] = "ai"
            update_data["source_id"] = item_id
            update_data["external_refs"] = json.dumps(
                _external_refs(
                    bundle.get("communication_id", ""),
                    bundle.get("id", ""),
                    item_id,
                )
            )
            # Remove None values
            update_data = {k: v for k, v in update_data.items() if v is not None}

            ops.append(
                (
                    {
                        "op": "update",
                        "table": "policy_directives",
                        "record_id": directive_id,
                        "data": update_data,
                    },
                    item_id,
                )
            )

    # Op 2+: Insert new matter links
    for link in data.get("add_matter_links", []):
        matter_id = link.get("matter_id")
        if not matter_id:
            continue

        # Resolve forward reference if matter_id is a $ref
        resolved_matter_id = (
            _resolve_ref(matter_id, refs, "matter")
            if "$ref:" in str(matter_id)
            else matter_id
        )

        ops.append(
            (
                {
                    "op": "insert",
                    "table": "directive_matters",
                    "data": {
                        "directive_id": directive_id,
                        "matter_id": resolved_matter_id,
                        "relationship_type": link.get(
                            "relationship_type", "related_to"
                        ),
                    },
                },
                item_id,
            )
        )

    if not ops:
        logger.warning(
            "directive_update for %s produced no operations", directive_id[:8]
        )

    return ops


CONVERTERS = {
    "new_organization": convert_new_organization,
    "new_person": convert_new_person,
    "task": convert_task,
    "task_update": convert_task_update,
    "decision": convert_decision,
    "decision_update": convert_decision_update,
    "matter_update": convert_matter_update,
    "status_change": convert_status_change,
    "meeting_record": convert_meeting_record,
    "stakeholder_addition": convert_stakeholder_addition,
    "document": convert_document,
    "context_note": convert_context_note,
    "person_detail_update": convert_person_detail_update,
    "org_detail_update": convert_org_detail_update,
    "directive_update": convert_directive_update,
}


def convert_item(item: dict, bundle: dict, refs: dict) -> list[tuple[dict, str | None]]:
    """Convert a single item to tracker batch operations.

    Returns list of (operation_dict, item_id) tuples.
    """
    converter = CONVERTERS.get(item["item_type"])
    if not converter:
        logger.warning(
            "No converter for item_type '%s' — skipping item %s",
            item["item_type"],
            item["id"][:8],
        )
        return []
    return converter(item, bundle, refs)
