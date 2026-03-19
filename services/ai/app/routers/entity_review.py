"""Entity review API — human gate for confirming entity mentions.

After enrichment extracts entities (people, orgs, regulations, etc.) from
the transcript, communications enter awaiting_entity_review. This router
provides endpoints to:

1. List communications needing entity review
2. Get entity details for a communication
3. Confirm entities as-is
4. Link entities to Tracker person/org records
5. Edit entity details (name, type, etc.)
6. Reject false-positive entities
7. Merge duplicate entities
8. Complete entity review (advances pipeline)

Entity lifecycle:
  - Extracted (confirmed=0, tracker_*_id=NULL) — raw from Haiku enrichment
  - Confirmed (confirmed=1, tracker_*_id=NULL) — human verified, not linked
  - Linked (confirmed=1, tracker_*_id=<id>) — verified AND linked to Tracker
  - Rejected (confirmed=-1) — false positive, excluded from downstream

Speaker identity (from speaker review) is separate from entity mentions.
Entity review handles people/orgs MENTIONED in conversation, not the
speakers themselves.
"""

import json
import logging
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from pydantic import BaseModel

from app.db import get_db
from app.pipeline.orchestrator import cas_transition
from app.routers.events import publish_event

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/entity-review", tags=["entity-review"])

# States where entity review is accessible
ENTITY_REVIEW_STATES = {"awaiting_entity_review", "entity_review_in_progress"}

# Valid entity types
VALID_ENTITY_TYPES = {
    "person", "organization", "regulation", "legislation", "case", "concept",
}


# ── Request/Response models ──

class ConfirmEntityRequest(BaseModel):
    entity_id: str


class LinkEntityRequest(BaseModel):
    entity_id: str
    tracker_person_id: Optional[str] = None
    tracker_org_id: Optional[str] = None
    proposed_name: Optional[str] = None
    proposed_title: Optional[str] = None
    proposed_org: Optional[str] = None


class EditEntityRequest(BaseModel):
    entity_id: str
    mention_text: Optional[str] = None
    entity_type: Optional[str] = None
    proposed_name: Optional[str] = None
    proposed_title: Optional[str] = None
    proposed_org: Optional[str] = None


class RejectEntityRequest(BaseModel):
    entity_id: str
    reason: Optional[str] = None


class MergeEntitiesRequest(BaseModel):
    from_entity_id: str
    to_entity_id: str


class EntityInfo(BaseModel):
    id: str
    mention_text: str
    entity_type: str
    tracker_person_id: Optional[str] = None
    tracker_org_id: Optional[str] = None
    proposed_name: Optional[str] = None
    proposed_title: Optional[str] = None
    proposed_org: Optional[str] = None
    confidence: Optional[float] = None
    confirmed: int = 0
    mention_count: int = 1
    context_snippet: Optional[str] = None
    first_mention_transcript_id: Optional[str] = None
    first_mention_text: Optional[str] = None
    first_mention_speaker: Optional[str] = None


class EntityReviewDetail(BaseModel):
    communication_id: str
    processing_status: str
    original_filename: Optional[str] = None
    duration_seconds: Optional[float] = None
    summary: Optional[str] = None
    entities: list[EntityInfo]
    entity_counts: dict
    sensitivity_flags: Optional[list] = None


# ── Endpoints ──

@router.get("/queue")
async def get_entity_review_queue(db=Depends(get_db)):
    """List all communications awaiting entity review."""
    rows = db.execute("""
        SELECT c.id, c.original_filename, c.processing_status,
               c.duration_seconds, c.created_at, c.updated_at,
               c.sensitivity_flags,
               (SELECT COUNT(*) FROM communication_entities ce
                WHERE ce.communication_id = c.id) as entity_count,
               (SELECT COUNT(*) FROM communication_entities ce
                WHERE ce.communication_id = c.id AND ce.confirmed = 1) as confirmed_count,
               (SELECT COUNT(*) FROM communication_entities ce
                WHERE ce.communication_id = c.id AND ce.confirmed = -1) as rejected_count
        FROM communications c
        WHERE c.processing_status IN ('awaiting_entity_review', 'entity_review_in_progress')
        ORDER BY c.created_at DESC
    """).fetchall()

    items = []
    for r in rows:
        item = dict(r)
        # Parse sensitivity flags
        if item.get("sensitivity_flags"):
            try:
                item["sensitivity_flags"] = json.loads(item["sensitivity_flags"])
            except (json.JSONDecodeError, TypeError):
                pass
        items.append(item)

    return {
        "items": items,
        "total": len(items),
    }


@router.get("/{communication_id}")
async def get_entity_review_detail(communication_id: str, db=Depends(get_db)):
    """Get detailed entity information for review."""
    comm = db.execute(
        """SELECT id, processing_status, original_filename, duration_seconds,
                  topic_segments_json, sensitivity_flags
           FROM communications WHERE id = ?""",
        (communication_id,),
    ).fetchone()
    if not comm:
        raise HTTPException(404, detail={"error_type": "not_found"})

    # Parse summary from topic_segments_json
    summary = None
    if comm["topic_segments_json"]:
        try:
            topic_data = json.loads(comm["topic_segments_json"])
            summary = topic_data.get("summary")
        except (json.JSONDecodeError, TypeError):
            pass

    # Parse sensitivity flags
    sensitivity_flags = None
    if comm["sensitivity_flags"]:
        try:
            sensitivity_flags = json.loads(comm["sensitivity_flags"])
        except (json.JSONDecodeError, TypeError):
            pass

    # Get entities with transcript context
    entities_raw = db.execute("""
        SELECT ce.id, ce.mention_text, ce.entity_type,
               ce.tracker_person_id, ce.tracker_org_id,
               ce.proposed_name, ce.proposed_title, ce.proposed_org,
               ce.confidence, ce.confirmed, ce.mention_count,
               ce.context_snippet, ce.first_mention_transcript_id
        FROM communication_entities ce
        WHERE ce.communication_id = ?
        ORDER BY ce.mention_count DESC, ce.mention_text
    """, (communication_id,)).fetchall()

    entities = []
    for e in entities_raw:
        info = EntityInfo(**dict(e))

        # Get first mention context from transcript
        if e["first_mention_transcript_id"]:
            seg = db.execute(
                """SELECT raw_text, cleaned_text, speaker_label
                   FROM transcripts WHERE id = ?""",
                (e["first_mention_transcript_id"],),
            ).fetchone()
            if seg:
                info.first_mention_text = (seg["cleaned_text"] or seg["raw_text"] or "")[:200]
                info.first_mention_speaker = seg["speaker_label"]

        entities.append(info)

    # Count by type and status
    entity_counts = {
        "total": len(entities),
        "confirmed": sum(1 for e in entities if e.confirmed == 1),
        "rejected": sum(1 for e in entities if e.confirmed == -1),
        "pending": sum(1 for e in entities if e.confirmed == 0),
        "linked": sum(1 for e in entities if e.tracker_person_id or e.tracker_org_id),
    }
    # Count by entity_type
    for etype in VALID_ENTITY_TYPES:
        entity_counts[f"type_{etype}"] = sum(1 for e in entities if e.entity_type == etype)

    return EntityReviewDetail(
        communication_id=communication_id,
        processing_status=comm["processing_status"],
        original_filename=comm["original_filename"],
        duration_seconds=comm["duration_seconds"],
        summary=summary,
        entities=entities,
        entity_counts=entity_counts,
        sensitivity_flags=sensitivity_flags,
    )


@router.post("/{communication_id}/confirm-entity")
async def confirm_entity(
    communication_id: str,
    req: ConfirmEntityRequest,
    db=Depends(get_db),
):
    """Confirm an entity mention as accurate (without Tracker linking)."""
    _check_review_state(db, communication_id)
    _ensure_in_progress(db, communication_id)

    entity = _get_entity(db, communication_id, req.entity_id)

    db.execute(
        "UPDATE communication_entities SET confirmed = 1, updated_at = datetime('now') WHERE id = ?",
        (req.entity_id,),
    )

    _audit(db, communication_id, "confirm_entity", {
        "entity_id": req.entity_id,
        "mention_text": entity["mention_text"],
        "entity_type": entity["entity_type"],
    })
    db.commit()

    logger.info("[%s] Confirmed entity: %s (%s)", communication_id[:8], entity["mention_text"], entity["entity_type"])
    return {"status": "ok", "entity_id": req.entity_id, "confirmed": True}


@router.post("/{communication_id}/link-entity")
async def link_entity(
    communication_id: str,
    req: LinkEntityRequest,
    db=Depends(get_db),
):
    """Link an entity to a Tracker person or organization record.

    Sets confirmed=1 and the appropriate tracker ID. For person entities,
    use tracker_person_id. For organization entities, use tracker_org_id.
    Both can be set if the entity refers to a person at an organization.
    """
    _check_review_state(db, communication_id)
    _ensure_in_progress(db, communication_id)

    if not req.tracker_person_id and not req.tracker_org_id:
        raise HTTPException(400, detail={
            "error_type": "validation_failure",
            "message": "At least one of tracker_person_id or tracker_org_id is required",
        })

    entity = _get_entity(db, communication_id, req.entity_id)

    db.execute("""
        UPDATE communication_entities
        SET confirmed = 1,
            tracker_person_id = COALESCE(?, tracker_person_id),
            tracker_org_id = COALESCE(?, tracker_org_id),
            proposed_name = COALESCE(?, proposed_name),
            proposed_title = COALESCE(?, proposed_title),
            proposed_org = COALESCE(?, proposed_org),
            updated_at = datetime('now')
        WHERE id = ?
    """, (
        req.tracker_person_id, req.tracker_org_id,
        req.proposed_name, req.proposed_title, req.proposed_org,
        req.entity_id,
    ))

    _audit(db, communication_id, "link_entity", {
        "entity_id": req.entity_id,
        "mention_text": entity["mention_text"],
        "tracker_person_id": req.tracker_person_id,
        "tracker_org_id": req.tracker_org_id,
    })
    db.commit()

    logger.info(
        "[%s] Linked entity %s -> person=%s org=%s",
        communication_id[:8], entity["mention_text"],
        (req.tracker_person_id or "")[:8], (req.tracker_org_id or "")[:8],
    )
    return {"status": "ok", "entity_id": req.entity_id, "linked": True}


@router.post("/{communication_id}/edit-entity")
async def edit_entity(
    communication_id: str,
    req: EditEntityRequest,
    db=Depends(get_db),
):
    """Edit an entity's details (mention text, type, proposed fields)."""
    _check_review_state(db, communication_id)
    _ensure_in_progress(db, communication_id)

    entity = _get_entity(db, communication_id, req.entity_id)

    if req.entity_type and req.entity_type not in VALID_ENTITY_TYPES:
        raise HTTPException(400, detail={
            "error_type": "validation_failure",
            "message": f"Invalid entity_type: {req.entity_type}. Valid: {sorted(VALID_ENTITY_TYPES)}",
        })

    # Build update dynamically for non-None fields
    updates = []
    params = []
    old_values = {}

    if req.mention_text is not None:
        updates.append("mention_text = ?")
        params.append(req.mention_text)
        old_values["mention_text"] = entity["mention_text"]
    if req.entity_type is not None:
        updates.append("entity_type = ?")
        params.append(req.entity_type)
        old_values["entity_type"] = entity["entity_type"]
    if req.proposed_name is not None:
        updates.append("proposed_name = ?")
        params.append(req.proposed_name)
        old_values["proposed_name"] = entity["proposed_name"]
    if req.proposed_title is not None:
        updates.append("proposed_title = ?")
        params.append(req.proposed_title)
    if req.proposed_org is not None:
        updates.append("proposed_org = ?")
        params.append(req.proposed_org)

    if not updates:
        raise HTTPException(400, detail={
            "error_type": "validation_failure",
            "message": "No fields to update",
        })

    updates.append("updated_at = datetime('now')")
    params.append(req.entity_id)

    db.execute(
        f"UPDATE communication_entities SET {', '.join(updates)} WHERE id = ?",
        params,
    )

    _audit(db, communication_id, "edit_entity", {
        "entity_id": req.entity_id,
        "old_values": old_values,
        "new_values": {k: v for k, v in req.model_dump().items() if v is not None and k != "entity_id"},
    })
    db.commit()

    logger.info("[%s] Edited entity %s", communication_id[:8], entity["mention_text"])
    return {"status": "ok", "entity_id": req.entity_id, "edited": True}


@router.post("/{communication_id}/reject-entity")
async def reject_entity(
    communication_id: str,
    req: RejectEntityRequest,
    db=Depends(get_db),
):
    """Reject a false-positive entity (marks confirmed=-1)."""
    _check_review_state(db, communication_id)
    _ensure_in_progress(db, communication_id)

    entity = _get_entity(db, communication_id, req.entity_id)

    db.execute(
        "UPDATE communication_entities SET confirmed = -1, updated_at = datetime('now') WHERE id = ?",
        (req.entity_id,),
    )

    _audit(db, communication_id, "reject_entity", {
        "entity_id": req.entity_id,
        "mention_text": entity["mention_text"],
        "entity_type": entity["entity_type"],
        "reason": req.reason,
    })
    db.commit()

    logger.info("[%s] Rejected entity: %s (%s)", communication_id[:8], entity["mention_text"], req.reason or "no reason")
    return {"status": "ok", "entity_id": req.entity_id, "rejected": True}


@router.post("/{communication_id}/merge-entities")
async def merge_entities(
    communication_id: str,
    req: MergeEntitiesRequest,
    db=Depends(get_db),
):
    """Merge two entity mentions (absorb from_entity into to_entity).

    Adds mention counts, preserves the to_entity's type/name/links,
    and removes the from_entity.
    """
    _check_review_state(db, communication_id)
    _ensure_in_progress(db, communication_id)

    from_entity = _get_entity(db, communication_id, req.from_entity_id)
    to_entity = _get_entity(db, communication_id, req.to_entity_id)

    # Add mention counts
    new_count = (to_entity["mention_count"] or 1) + (from_entity["mention_count"] or 1)
    db.execute(
        "UPDATE communication_entities SET mention_count = ?, updated_at = datetime('now') WHERE id = ?",
        (new_count, req.to_entity_id),
    )

    # Transfer tracker links from from_entity if to_entity doesn't have them
    if from_entity["tracker_person_id"] and not to_entity["tracker_person_id"]:
        db.execute(
            "UPDATE communication_entities SET tracker_person_id = ? WHERE id = ?",
            (from_entity["tracker_person_id"], req.to_entity_id),
        )
    if from_entity["tracker_org_id"] and not to_entity["tracker_org_id"]:
        db.execute(
            "UPDATE communication_entities SET tracker_org_id = ? WHERE id = ?",
            (from_entity["tracker_org_id"], req.to_entity_id),
        )

    # Remove the merged-away entity
    db.execute(
        "DELETE FROM communication_entities WHERE id = ?",
        (req.from_entity_id,),
    )

    _audit(db, communication_id, "merge_entities", {
        "from_entity_id": req.from_entity_id,
        "from_mention": from_entity["mention_text"],
        "to_entity_id": req.to_entity_id,
        "to_mention": to_entity["mention_text"],
        "new_count": new_count,
    })
    db.commit()

    logger.info(
        "[%s] Merged entity '%s' into '%s'",
        communication_id[:8], from_entity["mention_text"], to_entity["mention_text"],
    )
    return {"status": "ok", "merged_count": new_count}


@router.post("/{communication_id}/confirm-all")
async def confirm_all_entities(
    communication_id: str,
    db=Depends(get_db),
):
    """Confirm all pending (unreviewed) entities at once.

    Convenience endpoint for when the enrichment results look accurate.
    Does not touch already-rejected entities.
    """
    _check_review_state(db, communication_id)
    _ensure_in_progress(db, communication_id)

    count = db.execute("""
        UPDATE communication_entities
        SET confirmed = 1, updated_at = datetime('now')
        WHERE communication_id = ? AND confirmed = 0
    """, (communication_id,)).rowcount

    _audit(db, communication_id, "confirm_all_entities", {"count": count})
    db.commit()

    logger.info("[%s] Bulk confirmed %d entities", communication_id[:8], count)
    return {"status": "ok", "confirmed_count": count}


@router.post("/{communication_id}/complete")
async def complete_entity_review(
    communication_id: str,
    background_tasks: BackgroundTasks,
    db=Depends(get_db),
):
    """Complete entity review and advance the pipeline.

    All entities must be either confirmed (1) or rejected (-1).
    No pending (0) entities may remain.
    Transitions: entity_review_in_progress -> entities_confirmed.
    """
    comm = db.execute(
        "SELECT processing_status FROM communications WHERE id = ?",
        (communication_id,),
    ).fetchone()
    if not comm:
        raise HTTPException(404, detail={"error_type": "not_found"})

    status = comm["processing_status"]
    if status not in ENTITY_REVIEW_STATES:
        raise HTTPException(400, detail={
            "error_type": "invalid_state",
            "message": f"Communication not in entity review state (current: {status})",
        })

    # Check no pending entities remain
    pending = db.execute("""
        SELECT mention_text, entity_type FROM communication_entities
        WHERE communication_id = ? AND confirmed = 0
    """, (communication_id,)).fetchall()

    if pending:
        pending_list = [{"mention_text": r["mention_text"], "entity_type": r["entity_type"]} for r in pending]
        raise HTTPException(400, detail={
            "error_type": "validation_failure",
            "message": f"{len(pending)} unreviewed entities remain",
            "pending_entities": pending_list,
        })

    # Ensure we're in entity_review_in_progress
    if status == "awaiting_entity_review":
        cas_transition(db, communication_id, "awaiting_entity_review", "entity_review_in_progress")

    # Advance to entities_confirmed
    if not cas_transition(db, communication_id, "entity_review_in_progress", "entities_confirmed"):
        raise HTTPException(409, detail={
            "error_type": "conflict",
            "message": "Status already changed by another process",
        })

    # Count final state
    confirmed = db.execute(
        "SELECT COUNT(*) as cnt FROM communication_entities WHERE communication_id = ? AND confirmed = 1",
        (communication_id,),
    ).fetchone()["cnt"]
    rejected = db.execute(
        "SELECT COUNT(*) as cnt FROM communication_entities WHERE communication_id = ? AND confirmed = -1",
        (communication_id,),
    ).fetchone()["cnt"]
    linked = db.execute(
        """SELECT COUNT(*) as cnt FROM communication_entities
           WHERE communication_id = ? AND confirmed = 1
           AND (tracker_person_id IS NOT NULL OR tracker_org_id IS NOT NULL)""",
        (communication_id,),
    ).fetchone()["cnt"]

    _audit(db, communication_id, "complete_entity_review", {
        "confirmed": confirmed,
        "rejected": rejected,
        "linked": linked,
    })
    db.commit()

    await publish_event("entity_review_complete", {
        "communication_id": communication_id,
        "status": "entities_confirmed",
        "confirmed": confirmed,
        "rejected": rejected,
        "linked": linked,
    })

    # Resume pipeline in background
    background_tasks.add_task(_resume_pipeline, communication_id)

    logger.info(
        "[%s] Entity review completed: %d confirmed, %d rejected, %d linked",
        communication_id[:8], confirmed, rejected, linked,
    )

    return {
        "status": "entities_confirmed",
        "communication_id": communication_id,
        "confirmed": confirmed,
        "rejected": rejected,
        "linked": linked,
    }


# ── Helpers ──

def _check_review_state(db, communication_id: str):
    """Verify communication is in an entity review state."""
    row = db.execute(
        "SELECT processing_status FROM communications WHERE id = ?",
        (communication_id,),
    ).fetchone()
    if not row:
        raise HTTPException(404, detail={"error_type": "not_found"})
    if row["processing_status"] not in ENTITY_REVIEW_STATES:
        raise HTTPException(400, detail={
            "error_type": "invalid_state",
            "message": f"Communication not in entity review (current: {row['processing_status']})",
        })


def _ensure_in_progress(db, communication_id: str):
    """Move from awaiting_entity_review to entity_review_in_progress if needed."""
    cas_transition(db, communication_id, "awaiting_entity_review", "entity_review_in_progress")


def _get_entity(db, communication_id: str, entity_id: str) -> dict:
    """Fetch an entity, raising 404 if not found or wrong communication."""
    entity = db.execute(
        "SELECT * FROM communication_entities WHERE id = ? AND communication_id = ?",
        (entity_id, communication_id),
    ).fetchone()
    if not entity:
        raise HTTPException(404, detail={
            "error_type": "not_found",
            "message": f"Entity {entity_id} not found in communication {communication_id[:8]}",
        })
    return dict(entity)


def _audit(db, communication_id: str, action_type: str, details: dict):
    """Write to review_action_log."""
    db.execute("""
        INSERT INTO review_action_log (id, actor, communication_id, action_type, details)
        VALUES (?, 'user', ?, ?, ?)
    """, (str(uuid.uuid4()), communication_id, action_type, json.dumps(details)))


async def _resume_pipeline(communication_id: str):
    """Resume pipeline after human gate."""
    from app.pipeline.orchestrator import process_communication
    try:
        await process_communication(communication_id)
    except Exception as e:
        logger.exception("Pipeline resume failed for %s: %s", communication_id, e)
