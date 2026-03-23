"""
CFTC AI Layer — FastAPI Application

Standalone service for AI extraction, review, and intelligence.
Reads from tracker via /tracker/ai-context, writes via /tracker/batch.
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBasic, HTTPBasicCredentials
import secrets

from app.config import CORS_ORIGINS, AI_UPLOAD_DIR, AI_AUDIO_WATCH_DIR, load_policy, validate_config
from app.db import get_connection
from app.schema import init_schema

from app.routers import events, config_api, health, communications, entity_review, bundle_review, participant_review, speaker_review
from app.routers import meeting_intelligence as meeting_intelligence_api
from app.routers import intelligence as intelligence_api
from app.routers import telemetry as telemetry_api

from app.logging_config import setup_logging
setup_logging("ai")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database, config, and file watcher on startup."""
    validate_config()
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
        reports_policy = policy.get("scheduled_reports", {})

        if reports_policy.get("daily_digest", {}).get("enabled", False):
            scheduler.add_job(
                _run_daily_brief,
                CronTrigger(hour=5, minute=55),
                id="daily_brief",
                replace_existing=True,
            )
            logger.info("Daily brief job scheduled (05:55)")
        else:
            logger.info("Daily brief job DISABLED by policy")

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

        if reports_policy.get("weekly_brief", {}).get("enabled", False):
            scheduler.add_job(
                _run_weekly_brief,
                CronTrigger(day_of_week="sun", hour=20, minute=0),
                id="weekly_brief",
                replace_existing=True,
            )
            logger.info("Weekly brief job scheduled (Sun 20:00)")
        else:
            logger.info("Weekly brief job DISABLED by policy")
        def _run_dev_report():
            try:
                from app.jobs.dev_report import generate_dev_report
                from app.jobs.daily_brief import store_brief
                from app.jobs.html_renderer import render_dev_report_html
                from app.jobs.email_sender import send_email
                from app.db import get_connection
                from datetime import date

                db = get_connection()
                try:
                    data = generate_dev_report(db)
                    today = date.today().isoformat()
                    html = render_dev_report_html(data)
                    store_brief(db, "dev-report", today, data, None, None)
                    send_email(
                        subject="CFTC App Health — " + data.get("date_display", today),
                        html_body=html,
                    )
                    logger.info("Dev report generated and sent for %s", today)
                finally:
                    db.close()
            except Exception as e:
                logger.error("Dev report job failed: %s", e, exc_info=True)

        if reports_policy.get("dev_report", {}).get("enabled", False):
            scheduler.add_job(
                _run_dev_report,
                CronTrigger(day_of_week="sun", hour=20, minute=30),
                id="dev_report",
                replace_existing=True,
            )
            logger.info("Dev report job scheduled (Sun 20:30)")
        else:
            logger.info("Dev report job DISABLED by policy")

        logger.info("APScheduler started. Check above for enabled jobs.")
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

# Request ID + metrics + rate limiting middleware
from app.middleware import RequestIDMiddleware, RateLimiter, metrics as request_metrics
_rate_limiter = RateLimiter(
    max_requests=60,
    window_seconds=60,
    exclude_paths={"/health", "/metrics"},
)
app.add_middleware(RequestIDMiddleware, rate_limiter=_rate_limiter)


# ── 8A: Standard error response format ──
from fastapi.exceptions import RequestValidationError
from starlette.responses import JSONResponse as _JSONResponse
import traceback as _tb


@app.exception_handler(HTTPException)
async def _http_exception_handler(request, exc):
    """Map FastAPI HTTPException to standard error envelope.

    If the endpoint already provides a structured ``detail`` dict,
    it is preserved in ``details`` so existing consumers keep working.
    """
    code_map = {
        400: "BAD_REQUEST",
        401: "UNAUTHORIZED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        409: "CONFLICT",
        422: "VALIDATION_ERROR",
        429: "RATE_LIMITED",
    }
    # Preserve structured detail dicts (e.g. batch endpoint error_type payloads)
    if isinstance(exc.detail, dict):
        details = exc.detail
        message = exc.detail.get("message", str(exc.detail))
    else:
        details = {}
        message = str(exc.detail)

    body: dict = {
        "error": {
            "code": code_map.get(exc.status_code, f"HTTP_{exc.status_code}"),
            "message": message,
            "details": details,
        },
    }
    # Also include top-level "detail" key for backwards compatibility
    # with clients that read resp.json()["detail"]
    if isinstance(exc.detail, dict):
        body["detail"] = exc.detail

    return _JSONResponse(
        status_code=exc.status_code,
        content=body,
        headers=getattr(exc, "headers", None) or {},
    )


@app.exception_handler(RequestValidationError)
async def _validation_exception_handler(request, exc):
    """Map Pydantic / query-param validation errors to standard envelope."""
    return _JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Request validation failed",
                "details": {"errors": exc.errors()},
            }
        },
    )


@app.exception_handler(Exception)
async def _generic_exception_handler(request, exc):
    """Catch-all for unhandled exceptions."""
    logger.error("unhandled_exception", error=str(exc), tb=_tb.format_exc())
    return _JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "An unexpected error occurred",
                "details": {},
            }
        },
    )

# Optional auth dependency — enabled when AI_AUTH_USER and AI_AUTH_PASS are set
from app.config import AI_AUTH_USER, AI_AUTH_PASS

_ai_security = HTTPBasic(auto_error=False)
_auth_deps = []

if AI_AUTH_USER and AI_AUTH_PASS:
    def _verify_ai_auth(credentials: HTTPBasicCredentials = Depends(_ai_security)):
        if credentials is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required",
                headers={"WWW-Authenticate": "Basic"},
            )
        ok_user = secrets.compare_digest(credentials.username.encode(), AI_AUTH_USER.encode())
        ok_pass = secrets.compare_digest(credentials.password.encode(), AI_AUTH_PASS.encode())
        if not (ok_user and ok_pass):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials",
                headers={"WWW-Authenticate": "Basic"},
            )
        return credentials.username

    _auth_deps = [Depends(_verify_ai_auth)]
    logger.info("AI auth ENABLED (AI_AUTH_USER is set)")
else:
    logger.warning("AI auth DISABLED — set AI_AUTH_USER and AI_AUTH_PASS to enable")

@app.get("/ai/api/metrics")
async def get_metrics():
    """Request metrics snapshot."""
    return request_metrics.snapshot()


# Mount routers under /ai/api/ prefix
api_prefix = "/ai/api"
app.include_router(health.router, prefix=api_prefix)
app.include_router(config_api.router, prefix=api_prefix, dependencies=_auth_deps)
app.include_router(events.router, prefix=api_prefix, dependencies=_auth_deps)
app.include_router(communications.router, prefix=api_prefix, dependencies=_auth_deps)
app.include_router(entity_review.router, prefix=api_prefix, dependencies=_auth_deps)
app.include_router(bundle_review.router, prefix=api_prefix, dependencies=_auth_deps)
app.include_router(participant_review.router, prefix=api_prefix, dependencies=_auth_deps)
app.include_router(speaker_review.router, prefix=api_prefix, dependencies=_auth_deps)
app.include_router(meeting_intelligence_api.router, prefix=api_prefix, dependencies=_auth_deps)
app.include_router(intelligence_api.router, prefix=api_prefix, dependencies=_auth_deps)
app.include_router(telemetry_api.router, prefix=api_prefix, dependencies=_auth_deps)
