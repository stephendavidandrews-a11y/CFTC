"""
Document management service: version-controlled uploads and retrieval.
"""

import hashlib
import logging
import shutil
from pathlib import Path

from app.pipeline.config import PIPELINE_DOC_STORAGE

logger = logging.getLogger(__name__)


def _ensure_storage(item_id: int) -> Path:
    """Ensure document storage directory exists for an item."""
    path = PIPELINE_DOC_STORAGE / str(item_id)
    path.mkdir(parents=True, exist_ok=True)
    return path


def list_documents(conn, item_id: int, current_only=True) -> list[dict]:
    """List documents for an item."""
    sql = "SELECT * FROM pipeline_documents WHERE item_id = ?"
    params = [item_id]
    if current_only:
        sql += " AND is_current = 1"
    sql += " ORDER BY document_type, created_at DESC"
    rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


def get_document(conn, doc_id: int):
    """Get a single document by ID."""
    row = conn.execute(
        "SELECT * FROM pipeline_documents WHERE id = ?", (doc_id,)
    ).fetchone()
    return dict(row) if row else None


def create_document(
    conn, item_id: int, document_type: str, title: str,
    file_content: bytes, filename: str, mime_type: str = None,
    uploaded_by: str = None, change_summary: str = None,
) -> dict:
    """Create a new document (or new version of existing)."""
    # Check for existing current version of same type+title
    existing = conn.execute(
        """SELECT id, version FROM pipeline_documents
           WHERE item_id = ? AND document_type = ? AND title = ? AND is_current = 1""",
        (item_id, document_type, title),
    ).fetchone()

    parent_id = None
    version = 1
    if existing:
        parent_id = existing["id"]
        version = existing["version"] + 1
        # Mark old version as non-current
        conn.execute(
            "UPDATE pipeline_documents SET is_current = 0 WHERE id = ?",
            (existing["id"],),
        )

    # Save file
    storage = _ensure_storage(item_id)
    file_hash = hashlib.sha256(file_content).hexdigest()[:16]
    clean_filename = Path(filename).name.replace("..", "_") if filename else "upload"
    safe_name = f"v{version}_{file_hash}_{clean_filename}"
    file_path = storage / safe_name

    file_path.write_bytes(file_content)

    cursor = conn.execute(
        """INSERT INTO pipeline_documents
           (item_id, document_type, title, version, file_path, file_size,
            file_hash, mime_type, uploaded_by, change_summary, is_current,
            parent_version_id)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)""",
        (
            item_id, document_type, title, version, str(file_path),
            len(file_content), file_hash, mime_type, uploaded_by,
            change_summary, parent_id,
        ),
    )

    # Decision log
    conn.execute(
        """INSERT INTO pipeline_decision_log
           (item_id, action_type, description, new_value)
           VALUES (?, 'note', ?, ?)""",
        (item_id, f"Document uploaded: {title} v{version}", filename),
    )
    conn.commit()

    return get_document(conn, cursor.lastrowid)


def get_version_history(conn, doc_id: int) -> list[dict]:
    """Get full version history for a document chain."""
    doc = get_document(conn, doc_id)
    if not doc:
        return []

    # Walk up to find the root
    root_id = doc_id
    while True:
        row = conn.execute(
            "SELECT parent_version_id FROM pipeline_documents WHERE id = ?",
            (root_id,),
        ).fetchone()
        if not row or not row["parent_version_id"]:
            break
        root_id = row["parent_version_id"]

    # Now collect all versions in chain from root
    versions = []
    current_id = root_id
    while current_id:
        v = get_document(conn, current_id)
        if v:
            versions.append(v)
        child = conn.execute(
            "SELECT id FROM pipeline_documents WHERE parent_version_id = ?",
            (current_id,),
        ).fetchone()
        current_id = child["id"] if child else None

    return versions
