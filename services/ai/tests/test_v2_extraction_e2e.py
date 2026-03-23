#!/usr/bin/env python3
"""End-to-end behavioral test for v2.0.0 extraction pipeline.

Tests:
1. Pydantic validation of a realistic v2.0.0 extraction payload
2. Post-processing: name resolution, $ref validation, update validation,
   legacy follow_up conversion
3. Converter batch op generation for all new item types
4. Round-trip: payload -> validation -> post-processing -> converters

Run: cd services/ai && python -m tests.test_v2_extraction_e2e
"""

import json
import sys
import uuid
from pathlib import Path

# Ensure app imports work
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.pipeline.stages.extraction_models import (
    ExtractionOutput,
    ExtractionItem,
    ExtractionBundle,
    SourceEvidence,
    SourceTimeRange,
    VALID_ITEM_TYPES,
    POLICY_TOGGLE_MAP,
    TASK_UPDATE_ALLOWED_FIELDS,
    DECISION_UPDATE_ALLOWED_FIELDS,
)
from app.writeback.item_converters import (
    CONVERTERS,
    convert_item,
    convert_task,
    convert_task_update,
    convert_decision,
    convert_decision_update,
    convert_context_note,
    convert_person_detail_update,
    convert_org_detail_update,
)

# ═══════════════════════════════════════════════════════════════════════════
# Fixtures: realistic tracker context
# ═══════════════════════════════════════════════════════════════════════════

PERSON_TYLER_ID = "aaaaaaaa-1111-4000-8000-000000000001"
PERSON_STEPHEN_ID = "aaaaaaaa-1111-4000-8000-000000000002"
PERSON_PRIYA_ID = "aaaaaaaa-1111-4000-8000-000000000003"
ORG_OGC_REG_ID = "bbbbbbbb-2222-4000-8000-000000000001"
ORG_SEC_ID = "bbbbbbbb-2222-4000-8000-000000000002"
MATTER_CRYPTO_ID = "cccccccc-3333-4000-8000-000000000001"
MATTER_CUSTODY_ID = "cccccccc-3333-4000-8000-000000000002"
TASK_CUSTODY_MEMO_ID = "dddddddd-4444-4000-8000-000000000001"
DECISION_CLEARING_ID = "eeeeeeee-5555-4000-8000-000000000001"

FULL_CONTEXT = {
    "people": [
        {"id": PERSON_TYLER_ID, "full_name": "Tyler S. Badgley", "title": "General Counsel"},
        {"id": PERSON_STEPHEN_ID, "full_name": "Stephen Andrews", "title": "Deputy GC, Regulatory"},
        {"id": PERSON_PRIYA_ID, "full_name": "Priya Sharma", "title": "Attorney-Advisor"},
    ],
    "organizations": [
        {"id": ORG_OGC_REG_ID, "name": "OGC - Regulatory", "organization_type": "CFTC office"},
        {"id": ORG_SEC_ID, "name": "Securities and Exchange Commission", "organization_type": "Federal agency"},
    ],
    "matters": [
        {
            "id": MATTER_CRYPTO_ID,
            "title": "Crypto Derivatives NPRM",
            "matter_type": "rulemaking",
            "status": "draft in progress",
            "priority": "critical this week",
            "open_tasks": [
                {"id": TASK_CUSTODY_MEMO_ID, "title": "Draft custody rule options memo",
                 "status": "in progress", "assigned_to_person_id": PERSON_PRIYA_ID,
                 "due_date": "2026-04-30"},
            ],
            "open_decisions": [
                {"id": DECISION_CLEARING_ID, "title": "Clearing rule approach — phased vs immediate",
                 "status": "pending", "decision_type": "policy"},
            ],
            "stakeholders": [
                {"person_id": PERSON_TYLER_ID, "full_name": "Tyler S. Badgley", "role": "supervisor"},
            ],
            "organizations": [],
            "recent_updates": [],
        },
        {
            "id": MATTER_CUSTODY_ID,
            "title": "Digital Asset Custody Framework",
            "matter_type": "rulemaking",
            "status": "research in progress",
            "priority": "important this month",
            "open_tasks": [],
            "open_decisions": [],
            "stakeholders": [],
            "organizations": [],
            "recent_updates": [],
        },
    ],
    "standalone_tasks": [],
    "recent_meetings": [],
}

POLICY = {
    "extraction_policy": {
        "propose_tasks": True,
        "propose_decisions": True,
        "propose_matter_updates": True,
        "propose_meeting_records": True,
        "propose_stakeholders": True,
        "propose_status_changes": True,
        "propose_documents": True,
        "propose_new_people": True,
        "propose_new_organizations": True,
    },
    "routing_policy": {
        "match_confidence_minimum": 0.7,
        "standalone_items_enabled": True,
        "max_new_matters_per_communication": 5,
    },
    "model_config": {
        "primary_extraction_model": "claude-sonnet-4-20250514",
    },
}

# ═══════════════════════════════════════════════════════════════════════════
# Realistic v2.0.0 extraction payload
# ═══════════════════════════════════════════════════════════════════════════

SAMPLE_PAYLOAD = {
    "extraction_version": "2.0.0",
    "communication_id": "ffffffff-9999-4000-8000-000000000001",
    "extraction_summary": "Tyler briefed Stephen on crypto NPRM acceleration and custody memo deadline change. Key outputs: task update on Priya's memo, new follow-up task, decision recommendation on clearing rule, context notes on OGC-Reg operating posture, and person/org detail updates.",
    "matter_associations": [
        {
            "matter_id": MATTER_CRYPTO_ID,
            "matter_title": "Crypto Derivatives NPRM",
            "match_reason": "Speakers are matter stakeholders, crypto topic discussed",
            "match_confidence": 0.95,
        },
    ],
    "bundles": [
        {
            "bundle_type": "matter",
            "target_matter_id": MATTER_CRYPTO_ID,
            "target_matter_title": "Crypto Derivatives NPRM",
            "proposed_matter": None,
            "confidence": 0.94,
            "rationale": "Multiple items directly about the crypto NPRM matter.",
            "intelligence_notes": None,
            "uncertainty_flags": [],
            "items": [
                # ── 1. task: paired action (Tyler commits to ask Rusty) ──
                {
                    "item_type": "task",
                    "client_id": "temp-tyler-sec-contacts",
                    "proposed_data": {
                        "title": "Ask Rusty at SEC to identify crypto regulatory touch points",
                        "status": "not started",
                        "task_mode": "action",
                        "assigned_to_person_id": PERSON_TYLER_ID,
                        "expected_output": "Named SEC contacts for crypto regulatory coordination",
                    },
                    "confidence": 0.91,
                    "rationale": "Tyler made a direct commitment.",
                    "source_evidence": [
                        {
                            "excerpt": "I need to ask Rusty — he's their general counsel — who the right regulatory touch points are.",
                            "segments": ["seg-001"],
                            "time_range": {"start": 2081.6, "end": 2088.4},
                            "speaker": "Tyler S. Badgley",
                        },
                    ],
                },
                # ── 2. task: paired follow_up (Stephen tracks Tyler) ──
                {
                    "item_type": "task",
                    "proposed_data": {
                        "title": "Follow up with Tyler on SEC crypto regulatory contacts",
                        "status": "not started",
                        "task_mode": "follow_up",
                        "tracks_task_ref": "$ref:temp-tyler-sec-contacts",
                        "waiting_on_person_id": PERSON_TYLER_ID,
                        "waiting_on_description": "Tyler to ask Rusty at SEC about crypto regulatory touch points",
                        "next_follow_up_date": "2026-04-02",
                        "priority": "normal",
                    },
                    "confidence": 0.91,
                    "rationale": "Stephen needs to track Tyler's follow-through.",
                    "source_evidence": [
                        {
                            "excerpt": "I need to ask Rusty — he's their general counsel — who the right regulatory touch points are.",
                            "segments": ["seg-001"],
                            "time_range": {"start": 2081.6, "end": 2088.4},
                            "speaker": "Tyler S. Badgley",
                        },
                        {
                            "excerpt": "Especially with the crypto stuff, I'm probably going to want to have a pretty smooth relationship.",
                            "segments": ["seg-002"],
                            "time_range": {"start": 2088.7, "end": 2099.2},
                            "speaker": "Stephen Andrews",
                        },
                    ],
                },
                # ── 3. task_update: move Priya's memo deadline ──
                {
                    "item_type": "task_update",
                    "proposed_data": {
                        "existing_task_id": TASK_CUSTODY_MEMO_ID,
                        "existing_task_title": "Draft custody rule options memo",
                        "changes": {
                            "due_date": "2026-04-15",
                            "deadline_type": "soft",
                            "priority": "high",
                        },
                        "change_summary": "Due date moved from April 30 to April 15 per Tyler. Priority escalated — Chairman wants options before Hill meeting.",
                    },
                    "confidence": 0.95,
                    "rationale": "Tyler explicitly moved deadline and provided reason.",
                    "source_evidence": [
                        {
                            "excerpt": "That custody memo Priya's working on — I need it by the 15th now, not end of month. The Chairman wants to see options before his Hill meeting.",
                            "segments": ["seg-005"],
                            "time_range": {"start": 312.4, "end": 325.8},
                            "speaker": "Tyler S. Badgley",
                        },
                    ],
                },
                # ── 4. decision_update: recommendation on clearing rule ──
                {
                    "item_type": "decision_update",
                    "proposed_data": {
                        "existing_decision_id": DECISION_CLEARING_ID,
                        "existing_decision_title": "Clearing rule approach — phased vs immediate",
                        "changes": {
                            "status": "under consideration",
                            "recommended_option": "Option B — phased approach, per Tyler. Gives more flexibility with industry.",
                        },
                        "change_summary": "Tyler recommends phased approach. Status moved from pending to under consideration.",
                    },
                    "confidence": 0.88,
                    "rationale": "Tyler expressed a recommendation, not a final decision.",
                    "source_evidence": [
                        {
                            "excerpt": "I think we should go with Option B on the clearing rule — the phased approach gives us more flexibility.",
                            "segments": ["seg-010"],
                            "time_range": {"start": 567.2, "end": 580.1},
                            "speaker": "Tyler S. Badgley",
                        },
                    ],
                },
                # ── 5. context_note: OGC-Reg drafting expectation ──
                {
                    "item_type": "context_note",
                    "proposed_data": {
                        "title": "Leadership expects OGC-Reg to draft major rules directly",
                        "category": "policy_operating_rule",
                        "body": "Tyler Badgley said OGC-Regulatory has historically advised on rules drafted by policy divisions, but he expects the group to write major rules directly as bandwidth allows.",
                        "posture": "attributed_view",
                        "speaker_attribution": "Tyler S. Badgley",
                        "durability": "durable",
                        "sensitivity": "moderate",
                        "linked_entities": [
                            {"entity_type": "organization", "entity_id": ORG_OGC_REG_ID, "entity_name": "OGC - Regulatory", "relationship_role": "subject"},
                            {"entity_type": "person", "entity_id": None, "entity_name": "Tyler S. Badgley", "relationship_role": "source"},
                        ],
                    },
                    "confidence": 0.93,
                    "rationale": "Durable operating guidance for how OGC-Reg functions under current leadership.",
                    "source_evidence": [
                        {
                            "excerpt": "You guys will be taking the pen as much as you have the bandwidth to do on the major rules.",
                            "segments": ["seg-003"],
                            "time_range": {"start": 1371.5, "end": 1410.2},
                            "speaker": "Tyler S. Badgley",
                        },
                    ],
                },
                # ── 6. person_detail_update: Tyler's education ──
                {
                    "item_type": "person_detail_update",
                    "proposed_data": {
                        "person_id": PERSON_TYLER_ID,
                        "person_name": "Tyler S. Badgley",
                        "fields": {
                            "education_summary": "Georgetown Law",
                            "prior_roles_summary": "Approximately eight years at the SEC, Division of Trading and Markets",
                            "email": "tbadgley@cftc.gov",
                        },
                    },
                    "confidence": 0.95,
                    "rationale": "Self-disclosed education and career history. Email from signature block.",
                    "source_evidence": [
                        {
                            "excerpt": "I went to Georgetown Law, actually. And before this I spent about eight years at the SEC in their Division of Trading and Markets.",
                            "segments": ["seg-009"],
                            "time_range": {"start": 1890.3, "end": 1905.7},
                            "speaker": "Tyler S. Badgley",
                        },
                    ],
                },
                # ── 7. org_detail_update: SEC jurisdiction ──
                {
                    "item_type": "org_detail_update",
                    "proposed_data": {
                        "existing_org_id": ORG_SEC_ID,
                        "existing_org_name": "Securities and Exchange Commission",
                        "changes": {
                            "jurisdiction": "Securities markets, investment advisers, broker-dealers, digital asset securities",
                        },
                        "change_summary": "Added digital asset securities to SEC jurisdiction based on Tyler's discussion of crypto regulatory overlap.",
                    },
                    "confidence": 0.82,
                    "rationale": "Tyler discussed SEC's crypto jurisdiction in detail.",
                    "source_evidence": [
                        {
                            "excerpt": "SEC obviously has the securities side of digital assets, and there's real overlap with our derivatives jurisdiction.",
                            "segments": ["seg-011"],
                            "time_range": {"start": 2050.0, "end": 2065.3},
                            "speaker": "Tyler S. Badgley",
                        },
                    ],
                },
            ],
        },
        # ── Standalone bundle: meeting record ──
        {
            "bundle_type": "standalone",
            "target_matter_id": None,
            "target_matter_title": None,
            "proposed_matter": None,
            "confidence": 0.98,
            "rationale": "Meeting spans multiple matters.",
            "intelligence_notes": None,
            "uncertainty_flags": [],
            "items": [
                {
                    "item_type": "meeting_record",
                    "proposed_data": {
                        "title": "Stephen Andrews onboarding and OGC operating priorities briefing",
                        "date_time_start": "2026-03-19T10:00:00",
                        "meeting_type": "leadership meeting",
                        "purpose": "Orient incoming Deputy GC to OGC structure and regulatory priorities.",
                        "readout_summary": "Tyler briefed Stephen on the Chairman's priority buckets and crypto NPRM acceleration.",
                        "boss_attends": 1,
                        "external_parties_attend": 0,
                        "participants": [
                            {"person_id": PERSON_TYLER_ID, "meeting_role": "chair", "attended": True, "key_contribution_summary": "Led discussion."},
                            {"person_id": PERSON_STEPHEN_ID, "meeting_role": "attendee", "attended": True, "key_contribution_summary": "Asked about role expectations."},
                        ],
                        "matter_links": [
                            {"matter_id": MATTER_CRYPTO_ID, "relationship_type": "primary topic"},
                        ],
                    },
                    "confidence": 0.98,
                    "rationale": "Structured leadership meeting with two identified participants.",
                    "source_evidence": [
                        {
                            "excerpt": "This is kind of what he considers his tier one priorities now...",
                            "segments": ["seg-006"],
                            "time_range": {"start": 1246.2, "end": 1277.6},
                            "speaker": "Tyler S. Badgley",
                        },
                    ],
                },
            ],
        },
        # ── Bundle with name-only references (tests name resolution) ──
        {
            "bundle_type": "matter",
            "target_matter_id": None,
            "target_matter_title": "Crypto Derivatives NPRM",
            "proposed_matter": None,
            "confidence": 0.80,
            "rationale": "Task with name-only reference, no UUID.",
            "intelligence_notes": None,
            "uncertainty_flags": ["assigned_to resolved by name only"],
            "items": [
                {
                    "item_type": "task",
                    "proposed_data": {
                        "title": "Prepare crypto jurisdiction briefing for Chairman",
                        "status": "not started",
                        "task_mode": "action",
                        "assigned_to_person_id": None,
                        "assigned_to_name": "Priya Sharma",
                        "expected_output": "2-page briefing on crypto jurisdiction boundaries",
                        "due_date": "2026-04-01",
                    },
                    "confidence": 0.78,
                    "rationale": "Tyler assigned this to Priya during the meeting.",
                    "assigned_to_name": "Priya Sharma",
                    "source_evidence": [
                        {
                            "excerpt": "Priya, can you put together a short briefing on where our crypto jurisdiction starts and ends?",
                            "segments": ["seg-012"],
                            "time_range": {"start": 2120.0, "end": 2135.5},
                            "speaker": "Tyler S. Badgley",
                        },
                    ],
                },
            ],
        },
    ],
    "suppressed_observations": [
        {
            "item_type": "task",
            "description": "Tyler mentioned wanting to think about MOU with SEC",
            "reason_noted": "Too aspirational — no actor, deliverable, or timeline.",
            "source_excerpt": "We should probably think about some kind of MOU with SEC at some point.",
            "source_segments": ["seg-015"],
            "confidence_if_enabled": 0.45,
        },
    ],
    "unmatched_intelligence": None,
}

# Also test legacy follow_up item type conversion
LEGACY_FOLLOW_UP_PAYLOAD = {
    "extraction_version": "2.0.0",
    "communication_id": "ffffffff-9999-4000-8000-000000000002",
    "extraction_summary": "Legacy format test.",
    "bundles": [
        {
            "bundle_type": "standalone",
            "confidence": 0.85,
            "rationale": "Test legacy follow_up conversion.",
            "items": [
                {
                    "item_type": "follow_up",
                    "proposed_data": {
                        "title": "Check back with Tyler on SEC coordination",
                        "status": "not started",
                        "priority": "normal",
                    },
                    "confidence": 0.80,
                    "rationale": "Legacy item type — should be converted to task.",
                    "source_evidence": [
                        {
                            "excerpt": "Let's circle back on that SEC thing next week.",
                            "segments": ["seg-legacy-1"],
                            "time_range": {"start": 100.0, "end": 105.0},
                            "speaker": "Stephen Andrews",
                        },
                    ],
                },
            ],
        },
    ],
}


# ═══════════════════════════════════════════════════════════════════════════
# Test functions
# ═══════════════════════════════════════════════════════════════════════════

def section(title: str):
    print(f"\n{'=' * 70}")
    print(f"  {title}")
    print(f"{'=' * 70}\n")


def test_pydantic_validation():
    """Test 1: Pydantic validation of v2.0.0 payload."""
    section("TEST 1: Pydantic Validation")

    # Main payload
    print("--- Main payload validation ---")
    try:
        output = ExtractionOutput(**SAMPLE_PAYLOAD)
        print(f"  extraction_version: {output.extraction_version}")
        print(f"  communication_id:   {output.communication_id}")
        print(f"  bundles:            {len(output.bundles)}")
        total_items = sum(len(b.items) for b in output.bundles)
        print(f"  total items:        {total_items}")
        print(f"  suppressed:         {len(output.suppressed_observations)}")

        # Check source_evidence normalization
        print("\n--- Source evidence normalization ---")
        for bi, bundle in enumerate(output.bundles):
            for ii, item in enumerate(bundle.items):
                has_v2 = item.source_evidence is not None and len(item.source_evidence) > 0
                has_v1 = item.source_excerpt not in (None, "")
                ev_count = len(item.source_evidence) if item.source_evidence else 0
                print(f"  bundle[{bi}].item[{ii}] ({item.item_type}): "
                      f"v2_evidence={ev_count}, v1_excerpt={'yes' if has_v1 else 'no'}, "
                      f"v1_segments={len(item.source_segments or [])}, "
                      f"client_id={item.client_id or '-'}")

        print("\n  RESULT: PASS — Pydantic validation succeeded")
        return output

    except Exception as e:
        print(f"  RESULT: FAIL — {e}")
        raise


def test_legacy_follow_up_conversion():
    """Test 2: Legacy follow_up item type conversion."""
    section("TEST 2: Legacy follow_up Conversion")

    output = ExtractionOutput(**LEGACY_FOLLOW_UP_PAYLOAD)
    item = output.bundles[0].items[0]
    print(f"  Before conversion: item_type={item.item_type}")
    assert item.item_type == "follow_up", "Expected follow_up before conversion"

    # Import and run the converter
    from app.pipeline.stages.extraction import _convert_legacy_follow_ups
    count = _convert_legacy_follow_ups(output)

    item = output.bundles[0].items[0]
    print(f"  After conversion:  item_type={item.item_type}, task_mode={item.proposed_data.get('task_mode')}")
    print(f"  Conversion count:  {count}")
    assert item.item_type == "task", f"Expected task, got {item.item_type}"
    assert item.proposed_data.get("task_mode") == "follow_up", "Expected task_mode=follow_up"
    print(f"  RESULT: PASS — follow_up -> task(task_mode=follow_up)")


def test_name_resolution():
    """Test 3: Entity name resolution."""
    section("TEST 3: Entity Name Resolution")

    output = ExtractionOutput(**SAMPLE_PAYLOAD)

    from app.pipeline.stages.extraction import _resolve_entity_names, _fuzzy_title_match

    # Before resolution
    name_bundle = output.bundles[2]  # The name-only bundle
    task_item = name_bundle.items[0]
    print(f"  Before resolution:")
    print(f"    bundle.target_matter_id: {name_bundle.target_matter_id}")
    print(f"    item.assigned_to_person_id: {task_item.proposed_data.get('assigned_to_person_id')}")
    print(f"    item.assigned_to_name (item-level): {task_item.assigned_to_name}")
    print(f"    item.assigned_to_name (pd): {task_item.proposed_data.get('assigned_to_name')}")

    # Context note linked entity with null entity_id
    ctx_item = output.bundles[0].items[4]  # context_note
    linked = ctx_item.proposed_data.get("linked_entities", [])
    null_entity = [le for le in linked if le.get("entity_id") is None]
    print(f"    context_note linked_entities with null id: {len(null_entity)}")

    log = _resolve_entity_names(output, FULL_CONTEXT)

    print(f"\n  After resolution:")
    print(f"    bundle.target_matter_id: {name_bundle.target_matter_id}")
    print(f"    item.assigned_to_person_id: {task_item.proposed_data.get('assigned_to_person_id')}")

    # Check context note linked entity resolution
    linked_after = ctx_item.proposed_data.get("linked_entities", [])
    resolved_entities = [le for le in linked_after if le.get("entity_id") is not None]
    print(f"    context_note linked_entities resolved: {len(resolved_entities)}/{len(linked_after)}")

    print(f"\n  Resolution log ({len(log)} entries):")
    for entry in log:
        print(f"    - {entry}")

    # Assertions
    assert name_bundle.target_matter_id == MATTER_CRYPTO_ID, \
        f"Expected matter resolved, got {name_bundle.target_matter_id}"
    assert task_item.proposed_data["assigned_to_person_id"] == PERSON_PRIYA_ID, \
        f"Expected Priya's ID, got {task_item.proposed_data['assigned_to_person_id']}"

    print(f"\n  RESULT: PASS — Names resolved to UUIDs")


def test_ref_validation():
    """Test 4: $ref: validation between items."""
    section("TEST 4: $ref: Validation")

    output = ExtractionOutput(**SAMPLE_PAYLOAD)

    from app.pipeline.stages.extraction import _validate_tracks_task_refs

    # Check the follow_up task has a $ref
    follow_up_item = output.bundles[0].items[1]
    ref_before = follow_up_item.proposed_data.get("tracks_task_ref")
    print(f"  tracks_task_ref before validation: {ref_before}")

    warnings = _validate_tracks_task_refs(output)
    ref_after = follow_up_item.proposed_data.get("tracks_task_ref")
    print(f"  tracks_task_ref after validation:  {ref_after}")
    print(f"  Warnings: {warnings}")

    assert ref_after == "$ref:temp-tyler-sec-contacts", \
        f"Valid ref should be preserved, got {ref_after}"
    assert len(warnings) == 0, f"Expected no warnings, got {warnings}"
    print(f"  RESULT: PASS — Valid $ref preserved, no warnings")


def test_update_validation():
    """Test 5: Update item type validation."""
    section("TEST 5: Update Item Validation")

    output = ExtractionOutput(**SAMPLE_PAYLOAD)

    from app.pipeline.stages.extraction import _validate_update_items

    warnings = _validate_update_items(output, FULL_CONTEXT)

    print(f"  Warnings: {len(warnings)}")
    for w in warnings:
        print(f"    - {w}")

    # All our test items should pass validation (valid IDs, valid fields)
    assert len(warnings) == 0, f"Expected no warnings for valid items, got {warnings}"

    # Now test with a bad task_update
    bad_payload = {
        "extraction_version": "2.0.0",
        "communication_id": "test-bad",
        "extraction_summary": "Bad update test",
        "bundles": [{
            "bundle_type": "standalone",
            "confidence": 0.85,
            "rationale": "Test bad updates.",
            "items": [{
                "item_type": "task_update",
                "proposed_data": {
                    "existing_task_id": "nonexistent-task-id",
                    "existing_task_title": "Fake Task",
                    "changes": {"title": "New Title"},  # title is NOT in allowed fields
                    "change_summary": "Bad change",
                },
                "confidence": 0.80,
                "rationale": "Should generate warnings.",
                "source_evidence": [{
                    "excerpt": "test",
                    "segments": ["seg-bad"],
                    "time_range": {"start": 0, "end": 1},
                }],
            }],
        }],
    }
    bad_output = ExtractionOutput(**bad_payload)
    bad_warnings = _validate_update_items(bad_output, FULL_CONTEXT)
    print(f"\n  Bad task_update warnings: {len(bad_warnings)}")
    for w in bad_warnings:
        print(f"    - {w}")
    assert len(bad_warnings) >= 2, "Expected warnings for unknown task ID and disallowed field"

    print(f"\n  RESULT: PASS — Valid updates clean, invalid updates warned")


def test_converters():
    """Test 6: Writeback converter output for all item types."""
    section("TEST 6: Converter Batch Op Generation")

    output = ExtractionOutput(**SAMPLE_PAYLOAD)

    # First resolve names so converters have good data
    from app.pipeline.stages.extraction import _resolve_entity_names
    _resolve_entity_names(output, FULL_CONTEXT)

    bundle_dict = {
        "id": "test-bundle-001",
        "bundle_type": "matter",
        "target_matter_id": MATTER_CRYPTO_ID,
        "_communication_id": "test-comm-001",
    }
    standalone_bundle_dict = {
        "id": "test-bundle-002",
        "bundle_type": "standalone",
        "target_matter_id": None,
        "_communication_id": "test-comm-001",
    }

    refs = {}
    all_ops = []

    # Process each item from bundle 0 (matter bundle)
    print("--- Matter bundle items ---")
    for item in output.bundles[0].items:
        item_dict = {
            "id": str(uuid.uuid4()),
            "item_type": item.item_type,
            "proposed_data": item.proposed_data,
            "confidence": item.confidence,
        }
        ops = convert_item(item_dict, bundle_dict, refs)
        all_ops.extend(ops)
        for op, src_id in ops:
            print(f"  {item.item_type:25s} -> {op['op']:6s} {op['table']:25s} "
                  f"id={op.get('id', op.get('client_id', '-'))[:12] if op.get('id') or op.get('client_id') else '-'}")

    # Process standalone bundle items
    print("\n--- Standalone bundle items ---")
    for item in output.bundles[1].items:
        item_dict = {
            "id": str(uuid.uuid4()),
            "item_type": item.item_type,
            "proposed_data": item.proposed_data,
            "confidence": item.confidence,
        }
        ops = convert_item(item_dict, standalone_bundle_dict, refs)
        all_ops.extend(ops)
        for op, src_id in ops:
            print(f"  {item.item_type:25s} -> {op['op']:6s} {op['table']:25s}")

    print(f"\n  Total batch ops generated: {len(all_ops)}")

    # Validate specific converter behaviors
    print("\n--- Specific converter checks ---")

    # Check tracks_task_id on follow_up task
    follow_up_ops = [op for op, _ in all_ops if op.get("data", {}).get("tracks_task_id")]
    print(f"  Tasks with tracks_task_id: {len(follow_up_ops)}")
    if follow_up_ops:
        print(f"    tracks_task_id = {follow_up_ops[0]['data']['tracks_task_id']}")

    # Check task_update produces UPDATE not INSERT
    task_update_ops = [op for op, _ in all_ops if op.get("table") == "tasks" and op.get("op") == "update"]
    print(f"  Task UPDATE ops: {len(task_update_ops)}")
    if task_update_ops:
        print(f"    Target: {task_update_ops[0].get('id', '?')[:12]}...")
        print(f"    Changes: {list(task_update_ops[0]['data'].keys())}")

    # Check decision_update
    decision_update_ops = [op for op, _ in all_ops if op.get("table") == "decisions" and op.get("op") == "update"]
    print(f"  Decision UPDATE ops: {len(decision_update_ops)}")

    # Check org_detail_update
    org_update_ops = [op for op, _ in all_ops if op.get("table") == "organizations" and op.get("op") == "update"]
    print(f"  Org UPDATE ops: {len(org_update_ops)}")

    # Check person_detail_update splits
    profile_ops = [op for op, _ in all_ops if op.get("table") == "person_profiles"]
    people_ops = [op for op, _ in all_ops if op.get("table") == "people" and op.get("op") == "update"]
    print(f"  Person profile INSERT ops: {len(profile_ops)}")
    print(f"  People table UPDATE ops: {len(people_ops)}")
    if profile_ops:
        print(f"    Profile fields: {[k for k in profile_ops[0]['data'].keys() if k != 'person_id']}")
    if people_ops:
        print(f"    People fields: {list(people_ops[0]['data'].keys())}")

    # Check context_note
    ctx_ops = [op for op, _ in all_ops if op.get("table") == "context_notes"]
    print(f"  Context note INSERT ops: {len(ctx_ops)}")

    # Assertions
    assert len(task_update_ops) == 1, f"Expected 1 task UPDATE, got {len(task_update_ops)}"
    assert len(decision_update_ops) == 1, f"Expected 1 decision UPDATE, got {len(decision_update_ops)}"
    assert len(org_update_ops) == 1, f"Expected 1 org UPDATE, got {len(org_update_ops)}"
    assert len(profile_ops) == 1, f"Expected 1 person_profiles INSERT, got {len(profile_ops)}"
    assert len(people_ops) == 1, f"Expected 1 people UPDATE (email), got {len(people_ops)}"
    assert len(ctx_ops) == 1, f"Expected 1 context_notes INSERT, got {len(ctx_ops)}"
    assert len(follow_up_ops) >= 1, "Expected at least 1 task with tracks_task_id"

    print(f"\n  RESULT: PASS — All converters produce correct op types")


def test_converter_coverage():
    """Test 7: Verify CONVERTERS covers all VALID_ITEM_TYPES."""
    section("TEST 7: Converter Coverage")

    converter_types = set(CONVERTERS.keys())
    print(f"  VALID_ITEM_TYPES ({len(VALID_ITEM_TYPES)}): {sorted(VALID_ITEM_TYPES)}")
    print(f"  CONVERTERS keys  ({len(converter_types)}): {sorted(converter_types)}")

    missing = VALID_ITEM_TYPES - converter_types
    extra = converter_types - VALID_ITEM_TYPES
    print(f"  Missing converters: {missing or 'none'}")
    print(f"  Extra converters:   {extra or 'none'}")

    assert not missing, f"Missing converters: {missing}"
    assert "follow_up" not in converter_types, "follow_up should not be in CONVERTERS"

    print(f"\n  RESULT: PASS — Full coverage, no follow_up")


def test_policy_toggle_map():
    """Test 8: Verify POLICY_TOGGLE_MAP consistency."""
    section("TEST 8: Policy Toggle Map")

    print(f"  Toggle map entries ({len(POLICY_TOGGLE_MAP)}):")
    for toggle, item_type in sorted(POLICY_TOGGLE_MAP.items()):
        print(f"    {toggle:35s} -> {item_type}")

    assert "propose_follow_ups" not in POLICY_TOGGLE_MAP, \
        "propose_follow_ups should not be in POLICY_TOGGLE_MAP"

    # All toggle targets should be in VALID_ITEM_TYPES
    for toggle, item_type in POLICY_TOGGLE_MAP.items():
        assert item_type in VALID_ITEM_TYPES, \
            f"Toggle target {item_type} not in VALID_ITEM_TYPES"

    print(f"\n  RESULT: PASS — No follow_up toggle, all targets valid")


def test_batch_op_format():
    """Test 9: Verify batch ops match tracker API contract."""
    section("TEST 9: Batch Op Format Verification")

    output = ExtractionOutput(**SAMPLE_PAYLOAD)
    from app.pipeline.stages.extraction import _resolve_entity_names
    _resolve_entity_names(output, FULL_CONTEXT)

    bundle_dict = {
        "id": "test-bundle-001",
        "bundle_type": "matter",
        "target_matter_id": MATTER_CRYPTO_ID,
        "_communication_id": "test-comm-001",
    }
    refs = {}

    print("--- Sample batch ops (JSON-ready) ---\n")
    for item in output.bundles[0].items:
        item_dict = {
            "id": str(uuid.uuid4()),
            "item_type": item.item_type,
            "proposed_data": item.proposed_data,
            "confidence": item.confidence,
        }
        ops = convert_item(item_dict, bundle_dict, refs)
        for op, _ in ops:
            # Validate structure
            assert "op" in op, f"Missing 'op' key in {op}"
            assert "table" in op, f"Missing 'table' key in {op}"
            if op["op"] == "insert":
                assert "data" in op, f"INSERT missing 'data': {op}"
            elif op["op"] == "update":
                assert "data" in op, f"UPDATE missing 'data': {op}"
                assert "record_id" in op, \
                    f"UPDATE missing 'record_id': {op}"

            print(f"  {item.item_type}: {json.dumps(op, indent=4, default=str)[:500]}")
            print()

    print(f"  RESULT: PASS — All ops have valid structure")


# ═══════════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 70)
    print("  v2.0.0 Extraction Pipeline — End-to-End Behavioral Test")
    print("=" * 70)

    passed = 0
    failed = 0
    errors = []

    tests = [
        test_pydantic_validation,
        test_legacy_follow_up_conversion,
        test_name_resolution,
        test_ref_validation,
        test_update_validation,
        test_converters,
        test_converter_coverage,
        test_policy_toggle_map,
        test_batch_op_format,
    ]

    for test_fn in tests:
        try:
            test_fn()
            passed += 1
        except Exception as e:
            failed += 1
            errors.append((test_fn.__name__, str(e)))
            print(f"  RESULT: FAIL — {e}")

    section("FINAL RESULTS")
    print(f"  Passed: {passed}/{len(tests)}")
    print(f"  Failed: {failed}/{len(tests)}")
    if errors:
        print(f"\n  Failures:")
        for name, err in errors:
            print(f"    {name}: {err}")
    else:
        print(f"\n  ALL TESTS PASSED")
