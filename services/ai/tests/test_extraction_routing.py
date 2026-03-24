"""Routing tests for extraction context tiering."""

import sys
from pathlib import Path


AI_SERVICE_DIR = Path(__file__).resolve().parents[1]
if str(AI_SERVICE_DIR) not in sys.path:
    sys.path.insert(0, str(AI_SERVICE_DIR))

from app.pipeline.stages.extraction import _tier_context  # noqa: E402


def test_tier_context_promotes_matters_via_stakeholders_and_org_links():
    """Tier 1 routing uses matter_people and matter_organizations relationships."""
    full_context = {
        "matters": [
            {
                "id": "matter-stakeholder",
                "title": "Stakeholder matter",
                "matter_type": "rulemaking",
                "status": "draft in progress",
                "priority": "important this month",
                "stakeholders": [{"person_id": "person-1", "full_name": "Tyler S. Badgley"}],
                "organizations": [],
                "tags": [],
            },
            {
                "id": "matter-org",
                "title": "Org-linked matter",
                "matter_type": "rulemaking",
                "status": "research in progress",
                "priority": "critical this week",
                "stakeholders": [],
                "organizations": [{"organization_id": "org-1", "name": "SEC"}],
                "tags": [],
            },
            {
                "id": "matter-unrelated",
                "title": "Unrelated matter",
                "matter_type": "other",
                "status": "parked / monitoring",
                "priority": "monitoring only",
                "stakeholders": [],
                "organizations": [],
                "tags": [],
            },
        ],
        "recent_meetings": [],
        "people": [],
        "organizations": [],
        "standalone_tasks": [],
    }
    signals = {
        "speaker_person_ids": {"person-1"},
        "entity_person_ids": set(),
        "entity_org_ids": {"org-1"},
        "identifier_hits": {"rin": set(), "docket": set(), "cfr": set()},
    }

    tiered = _tier_context(full_context, signals)
    tier_1_ids = {matter["id"] for matter in tiered["tier_1_matters"]}
    tier_2_ids = {matter["id"] for matter in tiered["tier_2_matters"]}

    assert "matter-stakeholder" in tier_1_ids
    assert "matter-org" in tier_1_ids
    assert "matter-unrelated" in tier_2_ids
    assert tiered["tier_stats"]["tier_1_matter_count"] == 2
