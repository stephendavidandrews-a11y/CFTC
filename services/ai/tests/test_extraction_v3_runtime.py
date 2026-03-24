"""Deterministic routing/runtime tests for extraction v3."""

import sys
from pathlib import Path


AI_SERVICE_DIR = Path(__file__).resolve().parents[1]
if str(AI_SERVICE_DIR) not in sys.path:
    sys.path.insert(0, str(AI_SERVICE_DIR))

from app.pipeline.stages.extraction_v3 import (  # noqa: E402
    _normalize_pass1_payload,
    _normalize_pass2_payload,
    _preferred_transcript_text,
    build_routing_resolution_package_from_context,
)
from app.pipeline.stages.extraction_v3_models import (  # noqa: E402
    CommunicationUnderstandingOutput,
)


PERSON_TYLER_ID = "aaaaaaaa-1111-4000-8000-000000000001"
PERSON_PRIYA_ID = "aaaaaaaa-1111-4000-8000-000000000003"
ORG_SEC_ID = "bbbbbbbb-2222-4000-8000-000000000002"
MATTER_CRYPTO_ID = "cccccccc-3333-4000-8000-000000000001"
TASK_CUSTODY_MEMO_ID = "dddddddd-4444-4000-8000-000000000001"


FULL_CONTEXT = {
    "people": [
        {"id": PERSON_TYLER_ID, "full_name": "Tyler S. Badgley", "title": "General Counsel"},
        {"id": PERSON_PRIYA_ID, "full_name": "Priya Sharma", "title": "Attorney-Advisor"},
    ],
    "organizations": [
        {"id": ORG_SEC_ID, "name": "Securities and Exchange Commission", "short_name": "SEC"},
    ],
    "matters": [
        {
            "id": MATTER_CRYPTO_ID,
            "title": "Crypto Derivatives NPRM",
            "matter_type": "rulemaking",
            "status": "draft in progress",
            "priority": "critical this week",
            "stakeholders": [
                {"person_id": PERSON_TYLER_ID, "full_name": "Tyler S. Badgley", "role": "supervisor"},
            ],
            "organizations": [
                {"organization_id": ORG_SEC_ID, "name": "Securities and Exchange Commission", "organization_role": "partner agency"},
            ],
            "open_tasks": [
                {
                    "id": TASK_CUSTODY_MEMO_ID,
                    "title": "Draft custody rule options memo",
                    "status": "in progress",
                    "assigned_to_person_id": PERSON_PRIYA_ID,
                    "due_date": "2026-04-30",
                }
            ],
            "open_decisions": [],
        },
    ],
    "standalone_tasks": [],
    "recent_meetings": [],
}


def _sample_evidence() -> list[dict]:
    return [{"excerpt": "Sample evidence.", "segments": ["seg-001"]}]


def _base_pass1_payload() -> dict:
    return {
        "communication_id": "comm-001",
        "communication_kind": "audio",
        "communication_summary": "Tyler moved a memo deadline and shared background context.",
        "participants": [
            {
                "display_name": "Tyler S. Badgley",
                "tracker_person_id": PERSON_TYLER_ID,
                "organization_name": "CFTC",
                "confidence": 0.99,
            }
        ],
        "observations": [
            {
                "id": "obs-task",
                "observation_type": "task_signal",
                "observation_subtype": "deadline_change",
                "summary": "Tyler moved Priya's custody memo deadline to April 15.",
                "directness": "direct_statement",
                "confidence": 0.95,
                "durability": "working",
                "memory_value": "none",
                "speaker_refs": [{"name": "Tyler S. Badgley", "tracker_person_id": PERSON_TYLER_ID}],
                "entity_refs": [
                    {"entity_type": "person", "name": "Priya Sharma", "tracker_id": PERSON_PRIYA_ID},
                    {"entity_type": "organization", "name": "SEC", "tracker_id": ORG_SEC_ID},
                ],
                "candidate_matter_refs": [
                    {
                        "matter_id": MATTER_CRYPTO_ID,
                        "matter_title": "Crypto Derivatives NPRM",
                        "score": 0.92,
                        "reason": "Work product and stakeholders match the crypto matter.",
                    }
                ],
                "candidate_record_refs": [
                    {
                        "record_type": "task",
                        "record_id": TASK_CUSTODY_MEMO_ID,
                        "score": 0.94,
                        "reason": "Existing memo task title and assignee match.",
                    }
                ],
                "field_hints": {"due_date": "2026-04-15", "priority": "high"},
                "evidence": [{"excerpt": "I need it by the 15th now.", "segments": ["seg-001"]}],
            },
            {
                "id": "obs-person-memory",
                "observation_type": "person_memory_signal",
                "observation_subtype": "biography",
                "summary": "Tyler said he spent about eight years at the SEC.",
                "directness": "direct_statement",
                "confidence": 0.91,
                "durability": "durable",
                "memory_value": "high",
                "speaker_refs": [{"name": "Tyler S. Badgley", "tracker_person_id": PERSON_TYLER_ID}],
                "entity_refs": [{"entity_type": "person", "name": "Tyler S. Badgley", "tracker_id": PERSON_TYLER_ID}],
                "candidate_matter_refs": [],
                "candidate_record_refs": [],
                "field_hints": {"prior_roles_summary": "Approximately eight years at the SEC"},
                "evidence": [{"excerpt": "Before this I spent about eight years at the SEC.", "segments": ["seg-002"]}],
            },
        ],
    }


def test_v3_routing_package_resolves_entities_and_routes_to_existing_matter():
    pass1_output = CommunicationUnderstandingOutput(**_base_pass1_payload())
    routing_seeds = {
        "speaker_person_ids": {PERSON_TYLER_ID},
        "entity_person_ids": {PERSON_PRIYA_ID},
        "entity_org_ids": {ORG_SEC_ID},
        "identifier_hits": {"rin": set(), "docket": set(), "cfr": set()},
    }

    package = build_routing_resolution_package_from_context(
        communication_id="comm-001",
        pass1_output=pass1_output,
        full_context=FULL_CONTEXT,
        routing_seeds=routing_seeds,
    )

    assert package.matter_routing.primary_matter_id == MATTER_CRYPTO_ID
    assert package.matter_routing.routing_confidence == "high"
    assert any(match.record_id == TASK_CUSTODY_MEMO_ID for match in package.record_matches.tasks)
    assert {person.tracker_person_id for person in package.resolved_people} == {PERSON_TYLER_ID, PERSON_PRIYA_ID}
    assert {organization.tracker_org_id for organization in package.resolved_organizations} == {ORG_SEC_ID}
    assert [matter["id"] for matter in package.relevant_tracker_context["matters"]] == [MATTER_CRYPTO_ID]
    assert [task["id"] for task in package.relevant_tracker_context["matched_tasks"]] == [TASK_CUSTODY_MEMO_ID]


def test_v3_prefers_enriched_transcript_text():
    text, source = _preferred_transcript_text(
        {
            "raw_text": "raw line",
            "cleaned_text": "cleaned line",
            "enriched_text": "enriched line",
        }
    )

    assert text == "enriched line"
    assert source == "enriched_text"


def test_v3_normalizes_common_pass1_alias_labels():
    payload = _base_pass1_payload()
    payload["communication_kind"] = "audio_upload"
    payload["observations"][0]["directness"] = "explicit_statement"
    payload["observations"][0]["durability"] = "temporary"
    payload["observations"][1]["observation_subtype"] = "role"
    payload["observations"][1]["memory_value"] = "moderate"

    normalized = _normalize_pass1_payload(payload)

    assert normalized["communication_kind"] == "audio"
    assert normalized["observations"][0]["directness"] == "direct_statement"
    assert normalized["observations"][0]["durability"] == "working"
    assert normalized["observations"][1]["observation_subtype"] == "biography"
    assert normalized["observations"][1]["memory_value"] == "medium"


def test_v3_normalizes_common_pass2_shape_aliases():
    payload = {
        "communication_id": "comm-001",
        "extraction_summary": "Test output.",
        "routing_assessment": {
            "primary_matter_id": None,
            "secondary_matter_ids": [],
            "routing_confidence": "standalone",
            "routing_basis": ["cross-cutting onboarding discussion"],
            "standalone_reason": "No existing matter clearly owns the discussion.",
            "new_matter_candidate": False,
        },
        "bundles": [
            {
                "bundle_type": "standalone",
                "target_matter_id": None,
                "confidence": 0.8,
                "rationale": "Standalone bundle.",
                "items": [
                    {
                        "item_type": "context_note",
                        "proposed_data": {
                            "title": "Office guidance",
                            "content": "Use body, not content.",
                            "category": "policy_operating_rule",
                            "posture": "attributed_view",
                            "speaker_attribution": "Tyler S. Badgley",
                            "tags": ["bad"],
                        },
                        "confidence": 0.8,
                        "rationale": "Durable note.",
                        "why_new_vs_update": "New note.",
                        "why_this_matter": "Standalone.",
                        "source_observation_ids": ["obs-001"],
                        "source_evidence": _sample_evidence(),
                    },
                    {
                        "item_type": "person_detail_update",
                        "proposed_data": {
                            "person_id": PERSON_TYLER_ID,
                            "prior_roles_summary": "Eight years at SEC",
                        },
                        "confidence": 0.85,
                        "rationale": "Durable person memory.",
                        "why_new_vs_update": "Update existing profile.",
                        "why_this_matter": "Standalone.",
                        "source_observation_ids": ["obs-002"],
                        "source_evidence": _sample_evidence(),
                    },
                ],
            }
        ],
        "suppressed_observations": [],
    }

    normalized = _normalize_pass2_payload(payload)
    note_data = normalized["bundles"][0]["items"][0]["proposed_data"]
    person_data = normalized["bundles"][0]["items"][1]["proposed_data"]

    assert note_data["body"] == "Use body, not content."
    assert "content" not in note_data
    assert "tags" not in note_data
    assert person_data["fields"]["prior_roles_summary"] == "Eight years at SEC"
    assert "prior_roles_summary" not in person_data


def test_v3_routing_package_stays_standalone_for_memory_only_signal():
    payload = _base_pass1_payload()
    payload["observations"] = [payload["observations"][1]]

    pass1_output = CommunicationUnderstandingOutput(**payload)
    package = build_routing_resolution_package_from_context(
        communication_id="comm-standalone",
        pass1_output=pass1_output,
        full_context=FULL_CONTEXT,
        routing_seeds={"speaker_person_ids": set(), "entity_person_ids": set(), "entity_org_ids": set(), "identifier_hits": {"rin": set(), "docket": set(), "cfr": set()}},
    )

    assert package.matter_routing.routing_confidence == "standalone"
    assert package.matter_routing.standalone_reason is not None
    assert package.relevant_tracker_context["matters"] == []


def test_v3_routing_package_flags_new_matter_candidate_when_no_existing_match():
    payload = _base_pass1_payload()
    payload["observations"] = [
        {
            "id": "obs-a",
            "observation_type": "task_signal",
            "observation_subtype": "commitment",
            "summary": "Stephen will draft an outline for a new digital assets briefing.",
            "directness": "direct_commitment",
            "confidence": 0.82,
            "durability": "working",
            "memory_value": "none",
            "speaker_refs": [{"name": "Stephen Andrews"}],
            "entity_refs": [],
            "candidate_matter_refs": [],
            "candidate_record_refs": [],
            "field_hints": {"expected_output": "Outline for digital assets briefing"},
            "evidence": [{"excerpt": "I'll draft an outline for that.", "segments": ["seg-a"]}],
        },
        {
            "id": "obs-b",
            "observation_type": "matter_signal",
            "observation_subtype": "scope_change",
            "summary": "The workstream would cover a new digital assets briefing for leadership.",
            "directness": "direct_statement",
            "confidence": 0.78,
            "durability": "durable",
            "memory_value": "none",
            "speaker_refs": [{"name": "Stephen Andrews"}],
            "entity_refs": [],
            "candidate_matter_refs": [],
            "candidate_record_refs": [],
            "field_hints": {},
            "evidence": [{"excerpt": "This should become a briefing for leadership.", "segments": ["seg-b"]}],
        },
    ]

    pass1_output = CommunicationUnderstandingOutput(**payload)
    package = build_routing_resolution_package_from_context(
        communication_id="comm-new-matter",
        pass1_output=pass1_output,
        full_context={"people": [], "organizations": [], "matters": [], "standalone_tasks": [], "recent_meetings": []},
    )

    assert package.matter_routing.routing_confidence == "new_matter_candidate"
    assert package.matter_routing.new_matter_candidate is True
