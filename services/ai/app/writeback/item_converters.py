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
"""

import json
import logging

logger = logging.getLogger(__name__)


def _external_refs(communication_id: str, bundle_id: str, item_id: str) -> str:
    """Standard external_refs JSON for all AI-created records."""
    return json.dumps({
        "ai_communication_id": communication_id,
        "ai_bundle_id": bundle_id,
        "ai_bundle_item_id": item_id,
    })


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

def convert_new_matter_bundle(bundle: dict, refs: dict) -> list[tuple[dict, str | None]]:
    """Convert a new_matter bundle's proposed_matter to a matters INSERT.

    This is the first operation in a new_matter bundle's batch.
    Returns [(op_dict, None)] — None item_id because this is bundle-level.
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
            "problem_statement": proposed.get("problem_statement"),
            "why_it_matters": proposed.get("why_it_matters"),
            "status": proposed.get("status", "active"),
            "priority": proposed.get("priority"),
            "sensitivity": proposed.get("sensitivity"),
            "boss_involvement_level": proposed.get("boss_involvement_level"),
            "next_step": proposed.get("next_step"),
            "source": "ai",
            "source_id": bundle["id"],
            "ai_confidence": bundle.get("confidence"),
            "automation_hold": 1,
            "external_refs": json.dumps({
                "ai_communication_id": bundle.get("communication_id",
                    # communication_id not on the tree dict, injected by committer
                    ""),
                "ai_bundle_id": bundle["id"],
            }),
        },
    }
    # Remove None values — tracker schema may reject NULLs for some columns
    op["data"] = {k: v for k, v in op["data"].items() if v is not None}
    return [(op, None)]


# ═══════════════════════════════════════════════════════════════════════════
# Item-level converters
# ═══════════════════════════════════════════════════════════════════════════

def convert_new_organization(item: dict, bundle: dict, refs: dict) -> list[tuple[dict, str]]:
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
                bundle.get("_communication_id", ""), bundle["id"], item["id"]),
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
        "organization_id": _resolve_ref(
            data.get("organization_id"), refs, "org")
            or _resolve_ref(data.get("organization_name"), refs, "org"),
        "email": data.get("email"),
        "phone": data.get("phone"),
        "relationship_category": data.get("relationship_category"),
        "is_active": 1,
        "source": "ai",
        "source_id": item["id"],
        "external_refs": _external_refs(
            bundle.get("_communication_id", ""), bundle["id"], item["id"]),
    }
    op_data = {k: v for k, v in op_data.items() if v is not None}

    return [({
        "op": "insert",
        "table": "people",
        "client_id": client_id,
        "data": op_data,
    }, item["id"])]


def convert_task(item: dict, bundle: dict, refs: dict) -> list[tuple[dict, str]]:
    data = item["proposed_data"]
    matter_id = data.get("matter_id") or _resolve_matter_id(bundle, refs)

    op_data = {
        "title": data["title"],
        "matter_id": matter_id,
        "description": data.get("description"),
        "task_type": data.get("task_type"),
        "status": data.get("status", "not started"),
        "task_mode": data.get("task_mode", "action"),
        "priority": data.get("priority"),
        "assigned_to_person_id": _resolve_ref(
            data.get("assigned_to"), refs, "person") or data.get("assigned_to_person_id"),
        "expected_output": data.get("expected_output"),
        "due_date": data.get("due_date"),
        "deadline_type": data.get("deadline_type"),
        "source": "ai",
        "source_id": item["id"],
        "ai_confidence": item.get("confidence"),
        "automation_hold": 1,
        "external_refs": _external_refs(
            bundle.get("_communication_id", ""), bundle["id"], item["id"]),
    }
    op_data = {k: v for k, v in op_data.items() if v is not None}

    return [({
        "op": "insert",
        "table": "tasks",
        "data": op_data,
    }, item["id"])]


def convert_follow_up(item: dict, bundle: dict, refs: dict) -> list[tuple[dict, str]]:
    data = item["proposed_data"]
    matter_id = data.get("matter_id") or _resolve_matter_id(bundle, refs)

    op_data = {
        "title": data.get("title", "Follow up"),
        "matter_id": matter_id,
        "task_mode": "monitoring",
        "status": "not started",
        "priority": data.get("priority"),
        "assigned_to_person_id": _resolve_ref(
            data.get("assigned_to"), refs, "person") or data.get("assigned_to_person_id"),
        "due_date": data.get("due_date"),
        "source": "ai",
        "source_id": item["id"],
        "ai_confidence": item.get("confidence"),
        "automation_hold": 1,
        "external_refs": _external_refs(
            bundle.get("_communication_id", ""), bundle["id"], item["id"]),
    }
    op_data = {k: v for k, v in op_data.items() if v is not None}

    return [({
        "op": "insert",
        "table": "tasks",
        "data": op_data,
    }, item["id"])]


def convert_decision(item: dict, bundle: dict, refs: dict) -> list[tuple[dict, str]]:
    data = item["proposed_data"]
    matter_id = data.get("matter_id") or _resolve_matter_id(bundle, refs)

    op_data = {
        "title": data["title"],
        "matter_id": matter_id,
        "decision_type": data.get("decision_type"),
        "status": data.get("status"),
        "decision_result": data.get("decision_result"),
        "made_at": data.get("made_at"),
        "notes": data.get("notes"),
        "source": "ai",
        "source_id": item["id"],
        "ai_confidence": item.get("confidence"),
        "automation_hold": 1,
        "external_refs": _external_refs(
            bundle.get("_communication_id", ""), bundle["id"], item["id"]),
    }
    op_data = {k: v for k, v in op_data.items() if v is not None}

    return [({
        "op": "insert",
        "table": "decisions",
        "data": op_data,
    }, item["id"])]


def convert_matter_update(item: dict, bundle: dict, refs: dict) -> list[tuple[dict, str]]:
    data = item["proposed_data"]
    matter_id = data.get("matter_id") or _resolve_matter_id(bundle, refs)

    op_data = {
        "matter_id": matter_id,
        "update_type": data.get("update_type"),
        "summary": data["summary"],
    }
    op_data = {k: v for k, v in op_data.items() if v is not None}

    return [({
        "op": "insert",
        "table": "matter_updates",
        "data": op_data,
    }, item["id"])]


def convert_status_change(item: dict, bundle: dict, refs: dict) -> list[tuple[dict, str]]:
    data = item["proposed_data"]
    matter_id = data.get("matter_id") or _resolve_matter_id(bundle, refs)

    if not matter_id:
        logger.warning("status_change item %s has no matter_id — skipping", item["id"][:8])
        return []

    update_data = {}
    field = data.get("field", "status")
    new_value = data.get("new_value")
    if field and new_value:
        update_data[field] = new_value

    if not update_data:
        return []

    return [({
        "op": "update",
        "table": "matters",
        "record_id": matter_id,
        "data": update_data,
    }, item["id"])]


def convert_meeting_record(item: dict, bundle: dict, refs: dict) -> list[tuple[dict, str]]:
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

    ops.append(({
        "op": "insert",
        "table": "meetings",
        "client_id": meeting_client_id,
        "data": meeting_data,
    }, item["id"]))

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
                "stance_summary": p.get("stance_summary"),
            }

        part_data = {k: v for k, v in part_data.items() if v is not None}
        ops.append(({
            "op": "insert",
            "table": "meeting_participants",
            "data": part_data,
        }, item["id"]))

    # Op 3+: INSERT meeting_matters
    matter_id = _resolve_matter_id(bundle, refs)
    if matter_id:
        ops.append(({
            "op": "insert",
            "table": "meeting_matters",
            "data": {
                "meeting_id": f"$ref:{meeting_client_id}",
                "matter_id": matter_id,
                "relationship_type": "discussed",
            },
        }, item["id"]))

    for ml in data.get("matter_links", []):
        link_matter_id = ml.get("matter_id")
        if link_matter_id and link_matter_id != matter_id:
            ops.append(({
                "op": "insert",
                "table": "meeting_matters",
                "data": {
                    "meeting_id": f"$ref:{meeting_client_id}",
                    "matter_id": link_matter_id,
                    "relationship_type": ml.get("relationship_type", "discussed"),
                },
            }, item["id"]))

    return ops


def convert_stakeholder_addition(item: dict, bundle: dict, refs: dict) -> list[tuple[dict, str]]:
    data = item["proposed_data"]
    matter_id = data.get("matter_id") or _resolve_matter_id(bundle, refs)

    if not matter_id:
        logger.warning("stakeholder_addition item %s has no matter_id — skipping", item["id"][:8])
        return []

    # Determine if org or person stakeholder
    org_id = data.get("organization_id") or _resolve_ref(
        data.get("organization_name"), refs, "org")
    person_id = data.get("person_id") or _resolve_ref(
        data.get("person_name"), refs, "person")

    if org_id and not person_id:
        op_data = {
            "matter_id": matter_id,
            "organization_id": org_id,
            "organization_role": data.get("role") or data.get("matter_role"),
            "notes": data.get("notes"),
        }
        op_data = {k: v for k, v in op_data.items() if v is not None}
        return [({
            "op": "insert",
            "table": "matter_organizations",
            "data": op_data,
        }, item["id"])]

    if person_id:
        op_data = {
            "matter_id": matter_id,
            "person_id": person_id,
            "matter_role": data.get("role") or data.get("matter_role"),
            "engagement_level": data.get("engagement_level") or data.get("stance"),
            "notes": data.get("notes"),
        }
        op_data = {k: v for k, v in op_data.items() if v is not None}
        return [({
            "op": "insert",
            "table": "matter_people",
            "data": op_data,
        }, item["id"])]

    logger.warning("stakeholder_addition item %s has no person or org — skipping", item["id"][:8])
    return []


def convert_document(item: dict, bundle: dict, refs: dict) -> list[tuple[dict, str]]:
    data = item["proposed_data"]
    matter_id = data.get("matter_id") or _resolve_matter_id(bundle, refs)

    op_data = {
        "title": data["title"],
        "matter_id": matter_id,
        "document_type": data.get("document_type"),
        "status": data.get("status", "draft"),
        "summary": data.get("summary"),
        "notes": data.get("notes"),
        "source": "ai",
        "source_id": item["id"],
        "external_refs": _external_refs(
            bundle.get("_communication_id", ""), bundle["id"], item["id"]),
    }
    op_data = {k: v for k, v in op_data.items() if v is not None}

    return [({
        "op": "insert",
        "table": "documents",
        "data": op_data,
    }, item["id"])]


# ═══════════════════════════════════════════════════════════════════════════
# Dispatcher
# ═══════════════════════════════════════════════════════════════════════════

CONVERTERS = {
    "new_organization": convert_new_organization,
    "new_person": convert_new_person,
    "task": convert_task,
    "follow_up": convert_follow_up,
    "decision": convert_decision,
    "matter_update": convert_matter_update,
    "status_change": convert_status_change,
    "meeting_record": convert_meeting_record,
    "stakeholder_addition": convert_stakeholder_addition,
    "document": convert_document,
}


def convert_item(item: dict, bundle: dict, refs: dict) -> list[tuple[dict, str | None]]:
    """Convert a single item to tracker batch operations.

    Returns list of (operation_dict, item_id) tuples.
    """
    converter = CONVERTERS.get(item["item_type"])
    if not converter:
        logger.warning("No converter for item_type '%s' — skipping item %s",
                       item["item_type"], item["id"][:8])
        return []
    return converter(item, bundle, refs)
