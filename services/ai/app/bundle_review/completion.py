"""Bundle review completion — validate readiness, CAS transition, pipeline resume.

The complete function enforces that all bundles and items are in terminal
states before advancing the communication to 'reviewed'.
"""

import logging

from fastapi import HTTPException

from app.bundle_review.models import BUNDLE_REVIEW_STATES, BUNDLE_TERMINAL, ITEM_TERMINAL
from app.bundle_review.audit import write_audit
from app.pipeline.orchestrator import cas_transition

logger = logging.getLogger(__name__)


def complete_review(db, communication_id: str) -> dict:
    """Complete bundle review and advance the pipeline to reviewed.

    Validates that all bundles and items are in terminal states.
    Returns summary counts for the response. Does NOT trigger pipeline
    resume — the router handles that via BackgroundTasks.
    """
    comm = db.execute(
        "SELECT processing_status FROM communications WHERE id = ?",
        (communication_id,),
    ).fetchone()
    if not comm:
        raise HTTPException(404, detail={"error_type": "not_found"})

    status = comm["processing_status"]
    if status not in BUNDLE_REVIEW_STATES:
        raise HTTPException(400, detail={
            "error_type": "invalid_state",
            "message": f"Communication not in bundle review state (current: {status})",
        })

    # Get all bundles
    bundles = db.execute("""
        SELECT rb.id, rb.bundle_type, rb.status, rb.target_matter_title
        FROM review_bundles rb
        WHERE rb.communication_id = ?
    """, (communication_id,)).fetchall()

    blockers = []
    for b in bundles:
        if b["status"] not in BUNDLE_TERMINAL:
            blockers.append({
                "type": "bundle_not_resolved",
                "bundle_id": b["id"],
                "bundle_title": b["target_matter_title"],
                "current_status": b["status"],
            })
            continue

        if b["status"] == "rejected":
            continue  # All items in rejected bundles are moot

        # Check items in accepted bundles
        pending_items = db.execute("""
            SELECT id, item_type, status FROM review_bundle_items
            WHERE bundle_id = ? AND status NOT IN ('accepted', 'rejected', 'edited', 'moved')
        """, (b["id"],)).fetchall()

        for pi in pending_items:
            blockers.append({
                "type": "item_not_resolved",
                "bundle_id": b["id"],
                "item_id": pi["id"],
                "item_type": pi["item_type"],
                "current_status": pi["status"],
            })

    if blockers:
        raise HTTPException(400, detail={
            "error_type": "validation_failure",
            "message": f"Cannot complete: {len(blockers)} unresolved items/bundles remain",
            "blockers": blockers,
        })

    # Ensure we're in bundle_review_in_progress
    if status == "awaiting_bundle_review":
        cas_transition(db, communication_id, "awaiting_bundle_review", "bundle_review_in_progress")

    # Advance to reviewed
    if not cas_transition(db, communication_id, "bundle_review_in_progress", "reviewed"):
        raise HTTPException(409, detail={
            "error_type": "conflict",
            "message": "Status already changed by another process",
        })

    # Compute final counts
    accepted_bundles = sum(1 for b in bundles if b["status"] == "accepted")
    rejected_bundles = sum(1 for b in bundles if b["status"] == "rejected")

    all_items = db.execute("""
        SELECT ri.status, ri.item_type FROM review_bundle_items ri
        JOIN review_bundles rb ON ri.bundle_id = rb.id
        WHERE rb.communication_id = ?
    """, (communication_id,)).fetchall()

    items_accepted = sum(1 for i in all_items if i["status"] == "accepted")
    items_rejected = sum(1 for i in all_items if i["status"] == "rejected")
    items_edited = sum(1 for i in all_items if i["status"] == "edited")
    items_moved = sum(1 for i in all_items if i["status"] == "moved")

    zero_accepted = (items_accepted + items_edited) == 0

    write_audit(db, communication_id, None, None, "complete_bundle_review", {
        "accepted_bundles": accepted_bundles,
        "rejected_bundles": rejected_bundles,
        "items_accepted": items_accepted,
        "items_rejected": items_rejected,
        "items_edited": items_edited,
        "items_moved": items_moved,
        "zero_accepted_items": zero_accepted,
    })
    db.commit()

    logger.info(
        "[%s] Bundle review completed: %d/%d bundles accepted, %d items accepted, %d edited",
        communication_id[:8], accepted_bundles, len(bundles),
        items_accepted, items_edited,
    )

    return {
        "status": "reviewed",
        "communication_id": communication_id,
        "accepted_bundles": accepted_bundles,
        "rejected_bundles": rejected_bundles,
        "items_accepted": items_accepted,
        "items_rejected": items_rejected,
        "items_edited": items_edited,
        "items_moved": items_moved,
        "zero_accepted_items": zero_accepted,
    }


async def resume_pipeline(communication_id: str):
    """Resume pipeline after bundle review gate.

    Called as a BackgroundTask from the router after successful completion.
    """
    from app.pipeline.orchestrator import process_communication
    try:
        await process_communication(communication_id)
    except Exception as e:
        logger.exception("Pipeline resume failed for %s: %s", communication_id, e)
