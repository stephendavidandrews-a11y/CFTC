"""Document CRUD endpoints with file upload support."""
import uuid
from datetime import datetime
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from app.db import get_db
from app.config import UPLOAD_DIR, MAX_UPLOAD_SIZE
from app.validators import CreateDocument, UpdateDocument
import json
from fastapi import Request
from fastapi.responses import JSONResponse
from app.deps import get_write_source
from app.audit import log_event
from app.concurrency import get_etag, check_etag
from app.idempotency import claim_idempotency_key, finalize_idempotency_key

router = APIRouter(prefix="/documents", tags=["documents"])

@router.get("")
async def list_documents(
    db=Depends(get_db),
    search: str = Query(None),
    status: str = Query(None),
    matter_id: str = Query(None),
    document_type: str = Query(None),
    sort_by: str = Query("updated_at"),
    sort_dir: str = Query("desc"),
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
    if document_type:
        conditions.append("d.document_type = ?")
        params.append(document_type)
    where = "WHERE " + " AND ".join(conditions) if conditions else ""

    total = db.execute(f"SELECT COUNT(*) as c FROM documents d {where}", params).fetchone()["c"]
    rows = db.execute(f"""
        SELECT d.*, p.full_name as owner_name, m.title as matter_title, m.matter_number
        FROM documents d
        LEFT JOIN people p ON d.assigned_to_person_id = p.id
        LEFT JOIN matters m ON d.matter_id = m.id
        {where}
        ORDER BY d.updated_at DESC
        LIMIT ? OFFSET ?
    """, params + [limit, offset]).fetchall()
    return {"items": [dict(row) for row in rows], "total": total, "limit": limit, "offset": offset}


@router.post("")
async def create_document(body: CreateDocument, request: Request, db=Depends(get_db),
                      write_source: str = Depends(get_write_source)):
    idem_key = request.headers.get("idempotency-key")
    cached = claim_idempotency_key(db, idem_key, body.model_dump(), "/tracker/documents")
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
        INSERT INTO documents (id, matter_id, title, document_type, status,
            assigned_to_person_id, version_label, due_date, final_location,
            is_finalized, is_sent, sent_at, summary, notes,
            source, source_id, external_refs, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (did, body.matter_id, body.title, body.document_type,
          body.status, body.assigned_to_person_id,
          body.version_label, body.due_date, body.final_location,
          body.is_finalized, body.is_sent, body.sent_at,
          body.summary, body.notes, source_val, body.source_id,
          body.external_refs, now, now))
    new_data = body.model_dump()
    new_data.update({"id": did, "source": source_val, "created_at": now, "updated_at": now})
    log_event(db, table_name="documents", record_id=did, action="create",
              source=write_source, new_data=new_data)
    result = {"id": did}
    finalize_idempotency_key(db, idem_key, 200, result)
    db.commit()
    return result



@router.get("/{doc_id}")
async def get_document(doc_id: str, db=Depends(get_db)):
    """Get a single document by ID."""
    row = db.execute("""
        SELECT d.*, p.full_name as owner_name, m.title as matter_title, m.matter_number
        FROM documents d
        LEFT JOIN people p ON d.assigned_to_person_id = p.id
        LEFT JOIN matters m ON d.matter_id = m.id
        WHERE d.id = ?
    """, (doc_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Document not found")
    result = dict(row)
    result["files"] = [dict(r) for r in db.execute("""
        SELECT id, original_filename, mime_type, file_size_bytes, is_current, uploaded_at
        FROM document_files WHERE document_id = ? ORDER BY uploaded_at DESC
    """, (doc_id,))]
    return JSONResponse(content=result, headers={"ETag": get_etag(row)})


@router.put("/{doc_id}")
async def update_document(doc_id: str, body: UpdateDocument, request: Request, db=Depends(get_db),
                      write_source: str = Depends(get_write_source)):
    """Update document metadata."""
    old = db.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone()
    if not old:
        raise HTTPException(status_code=404, detail="Document not found")
    check_etag(request, old)
    data = body.model_dump(exclude_unset=True)
    if not data:
        raise HTTPException(status_code=400, detail="No fields to update")
    sets = [f"{k} = ?" for k in data]
    params = list(data.values())
    now = datetime.now().isoformat()
    sets.append("updated_at = ?")
    params.extend([now, doc_id])
    db.execute(f"UPDATE documents SET {', '.join(sets)} WHERE id = ?", params)
    log_event(db, table_name="documents", record_id=doc_id, action="update",
              source=write_source, old_record=old, new_data=data)
    db.commit()
    return {"id": doc_id, "updated": True}


@router.post("/{doc_id}/upload")
async def upload_file(doc_id: str, file: UploadFile = File(...), db=Depends(get_db)):
    """Upload a file for a document."""
    doc = db.execute("SELECT id FROM documents WHERE id = ?", (doc_id,)).fetchone()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    content = await file.read()
    if len(content) > MAX_UPLOAD_SIZE:
        raise HTTPException(status_code=413, detail="File too large (100MB max)")

    file_id = str(uuid.uuid4())
    doc_dir = UPLOAD_DIR / doc_id
    doc_dir.mkdir(parents=True, exist_ok=True)
    file_path = doc_dir / f"{file_id}_{file.filename}"
    file_path.write_bytes(content)

    now = datetime.now().isoformat()
    # Mark previous files as not current
    db.execute("UPDATE document_files SET is_current = 0 WHERE document_id = ?", (doc_id,))
    # Insert new file record
    db.execute("""
        INSERT INTO document_files (id, document_id, storage_provider, storage_path,
            original_filename, mime_type, file_size_bytes, is_current, uploaded_at, created_at, updated_at)
        VALUES (?, ?, 'local', ?, ?, ?, ?, 1, ?, ?, ?)
    """, (file_id, doc_id, str(file_path.relative_to(UPLOAD_DIR)), file.filename,
          file.content_type, len(content), now, now, now))
    # Update document's current_file_id
    db.execute("UPDATE documents SET current_file_id = ?, updated_at = ? WHERE id = ?",
               (file_id, now, doc_id))
    db.commit()
    return {"file_id": file_id, "filename": file.filename, "size": len(content)}


@router.delete("/{doc_id}")
async def delete_document(doc_id: str, request: Request, db=Depends(get_db),
                      write_source: str = Depends(get_write_source)):
    """Delete a document and its file records and reviewers."""
    old = db.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone()
    if not old:
        raise HTTPException(status_code=404, detail="Document not found")
    check_etag(request, old)
    db.execute("DELETE FROM document_reviewers WHERE document_id = ?", (doc_id,))
    db.execute("DELETE FROM document_files WHERE document_id = ?", (doc_id,))
    db.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
    log_event(db, table_name="documents", record_id=doc_id, action="delete",
              source=write_source, old_record=old)
    db.commit()
    return {"id": doc_id, "deleted": True}
