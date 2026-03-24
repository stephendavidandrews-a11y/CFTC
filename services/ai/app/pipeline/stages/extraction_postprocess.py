"""Post-processing and validation for extraction output.

Pure-logic functions: parsing LLM response, resolving entity names,
validating references, normalizing items, and the 7-step post-process pass.
"""
import json
import logging
from typing import Optional


from app.pipeline.stages.extraction_models import (
    ExtractionOutput,
    POLICY_TOGGLE_MAP,
    TASK_UPDATE_ALLOWED_FIELDS,
    DECISION_UPDATE_ALLOWED_FIELDS,
)

logger = logging.getLogger(__name__)

CONTEXT_NOTE_CATEGORIES = {
    "people_insight",
    "process_note",
    "policy_operating_rule",
    "strategic_context",
    "culture_climate",
    "relationship_dynamic",
}
CONTEXT_NOTE_CATEGORY_ALIASES = {
    "institutional_knowledge": "process_note",
    "strategic_priorities": "strategic_context",
    "process_change": "process_note",
    "organizational_history": "culture_climate",
    "interagency_relations": "relationship_dynamic",
}
CONTEXT_NOTE_POSTURES = {"factual", "attributed_view"}
PERSON_PROFILE_FIELDS = {
    "birthday",
    "spouse_name",
    "children_count",
    "children_names",
    "hometown",
    "current_city",
    "prior_roles_summary",
    "education_summary",
    "interests",
    "personal_notes_summary",
    "scheduling_notes",
    "relationship_preferences",
    "leadership_notes",
}
PERSON_PEOPLE_FIELDS = {
    "relationship_category",
    "email",
    "phone",
    "assistant_name",
    "assistant_contact",
    "substantive_areas",
    "manager_person_id",
}
PERSON_DETAIL_FIELDS = PERSON_PROFILE_FIELDS | PERSON_PEOPLE_FIELDS
CURRENT_ROLE_MARKERS = (
    "key contact",
    "contact for",
    "go-between",
    "go between",
    "go to",
    "liaison",
    "coordinator",
    "serves as",
    "acts as",
)
PRIOR_ROLE_MARKERS = (
    "previously",
    "before this",
    "former",
    "spent",
    "worked at",
    "worked in",
    "years at",
    "came from",
)

def _first_source_speaker(item) -> Optional[str]:
    """Return the first speaker named in source evidence, if any."""
    for ev in getattr(item, "source_evidence", []) or []:
        speaker = getattr(ev, "speaker", None)
        if speaker is None and isinstance(ev, dict):
            speaker = ev.get("speaker")
        if speaker:
            return speaker
    return None


def _choose_context_note_category(title: str, body: str, raw_category: Optional[str]) -> str:
    """Map model-emitted context note categories into the canonical set."""
    if raw_category in CONTEXT_NOTE_CATEGORIES:
        return raw_category
    if raw_category in CONTEXT_NOTE_CATEGORY_ALIASES:
        return CONTEXT_NOTE_CATEGORY_ALIASES[raw_category]

    text = f"{title} {body}".lower()
    if any(token in text for token in ("priority", "priorities", "strategic", "agenda")):
        return "strategic_context"
    if any(token in text for token in ("culture", "morale", "toxic", "collaborative")):
        return "culture_climate"
    if any(token in text for token in ("oira", "sec", "treasury", "harmonization", "coordination", "relationship")):
        return "relationship_dynamic"
    if any(token in text for token in ("draft", "hold the pen", "lead on rule", "operating rule", "expects")):
        return "policy_operating_rule"
    if any(token in text for token in ("process", "workflow", "how the office works")):
        return "process_note"
    return "process_note"


def _choose_context_note_posture(raw_posture: Optional[str], speaker_attribution: Optional[str]) -> str:
    """Map posture drift into the canonical posture set."""
    if raw_posture in CONTEXT_NOTE_POSTURES:
        return raw_posture
    return "attributed_view" if speaker_attribution else "factual"


def _normalize_context_note_item(item, repair_log: list[dict]):
    """Repair common context_note shape drift into contract-safe form."""
    data = item.proposed_data
    title = data.get("title", "")

    if "body" not in data and data.get("content"):
        data["body"] = data.pop("content")
        repair_log.append({
            "item_type": "context_note",
            "title": title,
            "repair": "content_to_body",
        })

    if "tags" in data:
        data.pop("tags", None)
        repair_log.append({
            "item_type": "context_note",
            "title": title,
            "repair": "removed_tags",
        })

    body = data.get("body", "")
    mapped_category = _choose_context_note_category(title, body, data.get("category"))
    if mapped_category != data.get("category"):
        repair_log.append({
            "item_type": "context_note",
            "title": title,
            "repair": "category_normalized",
            "from": data.get("category"),
            "to": mapped_category,
        })
        data["category"] = mapped_category

    speaker_attribution = data.get("speaker_attribution") or _first_source_speaker(item)
    mapped_posture = _choose_context_note_posture(data.get("posture"), speaker_attribution)
    if mapped_posture != data.get("posture"):
        repair_log.append({
            "item_type": "context_note",
            "title": title,
            "repair": "posture_normalized",
            "from": data.get("posture"),
            "to": mapped_posture,
        })
        data["posture"] = mapped_posture

    if mapped_posture == "attributed_view" and speaker_attribution and not data.get("speaker_attribution"):
        data["speaker_attribution"] = speaker_attribution
        repair_log.append({
            "item_type": "context_note",
            "title": title,
            "repair": "speaker_attribution_filled",
            "value": speaker_attribution,
        })

    if data.get("sensitivity") == "medium":
        data["sensitivity"] = "moderate"
        repair_log.append({
            "item_type": "context_note",
            "title": title,
            "repair": "sensitivity_normalized",
            "from": "medium",
            "to": "moderate",
        })


def _looks_like_current_role_note(text: str) -> bool:
    """Return True when the text looks like a current liaison/contact note, not career history."""
    lowered = (text or "").lower()
    if not lowered:
        return False
    has_current_role_markers = any(marker in lowered for marker in CURRENT_ROLE_MARKERS)
    has_prior_role_markers = any(marker in lowered for marker in PRIOR_ROLE_MARKERS)
    return has_current_role_markers and not has_prior_role_markers


def _normalize_person_detail_update_item(item, repair_log: list[dict]):
    """Repair person_detail_update payloads into the writeback shape."""
    data = item.proposed_data
    person_name = data.get("person_name") or data.get("person_id")
    fields = data.get("fields", {})
    if not isinstance(fields, dict):
        fields = {}

    moved_fields = []
    for key in list(data.keys()):
        if key in PERSON_DETAIL_FIELDS:
            fields.setdefault(key, data.pop(key))
            moved_fields.append(key)

    if moved_fields:
        repair_log.append({
            "item_type": "person_detail_update",
            "person": person_name,
            "repair": "moved_top_level_fields_into_fields",
            "fields": moved_fields,
        })

    prior_roles = fields.get("prior_roles_summary")
    if isinstance(prior_roles, str) and _looks_like_current_role_note(prior_roles):
        existing_notes = fields.get("personal_notes_summary")
        fields["personal_notes_summary"] = (
            f"{existing_notes}\n{prior_roles}" if existing_notes else prior_roles
        )
        fields.pop("prior_roles_summary", None)
        repair_log.append({
            "item_type": "person_detail_update",
            "person": person_name,
            "repair": "current_role_note_moved_out_of_prior_roles",
        })

    data["fields"] = fields



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
        "shape_repairs": [],
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
    for bundle in extraction.bundles:
        for item in bundle.items:
            if item.item_type == "context_note":
                _normalize_context_note_item(item, log["shape_repairs"])
            elif item.item_type == "person_detail_update":
                _normalize_person_detail_update_item(item, log["shape_repairs"])

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
