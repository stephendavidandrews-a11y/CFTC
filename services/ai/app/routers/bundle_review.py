"""Bundle review router — thin delegation layer for the human review gate.

Route definitions only. All business logic lives in app.bundle_review.*:
    retrieval       — queue + detail
    item_actions    — accept/reject/edit/restore/add items
    bundle_actions  — accept/reject/edit bundles, accept-all
    restructure     — move item, create bundle, merge bundles
    completion      — complete review + pipeline resume
    guards          — state checks, DB lookups
    validation      — proposed_data checks, blockers
    audit           — review_action_log writer
    models          — Pydantic request models, status constants
"""

from fastapi import APIRouter, Depends, BackgroundTasks

from app.db import get_db
from app.routers.events import publish_event

from app.bundle_review.models import (
    AcceptBundleRequest,
    RejectBundleRequest,
    EditBundleRequest,
    AcceptItemRequest,
    RejectItemRequest,
    EditItemRequest,
    RestoreItemRequest,
    AddItemRequest,
    MoveItemRequest,
    CreateBundleRequest,
    MergeBundlesRequest,
)
from app.bundle_review.guards import (
    check_review_state,
    ensure_in_progress,
    get_bundle,
    get_item,
)
from app.bundle_review import (
    retrieval,
    item_actions,
    bundle_actions,
    restructure,
    completion,
)

router = APIRouter(prefix="/bundle-review", tags=["bundle-review"])


# ═══════════════════════════════════════════════════════════════════════════
# 1. Queue + Detail
# ═══════════════════════════════════════════════════════════════════════════


@router.get("/queue")
async def get_bundle_review_queue(db=Depends(get_db)):
    """List all communications awaiting bundle review."""
    return retrieval.get_queue(db)


@router.get("/{communication_id}")
async def get_bundle_review_detail(communication_id: str, db=Depends(get_db)):
    """Full bundle review detail with suppression visibility and readiness assessment."""
    return retrieval.get_detail(db, communication_id)


# ═══════════════════════════════════════════════════════════════════════════
# 2. Item-level actions
# ═══════════════════════════════════════════════════════════════════════════


@router.post("/{communication_id}/accept-item")
async def accept_item_endpoint(
    communication_id: str, req: AcceptItemRequest, db=Depends(get_db)
):
    """Accept a single item within a bundle."""
    check_review_state(db, communication_id)
    ensure_in_progress(db, communication_id)
    get_bundle(db, communication_id, req.bundle_id)
    item = get_item(db, req.bundle_id, req.item_id)
    return item_actions.accept_item(
        db, communication_id, req.bundle_id, req.item_id, item
    )


@router.post("/{communication_id}/reject-item")
async def reject_item_endpoint(
    communication_id: str, req: RejectItemRequest, db=Depends(get_db)
):
    """Reject a single item within a bundle."""
    check_review_state(db, communication_id)
    ensure_in_progress(db, communication_id)
    get_bundle(db, communication_id, req.bundle_id)
    item = get_item(db, req.bundle_id, req.item_id)
    return item_actions.reject_item(
        db, communication_id, req.bundle_id, req.item_id, item, req.reason
    )


@router.post("/{communication_id}/edit-item")
async def edit_item_endpoint(
    communication_id: str, req: EditItemRequest, db=Depends(get_db)
):
    """Edit an item's proposed_data. Preserves original on first edit."""
    check_review_state(db, communication_id)
    ensure_in_progress(db, communication_id)
    get_bundle(db, communication_id, req.bundle_id)
    item = get_item(db, req.bundle_id, req.item_id)
    return item_actions.edit_item(
        db, communication_id, req.bundle_id, req.item_id, item, req.proposed_data
    )


@router.post("/{communication_id}/restore-item")
async def restore_item_endpoint(
    communication_id: str, req: RestoreItemRequest, db=Depends(get_db)
):
    """Restore an edited item to its original proposed_data."""
    check_review_state(db, communication_id)
    ensure_in_progress(db, communication_id)
    get_bundle(db, communication_id, req.bundle_id)
    item = get_item(db, req.bundle_id, req.item_id)
    return item_actions.restore_item(
        db, communication_id, req.bundle_id, req.item_id, item
    )


@router.post("/{communication_id}/add-item")
async def add_item_endpoint(
    communication_id: str, req: AddItemRequest, db=Depends(get_db)
):
    """Add a reviewer-created item to an existing bundle."""
    check_review_state(db, communication_id)
    ensure_in_progress(db, communication_id)
    get_bundle(db, communication_id, req.bundle_id)
    return item_actions.add_item(
        db,
        communication_id,
        req.bundle_id,
        req.item_type,
        req.proposed_data,
        req.rationale,
        req.source_excerpt,
        req.source_start_time,
        req.source_end_time,
    )


# ═══════════════════════════════════════════════════════════════════════════
# 3. Bundle-level actions
# ═══════════════════════════════════════════════════════════════════════════


@router.post("/{communication_id}/accept-bundle")
async def accept_bundle_endpoint(
    communication_id: str, req: AcceptBundleRequest, db=Depends(get_db)
):
    """Accept an entire bundle. Auto-accepts all proposed items."""
    check_review_state(db, communication_id)
    ensure_in_progress(db, communication_id)
    bundle = get_bundle(db, communication_id, req.bundle_id)
    return bundle_actions.accept_bundle(db, communication_id, req.bundle_id, bundle)


@router.post("/{communication_id}/reject-bundle")
async def reject_bundle_endpoint(
    communication_id: str, req: RejectBundleRequest, db=Depends(get_db)
):
    """Reject an entire bundle. Auto-rejects all non-moved items."""
    check_review_state(db, communication_id)
    ensure_in_progress(db, communication_id)
    bundle = get_bundle(db, communication_id, req.bundle_id)
    return bundle_actions.reject_bundle(
        db, communication_id, req.bundle_id, bundle, req.reason
    )


@router.post("/{communication_id}/edit-bundle")
async def edit_bundle_endpoint(
    communication_id: str, req: EditBundleRequest, db=Depends(get_db)
):
    """Edit bundle metadata: target matter, type, notes, rationale."""
    check_review_state(db, communication_id)
    ensure_in_progress(db, communication_id)
    bundle = get_bundle(db, communication_id, req.bundle_id)
    return bundle_actions.edit_bundle(
        db,
        communication_id,
        req.bundle_id,
        bundle,
        req.target_matter_id,
        req.target_matter_title,
        req.bundle_type,
        req.intelligence_notes,
        req.rationale,
    )


@router.post("/{communication_id}/accept-all")
async def accept_all_endpoint(communication_id: str, db=Depends(get_db)):
    """Bulk-accept all proposed bundles and their proposed items."""
    check_review_state(db, communication_id)
    ensure_in_progress(db, communication_id)
    return bundle_actions.accept_all(db, communication_id)


# ═══════════════════════════════════════════════════════════════════════════
# 4. Restructuring
# ═══════════════════════════════════════════════════════════════════════════


@router.post("/{communication_id}/move-item")
async def move_item_endpoint(
    communication_id: str, req: MoveItemRequest, db=Depends(get_db)
):
    """Move an item from one bundle to another. Preserves provenance."""
    check_review_state(db, communication_id)
    ensure_in_progress(db, communication_id)
    get_bundle(db, communication_id, req.from_bundle_id)
    get_bundle(db, communication_id, req.to_bundle_id)
    item = get_item(db, req.from_bundle_id, req.item_id)
    return restructure.move_item(
        db,
        communication_id,
        req.item_id,
        req.from_bundle_id,
        req.to_bundle_id,
        item,
    )


@router.post("/{communication_id}/create-bundle")
async def create_bundle_endpoint(
    communication_id: str, req: CreateBundleRequest, db=Depends(get_db)
):
    """Create a new empty reviewer-created bundle."""
    check_review_state(db, communication_id)
    ensure_in_progress(db, communication_id)
    return restructure.create_bundle(
        db,
        communication_id,
        req.bundle_type,
        req.target_matter_id,
        req.target_matter_title,
        req.rationale,
        req.intelligence_notes,
    )


@router.post("/{communication_id}/merge-bundles")
async def merge_bundles_endpoint(
    communication_id: str, req: MergeBundlesRequest, db=Depends(get_db)
):
    """Merge source bundle into target. Moves all items, rejects source."""
    check_review_state(db, communication_id)
    ensure_in_progress(db, communication_id)
    source = get_bundle(db, communication_id, req.source_bundle_id)
    target = get_bundle(db, communication_id, req.target_bundle_id)
    return restructure.merge_bundles(
        db,
        communication_id,
        req.source_bundle_id,
        req.target_bundle_id,
        source,
        target,
    )


# ═══════════════════════════════════════════════════════════════════════════
# 5. Completion
# ═══════════════════════════════════════════════════════════════════════════


@router.post("/{communication_id}/complete")
async def complete_bundle_review_endpoint(
    communication_id: str,
    background_tasks: BackgroundTasks,
    db=Depends(get_db),
):
    """Complete bundle review. Validates all items terminal, advances to reviewed."""
    result = completion.complete_review(db, communication_id)

    await publish_event(
        "bundle_review_complete",
        {
            "communication_id": communication_id,
            "status": "reviewed",
            "accepted_bundles": result["accepted_bundles"],
            "rejected_bundles": result["rejected_bundles"],
            "items_accepted": result["items_accepted"],
            "items_edited": result["items_edited"],
            "zero_accepted_items": result["zero_accepted_items"],
        },
    )

    # Resume pipeline in background
    background_tasks.add_task(completion.resume_pipeline, communication_id)

    return result
