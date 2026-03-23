"""Tracker writeback committer — orchestrates the commit of reviewed bundles.

Entry point: commit_communication(db, communication_id) -> CommitResult

Flow:
1. Load bundles via _build_bundle_tree
2. Filter: accepted bundles only, accepted/edited items only (skip moved/rejected)
3. For each accepted bundle:
   a. If new_matter: convert proposed_matter_json to matter INSERT (first op)
   b. Order items by dependency
   c. Convert items to batch operations
   d. Call POST /tracker/batch with idempotency key
   e. Record tracker_writebacks for each result
4. Return CommitResult with per-bundle outcomes
"""

import json
import logging
import uuid as uuid_mod
from dataclasses import dataclass, field

from app.bundle_review.retrieval import _build_bundle_tree
from app.bundle_review.audit import write_audit
from app.writeback.ordering import order_items
from app.writeback.item_converters import convert_item, convert_new_matter_bundle
from app.writeback.tracker_client import post_batch, TrackerBatchError

logger = logging.getLogger(__name__)

# Item statuses eligible for commit
COMMITTABLE_ITEM_STATUSES = {"accepted", "edited"}


@dataclass
class BundleCommitResult:
    bundle_id: str
    bundle_type: str
    target_matter_title: str | None
    success: bool
    operations_sent: int = 0
    records_written: int = 0
    error: str | None = None
    error_type: str | None = None


@dataclass
class CommitResult:
    communication_id: str
    bundles_committed: int = 0
    bundles_skipped: int = 0
    bundles_failed: int = 0
    total_records: int = 0
    bundle_results: list = field(default_factory=list)

    @property
    def all_succeeded(self) -> bool:
        return self.bundles_failed == 0


async def commit_communication(db, communication_id: str) -> CommitResult:
    """Commit all accepted bundles for a communication to the tracker.

    This is the top-level entry point called by the orchestrator's
    _handle_committing handler.
    """
    result = CommitResult(communication_id=communication_id)

    write_audit(db, communication_id, None, None, "commit_started", {})
    db.commit()

    # Load the full bundle tree
    bundles = _build_bundle_tree(db, communication_id)

    # Check if already committed (idempotency at the communication level)
    existing_writebacks = db.execute(
        "SELECT COUNT(*) as cnt FROM tracker_writebacks WHERE communication_id = ?",
        (communication_id,)
    ).fetchone()["cnt"]

    for bundle in bundles:
        # Inject communication_id for converters (not on the tree dict by default)
        bundle["_communication_id"] = communication_id

        # Skip rejected bundles
        if bundle["status"] == "rejected":
            result.bundles_skipped += 1
            continue

        # Skip bundles that aren't accepted (shouldn't happen post-review, but defensive)
        if bundle["status"] != "accepted":
            result.bundles_skipped += 1
            logger.warning("[%s] Skipping non-accepted bundle %s (status=%s)",
                           communication_id[:8], bundle["id"][:8], bundle["status"])
            continue

        # Filter to committable items
        committable_items = [
            item for item in bundle.get("items", [])
            if item["status"] in COMMITTABLE_ITEM_STATUSES
        ]

        if not committable_items:
            result.bundles_skipped += 1
            logger.info("[%s] Bundle %s has no committable items — skipping",
                        communication_id[:8], bundle["id"][:8])
            continue

        # Commit this bundle
        br = await _commit_bundle(db, communication_id, bundle, committable_items)
        result.bundle_results.append(br)

        if br.success:
            result.bundles_committed += 1
            result.total_records += br.records_written
        else:
            result.bundles_failed += 1

    # Audit the final result
    write_audit(db, communication_id, None, None,
                "commit_complete" if result.all_succeeded else "commit_partial_failure",
                {
                    "bundles_committed": result.bundles_committed,
                    "bundles_skipped": result.bundles_skipped,
                    "bundles_failed": result.bundles_failed,
                    "total_records": result.total_records,
                })
    db.commit()

    return result


async def _commit_bundle(db, communication_id: str, bundle: dict,
                         items: list[dict]) -> BundleCommitResult:
    """Commit a single bundle's items to the tracker."""
    bundle_id = bundle["id"]
    br = BundleCommitResult(
        bundle_id=bundle_id,
        bundle_type=bundle["bundle_type"],
        target_matter_title=bundle.get("target_matter_title"),
        success=False,
    )

    try:
        # Check if this bundle was already committed (idempotency)
        existing = db.execute(
            "SELECT COUNT(*) as cnt FROM tracker_writebacks WHERE bundle_id = ?",
            (bundle_id,)
        ).fetchone()["cnt"]
        if existing > 0:
            logger.info("[%s] Bundle %s already has %d writebacks — will replay via idempotency",
                        communication_id[:8], bundle_id[:8], existing)

        # Build the forward reference dict
        refs = {}

        # Collect all operations
        all_ops = []  # list of (op_dict, item_id)

        # Step 1: If new_matter bundle, insert the matter first
        if bundle["bundle_type"] == "new_matter":
            matter_ops = convert_new_matter_bundle(bundle, refs)
            all_ops.extend(matter_ops)

        # Step 2: Order items by dependency
        ordered_items = order_items(items)

        # Step 3: Convert each item
        for item in ordered_items:
            item_ops = convert_item(item, bundle, refs)
            all_ops.extend(item_ops)

        if not all_ops:
            br.success = True
            return br

        # Step 4: Build the batch payload
        operations = [op for op, _ in all_ops]
        item_ids = [item_id for _, item_id in all_ops]

        idempotency_key = f"commit_{communication_id}_{bundle_id}"

        source_metadata = {
            "communication_id": communication_id,
            "bundle_id": bundle_id,
            "bundle_type": bundle["bundle_type"],
        }

        br.operations_sent = len(operations)

        # Step 5: Call tracker
        response = await post_batch(
            operations=operations,
            source="ai",
            source_metadata=source_metadata,
            idempotency_key=idempotency_key,
        )

        # Step 6: Record writebacks
        results = response.get("results", [])
        br.records_written = len(results)

        for i, tracker_result in enumerate(results):
            wb_item_id = item_ids[i] if i < len(item_ids) else None
            _record_writeback(
                db, communication_id, bundle_id, wb_item_id,
                tracker_result, operations[i] if i < len(operations) else {},
            )

        write_audit(db, communication_id, bundle_id, None, "bundle_committed", {
            "operations_sent": br.operations_sent,
            "records_written": br.records_written,
            "target_matter": bundle.get("target_matter_title"),
        })
        db.commit()

        br.success = True
        logger.info("[%s] Bundle %s committed: %d ops → %d records",
                    communication_id[:8], bundle_id[:8],
                    br.operations_sent, br.records_written)

    except TrackerBatchError as e:
        br.error = str(e)
        br.error_type = e.error_type
        write_audit(db, communication_id, bundle_id, None, "bundle_commit_failed", {
            "error": str(e),
            "error_type": e.error_type,
            "status_code": e.status_code,
            "operation_index": e.operation_index,
        })
        db.commit()
        logger.error("[%s] Bundle %s commit failed: %s",
                     communication_id[:8], bundle_id[:8], e)

    except Exception as e:
        br.error = str(e)
        br.error_type = "internal_error"
        write_audit(db, communication_id, bundle_id, None, "bundle_commit_failed", {
            "error": str(e),
            "error_type": "internal_error",
        })
        db.commit()
        logger.exception("[%s] Bundle %s commit unexpected error",
                         communication_id[:8], bundle_id[:8])

    return br


def _record_writeback(db, communication_id: str, bundle_id: str,
                      item_id: str | None, tracker_result: dict,
                      operation: dict):
    """Record a single tracker_writebacks row."""
    wb_id = str(uuid_mod.uuid4())
    db.execute("""
        INSERT OR IGNORE INTO tracker_writebacks
            (id, communication_id, bundle_id, bundle_item_id,
             target_table, target_record_id, write_type,
             written_data, previous_data, auto_committed, written_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, datetime('now'))
    """, (
        wb_id,
        communication_id,
        bundle_id,
        item_id,
        tracker_result.get("table", operation.get("table", "")),
        tracker_result.get("record_id", ""),
        tracker_result.get("op", operation.get("op", "")),
        json.dumps(operation.get("data", {}), default=str),
        json.dumps(tracker_result.get("previous_data"), default=str),
    ))
