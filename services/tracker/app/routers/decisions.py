"""Decision CRUD endpoints."""
import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from app.db import get_db
from app.validators import CreateDecision, UpdateDecision

router = APIRouter(prefix="/decisions", tags=["decisions"])

@router.get("")
async def list_decisions(
    db=Depends(get_db),
    search: str = Query(None),
    status: str = Query(None),
    matter_id: str = Query(None),
    sort_by: str = Query("decision_due_date"),
    sort_dir: str = Query("asc"),
    limit: int = Query(100),
    offset: int = Query(0),
):
    conditions, params = [], []
    if search:
        conditions.append("(d.title LIKE ?)")
        params.append(f"%{search}%")
    if status:
        conditions.append("d.status = ?")
        params.append(status)
    if matter_id:
        conditions.append("d.matter_id = ?")
        params.append(matter_id)
    where = "WHERE " + " AND ".join(conditions) if conditions else ""

    total = db.execute(f"SELECT COUNT(*) as c FROM decisions d {where}", params).fetchone()["c"]
    rows = db.execute(f"""
        SELECT d.*, p.full_name as owner_name, m.title as matter_title, m.matter_number
        FROM decisions d
        LEFT JOIN people p ON d.decision_assigned_to_person_id = p.id
        LEFT JOIN matters m ON d.matter_id = m.id
        {where}
        ORDER BY d.decision_due_date ASC NULLS LAST
        LIMIT ? OFFSET ?
    """, params + [limit, offset]).fetchall()
    return {"items": [dict(row) for row in rows], "total": total, "limit": limit, "offset": offset}


@router.post("")
async def create_decision(body: CreateDecision, db=Depends(get_db)):
    did = str(uuid.uuid4())
    now = datetime.now().isoformat()
    db.execute("""
        INSERT INTO decisions (id, matter_id, title, decision_type, status,
            decision_assigned_to_person_id, decision_due_date, options_summary,
            recommended_option, notes, source, source_id, ai_confidence,
            automation_hold, external_refs, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (did, body.matter_id, body.title, body.decision_type,
          body.status, body.decision_assigned_to_person_id,
          body.decision_due_date, body.options_summary,
          body.recommended_option, body.notes,
          body.source, body.source_id,
          body.ai_confidence, body.automation_hold,
          body.external_refs, now, now))
    db.commit()
    return {"id": did}


@router.put("/{decision_id}")
async def update_decision(decision_id: str, body: UpdateDecision, db=Depends(get_db)):
    existing = db.execute("SELECT id FROM decisions WHERE id = ?", (decision_id,)).fetchone()
    if not existing:
        raise HTTPException(status_code=404, detail="Decision not found")
    data = body.model_dump(exclude_unset=True)
    if not data:
        raise HTTPException(status_code=400, detail="No fields to update")
    sets = [f"{k} = ?" for k in data]
    params = list(data.values())
    now = datetime.now().isoformat()
    sets.append("updated_at = ?")
    params.extend([now, decision_id])
    db.execute(f"UPDATE decisions SET {', '.join(sets)} WHERE id = ?", params)
    db.commit()
    return {"id": decision_id, "updated": True}


@router.get("/{decision_id}")
async def get_decision(decision_id: str, db=Depends(get_db)):
    """Get a single decision by ID."""
    row = db.execute("""
        SELECT d.*, p.full_name as owner_name, m.title as matter_title, m.matter_number
        FROM decisions d
        LEFT JOIN people p ON d.decision_assigned_to_person_id = p.id
        LEFT JOIN matters m ON d.matter_id = m.id
        WHERE d.id = ?
    """, (decision_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Decision not found")
    return dict(row)


@router.delete("/{decision_id}")
async def delete_decision(decision_id: str, db=Depends(get_db)):
    """Delete a decision."""
    existing = db.execute("SELECT id FROM decisions WHERE id = ?", (decision_id,)).fetchone()
    if not existing:
        raise HTTPException(status_code=404, detail="Decision not found")
    db.execute("DELETE FROM decisions WHERE id = ?", (decision_id,))
    db.commit()
    return {"id": decision_id, "deleted": True}
