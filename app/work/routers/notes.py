"""
Manager notes CRUD routes.
"""

from fastapi import APIRouter, HTTPException
from typing import Optional

from app.work.db import get_connection, attach_pipeline
from app.pipeline.db_async import run_db
from app.work.models import NoteCreate, NoteUpdate, NoteResponse

router = APIRouter(prefix="/notes", tags=["Work Notes"])


def _conn():
    conn = get_connection()
    attach_pipeline(conn)
    return conn


def _enrich_note(row, conn):
    d = dict(row)
    if d.get("linked_member_id"):
        try:
            member = conn.execute(
                "SELECT name FROM pipeline.team_members WHERE id = ?",
                (d["linked_member_id"],)
            ).fetchone()
            d["member_name"] = member["name"] if member else None
        except Exception:
            d["member_name"] = None
    else:
        d["member_name"] = None
    # Ensure new fields have defaults
    d.setdefault("context_type", "general")
    d.setdefault("processed", False)
    d.setdefault("ai_insights", None)
    if isinstance(d.get("processed"), int):
        d["processed"] = bool(d["processed"])
    return d


@router.get("", response_model=list[NoteResponse])
async def list_notes(
    project_id: Optional[int] = None,
    work_item_id: Optional[int] = None,
    linked_member_id: Optional[int] = None,
    note_type: Optional[str] = None,
):
    def _query():
        conn = _conn()
        try:
            sql = "SELECT * FROM manager_notes WHERE 1=1"
            params = []
            if project_id is not None:
                sql += " AND project_id = ?"
                params.append(project_id)
            if work_item_id is not None:
                sql += " AND work_item_id = ?"
                params.append(work_item_id)
            if linked_member_id is not None:
                sql += " AND linked_member_id = ?"
                params.append(linked_member_id)
            if note_type:
                sql += " AND note_type = ?"
                params.append(note_type)
            sql += " ORDER BY created_at DESC"
            rows = conn.execute(sql, params).fetchall()
            return [_enrich_note(r, conn) for r in rows]
        finally:
            conn.close()
    return await run_db(_query)


@router.get("/unprocessed", response_model=list[NoteResponse])
async def list_unprocessed_notes():
    """List notes that haven't been processed by AI yet."""
    def _query():
        conn = _conn()
        try:
            rows = conn.execute(
                "SELECT * FROM manager_notes WHERE processed = 0 ORDER BY created_at DESC"
            ).fetchall()
            return [_enrich_note(r, conn) for r in rows]
        finally:
            conn.close()
    return await run_db(_query)


@router.post("", response_model=NoteResponse, status_code=201)
async def create_note(body: NoteCreate):
    def _query():
        conn = _conn()
        try:
            data = body.model_dump()
            cols = [k for k in data if data[k] is not None]
            placeholders = ", ".join(["?"] * len(cols))
            col_names = ", ".join(cols)
            vals = [data[k] for k in cols]
            cur = conn.execute(f"INSERT INTO manager_notes ({col_names}) VALUES ({placeholders})", vals)
            conn.commit()
            row = conn.execute("SELECT * FROM manager_notes WHERE id = ?", (cur.lastrowid,)).fetchone()
            return _enrich_note(row, conn)
        finally:
            conn.close()
    return await run_db(_query)


@router.patch("/{note_id}", response_model=NoteResponse)
async def update_note(note_id: int, body: NoteUpdate):
    """Update a note (content, processing status, AI insights)."""
    def _query():
        conn = _conn()
        try:
            existing = conn.execute(
                "SELECT * FROM manager_notes WHERE id = ?", (note_id,)
            ).fetchone()
            if not existing:
                return None

            data = body.model_dump(exclude_unset=True)
            if not data:
                return _enrich_note(existing, conn)

            # Convert processed bool to int for SQLite
            if "processed" in data:
                data["processed"] = 1 if data["processed"] else 0

            set_clause = ", ".join(f"{k} = ?" for k in data)
            vals = list(data.values()) + [note_id]
            conn.execute(f"UPDATE manager_notes SET {set_clause} WHERE id = ?", vals)
            conn.commit()
            row = conn.execute("SELECT * FROM manager_notes WHERE id = ?", (note_id,)).fetchone()
            return _enrich_note(row, conn)
        finally:
            conn.close()

    result = await run_db(_query)
    if result is None:
        raise HTTPException(404, f"Note {note_id} not found")
    return result


@router.delete("/{note_id}", status_code=204)
async def delete_note(note_id: int):
    def _query():
        conn = _conn()
        try:
            conn.execute("DELETE FROM manager_notes WHERE id = ?", (note_id,))
            conn.commit()
        finally:
            conn.close()
    await run_db(_query)
