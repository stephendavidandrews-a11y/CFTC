"""Directive-Matter link/unlink endpoints.

Join table for many-to-many between policy_directives and matters.
"""
import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Request
from app.db import get_db
from app.validators import CreateDirectiveMatter
from app.deps import get_write_source
from app.audit import log_event

router = APIRouter(tags=["directive_matters"])


@router.get("/policy-directives/{directive_id}/matters")
async def list_directive_matters(directive_id: str, db=Depends(get_db)):
    """List matters linked to a directive."""
    directive = db.execute("SELECT id FROM policy_directives WHERE id = ?", (directive_id,)).fetchone()
    if not directive:
        raise HTTPException(status_code=404, detail="Policy directive not found")

    rows = db.execute("""
        SELECT dm.*, m.title as matter_title, m.matter_number,
               m.status as matter_status, m.matter_type, m.priority as matter_priority
        FROM directive_matters dm
        JOIN matters m ON dm.matter_id = m.id
        WHERE dm.directive_id = ?
        ORDER BY dm.created_at ASC
    """, (directive_id,)).fetchall()
    return {"items": [dict(row) for row in rows], "total": len(rows)}


@router.get("/matters/{matter_id}/directives")
async def list_matter_directives(matter_id: str, db=Depends(get_db)):
    """List directives linked to a matter (reverse lookup)."""
    matter = db.execute("SELECT id FROM matters WHERE id = ?", (matter_id,)).fetchone()
    if not matter:
        raise HTTPException(status_code=404, detail="Matter not found")

    rows = db.execute("""
        SELECT dm.*, pd.directive_label, pd.source_document,
               pd.implementation_status, pd.priority_tier, pd.responsible_entity
        FROM directive_matters dm
        JOIN policy_directives pd ON dm.directive_id = pd.id
        WHERE dm.matter_id = ?
        ORDER BY dm.created_at ASC
    """, (matter_id,)).fetchall()
    return {"items": [dict(row) for row in rows], "total": len(rows)}


@router.post("/directive-matters")
async def create_directive_matter(
    body: CreateDirectiveMatter,
    request: Request,
    db=Depends(get_db),
    write_source: str = Depends(get_write_source),
):
    """Link a directive to a matter."""
    # Verify both sides exist
    directive = db.execute("SELECT id FROM policy_directives WHERE id = ?",
                           (body.directive_id,)).fetchone()
    if not directive:
        raise HTTPException(status_code=404, detail="Policy directive not found")
    matter = db.execute("SELECT id FROM matters WHERE id = ?", (body.matter_id,)).fetchone()
    if not matter:
        raise HTTPException(status_code=404, detail="Matter not found")

    # Check for duplicate
    existing = db.execute(
        "SELECT id FROM directive_matters WHERE directive_id = ? AND matter_id = ?",
        (body.directive_id, body.matter_id)
    ).fetchone()
    if existing:
        raise HTTPException(status_code=409,
                            detail="This directive is already linked to this matter")

    lid = str(uuid.uuid4())
    now = datetime.now().isoformat()

    db.execute("""
        INSERT INTO directive_matters (id, directive_id, matter_id, relationship_type, notes, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (lid, body.directive_id, body.matter_id, body.relationship_type, body.notes, now))

    new_data = body.model_dump()
    new_data.update({"id": lid, "created_at": now})
    log_event(db, table_name="directive_matters", record_id=lid, action="create",
              source=write_source, new_data=new_data)
    db.commit()
    return {"id": lid}


@router.delete("/directive-matters/{link_id}")
async def delete_directive_matter(
    link_id: str,
    request: Request,
    db=Depends(get_db),
    write_source: str = Depends(get_write_source),
):
    """Unlink a directive from a matter."""
    old = db.execute("SELECT * FROM directive_matters WHERE id = ?", (link_id,)).fetchone()
    if not old:
        raise HTTPException(status_code=404, detail="Directive-matter link not found")

    db.execute("DELETE FROM directive_matters WHERE id = ?", (link_id,))
    log_event(db, table_name="directive_matters", record_id=link_id, action="delete",
              source=write_source, old_record=old)
    db.commit()
    return {"id": link_id, "deleted": True}
