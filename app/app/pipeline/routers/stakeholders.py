"""
Stakeholder and meeting endpoints.
"""

import json
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.pipeline.db_async import run_db
from app.pipeline.connection import get_connection
from app.pipeline.models import (
    StakeholderCreate, StakeholderResponse,
    MeetingCreate, MeetingResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/stakeholders", tags=["Pipeline Stakeholders"])


def _conn():
    return get_connection()


# ── Stakeholder CRUD ────────────────────────────────────────────────

@router.get("", response_model=list[StakeholderResponse])
async def list_stakeholders(
    stakeholder_type: Optional[str] = None,
    search: Optional[str] = None,
):
    """List stakeholders."""
    def _query():
        conn = _conn()
        try:
            conditions, params = [], []
            if stakeholder_type:
                conditions.append("stakeholder_type = ?")
                params.append(stakeholder_type)
            if search:
                conditions.append("(name LIKE ? OR organization LIKE ?)")
                term = f"%{search}%"
                params.extend([term, term])

            where = ""
            if conditions:
                where = "WHERE " + " AND ".join(conditions)

            rows = conn.execute(
                f"SELECT * FROM pipeline_stakeholders {where} ORDER BY name",
                params,
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    return await run_db(_query)


@router.get("/{stakeholder_id}", response_model=StakeholderResponse)
async def get_stakeholder(stakeholder_id: int):
    """Get a single stakeholder."""
    def _query():
        conn = _conn()
        try:
            row = conn.execute(
                "SELECT * FROM pipeline_stakeholders WHERE id = ?",
                (stakeholder_id,),
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    result = await run_db(_query)
    if not result:
        raise HTTPException(404, f"Stakeholder {stakeholder_id} not found")
    return result


@router.post("", response_model=StakeholderResponse, status_code=201)
async def create_stakeholder(data: StakeholderCreate):
    """Create a new stakeholder."""
    def _create():
        conn = _conn()
        try:
            cursor = conn.execute(
                """INSERT INTO pipeline_stakeholders
                   (name, organization, stakeholder_type, title, email, phone, notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    data.name, data.organization, data.stakeholder_type,
                    data.title, data.email, data.phone, data.notes,
                ),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM pipeline_stakeholders WHERE id = ?",
                (cursor.lastrowid,),
            ).fetchone()
            return dict(row)
        finally:
            conn.close()

    return await run_db(_create)


# ── Meeting CRUD ────────────────────────────────────────────────────

@router.get("/meetings", response_model=list[MeetingResponse])
async def list_meetings(
    item_id: Optional[int] = None,
    meeting_type: Optional[str] = None,
):
    """List meetings."""
    def _query():
        conn = _conn()
        try:
            conditions, params = [], []
            if item_id:
                conditions.append("pm.item_id = ?")
                params.append(item_id)
            if meeting_type:
                conditions.append("pm.meeting_type = ?")
                params.append(meeting_type)

            where = ""
            if conditions:
                where = "WHERE " + " AND ".join(conditions)

            rows = conn.execute(
                f"""SELECT pm.*, COALESCE(pi.short_title, pi.title) as item_title
                    FROM pipeline_meetings pm
                    LEFT JOIN pipeline_items pi ON pm.item_id = pi.id
                    {where}
                    ORDER BY pm.date DESC""",
                params,
            ).fetchall()

            result = []
            for r in rows:
                m = dict(r)
                m["is_ex_parte"] = bool(m.get("is_ex_parte", 0))
                m["ex_parte_filed"] = bool(m.get("ex_parte_filed", 0))
                try:
                    m["attendees"] = json.loads(m.get("attendees") or "[]")
                except (json.JSONDecodeError, TypeError):
                    m["attendees"] = []
                result.append(m)
            return result
        finally:
            conn.close()

    return await run_db(_query)


@router.post("/meetings", response_model=MeetingResponse, status_code=201)
async def create_meeting(data: MeetingCreate):
    """Create a meeting record."""
    def _create():
        conn = _conn()
        try:
            attendees_json = json.dumps(data.attendees)
            cursor = conn.execute(
                """INSERT INTO pipeline_meetings
                   (item_id, meeting_type, title, date, attendees, summary, is_ex_parte)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    data.item_id, data.meeting_type, data.title,
                    data.date, attendees_json, data.summary,
                    1 if data.is_ex_parte else 0,
                ),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM pipeline_meetings WHERE id = ?",
                (cursor.lastrowid,),
            ).fetchone()
            m = dict(row)
            m["is_ex_parte"] = bool(m.get("is_ex_parte", 0))
            m["ex_parte_filed"] = bool(m.get("ex_parte_filed", 0))
            m["item_title"] = None
            try:
                m["attendees"] = json.loads(m.get("attendees") or "[]")
            except (json.JSONDecodeError, TypeError):
                m["attendees"] = []
            return m
        finally:
            conn.close()

    return await run_db(_create)
