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
    CreateMatterRulemaking,
    UpdateMatterRulemaking,
    CreateMatterGuidance,
    UpdateMatterGuidance,
    CreateMatterEnforcement,
    UpdateMatterEnforcement,
    CreateMatterRegulatoryId,
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
    """Generate MAT-YYYY-NNNN using atomic sequence table."""
    year = datetime.now().year
    row = db.execute(
        "UPDATE matter_number_seq SET next_val = next_val + 1 WHERE prefix = 'MAT' AND year = ? RETURNING next_val",
        (year,),
    ).fetchone()
    if row:
        seq = row[0] - 1  # RETURNING gives post-increment value
    else:
        db.execute(
            "INSERT INTO matter_number_seq (prefix, year, next_val) VALUES ('MAT', ?, 2)",
            (year,),
        )
        seq = 1
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

    # Fetch with joins (including extension tables for workflow_status and comment period)
    rows = db.execute(
        f"""
        SELECT m.*,
               p.full_name as owner_name,
               co.name as client_org_name,
               COALESCE(mr.workflow_status, mg.workflow_status, me.workflow_status) AS workflow_status,
               mr.current_comment_period_closes,
               CASE
                   WHEN mr.current_comment_period_closes IS NULL THEN NULL
                   WHEN mr.current_comment_period_closes >= date('now') THEN 'open'
                   ELSE 'closed'
               END AS comment_period_status
        FROM matters m
        LEFT JOIN people p ON m.assigned_to_person_id = p.id
        LEFT JOIN organizations co ON m.client_organization_id = co.id
        LEFT JOIN matter_rulemaking mr ON m.id = mr.matter_id
        LEFT JOIN matter_guidance mg ON m.id = mg.matter_id
        LEFT JOIN matter_enforcement me ON m.id = me.matter_id
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
            SUM(CASE WHEN m.blocker IS NOT NULL AND m.blocker != '' THEN 1 ELSE 0 END) as blocked_matters,
            SUM(CASE WHEN m.updated_at < datetime('now', '-14 days') THEN 1 ELSE 0 END) as stale_matters
        FROM matters m
        WHERE m.status IN ('active', 'paused')
    """).fetchone()
    summary = {
        "open_matters": summary_rows["open_matters"] or 0,
        "critical_this_week": summary_rows["critical_this_week"] or 0,
        "blocked_matters": summary_rows["blocked_matters"] or 0,
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
               co.name as client_org_name,
               cb.full_name as created_by_name
        FROM matters m
        LEFT JOIN people p ON m.assigned_to_person_id = p.id
        LEFT JOIN organizations co ON m.client_organization_id = co.id
        LEFT JOIN people cb ON m.created_by_person_id = cb.id
        WHERE m.id = ?
    """,
        (matter_id,),
    ).fetchone()

    if not matter:
        raise HTTPException(status_code=404, detail="Matter not found")

    result = dict(matter)

    # Extension data based on matter_type
    ext = None
    mt = matter["matter_type"]
    if mt == "rulemaking":
        ext = db.execute("SELECT * FROM matter_rulemaking WHERE matter_id = ?", (matter_id,)).fetchone()
    elif mt == "guidance":
        ext = db.execute("SELECT * FROM matter_guidance WHERE matter_id = ?", (matter_id,)).fetchone()
    elif mt == "enforcement":
        ext = db.execute("SELECT * FROM matter_enforcement WHERE matter_id = ?", (matter_id,)).fetchone()
    result["extension"] = dict(ext) if ext else None

    # Regulatory IDs
    reg_ids = db.execute(
        "SELECT * FROM matter_regulatory_ids WHERE matter_id = ? ORDER BY created_at",
        (matter_id,),
    ).fetchall()
    result["regulatory_ids"] = [dict(r) for r in reg_ids]

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
            id, matter_number, title, matter_type, description,
            status, priority, sensitivity,
            assigned_to_person_id, client_organization_id,
            opened_date, work_deadline, external_deadline,
            next_step, outcome_summary, blocker,
            source, source_id, ai_confidence, automation_hold, external_refs,
            last_material_update_at, created_by_person_id, created_at, updated_at
        ) VALUES (
            ?, ?, ?, ?, ?,
            ?, ?, ?,
            ?, ?,
            ?, ?, ?,
            ?, ?, ?,
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
            body.status,
            body.priority,
            body.sensitivity,
            body.assigned_to_person_id,
            body.client_organization_id,
            body.opened_date or now[:10],
            body.work_deadline,
            body.external_deadline,
            body.next_step,
            body.outcome_summary,
            body.blocker,
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
    # Insert extension row if applicable
    raw_body = await request.json() if hasattr(request, '_body') else {}
    # Re-parse raw body for extension fields
    try:
        raw_body = json.loads(await request.body())
    except Exception:
        raw_body = {}
    ext_data = raw_body.get("extension", {})
    if ext_data and isinstance(ext_data, dict):
        ext_id = str(uuid.uuid4())
        if body.matter_type == "rulemaking":
            ext_model = CreateMatterRulemaking(**ext_data)
            cols = ext_model.model_dump()
            cols["id"] = ext_id
            cols["matter_id"] = matter_id
            col_names = ", ".join(cols.keys())
            placeholders = ", ".join("?" * len(cols))
            db.execute(f"INSERT INTO matter_rulemaking ({col_names}) VALUES ({placeholders})", list(cols.values()))
        elif body.matter_type == "guidance":
            ext_model = CreateMatterGuidance(**ext_data)
            cols = ext_model.model_dump()
            cols["id"] = ext_id
            cols["matter_id"] = matter_id
            col_names = ", ".join(cols.keys())
            placeholders = ", ".join("?" * len(cols))
            db.execute(f"INSERT INTO matter_guidance ({col_names}) VALUES ({placeholders})", list(cols.values()))
        elif body.matter_type == "enforcement":
            ext_model = CreateMatterEnforcement(**ext_data)
            cols = ext_model.model_dump()
            cols["id"] = ext_id
            cols["matter_id"] = matter_id
            col_names = ", ".join(cols.keys())
            placeholders = ", ".join("?" * len(cols))
            db.execute(f"INSERT INTO matter_enforcement ({col_names}) VALUES ({placeholders})", list(cols.values()))

    new_data = body.model_dump()
    new_data.update(
        {"id": matter_id, "source": source_val, "created_at": now, "updated_at": now}
    )
    if ext_data:
        new_data["extension"] = ext_data
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

    # Parse extension fields from raw body
    try:
        raw_body = json.loads(await request.body())
    except Exception:
        raw_body = {}
    ext_data = raw_body.get("extension", {})

    if not data and not ext_data:
        raise HTTPException(status_code=400, detail="No fields to update")

    now = datetime.now().isoformat()

    # Update base matter fields if any
    if data:
        sets = [f"{k} = ?" for k in data]
        params = list(data.values())
        sets.append("updated_at = ?")
        sets.append("last_material_update_at = ?")
        params.extend([now, now, matter_id])
        db.execute(f"UPDATE matters SET {', '.join(sets)} WHERE id = ?", params)

    # Update extension table if applicable
    if ext_data and isinstance(ext_data, dict):
        mt = old["matter_type"]
        if mt == "rulemaking":
            ext_model = UpdateMatterRulemaking(**ext_data)
            ext_fields = ext_model.model_dump(exclude_unset=True)
            if ext_fields:
                existing = db.execute("SELECT matter_id FROM matter_rulemaking WHERE matter_id = ?", (matter_id,)).fetchone()
                if existing:
                    ext_sets = [f"{k} = ?" for k in ext_fields]
                    ext_params = list(ext_fields.values()) + [matter_id]
                    db.execute(f"UPDATE matter_rulemaking SET {', '.join(ext_sets)} WHERE matter_id = ?", ext_params)
                else:
                    ext_fields["id"] = str(uuid.uuid4())
                    ext_fields["matter_id"] = matter_id
                    col_names = ", ".join(ext_fields.keys())
                    placeholders = ", ".join("?" * len(ext_fields))
                    db.execute(f"INSERT INTO matter_rulemaking ({col_names}) VALUES ({placeholders})", list(ext_fields.values()))
        elif mt == "guidance":
            ext_model = UpdateMatterGuidance(**ext_data)
            ext_fields = ext_model.model_dump(exclude_unset=True)
            if ext_fields:
                existing = db.execute("SELECT matter_id FROM matter_guidance WHERE matter_id = ?", (matter_id,)).fetchone()
                if existing:
                    ext_sets = [f"{k} = ?" for k in ext_fields]
                    ext_params = list(ext_fields.values()) + [matter_id]
                    db.execute(f"UPDATE matter_guidance SET {', '.join(ext_sets)} WHERE matter_id = ?", ext_params)
                else:
                    ext_fields["id"] = str(uuid.uuid4())
                    ext_fields["matter_id"] = matter_id
                    col_names = ", ".join(ext_fields.keys())
                    placeholders = ", ".join("?" * len(ext_fields))
                    db.execute(f"INSERT INTO matter_guidance ({col_names}) VALUES ({placeholders})", list(ext_fields.values()))
        elif mt == "enforcement":
            ext_model = UpdateMatterEnforcement(**ext_data)
            ext_fields = ext_model.model_dump(exclude_unset=True)
            if ext_fields:
                existing = db.execute("SELECT matter_id FROM matter_enforcement WHERE matter_id = ?", (matter_id,)).fetchone()
                if existing:
                    ext_sets = [f"{k} = ?" for k in ext_fields]
                    ext_params = list(ext_fields.values()) + [matter_id]
                    db.execute(f"UPDATE matter_enforcement SET {', '.join(ext_sets)} WHERE matter_id = ?", ext_params)
                else:
                    ext_fields["id"] = str(uuid.uuid4())
                    ext_fields["matter_id"] = matter_id
                    col_names = ", ".join(ext_fields.keys())
                    placeholders = ", ".join("?" * len(ext_fields))
                    db.execute(f"INSERT INTO matter_enforcement ({col_names}) VALUES ({placeholders})", list(ext_fields.values()))

    log_event(
        db,
        table_name="matters",
        record_id=matter_id,
        action="update",
        source=write_source,
        old_record=old,
        new_data={**data, **({"extension": ext_data} if ext_data else {})},
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


# --- Regulatory IDs ---


@router.get("/{matter_id}/regulatory-ids")
async def get_matter_regulatory_ids(matter_id: str, db=Depends(get_db)):
    """List regulatory IDs linked to a matter."""
    rows = db.execute(
        "SELECT * FROM matter_regulatory_ids WHERE matter_id = ? ORDER BY created_at",
        (matter_id,),
    ).fetchall()
    return [dict(r) for r in rows]


@router.post("/{matter_id}/regulatory-ids")
async def add_matter_regulatory_id(
    matter_id: str, body: CreateMatterRegulatoryId, db=Depends(get_db)
):
    """Create a regulatory ID link for a matter."""
    rid = str(uuid.uuid4())
    now = datetime.now().isoformat()
    db.execute(
        """
        INSERT INTO matter_regulatory_ids (id, matter_id, id_type, id_value, relationship, notes, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """,
        (rid, matter_id, body.id_type, body.id_value, body.relationship, body.notes, now),
    )
    db.commit()
    return {"id": rid}


@router.delete("/{matter_id}/regulatory-ids/{rid}")
async def remove_matter_regulatory_id(matter_id: str, rid: str, db=Depends(get_db)):
    """Remove a regulatory ID from a matter."""
    db.execute(
        "DELETE FROM matter_regulatory_ids WHERE id = ? AND matter_id = ?",
        (rid, matter_id),
    )
    db.commit()
    return {"deleted": True}
