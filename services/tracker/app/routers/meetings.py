"""Meeting CRUD endpoints."""
import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from app.db import get_db
from app.validators import CreateMeeting, UpdateMeeting
import json
from fastapi import Request
from fastapi.responses import JSONResponse
from app.deps import get_write_source
from app.audit import log_event
from app.concurrency import get_etag, check_etag
from app.idempotency import claim_idempotency_key, finalize_idempotency_key

router = APIRouter(prefix="/meetings", tags=["meetings"])

@router.get("")
async def list_meetings(
    db=Depends(get_db),
    search: str = Query(None),
    meeting_type: str = Query(None),
    matter_id: str = Query(None),
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
    if matter_id:
        conditions.append("m.id IN (SELECT mm.meeting_id FROM meeting_matters mm WHERE mm.matter_id = ?)")
        params.append(matter_id)
    where = "WHERE " + " AND ".join(conditions) if conditions else ""

    total = db.execute(f"SELECT COUNT(*) as c FROM meetings m {where}", params).fetchone()["c"]
    rows = db.execute(f"""
        SELECT m.*, p.full_name as owner_name,
               (SELECT mat.title FROM meeting_matters mm
                JOIN matters mat ON mm.matter_id = mat.id
                WHERE mm.meeting_id = m.id LIMIT 1) as matter_title
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
        SELECT m.id, m.title as matter_title, m.matter_number, m.status, m.priority,
               mm.relationship_type, mm.decision_made, mm.decision_summary, mm.notes
        FROM meeting_matters mm
        JOIN matters m ON mm.matter_id = m.id
        WHERE mm.meeting_id = ?
    """, (meeting_id,))]
    return JSONResponse(content=result, headers={"ETag": get_etag(row)})


@router.post("")
async def create_meeting(body: CreateMeeting, request: Request, db=Depends(get_db),
                      write_source: str = Depends(get_write_source)):
    idem_key = request.headers.get("idempotency-key")
    cached = claim_idempotency_key(db, idem_key, body.model_dump(), "/tracker/meetings")
    if cached == "conflict":
        raise HTTPException(409, detail="Idempotency key reused with different payload")
    if cached == "pending":
        raise HTTPException(409, detail="Request with this idempotency key is still in progress")
    if isinstance(cached, dict):
        return JSONResponse(status_code=cached["status_code"], content=json.loads(cached["body"]))
    mid = str(uuid.uuid4())
    now = datetime.now().isoformat()
    source_val = write_source if body.source == "manual" else body.source
    db.execute("""
        INSERT INTO meetings (id, title, meeting_type, date_time_start, date_time_end,
            location_or_link, purpose, prep_needed, notes,
            decisions_made, readout_summary, created_followups,
            boss_attends, external_parties_attend,
            assigned_to_person_id, created_by_person_id, source, source_id, external_refs,
            created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (mid, body.title, body.meeting_type, body.date_time_start,
          body.date_time_end, body.location_or_link, body.purpose,
          body.prep_needed, body.notes,
          body.decisions_made, body.readout_summary, body.created_followups,
          body.boss_attends, body.external_parties_attend,
          body.assigned_to_person_id, body.created_by_person_id,
          source_val, body.source_id, body.external_refs,
          now, now))
    # Add participants if provided
    for p in body.participants:
        db.execute("""
            INSERT INTO meeting_participants (id, meeting_id, person_id, organization_id,
                meeting_role, attendance_status, attended, follow_up_expected, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (str(uuid.uuid4()), mid, p.person_id, p.organization_id,
              p.meeting_role, p.attendance_status,
              p.attended, p.follow_up_expected, p.notes))
    # Link matters if provided
    for m in body.matter_ids:
        db.execute("""
            INSERT INTO meeting_matters (id, meeting_id, matter_id, relationship_type, created_at, updated_at)
            VALUES (?, ?, ?, 'primary topic', ?, ?)
        """, (str(uuid.uuid4()), mid, m, now, now))
    new_data = body.model_dump()
    new_data.update({"id": mid, "source": source_val, "created_at": now, "updated_at": now})
    log_event(db, table_name="meetings", record_id=mid, action="create",
              source=write_source, new_data=new_data)
    result = {"id": mid}
    finalize_idempotency_key(db, idem_key, 200, result)
    db.commit()
    return result


@router.put("/{meeting_id}")
async def update_meeting(meeting_id: str, body: UpdateMeeting, request: Request, db=Depends(get_db),
                      write_source: str = Depends(get_write_source)):
    old = db.execute("SELECT * FROM meetings WHERE id = ?", (meeting_id,)).fetchone()
    if not old:
        raise HTTPException(status_code=404, detail="Meeting not found")
    check_etag(request, old)
    data = body.model_dump(exclude_unset=True)
    if not data:
        raise HTTPException(status_code=400, detail="No fields to update")
    sets = [f"{k} = ?" for k in data]
    params = list(data.values())
    now = datetime.now().isoformat()
    sets.append("updated_at = ?")
    params.extend([now, meeting_id])
    db.execute(f"UPDATE meetings SET {', '.join(sets)} WHERE id = ?", params)
    log_event(db, table_name="meetings", record_id=meeting_id, action="update",
              source=write_source, old_record=old, new_data=data)
    db.commit()
    return {"id": meeting_id, "updated": True}


@router.delete("/{meeting_id}")
async def delete_meeting(meeting_id: str, request: Request, db=Depends(get_db),
                      write_source: str = Depends(get_write_source)):
    """Delete a meeting and its participant/matter links."""
    old = db.execute("SELECT * FROM meetings WHERE id = ?", (meeting_id,)).fetchone()
    if not old:
        raise HTTPException(status_code=404, detail="Meeting not found")
    check_etag(request, old)
    db.execute("DELETE FROM meeting_participants WHERE meeting_id = ?", (meeting_id,))
    db.execute("DELETE FROM meeting_matters WHERE meeting_id = ?", (meeting_id,))
    db.execute("DELETE FROM meetings WHERE id = ?", (meeting_id,))
    log_event(db, table_name="meetings", record_id=meeting_id, action="delete",
              source=write_source, old_record=old)
    db.commit()
    return {"id": meeting_id, "deleted": True}


# --- Meeting Participants (post-creation management) ---

@router.post("/{meeting_id}/participants")
async def add_participant(meeting_id: str, body: dict, db=Depends(get_db)):
    """Add a participant to an existing meeting."""
    person_id = body.get("person_id")
    if not person_id:
        raise HTTPException(status_code=400, detail="person_id required")
    pid = str(uuid.uuid4())
    db.execute("""
        INSERT INTO meeting_participants (id, meeting_id, person_id, organization_id,
            meeting_role, attendance_status, attended, follow_up_expected, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (pid, meeting_id, person_id,
          body.get("organization_id"),
          body.get("meeting_role", "attendee"),
          body.get("attendance_status", "invited"),
          body.get("attended"),
          body.get("follow_up_expected"),
          body.get("notes")))
    db.commit()
    return {"id": pid}


@router.put("/{meeting_id}/participants/{participant_id}")
async def update_participant(meeting_id: str, participant_id: str, body: dict, db=Depends(get_db)):
    """Update a meeting participant."""
    updates = []
    params = []
    for field in ["meeting_role", "attendance_status", "attended", "follow_up_expected", "notes"]:
        val = body.get(field)
        if val is not None:
            updates.append(f"{field} = ?")
            params.append(val)
    if not updates:
        return {"id": participant_id, "updated": False}
    params.extend([participant_id, meeting_id])
    set_clause = ", ".join(updates)
    db.execute(f"UPDATE meeting_participants SET {set_clause} WHERE id = ? AND meeting_id = ?", params)
    db.commit()
    return {"id": participant_id, "updated": True}


@router.delete("/{meeting_id}/participants/{participant_id}")
async def remove_participant(meeting_id: str, participant_id: str, db=Depends(get_db)):
    """Remove a participant from a meeting."""
    db.execute("DELETE FROM meeting_participants WHERE id = ? AND meeting_id = ?",
               (participant_id, meeting_id))
    db.commit()
    return {"deleted": True}


# --- Meeting Matters (post-creation management) ---

@router.put("/{meeting_id}/matters")
async def update_meeting_matters(meeting_id: str, body: dict, db=Depends(get_db)):
    """Replace the set of matters linked to a meeting."""
    matter_ids = body.get("matter_ids", [])
    db.execute("DELETE FROM meeting_matters WHERE meeting_id = ?", (meeting_id,))
    now = datetime.now().isoformat()
    for mid in matter_ids:
        mm_id = str(uuid.uuid4())
        db.execute("""
            INSERT INTO meeting_matters (id, meeting_id, matter_id, relationship_type, created_at, updated_at)
            VALUES (?, ?, ?, 'primary topic', ?, ?)
        """, (mm_id, meeting_id, mid, now, now))
    db.commit()
    return {"updated": True, "matter_count": len(matter_ids)}
