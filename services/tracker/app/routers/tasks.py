"""Task CRUD endpoints."""
import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from app.db import get_db
from app.validators import CreateTask, UpdateTask

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
    return dict(row)


@router.post("")
async def create_task(body: CreateTask, db=Depends(get_db)):
    task_id = str(uuid.uuid4())
    now = datetime.now().isoformat()
    db.execute("""
        INSERT INTO tasks (id, matter_id, title, description, task_type, status, task_mode,
            priority, assigned_to_person_id, created_by_person_id, delegated_by_person_id,
            supervising_person_id, waiting_on_person_id, waiting_on_org_id,
            expected_output, due_date, deadline_type, sort_order,
            source, source_id, ai_confidence, automation_hold, external_refs,
            created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        task_id, body.matter_id, body.title, body.description,
        body.task_type, body.status, body.task_mode,
        body.priority, body.assigned_to_person_id,
        body.created_by_person_id, body.delegated_by_person_id,
        body.supervising_person_id, body.waiting_on_person_id,
        body.waiting_on_org_id,
        body.expected_output, body.due_date, body.deadline_type,
        body.sort_order,
        body.source, body.source_id,
        body.ai_confidence, body.automation_hold, body.external_refs,
        now, now,
    ))
    db.commit()
    return {"id": task_id}


@router.put("/{task_id}")
async def update_task(task_id: str, body: UpdateTask, db=Depends(get_db)):
    existing = db.execute("SELECT id FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if not existing:
        raise HTTPException(status_code=404, detail="Task not found")

    data = body.model_dump(exclude_unset=True)
    if not data:
        raise HTTPException(status_code=400, detail="No fields to update")
    sets = [f"{k} = ?" for k in data]
    params = list(data.values())

    now = datetime.now().isoformat()
    sets.append("updated_at = ?")
    params.extend([now, task_id])
    db.execute(f"UPDATE tasks SET {', '.join(sets)} WHERE id = ?", params)
    db.commit()
    return {"id": task_id, "updated": True}


@router.delete("/{task_id}")
async def delete_task(task_id: str, db=Depends(get_db)):
    db.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    db.commit()
    return {"deleted": True}
