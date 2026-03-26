"""
CFTC AI Layer — FastAPI Application

Standalone service for AI extraction, review, and intelligence.
Reads from tracker via /tracker/ai-context, writes via /tracker/batch.
"""

import asyncio
import logging
import os
import sqlite3
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import shutil
from pathlib import Path


from app.config import CORS_ORIGINS, AI_UPLOAD_DIR, AI_AUDIO_WATCH_DIR, load_policy
from app.db import get_connection
from app.schema import init_schema

# Readiness flags: _ready is True after successful startup
# _startup_error holds a description if startup failed
_ready = False
_startup_error = None

from app.routers import (
    events,
    config_api,
    health,
    communications,
    entity_review,
    bundle_review,
    participant_review,
    speaker_review,
    intelligence,
    meeting_intelligence,
    telemetry,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)


# Stuck recovery configuration
STUCK_SCAN_INTERVAL = 900  # 15 minutes
STUCK_THRESHOLD_MINUTES = 60  # Communications stuck longer than this are recovered

# States that are automated (not terminal, not human gate)
_AUTOMATED_STATES = {
    "preprocessing",
    "transcribing",
    "cleaning",
    "enriching",
    "extracting",
    "committing",
    "parsing",
    "processing_attachments",
    "speakers_confirmed",
    "participants_confirmed",
    "associations_confirmed",
}

# Review-in-progress states that can be reset to their awaiting counterpart
_REVIEW_IN_PROGRESS_RESET = {
    "speaker_review_in_progress": "awaiting_speaker_review",
    "association_review_in_progress": "awaiting_association_review",
    "bundle_review_in_progress": "awaiting_bundle_review",
}


def run_stuck_recovery(conn=None) -> list[dict]:
    """Scan for stuck communications and recover them.

    Returns a list of recovery actions taken.
    Can be called manually (with conn) or from the background loop.
    """
    from app.pipeline.orchestrator import TERMINAL_STATES, HUMAN_GATE_STATES, _log_error

    close_conn = False
    if conn is None:
        conn = get_connection()
        close_conn = True

    try:
        now = datetime.utcnow().isoformat()
        threshold = "-%d minutes" % STUCK_THRESHOLD_MINUTES
        actions = []

        # Find communications that are:
        # 1. Not in a terminal or human gate state
        # 2. Updated more than STUCK_THRESHOLD_MINUTES ago
        # 3. Not currently locked (lock expired or released)
        # Use julianday() for comparison — handles both 'T' and space datetime separators
        stuck = conn.execute(
            """
            SELECT id, processing_status, updated_at
            FROM communications
            WHERE processing_status NOT IN (%s)
            AND julianday(updated_at) < julianday('now', ?)
            AND (processing_lock_token IS NULL
                 OR julianday(lock_expires_at) < julianday('now'))
        """
            % ",".join("?" for _ in (TERMINAL_STATES | HUMAN_GATE_STATES)),
            list(TERMINAL_STATES | HUMAN_GATE_STATES) + [threshold],
        ).fetchall()

        for row in stuck:
            comm_id = row["id"]
            status = row["processing_status"]
            updated = row["updated_at"]

            if status in _AUTOMATED_STATES:
                # Transition to error with recovery message
                msg = "Auto-recovered: stuck in '%s' for >%d min (last update: %s)" % (
                    status,
                    STUCK_THRESHOLD_MINUTES,
                    updated,
                )
                _log_error(conn, comm_id, status, msg)
                conn.execute(
                    """
                    UPDATE communications
                    SET processing_status = 'error',
                        error_message = ?,
                        error_stage = ?,
                        updated_at = ?
                    WHERE id = ?
                """,
                    (msg, status, now, comm_id),
                )
                conn.commit()
                actions.append(
                    {"id": comm_id, "from": status, "to": "error", "reason": msg}
                )
                logger.warning(
                    "Stuck recovery: %s '%s' -> 'error'", comm_id[:8], status
                )

            elif status in _REVIEW_IN_PROGRESS_RESET:
                # Reset to awaiting state
                reset_to = _REVIEW_IN_PROGRESS_RESET[status]
                conn.execute(
                    """
                    UPDATE communications
                    SET processing_status = ?, updated_at = ?
                    WHERE id = ?
                """,
                    (reset_to, now, comm_id),
                )
                conn.commit()
                actions.append(
                    {
                        "id": comm_id,
                        "from": status,
                        "to": reset_to,
                        "reason": "reset to gate",
                    }
                )
                logger.warning(
                    "Stuck recovery: %s '%s' -> '%s'", comm_id[:8], status, reset_to
                )

            else:
                logger.warning(
                    "Stuck recovery: %s in unexpected state '%s' — skipping",
                    comm_id[:8],
                    status,
                )

        if actions:
            logger.info("Stuck recovery: %d communications recovered", len(actions))
        return actions

    finally:
        if close_conn:
            conn.close()


async def _stuck_recovery_loop():
    """Background task: scan for stuck communications every STUCK_SCAN_INTERVAL seconds."""
    logger.info(
        "Stuck recovery scanner started (interval=%ds, threshold=%dm)",
        STUCK_SCAN_INTERVAL,
        STUCK_THRESHOLD_MINUTES,
    )
    while True:
        try:
            await asyncio.sleep(STUCK_SCAN_INTERVAL)
            actions = run_stuck_recovery()
            if actions:
                from app.routers.events import publish_event

                for action in actions:
                    await publish_event(
                        "communication_status",
                        {
                            "communication_id": action["id"],
                            "status": action["to"],
                            "previous_status": action["from"],
                            "recovery": True,
                        },
                    )
        except asyncio.CancelledError:
            logger.info("Stuck recovery scanner stopped.")
            raise
        except Exception as e:
            logger.error("Stuck recovery scanner error: %s", e)
            # Continue scanning despite errors


# ---------------------------------------------------------------------------
# Health probe loops — resume deferred communications when dependencies return
# ---------------------------------------------------------------------------

HEALTH_PROBE_INTERVAL = 300  # 5 minutes

# Disk space thresholds
DISK_WARNING_BYTES = 1 * 1024 * 1024 * 1024  # 1 GB
DISK_CRITICAL_BYTES = 200 * 1024 * 1024  # 200 MB
_disk_low = False  # Set True when disk is critically low


async def _api_health_probe_loop():
    """Probe Anthropic API every 5 minutes. Resume waiting_for_api communications when healthy."""
    logger.info("API health probe started (interval=%ds)", HEALTH_PROBE_INTERVAL)
    while True:
        try:
            await asyncio.sleep(HEALTH_PROBE_INTERVAL)
            conn = get_connection()
            try:
                waiting = conn.execute(
                    "SELECT id, error_stage FROM communications WHERE processing_status = 'waiting_for_api'"
                ).fetchall()
                if not waiting:
                    continue

                # Probe: try a tiny API call
                import anthropic
                from app.config import ANTHROPIC_API_KEY

                try:
                    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
                    client.messages.create(
                        model="claude-haiku-4-5-20251001",
                        max_tokens=1,
                        messages=[{"role": "user", "content": "ping"}],
                    )
                    api_healthy = True
                except Exception:
                    api_healthy = False

                if api_healthy:
                    logger.info(
                        "API health probe: Anthropic API is healthy. Resuming %d communications.",
                        len(waiting),
                    )
                    for row in waiting:
                        resume_to = row["error_stage"] or "pending"
                        conn.execute(
                            "UPDATE communications SET processing_status = ?, error_message = NULL, "
                            "error_stage = NULL, updated_at = datetime('now') WHERE id = ?",
                            (resume_to, row["id"]),
                        )
                    conn.commit()

                    # Trigger processing for each resumed communication
                    from app.pipeline.orchestrator import process_communication

                    for row in waiting:
                        asyncio.create_task(process_communication(row["id"]))
            finally:
                conn.close()

        except asyncio.CancelledError:
            logger.info("API health probe stopped.")
            raise
        except Exception as e:
            logger.error("API health probe error: %s", e)


async def _tracker_health_probe_loop():
    """Probe tracker service every 5 minutes. Resume awaiting_tracker communications when healthy."""
    logger.info("Tracker health probe started (interval=%ds)", HEALTH_PROBE_INTERVAL)
    while True:
        try:
            await asyncio.sleep(HEALTH_PROBE_INTERVAL)
            conn = get_connection()
            try:
                waiting = conn.execute(
                    "SELECT id, error_stage FROM communications WHERE processing_status = 'awaiting_tracker'"
                ).fetchall()
                if not waiting:
                    continue

                # Probe: ping tracker health endpoint
                import httpx
                from app.config import TRACKER_BASE_URL

                try:
                    async with httpx.AsyncClient(timeout=5.0) as hc:
                        resp = await hc.get(
                            TRACKER_BASE_URL.replace("/tracker", "") + "/tracker/health"
                        )
                    tracker_healthy = resp.status_code == 200
                except Exception:
                    tracker_healthy = False

                if tracker_healthy:
                    logger.info(
                        "Tracker health probe: tracker is healthy. Resuming %d communications.",
                        len(waiting),
                    )
                    for row in waiting:
                        resume_to = row["error_stage"] or "pending"
                        conn.execute(
                            "UPDATE communications SET processing_status = ?, error_message = NULL, "
                            "error_stage = NULL, updated_at = datetime('now') WHERE id = ?",
                            (resume_to, row["id"]),
                        )
                    conn.commit()

                    from app.pipeline.orchestrator import process_communication

                    for row in waiting:
                        asyncio.create_task(process_communication(row["id"]))
            finally:
                conn.close()

        except asyncio.CancelledError:
            logger.info("Tracker health probe stopped.")
            raise
        except Exception as e:
            logger.error("Tracker health probe error: %s", e)


async def _fr_watcher_loop():
    """Poll Federal Register for new CFTC publications on configured interval."""
    from app.pipeline.fr_watcher import run_watcher
    from app.pipeline.fr_processor import run_processor, TrackerAPI

    logger.info("Federal Register watcher loop started")

    while True:
        try:
            # Load config each cycle (allows runtime enable/disable)
            try:
                import json as _json

                with open(
                    Path(__file__).parent.parent / "config" / "ai_policy.json"
                ) as f:
                    policy = _json.load(f)
                fr_config = policy.get("federal_register", {})
            except Exception:
                fr_config = {}

            if not fr_config.get("enabled", False):
                await asyncio.sleep(3600)  # Check again in 1 hour
                continue

            poll_hours = fr_config.get("poll_interval_hours", 24)
            logger.info("FR watcher: polling (interval=%dh)", poll_hours)

            # Run watcher (fetch + classify + stage)
            db = get_connection()
            try:
                watcher_result = await run_watcher(db, fr_config)
                new_count = watcher_result.get("new", 0)
                logger.info("FR watcher: %d new documents staged", new_count)

                # Run processor if we have new Tier 1/2 docs
                if new_count > 0:
                    tracker_url = os.environ.get("TRACKER_URL", "http://localhost:8004")
                    tracker_user = os.environ.get("TRACKER_USER", "")
                    tracker_pass = os.environ.get("TRACKER_PASS", "")
                    if tracker_user and tracker_pass:
                        tracker_api = TrackerAPI(
                            tracker_url, (tracker_user, tracker_pass)
                        )
                        results = await run_processor(db, tracker_api)
                        created = sum(1 for r in results if r.get("matter_created"))
                        matched = sum(1 for r in results if r.get("matter_matched"))
                        topics = sum(r.get("topics_created", 0) for r in results)
                        qs = sum(r.get("questions_extracted", 0) for r in results)
                        logger.info(
                            "FR processor: %d created, %d matched, %d topics, %d questions",
                            created,
                            matched,
                            topics,
                            qs,
                        )
                    else:
                        logger.warning(
                            "FR processor skipped: TRACKER_USER/TRACKER_PASS not set"
                        )
            finally:
                db.close()

            # Sleep for poll interval
            await asyncio.sleep(poll_hours * 3600)

        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error("FR watcher loop error: %s", e, exc_info=True)
            await asyncio.sleep(3600)  # Retry in 1 hour on error


async def _disk_monitor_loop():
    """Check disk space every hour. Set _disk_low flag when critically low."""
    global _disk_low
    logger.info(
        "Disk monitor started (warning=%dMB, critical=%dMB)",
        DISK_WARNING_BYTES // (1024 * 1024),
        DISK_CRITICAL_BYTES // (1024 * 1024),
    )
    while True:
        try:
            await asyncio.sleep(3600)  # 1 hour
            usage = shutil.disk_usage("/")
            free = usage.free
            if free < DISK_CRITICAL_BYTES:
                logger.critical("DISK CRITICALLY LOW: %dMB free", free // (1024 * 1024))
                _disk_low = True
            elif free < DISK_WARNING_BYTES:
                logger.warning("Disk space low: %dMB free", free // (1024 * 1024))
                _disk_low = False
            else:
                _disk_low = False
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error("Disk monitor error: %s", e)


def _check_db_integrity(db_path, label: str) -> bool:
    """Run PRAGMA quick_check on a database. Returns True if ok."""
    try:
        c = sqlite3.connect(str(db_path))
        result = c.execute("PRAGMA quick_check").fetchone()[0]
        c.close()
        if result == "ok":
            logger.info("Integrity check PASSED: %s", label)
            return True
        else:
            logger.critical("Integrity check FAILED for %s: %s", label, result)
            return False
    except Exception as e:
        logger.critical("Integrity check ERROR for %s: %s", label, e)
        return False



# ── Brief scheduler ──────────────────────────────────────────────────────────

async def _brief_scheduler_loop():
    """Run daily/weekly brief generation on schedule.

    Checks every 5 minutes if it's time to generate a brief.
    Uses the AI policy config for schedule times and enabled status.
    """

    logger.info("Brief scheduler started")
    try:
        while True:
            await asyncio.sleep(300)  # Check every 5 minutes
            try:
                policy = load_policy()
                proactive = policy.get("proactive_config", {})
                now = datetime.now()
                current_time = now.strftime("%H:%M")

                # Daily brief
                daily_config = proactive.get("daily_digest", {})
                if daily_config.get("enabled"):
                    schedule_time = daily_config.get("schedule_time", "06:00")
                    # Check if we're within 10 minutes of schedule time
                    # (sleep is 300s so window must be > 5min to guarantee a hit)
                    sched_hour, sched_min = map(int, schedule_time.split(":"))
                    if now.hour == sched_hour and 0 <= now.minute - sched_min < 10:
                        # Check if we already generated today
                        from app.db import get_connection
                        conn = get_connection()
                        try:
                            existing = conn.execute(
                                "SELECT id FROM intelligence_briefs WHERE brief_type = 'daily' AND brief_date = ?",
                                (date.today().isoformat(),),
                            ).fetchone()
                            if not existing:
                                logger.info("Brief scheduler: generating daily brief")
                                from app.jobs.daily_brief import generate_daily_brief, store_brief
                                from app.jobs.html_renderer import render_daily_html
                                from app.jobs.docx_renderer import render_daily_docx
                                from app.jobs.email_sender import send_email

                                llm_client = None
                                try:
                                    from app.llm.client import get_llm_client
                                    llm_client = get_llm_client()
                                except Exception:
                                    pass

                                data = generate_daily_brief(conn, llm_client=llm_client)
                                today = date.today().isoformat()
                                html = render_daily_html(data)
                                docx_path = render_daily_docx(data)
                                model = "haiku" if any(m.get("prep_narrative") for m in data.get("meetings", [])) else None
                                store_brief(conn, "daily", today, data, str(docx_path), model)

                                # Send email if configured
                                if daily_config.get("email_digest", True):
                                    send_email(
                                        subject=f"CFTC Daily Brief — {data.get('date_display', today)}",
                                        html_body=html,
                                        docx_path=docx_path,
                                    )
                                    logger.info("Brief scheduler: daily brief emailed")
                                else:
                                    logger.info("Brief scheduler: daily brief generated (email disabled)")
                        finally:
                            conn.close()

                # Weekly brief
                weekly_config = proactive.get("weekly_brief", {})
                if weekly_config.get("enabled"):
                    schedule_day = weekly_config.get("schedule_day", "sunday")
                    schedule_time = weekly_config.get("schedule_time", "20:00")
                    day_names = {"monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
                                 "friday": 4, "saturday": 5, "sunday": 6}
                    target_day = day_names.get(schedule_day.lower(), 6)
                    sched_hour, sched_min = map(int, schedule_time.split(":"))
                    if now.weekday() == target_day and now.hour == sched_hour and 0 <= now.minute - sched_min < 10:
                        from app.db import get_connection
                        conn = get_connection()
                        try:
                            existing = conn.execute(
                                "SELECT id FROM intelligence_briefs WHERE brief_type = 'weekly' AND brief_date = ?",
                                (date.today().isoformat(),),
                            ).fetchone()
                            if not existing:
                                logger.info("Brief scheduler: generating weekly brief")
                                from app.jobs.weekly_brief import generate_weekly_brief, store_brief as store_weekly
                                from app.jobs.html_renderer import render_weekly_html
                                from app.jobs.docx_renderer import render_weekly_docx
                                from app.jobs.email_sender import send_email

                                llm_client = None
                                try:
                                    from app.llm.client import get_llm_client
                                    llm_client = get_llm_client()
                                except Exception:
                                    pass

                                data = generate_weekly_brief(conn, llm_client=llm_client)
                                today = date.today().isoformat()
                                html = render_weekly_html(data)
                                docx_path = render_weekly_docx(data)
                                store_weekly(conn, "weekly", today, data, str(docx_path))

                                send_email(
                                    subject=f"CFTC Weekly Brief — {data.get('date_display', today)}",
                                    html_body=html,
                                    docx_path=docx_path,
                                )
                                logger.info("Brief scheduler: weekly brief emailed")
                        finally:
                            conn.close()

            except Exception as e:
                logger.error("Brief scheduler error: %s", e)
    except asyncio.CancelledError:
        logger.info("Brief scheduler stopped.")

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

        # Integrity check
        from app.config import AI_DB_PATH

        _check_db_integrity(AI_DB_PATH, "ai.db")

        # WAL checkpoint — flush pending WAL frames to main DB
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        logger.info("WAL checkpoint completed for ai.db")

        logger.info("ai.db ready.")

        # Crash recovery (same connection — avoids :memory: DB isolation issue)
        stale_committing = conn.execute(
            "SELECT id FROM communications WHERE processing_status = 'committing' "
            "AND processing_lock_token IS NULL"
        ).fetchall()
        for row in stale_committing:
            conn.execute(
                "UPDATE communications SET processing_status = 'error', "
                "error_message = 'Crash recovery: found in committing state on startup', "
                "error_stage = 'committing', updated_at = datetime('now') WHERE id = ?",
                (row["id"],),
            )
            logger.warning(
                "Crash recovery: %s was stuck in 'committing' — moved to error",
                row["id"][:8],
            )
        if stale_committing:
            conn.commit()
            logger.info(
                "Crash recovery: %d stale committing communications recovered",
                len(stale_committing),
            )

        # Clean up temp files in _incoming/
        incoming_dir = AI_UPLOAD_DIR / "_incoming"
        if incoming_dir.exists():
            cleaned = 0
            for f in incoming_dir.iterdir():
                if f.is_file():
                    f.unlink()
                    cleaned += 1
            if cleaned:
                logger.info(
                    "Crash recovery: cleaned %d temp files from _incoming/", cleaned
                )
    finally:
        conn.close()

    # Load policy config
    policy = load_policy()
    logger.info(
        "AI policy loaded. Extraction model: %s",
        policy.get("model_config", {}).get("primary_extraction_model", "unknown"),
    )

    # Start file watcher for audio inbox (if directory exists and watcher is configured)
    watcher = None
    try:
        from app.pipeline.watcher import AudioInboxWatcher

        watcher = AudioInboxWatcher(watch_dir=AI_AUDIO_WATCH_DIR)
        watcher.start()
        logger.info("Audio inbox watcher started: %s", AI_AUDIO_WATCH_DIR)
    except Exception as e:
        logger.warning("Audio inbox watcher not started: %s", e)

    # Inbox re-scan: find files that arrived while the service was down
    if watcher:
        rescan_conn = get_connection()
        try:
            rescan_count = 0
            for subdir in AI_AUDIO_WATCH_DIR.iterdir():
                if not subdir.is_dir() or subdir.name.startswith("_"):
                    continue
                for f in subdir.iterdir():
                    if not f.is_file() or f.suffix.lower() not in (
                        ".wav",
                        ".flac",
                        ".mp3",
                        ".m4a",
                        ".ogg",
                        ".opus",
                    ):
                        continue
                    existing = rescan_conn.execute(
                        "SELECT id FROM audio_files WHERE file_path = ?", (str(f),)
                    ).fetchone()
                    if not existing:
                        rescan_count += 1
                        logger.info("Inbox re-scan: found unregistered file %s", f.name)
            if rescan_count:
                logger.info(
                    "Inbox re-scan: %d unregistered files found (watcher will process them)",
                    rescan_count,
                )
            else:
                logger.debug("Inbox re-scan: no unregistered files found")
        except Exception as e:
            logger.warning("Inbox re-scan failed: %s", e)
        finally:
            rescan_conn.close()

    # Start background tasks
    stuck_task = asyncio.create_task(_stuck_recovery_loop())
    api_probe_task = asyncio.create_task(_api_health_probe_loop())
    tracker_probe_task = asyncio.create_task(_tracker_health_probe_loop())
    disk_task = asyncio.create_task(_disk_monitor_loop())
    fr_task = asyncio.create_task(_fr_watcher_loop())
    brief_task = asyncio.create_task(_brief_scheduler_loop())

    # Mark service as ready
    global _ready, _startup_error
    _ready = True
    logger.info("CFTC AI Layer ready.")

    yield

    _ready = False

    # Shutdown — cancel all background tasks
    for task in [stuck_task, api_probe_task, tracker_probe_task, disk_task, fr_task, brief_task]:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    # Close shared httpx client
    from app.writeback.tracker_client import close_shared_client

    await close_shared_client()

    if watcher:
        watcher.stop()
        logger.info("Audio inbox watcher stopped.")
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
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=[
        "Content-Type",
        "Authorization",
        "X-Write-Source",
        "X-Request-ID",
        "If-Match",
    ],
)


# Readiness middleware: return 503 during startup
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse as StarletteJSONResponse


class ReadinessMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        # Allow health check during startup (for liveness probes)
        if request.url.path == "/ai/api/health":
            return await call_next(request)
        if not _ready:
            if _startup_error:
                return StarletteJSONResponse(
                    {
                        "detail": f"Service startup failed: {_startup_error}",
                        "ready": False,
                        "failed": True,
                    },
                    status_code=503,
                )
            return StarletteJSONResponse(
                {"detail": "Service starting up", "ready": False, "failed": False},
                status_code=503,
            )
        return await call_next(request)


app.add_middleware(ReadinessMiddleware)


# -- Global exception handler --


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    import traceback

    logger.error("Unhandled exception: %s\n%s", exc, traceback.format_exc())
    request_id = request.headers.get("x-request-id", "unknown")
    return StarletteJSONResponse(
        status_code=500,
        content={
            "error_type": "internal_error",
            "message": "Internal server error",
            "request_id": request_id,
        },
        headers={"X-Request-ID": request_id},
    )


# ── Authentication (HTTP Basic) ──────────────────────────────────────────
from app.config import AI_AUTH_USER, AI_AUTH_PASS, APP_ENV

if AI_AUTH_USER and AI_AUTH_PASS:
    from fastapi.security import HTTPBasic, HTTPBasicCredentials
    from fastapi import Depends, HTTPException, status
    import secrets as _secrets

    _security = HTTPBasic()

    def _verify_ai_auth(credentials: HTTPBasicCredentials = Depends(_security)):
        correct_user = _secrets.compare_digest(
            credentials.username.encode(), AI_AUTH_USER.encode()
        )
        correct_pass = _secrets.compare_digest(
            credentials.password.encode(), AI_AUTH_PASS.encode()
        )
        if not (correct_user and correct_pass):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials",
                headers={"WWW-Authenticate": "Basic"},
            )
        return credentials.username

    _ai_auth_dep = [Depends(_verify_ai_auth)]
    logger.info("AI service: HTTP Basic auth ENABLED")
else:
    _ai_auth_dep = []
    if APP_ENV == "production":
        logger.warning(
            "AI service: auth NOT configured in production — set AI_AUTH_USER and AI_AUTH_PASS"
        )
    else:
        logger.info("AI service: auth disabled (development mode)")

# Mount routers under /ai/api/ prefix
api_prefix = "/ai/api"
# Public: liveness probe only (no auth)
app.include_router(health.public_router, prefix=api_prefix)
# Protected: operational/admin endpoints
app.include_router(health.router, prefix=api_prefix, dependencies=_ai_auth_dep)
app.include_router(config_api.router, prefix=api_prefix, dependencies=_ai_auth_dep)
app.include_router(events.router, prefix=api_prefix, dependencies=_ai_auth_dep)
app.include_router(communications.router, prefix=api_prefix, dependencies=_ai_auth_dep)
app.include_router(entity_review.router, prefix=api_prefix, dependencies=_ai_auth_dep)
app.include_router(bundle_review.router, prefix=api_prefix, dependencies=_ai_auth_dep)
app.include_router(
    participant_review.router, prefix=api_prefix, dependencies=_ai_auth_dep
)
app.include_router(speaker_review.router, prefix=api_prefix, dependencies=_ai_auth_dep)
app.include_router(intelligence.router, prefix=api_prefix, dependencies=_ai_auth_dep)
app.include_router(
    meeting_intelligence.router, prefix=api_prefix, dependencies=_ai_auth_dep
)
app.include_router(telemetry.router, prefix=api_prefix, dependencies=_ai_auth_dep)
