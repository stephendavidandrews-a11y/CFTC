"""Task CRUD endpoints."""
import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from app.db import get_db
from app.validators import CreateTask, UpdateTask
import json
from fastapi import Request
from fastapi.responses import JSONResponse
from app.deps import get_write_source
from app.audit import log_event
from app.concurrency import get_etag, check_etag
from app.idempotency import claim_idempotency_key, finalize_idempotency_key

router = APIRouter(prefix="/tasks", tags=["tasks"])

@router.get("")
async def list_tasks(
    db=Depends(get_db),
    search: str = Query(None),
    status: str = Query(None),
    matter_id: str = Query(None),
    assigned_to: str = Query(None),
    mode: str = Query(None),
    sort_by: str = Query("due_date"),
    sort_dir: str = Query("asc"),
    limit: int = Query(100, le=500),
    offset: int = Query(0),
):
    conditions = []
    params = []
    if search:
        conditions.append("(t.title LIKE ? OR t.description LIKE ?)")
        params.extend([f"%{search}%"] * 2)
    if status:
        conditions.append("t.status = ?")
        params.append(status)
    if matter_id:
        conditions.append("t.matter_id = ?")
        params.append(matter_id)
    if assigned_to:
        conditions.append("t.assigned_to_person_id = ?")
        params.append(assigned_to)
    if mode:
        conditions.append("t.task_mode = ?")
        params.append(mode)

    where = "WHERE " + " AND ".join(conditions) if conditions else ""
    allowed_sorts = {"title", "status", "due_date", "priority", "created_at", "updated_at"}
    if sort_by not in allowed_sorts:
        sort_by = "due_date"
    sort_direction = "DESC" if sort_dir.lower() == "desc" else "ASC"

    total = db.execute(f"SELECT COUNT(*) as c FROM tasks t {where}", params).fetchone()["c"]

    rows = db.execute(f"""
        SELECT t.*, p.full_name as owner_name, m.title as matter_title, m.matter_number
        FROM tasks t
        LEFT JOIN people p ON t.assigned_to_person_id = p.id
        LEFT JOIN matters m ON t.matter_id = m.id
        {where}
        ORDER BY t.{sort_by} {sort_direction} NULLS LAST
        LIMIT ? OFFSET ?
    """, params + [limit, offset]).fetchall()

    return {"items": [dict(row) for row in rows], "total": total, "limit": limit, "offset": offset}


@router.get("/{task_id}")
async def get_task(task_id: str, db=Depends(get_db)):
    row = db.execute("""
        SELECT t.*, p.full_name as owner_name, m.title as matter_title, m.matter_number,
               wp.full_name as waiting_on_name, wo.name as waiting_on_org_name
        FROM tasks t
        LEFT JOIN people p ON t.assigned_to_person_id = p.id
        LEFT JOIN matters m ON t.matter_id = m.id
        LEFT JOIN people wp ON t.waiting_on_person_id = wp.id
        LEFT JOIN organizations wo ON t.waiting_on_org_id = wo.id
        WHERE t.id = ?
    """, (task_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Task not found")
    return JSONResponse(content=dict(row), headers={"ETag": get_etag(row)})


@router.post("")
async def create_task(body: CreateTask, request: Request, db=Depends(get_db),
                      write_source: str = Depends(get_write_source)):
    idem_key = request.headers.get("idempotency-key")
    cached = claim_idempotency_key(db, idem_key, body.model_dump(), "/tracker/tasks")
    if cached == "conflict":
        raise HTTPException(409, detail="Idempotency key reused with different payload")
    if cached == "pending":
        raise HTTPException(409, detail="Request with this idempotency key is still in progress")
    if isinstance(cached, dict):
        return JSONResponse(status_code=cached["status_code"], content=json.loads(cached["body"]))
    task_id = str(uuid.uuid4())
    now = datetime.now().isoformat()
    source_val = write_source if body.source == "manual" else body.source
    db.execute("""
        INSERT INTO tasks (id, matter_id, title, description, task_type, status, task_mode,
            priority, assigned_to_person_id, created_by_person_id, delegated_by_person_id,
            supervising_person_id, waiting_on_person_id, waiting_on_org_id,
            waiting_on_description, expected_output, due_date, deadline_type, sort_order,
            next_follow_up_date, completion_notes, started_at, completed_at,
            source, source_id, ai_confidence, automation_hold, external_refs,
            created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        task_id, body.matter_id, body.title, body.description,
        body.task_type, body.status, body.task_mode,
        body.priority, body.assigned_to_person_id,
        body.created_by_person_id, body.delegated_by_person_id,
        body.supervising_person_id, body.waiting_on_person_id,
        body.waiting_on_org_id, body.waiting_on_description,
        body.expected_output, body.due_date, body.deadline_type,
        body.sort_order,
        body.next_follow_up_date, body.completion_notes,
        body.started_at, body.completed_at,
        source_val, body.source_id,
        body.ai_confidence, body.automation_hold, body.external_refs,
        now, now,
    ))
    new_data = body.model_dump()
    new_data.update({"id": task_id, "source": source_val, "created_at": now, "updated_at": now})
    log_event(db, table_name="tasks", record_id=task_id, action="create",
              source=write_source, new_data=new_data)
    result = {"id": task_id}
    finalize_idempotency_key(db, idem_key, 200, result)
    db.commit()
    return result


@router.put("/{task_id}")
async def update_task(task_id: str, body: UpdateTask, request: Request, db=Depends(get_db),
                      write_source: str = Depends(get_write_source)):
    old = db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if not old:
        raise HTTPException(status_code=404, detail="Task not found")
    check_etag(request, old)

    data = body.model_dump(exclude_unset=True)
    if not data:
        raise HTTPException(status_code=400, detail="No fields to update")
    sets = [f"{k} = ?" for k in data]
    params = list(data.values())

    now = datetime.now().isoformat()
    sets.append("updated_at = ?")
    params.extend([now, task_id])
    db.execute(f"UPDATE tasks SET {', '.join(sets)} WHERE id = ?", params)
    log_event(db, table_name="tasks", record_id=task_id, action="update",
              source=write_source, old_record=old, new_data=data)
    db.commit()
    return {"id": task_id, "updated": True}


@router.delete("/{task_id}")
async def delete_task(task_id: str, request: Request, db=Depends(get_db),
                      write_source: str = Depends(get_write_source)):
    old = db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if not old:
        raise HTTPException(status_code=404, detail="Task not found")
    check_etag(request, old)
    db.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    log_event(db, table_name="tasks", record_id=task_id, action="delete",
              source=write_source, old_record=old)
    db.commit()
    return {"deleted": True}
