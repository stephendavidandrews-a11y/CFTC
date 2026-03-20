"""Dependency ordering for bundle items within a single batch.

new_organization must precede new_person (org_id ref),
new_person must precede items referencing person_id,
new_matter bundle-level insert must precede all items (handled by committer),
meeting_record before stakeholder_addition (participant refs).
"""

# Priority tiers — lower number = earlier in batch
ITEM_TYPE_ORDER = {
    "new_organization": 0,
    "new_person": 1,
    "meeting_record": 2,
    "stakeholder_addition": 3,
    "document": 4,
    "task": 5,
    "follow_up": 6,
    "matter_update": 7,
    "decision": 8,
    "status_change": 9,
    "context_note": 10,
    "person_detail_update": 11,
}


def order_items(items: list[dict]) -> list[dict]:
    """Sort items by dependency-safe write order.

    Within the same tier, items are sorted by sort_order (DB-assigned).
    """
    return sorted(items, key=lambda i: (
        ITEM_TYPE_ORDER.get(i["item_type"], 99),
        i.get("sort_order", 0),
    ))
