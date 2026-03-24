"""Policy Directives CRUD endpoints.

Tracks formal external mandates directed at the CFTC.
Manual-only — not in AI_WRITABLE_TABLES.
"""
import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from app.db import get_db
from app.validators import CreatePolicyDirective, UpdatePolicyDirective
from app.deps import get_write_source
from app.audit import log_event
from app.concurrency import get_etag, check_etag
from app.idempotency import claim_idempotency_key, finalize_idempotency_key
import json

router = APIRouter(prefix="/policy-directives", tags=["policy_directives"])


@router.get("")
async def list_policy_directives(
    db=Depends(get_db),
    search: str = Query(None),
    source_document_type: str = Query(None),
    implementation_status: str = Query(None),
    responsible_entity: str = Query(None),
    ogc_role: str = Query(None),
    priority_tier: str = Query(None),
    assigned_to_person_id: str = Query(None),
    sort_by: str = Query("sort_order"),
    sort_dir: str = Query("asc"),
    limit: int = Query(100, le=500),
    offset: int = Query(0),
):
    conditions, params = [], []
    if search:
        conditions.append("(pd.directive_label LIKE ? OR pd.source_document LIKE ?)")
        params.extend([f"%{search}%", f"%{search}%"])
    if source_document_type:
        conditions.append("pd.source_document_type = ?")
        params.append(source_document_type)
    if implementation_status:
        conditions.append("pd.implementation_status = ?")
        params.append(implementation_status)
    if responsible_entity:
        conditions.append("pd.responsible_entity = ?")
        params.append(responsible_entity)
    if ogc_role:
        conditions.append("pd.ogc_role = ?")
        params.append(ogc_role)
    if priority_tier:
        conditions.append("pd.priority_tier = ?")
        params.append(priority_tier)
    if assigned_to_person_id:
        conditions.append("pd.assigned_to_person_id = ?")
        params.append(assigned_to_person_id)
    where = "WHERE " + " AND ".join(conditions) if conditions else ""

    allowed_sort = {
        "sort_order": "pd.sort_order",
        "directive_label": "pd.directive_label",
        "source_document": "pd.source_document",
        "implementation_status": "pd.implementation_status",
        "priority_tier": "pd.priority_tier",
        "target_date": "pd.target_date",
        "source_date": "pd.source_date",
        "created_at": "pd.created_at",
    }
    order_col = allowed_sort.get(sort_by, "pd.sort_order")
    direction = "DESC" if sort_dir.lower() == "desc" else "ASC"

    total = db.execute(f"SELECT COUNT(*) as c FROM policy_directives pd {where}", params).fetchone()["c"]
    rows = db.execute(f"""
        SELECT pd.*,
               p.full_name as assigned_to_name,
               (SELECT COUNT(*) FROM directive_matters dm WHERE dm.directive_id = pd.id) as linked_matter_count
        FROM policy_directives pd
        LEFT JOIN people p ON pd.assigned_to_person_id = p.id
        {where}
        ORDER BY {order_col} {direction} NULLS LAST
        LIMIT ? OFFSET ?
    """, params + [limit, offset]).fetchall()
    return {"items": [dict(row) for row in rows], "total": total, "limit": limit, "offset": offset}


@router.post("")
async def create_policy_directive(
    body: CreatePolicyDirective,
    request: Request,
    db=Depends(get_db),
    write_source: str = Depends(get_write_source),
):
    idem_key = request.headers.get("idempotency-key")
    cached = claim_idempotency_key(db, idem_key, body.model_dump(), "/tracker/policy-directives")
    if cached == "conflict":
        raise HTTPException(409, detail="Idempotency key reused with different payload")
    if cached == "pending":
        raise HTTPException(409, detail="Request with this idempotency key is still in progress")
    if isinstance(cached, dict):
        return JSONResponse(status_code=cached["status_code"], content=json.loads(cached["body"]))

    did = str(uuid.uuid4())
    now = datetime.now().isoformat()
    source_val = write_source if body.source == "manual" else body.source

    db.execute("""
        INSERT INTO policy_directives (
            id, source_document, source_document_type, source_document_url,
            source_date, directive_label, directive_text, section_reference,
            chapter, priority_tier, responsible_entity, ogc_role,
            assigned_to_person_id, implementation_status, implementation_notes,
            target_date, completed_date, notes, sort_order,
            source, source_id, external_refs,
            created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (did, body.source_document, body.source_document_type,
          body.source_document_url, body.source_date,
          body.directive_label, body.directive_text, body.section_reference,
          body.chapter, body.priority_tier, body.responsible_entity,
          body.ogc_role, body.assigned_to_person_id,
          body.implementation_status, body.implementation_notes,
          body.target_date, body.completed_date, body.notes, body.sort_order,
          source_val, body.source_id, body.external_refs,
          now, now))

    new_data = body.model_dump()
    new_data.update({"id": did, "source": source_val, "created_at": now, "updated_at": now})
    log_event(db, table_name="policy_directives", record_id=did, action="create",
              source=write_source, new_data=new_data)

    result = {"id": did}
    finalize_idempotency_key(db, idem_key, 200, result)
    db.commit()
    return result


@router.get("/{directive_id}")
async def get_policy_directive(directive_id: str, db=Depends(get_db)):
    """Get a directive with linked matters."""
    row = db.execute("""
        SELECT pd.*, p.full_name as assigned_to_name
        FROM policy_directives pd
        LEFT JOIN people p ON pd.assigned_to_person_id = p.id
        WHERE pd.id = ?
    """, (directive_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Policy directive not found")

    directive = dict(row)

    # Fetch linked matters
    links = db.execute("""
        SELECT dm.*, m.title as matter_title, m.matter_number, m.status as matter_status
        FROM directive_matters dm
        JOIN matters m ON dm.matter_id = m.id
        WHERE dm.directive_id = ?
        ORDER BY dm.created_at ASC
    """, (directive_id,)).fetchall()
    directive["linked_matters"] = [dict(lnk) for lnk in links]

    return JSONResponse(content=directive, headers={"ETag": get_etag(row)})


@router.put("/{directive_id}")
async def update_policy_directive(
    directive_id: str,
    body: UpdatePolicyDirective,
    request: Request,
    db=Depends(get_db),
    write_source: str = Depends(get_write_source),
):
    old = db.execute("SELECT * FROM policy_directives WHERE id = ?", (directive_id,)).fetchone()
    if not old:
        raise HTTPException(status_code=404, detail="Policy directive not found")
    check_etag(request, old)

    data = body.model_dump(exclude_unset=True)
    if not data:
        raise HTTPException(status_code=400, detail="No fields to update")

    sets = [f"{k} = ?" for k in data]
    params = list(data.values())
    now = datetime.now().isoformat()
    sets.append("updated_at = ?")
    params.extend([now, directive_id])

    db.execute(f"UPDATE policy_directives SET {', '.join(sets)} WHERE id = ?", params)
    log_event(db, table_name="policy_directives", record_id=directive_id, action="update",
              source=write_source, old_record=old, new_data=data)
    db.commit()
    return {"id": directive_id, "updated": True}


@router.delete("/{directive_id}")
async def delete_policy_directive(
    directive_id: str,
    request: Request,
    db=Depends(get_db),
    write_source: str = Depends(get_write_source),
):
    """Delete a directive and its matter links."""
    old = db.execute("SELECT * FROM policy_directives WHERE id = ?", (directive_id,)).fetchone()
    if not old:
        raise HTTPException(status_code=404, detail="Policy directive not found")
    check_etag(request, old)

    # Cascade delete links
    link_count = db.execute(
        "SELECT COUNT(*) as c FROM directive_matters WHERE directive_id = ?",
        (directive_id,)
    ).fetchone()["c"]
    db.execute("DELETE FROM directive_matters WHERE directive_id = ?", (directive_id,))
    db.execute("DELETE FROM policy_directives WHERE id = ?", (directive_id,))

    log_event(db, table_name="policy_directives", record_id=directive_id, action="delete",
              source=write_source, old_record=old,
              new_data={"cascade_deleted_links": link_count})
    db.commit()
    return {"id": directive_id, "deleted": True, "links_deleted": link_count}
