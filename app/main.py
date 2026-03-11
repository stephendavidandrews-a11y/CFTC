"""CFTC Regulatory Pipeline Manager — FastAPI Application."""

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, time as dt_time

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import engine, Base
from app.api.routes import router

# Pipeline module
from app.pipeline.connection import get_connection as get_pipeline_connection
from app.pipeline.schema import init_pipeline_schema
from app.pipeline.seed import seed_all as seed_pipeline
from app.pipeline.routers.items import router as pipeline_items_router
from app.pipeline.routers.deadlines import router as pipeline_deadlines_router
from app.pipeline.routers.team import router as pipeline_team_router
from app.pipeline.routers.documents import router as pipeline_documents_router
from app.pipeline.routers.dashboard import router as pipeline_dashboard_router
from app.pipeline.routers.stakeholders import router as pipeline_stakeholders_router
from app.pipeline.routers.integrations import router as pipeline_integrations_router
from app.pipeline.routers.contacts import router as pipeline_contacts_router
from app.pipeline.routers.interagency import router as pipeline_interagency_router
from app.pipeline.routers.ai import router as pipeline_ai_router
from app.pipeline.routers.loper import router as pipeline_loper_router

# Work Management module
from app.work.main import init_work_module
from app.work.routers.projects import router as work_projects_router
from app.work.routers.items import router as work_items_router
from app.work.routers.tasks import router as work_tasks_router
from app.work.routers.notes import router as work_notes_router
from app.work.routers.dashboard import router as work_dashboard_router
from app.work.routers.templates import router as work_templates_router

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    # Startup: create comment system tables (PostgreSQL)
    logger.info("Starting CFTC Regulatory Pipeline Manager...")
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Comment system database tables verified.")
    except Exception as e:
        logger.warning(f"Comment system database unavailable (PostgreSQL): {e}")
        logger.warning("Comment system endpoints will not work. Pipeline endpoints are unaffected.")

    # Startup: create pipeline tables (SQLite)
    pipeline_conn = get_pipeline_connection()
    try:
        created = init_pipeline_schema(pipeline_conn)
        if created:
            logger.info(f"Pipeline schema: created {len(created)} new tables")
        seed_pipeline(pipeline_conn)
        logger.info("Pipeline database ready.")
    finally:
        pipeline_conn.close()

    # Startup: create work management tables (SQLite)
    init_work_module()

    # Run initial sync (non-blocking)
    sync_task = asyncio.create_task(_run_initial_sync())

    # Start daily sync background loop
    daily_task = asyncio.create_task(_daily_sync_loop())

    # Start team tracker scheduled loops
    status_email_task = asyncio.create_task(_status_email_loop())
    bottleneck_task = asyncio.create_task(_bottleneck_alert_loop())
    weekly_task = asyncio.create_task(_weekly_processing_loop())

    yield

    # Shutdown — cancel background tasks
    for t in (daily_task, sync_task, status_email_task, bottleneck_task, weekly_task):
        t.cancel()
    logger.info("Shutting down...")
    await engine.dispose()


async def _run_initial_sync():
    """Run an initial rulemaking sync on startup."""
    await asyncio.sleep(5)  # Let the app finish starting up
    try:
        from app.pipeline.services.sync import run_sync
        from app.pipeline.db_async import run_db
        logger.info("Running initial rulemaking sync...")
        result = await run_db(run_sync)
        logger.info(
            f"Initial sync complete: {result.get('created', 0)} created, "
            f"{result.get('updated', 0)} updated, "
            f"{result.get('discrepancies', 0)} discrepancies"
        )
    except Exception as e:
        logger.error(f"Initial sync failed (non-fatal): {e}")


async def _daily_sync_loop():
    """Background loop that re-syncs every SYNC_INTERVAL_HOURS hours."""
    interval_hours = int(os.environ.get("SYNC_INTERVAL_HOURS", "24"))
    interval_secs = interval_hours * 3600
    logger.info(f"Daily sync loop started (interval: {interval_hours}h)")

    # Wait for the first interval before re-syncing (initial sync runs on startup)
    await asyncio.sleep(interval_secs)

    while True:
        try:
            from app.pipeline.services.sync import run_sync
            from app.pipeline.db_async import run_db
            logger.info("Running scheduled rulemaking sync...")
            result = await run_db(run_sync)
            logger.info(
                f"Scheduled sync complete: {result.get('created', 0)} created, "
                f"{result.get('updated', 0)} updated"
            )
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Scheduled sync failed: {e}")

        await asyncio.sleep(interval_secs)


def _should_run(conn, task_key: str) -> bool:
    """Check scheduler_state to prevent double-runs after restart."""
    row = conn.execute(
        "SELECT last_run_at FROM scheduler_state WHERE task_key = ?", (task_key,)
    ).fetchone()
    if not row or not row["last_run_at"]:
        return True
    last = datetime.fromisoformat(row["last_run_at"])
    # Don't re-run if last run was less than 4 hours ago
    return (datetime.utcnow() - last).total_seconds() > 4 * 3600


def _mark_run(conn, task_key: str, status: str = "ok"):
    """Record a scheduler run."""
    now = datetime.utcnow().isoformat()
    conn.execute(
        "INSERT INTO scheduler_state (task_key, last_run_at, last_status) "
        "VALUES (?, ?, ?) "
        "ON CONFLICT(task_key) DO UPDATE SET last_run_at = ?, last_status = ?",
        (task_key, now, status, now, status),
    )
    conn.commit()


async def _wait_until(target_hour: int, target_minute: int = 0):
    """Sleep until the next occurrence of the target ET hour."""
    # Use ET offset (UTC-5 standard, UTC-4 DST). Simplified: use UTC-5.
    et_offset_hours = 5
    while True:
        now_utc = datetime.utcnow()
        target_utc_hour = (target_hour + et_offset_hours) % 24
        target = now_utc.replace(
            hour=target_utc_hour, minute=target_minute, second=0, microsecond=0
        )
        if target <= now_utc:
            target = target.replace(day=target.day + 1)
        wait_secs = (target - now_utc).total_seconds()
        if wait_secs > 0:
            return wait_secs
        return 60  # fallback


async def _status_email_loop():
    """Send status emails Mon/Wed/Fri at 6 AM ET."""
    logger.info("Status email scheduler started")
    await asyncio.sleep(30)  # let app finish starting

    while True:
        try:
            wait = await _wait_until(6, 0)
            await asyncio.sleep(wait)

            weekday = datetime.utcnow().weekday()
            if weekday not in (0, 2, 4):  # Mon, Wed, Fri
                continue

            from app.pipeline.db_async import run_db
            def _send():
                conn = get_pipeline_connection()
                try:
                    if not _should_run(conn, "status_email"):
                        return {"skipped": True}
                    from app.pipeline.services.email_service import send_status_email
                    result = send_status_email(conn)
                    _mark_run(conn, "status_email")
                    return result
                finally:
                    conn.close()

            result = await run_db(_send)
            if result and not result.get("skipped"):
                logger.info(f"Status email sent: {result}")
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Status email loop error: {e}")
            await asyncio.sleep(300)


async def _bottleneck_alert_loop():
    """Send bottleneck alerts daily at 7 AM ET."""
    logger.info("Bottleneck alert scheduler started")
    await asyncio.sleep(30)

    while True:
        try:
            wait = await _wait_until(7, 0)
            await asyncio.sleep(wait)

            from app.pipeline.db_async import run_db
            def _send():
                conn = get_pipeline_connection()
                try:
                    if not _should_run(conn, "bottleneck_alert"):
                        return {"skipped": True}
                    from app.pipeline.services.email_service import send_bottleneck_alert
                    result = send_bottleneck_alert(conn)
                    _mark_run(conn, "bottleneck_alert")
                    return result
                finally:
                    conn.close()

            result = await run_db(_send)
            if result and not result.get("skipped"):
                logger.info(f"Bottleneck alert sent: {result}")
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Bottleneck alert loop error: {e}")
            await asyncio.sleep(300)


async def _weekly_processing_loop():
    """Run weekly processing Sunday 8 PM ET: AI note processing + contact reminders."""
    logger.info("Weekly processing scheduler started")
    await asyncio.sleep(30)

    while True:
        try:
            wait = await _wait_until(20, 0)  # 8 PM ET
            await asyncio.sleep(wait)

            weekday = datetime.utcnow().weekday()
            if weekday != 6:  # Sunday
                continue

            from app.pipeline.db_async import run_db
            def _process():
                conn = get_pipeline_connection()
                try:
                    if not _should_run(conn, "weekly_processing"):
                        return {"skipped": True}

                    results = {}

                    # Process unprocessed notes with AI
                    try:
                        from app.pipeline.services.email_service import send_note_digest
                        digest = send_note_digest(conn)
                        results["note_digest"] = digest
                    except Exception as e:
                        logger.error(f"Note digest failed: {e}")
                        results["note_digest_error"] = str(e)

                    # Send contact reminders for dormant contacts
                    try:
                        from app.pipeline.services.email_service import send_contact_reminder
                        reminder = send_contact_reminder(conn)
                        results["contact_reminder"] = reminder
                    except Exception as e:
                        logger.error(f"Contact reminder failed: {e}")
                        results["contact_reminder_error"] = str(e)

                    _mark_run(conn, "weekly_processing")
                    return results
                finally:
                    conn.close()

            result = await run_db(_process)
            if result and not result.get("skipped"):
                logger.info(f"Weekly processing complete: {result}")
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Weekly processing loop error: {e}")
            await asyncio.sleep(300)


app = FastAPI(
    title="CFTC Regulatory Pipeline Manager",
    description="Unified pipeline management for CFTC rulemaking and regulatory actions.",
    version="0.2.0",
    lifespan=lifespan,
)

# CORS — allow Command Center dev server
cors_origins = settings.cors_origins_list + [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Comment system routes (existing)
app.include_router(router, prefix="/api/v1", tags=["CFTC Comment System"])

# Pipeline routes
PIPELINE_PREFIX = "/pipeline"
app.include_router(pipeline_items_router, prefix=PIPELINE_PREFIX)
app.include_router(pipeline_deadlines_router, prefix=PIPELINE_PREFIX)
app.include_router(pipeline_team_router, prefix=PIPELINE_PREFIX)
app.include_router(pipeline_documents_router, prefix=PIPELINE_PREFIX)
app.include_router(pipeline_dashboard_router, prefix=PIPELINE_PREFIX)
app.include_router(pipeline_stakeholders_router, prefix=PIPELINE_PREFIX)
app.include_router(pipeline_integrations_router, prefix=PIPELINE_PREFIX)
app.include_router(pipeline_contacts_router, prefix=PIPELINE_PREFIX)
app.include_router(pipeline_interagency_router, prefix=PIPELINE_PREFIX)
app.include_router(pipeline_ai_router, prefix=PIPELINE_PREFIX)
app.include_router(pipeline_loper_router, prefix=PIPELINE_PREFIX)


# Work Management routes
WORK_PREFIX = "/pipeline/work"
app.include_router(work_projects_router, prefix=WORK_PREFIX)
app.include_router(work_items_router, prefix=WORK_PREFIX)
app.include_router(work_tasks_router, prefix=WORK_PREFIX)
app.include_router(work_notes_router, prefix=WORK_PREFIX)
app.include_router(work_dashboard_router, prefix=WORK_PREFIX)
app.include_router(work_templates_router, prefix=WORK_PREFIX)


@app.get("/health")
async def health_check():
    return {"status": "ok", "version": "0.2.0", "system": "CFTC Regulatory Pipeline Manager"}
