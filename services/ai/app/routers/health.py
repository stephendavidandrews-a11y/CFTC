"""Health and operational status endpoints."""
import logging
import shutil
from datetime import datetime
from fastapi import APIRouter, Depends
from app.db import get_db
from app.config import load_policy

logger = logging.getLogger(__name__)
router = APIRouter(tags=["health"])

# Public liveness/readiness endpoint - no auth required
public_router = APIRouter(tags=["health"])

AI_SERVICE_VERSION = "0.5.0"


@public_router.get("/health")
async def health(db=Depends(get_db)):
    """Service health and queue stats."""
    # Count communications by status for queue overview
    status_counts = {}
    rows = db.execute("""
        SELECT processing_status, COUNT(*) as cnt
        FROM communications
        GROUP BY processing_status
    """).fetchall()
    for r in rows:
        status_counts[r["processing_status"]] = r["cnt"]

    # Today's LLM spend
    spend_row = db.execute("""
        SELECT COALESCE(SUM(cost_usd), 0.0) as today_spend
        FROM llm_usage
        WHERE created_at >= date('now')
    """).fetchone()
    today_spend = spend_row["today_spend"] if spend_row else 0.0

    policy = load_policy()
    daily_budget = policy.get("model_config", {}).get("daily_budget_usd", 10.0)

    # Disk space
    try:
        usage = shutil.disk_usage("/")
        disk_free_mb = usage.free // (1024 * 1024)
    except Exception:
        disk_free_mb = -1

    from app.main import _disk_low, _ready
    return {
        "status": "ok" if _ready else "starting",
        "ready": _ready,
        "service": "cftc-ai",
        "version": AI_SERVICE_VERSION,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "queue": status_counts,
        "spend": {
            "today_usd": round(today_spend, 4),
            "daily_budget_usd": daily_budget,
            "budget_remaining_usd": round(daily_budget - today_spend, 4),
            "paused": today_spend >= daily_budget,
        },
        "disk": {
            "free_mb": disk_free_mb,
            "low": _disk_low,
        },
    }


@router.get("/errors")
async def recent_errors(db=Depends(get_db), limit: int = 50):
    """Recent pipeline errors with communication details."""
    rows = db.execute("""
        SELECT c.id, c.title, c.processing_status, c.error_stage, c.error_message,
               c.updated_at, c.source_type
        FROM communications c
        WHERE c.processing_status IN ('error', 'waiting_for_api', 'awaiting_tracker', 'paused_budget')
        ORDER BY c.updated_at DESC
        LIMIT ?
    """, (limit,)).fetchall()
    return {"errors": [dict(r) for r in rows], "count": len(rows)}


@router.get("/errors/history")
async def error_history(db=Depends(get_db), communication_id: str = None, limit: int = 100):
    """Error history from communication_error_log."""
    if communication_id:
        rows = db.execute(
            "SELECT * FROM communication_error_log WHERE communication_id = ? ORDER BY created_at DESC LIMIT ?",
            (communication_id, limit),
        ).fetchall()
    else:
        rows = db.execute(
            "SELECT * FROM communication_error_log ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return {"history": [dict(r) for r in rows], "count": len(rows)}


@router.get("/costs")
async def cost_summary(db=Depends(get_db)):
    """LLM cost breakdown: today, this week, this month, by model, by stage."""
    today = db.execute(
        "SELECT COALESCE(SUM(cost_usd), 0.0) as total FROM llm_usage WHERE created_at >= date('now')"
    ).fetchone()["total"]

    week = db.execute(
        "SELECT COALESCE(SUM(cost_usd), 0.0) as total FROM llm_usage WHERE created_at >= date('now', '-7 days')"
    ).fetchone()["total"]

    month = db.execute(
        "SELECT COALESCE(SUM(cost_usd), 0.0) as total FROM llm_usage WHERE created_at >= date('now', '-30 days')"
    ).fetchone()["total"]

    by_model = {}
    for r in db.execute(
        "SELECT model, COALESCE(SUM(cost_usd), 0.0) as total, COUNT(*) as calls "
        "FROM llm_usage WHERE created_at >= date('now', '-30 days') GROUP BY model"
    ).fetchall():
        by_model[r["model"]] = {"cost_usd": round(r["total"], 4), "calls": r["calls"]}

    by_stage = {}
    for r in db.execute(
        "SELECT stage, COALESCE(SUM(cost_usd), 0.0) as total, COUNT(*) as calls "
        "FROM llm_usage WHERE created_at >= date('now', '-30 days') GROUP BY stage"
    ).fetchall():
        by_stage[r["stage"]] = {"cost_usd": round(r["total"], 4), "calls": r["calls"]}

    policy = load_policy()
    daily_budget = policy.get("model_config", {}).get("daily_budget_usd", 10.0)

    return {
        "today_usd": round(today, 4),
        "week_usd": round(week, 4),
        "month_usd": round(month, 4),
        "daily_budget_usd": daily_budget,
        "by_model": by_model,
        "by_stage": by_stage,
    }


@router.get("/notifications/status")
async def notification_status():
    """Current state of the error notification system."""
    from app.notifications import get_buffer_status
    return get_buffer_status()


@router.post("/notifications/flush")
async def flush_notifications():
    """Force-flush buffered error notifications."""
    from app.notifications import flush_error_buffer
    count = flush_error_buffer()
    return {"flushed": count}


@router.post("/notifications/test")
async def test_notification():
    """Send a test notification email to verify SMTP configuration."""
    from app.notifications import notify_pipeline_error, get_buffer_status
    status = get_buffer_status()
    if not status["smtp_configured"]:
        return {"error": "SMTP not configured", "status": status}
    notify_pipeline_error(
        communication_id="test-000",
        title="SMTP Configuration Test",
        error_stage="test",
        error_message="This is a test notification to verify SMTP delivery. Safe to ignore.",
        target_state="test",
    )
    return {"sent": True, "status": get_buffer_status()}


@router.post("/stuck-recovery/trigger")
async def trigger_stuck_recovery():
    """Manual trigger for stuck communication recovery scanner."""
    from app.main import run_stuck_recovery
    actions = run_stuck_recovery()
    return {
        "recovered": len(actions),
        "actions": actions,
    }
