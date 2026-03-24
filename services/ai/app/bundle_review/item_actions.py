"""Item-level review actions — accept, reject, edit, restore, add.

All functions take a db connection and return a result dict.
State guards (check_review_state, ensure_in_progress) are the caller's
responsibility — the router calls them before dispatching here.
"""

import json
import uuid as uuid_mod

from fastapi import HTTPException

from app.pipeline.stages.extraction_models import VALID_ITEM_TYPES
from app.bundle_review.audit import write_audit
from app.bundle_review.validation import validate_proposed_data


def accept_item(db, communication_id: str, bundle_id: str, item_id: str,
                item: dict) -> dict:
    """Accept a single item. Returns {item_id, new_status}."""
    if item["status"] in ("rejected", "moved"):
        raise HTTPException(400, detail={
            "error_type": "invalid_state",
            "message": f"Cannot accept item in '{item['status']}' state",
        })

    # CAS: only update if item is still in expected state
    cursor = db.execute("""
        UPDATE review_bundle_items
        SET status = 'accepted', reviewed_at = datetime('now'), updated_at = datetime('now')
        WHERE id = ? AND status = ?
    """, (item_id, item["status"]))
    if cursor.rowcount == 0:
        raise HTTPException(409, detail={
            "error_type": "concurrent_modification",
            "message": "Item %s status changed since read (expected '%s')" % (item_id, item["status"]),
        })

    write_audit(db, communication_id, bundle_id, item_id, "accept_item", {
        "item_type": item["item_type"],
        "old_status": item["status"],
    })
    db.commit()
    return {"status": "ok", "item_id": item_id, "new_status": "accepted"}


def reject_item(db, communication_id: str, bundle_id: str, item_id: str,
                item: dict, reason: str | None = None) -> dict:
    """Reject a single item. Returns {item_id, new_status}."""
    if item["status"] == "moved":
        raise HTTPException(400, detail={
            "error_type": "invalid_state",
            "message": "Cannot reject a moved item — reject it in its destination bundle",
        })

    # CAS: only update if item is still in expected state
    cursor = db.execute("""
        UPDATE review_bundle_items
        SET status = 'rejected', reviewed_at = datetime('now'), updated_at = datetime('now')
        WHERE id = ? AND status = ?
    """, (item_id, item["status"]))
    if cursor.rowcount == 0:
        raise HTTPException(409, detail={
            "error_type": "concurrent_modification",
            "message": "Item %s status changed since read (expected '%s')" % (item_id, item["status"]),
        })

    write_audit(db, communication_id, bundle_id, item_id, "reject_item", {
        "item_type": item["item_type"],
        "old_status": item["status"],
        "reason": reason,
    })
    db.commit()
    return {"status": "ok", "item_id": item_id, "new_status": "rejected"}


def edit_item(db, communication_id: str, bundle_id: str, item_id: str,
              item: dict, proposed_data: dict) -> dict:
    """Edit an item's proposed_data. Preserves original_proposed_data on first edit.

    Sets status to 'edited' (implies acceptance).
    """
    if item["status"] == "moved":
        raise HTTPException(400, detail={
            "error_type": "invalid_state",
            "message": "Cannot edit a moved item — edit it in its destination bundle",
        })

    if not proposed_data:
        raise HTTPException(400, detail={
            "error_type": "validation_failure",
            "message": "proposed_data cannot be empty",
        })

    validate_proposed_data(item["item_type"], proposed_data)

    # Preserve original on first edit only
    current_data = item["proposed_data"]
    new_data_json = json.dumps(proposed_data, ensure_ascii=False)

    if item["original_proposed_data"] is None:
        db.execute("""
            UPDATE review_bundle_items
            SET original_proposed_data = ?,
                proposed_data = ?,
                status = 'edited',
                reviewed_at = datetime('now'),
                updated_at = datetime('now')
            WHERE id = ?
        """, (current_data, new_data_json, item_id))
    else:
        db.execute("""
            UPDATE review_bundle_items
            SET proposed_data = ?,
                status = 'edited',
                reviewed_at = datetime('now'),
                updated_at = datetime('now')
            WHERE id = ?
        """, (new_data_json, item_id))

    write_audit(db, communication_id, bundle_id, item_id, "edit_item", {
        "item_type": item["item_type"],
        "old_status": item["status"],
        "fields_changed": list(proposed_data.keys()),
    })
    db.commit()
    return {"status": "ok", "item_id": item_id, "new_status": "edited"}


def restore_item(db, communication_id: str, bundle_id: str, item_id: str,
                 item: dict) -> dict:
    """Restore an edited item to its original proposed_data."""
    if item["original_proposed_data"] is None:
        raise HTTPException(400, detail={
            "error_type": "validation_failure",
            "message": "Item has not been edited — nothing to restore",
        })

    db.execute("""
        UPDATE review_bundle_items
        SET proposed_data = original_proposed_data,
            original_proposed_data = NULL,
            status = 'proposed',
            reviewed_at = NULL,
            updated_at = datetime('now')
        WHERE id = ?
    """, (item_id,))

    write_audit(db, communication_id, bundle_id, item_id, "restore_item", {
        "item_type": item["item_type"],
        "old_status": item["status"],
    })
    db.commit()
    return {"status": "ok", "item_id": item_id, "new_status": "proposed"}


def add_item(db, communication_id: str, bundle_id: str,
             item_type: str, proposed_data: dict,
             rationale: str | None = None,
             source_excerpt: str | None = None,
             source_start_time: float | None = None,
             source_end_time: float | None = None) -> dict:
    """Add a reviewer-created item to an existing bundle.

    Reviewer items have confidence=NULL and status='accepted'.
    """
    if item_type not in VALID_ITEM_TYPES:
        raise HTTPException(400, detail={
            "error_type": "validation_failure",
            "message": f"Invalid item_type: {item_type}. Valid: {sorted(VALID_ITEM_TYPES)}",
        })

    if not proposed_data:
        raise HTTPException(400, detail={
            "error_type": "validation_failure",
            "message": "proposed_data cannot be empty",
        })

    validate_proposed_data(item_type, proposed_data)

    # Get next sort_order
    max_sort = db.execute(
        "SELECT MAX(sort_order) as ms FROM review_bundle_items WHERE bundle_id = ?",
        (bundle_id,),
    ).fetchone()
    next_sort = (max_sort["ms"] or 0) + 1

    item_id = str(uuid_mod.uuid4())

    # Build source_locator if any provenance provided
    source_locator = None
    if source_excerpt or source_start_time is not None:
        source_locator = json.dumps({
            "type": "reviewer",
            "excerpt": source_excerpt,
            "time_range": {
                "start_seconds": source_start_time,
                "end_seconds": source_end_time,
            } if source_start_time is not None else None,
        })

    db.execute("""
        INSERT INTO review_bundle_items
            (id, bundle_id, item_type, status, proposed_data,
             confidence, rationale, source_excerpt,
             source_start_time, source_end_time, source_locator_json,
             sort_order, created_at, updated_at)
        VALUES (?, ?, ?, 'accepted', ?, NULL, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
    """, (
        item_id, bundle_id, item_type,
        json.dumps(proposed_data, ensure_ascii=False),
        rationale, source_excerpt,
        source_start_time, source_end_time,
        source_locator, next_sort,
    ))

    write_audit(db, communication_id, bundle_id, item_id, "add_item", {
        "item_type": item_type,
        "reviewer_created": True,
        "proposed_data_keys": list(proposed_data.keys()),
    })
    db.commit()
    return {"status": "ok", "item_id": item_id, "new_status": "accepted"}
