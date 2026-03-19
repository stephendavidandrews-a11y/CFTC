"""Bundle-level review actions — accept, reject, edit, accept-all.

All functions take a db connection and return a result dict.
State guards are the caller's responsibility.
"""

from fastapi import HTTPException

from app.pipeline.stages.extraction_models import VALID_BUNDLE_TYPES
from app.bundle_review.models import BUNDLE_TERMINAL
from app.bundle_review.audit import write_audit


def accept_bundle(db, communication_id: str, bundle_id: str,
                  bundle: dict) -> dict:
    """Accept an entire bundle. Auto-accepts all proposed items within it."""
    if bundle["status"] in BUNDLE_TERMINAL:
        raise HTTPException(400, detail={
            "error_type": "invalid_state",
            "message": f"Bundle already in terminal state: {bundle['status']}",
        })

    db.execute("""
        UPDATE review_bundles
        SET status = 'accepted', reviewed_by = 'user', reviewed_at = datetime('now'),
            updated_at = datetime('now')
        WHERE id = ?
    """, (bundle_id,))

    # Auto-accept all proposed items (don't touch already-rejected or edited items)
    auto_count = db.execute("""
        UPDATE review_bundle_items
        SET status = 'accepted', reviewed_at = datetime('now'), updated_at = datetime('now')
        WHERE bundle_id = ? AND status = 'proposed'
    """, (bundle_id,)).rowcount

    write_audit(db, communication_id, bundle_id, None, "accept_bundle", {
        "bundle_type": bundle["bundle_type"],
        "target_matter": bundle["target_matter_title"],
        "auto_accepted_items": auto_count,
    })
    db.commit()

    return {"status": "ok", "bundle_id": bundle_id, "new_status": "accepted",
            "auto_accepted_items": auto_count}


def reject_bundle(db, communication_id: str, bundle_id: str,
                  bundle: dict, reason: str | None = None) -> dict:
    """Reject an entire bundle. Auto-rejects all non-moved items."""
    if bundle["status"] in BUNDLE_TERMINAL:
        raise HTTPException(400, detail={
            "error_type": "invalid_state",
            "message": f"Bundle already in terminal state: {bundle['status']}",
        })

    db.execute("""
        UPDATE review_bundles
        SET status = 'rejected', reviewed_by = 'user', reviewed_at = datetime('now'),
            updated_at = datetime('now')
        WHERE id = ?
    """, (bundle_id,))

    auto_count = db.execute("""
        UPDATE review_bundle_items
        SET status = 'rejected', reviewed_at = datetime('now'), updated_at = datetime('now')
        WHERE bundle_id = ? AND status IN ('proposed', 'accepted', 'edited')
    """, (bundle_id,)).rowcount

    write_audit(db, communication_id, bundle_id, None, "reject_bundle", {
        "bundle_type": bundle["bundle_type"],
        "target_matter": bundle["target_matter_title"],
        "auto_rejected_items": auto_count,
        "reason": reason,
    })
    db.commit()

    return {"status": "ok", "bundle_id": bundle_id, "new_status": "rejected",
            "auto_rejected_items": auto_count}


def edit_bundle(db, communication_id: str, bundle_id: str, bundle: dict,
                target_matter_id: str | None = None,
                target_matter_title: str | None = None,
                bundle_type: str | None = None,
                intelligence_notes: str | None = None,
                rationale: str | None = None) -> dict:
    """Edit bundle metadata: target matter, type, notes, rationale."""
    if bundle["status"] == "rejected":
        raise HTTPException(400, detail={
            "error_type": "invalid_state",
            "message": "Cannot edit a rejected bundle",
        })

    if bundle_type and bundle_type not in VALID_BUNDLE_TYPES:
        raise HTTPException(400, detail={
            "error_type": "validation_failure",
            "message": f"Invalid bundle_type: {bundle_type}. Valid: {sorted(VALID_BUNDLE_TYPES)}",
        })

    updates = []
    params = []
    old_values = {}

    for field, value in [
        ("target_matter_id", target_matter_id),
        ("target_matter_title", target_matter_title),
        ("bundle_type", bundle_type),
        ("intelligence_notes", intelligence_notes),
        ("rationale", rationale),
    ]:
        if value is not None:
            updates.append(f"{field} = ?")
            params.append(value)
            old_values[field] = bundle[field]

    # If setting to standalone, clear target_matter_id
    if bundle_type == "standalone" and target_matter_id is None:
        if "target_matter_id" not in old_values:
            updates.append("target_matter_id = NULL")
            old_values["target_matter_id"] = bundle["target_matter_id"]

    if not updates:
        raise HTTPException(400, detail={
            "error_type": "validation_failure",
            "message": "No fields to update",
        })

    updates.append("updated_at = datetime('now')")
    params.append(bundle_id)

    db.execute(
        f"UPDATE review_bundles SET {', '.join(updates)} WHERE id = ?",
        params,
    )

    new_values = {}
    for k, v in [("target_matter_id", target_matter_id),
                 ("target_matter_title", target_matter_title),
                 ("bundle_type", bundle_type),
                 ("intelligence_notes", intelligence_notes),
                 ("rationale", rationale)]:
        if v is not None:
            new_values[k] = v

    write_audit(db, communication_id, bundle_id, None, "edit_bundle", {
        "old_values": old_values,
        "new_values": new_values,
    })
    db.commit()

    return {"status": "ok", "bundle_id": bundle_id, "edited": True}


def accept_all(db, communication_id: str) -> dict:
    """Bulk-accept all proposed bundles and their proposed items."""
    bundles_accepted = db.execute("""
        UPDATE review_bundles
        SET status = 'accepted', reviewed_by = 'user', reviewed_at = datetime('now'),
            updated_at = datetime('now')
        WHERE communication_id = ? AND status = 'proposed'
    """, (communication_id,)).rowcount

    items_accepted = db.execute("""
        UPDATE review_bundle_items
        SET status = 'accepted', reviewed_at = datetime('now'), updated_at = datetime('now')
        WHERE bundle_id IN (
            SELECT id FROM review_bundles WHERE communication_id = ?
        ) AND status = 'proposed'
    """, (communication_id,)).rowcount

    write_audit(db, communication_id, None, None, "accept_all", {
        "bundles_accepted": bundles_accepted,
        "items_accepted": items_accepted,
    })
    db.commit()

    return {"status": "ok", "bundles_accepted": bundles_accepted,
            "items_accepted": items_accepted}
