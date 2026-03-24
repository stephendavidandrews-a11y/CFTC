"""Tests for extraction_v3_models."""

import pytest
from pydantic import ValidationError

from app.pipeline.stages.extraction_v3_models import (
    CommunicationUnderstandingOutput,
    RoutingResolutionPackage,
    V3Bundle,
    V3ExtractionOutput,
    V3ProposalItem,
)


def _sample_evidence():
    return [{
        "excerpt": "I need it by the 15th now, not end of month.",
        "speaker": "Tyler S. Badgley",
        "segments": ["seg-005"],
        "time_range": {"start": 312.4, "end": 325.8},
    }]


def test_pass1_accepts_person_memory_management_guidance():
    payload = {
        "communication_id": "comm-001",
        "communication_kind": "audio",
        "communication_summary": "Team management discussion.",
        "participants": [],
        "observations": [{
            "id": "obs-001",
            "observation_type": "person_memory_signal",
            "observation_subtype": "management_guidance",
            "summary": "Priya responds best to direct framing and quick iteration.",
            "directness": "direct_statement",
            "confidence": 0.87,
            "durability": "durable",
            "memory_value": "high",
            "speaker_refs": [{"name": "Tyler S. Badgley"}],
            "entity_refs": [{"entity_type": "person", "name": "Priya Sharma"}],
            "field_hints": {
                "leadership_notes": "Works best with direct framing and quick iteration.",
            },
            "evidence": _sample_evidence(),
        }],
    }

    output = CommunicationUnderstandingOutput(**payload)
    obs = output.observations[0]
    assert obs.observation_type == "person_memory_signal"
    assert obs.observation_subtype == "management_guidance"


def test_pass1_accepts_concept_and_legislation_entity_refs():
    payload = {
        "communication_id": "comm-001",
        "communication_kind": "audio",
        "communication_summary": "Policy discussion with legislative references.",
        "participants": [],
        "observations": [{
            "id": "obs-001",
            "observation_type": "institutional_memory_signal",
            "observation_subtype": "strategic_context",
            "summary": "Tyler discussed crypto and Dodd-Frank priorities.",
            "directness": "direct_statement",
            "confidence": 0.82,
            "durability": "durable",
            "memory_value": "high",
            "entity_refs": [
                {"entity_type": "concept", "name": "crypto"},
                {"entity_type": "legislation", "name": "Dodd-Frank"},
            ],
            "evidence": _sample_evidence(),
        }],
    }

    output = CommunicationUnderstandingOutput(**payload)
    assert output.observations[0].entity_refs[0].entity_type == "concept"
    assert output.observations[0].entity_refs[1].entity_type == "legislation"


def test_pass1_rejects_invalid_subtype_for_observation_type():
    payload = {
        "communication_id": "comm-001",
        "communication_kind": "audio",
        "communication_summary": "Bad subtype test.",
        "observations": [{
            "id": "obs-001",
            "observation_type": "task_signal",
            "observation_subtype": "biography",
            "summary": "Bad subtype.",
            "directness": "direct_statement",
            "confidence": 0.5,
            "durability": "working",
            "memory_value": "none",
            "evidence": _sample_evidence(),
        }],
    }

    with pytest.raises(ValidationError):
        CommunicationUnderstandingOutput(**payload)


def test_memory_observations_require_memory_value():
    payload = {
        "communication_id": "comm-001",
        "communication_kind": "audio",
        "communication_summary": "Missing memory value.",
        "observations": [{
            "id": "obs-001",
            "observation_type": "institutional_memory_signal",
            "observation_subtype": "operating_rule",
            "summary": "OGC-Reg writes major rules directly when bandwidth allows.",
            "directness": "direct_statement",
            "confidence": 0.9,
            "durability": "durable",
            "memory_value": "none",
            "evidence": _sample_evidence(),
        }],
    }

    with pytest.raises(ValidationError):
        CommunicationUnderstandingOutput(**payload)


def test_routing_package_requires_standalone_reason_for_standalone():
    payload = {
        "communication_id": "comm-001",
        "resolved_people": [],
        "resolved_organizations": [],
        "matter_routing": {
            "primary_matter_id": None,
            "secondary_matter_ids": [],
            "routing_confidence": "standalone",
            "routing_basis": [],
            "new_matter_candidate": False,
        },
        "record_matches": {},
        "relevant_tracker_context": {},
    }

    with pytest.raises(ValidationError):
        RoutingResolutionPackage(**payload)


def test_pass2_rejects_new_matter_as_item_type():
    with pytest.raises(ValidationError):
        V3ProposalItem(
            item_type="new_matter",
            proposed_data={},
            confidence=0.9,
            rationale="Bad item type.",
            why_new_vs_update="Bad test.",
            why_this_matter="Bad test.",
            source_observation_ids=["obs-001"],
            source_evidence=_sample_evidence(),
        )


def test_new_matter_bundle_requires_bundle_level_proposed_matter():
    with pytest.raises(ValidationError):
        V3Bundle(
            bundle_type="new_matter",
            confidence=0.9,
            rationale="New matter bundle.",
            items=[V3ProposalItem(
                item_type="task",
                proposed_data={"title": "Do thing"},
                confidence=0.9,
                rationale="Task.",
                why_new_vs_update="New task.",
                why_this_matter="Part of proposed workstream.",
                source_observation_ids=["obs-001"],
                source_evidence=_sample_evidence(),
            )],
        )


def test_pass2_accepts_contract_aligned_output():
    payload = {
        "communication_id": "comm-001",
        "extraction_summary": "Deadline changed and one useful person memory item surfaced.",
        "routing_assessment": {
            "primary_matter_id": "matter-001",
            "secondary_matter_ids": [],
            "routing_confidence": "high",
            "routing_basis": ["speaker is matter stakeholder"],
            "new_matter_candidate": False,
        },
        "bundles": [{
            "bundle_type": "matter",
            "target_matter_id": "matter-001",
            "target_matter_title": "Crypto Derivatives NPRM",
            "confidence": 0.93,
            "rationale": "Most changes belong to this matter.",
            "items": [
                {
                    "item_type": "task_update",
                    "proposed_data": {
                        "existing_task_id": "task-001",
                        "changes": {
                            "due_date": "2026-04-15",
                            "priority": "high",
                        },
                    },
                    "confidence": 0.95,
                    "rationale": "Existing task clearly changed.",
                    "why_new_vs_update": "Matches existing task by title and deliverable.",
                    "why_this_matter": "The task is already tracked under this matter.",
                    "source_observation_ids": ["obs-001"],
                    "source_evidence": _sample_evidence(),
                },
                {
                    "item_type": "person_detail_update",
                    "proposed_data": {
                        "person_id": "person-001",
                        "fields": {
                            "leadership_notes": "Responds best to direct framing and quick iteration.",
                        },
                    },
                    "confidence": 0.88,
                    "rationale": "Durable management guidance worth remembering.",
                    "why_new_vs_update": "This belongs on the existing person profile.",
                    "why_this_matter": "Same communication bundle; not a separate matter write.",
                    "source_observation_ids": ["obs-002"],
                    "source_evidence": _sample_evidence(),
                },
            ],
        }],
        "suppressed_observations": [{
            "observation_id": "obs-003",
            "observation_type": "person_memory_signal",
            "observation_subtype": "preference",
            "description": "Possible useful preference noticed but not committed.",
            "reason_noted": "Useful but below commit threshold.",
            "candidate_item_type": "person_detail_update",
            "candidate_fields": {"interests": "distance running"},
            "confidence_if_enabled": 0.62,
            "source_excerpt": "I usually do long runs before work.",
            "source_segments": ["seg-021"],
        }],
    }

    output = V3ExtractionOutput(**payload)
    assert output.bundles[0].items[1].item_type == "person_detail_update"
    assert output.suppressed_observations[0].observation_subtype == "preference"


def test_pass2_accepts_canonical_context_note_shape():
    item = V3ProposalItem(
        item_type="context_note",
        proposed_data={
            "title": "Leadership expects OGC-Reg to draft major rules directly",
            "body": "Tyler said OGC-Reg should take the pen on major rules when bandwidth allows.",
            "category": "policy_operating_rule",
            "posture": "attributed_view",
            "speaker_attribution": "Tyler S. Badgley",
            "durability": "durable",
            "sensitivity": "moderate",
            "linked_entities": [
                {"entity_type": "organization", "entity_id": "org-001", "relationship_role": "subject"},
            ],
        },
        confidence=0.93,
        rationale="Durable operating guidance.",
        why_new_vs_update="New durable note rather than update.",
        why_this_matter="Standalone office guidance.",
        source_observation_ids=["obs-001"],
        source_evidence=_sample_evidence(),
    )

    assert item.proposed_data["category"] == "policy_operating_rule"


def test_pass2_rejects_noncanonical_context_note_shape():
    with pytest.raises(ValidationError):
        V3ProposalItem(
            item_type="context_note",
            proposed_data={
                "title": "Bad note",
                "content": "Wrong key",
                "category": "strategic_priorities",
                "posture": "neutral",
            },
            confidence=0.7,
            rationale="Bad shape.",
            why_new_vs_update="Bad test.",
            why_this_matter="Bad test.",
            source_observation_ids=["obs-001"],
            source_evidence=_sample_evidence(),
        )


def test_pass2_rejects_flat_person_detail_update_fields():
    with pytest.raises(ValidationError):
        V3ProposalItem(
            item_type="person_detail_update",
            proposed_data={
                "person_id": "person-001",
                "prior_roles_summary": "Eight years at SEC",
            },
            confidence=0.88,
            rationale="Bad person field shape.",
            why_new_vs_update="Bad test.",
            why_this_matter="Bad test.",
            source_observation_ids=["obs-002"],
            source_evidence=_sample_evidence(),
        )
