"""People CRUD endpoints."""
import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from app.db import get_db
from app.validators import CreatePerson, UpdatePerson

router = APIRouter(prefix="/people", tags=["people"])

@router.get("")
async def list_people(
    db=Depends(get_db),
    search: str = Query(None),
    organization_id: str = Query(None),
    relationship_category: str = Query(None),
    relationship_lane: str = Query(None),
    include_in_team: bool = Query(None),
    is_active: bool = Query(True),
    sort_by: str = Query("full_name"),
    sort_dir: str = Query("asc"),
    limit: int = Query(100, le=500),
    offset: int = Query(0),
):
    conditions = ["p.is_active = ?"]
    params = [1 if is_active else 0]
    if search:
        conditions.append("(p.full_name LIKE ? OR p.email LIKE ? OR p.title LIKE ?)")
        params.extend([f"%{search}%"] * 3)
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
    allowed_sorts = {"full_name", "title", "organization_id", "last_interaction_date", "created_at"}
    if sort_by not in allowed_sorts:
        sort_by = "full_name"
    direction = "DESC" if sort_dir.lower() == "desc" else "ASC"

    total = db.execute(f"SELECT COUNT(*) as c FROM people p {where}", params).fetchone()["c"]
    rows = db.execute(f"""
        SELECT p.*, o.name as org_name, o.short_name as org_short_name
        FROM people p
        LEFT JOIN organizations o ON p.organization_id = o.id
        {where}
        ORDER BY p.{sort_by} {direction}
        LIMIT ? OFFSET ?
    """, params + [limit, offset]).fetchall()

    return {"items": [dict(row) for row in rows], "total": total, "limit": limit, "offset": offset}


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
        SELECT t.id, t.title, t.status, t.due_date, t.priority, m.title as matter_title
        FROM tasks t
        LEFT JOIN matters m ON t.matter_id = m.id
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

    return result


@router.post("")
async def create_person(body: CreatePerson, db=Depends(get_db)):
    pid = str(uuid.uuid4())
    now = datetime.now().isoformat()
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
        body.relationship_assigned_to_person_id, 1,
        body.source, body.source_id, body.external_refs,
        now, now,
    ))
    db.commit()
    return {"id": pid}


@router.put("/{person_id}")
async def update_person(person_id: str, body: UpdatePerson, db=Depends(get_db)):
    existing = db.execute("SELECT id FROM people WHERE id = ?", (person_id,)).fetchone()
    if not existing:
        raise HTTPException(status_code=404, detail="Person not found")
    data = body.model_dump(exclude_unset=True)
    if not data:
        raise HTTPException(status_code=400, detail="No fields to update")
    sets = [f"{k} = ?" for k in data]
    params = list(data.values())
    now = datetime.now().isoformat()
    sets.append("updated_at = ?")
    params.extend([now, person_id])
    db.execute(f"UPDATE people SET {', '.join(sets)} WHERE id = ?", params)
    db.commit()
    return {"id": person_id, "updated": True}


@router.delete("/{person_id}")
async def delete_person(person_id: str, db=Depends(get_db)):
    """Soft-delete a person by setting is_active = 0."""
    existing = db.execute("SELECT id FROM people WHERE id = ?", (person_id,)).fetchone()
    if not existing:
        raise HTTPException(status_code=404, detail="Person not found")
    now = datetime.now().isoformat()
    db.execute(
        "UPDATE people SET is_active = 0, updated_at = ? WHERE id = ?",
        (now, person_id)
    )
    db.commit()
    return {"id": person_id, "deleted": True}
