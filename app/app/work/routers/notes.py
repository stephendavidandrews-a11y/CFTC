"""
Manager notes CRUD routes.
"""

from fastapi import APIRouter, HTTPException
from typing import Optional

from app.work.db import get_connection, attach_pipeline
from app.pipeline.db_async import run_db
from app.work.models import NoteCreate, NoteResponse

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
