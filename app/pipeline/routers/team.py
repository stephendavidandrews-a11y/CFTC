"""
Team management endpoints.
"""

import logging

from fastapi import APIRouter, HTTPException

from app.pipeline.db_async import run_db
from app.pipeline.connection import get_connection
from app.pipeline.services import team as svc
from app.pipeline.models import (
    TeamMemberCreate, TeamMemberUpdate, TeamMemberResponse,
    WorkloadResponse, TeamDashboardResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/team", tags=["Pipeline Team"])


def _conn():
    return get_connection()


@router.get("", response_model=list[TeamMemberResponse])
async def list_members(active_only: bool = True):
    """List all team members."""
    def _query():
        conn = _conn()
        try:
            return svc.list_members(conn, active_only=active_only)
        finally:
            conn.close()

    return await run_db(_query)


@router.get("/dashboard", response_model=TeamDashboardResponse)
async def team_dashboard():
    """Aggregate workload across all team members."""
    def _query():
        conn = _conn()
        try:
            return svc.get_team_dashboard(conn)
        finally:
            conn.close()

    return await run_db(_query)


@router.get("/{member_id}", response_model=TeamMemberResponse)
async def get_member(member_id: int):
    """Get a single team member."""
    def _query():
        conn = _conn()
        try:
            return svc.get_member(conn, member_id)
        finally:
            conn.close()

    result = await run_db(_query)
    if not result:
        raise HTTPException(404, f"Team member {member_id} not found")
    return result


@router.get("/{member_id}/workload", response_model=WorkloadResponse)
async def get_workload(member_id: int):
    """Get workload summary for a team member."""
    def _query():
        conn = _conn()
        try:
            return svc.get_workload(conn, member_id)
        finally:
            conn.close()

    result = await run_db(_query)
    if not result:
        raise HTTPException(404, f"Team member {member_id} not found")
    return result


@router.post("", response_model=TeamMemberResponse, status_code=201)
async def create_member(data: TeamMemberCreate):
    """Add a new team member."""
    def _create():
        conn = _conn()
        try:
            return svc.create_member(conn, data.model_dump())
        finally:
            conn.close()

    return await run_db(_create)


@router.patch("/{member_id}", response_model=TeamMemberResponse)
async def update_member(member_id: int, data: TeamMemberUpdate):
    """Update team member fields."""
    def _update():
        conn = _conn()
        try:
            return svc.update_member(conn, member_id, data.model_dump(exclude_unset=True))
        finally:
            conn.close()

    result = await run_db(_update)
    if not result:
        raise HTTPException(404, f"Team member {member_id} not found")
    return result


@router.delete("/{member_id}", status_code=204)
async def delete_member(member_id: int):
    """Soft-delete a team member (marks inactive)."""
    def _delete():
        conn = _conn()
        try:
            return svc.delete_member(conn, member_id)
        finally:
            conn.close()

    found = await run_db(_delete)
    if not found:
        raise HTTPException(404, f"Team member {member_id} not found")
