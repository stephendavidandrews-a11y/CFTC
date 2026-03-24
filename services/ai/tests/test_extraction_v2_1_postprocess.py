"""Focused post-processing regression tests for v2.1 behavior."""

import sys
from pathlib import Path


AI_SERVICE_DIR = Path(__file__).resolve().parents[1]
if str(AI_SERVICE_DIR) not in sys.path:
    sys.path.insert(0, str(AI_SERVICE_DIR))

from app.pipeline.stages.extraction import _post_process  # noqa: E402
from app.pipeline.stages.extraction_models import ExtractionOutput  # noqa: E402


PERSON_TYLER_ID = "aaaaaaaa-1111-4000-8000-000000000001"
PERSON_STEPHEN_ID = "aaaaaaaa-1111-4000-8000-000000000002"
PERSON_MEGHAN_ID = "aaaaaaaa-1111-4000-8000-000000000004"
MATTER_CRYPTO_ID = "cccccccc-3333-4000-8000-000000000001"

FULL_CONTEXT = {
    "people": [
        {"id": PERSON_TYLER_ID, "full_name": "Tyler S. Badgley"},
        {"id": PERSON_STEPHEN_ID, "full_name": "Stephen Andrews"},
        {"id": PERSON_MEGHAN_ID, "full_name": "Meghan Tenney"},
    ],
    "organizations": [],
    "matters": [
        {
            "id": MATTER_CRYPTO_ID,
            "title": "Crypto Derivatives NPRM",
            "open_tasks": [],
            "open_decisions": [],
            "stakeholders": [],
            "organizations": [],
            "recent_updates": [],
        }
    ],
    "standalone_tasks": [],
}

POLICY = {
    "extraction_policy": {},
    "routing_policy": {
        "match_confidence_minimum": 0.7,
        "standalone_items_enabled": True,
        "max_new_matters_per_communication": 5,
    },
}


def _sample_evidence(speaker: str, excerpt: str) -> list[dict]:
    return [{
        "excerpt": excerpt,
        "segments": ["seg-001"],
        "time_range": {"start": 1.0, "end": 2.0},
        "speaker": speaker,
    }]


def test_v2_1_postprocess_repairs_shapes_without_rewriting_task_ownership():
    payload = {
        "extraction_version": "2.0.0",
        "communication_id": "comm-001",
        "extraction_summary": "Test payload.",
        "matter_associations": [],
        "bundles": [
            {
                "bundle_type": "matter",
                "target_matter_id": MATTER_CRYPTO_ID,
                "target_matter_title": "Crypto Derivatives NPRM",
                "proposed_matter": None,
                "confidence": 0.9,
                "rationale": "Single matter bundle.",
                "intelligence_notes": None,
                "uncertainty_flags": [],
                "items": [
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
                        "source_evidence": _sample_evidence(
                            "Tyler S. Badgley",
                            "I need to ask Rusty who the right touch points are.",
                        ),
                    },
                    {
                        "item_type": "task",
                        "proposed_data": {
                            "title": "Follow up with Tyler on SEC crypto regulatory contacts",
                            "status": "not started",
                            "task_mode": "follow_up",
                            "tracks_task_ref": "$ref:temp-tyler-sec-contacts",
                            "waiting_on_person_id": PERSON_TYLER_ID,
                            "waiting_on_description": "Tyler to ask Rusty at SEC about crypto touch points",
                        },
                        "confidence": 0.91,
                        "rationale": "Stephen should track Tyler's follow-through.",
                        "source_evidence": _sample_evidence(
                            "Stephen Andrews",
                            "I want to keep a smooth relationship on the crypto side.",
                        ),
                    },
                    {
                        "item_type": "context_note",
                        "proposed_data": {
                            "title": "CFTC four major priorities",
                            "content": "The four priorities are crypto, prediction markets, Dodd-Frank reforms, and SEC harmonization.",
                            "category": "strategic_priorities",
                            "posture": "neutral",
                            "sensitivity": "medium",
                            "tags": ["priority-list"],
                        },
                        "confidence": 0.84,
                        "rationale": "Durable strategic context.",
                        "source_evidence": _sample_evidence(
                            "Tyler S. Badgley",
                            "The four priorities are crypto, prediction markets, Dodd-Frank reforms, and SEC harmonization.",
                        ),
                    },
                    {
                        "item_type": "person_detail_update",
                        "proposed_data": {
                            "person_id": PERSON_MEGHAN_ID,
                            "person_name": "Meghan Tenney",
                            "prior_roles_summary": "Serves as special projects coordinator and go-between for CFTC-SEC harmonization efforts.",
                        },
                        "confidence": 0.82,
                        "rationale": "Useful recurring person memory.",
                        "source_evidence": _sample_evidence(
                            "Tyler S. Badgley",
                            "Meghan is the go-between on harmonization.",
                        ),
                    },
                ],
            }
        ],
        "suppressed_observations": [],
        "unmatched_intelligence": None,
    }

    extraction = ExtractionOutput(**payload)
    processed = _post_process(
        extraction=extraction,
        full_context=FULL_CONTEXT,
        policy=POLICY,
        db=None,
        communication_id="comm-001",
    )

    items = processed["bundles"][0].items
    action_task = items[0]
    follow_up_task = items[1]
    context_note = items[2]
    person_detail = items[3]

    assert action_task.proposed_data["assigned_to_person_id"] == PERSON_TYLER_ID
    assert follow_up_task.proposed_data["waiting_on_person_id"] == PERSON_TYLER_ID
    assert follow_up_task.proposed_data["tracks_task_ref"] == "$ref:temp-tyler-sec-contacts"

    assert context_note.proposed_data["body"].startswith("The four priorities are crypto")
    assert "content" not in context_note.proposed_data
    assert "tags" not in context_note.proposed_data
    assert context_note.proposed_data["category"] == "strategic_context"
    assert context_note.proposed_data["posture"] == "attributed_view"
    assert context_note.proposed_data["speaker_attribution"] == "Tyler S. Badgley"
    assert context_note.proposed_data["sensitivity"] == "moderate"

    assert "prior_roles_summary" not in person_detail.proposed_data
    assert "prior_roles_summary" not in person_detail.proposed_data["fields"]
    assert "go-between" in person_detail.proposed_data["fields"]["personal_notes_summary"].lower()

    repairs = processed["post_processing_log"]["shape_repairs"]
    assert len(repairs) >= 4
