"""Matter and task update endpoints."""

from fastapi import APIRouter, Depends, Query
from app.db import get_db

router = APIRouter(prefix="/updates", tags=["updates"])


@router.get("/recent")
async def recent_updates(
    db=Depends(get_db),
    limit: int = Query(20),
):
    """Get recent updates across all matters."""
    rows = db.execute(
        """
        SELECT mu.*, m.title as matter_title, m.matter_number, p.full_name as author_name
        FROM matter_updates mu
        JOIN matters m ON mu.matter_id = m.id
        LEFT JOIN people p ON mu.created_by_person_id = p.id
        ORDER BY mu.created_at DESC
        LIMIT ?
    """,
        (limit,),
    ).fetchall()
    return [dict(row) for row in rows]
