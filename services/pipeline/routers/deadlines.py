"""
Deadline endpoints.
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.pipeline.db_async import run_db
from app.pipeline.connection import get_connection
from app.pipeline.services import deadlines as svc
from app.pipeline.models import (
    DeadlineCreate, DeadlineUpdate, DeadlineResponse, DeadlineListResponse,
    ExtendDeadlineRequest, BackwardCalcRequest,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/deadlines", tags=["Pipeline Deadlines"])


def _conn():
    return get_connection()


@router.get("", response_model=DeadlineListResponse)
async def list_deadlines(
    item_id: Optional[int] = None,
    deadline_type: Optional[str] = None,
    status: Optional[str] = None,
    due_before: Optional[str] = None,
    due_after: Optional[str] = None,
    overdue_only: bool = False,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    """List deadlines with filters."""
    def _query():
        conn = _conn()
        try:
            items, total = svc.list_deadlines(
                conn, item_id=item_id, deadline_type=deadline_type,
                status=status, due_before=due_before, due_after=due_after,
                overdue_only=overdue_only, page=page, page_size=page_size,
            )
            return {"deadlines": items, "total": total}
        finally:
            conn.close()

    return await run_db(_query)


@router.get("/upcoming", response_model=list[DeadlineResponse])
async def get_upcoming(days: int = Query(30, ge=1, le=365)):
    """Get upcoming deadlines for dashboard."""
    def _query():
        conn = _conn()
        try:
            return svc.get_upcoming(conn, days=days)
        finally:
            conn.close()

    return await run_db(_query)


@router.post("", response_model=DeadlineResponse, status_code=201)
async def create_deadline(data: DeadlineCreate):
    """Create a new deadline."""
    def _create():
        conn = _conn()
        try:
            return svc.create_deadline(conn, data.model_dump())
        finally:
            conn.close()

    return await run_db(_create)


@router.patch("/{deadline_id}", response_model=DeadlineResponse)
async def update_deadline(deadline_id: int, data: DeadlineUpdate):
    """Update deadline fields."""
    def _update():
        conn = _conn()
        try:
            return svc.update_deadline(conn, deadline_id, data.model_dump(exclude_unset=True))
        finally:
            conn.close()

    result = await run_db(_update)
    if not result:
        raise HTTPException(404, f"Deadline {deadline_id} not found")
    return result


@router.post("/{deadline_id}/extend", response_model=DeadlineResponse)
async def extend_deadline(deadline_id: int, data: ExtendDeadlineRequest):
    """Extend a deadline with reason."""
    def _extend():
        conn = _conn()
        try:
            return svc.extend_deadline(conn, deadline_id, data.new_due_date, data.reason)
        finally:
            conn.close()

    result = await run_db(_extend)
    if not result:
        raise HTTPException(404, f"Deadline {deadline_id} not found")
    return result


@router.post("/backward-calculate", response_model=list[DeadlineResponse])
async def backward_calculate(data: BackwardCalcRequest):
    """Generate backward-calculated deadlines from a final deadline date."""
    def _calc():
        conn = _conn()
        try:
            return svc.backward_calculate(
                conn, data.item_id, data.final_deadline_date, data.item_type,
            )
        finally:
            conn.close()

    return await run_db(_calc)
