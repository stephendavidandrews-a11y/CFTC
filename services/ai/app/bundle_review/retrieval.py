"""Bundle review retrieval — queue listing and full detail with suppression visibility.

These are read-only query functions. The detail function builds the full
nested structure with bundles -> items, extraction metadata, suppression
categories, and readiness assessment.
"""

import json

from fastapi import HTTPException

from app.bundle_review.validation import compute_blockers


def get_queue(db) -> dict:
    """List all communications awaiting bundle review with summary counts."""
    rows = db.execute("""
        SELECT c.id, c.title, c.original_filename, c.processing_status,
               c.duration_seconds, c.created_at, c.updated_at,
               c.sensitivity_flags,
               (SELECT COUNT(*) FROM review_bundles rb
                WHERE rb.communication_id = c.id) as bundle_count,
               (SELECT COUNT(*) FROM review_bundles rb
                WHERE rb.communication_id = c.id AND rb.status = 'proposed') as bundles_proposed,
               (SELECT COUNT(*) FROM review_bundles rb
                WHERE rb.communication_id = c.id AND rb.status = 'accepted') as bundles_accepted,
               (SELECT COUNT(*) FROM review_bundles rb
                WHERE rb.communication_id = c.id AND rb.status = 'rejected') as bundles_rejected,
               (SELECT COUNT(*) FROM review_bundle_items ri
                JOIN review_bundles rb ON ri.bundle_id = rb.id
                WHERE rb.communication_id = c.id) as item_count,
               (SELECT COUNT(*) FROM review_bundle_items ri
                JOIN review_bundles rb ON ri.bundle_id = rb.id
                WHERE rb.communication_id = c.id AND ri.status = 'proposed') as items_proposed
        FROM communications c
        WHERE c.processing_status IN ('awaiting_bundle_review', 'bundle_review_in_progress')
        ORDER BY c.created_at DESC
    """).fetchall()

    items = []
    for r in rows:
        item = dict(r)
        if item.get("sensitivity_flags"):
            try:
                item["sensitivity_flags"] = json.loads(item["sensitivity_flags"])
            except (json.JSONDecodeError, TypeError):
                pass
        items.append(item)

    return {"items": items, "total": len(items)}


def get_detail(db, communication_id: str) -> dict:
    """Full bundle review detail for a communication.

    Returns bundles with nested items, extraction metadata, suppression
    visibility, provenance, and readiness-to-complete assessment.
    """
    comm = db.execute("""
        SELECT id, processing_status, title, original_filename, duration_seconds,
               topic_segments_json, sensitivity_flags, created_at
        FROM communications WHERE id = ?
    """, (communication_id,)).fetchone()
    if not comm:
        raise HTTPException(404, detail={"error_type": "not_found"})

    # Parse enrichment summary
    summary = None
    topics = []
    if comm["topic_segments_json"]:
        try:
            td = json.loads(comm["topic_segments_json"])
            summary = td.get("summary")
            topics = td.get("topics", [])
        except (json.JSONDecodeError, TypeError):
            pass

    sensitivity_flags = None
    if comm["sensitivity_flags"]:
        try:
            sensitivity_flags = json.loads(comm["sensitivity_flags"])
        except (json.JSONDecodeError, TypeError):
            pass

    # Get extraction metadata
    extraction = db.execute("""
        SELECT id, model_used, prompt_version, raw_output, input_tokens,
               output_tokens, processing_seconds, extracted_at
        FROM ai_extractions
        WHERE communication_id = ?
        ORDER BY extracted_at DESC LIMIT 1
    """, (communication_id,)).fetchone()

    extraction_meta = None
    suppressed_observations = []
    code_suppressions = []
    dedup_warnings = []
    invalid_refs = []
    extraction_summary_text = None

    if extraction:
        extraction_meta = {
            "extraction_id": extraction["id"],
            "model_used": extraction["model_used"],
            "prompt_version": extraction["prompt_version"],
            "input_tokens": extraction["input_tokens"],
            "output_tokens": extraction["output_tokens"],
            "processing_seconds": extraction["processing_seconds"],
            "extracted_at": extraction["extracted_at"],
        }
        if extraction["raw_output"]:
            try:
                raw = json.loads(extraction["raw_output"])
                suppressed_observations = raw.get("suppressed_observations", [])
                extraction_summary_text = raw.get("extraction_summary")
                pp = raw.get("_post_processing", {})
                code_suppressions = pp.get("code_suppressed_items", [])
                dedup_warnings = pp.get("dedup_warnings", [])
                invalid_refs = pp.get("invalid_references_cleaned", [])
            except (json.JSONDecodeError, TypeError):
                pass

    # Get bundles with nested items
    bundles = _build_bundle_tree(db, communication_id)

    # Aggregate counts
    total_items_by_status = {}
    total_items_by_type = {}
    for b in bundles:
        for item in b.get("items", []):
            total_items_by_status[item["status"]] = total_items_by_status.get(item["status"], 0) + 1
            total_items_by_type[item["item_type"]] = total_items_by_type.get(item["item_type"], 0) + 1

    bundle_counts = {
        "total": len(bundles),
        "proposed": sum(1 for b in bundles if b["status"] == "proposed"),
        "accepted": sum(1 for b in bundles if b["status"] == "accepted"),
        "rejected": sum(1 for b in bundles if b["status"] == "rejected"),
    }

    blockers = compute_blockers(bundles)

    return {
        "communication_id": communication_id,
        "processing_status": comm["processing_status"],
        "title": comm["title"],
        "original_filename": comm["original_filename"],
        "duration_seconds": comm["duration_seconds"],
        "created_at": comm["created_at"],
        "summary": summary,
        "topics": topics,
        "sensitivity_flags": sensitivity_flags,
        "extraction_meta": extraction_meta,
        "extraction_summary": extraction_summary_text,
        "bundles": bundles,
        "bundle_counts": bundle_counts,
        "item_counts_by_status": total_items_by_status,
        "item_counts_by_type": total_items_by_type,
        "suppressed_observations": suppressed_observations,
        "code_suppressions": code_suppressions,
        "dedup_warnings": dedup_warnings,
        "invalid_refs_cleaned": invalid_refs,
        "ready_to_complete": len(blockers) == 0,
        "completion_blockers": blockers,
    }


def _build_bundle_tree(db, communication_id: str) -> list[dict]:
    """Build the full bundle -> items tree for a communication.

    This function is reusable: Phase 5 writeback can call it to
    read accepted/edited items for tracker commit formatting.
    """
    bundle_rows = db.execute("""
        SELECT id, bundle_type, target_matter_id, target_matter_title,
               proposed_matter_json, status, confidence, rationale,
               intelligence_notes, sort_order, reviewed_by, reviewed_at,
               created_at, updated_at
        FROM review_bundles
        WHERE communication_id = ?
        ORDER BY sort_order, created_at
    """, (communication_id,)).fetchall()

    bundles = []
    for br in bundle_rows:
        bundle = dict(br)
        # Parse proposed_matter_json
        if bundle["proposed_matter_json"]:
            try:
                bundle["proposed_matter"] = json.loads(bundle["proposed_matter_json"])
            except (json.JSONDecodeError, TypeError):
                bundle["proposed_matter"] = None
        else:
            bundle["proposed_matter"] = None
        del bundle["proposed_matter_json"]

        # Detect reviewer-created bundles
        bundle["reviewer_created"] = bool(
            (bundle.get("rationale") or "").startswith("Reviewer-created")
        )

        # Get items for this bundle
        item_rows = db.execute("""
            SELECT id, item_type, status, proposed_data, original_proposed_data,
                   confidence, rationale, source_excerpt,
                   source_transcript_id, source_start_time, source_end_time,
                   source_locator_json, sort_order, moved_from_bundle_id,
                   reviewed_at, created_at, updated_at
            FROM review_bundle_items
            WHERE bundle_id = ?
            ORDER BY sort_order, created_at
        """, (br["id"],)).fetchall()

        items = []
        for ir in item_rows:
            item = dict(ir)
            for jf in ("proposed_data", "original_proposed_data", "source_locator_json"):
                if item[jf]:
                    try:
                        item[jf] = json.loads(item[jf])
                    except (json.JSONDecodeError, TypeError):
                        pass

            # Detect reviewer-created items
            item["reviewer_created"] = (
                item.get("confidence") is None
                and item.get("source_excerpt") is None
            )

            # Warnings
            item["warnings"] = []
            if item.get("rationale") and "[DEDUP WARNING" in item["rationale"]:
                item["warnings"].append("dedup_warning")
            if item.get("rationale") and "[Note: some references were cleaned" in item["rationale"]:
                item["warnings"].append("references_cleaned")

            items.append(item)

        bundle["items"] = items
        bundle["item_counts"] = {
            "total": len(items),
            "proposed": sum(1 for i in items if i["status"] == "proposed"),
            "accepted": sum(1 for i in items if i["status"] == "accepted"),
            "rejected": sum(1 for i in items if i["status"] == "rejected"),
            "edited": sum(1 for i in items if i["status"] == "edited"),
            "moved": sum(1 for i in items if i["status"] == "moved"),
        }
        bundles.append(bundle)

    return bundles
