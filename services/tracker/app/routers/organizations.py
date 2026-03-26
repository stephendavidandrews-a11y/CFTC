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
    is_active: bool = Query(None),
    sort_by: str = Query("name"),
    sort_dir: str = Query("asc"),
    limit: int = Query(100, le=500),
    offset: int = Query(0),
):
    conditions = []
    params = []
    if is_active is not None:
        conditions.append("o.is_active = ?")
        params.append(1 if is_active else 0)
    if search:
        conditions.append(
            "(o.name LIKE ? OR o.short_name LIKE ? OR o.jurisdiction LIKE ? OR o.notes LIKE ?)"
        )
        params.extend([f"%{search}%"] * 4)
    if organization_type:
        conditions.append("o.organization_type = ?")
        params.append(organization_type)

    where = "WHERE " + " AND ".join(conditions) if conditions else ""
    allowed_sorts = {"name", "organization_type", "created_at"}
    if sort_by not in allowed_sorts:
        sort_by = "name"
    direction = "DESC" if sort_dir.lower() == "desc" else "ASC"

    allowed_sorts = allowed_sorts | {"active_matters", "people_count"}
    total = db.execute(
        f"SELECT COUNT(*) as c FROM organizations o {where}", params
    ).fetchone()["c"]
    rows = db.execute(
        f"""
        SELECT o.*, po.name as parent_org_name,
            (SELECT COUNT(*) FROM matter_organizations mo
             JOIN matters m ON mo.matter_id = m.id
             WHERE mo.organization_id = o.id AND m.status != 'closed') AS active_matters,
            (SELECT COUNT(*) FROM people p
             WHERE p.organization_id = o.id AND p.is_active = 1) AS people_count
        FROM organizations o
        LEFT JOIN organizations po ON o.parent_organization_id = po.id
        {where}
        ORDER BY {"active_matters" if sort_by == "active_matters" else "people_count" if sort_by == "people_count" else "o." + sort_by} {direction}
        LIMIT ? OFFSET ?
    """,
        params + [limit, offset],
    ).fetchall()

    items = [dict(row) for row in rows]

    # Compute summary counts by category
    cat_rows = db.execute(
        f"""
        SELECT o.organization_type, COUNT(*) as cnt
        FROM organizations o {where}
        GROUP BY o.organization_type
    """,
        params,
    ).fetchall()
    cat_map = {r["organization_type"]: r["cnt"] for r in cat_rows}
    cftc_types = {"CFTC office", "CFTC division", "Commissioner office"}
    federal_types = {"Federal agency", "White House / OMB"}
    external_types = {
        "Exchange",
        "Clearinghouse",
        "Trade association",
        "Regulated entity",
        "Outside counsel",
    }
    congressional_types = {"Congressional office"}
    summary = {
        "total_active": total,
        "cftc_internal": sum(cat_map.get(t, 0) for t in cftc_types),
        "federal_interagency": sum(cat_map.get(t, 0) for t in federal_types),
        "external": sum(cat_map.get(t, 0) for t in external_types),
        "congressional": sum(cat_map.get(t, 0) for t in congressional_types),
    }

    return {
        "items": items,
        "total": total,
        "limit": limit,
        "offset": offset,
        "summary": summary,
    }


@router.get("/{org_id}")
async def get_organization(org_id: str, db=Depends(get_db)):
    row = db.execute(
        """
        SELECT o.*, po.name as parent_org_name
        FROM organizations o
        LEFT JOIN organizations po ON o.parent_organization_id = po.id
        WHERE o.id = ?
    """,
        (org_id,),
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Organization not found")

    result = dict(row)
    # Key people (expanded fields for detail page)
    result["people"] = [
        dict(r)
        for r in db.execute(
            """
        SELECT id, full_name, title, email, relationship_category,
               last_interaction_date, next_interaction_needed_date
        FROM people WHERE organization_id = ? AND is_active = 1
        ORDER BY full_name
    """,
            (org_id,),
        )
    ]
    # Active matters (expanded for detail page)
    result["matters"] = [
        dict(r)
        for r in db.execute(
            """
        SELECT DISTINCT m.id, m.title, m.matter_number, m.status, m.priority,
               m.next_step, mo.organization_role
        FROM matter_organizations mo
        JOIN matters m ON mo.matter_id = m.id
        WHERE mo.organization_id = ? AND m.status != 'closed'
        ORDER BY m.priority
    """,
            (org_id,),
        )
    ]
    # Child orgs
    result["children"] = [
        dict(r)
        for r in db.execute(
            """
        SELECT id, name, short_name, organization_type
        FROM organizations WHERE parent_organization_id = ? AND is_active = 1
        ORDER BY name
    """,
            (org_id,),
        )
    ]
    # Recent meetings (via participant org or via linked matters)
    result["meetings"] = [
        dict(r)
        for r in db.execute(
            """
        SELECT DISTINCT mtg.id, mtg.title, mtg.date_time_start, mtg.meeting_type
        FROM meetings mtg
        LEFT JOIN meeting_participants mp ON mp.meeting_id = mtg.id
        LEFT JOIN meeting_matters mm ON mm.meeting_id = mtg.id
        LEFT JOIN matter_organizations mo2 ON mo2.matter_id = mm.matter_id
        WHERE mp.organization_id = ? OR mo2.organization_id = ?
        ORDER BY mtg.date_time_start DESC
        LIMIT 10
    """,
            (org_id, org_id),
        )
    ]

    return JSONResponse(content=result, headers={"ETag": get_etag(row)})


@router.post("")
async def create_organization(
    body: CreateOrganization,
    request: Request,
    db=Depends(get_db),
    write_source: str = Depends(get_write_source),
):
    idem_key = request.headers.get("idempotency-key")
    cached = claim_idempotency_key(
        db, idem_key, body.model_dump(), "/tracker/organizations"
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
    oid = str(uuid.uuid4())
    now = datetime.now().isoformat()
    source_val = write_source if body.source == "manual" else body.source
    db.execute(
        """
        INSERT INTO organizations (id, name, short_name, organization_type,
            parent_organization_id, jurisdiction, notes, is_active,
            source, source_id, external_refs, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """,
        (
            oid,
            body.name,
            body.short_name,
            body.organization_type,
            body.parent_organization_id,
            body.jurisdiction,
            body.notes,
            body.is_active,
            source_val,
            body.source_id,
            body.external_refs,
            now,
            now,
        ),
    )
    new_data = body.model_dump()
    new_data.update(
        {"id": oid, "source": source_val, "created_at": now, "updated_at": now}
    )
    log_event(
        db,
        table_name="organizations",
        record_id=oid,
        action="create",
        source=write_source,
        new_data=new_data,
    )
    result = {"id": oid}
    finalize_idempotency_key(db, idem_key, 200, result)
    db.commit()
    return result


@router.put("/{org_id}")
async def update_organization(
    org_id: str,
    body: UpdateOrganization,
    request: Request,
    db=Depends(get_db),
    write_source: str = Depends(get_write_source),
):
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
    log_event(
        db,
        table_name="organizations",
        record_id=org_id,
        action="update",
        source=write_source,
        old_record=old,
        new_data=data,
    )
    db.commit()
    return {"id": org_id, "updated": True}


@router.delete("/{org_id}")
async def delete_organization(
    org_id: str,
    request: Request,
    db=Depends(get_db),
    write_source: str = Depends(get_write_source),
):
    """Soft-delete an organization by setting is_active = 0."""
    old = db.execute("SELECT * FROM organizations WHERE id = ?", (org_id,)).fetchone()
    if not old:
        raise HTTPException(status_code=404, detail="Organization not found")
    check_etag(request, old)
    now = datetime.now().isoformat()
    db.execute(
        "UPDATE organizations SET is_active = 0, updated_at = ? WHERE id = ?",
        (now, org_id),
    )
    log_event(
        db,
        table_name="organizations",
        record_id=org_id,
        action="delete",
        source=write_source,
        old_record=old,
    )
    db.commit()
    return {"id": org_id, "deleted": True}
