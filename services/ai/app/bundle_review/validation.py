"""Validation logic for bundle review — proposed_data checks and completion blockers.

These functions are pure logic with no DB writes. They raise HTTPException
on validation failure for consistency with the router layer.
"""

from fastapi import HTTPException

from app.bundle_review.models import BUNDLE_TERMINAL, ITEM_TERMINAL


def validate_proposed_data(item_type: str, data: dict):
    """Validate item_type-specific required fields in proposed_data.

    Raises HTTPException 400 on validation failure.
    """
    required = {}
    if item_type == "task":
        required = {"title": str}
    elif item_type == "follow_up":
        required = {"title": str}
    elif item_type == "matter_update":
        required = {"summary": str}
    elif item_type == "meeting_record":
        required = {"title": str}
    elif item_type == "stakeholder_addition":
        # Need at least person_id or organization_id or a name
        if not (
            data.get("person_id")
            or data.get("organization_id")
            or data.get("person_name")
            or data.get("organization_name")
        ):
            raise HTTPException(
                400,
                detail={
                    "error_type": "validation_failure",
                    "message": "stakeholder_addition requires person_id, organization_id, "
                    "person_name, or organization_name",
                },
            )
        return
    elif item_type == "document":
        required = {"title": str}
    elif item_type == "decision":
        required = {"title": str}
    elif item_type == "status_change":
        required = {"field": str, "new_value": str}
    elif item_type in ("new_person",):
        required = {"full_name": str}
    elif item_type in ("new_organization",):
        required = {"name": str}

    missing = [k for k in required if not data.get(k)]
    if missing:
        raise HTTPException(
            400,
            detail={
                "error_type": "validation_failure",
                "message": f"{item_type} requires: {', '.join(missing)}",
            },
        )


def compute_blockers(bundles: list[dict]) -> list[dict]:
    """Compute what blocks review completion.

    Expects bundles with nested 'items' lists (as returned by retrieval.get_detail).
    Returns a list of blocker dicts, empty if ready to complete.
    """
    blockers = []
    for b in bundles:
        if b["status"] not in BUNDLE_TERMINAL:
            blockers.append(
                {
                    "type": "bundle_not_resolved",
                    "bundle_id": b["id"],
                    "bundle_title": b.get("target_matter_title"),
                    "current_status": b["status"],
                }
            )
            continue
        if b["status"] == "rejected":
            continue
        for item in b.get("items", []):
            if item["status"] not in ITEM_TERMINAL:
                blockers.append(
                    {
                        "type": "item_not_resolved",
                        "bundle_id": b["id"],
                        "item_id": item["id"],
                        "item_type": item["item_type"],
                        "current_status": item["status"],
                    }
                )
    return blockers
