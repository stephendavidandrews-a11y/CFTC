"""Telemetry API router.

Tracks page visits for the weekly dev report.
"""
import logging
import uuid
from datetime import datetime

from fastapi import APIRouter
from pydantic import BaseModel

from app.db import get_connection

logger = logging.getLogger(__name__)
router = APIRouter(tags=["telemetry"])


class PageVisitRequest(BaseModel):
    page: str
    session_id: str | None = None


@router.post("/telemetry/page-visit")
def log_page_visit(req: PageVisitRequest):
    """Log a frontend page visit."""
    db = get_connection()
    try:
        db.execute(
            "INSERT INTO page_visits (id, page, timestamp, session_id) VALUES (?, ?, ?, ?)",
            (str(uuid.uuid4()), req.page, datetime.utcnow().isoformat(), req.session_id),
        )
        db.commit()
        return {"status": "ok"}
    finally:
        db.close()


@router.get("/telemetry/summary")
def get_telemetry_summary(days: int = 7):
    """Get page visit summary for the last N days."""
    db = get_connection()
    try:
        rows = db.execute(
            """SELECT page, COUNT(*) as visits
               FROM page_visits
               WHERE timestamp >= datetime('now', ?)
               GROUP BY page
               ORDER BY visits DESC""",
            (f"-{days} days",),
        ).fetchall()
        return {"period_days": days, "pages": [dict(r) for r in rows]}
    finally:
        db.close()
