"""Organization CRUD endpoints."""
import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from app.db import get_db
from app.validators import CreateOrganization, UpdateOrganization
import json
from fastapi import Request
from fastapi.responses import JSONResponse
from app.deps import get_write_source
from app.audit import log_event
from app.concurrency import get_etag, check_etag
from app.idempotency import claim_idempotency_key, finalize_idempotency_key

router = APIRouter(prefix="/organizations", tags=["organizations"])

@router.get("")
async def list_organizations(
    db=Depends(get_db),
    search: str = Query(None),
    organization_type: str = Query(None),
    parent_id: str = Query(None),
    is_active: bool = Query(True),
    sort_by: str = Query("name"),
    sort_dir: str = Query("asc"),
    limit: int = Query(100, le=500),
    offset: int = Query(0),
):
    conditions = ["o.is_active = ?"]
    params = [1 if is_active else 0]
    if search:
        conditions.append("(o.name LIKE ? OR o.short_name LIKE ?)")
        params.extend([f"%{search}%"] * 2)
    if organization_type:
        conditions.append("o.organization_type = ?")
        params.append(organization_type)
    if parent_id:
        conditions.append("o.parent_organization_id = ?")
        params.append(parent_id)

    where = "WHERE " + " AND ".join(conditions)
    allowed_sorts = {"name", "organization_type", "created_at"}
    if sort_by not in allowed_sorts:
        sort_by = "name"
    direction = "DESC" if sort_dir.lower() == "desc" else "ASC"

    total = db.execute(f"SELECT COUNT(*) as c FROM organizations o {where}", params).fetchone()["c"]
    rows = db.execute(f"""
        SELECT o.*, po.name as parent_org_name
        FROM organizations o
        LEFT JOIN organizations po ON o.parent_organization_id = po.id
        {where}
        ORDER BY o.{sort_by} {direction}
        LIMIT ? OFFSET ?
    """, params + [limit, offset]).fetchall()

    return {"items": [dict(row) for row in rows], "total": total, "limit": limit, "offset": offset}


@router.get("/{org_id}")
async def get_organization(org_id: str, db=Depends(get_db)):
    row = db.execute("""
        SELECT o.*, po.name as parent_org_name
        FROM organizations o
        LEFT JOIN organizations po ON o.parent_organization_id = po.id
        WHERE o.id = ?
    """, (org_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Organization not found")

    result = dict(row)
    # Key people
    result["people"] = [dict(r) for r in db.execute("""
        SELECT id, full_name, title, email, relationship_category
        FROM people WHERE organization_id = ? AND is_active = 1
        ORDER BY full_name
    """, (org_id,))]
    # Active matters
    result["matters"] = [dict(r) for r in db.execute("""
        SELECT DISTINCT m.id, m.title, m.matter_number, m.status, m.priority, mo.organization_role
        FROM matter_organizations mo
        JOIN matters m ON mo.matter_id = m.id
        WHERE mo.organization_id = ? AND m.status != 'closed'
        ORDER BY m.priority
    """, (org_id,))]
    # Child orgs
    result["children"] = [dict(r) for r in db.execute("""
        SELECT id, name, short_name, organization_type
        FROM organizations WHERE parent_organization_id = ? AND is_active = 1
        ORDER BY name
    """, (org_id,))]

    return JSONResponse(content=result, headers={"ETag": get_etag(row)})


@router.post("")
async def create_organization(body: CreateOrganization, request: Request, db=Depends(get_db),
                      write_source: str = Depends(get_write_source)):
    idem_key = request.headers.get("idempotency-key")
    cached = claim_idempotency_key(db, idem_key, body.model_dump(), "/tracker/organizations")
    if cached == "conflict":
        raise HTTPException(409, detail="Idempotency key reused with different payload")
    if cached == "pending":
        raise HTTPException(409, detail="Request with this idempotency key is still in progress")
    if isinstance(cached, dict):
        return JSONResponse(status_code=cached["status_code"], content=json.loads(cached["body"]))
    oid = str(uuid.uuid4())
    now = datetime.now().isoformat()
    source_val = write_source if body.source == "manual" else body.source
    db.execute("""
        INSERT INTO organizations (id, name, short_name, organization_type,
            parent_organization_id, jurisdiction, notes, is_active,
            source, source_id, external_refs, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (oid, body.name, body.short_name, body.organization_type,
          body.parent_organization_id, body.jurisdiction,
          body.notes, body.is_active, source_val, body.source_id,
          body.external_refs, now, now))
    new_data = body.model_dump()
    new_data.update({"id": oid, "source": source_val, "created_at": now, "updated_at": now})
    log_event(db, table_name="organizations", record_id=oid, action="create",
              source=write_source, new_data=new_data)
    result = {"id": oid}
    finalize_idempotency_key(db, idem_key, 200, result)
    db.commit()
    return result


@router.put("/{org_id}")
async def update_organization(org_id: str, body: UpdateOrganization, request: Request, db=Depends(get_db),
                      write_source: str = Depends(get_write_source)):
    old = db.execute("SELECT * FROM organizations WHERE id = ?", (org_id,)).fetchone()
    if not old:
        raise HTTPException(status_code=404, detail="Organization not found")
    check_etag(request, old)
    data = body.model_dump(exclude_unset=True)
    if not data:
        raise HTTPException(status_code=400, detail="No fields to update")
    sets = [f"{k} = ?" for k in data]
    params = list(data.values())
    now = datetime.now().isoformat()
    sets.append("updated_at = ?")
    params.extend([now, org_id])
    db.execute(f"UPDATE organizations SET {', '.join(sets)} WHERE id = ?", params)
    log_event(db, table_name="organizations", record_id=org_id, action="update",
              source=write_source, old_record=old, new_data=data)
    db.commit()
    return {"id": org_id, "updated": True}


@router.delete("/{org_id}")
async def delete_organization(org_id: str, request: Request, db=Depends(get_db),
                      write_source: str = Depends(get_write_source)):
    """Soft-delete an organization by setting is_active = 0."""
    old = db.execute("SELECT * FROM organizations WHERE id = ?", (org_id,)).fetchone()
    if not old:
        raise HTTPException(status_code=404, detail="Organization not found")
    check_etag(request, old)
    now = datetime.now().isoformat()
    db.execute(
        "UPDATE organizations SET is_active = 0, updated_at = ? WHERE id = ?",
        (now, org_id)
    )
    log_event(db, table_name="organizations", record_id=org_id, action="delete",
              source=write_source, old_record=old)
    db.commit()
    return {"id": org_id, "deleted": True}
