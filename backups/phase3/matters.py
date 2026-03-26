"""Matter CRUD endpoints — the core of the tracker."""

import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from app.db import get_db
from app.validators import (
    CreateMatter,
    UpdateMatter,
    AddMatterPerson,
    AddMatterOrg,
    AddMatterUpdate,
)
import json
from fastapi import Request
from fastapi.responses import JSONResponse
from app.deps import get_write_source
from app.audit import log_event
from app.concurrency import get_etag, check_etag
from app.idempotency import claim_idempotency_key, finalize_idempotency_key

router = APIRouter(prefix="/matters", tags=["matters"])


def next_matter_number(db) -> str:
    """Generate MAT-YYYY-NNNN."""
    year = datetime.now().year
    row = db.execute(
        "SELECT COUNT(*) as c FROM matters WHERE matter_number LIKE ?",
        (f"MAT-{year}-%",),
    ).fetchone()
    seq = (row["c"] or 0) + 1
    return f"MAT-{year}-{seq:04d}"


@router.get("")
async def list_matters(
    db=Depends(get_db),
    search: str = Query(None),
    status: str = Query(None),
    priority: str = Query(None),
    matter_type: str = Query(None),
    assigned_to: str = Query(None),
    source: str = Query(None),
    source_id: str = Query(None),
    sort_by: str = Query("updated_at"),
    sort_dir: str = Query("desc"),
    limit: int = Query(100, le=500),
    offset: int = Query(0),
):
    """List matters with optional filters."""
    conditions = []
    params = []

    if search:
        conditions.append(
            "(m.title LIKE ? OR m.matter_number LIKE ? OR m.description LIKE ?)"
        )
        params.extend([f"%{search}%"] * 3)
    if status:
        conditions.append("m.status = ?")
        params.append(status)
    if priority:
        conditions.append("m.priority = ?")
        params.append(priority)
    if matter_type:
        conditions.append("m.matter_type = ?")
        params.append(matter_type)
    if assigned_to:
        conditions.append("m.assigned_to_person_id = ?")
        params.append(assigned_to)
    if source:
        conditions.append("m.source = ?")
        params.append(source)
    if source_id:
        conditions.append("m.source_id = ?")
        params.append(source_id)

    where = "WHERE " + " AND ".join(conditions) if conditions else ""

    # Validate sort column
    allowed_sorts = {
        "title",
        "matter_number",
        "status",
        "priority",
        "matter_type",
        "work_deadline",
        "decision_deadline",
        "external_deadline",
        "updated_at",
        "created_at",
        "opened_date",
        "last_material_update_at",
    }
    if sort_by not in allowed_sorts:
        sort_by = "updated_at"
    sort_direction = "DESC" if sort_dir.lower() == "desc" else "ASC"

    # Count total
    count_row = db.execute(
        f"SELECT COUNT(*) as c FROM matters m {where}", params
    ).fetchone()
    total = count_row["c"]

    # Fetch with joins
    rows = db.execute(
        f"""
        SELECT m.*,
               p.full_name as owner_name,
               nsp.full_name as next_step_owner_name,
               co.name as client_org_name
        FROM matters m
        LEFT JOIN people p ON m.assigned_to_person_id = p.id
        LEFT JOIN people nsp ON m.next_step_assigned_to_person_id = nsp.id
        LEFT JOIN organizations co ON m.client_organization_id = co.id
        {where}
        ORDER BY m.{sort_by} {sort_direction}
        LIMIT ? OFFSET ?
    """,
        params + [limit, offset],
    ).fetchall()

    items = [dict(row) for row in rows]

    # Compute summary counts (always against unfiltered open matters)
    summary_rows = db.execute("""
        SELECT
            COUNT(*) as open_matters,
            SUM(CASE WHEN m.priority = 'critical this week' THEN 1 ELSE 0 END) as critical_this_week,
            SUM(CASE WHEN m.status IN ('awaiting comments', 'awaiting decision') OR m.pending_decision IS NOT NULL AND m.pending_decision != '' THEN 1 ELSE 0 END) as awaiting_decision,
            SUM(CASE WHEN m.updated_at < datetime('now', '-14 days') THEN 1 ELSE 0 END) as stale_matters
        FROM matters m
        WHERE m.status != 'closed'
    """).fetchone()
    summary = {
        "open_matters": summary_rows["open_matters"] or 0,
        "critical_this_week": summary_rows["critical_this_week"] or 0,
        "awaiting_decision": summary_rows["awaiting_decision"] or 0,
        "stale_matters": summary_rows["stale_matters"] or 0,
    }

    return {
        "items": items,
        "total": total,
        "limit": limit,
        "offset": offset,
        "summary": summary,
    }


@router.get("/{matter_id}")
async def get_matter(matter_id: str, db=Depends(get_db)):
    """Get full matter detail with all related data."""
    matter = db.execute(
        """
        SELECT m.*,
               p.full_name as owner_name,
               nsp.full_name as next_step_owner_name,
               sup.full_name as supervisor_name,
               ro.name as requesting_org_name,
               co.name as client_org_name,
               rvo.name as reviewing_org_name,
               leo.name as lead_external_org_name
        FROM matters m
        LEFT JOIN people p ON m.assigned_to_person_id = p.id
        LEFT JOIN people nsp ON m.next_step_assigned_to_person_id = nsp.id
        LEFT JOIN people sup ON m.supervisor_person_id = sup.id
        LEFT JOIN organizations ro ON m.requesting_organization_id = ro.id
        LEFT JOIN organizations co ON m.client_organization_id = co.id
        LEFT JOIN organizations rvo ON m.reviewing_organization_id = rvo.id
        LEFT JOIN organizations leo ON m.lead_external_org_id = leo.id
        WHERE m.id = ?
    """,
        (matter_id,),
    ).fetchone()

    if not matter:
        raise HTTPException(status_code=404, detail="Matter not found")

    result = dict(matter)

    # Stakeholders (matter_people)
    result["stakeholders"] = [
        dict(row)
        for row in db.execute(
            """
        SELECT mp.*, p.full_name, p.title as person_title, o.name as org_name
        FROM matter_people mp
        JOIN people p ON mp.person_id = p.id
        LEFT JOIN organizations o ON p.organization_id = o.id
        WHERE mp.matter_id = ?
        ORDER BY mp.matter_role
    """,
            (matter_id,),
        )
    ]

    # Organizations
    result["organizations"] = [
        dict(row)
        for row in db.execute(
            """
        SELECT mo.*, o.name, o.short_name, o.organization_type
        FROM matter_organizations mo
        JOIN organizations o ON mo.organization_id = o.id
        WHERE mo.matter_id = ?
        ORDER BY mo.organization_role
    """,
            (matter_id,),
        )
    ]

    # Tasks
    result["tasks"] = [
        dict(row)
        for row in db.execute(
            """
        SELECT t.*, p.full_name as owner_name
        FROM tasks t
        LEFT JOIN people p ON t.assigned_to_person_id = p.id
        WHERE t.matter_id = ?
        ORDER BY t.sort_order, t.due_date
    """,
            (matter_id,),
        )
    ]

    # Meetings (via meeting_matters)
    result["meetings"] = [
        dict(row)
        for row in db.execute(
            """
        SELECT mtg.*, mm.relationship_type, mm.decision_made, mm.decision_summary
        FROM meeting_matters mm
        JOIN meetings mtg ON mm.meeting_id = mtg.id
        WHERE mm.matter_id = ?
        ORDER BY mtg.date_time_start DESC
        LIMIT 20
    """,
            (matter_id,),
        )
    ]

    # Documents
    result["documents"] = [
        dict(row)
        for row in db.execute(
            """
        SELECT d.*, p.full_name as owner_name
        FROM documents d
        LEFT JOIN people p ON d.assigned_to_person_id = p.id
        WHERE d.matter_id = ?
        ORDER BY d.updated_at DESC
    """,
            (matter_id,),
        )
    ]

    # Decisions
    result["decisions"] = [
        dict(row)
        for row in db.execute(
            """
        SELECT d.*, p.full_name as owner_name
        FROM decisions d
        LEFT JOIN people p ON d.decision_assigned_to_person_id = p.id
        WHERE d.matter_id = ?
        ORDER BY d.created_at DESC
    """,
            (matter_id,),
        )
    ]

    # Updates
    result["updates"] = [
        dict(row)
        for row in db.execute(
            """
        SELECT mu.*, p.full_name as author_name
        FROM matter_updates mu
        LEFT JOIN people p ON mu.created_by_person_id = p.id
        WHERE mu.matter_id = ?
        ORDER BY mu.created_at DESC
        LIMIT 50
    """,
            (matter_id,),
        )
    ]

    # Dependencies
    result["dependencies"] = [
        dict(row)
        for row in db.execute(
            """
        SELECT md.*, m.title as depends_on_title, m.status as depends_on_status
        FROM matter_dependencies md
        JOIN matters m ON md.depends_on_matter_id = m.id
        WHERE md.matter_id = ?
    """,
            (matter_id,),
        )
    ]

    # Tags
    result["tags"] = [
        dict(row)
        for row in db.execute(
            """
        SELECT t.id, t.name, t.tag_type
        FROM tags t
        JOIN matter_tags mt ON t.id = mt.tag_id
        WHERE mt.matter_id = ?
        ORDER BY t.name
    """,
            (matter_id,),
        )
    ]

    return JSONResponse(content=result, headers={"ETag": get_etag(matter)})


@router.post("")
async def create_matter(
    body: CreateMatter,
    request: Request,
    db=Depends(get_db),
    write_source: str = Depends(get_write_source),
):
    """Create a new matter."""
    idem_key = request.headers.get("idempotency-key")
    cached = claim_idempotency_key(db, idem_key, body.model_dump(), "/tracker/matters")
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
    matter_id = str(uuid.uuid4())
    matter_number = next_matter_number(db)
    now = datetime.now().isoformat()

    source_val = write_source if body.source == "manual" else body.source
    db.execute(
        """
        INSERT INTO matters (
            id, matter_number, title, matter_type, description, problem_statement,
            why_it_matters, status, priority, sensitivity, risk_level,
            boss_involvement_level, assigned_to_person_id, supervisor_person_id,
            requesting_organization_id, client_organization_id,
            reviewing_organization_id, lead_external_org_id,
            opened_date, work_deadline, decision_deadline, external_deadline,
            revisit_date, next_step, next_step_assigned_to_person_id,
            pending_decision, rin, regulatory_stage, federal_register_citation,
            unified_agenda_priority, cfr_citation, docket_number, fr_doc_number,
            source, source_id, ai_confidence, automation_hold, external_refs,
            last_material_update_at, created_by_person_id, created_at, updated_at
        ) VALUES (
            ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?,
            ?, ?, ?,
            ?, ?,
            ?, ?,
            ?, ?, ?, ?,
            ?, ?, ?,
            ?, ?, ?, ?,
            ?, ?, ?, ?,
            ?, ?, ?, ?, ?,
            ?, ?, ?, ?
        )
    """,
        (
            matter_id,
            matter_number,
            body.title,
            body.matter_type,
            body.description,
            body.problem_statement,
            body.why_it_matters,
            body.status,
            body.priority,
            body.sensitivity,
            body.risk_level,
            body.boss_involvement_level,
            body.assigned_to_person_id,
            body.supervisor_person_id,
            body.requesting_organization_id,
            body.client_organization_id,
            body.reviewing_organization_id,
            body.lead_external_org_id,
            body.opened_date or now[:10],
            body.work_deadline,
            body.decision_deadline,
            body.external_deadline,
            body.revisit_date,
            body.next_step,
            body.next_step_assigned_to_person_id,
            body.pending_decision,
            body.rin,
            body.regulatory_stage,
            body.federal_register_citation,
            body.unified_agenda_priority,
            body.cfr_citation,
            body.docket_number,
            body.fr_doc_number,
            source_val,
            body.source_id,
            body.ai_confidence,
            body.automation_hold,
            body.external_refs,
            now,
            body.created_by_person_id,
            now,
            now,
        ),
    )
    new_data = body.model_dump()
    new_data.update(
        {"id": matter_id, "source": source_val, "created_at": now, "updated_at": now}
    )
    log_event(
        db,
        table_name="matters",
        record_id=matter_id,
        action="create",
        source=write_source,
        new_data=new_data,
    )
    result = {"id": matter_id, "matter_number": matter_number}
    finalize_idempotency_key(db, idem_key, 200, result)
    db.commit()

    return result


@router.put("/{matter_id}")
async def update_matter(
    matter_id: str,
    body: UpdateMatter,
    request: Request,
    db=Depends(get_db),
    write_source: str = Depends(get_write_source),
):
    """Update an existing matter."""
    old = db.execute("SELECT * FROM matters WHERE id = ?", (matter_id,)).fetchone()
    if not old:
        raise HTTPException(status_code=404, detail="Matter not found")
    check_etag(request, old)

    data = body.model_dump(exclude_unset=True)
    if not data:
        raise HTTPException(status_code=400, detail="No fields to update")
    sets = [f"{k} = ?" for k in data]
    params = list(data.values())

    sets.append("updated_at = ?")
    sets.append("last_material_update_at = ?")
    now = datetime.now().isoformat()
    params.extend([now, now, matter_id])

    db.execute(f"UPDATE matters SET {', '.join(sets)} WHERE id = ?", params)
    log_event(
        db,
        table_name="matters",
        record_id=matter_id,
        action="update",
        source=write_source,
        old_record=old,
        new_data=data,
    )
    db.commit()

    return {"id": matter_id, "updated": True}


@router.delete("/{matter_id}")
async def delete_matter(
    matter_id: str,
    request: Request,
    db=Depends(get_db),
    write_source: str = Depends(get_write_source),
):
    """Soft-delete a matter by setting status to closed."""
    old = db.execute("SELECT * FROM matters WHERE id = ?", (matter_id,)).fetchone()
    if not old:
        raise HTTPException(status_code=404, detail="Matter not found")
    check_etag(request, old)
    now = datetime.now().isoformat()
    db.execute(
        "UPDATE matters SET status = 'closed', closed_at = ?, updated_at = ? WHERE id = ?",
        (now, now, matter_id),
    )
    log_event(
        db,
        table_name="matters",
        record_id=matter_id,
        action="delete",
        source=write_source,
        old_record=old,
    )
    db.commit()
    return {"id": matter_id, "deleted": True}


# --- Stakeholder sub-routes ---


@router.get("/{matter_id}/people")
async def get_matter_people(matter_id: str, db=Depends(get_db)):
    """Get stakeholders for a matter."""
    rows = db.execute(
        """
        SELECT mp.*, p.full_name, p.title as person_title, p.email,
               o.name as org_name, o.short_name as org_short_name
        FROM matter_people mp
        JOIN people p ON mp.person_id = p.id
        LEFT JOIN organizations o ON p.organization_id = o.id
        WHERE mp.matter_id = ?
        ORDER BY mp.matter_role
    """,
        (matter_id,),
    ).fetchall()
    return [dict(row) for row in rows]


@router.post("/{matter_id}/people")
async def add_matter_person(matter_id: str, body: AddMatterPerson, db=Depends(get_db)):
    """Add a stakeholder to a matter."""
    mp_id = str(uuid.uuid4())
    now = datetime.now().isoformat()
    db.execute(
        """
        INSERT INTO matter_people (id, matter_id, person_id, matter_role, engagement_level, notes, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """,
        (
            mp_id,
            matter_id,
            body.person_id,
            body.matter_role,
            body.engagement_level,
            body.notes,
            now,
            now,
        ),
    )
    db.commit()
    return {"id": mp_id}


@router.delete("/{matter_id}/people/{mp_id}")
async def remove_matter_person(matter_id: str, mp_id: str, db=Depends(get_db)):
    """Remove a stakeholder from a matter."""
    db.execute(
        "DELETE FROM matter_people WHERE id = ? AND matter_id = ?", (mp_id, matter_id)
    )
    db.commit()
    return {"deleted": True}


# --- Organization sub-routes ---


@router.get("/{matter_id}/orgs")
async def get_matter_orgs(matter_id: str, db=Depends(get_db)):
    """Get organizations linked to a matter."""
    rows = db.execute(
        """
        SELECT mo.*, o.name, o.short_name, o.organization_type
        FROM matter_organizations mo
        JOIN organizations o ON mo.organization_id = o.id
        WHERE mo.matter_id = ?
        ORDER BY mo.organization_role
    """,
        (matter_id,),
    ).fetchall()
    return [dict(row) for row in rows]


@router.post("/{matter_id}/orgs")
async def add_matter_org(matter_id: str, body: AddMatterOrg, db=Depends(get_db)):
    """Add an organization to a matter."""
    mo_id = str(uuid.uuid4())
    now = datetime.now().isoformat()
    db.execute(
        """
        INSERT INTO matter_organizations (id, matter_id, organization_id, organization_role, notes, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """,
        (
            mo_id,
            matter_id,
            body.organization_id,
            body.organization_role,
            body.notes,
            now,
            now,
        ),
    )
    db.commit()
    return {"id": mo_id}


@router.delete("/{matter_id}/orgs/{mo_id}")
async def remove_matter_org(matter_id: str, mo_id: str, db=Depends(get_db)):
    """Remove an organization from a matter."""
    db.execute(
        "DELETE FROM matter_organizations WHERE id = ? AND matter_id = ?",
        (mo_id, matter_id),
    )
    db.commit()
    return {"deleted": True}


# --- Updates sub-routes ---


@router.get("/{matter_id}/updates")
async def get_matter_updates(matter_id: str, db=Depends(get_db)):
    """Get update history for a matter."""
    rows = db.execute(
        """
        SELECT mu.*, p.full_name as author_name
        FROM matter_updates mu
        LEFT JOIN people p ON mu.created_by_person_id = p.id
        WHERE mu.matter_id = ?
        ORDER BY mu.created_at DESC
    """,
        (matter_id,),
    ).fetchall()
    return [dict(row) for row in rows]


@router.post("/{matter_id}/updates")
async def add_matter_update(matter_id: str, body: AddMatterUpdate, db=Depends(get_db)):
    """Add an update to a matter."""
    update_id = str(uuid.uuid4())
    now = datetime.now().isoformat()
    db.execute(
        """
        INSERT INTO matter_updates (id, matter_id, update_type, summary, created_by_person_id, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """,
        (
            update_id,
            matter_id,
            body.update_type,
            body.summary,
            body.created_by_person_id,
            now,
        ),
    )
    # Also update the matter's last_material_update_at
    db.execute(
        "UPDATE matters SET last_material_update_at = ?, updated_at = ? WHERE id = ?",
        (now, now, matter_id),
    )
    db.commit()
    return {"id": update_id}


# --- Matter Tags ---


@router.get("/{matter_id}/tags")
async def get_matter_tags(matter_id: str, db=Depends(get_db)):
    """Get tags for a matter."""
    rows = db.execute(
        """
        SELECT t.id, t.name, t.tag_type
        FROM tags t JOIN matter_tags mt ON t.id = mt.tag_id
        WHERE mt.matter_id = ?
        ORDER BY t.name
    """,
        (matter_id,),
    ).fetchall()
    return [dict(r) for r in rows]


@router.post("/{matter_id}/tags")
async def add_matter_tag(matter_id: str, body: dict, db=Depends(get_db)):
    """Add a tag to a matter."""
    tag_id = body.get("tag_id")
    if not tag_id:
        raise HTTPException(status_code=400, detail="tag_id required")
    existing = db.execute(
        "SELECT 1 FROM matter_tags WHERE matter_id = ? AND tag_id = ?",
        (matter_id, tag_id),
    ).fetchone()
    if existing:
        return {"exists": True}
    db.execute(
        "INSERT INTO matter_tags (matter_id, tag_id) VALUES (?, ?)", (matter_id, tag_id)
    )
    db.commit()
    return {"added": True}


@router.delete("/{matter_id}/tags/{tag_id}")
async def remove_matter_tag(matter_id: str, tag_id: str, db=Depends(get_db)):
    """Remove a tag from a matter."""
    db.execute(
        "DELETE FROM matter_tags WHERE matter_id = ? AND tag_id = ?",
        (matter_id, tag_id),
    )
    db.commit()
    return {"deleted": True}


# --- Matter Dependencies ---


@router.post("/{matter_id}/dependencies")
async def add_matter_dependency(matter_id: str, body: dict, db=Depends(get_db)):
    """Add a dependency to a matter."""
    depends_on = body.get("depends_on_matter_id")
    if not depends_on:
        raise HTTPException(status_code=400, detail="depends_on_matter_id required")
    dep_id = str(uuid.uuid4())
    db.execute(
        """
        INSERT INTO matter_dependencies (id, matter_id, depends_on_matter_id, dependency_type, notes)
        VALUES (?, ?, ?, ?, ?)
    """,
        (
            dep_id,
            matter_id,
            depends_on,
            body.get("dependency_type", "sequencing dependency"),
            body.get("notes"),
        ),
    )
    db.commit()
    return {"id": dep_id}


@router.delete("/{matter_id}/dependencies/{dep_id}")
async def remove_matter_dependency(matter_id: str, dep_id: str, db=Depends(get_db)):
    """Remove a dependency from a matter."""
    db.execute(
        "DELETE FROM matter_dependencies WHERE id = ? AND matter_id = ?",
        (dep_id, matter_id),
    )
    db.commit()
    return {"deleted": True}
