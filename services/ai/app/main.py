"""
CFTC AI Layer — FastAPI Application

Standalone service for AI extraction, review, and intelligence.
Reads from tracker via /tracker/ai-context, writes via /tracker/batch.
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import CORS_ORIGINS, AI_UPLOAD_DIR, AI_AUDIO_WATCH_DIR, load_policy
from app.db import get_connection
from app.schema import init_schema

from app.routers import events, config_api, health, communications, entity_review, bundle_review, participant_review, speaker_review
from app.routers import meeting_intelligence as meeting_intelligence_api
from app.routers import intelligence as intelligence_api
from app.routers import telemetry as telemetry_api

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database, config, and file watcher on startup."""
    logger.info("Starting CFTC AI Layer...")

    # Ensure directories exist
    AI_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    AI_AUDIO_WATCH_DIR.mkdir(parents=True, exist_ok=True)

    # Initialize database
    conn = get_connection()
    try:
        created = init_schema(conn)
        if created:
            logger.info("Schema: created %d new tables: %s", len(created), created)

        # Clean up expired processing locks on startup
        conn.execute("""
            UPDATE communications
            SET processing_lock_token = NULL, locked_at = NULL, lock_expires_at = NULL
            WHERE lock_expires_at < datetime('now')
        """)
        conn.commit()
        logger.info("ai.db ready.")
    finally:
        conn.close()

    # Load policy config
    policy = load_policy()
    logger.info("AI policy loaded. Extraction model: %s",
                policy.get("model_config", {}).get("primary_extraction_model", "unknown"))

    # Start file watcher for audio inbox (if directory exists and watcher is configured)
    watcher = None
    try:
        from app.pipeline.watcher import AudioInboxWatcher
        watcher = AudioInboxWatcher(watch_dir=AI_AUDIO_WATCH_DIR)
        watcher.start()
        logger.info("Audio inbox watcher started: %s", AI_AUDIO_WATCH_DIR)
    except Exception as e:
        logger.warning("Audio inbox watcher not started: %s", e)

    # Start APScheduler for intelligence briefs
    scheduler = None
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.cron import CronTrigger

        def _run_daily_brief():
            try:
                from app.jobs.daily_brief import generate_daily_brief, store_brief
                from app.jobs.html_renderer import render_daily_html
                from app.jobs.docx_renderer import render_daily_docx
                from app.jobs.email_sender import send_email
                from app.db import get_connection
                from datetime import date

                db = get_connection()
                try:
                    llm_client = None
                    try:
                        from app.llm.client import get_llm_client
                        llm_client = get_llm_client()
                    except Exception:
                        pass

                    data = generate_daily_brief(db, llm_client=llm_client)
                    today = date.today().isoformat()
                    html = render_daily_html(data)
                    docx_path = render_daily_docx(data)
                    model = "haiku" if any(m.get("prep_narrative") for m in data.get("meetings", [])) else None
                    store_brief(db, "daily", today, data, str(docx_path), model)
                    send_email(
                        subject="CFTC Daily Brief \u2014 " + data.get("date_display", today),
                        html_body=html,
                        docx_path=docx_path,
                    )
                    logger.info("Daily brief generated and sent for %s", today)
                finally:
                    db.close()
            except Exception as e:
                logger.error("Daily brief job failed: %s", e, exc_info=True)

        scheduler = BackgroundScheduler(daemon=True)
        scheduler.add_job(
            _run_daily_brief,
            CronTrigger(hour=5, minute=55),
            id="daily_brief",
            replace_existing=True,
        )
        scheduler.start()
        def _run_weekly_brief():
            try:
                from app.jobs.weekly_brief import generate_weekly_brief, add_executive_summary
                from app.jobs.daily_brief import store_brief
                from app.jobs.html_renderer import render_weekly_html
                from app.jobs.docx_renderer import render_weekly_docx
                from app.jobs.email_sender import send_email
                from app.db import get_connection
                from datetime import date

                db = get_connection()
                try:
                    data = generate_weekly_brief(db)
                    try:
                        data = add_executive_summary(data, True)
                    except Exception:
                        pass
                    today = date.today().isoformat()
                    html = render_weekly_html(data)
                    docx_path = render_weekly_docx(data)
                    model = "sonnet" if data.get("executive_summary") else None
                    store_brief(db, "weekly", today, data, str(docx_path), model)
                    send_email(
                        subject="CFTC Weekly Brief \u2014 " + data.get("date_display", today),
                        html_body=html,
                        docx_path=docx_path,
                    )
                    logger.info("Weekly brief generated and sent for %s", today)
                finally:
                    db.close()
            except Exception as e:
                logger.error("Weekly brief job failed: %s", e, exc_info=True)

        scheduler.add_job(
            _run_weekly_brief,
            CronTrigger(day_of_week="sun", hour=20, minute=0),
            id="weekly_brief",
            replace_existing=True,
        )
        logger.info("APScheduler started: daily_brief at 05:55, weekly_brief Sun 20:00")
    except ImportError:
        logger.warning("APScheduler not installed \u2014 intelligence briefs will not auto-generate")
    except Exception as e:
        logger.warning("Scheduler setup failed: %s", e)

    yield

    # Shutdown
    if watcher:
        watcher.stop()
        logger.info("Audio inbox watcher stopped.")
    if scheduler:
        scheduler.shutdown(wait=False)
        logger.info("APScheduler stopped.")
    logger.info("Shutting down CFTC AI Layer.")


app = FastAPI(
    title="CFTC AI Layer",
    version="0.5.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount routers under /ai/api/ prefix
api_prefix = "/ai/api"
app.include_router(health.router, prefix=api_prefix)
app.include_router(config_api.router, prefix=api_prefix)
app.include_router(events.router, prefix=api_prefix)
app.include_router(communications.router, prefix=api_prefix)
app.include_router(entity_review.router, prefix=api_prefix)
app.include_router(bundle_review.router, prefix=api_prefix)
app.include_router(participant_review.router, prefix=api_prefix)
app.include_router(speaker_review.router, prefix=api_prefix)
app.include_router(meeting_intelligence_api.router, prefix=api_prefix)
app.include_router(intelligence_api.router, prefix=api_prefix)
app.include_router(telemetry_api.router, prefix=api_prefix)
