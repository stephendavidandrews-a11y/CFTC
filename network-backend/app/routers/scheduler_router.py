"""
Admin endpoints for scheduler management.
Allows viewing scheduler status, triggering jobs manually, and viewing notification logs.
"""

import sqlite3
from typing import List

from fastapi import APIRouter, Depends, HTTPException

from app.database import get_db
from app.models import NotificationLogResponse, SchedulerJobStatus, SchedulerStatusResponse
from app.scheduler import scheduler, trigger_job

router = APIRouter()


@router.get("/status", response_model=SchedulerStatusResponse)
def get_scheduler_status():
    """Get the current scheduler status and all job information."""
    jobs = scheduler.get_jobs()
    job_list = []
    for job in jobs:
        next_run = job.next_run_time.isoformat() if job.next_run_time else None
        # Extract cron expression from trigger
        trigger = job.trigger
        cron_str = str(trigger) if trigger else "unknown"
        job_list.append(SchedulerJobStatus(
            job_name=job.id,
            enabled=job.next_run_time is not None,
            cron=cron_str,
            next_run=next_run,
        ))
    return SchedulerStatusResponse(
        running=scheduler.running,
        jobs=job_list,
    )


@router.post("/trigger/{job_name}")
async def trigger_scheduler_job(job_name: str):
    """Manually trigger a scheduler job for testing."""
    result = await trigger_job(job_name)
    if "error" in result and result.get("status") != "completed":
        raise HTTPException(status_code=400, detail=result.get("error", "Job failed"))
    return result


@router.get("/logs", response_model=List[NotificationLogResponse])
def get_notification_logs(
    limit: int = 50,
    db: sqlite3.Connection = Depends(get_db),
):
    """Get recent notification/generation logs."""
    rows = db.execute(
        """
        SELECT * FROM notification_log
        ORDER BY sent_at DESC
        LIMIT ?
        """,
        [limit],
    ).fetchall()
    return [
        NotificationLogResponse(
            id=row["id"],
            job_name=row["job_name"],
            sent_at=row["sent_at"],
            title=row["title"],
            message=row["message"],
            plans_generated=row["plans_generated"],
        )
        for row in rows
    ]


@router.get("/pending-count")
def get_pending_count(db: sqlite3.Connection = Depends(get_db)):
    """Get the count of pending outreach plans (for badge/notification use)."""
    row = db.execute(
        "SELECT COUNT(*) as cnt FROM outreach_plans WHERE status = 'pending'"
    ).fetchone()
    return {"pending_count": row["cnt"] if row else 0}
