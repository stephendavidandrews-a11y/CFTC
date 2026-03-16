"""
Document management endpoints.
"""

import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Query
from fastapi.responses import FileResponse

from app.pipeline.db_async import run_db
from app.pipeline.connection import get_connection
from app.pipeline.services import documents as svc

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/documents", tags=["Pipeline Documents"])


def _conn():
    return get_connection()


@router.get("")
async def list_documents(
    item_id: int = Query(...),
    current_only: bool = True,
):
    """List documents for a pipeline item."""
    def _query():
        conn = _conn()
        try:
            return svc.list_documents(conn, item_id, current_only=current_only)
        finally:
            conn.close()

    return await run_db(_query)


@router.post("", status_code=201)
async def upload_document(
    item_id: int = Form(...),
    document_type: str = Form(...),
    title: str = Form(...),
    change_summary: str = Form(None),
    uploaded_by: str = Form(None),
    file: UploadFile = File(...),
):
    """Upload a new document (or new version)."""
    content = await file.read()

    def _create():
        conn = _conn()
        try:
            return svc.create_document(
                conn,
                item_id=item_id,
                document_type=document_type,
                title=title,
                file_content=content,
                filename=file.filename,
                mime_type=file.content_type,
                uploaded_by=uploaded_by,
                change_summary=change_summary,
            )
        finally:
            conn.close()

    return await run_db(_create)


@router.get("/{doc_id}")
async def get_document(doc_id: int):
    """Get document metadata."""
    def _query():
        conn = _conn()
        try:
            return svc.get_document(conn, doc_id)
        finally:
            conn.close()

    result = await run_db(_query)
    if not result:
        raise HTTPException(404, f"Document {doc_id} not found")
    return result


@router.get("/{doc_id}/versions")
async def get_version_history(doc_id: int):
    """Get full version history for a document chain."""
    def _query():
        conn = _conn()
        try:
            return svc.get_version_history(conn, doc_id)
        finally:
            conn.close()

    return await run_db(_query)


@router.get("/{doc_id}/download")
async def download_document(doc_id: int):
    """Download a document file."""
    def _query():
        conn = _conn()
        try:
            return svc.get_document(conn, doc_id)
        finally:
            conn.close()

    doc = await run_db(_query)
    if not doc:
        raise HTTPException(404, f"Document {doc_id} not found")

    file_path = Path(doc["file_path"])
    if not file_path.exists():
        raise HTTPException(404, "File not found on disk")

    return FileResponse(
        path=str(file_path),
        filename=file_path.name,
        media_type=doc.get("mime_type") or "application/octet-stream",
    )
