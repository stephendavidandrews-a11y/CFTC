"""State guards and DB lookup helpers for bundle review.

All functions take a raw sqlite3 connection — no FastAPI dependencies.
Raise HTTPException for consistency with the router layer. Phase 5 can
catch these or call the underlying queries directly.
"""

from fastapi import HTTPException

from app.bundle_review.models import BUNDLE_REVIEW_STATES
from app.pipeline.orchestrator import cas_transition


def check_review_state(db, communication_id: str):
    """Verify communication is in a bundle review state."""
    row = db.execute(
        "SELECT processing_status FROM communications WHERE id = ?",
        (communication_id,),
    ).fetchone()
    if not row:
        raise HTTPException(404, detail={"error_type": "not_found"})
    if row["processing_status"] not in BUNDLE_REVIEW_STATES:
        raise HTTPException(400, detail={
            "error_type": "invalid_state",
            "message": f"Communication not in bundle review (current: {row['processing_status']})",
        })


def ensure_in_progress(db, communication_id: str):
    """Auto-transition from awaiting_bundle_review to bundle_review_in_progress."""
    cas_transition(db, communication_id, "awaiting_bundle_review", "bundle_review_in_progress")


def get_bundle(db, communication_id: str, bundle_id: str) -> dict:
    """Fetch a bundle, raising 404 if not found or wrong communication."""
    bundle = db.execute(
        "SELECT * FROM review_bundles WHERE id = ? AND communication_id = ?",
        (bundle_id, communication_id),
    ).fetchone()
    if not bundle:
        raise HTTPException(404, detail={
            "error_type": "not_found",
            "message": f"Bundle {bundle_id[:8]} not found in communication {communication_id[:8]}",
        })
    return dict(bundle)


def get_item(db, bundle_id: str, item_id: str) -> dict:
    """Fetch an item, raising 404 if not found or wrong bundle."""
    item = db.execute(
        "SELECT * FROM review_bundle_items WHERE id = ? AND bundle_id = ?",
        (item_id, bundle_id),
    ).fetchone()
    if not item:
        raise HTTPException(404, detail={
            "error_type": "not_found",
            "message": f"Item {item_id[:8]} not found in bundle {bundle_id[:8]}",
        })
    return dict(item)
