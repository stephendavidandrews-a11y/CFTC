"""
CFTC Regulatory Ops Tracker — FastAPI Application
"""
import logging
import sqlite3
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBasic, HTTPBasicCredentials
import secrets

from app.config import CORS_ORIGINS, AUTH_USER, AUTH_PASS, UPLOAD_DIR
from app.db import get_connection
from app.schema import init_schema
from app.seed import seed_all

# Import routers
from app.routers import (
    organizations,
    people,
    matters,
    tasks,
    meetings,
    documents,
    decisions,
    updates,
    lookups,
    dashboard,
    tags,
    ai_context,
    batch,
    schema_version,
    export,
    context_notes,
    comment_topics,
    policy_directives,
    directive_matters,
)
from app.routers import config as config_router

logger = logging.getLogger(__name__)
security = HTTPBasic()


def verify_auth(credentials: HTTPBasicCredentials = Depends(security)):
    """HTTP Basic Auth dependency — validates credentials directly."""
    correct_user = secrets.compare_digest(credentials.username.encode(), AUTH_USER.encode())
    correct_pass = secrets.compare_digest(credentials.password.encode(), AUTH_PASS.encode())
    if not (correct_user and correct_pass):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username


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


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database on startup."""
    logger.info("Starting CFTC Tracker...")
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    conn = get_connection()
    try:
        created = init_schema(conn)
        if created:
            logger.info(f"Schema: created {len(created)} new tables: {created}")
        seed_all(conn)
        # Clean up expired idempotency keys (>24h)
        conn.execute("DELETE FROM idempotency_keys WHERE created_at < datetime('now', '-24 hours')")
        conn.commit()

        # Integrity check
        from app.config import TRACKER_DB_PATH
        _check_db_integrity(TRACKER_DB_PATH, "tracker.db")

        # WAL checkpoint — flush pending WAL frames to main DB
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        logger.info("WAL checkpoint completed for tracker.db")

        logger.info("Database ready.")
    finally:
        conn.close()
    yield
    logger.info("Shutting down CFTC Tracker.")


app = FastAPI(
    title="CFTC Regulatory Ops Tracker",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Write-Source", "X-Request-ID", "If-Match"],
)

# Mount routers — all under /tracker/ prefix, all require auth
router_prefix = "/tracker"
app.include_router(dashboard.router, prefix=router_prefix, dependencies=[Depends(verify_auth)])
app.include_router(matters.router, prefix=router_prefix, dependencies=[Depends(verify_auth)])
app.include_router(tasks.router, prefix=router_prefix, dependencies=[Depends(verify_auth)])
app.include_router(people.router, prefix=router_prefix, dependencies=[Depends(verify_auth)])
app.include_router(organizations.router, prefix=router_prefix, dependencies=[Depends(verify_auth)])
app.include_router(meetings.router, prefix=router_prefix, dependencies=[Depends(verify_auth)])
app.include_router(documents.router, prefix=router_prefix, dependencies=[Depends(verify_auth)])
app.include_router(decisions.router, prefix=router_prefix, dependencies=[Depends(verify_auth)])
app.include_router(updates.router, prefix=router_prefix, dependencies=[Depends(verify_auth)])
app.include_router(lookups.router, prefix=router_prefix, dependencies=[Depends(verify_auth)])
app.include_router(tags.router, prefix=router_prefix, dependencies=[Depends(verify_auth)])
app.include_router(ai_context.router, prefix=router_prefix, dependencies=[Depends(verify_auth)])
app.include_router(batch.router, prefix=router_prefix, dependencies=[Depends(verify_auth)])
app.include_router(schema_version.router, prefix=router_prefix, dependencies=[Depends(verify_auth)])
app.include_router(export.router, prefix=router_prefix, dependencies=[Depends(verify_auth)])
app.include_router(context_notes.router, prefix=router_prefix, dependencies=[Depends(verify_auth)])
app.include_router(comment_topics.router, prefix=router_prefix, dependencies=[Depends(verify_auth)])
app.include_router(policy_directives.router, prefix=router_prefix, dependencies=[Depends(verify_auth)])
app.include_router(directive_matters.router, prefix=router_prefix, dependencies=[Depends(verify_auth)])
app.include_router(config_router.router, prefix=router_prefix, dependencies=[Depends(verify_auth)])



# -- Global exception handler --
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    import traceback
    logger.error("Unhandled exception: %s\n%s", exc, traceback.format_exc())
    request_id = request.headers.get("x-request-id", "unknown")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "request_id": request_id},
        headers={"X-Request-ID": request_id},
    )

@app.get("/tracker/health")
async def health():
    """Health check — no auth required. Reports healthy, degraded, or impaired."""
    import shutil
    import httpx

    checks = {}
    status = "ok"

    # Database check
    try:
        conn = get_connection()
        conn.execute("SELECT 1").fetchone()
        conn.close()
        checks["db"] = "ok"
    except Exception as e:
        checks["db"] = "error: %s" % str(e)[:80]
        status = "degraded"

    # Disk check
    try:
        usage = shutil.disk_usage("/")
        checks["disk_free_mb"] = usage.free // (1024 * 1024)
        if usage.free < 200 * 1024 * 1024:
            checks["disk"] = "critical"
            status = "degraded"
        elif usage.free < 1024 * 1024 * 1024:
            checks["disk"] = "low"
        else:
            checks["disk"] = "ok"
    except Exception:
        checks["disk"] = "unknown"

    # AI service check
    try:
        async with httpx.AsyncClient(timeout=3.0) as hc:
            resp = await hc.get("http://127.0.0.1:8006/ai/api/health")
        if resp.status_code == 200:
            checks["ai_service"] = "ok"
        else:
            checks["ai_service"] = "degraded (HTTP %d)" % resp.status_code
            if status == "ok":
                status = "degraded"
    except Exception:
        checks["ai_service"] = "unavailable"
        if status == "ok":
            status = "degraded"

    return {
        "status": status,
        "service": "cftc-tracker",
        "version": "0.1.0",
        "checks": checks,
    }
