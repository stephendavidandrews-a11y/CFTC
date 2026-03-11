"""CFTC Regulatory Pipeline Manager — FastAPI Application."""

import asyncio
import logging
import os
from contextlib import asynccontextmanager

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
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Comment system database tables verified.")

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

    yield

    # Shutdown — cancel background tasks
    daily_task.cancel()
    sync_task.cancel()
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
PIPELINE_PREFIX = "/api/v1/pipeline"
app.include_router(pipeline_items_router, prefix=PIPELINE_PREFIX)
app.include_router(pipeline_deadlines_router, prefix=PIPELINE_PREFIX)
app.include_router(pipeline_team_router, prefix=PIPELINE_PREFIX)
app.include_router(pipeline_documents_router, prefix=PIPELINE_PREFIX)
app.include_router(pipeline_dashboard_router, prefix=PIPELINE_PREFIX)
app.include_router(pipeline_stakeholders_router, prefix=PIPELINE_PREFIX)
app.include_router(pipeline_integrations_router, prefix=PIPELINE_PREFIX)


# Work Management routes
WORK_PREFIX = "/api/v1/pipeline/work"
app.include_router(work_projects_router, prefix=WORK_PREFIX)
app.include_router(work_items_router, prefix=WORK_PREFIX)
app.include_router(work_tasks_router, prefix=WORK_PREFIX)
app.include_router(work_notes_router, prefix=WORK_PREFIX)
app.include_router(work_dashboard_router, prefix=WORK_PREFIX)
app.include_router(work_templates_router, prefix=WORK_PREFIX)


@app.get("/health")
async def health_check():
    return {"status": "ok", "version": "0.2.0", "system": "CFTC Regulatory Pipeline Manager"}
