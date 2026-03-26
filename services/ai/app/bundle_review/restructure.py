"""Bundle restructuring operations — move item, create bundle, merge bundles.

Move-as-copy pattern: moving an item marks the original as 'moved' and creates
a copy in the destination bundle with moved_from_bundle_id provenance.
"""

import uuid as uuid_mod

from fastapi import HTTPException

from app.pipeline.stages.extraction_models import VALID_BUNDLE_TYPES
from app.bundle_review.audit import write_audit


def move_item(
    db,
    communication_id: str,
    item_id: str,
    from_bundle_id: str,
    to_bundle_id: str,
    item: dict,
) -> dict:
    """Move an item from one bundle to another. Preserves provenance.

    Original is marked 'moved'. A copy is created in the destination
    with moved_from_bundle_id set and all source_locator data preserved.
    """
    if from_bundle_id == to_bundle_id:
        raise HTTPException(
            400,
            detail={
                "error_type": "validation_failure",
                "message": "Source and destination bundles are the same",
            },
        )

    if item["status"] == "moved":
        raise HTTPException(
            400,
            detail={
                "error_type": "invalid_state",
                "message": "Item has already been moved — operate on it in its current bundle",
            },
        )

    # Get next sort_order in target bundle
    max_sort = db.execute(
        "SELECT MAX(sort_order) as ms FROM review_bundle_items WHERE bundle_id = ?",
        (to_bundle_id,),
    ).fetchone()
    next_sort = (max_sort["ms"] or 0) + 1

    # Mark original item as moved (keep it for audit trail)
    db.execute(
        """
        UPDATE review_bundle_items
        SET status = 'moved', updated_at = datetime('now')
        WHERE id = ?
    """,
        (item_id,),
    )

    # Create copy in destination bundle with provenance preserved
    new_item_id = str(uuid_mod.uuid4())
    db.execute(
        """
        INSERT INTO review_bundle_items
            (id, bundle_id, item_type, status, proposed_data, original_proposed_data,
             confidence, rationale, source_excerpt, source_transcript_id,
             source_start_time, source_end_time, source_locator_json,
             sort_order, moved_from_bundle_id, created_at, updated_at)
        SELECT ?, ?, item_type, 'proposed', proposed_data, original_proposed_data,
               confidence, rationale, source_excerpt, source_transcript_id,
               source_start_time, source_end_time, source_locator_json,
               ?, ?, datetime('now'), datetime('now')
        FROM review_bundle_items WHERE id = ?
    """,
        (new_item_id, to_bundle_id, next_sort, from_bundle_id, item_id),
    )

    write_audit(
        db,
        communication_id,
        from_bundle_id,
        item_id,
        "move_item",
        {
            "item_type": item["item_type"],
            "from_bundle_id": from_bundle_id,
            "to_bundle_id": to_bundle_id,
            "new_item_id": new_item_id,
        },
    )
    db.commit()

    return {
        "status": "ok",
        "original_item_id": item_id,
        "new_item_id": new_item_id,
        "moved_to_bundle": to_bundle_id,
    }


def create_bundle(
    db,
    communication_id: str,
    bundle_type: str = "standalone",
    target_matter_id: str | None = None,
    target_matter_title: str | None = None,
    rationale: str | None = "Reviewer-created bundle",
    intelligence_notes: str | None = None,
) -> dict:
    """Create a new empty reviewer-created bundle."""
    if bundle_type not in VALID_BUNDLE_TYPES:
        raise HTTPException(
            400,
            detail={
                "error_type": "validation_failure",
                "message": f"Invalid bundle_type: {bundle_type}. Valid: {sorted(VALID_BUNDLE_TYPES)}",
            },
        )

    # Get next sort_order
    max_sort = db.execute(
        "SELECT MAX(sort_order) as ms FROM review_bundles WHERE communication_id = ?",
        (communication_id,),
    ).fetchone()
    next_sort = (max_sort["ms"] or 0) + 1

    bundle_id = str(uuid_mod.uuid4())
    db.execute(
        """
        INSERT INTO review_bundles
            (id, communication_id, bundle_type, target_matter_id,
             target_matter_title, status, confidence, rationale,
             intelligence_notes, sort_order, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, 'proposed', NULL, ?, ?, ?, datetime('now'), datetime('now'))
    """,
        (
            bundle_id,
            communication_id,
            bundle_type,
            target_matter_id,
            target_matter_title,
            rationale,
            intelligence_notes,
            next_sort,
        ),
    )

    write_audit(
        db,
        communication_id,
        bundle_id,
        None,
        "create_bundle",
        {
            "bundle_type": bundle_type,
            "target_matter_id": target_matter_id,
            "reviewer_created": True,
        },
    )
    db.commit()

    return {"status": "ok", "bundle_id": bundle_id, "bundle_type": bundle_type}


def merge_bundles(
    db,
    communication_id: str,
    source_bundle_id: str,
    target_bundle_id: str,
    source: dict,
    target: dict,
) -> dict:
    """Merge source bundle into target. Moves all items, rejects source."""
    if source_bundle_id == target_bundle_id:
        raise HTTPException(
            400,
            detail={
                "error_type": "validation_failure",
                "message": "Cannot merge a bundle into itself",
            },
        )

    if source["status"] == "rejected":
        raise HTTPException(
            400,
            detail={
                "error_type": "invalid_state",
                "message": "Source bundle is already rejected",
            },
        )

    # Get items from source (skip already-moved)
    source_items = db.execute(
        """
        SELECT id, item_type, status FROM review_bundle_items
        WHERE bundle_id = ? AND status != 'moved'
    """,
        (source_bundle_id,),
    ).fetchall()

    # Get next sort_order in target
    max_sort = db.execute(
        "SELECT MAX(sort_order) as ms FROM review_bundle_items WHERE bundle_id = ?",
        (target_bundle_id,),
    ).fetchone()
    next_sort = (max_sort["ms"] or 0) + 1

    moved_count = 0
    for si in source_items:
        # Mark original as moved
        db.execute(
            """
            UPDATE review_bundle_items
            SET status = 'moved', updated_at = datetime('now')
            WHERE id = ?
        """,
            (si["id"],),
        )

        # Copy to target with provenance
        new_id = str(uuid_mod.uuid4())
        db.execute(
            """
            INSERT INTO review_bundle_items
                (id, bundle_id, item_type, status, proposed_data, original_proposed_data,
                 confidence, rationale, source_excerpt, source_transcript_id,
                 source_start_time, source_end_time, source_locator_json,
                 sort_order, moved_from_bundle_id, created_at, updated_at)
            SELECT ?, ?, item_type, ?, proposed_data, original_proposed_data,
                   confidence, rationale, source_excerpt, source_transcript_id,
                   source_start_time, source_end_time, source_locator_json,
                   ?, ?, datetime('now'), datetime('now')
            FROM review_bundle_items WHERE id = ?
        """,
            (
                new_id,
                target_bundle_id,
                si["status"] if si["status"] in ("accepted", "edited") else "proposed",
                next_sort,
                source_bundle_id,
                si["id"],
            ),
        )
        next_sort += 1
        moved_count += 1

    # Reject the now-empty source bundle
    db.execute(
        """
        UPDATE review_bundles
        SET status = 'rejected', reviewed_by = 'user', reviewed_at = datetime('now'),
            updated_at = datetime('now')
        WHERE id = ?
    """,
        (source_bundle_id,),
    )

    write_audit(
        db,
        communication_id,
        target_bundle_id,
        None,
        "merge_bundles",
        {
            "source_bundle_id": source_bundle_id,
            "target_bundle_id": target_bundle_id,
            "items_moved": moved_count,
        },
    )
    db.commit()

    return {
        "status": "ok",
        "target_bundle_id": target_bundle_id,
        "source_bundle_id": source_bundle_id,
        "items_moved": moved_count,
    }
