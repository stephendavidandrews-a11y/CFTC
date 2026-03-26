"""Decision CRUD endpoints."""

import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from app.db import get_db
from app.validators import CreateDecision, UpdateDecision
import json
from fastapi import Request
from fastapi.responses import JSONResponse
from app.deps import get_write_source
from app.audit import log_event
from app.concurrency import get_etag, check_etag
from app.idempotency import claim_idempotency_key, finalize_idempotency_key

router = APIRouter(prefix="/decisions", tags=["decisions"])


@router.get("")
async def list_decisions(
    db=Depends(get_db),
    search: str = Query(None),
    status: str = Query(None),
    matter_id: str = Query(None),
    sort_by: str = Query("decision_due_date"),
    sort_dir: str = Query("asc"),
    limit: int = Query(100, le=500),
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

    total = db.execute(
        f"SELECT COUNT(*) as c FROM decisions d {where}", params
    ).fetchone()["c"]
    rows = db.execute(
        f"""
        SELECT d.*, p.full_name as owner_name, m.title as matter_title, m.matter_number
        FROM decisions d
        LEFT JOIN people p ON d.decision_assigned_to_person_id = p.id
        LEFT JOIN matters m ON d.matter_id = m.id
        {where}
        ORDER BY d.decision_due_date ASC NULLS LAST
        LIMIT ? OFFSET ?
    """,
        params + [limit, offset],
    ).fetchall()
    return {
        "items": [dict(row) for row in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.post("")
async def create_decision(
    body: CreateDecision,
    request: Request,
    db=Depends(get_db),
    write_source: str = Depends(get_write_source),
):
    idem_key = request.headers.get("idempotency-key")
    cached = claim_idempotency_key(
        db, idem_key, body.model_dump(), "/tracker/decisions"
    )
    if cached == "conflict":
        raise HTTPException(409, detail="Idempotency key reused with different payload")
    if cached == "pending":
        raise HTTPException(
            409, detail="Request with this idempotency key is still in progress"
        )
    if isinstance(cached, dict):
        return JSONResponse(
            status_code=cached["status_code"], content=json.loads(cached["body"])
        )
    did = str(uuid.uuid4())
    now = datetime.now().isoformat()
    source_val = write_source if body.source == "manual" else body.source
    db.execute(
        """
        INSERT INTO decisions (id, matter_id, title, decision_type, status,
            decision_assigned_to_person_id, decision_due_date, options_summary,
            recommended_option, decision_result, made_at, notes, source, source_id,
            ai_confidence, automation_hold, external_refs, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """,
        (
            did,
            body.matter_id,
            body.title,
            body.decision_type,
            body.status,
            body.decision_assigned_to_person_id,
            body.decision_due_date,
            body.options_summary,
            body.recommended_option,
            body.decision_result,
            body.made_at,
            body.notes,
            source_val,
            body.source_id,
            body.ai_confidence,
            body.automation_hold,
            body.external_refs,
            now,
            now,
        ),
    )
    new_data = body.model_dump()
    new_data.update(
        {
            "id": did,
            "source": source_val,
            "created_at": now,
            "updated_at": now,
            "made_at": body.made_at,
            "decision_result": body.decision_result,
        }
    )
    log_event(
        db,
        table_name="decisions",
        record_id=did,
        action="create",
        source=write_source,
        new_data=new_data,
    )
    result = {"id": did}
    finalize_idempotency_key(db, idem_key, 200, result)
    db.commit()
    return result


@router.put("/{decision_id}")
async def update_decision(
    decision_id: str,
    body: UpdateDecision,
    request: Request,
    db=Depends(get_db),
    write_source: str = Depends(get_write_source),
):
    old = db.execute("SELECT * FROM decisions WHERE id = ?", (decision_id,)).fetchone()
    if not old:
        raise HTTPException(status_code=404, detail="Decision not found")
    check_etag(request, old)
    data = body.model_dump(exclude_unset=True)
    if not data:
        raise HTTPException(status_code=400, detail="No fields to update")
    sets = [f"{k} = ?" for k in data]
    params = list(data.values())
    now = datetime.now().isoformat()
    sets.append("updated_at = ?")
    params.extend([now, decision_id])
    db.execute(f"UPDATE decisions SET {', '.join(sets)} WHERE id = ?", params)
    log_event(
        db,
        table_name="decisions",
        record_id=decision_id,
        action="update",
        source=write_source,
        old_record=old,
        new_data=data,
    )
    db.commit()
    return {"id": decision_id, "updated": True}


@router.get("/{decision_id}")
async def get_decision(decision_id: str, db=Depends(get_db)):
    """Get a single decision by ID."""
    row = db.execute(
        """
        SELECT d.*, p.full_name as owner_name, m.title as matter_title, m.matter_number
        FROM decisions d
        LEFT JOIN people p ON d.decision_assigned_to_person_id = p.id
        LEFT JOIN matters m ON d.matter_id = m.id
        WHERE d.id = ?
    """,
        (decision_id,),
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Decision not found")
    return JSONResponse(content=dict(row), headers={"ETag": get_etag(row)})


@router.delete("/{decision_id}")
async def delete_decision(
    decision_id: str,
    request: Request,
    db=Depends(get_db),
    write_source: str = Depends(get_write_source),
):
    """Delete a decision."""
    old = db.execute("SELECT * FROM decisions WHERE id = ?", (decision_id,)).fetchone()
    if not old:
        raise HTTPException(status_code=404, detail="Decision not found")
    check_etag(request, old)
    db.execute("DELETE FROM decisions WHERE id = ?", (decision_id,))
    log_event(
        db,
        table_name="decisions",
        record_id=decision_id,
        action="delete",
        source=write_source,
        old_record=old,
    )
    db.commit()
    return {"id": decision_id, "deleted": True}
