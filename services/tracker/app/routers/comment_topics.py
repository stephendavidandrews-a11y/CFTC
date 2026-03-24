"""Comment Topics and Comment Questions CRUD endpoints.

Topics are scoped to a matter. Questions are children of topics.
"""
import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from app.db import get_db
from app.validators import (
    CreateCommentTopic, UpdateCommentTopic,
    CreateCommentQuestion, UpdateCommentQuestion, MoveCommentQuestion,
)
from app.deps import get_write_source
from app.audit import log_event
from app.concurrency import get_etag, check_etag
from app.idempotency import claim_idempotency_key, finalize_idempotency_key
import json

router = APIRouter(tags=["comment_topics"])


# ---------------------------------------------------------------------------
# Topics
# ---------------------------------------------------------------------------

@router.get("/matters/{matter_id}/comment-topics")
async def list_comment_topics(
    matter_id: str,
    db=Depends(get_db),
    position_status: str = Query(None),
    topic_area: str = Query(None),
    assigned_to_person_id: str = Query(None),
    sort_by: str = Query("sort_order"),
    sort_dir: str = Query("asc"),
):
    """List topics for a matter with nested questions."""
    # Verify matter exists
    matter = db.execute("SELECT id FROM matters WHERE id = ?", (matter_id,)).fetchone()
    if not matter:
        raise HTTPException(status_code=404, detail="Matter not found")

    conditions = ["ct.matter_id = ?"]
    params = [matter_id]
    if position_status:
        conditions.append("ct.position_status = ?")
        params.append(position_status)
    if topic_area:
        conditions.append("ct.topic_area = ?")
        params.append(topic_area)
    if assigned_to_person_id:
        conditions.append("ct.assigned_to_person_id = ?")
        params.append(assigned_to_person_id)
    where = "WHERE " + " AND ".join(conditions)

    allowed_sort = {
        "sort_order": "ct.sort_order",
        "topic_label": "ct.topic_label",
        "position_status": "ct.position_status",
        "due_date": "ct.due_date",
        "priority": "ct.priority",
        "created_at": "ct.created_at",
    }
    order_col = allowed_sort.get(sort_by, "ct.sort_order")
    direction = "DESC" if sort_dir.lower() == "desc" else "ASC"

    rows = db.execute(f"""
        SELECT ct.*,
               p.full_name as assigned_to_name,
               p2.full_name as secondary_assignee_name
        FROM comment_topics ct
        LEFT JOIN people p ON ct.assigned_to_person_id = p.id
        LEFT JOIN people p2 ON ct.secondary_assignee_person_id = p2.id
        {where}
        ORDER BY {order_col} {direction} NULLS LAST
    """, params).fetchall()

    topics = []
    topic_ids = []
    for row in rows:
        topic = dict(row)
        topic["questions"] = []
        topics.append(topic)
        topic_ids.append(topic["id"])

    # Batch-fetch questions for all topics
    if topic_ids:
        placeholders = ",".join("?" * len(topic_ids))
        questions = db.execute(f"""
            SELECT * FROM comment_questions
            WHERE comment_topic_id IN ({placeholders})
            ORDER BY sort_order ASC NULLS LAST, question_number ASC
        """, topic_ids).fetchall()

        topic_map = {t["id"]: t for t in topics}
        for q in questions:
            qd = dict(q)
            tid = qd["comment_topic_id"]
            if tid in topic_map:
                topic_map[tid]["questions"].append(qd)

    return {"items": topics, "total": len(topics)}


@router.post("/matters/{matter_id}/comment-topics")
async def create_comment_topic(
    matter_id: str,
    body: CreateCommentTopic,
    request: Request,
    db=Depends(get_db),
    write_source: str = Depends(get_write_source),
):
    """Create a comment topic for a matter."""
    # Verify matter exists
    matter = db.execute("SELECT id FROM matters WHERE id = ?", (matter_id,)).fetchone()
    if not matter:
        raise HTTPException(status_code=404, detail="Matter not found")

    # Override body.matter_id with path param
    if body.matter_id != matter_id:
        body.matter_id = matter_id

    idem_key = request.headers.get("idempotency-key")
    cached = claim_idempotency_key(db, idem_key, body.model_dump(), f"/tracker/matters/{matter_id}/comment-topics")
    if cached == "conflict":
        raise HTTPException(409, detail="Idempotency key reused with different payload")
    if cached == "pending":
        raise HTTPException(409, detail="Request with this idempotency key is still in progress")
    if isinstance(cached, dict):
        return JSONResponse(status_code=cached["status_code"], content=json.loads(cached["body"]))

    tid = str(uuid.uuid4())
    now = datetime.now().isoformat()
    source_val = write_source if body.source == "manual" else body.source

    db.execute("""
        INSERT INTO comment_topics (
            id, matter_id, topic_label, topic_area,
            assigned_to_person_id, secondary_assignee_person_id,
            position_status, position_summary, priority, due_date, deadline_type,
            source_fr_doc_number, source_document_type, response_fr_doc_number,
            notes, sort_order, source, source_id,
            ai_confidence, automation_hold, external_refs,
            created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (tid, matter_id, body.topic_label, body.topic_area,
          body.assigned_to_person_id, body.secondary_assignee_person_id,
          body.position_status, body.position_summary, body.priority,
          body.due_date, body.deadline_type,
          body.source_fr_doc_number, body.source_document_type,
          body.response_fr_doc_number,
          body.notes, body.sort_order, source_val, body.source_id,
          body.ai_confidence, body.automation_hold, body.external_refs,
          now, now))

    new_data = body.model_dump()
    new_data.update({"id": tid, "source": source_val, "created_at": now, "updated_at": now})
    log_event(db, table_name="comment_topics", record_id=tid, action="create",
              source=write_source, new_data=new_data)

    result = {"id": tid}
    finalize_idempotency_key(db, idem_key, 200, result)
    db.commit()
    return result


@router.get("/comment-topics/{topic_id}")
async def get_comment_topic(topic_id: str, db=Depends(get_db)):
    """Get a single topic with nested questions."""
    row = db.execute("""
        SELECT ct.*,
               p.full_name as assigned_to_name,
               p2.full_name as secondary_assignee_name,
               m.title as matter_title, m.matter_number
        FROM comment_topics ct
        LEFT JOIN people p ON ct.assigned_to_person_id = p.id
        LEFT JOIN people p2 ON ct.secondary_assignee_person_id = p2.id
        LEFT JOIN matters m ON ct.matter_id = m.id
        WHERE ct.id = ?
    """, (topic_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Comment topic not found")

    topic = dict(row)
    questions = db.execute("""
        SELECT * FROM comment_questions
        WHERE comment_topic_id = ?
        ORDER BY sort_order ASC NULLS LAST, question_number ASC
    """, (topic_id,)).fetchall()
    topic["questions"] = [dict(q) for q in questions]

    return JSONResponse(content=topic, headers={"ETag": get_etag(row)})


@router.put("/comment-topics/{topic_id}")
async def update_comment_topic(
    topic_id: str,
    body: UpdateCommentTopic,
    request: Request,
    db=Depends(get_db),
    write_source: str = Depends(get_write_source),
):
    """Update a comment topic."""
    old = db.execute("SELECT * FROM comment_topics WHERE id = ?", (topic_id,)).fetchone()
    if not old:
        raise HTTPException(status_code=404, detail="Comment topic not found")
    check_etag(request, old)

    data = body.model_dump(exclude_unset=True)
    if not data:
        raise HTTPException(status_code=400, detail="No fields to update")

    sets = [f"{k} = ?" for k in data]
    params = list(data.values())
    now = datetime.now().isoformat()
    sets.append("updated_at = ?")
    params.extend([now, topic_id])

    db.execute(f"UPDATE comment_topics SET {', '.join(sets)} WHERE id = ?", params)
    log_event(db, table_name="comment_topics", record_id=topic_id, action="update",
              source=write_source, old_record=old, new_data=data)
    db.commit()
    return {"id": topic_id, "updated": True}


@router.delete("/comment-topics/{topic_id}")
async def delete_comment_topic(
    topic_id: str,
    request: Request,
    db=Depends(get_db),
    write_source: str = Depends(get_write_source),
):
    """Delete a topic and cascade-delete all child questions."""
    old = db.execute("SELECT * FROM comment_topics WHERE id = ?", (topic_id,)).fetchone()
    if not old:
        raise HTTPException(status_code=404, detail="Comment topic not found")
    check_etag(request, old)

    # Count questions for audit
    q_count = db.execute(
        "SELECT COUNT(*) as c FROM comment_questions WHERE comment_topic_id = ?",
        (topic_id,)
    ).fetchone()["c"]

    # Cascade delete questions first
    db.execute("DELETE FROM comment_questions WHERE comment_topic_id = ?", (topic_id,))
    db.execute("DELETE FROM comment_topics WHERE id = ?", (topic_id,))

    log_event(db, table_name="comment_topics", record_id=topic_id, action="delete",
              source=write_source, old_record=old,
              new_data={"cascade_deleted_questions": q_count})
    db.commit()
    return {"id": topic_id, "deleted": True, "questions_deleted": q_count}


# ---------------------------------------------------------------------------
# Questions (children of topics)
# ---------------------------------------------------------------------------

@router.post("/comment-topics/{topic_id}/questions")
async def create_comment_question(
    topic_id: str,
    body: CreateCommentQuestion,
    request: Request,
    db=Depends(get_db),
    write_source: str = Depends(get_write_source),
):
    """Add a question to a topic."""
    topic = db.execute("SELECT id, matter_id FROM comment_topics WHERE id = ?", (topic_id,)).fetchone()
    if not topic:
        raise HTTPException(status_code=404, detail="Comment topic not found")

    idem_key = request.headers.get("idempotency-key")
    cached = claim_idempotency_key(db, idem_key, body.model_dump(), f"/tracker/comment-topics/{topic_id}/questions")
    if cached == "conflict":
        raise HTTPException(409, detail="Idempotency key reused with different payload")
    if cached == "pending":
        raise HTTPException(409, detail="Request with this idempotency key is still in progress")
    if isinstance(cached, dict):
        return JSONResponse(status_code=cached["status_code"], content=json.loads(cached["body"]))

    qid = str(uuid.uuid4())
    now = datetime.now().isoformat()
    source_val = write_source if body.source == "manual" else body.source

    db.execute("""
        INSERT INTO comment_questions (
            id, comment_topic_id, question_number, question_text,
            sort_order, source, source_id, ai_confidence, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (qid, topic_id, body.question_number, body.question_text,
          body.sort_order, source_val, body.source_id, body.ai_confidence, now))

    new_data = body.model_dump()
    new_data.update({"id": qid, "comment_topic_id": topic_id, "source": source_val, "created_at": now})
    log_event(db, table_name="comment_questions", record_id=qid, action="create",
              source=write_source, new_data=new_data)

    result = {"id": qid}
    finalize_idempotency_key(db, idem_key, 200, result)
    db.commit()
    return result


@router.put("/comment-questions/{question_id}")
async def update_comment_question(
    question_id: str,
    body: UpdateCommentQuestion,
    request: Request,
    db=Depends(get_db),
    write_source: str = Depends(get_write_source),
):
    """Update a question's text or sort order."""
    old = db.execute("SELECT * FROM comment_questions WHERE id = ?", (question_id,)).fetchone()
    if not old:
        raise HTTPException(status_code=404, detail="Comment question not found")

    data = body.model_dump(exclude_unset=True)
    if not data:
        raise HTTPException(status_code=400, detail="No fields to update")

    sets = [f"{k} = ?" for k in data]
    params = list(data.values())
    params.append(question_id)

    # comment_questions has no updated_at by design
    db.execute(f"UPDATE comment_questions SET {', '.join(sets)} WHERE id = ?", params)
    log_event(db, table_name="comment_questions", record_id=question_id, action="update",
              source=write_source, old_record=old, new_data=data)
    db.commit()
    return {"id": question_id, "updated": True}


@router.delete("/comment-questions/{question_id}")
async def delete_comment_question(
    question_id: str,
    request: Request,
    db=Depends(get_db),
    write_source: str = Depends(get_write_source),
):
    """Delete a single question."""
    old = db.execute("SELECT * FROM comment_questions WHERE id = ?", (question_id,)).fetchone()
    if not old:
        raise HTTPException(status_code=404, detail="Comment question not found")

    db.execute("DELETE FROM comment_questions WHERE id = ?", (question_id,))
    log_event(db, table_name="comment_questions", record_id=question_id, action="delete",
              source=write_source, old_record=old)
    db.commit()
    return {"id": question_id, "deleted": True}


@router.patch("/comment-questions/{question_id}/move")
async def move_comment_question(
    question_id: str,
    body: MoveCommentQuestion,
    request: Request,
    db=Depends(get_db),
    write_source: str = Depends(get_write_source),
):
    """Move a question to a different topic."""
    old = db.execute("SELECT * FROM comment_questions WHERE id = ?", (question_id,)).fetchone()
    if not old:
        raise HTTPException(status_code=404, detail="Comment question not found")

    # Verify target topic exists
    target = db.execute("SELECT id, matter_id FROM comment_topics WHERE id = ?",
                        (body.target_topic_id,)).fetchone()
    if not target:
        raise HTTPException(status_code=404, detail="Target topic not found")

    # Verify same matter (can't move questions across matters)
    source_topic = db.execute("SELECT matter_id FROM comment_topics WHERE id = ?",
                              (old["comment_topic_id"],)).fetchone()
    if source_topic and target and source_topic["matter_id"] != target["matter_id"]:
        raise HTTPException(status_code=400,
                            detail="Cannot move question to a topic in a different matter")

    db.execute("UPDATE comment_questions SET comment_topic_id = ? WHERE id = ?",
               (body.target_topic_id, question_id))
    log_event(db, table_name="comment_questions", record_id=question_id, action="update",
              source=write_source, old_record=old,
              new_data={"comment_topic_id": body.target_topic_id, "moved_from": old["comment_topic_id"]})
    db.commit()
    return {"id": question_id, "moved": True,
            "from_topic_id": old["comment_topic_id"],
            "to_topic_id": body.target_topic_id}
