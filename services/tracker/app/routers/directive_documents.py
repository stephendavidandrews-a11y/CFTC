"""Directive-Document link/unlink endpoints.

Join table for many-to-many between policy_directives and documents.
"""

import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Request
from app.db import get_db
from app.validators import CreateDirectiveDocument
from app.deps import get_write_source
from app.audit import log_event

router = APIRouter(tags=["directive_documents"])


@router.get("/policy-directives/{directive_id}/documents")
async def list_directive_documents(directive_id: str, db=Depends(get_db)):
    """List documents linked to a directive."""
    directive = db.execute(
        "SELECT id FROM policy_directives WHERE id = ?", (directive_id,)
    ).fetchone()
    if not directive:
        raise HTTPException(status_code=404, detail="Policy directive not found")

    rows = db.execute(
        """
        SELECT dd.id as link_id, dd.directive_id, dd.document_id,
               dd.relationship_type, dd.notes as link_notes, dd.created_at as link_created_at,
               d.id, d.title, d.document_type, d.status, d.current_file_id,
               d.external_refs, d.summary as doc_summary
        FROM directive_documents dd
        JOIN documents d ON dd.document_id = d.id
        WHERE dd.directive_id = ?
        ORDER BY d.document_type, d.title
    """,
        (directive_id,),
    ).fetchall()
    return {"items": [dict(row) for row in rows], "total": len(rows)}


@router.get("/documents/{document_id}/directives")
async def list_document_directives(document_id: str, db=Depends(get_db)):
    """List directives linked to a document (reverse lookup)."""
    doc = db.execute("SELECT id FROM documents WHERE id = ?", (document_id,)).fetchone()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    rows = db.execute(
        """
        SELECT dd.id as link_id, dd.directive_id, dd.document_id,
               dd.relationship_type, dd.notes as link_notes,
               pd.directive_label, pd.source_document,
               pd.implementation_status, pd.priority_tier, pd.responsible_entity
        FROM directive_documents dd
        JOIN policy_directives pd ON dd.directive_id = pd.id
        WHERE dd.document_id = ?
        ORDER BY dd.created_at ASC
    """,
        (document_id,),
    ).fetchall()
    return {"items": [dict(row) for row in rows], "total": len(rows)}


@router.post("/directive-documents")
async def create_directive_document(
    body: CreateDirectiveDocument,
    request: Request,
    db=Depends(get_db),
    write_source: str = Depends(get_write_source),
):
    """Link a directive to a document."""
    directive = db.execute(
        "SELECT id FROM policy_directives WHERE id = ?", (body.directive_id,)
    ).fetchone()
    if not directive:
        raise HTTPException(status_code=404, detail="Policy directive not found")
    doc = db.execute(
        "SELECT id FROM documents WHERE id = ?", (body.document_id,)
    ).fetchone()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    existing = db.execute(
        "SELECT id FROM directive_documents WHERE directive_id = ? AND document_id = ?",
        (body.directive_id, body.document_id),
    ).fetchone()
    if existing:
        raise HTTPException(
            status_code=409, detail="This directive is already linked to this document"
        )

    lid = str(uuid.uuid4())
    now = datetime.now().isoformat()

    db.execute(
        """
        INSERT INTO directive_documents (id, directive_id, document_id, relationship_type, notes, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """,
        (
            lid,
            body.directive_id,
            body.document_id,
            body.relationship_type,
            body.notes,
            now,
        ),
    )

    new_data = body.model_dump()
    new_data.update({"id": lid, "created_at": now})
    log_event(
        db,
        table_name="directive_documents",
        record_id=lid,
        action="create",
        source=write_source,
        new_data=new_data,
    )
    db.commit()
    return {"id": lid}


@router.delete("/directive-documents/{link_id}")
async def delete_directive_document(
    link_id: str,
    request: Request,
    db=Depends(get_db),
    write_source: str = Depends(get_write_source),
):
    """Unlink a directive from a document."""
    old = db.execute(
        "SELECT * FROM directive_documents WHERE id = ?", (link_id,)
    ).fetchone()
    if not old:
        raise HTTPException(status_code=404, detail="Directive-document link not found")

    db.execute("DELETE FROM directive_documents WHERE id = ?", (link_id,))
    log_event(
        db,
        table_name="directive_documents",
        record_id=link_id,
        action="delete",
        source=write_source,
        old_record=old,
    )
    db.commit()
    return {"id": link_id, "deleted": True}
