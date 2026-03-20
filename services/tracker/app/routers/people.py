"""People CRUD endpoints."""
import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from app.db import get_db
from app.validators import CreatePerson, UpdatePerson
import json
from fastapi import Request
from fastapi.responses import JSONResponse
from app.deps import get_write_source
from app.audit import log_event
from app.concurrency import get_etag, check_etag
from app.idempotency import claim_idempotency_key, finalize_idempotency_key

router = APIRouter(prefix="/people", tags=["people"])

@router.get("")
async def list_people(
    db=Depends(get_db),
    search: str = Query(None),
    organization_id: str = Query(None),
    relationship_category: str = Query(None),
    relationship_lane: str = Query(None),
    include_in_team: bool = Query(None),
    is_active: bool = Query(None),
    sort_by: str = Query("full_name"),
    sort_dir: str = Query("asc"),
    limit: int = Query(100, le=500),
    offset: int = Query(0),
):
    conditions = []
    params = []
    if is_active is not None:
        conditions.append("p.is_active = ?")
        params.append(1 if is_active else 0)
    if search:
        conditions.append("(p.full_name LIKE ? OR p.email LIKE ? OR p.title LIKE ? OR o.name LIKE ? OR o.short_name LIKE ? OR p.relationship_category LIKE ?)")
        params.extend([f"%{search}%"] * 6)
    if organization_id:
        conditions.append("p.organization_id = ?")
        params.append(organization_id)
    if relationship_category:
        conditions.append("p.relationship_category = ?")
        params.append(relationship_category)
    if relationship_lane:
        conditions.append("p.relationship_lane = ?")
        params.append(relationship_lane)
    if include_in_team is not None:
        conditions.append("p.include_in_team_workload = ?")
        params.append(1 if include_in_team else 0)

    where = "WHERE " + " AND ".join(conditions) if conditions else ""
    allowed_sorts = {"full_name", "title", "organization_id", "last_interaction_date",
                     "next_interaction_needed_date", "created_at", "active_matters", "open_tasks"}
    if sort_by not in allowed_sorts:
        sort_by = "full_name"
    direction = "DESC" if sort_dir.lower() == "desc" else "ASC"

    total = db.execute(f"""
        SELECT COUNT(*) as c FROM people p
        LEFT JOIN organizations o ON p.organization_id = o.id
        {where}
    """, params).fetchone()["c"]
    order_expr = {
        "active_matters": "active_matters",
        "open_tasks": "open_tasks",
    }.get(sort_by, f"p.{sort_by}")
    rows = db.execute(f"""
        SELECT p.*, o.name as org_name, o.short_name as org_short_name,
            (SELECT COUNT(DISTINCT mp.matter_id) FROM matter_people mp
             JOIN matters m ON mp.matter_id = m.id
             WHERE mp.person_id = p.id AND m.status != 'closed') AS active_matters,
            (SELECT COUNT(*) FROM tasks t
             WHERE t.assigned_to_person_id = p.id AND t.status NOT IN ('completed', 'deferred')) AS open_tasks
        FROM people p
        LEFT JOIN organizations o ON p.organization_id = o.id
        {where}
        ORDER BY {order_expr} {direction}
        LIMIT ? OFFSET ?
    """, params + [limit, offset]).fetchall()

    items = [dict(row) for row in rows]

    # Summary counts (always unfiltered active people)
    summary_rows = db.execute("""
        SELECT
            SUM(CASE WHEN p.include_in_team_workload = 1 THEN 1 ELSE 0 END) as team,
            SUM(CASE WHEN p.relationship_category = 'Internal client' THEN 1 ELSE 0 END) as internal_clients,
            SUM(CASE WHEN p.relationship_category IN ('Partner agency', 'Hill', 'Outside party') THEN 1 ELSE 0 END) as external_stakeholders,
            SUM(CASE WHEN p.next_interaction_needed_date IS NOT NULL AND p.next_interaction_needed_date <= date('now', '+7 days') THEN 1 ELSE 0 END) as follow_up_needed
        FROM people p WHERE p.is_active = 1
    """).fetchone()
    summary = {
        "team": summary_rows["team"] or 0,
        "internal_clients": summary_rows["internal_clients"] or 0,
        "external_stakeholders": summary_rows["external_stakeholders"] or 0,
        "follow_up_needed": summary_rows["follow_up_needed"] or 0,
    }

    return {"items": items, "total": total, "limit": limit, "offset": offset, "summary": summary}


@router.get("/{person_id}")
async def get_person(person_id: str, db=Depends(get_db)):
    row = db.execute("""
        SELECT p.*, o.name as org_name, o.short_name as org_short_name,
               mgr.full_name as manager_name
        FROM people p
        LEFT JOIN organizations o ON p.organization_id = o.id
        LEFT JOIN people mgr ON p.manager_person_id = mgr.id
        WHERE p.id = ?
    """, (person_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Person not found")

    result = dict(row)

    # Relationship owner name
    if result.get("relationship_assigned_to_person_id"):
        owner_row = db.execute(
            "SELECT full_name FROM people WHERE id = ?",
            (result["relationship_assigned_to_person_id"],)
        ).fetchone()
        result["relationship_owner_name"] = owner_row["full_name"] if owner_row else None
    else:
        result["relationship_owner_name"] = None

    # Matters this person is on
    result["matters"] = [dict(r) for r in db.execute("""
        SELECT mp.matter_role, mp.engagement_level, m.id, m.title, m.matter_number, m.status, m.priority
        FROM matter_people mp
        JOIN matters m ON mp.matter_id = m.id
        WHERE mp.person_id = ? AND m.status != 'closed'
        ORDER BY m.priority, m.updated_at DESC
    """, (person_id,))]

    # Tasks assigned
    result["tasks"] = [dict(r) for r in db.execute("""
        SELECT t.id, t.title, t.status, t.due_date, t.priority,
               t.expected_output, t.waiting_on_description,
               m.title as matter_title,
               wp.full_name as waiting_on_person_name
        FROM tasks t
        LEFT JOIN matters m ON t.matter_id = m.id
        LEFT JOIN people wp ON t.waiting_on_person_id = wp.id
        WHERE t.assigned_to_person_id = ? AND t.status NOT IN ('done', 'deferred')
        ORDER BY t.due_date
    """, (person_id,))]

    # Recent meetings
    result["meetings"] = [dict(r) for r in db.execute("""
        SELECT mtg.id, mtg.title, mtg.date_time_start, mtg.meeting_type, mp.meeting_role
        FROM meeting_participants mp
        JOIN meetings mtg ON mp.meeting_id = mtg.id
        WHERE mp.person_id = ?
        ORDER BY mtg.date_time_start DESC
        LIMIT 10
    """, (person_id,))]

    return JSONResponse(content=result, headers={"ETag": get_etag(row)})


@router.post("")
async def create_person(body: CreatePerson, request: Request, db=Depends(get_db),
                      write_source: str = Depends(get_write_source)):
    idem_key = request.headers.get("idempotency-key")
    cached = claim_idempotency_key(db, idem_key, body.model_dump(), "/tracker/people")
    if cached == "conflict":
        raise HTTPException(409, detail="Idempotency key reused with different payload")
    if cached == "pending":
        raise HTTPException(409, detail="Request with this idempotency key is still in progress")
    if isinstance(cached, dict):
        return JSONResponse(status_code=cached["status_code"], content=json.loads(cached["body"]))
    pid = str(uuid.uuid4())
    now = datetime.now().isoformat()
    source_val = write_source if body.source == "manual" else body.source
    # Auto-set include_in_team_workload for Direct reports
    if body.relationship_category in ("Direct report", "Indirect report") and body.include_in_team_workload is None:
        body.include_in_team_workload = 1
    db.execute("""
        INSERT INTO people (id, full_name, first_name, last_name, title, organization_id,
            email, phone, assistant_name, assistant_contact, working_style_notes,
            substantive_areas, relationship_category, relationship_lane, personality,
            last_interaction_date, next_interaction_needed_date, next_interaction_type,
            next_interaction_purpose, manager_person_id, include_in_team_workload,
            relationship_assigned_to_person_id, is_active,
            source, source_id, external_refs, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        pid, body.full_name, body.first_name, body.last_name,
        body.title, body.organization_id,
        body.email, body.phone, body.assistant_name,
        body.assistant_contact, body.working_style_notes,
        body.substantive_areas, body.relationship_category,
        body.relationship_lane, body.personality,
        body.last_interaction_date, body.next_interaction_needed_date,
        body.next_interaction_type, body.next_interaction_purpose,
        body.manager_person_id, body.include_in_team_workload,
        body.relationship_assigned_to_person_id, body.is_active,
        source_val, body.source_id, body.external_refs,
        now, now,
    ))
    new_data = body.model_dump()
    new_data.update({"id": pid, "source": source_val, "created_at": now, "updated_at": now})
    log_event(db, table_name="people", record_id=pid, action="create",
              source=write_source, new_data=new_data)
    result = {"id": pid}
    finalize_idempotency_key(db, idem_key, 200, result)
    db.commit()
    return result


@router.put("/{person_id}")
async def update_person(person_id: str, body: UpdatePerson, request: Request, db=Depends(get_db),
                      write_source: str = Depends(get_write_source)):
    old = db.execute("SELECT * FROM people WHERE id = ?", (person_id,)).fetchone()
    if not old:
        raise HTTPException(status_code=404, detail="Person not found")
    check_etag(request, old)
    data = body.model_dump(exclude_unset=True)
    if not data:
        raise HTTPException(status_code=400, detail="No fields to update")
    # Auto-set include_in_team_workload for Direct reports (only if not explicitly set in payload or DB)
    if data.get("relationship_category") in ("Direct report", "Indirect report"):
        if "include_in_team_workload" not in data and not old["include_in_team_workload"]:
            data["include_in_team_workload"] = 1
    sets = [f"{k} = ?" for k in data]
    params = list(data.values())
    now = datetime.now().isoformat()
    sets.append("updated_at = ?")
    params.extend([now, person_id])
    db.execute(f"UPDATE people SET {', '.join(sets)} WHERE id = ?", params)
    log_event(db, table_name="people", record_id=person_id, action="update",
              source=write_source, old_record=old, new_data=data)
    db.commit()
    return {"id": person_id, "updated": True}


@router.delete("/{person_id}")
async def delete_person(person_id: str, request: Request, db=Depends(get_db),
                      write_source: str = Depends(get_write_source)):
    """Soft-delete a person by setting is_active = 0."""
    old = db.execute("SELECT * FROM people WHERE id = ?", (person_id,)).fetchone()
    if not old:
        raise HTTPException(status_code=404, detail="Person not found")
    check_etag(request, old)
    now = datetime.now().isoformat()
    db.execute(
        "UPDATE people SET is_active = 0, updated_at = ? WHERE id = ?",
        (now, person_id)
    )
    log_event(db, table_name="people", record_id=person_id, action="delete",
              source=write_source, old_record=old)
    db.commit()
    return {"id": person_id, "deleted": True}
