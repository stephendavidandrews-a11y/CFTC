"""
Pipeline item endpoints.

All routes use run_db() to wrap synchronous SQLite calls.
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.pipeline.db_async import run_db
from app.pipeline.connection import get_connection
from app.pipeline.services import items as svc
from app.pipeline.models import (
    PipelineItemCreate, PipelineItemUpdate, PipelineItemResponse,
    PipelineItemDetailResponse, PipelineItemListResponse,
    StageAdvanceRequest, KanbanResponse,
    DecisionLogCreate, DecisionLogResponse,
    CreateProjectRequest, PipelineItemSimple,
)
from app.work.models import ProjectResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/items", tags=["Pipeline Items"])


def _conn():
    return get_connection()


@router.get("", response_model=PipelineItemListResponse)
async def list_items(
    module: Optional[str] = None,
    item_type: Optional[str] = None,
    stage: Optional[str] = None,
    status: Optional[str] = "active",
    assigned_to: Optional[int] = None,
    priority_label: Optional[str] = None,
    search: Optional[str] = None,
    sort_by: str = "priority_composite",
    sort_order: str = "desc",
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    """List pipeline items with filters and pagination."""
    def _query():
        conn = _conn()
        try:
            items, total = svc.list_items(
                conn, module=module, item_type=item_type, stage=stage,
                status=status, assigned_to=assigned_to, priority_label=priority_label,
                search=search, sort_by=sort_by, sort_order=sort_order,
                page=page, page_size=page_size,
            )
            return {"items": items, "total": total}
        finally:
            conn.close()

    return await run_db(_query)


@router.get("/kanban", response_model=KanbanResponse)
async def get_kanban(
    module: str = Query(..., pattern="^(rulemaking|regulatory_action)$"),
    item_type: Optional[str] = None,
    status: str = "active",
):
    """Get items grouped by stage for Kanban view."""
    def _query():
        conn = _conn()
        try:
            return svc.get_kanban(conn, module, item_type=item_type, status=status)
        finally:
            conn.close()

    return await run_db(_query)


@router.get("/simple", response_model=list[PipelineItemSimple])
async def list_items_simple():
    """Lightweight item list for dropdowns. Excludes items already linked to a work project."""
    def _query():
        conn = _conn()
        try:
            return svc.list_items_simple(conn)
        finally:
            conn.close()

    return await run_db(_query)


@router.get("/{item_id}", response_model=PipelineItemDetailResponse)
async def get_item(item_id: int):
    """Get full item detail."""
    def _query():
        conn = _conn()
        try:
            return svc.get_item(conn, item_id)
        finally:
            conn.close()

    result = await run_db(_query)
    if not result:
        raise HTTPException(404, f"Item {item_id} not found")
    return result


@router.post("", response_model=PipelineItemResponse, status_code=201)
async def create_item(data: PipelineItemCreate):
    """Create a new pipeline item."""
    def _create():
        conn = _conn()
        try:
            return svc.create_item(conn, data.model_dump())
        finally:
            conn.close()

    return await run_db(_create)


@router.patch("/{item_id}", response_model=PipelineItemResponse)
async def update_item(item_id: int, data: PipelineItemUpdate):
    """Update item fields."""
    def _update():
        conn = _conn()
        try:
            return svc.update_item(conn, item_id, data.model_dump(exclude_unset=True))
        finally:
            conn.close()

    result = await run_db(_update)
    if not result:
        raise HTTPException(404, f"Item {item_id} not found")
    return result


@router.post("/{item_id}/advance", response_model=PipelineItemResponse)
async def advance_stage(item_id: int, data: StageAdvanceRequest):
    """Advance item to next stage."""
    def _advance():
        conn = _conn()
        try:
            return svc.advance_stage(
                conn, item_id,
                rationale=data.rationale, decided_by=data.decided_by,
            )
        finally:
            conn.close()

    result = await run_db(_advance)
    if not result:
        raise HTTPException(400, "Item not found or already at terminal stage")
    return result


@router.get("/{item_id}/decision-log", response_model=list[DecisionLogResponse])
async def get_decision_log(item_id: int, limit: int = Query(50, ge=1, le=200)):
    """Get decision log entries for an item."""
    def _query():
        conn = _conn()
        try:
            return svc.get_decision_log(conn, item_id, limit=limit)
        finally:
            conn.close()

    return await run_db(_query)


@router.post("/{item_id}/decision-log", response_model=DecisionLogResponse, status_code=201)
async def add_decision_log(item_id: int, data: DecisionLogCreate):
    """Add a manual decision log entry."""
    def _add():
        conn = _conn()
        try:
            return svc.add_decision_log(conn, item_id, data.model_dump())
        finally:
            conn.close()

    return await run_db(_add)


@router.post("/{item_id}/create-project", response_model=ProjectResponse, status_code=201)
async def create_project_from_item(item_id: int, body: CreateProjectRequest):
    """Create a work project pre-populated from a pipeline item."""
    def _create():
        conn = _conn()
        try:
            return svc.create_project_from_item(conn, item_id, body.model_dump())
        except ValueError as e:
            raise HTTPException(404, str(e))
        except LookupError as e:
            raise HTTPException(409, str(e))
        finally:
            conn.close()

    return await run_db(_create)
