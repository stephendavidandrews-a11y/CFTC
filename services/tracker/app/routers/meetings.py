"""Meeting CRUD endpoints."""
import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from app.db import get_db
from app.validators import CreateMeeting, UpdateMeeting

router = APIRouter(prefix="/meetings", tags=["meetings"])

@router.get("")
async def list_meetings(
    db=Depends(get_db),
    search: str = Query(None),
    meeting_type: str = Query(None),
    sort_by: str = Query("date_time_start"),
    sort_dir: str = Query("desc"),
    limit: int = Query(100),
    offset: int = Query(0),
):
    conditions, params = [], []
    if search:
        conditions.append("(m.title LIKE ? OR m.purpose LIKE ?)")
        params.extend([f"%{search}%"] * 2)
    if meeting_type:
        conditions.append("m.meeting_type = ?")
        params.append(meeting_type)
    where = "WHERE " + " AND ".join(conditions) if conditions else ""

    total = db.execute(f"SELECT COUNT(*) as c FROM meetings m {where}", params).fetchone()["c"]
    rows = db.execute(f"""
        SELECT m.*, p.full_name as owner_name
        FROM meetings m
        LEFT JOIN people p ON m.assigned_to_person_id = p.id
        {where}
        ORDER BY m.date_time_start {"DESC" if sort_dir == "desc" else "ASC"}
        LIMIT ? OFFSET ?
    """, params + [limit, offset]).fetchall()
    return {"items": [dict(row) for row in rows], "total": total, "limit": limit, "offset": offset}


@router.get("/{meeting_id}")
async def get_meeting(meeting_id: str, db=Depends(get_db)):
    row = db.execute("SELECT * FROM meetings WHERE id = ?", (meeting_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Meeting not found")
    result = dict(row)
    result["participants"] = [dict(r) for r in db.execute("""
        SELECT mp.*, p.full_name, p.title as person_title, o.name as org_name
        FROM meeting_participants mp
        JOIN people p ON mp.person_id = p.id
        LEFT JOIN organizations o ON mp.organization_id = o.id
        WHERE mp.meeting_id = ?
    """, (meeting_id,))]
    result["matters"] = [dict(r) for r in db.execute("""
        SELECT mm.*, m.title as matter_title, m.matter_number
        FROM meeting_matters mm
        JOIN matters m ON mm.matter_id = m.id
        WHERE mm.meeting_id = ?
    """, (meeting_id,))]
    return result


@router.post("")
async def create_meeting(body: CreateMeeting, db=Depends(get_db)):
    mid = str(uuid.uuid4())
    now = datetime.now().isoformat()
    db.execute("""
        INSERT INTO meetings (id, title, meeting_type, date_time_start, date_time_end,
            location_or_link, purpose, prep_needed, notes, boss_attends, external_parties_attend,
            assigned_to_person_id, created_by_person_id, source, source_id, external_refs,
            created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (mid, body.title, body.meeting_type, body.date_time_start,
          body.date_time_end, body.location_or_link, body.purpose,
          body.prep_needed, body.notes,
          body.boss_attends, body.external_parties_attend,
          body.assigned_to_person_id, body.created_by_person_id,
          body.source, body.source_id, body.external_refs,
          now, now))
    # Add participants if provided
    for p in body.participants:
        db.execute("""
            INSERT INTO meeting_participants (id, meeting_id, person_id, organization_id, meeting_role, attendance_status)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (str(uuid.uuid4()), mid, p.person_id, p.organization_id,
              p.meeting_role, p.attendance_status))
    # Link matters if provided
    for m in body.matter_ids:
        db.execute("""
            INSERT INTO meeting_matters (id, meeting_id, matter_id, relationship_type, created_at, updated_at)
            VALUES (?, ?, ?, 'primary topic', ?, ?)
        """, (str(uuid.uuid4()), mid, m, now, now))
    db.commit()
    return {"id": mid}


@router.put("/{meeting_id}")
async def update_meeting(meeting_id: str, body: UpdateMeeting, db=Depends(get_db)):
    existing = db.execute("SELECT id FROM meetings WHERE id = ?", (meeting_id,)).fetchone()
    if not existing:
        raise HTTPException(status_code=404, detail="Meeting not found")
    data = body.model_dump(exclude_unset=True)
    if not data:
        raise HTTPException(status_code=400, detail="No fields to update")
    sets = [f"{k} = ?" for k in data]
    params = list(data.values())
    now = datetime.now().isoformat()
    sets.append("updated_at = ?")
    params.extend([now, meeting_id])
    db.execute(f"UPDATE meetings SET {', '.join(sets)} WHERE id = ?", params)
    db.commit()
    return {"id": meeting_id, "updated": True}


@router.delete("/{meeting_id}")
async def delete_meeting(meeting_id: str, db=Depends(get_db)):
    """Delete a meeting and its participant/matter links."""
    existing = db.execute("SELECT id FROM meetings WHERE id = ?", (meeting_id,)).fetchone()
    if not existing:
        raise HTTPException(status_code=404, detail="Meeting not found")
    db.execute("DELETE FROM meeting_participants WHERE meeting_id = ?", (meeting_id,))
    db.execute("DELETE FROM meeting_matters WHERE meeting_id = ?", (meeting_id,))
    db.execute("DELETE FROM meetings WHERE id = ?", (meeting_id,))
    db.commit()
    return {"id": meeting_id, "deleted": True}
