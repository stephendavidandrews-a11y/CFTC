"""
Interagency rulemakings endpoints.
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException

from app.pipeline.db_async import run_db
from app.pipeline.connection import get_connection
from app.pipeline.services import interagency as svc
from app.pipeline.models import (
    InteragencyRulemakingCreate,
    InteragencyRulemakingUpdate,
    InteragencyRulemakingResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/interagency-rules", tags=["Interagency Rulemakings"])


def _conn():
    return get_connection()


@router.get("", response_model=list[InteragencyRulemakingResponse])
async def list_rulemakings(agency: Optional[str] = None, status: Optional[str] = None):
    """List interagency rulemakings."""
    def _query():
        conn = _conn()
        try:
            return svc.list_rulemakings(conn, agency=agency, status=status)
        finally:
            conn.close()
    return await run_db(_query)


@router.get("/{rulemaking_id}", response_model=InteragencyRulemakingResponse)
async def get_rulemaking(rulemaking_id: int):
    """Get a single rulemaking."""
    def _query():
        conn = _conn()
        try:
            return svc.get_rulemaking(conn, rulemaking_id)
        finally:
            conn.close()
    result = await run_db(_query)
    if not result:
        raise HTTPException(404, f"Rulemaking {rulemaking_id} not found")
    return result


@router.post("", response_model=InteragencyRulemakingResponse, status_code=201)
async def create_rulemaking(data: InteragencyRulemakingCreate):
    """Create a new interagency rulemaking."""
    def _create():
        conn = _conn()
        try:
            return svc.create_rulemaking(conn, data.model_dump())
        finally:
            conn.close()
    return await run_db(_create)


@router.patch("/{rulemaking_id}", response_model=InteragencyRulemakingResponse)
async def update_rulemaking(rulemaking_id: int, data: InteragencyRulemakingUpdate):
    """Update rulemaking fields."""
    def _update():
        conn = _conn()
        try:
            return svc.update_rulemaking(conn, rulemaking_id, data.model_dump(exclude_unset=True))
        finally:
            conn.close()
    result = await run_db(_update)
    if not result:
        raise HTTPException(404, f"Rulemaking {rulemaking_id} not found")
    return result


@router.delete("/{rulemaking_id}", status_code=204)
async def delete_rulemaking(rulemaking_id: int):
    """Delete a rulemaking."""
    def _delete():
        conn = _conn()
        try:
            svc.delete_rulemaking(conn, rulemaking_id)
        finally:
            conn.close()
    await run_db(_delete)
