"""
Dashboard and notification endpoints.
"""

import logging

from fastapi import APIRouter, HTTPException, Query

from app.pipeline.db_async import run_db
from app.pipeline.connection import get_connection
from app.pipeline.services import dashboard as dash_svc
from app.pipeline.services import notifications as notif_svc
from app.pipeline.models import (
    ExecutiveSummaryResponse, NotificationResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/dashboard", tags=["Pipeline Dashboard"])


def _conn():
    return get_connection()


@router.get("/summary", response_model=ExecutiveSummaryResponse)
async def executive_summary():
    """Executive dashboard summary."""
    def _query():
        conn = _conn()
        try:
            return dash_svc.get_executive_summary(conn)
        finally:
            conn.close()

    return await run_db(_query)


@router.get("/metrics")
async def pipeline_metrics():
    """Pipeline performance metrics."""
    def _query():
        conn = _conn()
        try:
            return dash_svc.get_metrics(conn)
        finally:
            conn.close()

    return await run_db(_query)


@router.get("/notifications", response_model=list[NotificationResponse])
async def list_notifications(
    unread_only: bool = False,
    limit: int = Query(50, ge=1, le=200),
):
    """List notifications."""
    def _query():
        conn = _conn()
        try:
            return notif_svc.list_notifications(conn, unread_only=unread_only, limit=limit)
        finally:
            conn.close()

    return await run_db(_query)


@router.patch("/notifications/{notification_id}/read", response_model=NotificationResponse)
async def mark_notification_read(notification_id: int):
    """Mark a notification as read."""
    def _update():
        conn = _conn()
        try:
            return notif_svc.mark_read(conn, notification_id)
        finally:
            conn.close()

    result = await run_db(_update)
    if not result:
        raise HTTPException(404, f"Notification {notification_id} not found")
    return result


@router.get("/notifications/count")
async def unread_count():
    """Get unread notification count."""
    def _query():
        conn = _conn()
        try:
            return {"unread": notif_svc.count_unread(conn)}
        finally:
            conn.close()

    return await run_db(_query)
