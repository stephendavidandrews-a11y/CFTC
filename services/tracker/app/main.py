"""
CFTC Regulatory Ops Tracker — FastAPI Application
"""
import logging
from app.logging_config import setup_logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBasic, HTTPBasicCredentials
import secrets

from app.config import CORS_ORIGINS, AUTH_USER, AUTH_PASS, UPLOAD_DIR, validate_config
from app.db import get_connection
from app.schema import init_schema, migrate_schema
from app.seed import seed_all

# Import routers
from app.routers import (
    config,
    context_notes,
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
)

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


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database on startup."""
    setup_logging("tracker")
    validate_config()
    setup_logging("tracker")
    validate_config()
    logger.info("Starting CFTC Tracker...")
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    # ── Startup banner: resolve DB ambiguity ──
    from app.config import TRACKER_DB_PATH, TRACKER_DB_PATH_SOURCE
    resolved_db = TRACKER_DB_PATH.resolve()
    print("=" * 60)
    print("TRACKER DB PATH:", resolved_db)
    print("TRACKER DB SOURCE:", TRACKER_DB_PATH_SOURCE)
    if TRACKER_DB_PATH_SOURCE == "default":
        print(
            "WARNING: DB path is the code-default fallback. "
            "Set TRACKER_DB_PATH env var for production."
        )
    if not resolved_db.exists():
        print("DB file does not exist yet — will be created by init_schema")
    else:
        import sqlite3 as _sql
        _c = _sql.connect(str(resolved_db))
        _task_count = _c.execute("SELECT COUNT(*) FROM tasks").fetchone()[0] if "tasks" in [r[0] for r in _c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()] else "N/A"
        _c.close()
        print("DB file exists: %d bytes, tasks=%s" % (resolved_db.stat().st_size, _task_count))
    print("=" * 60)

    conn = get_connection()
    try:
        created = init_schema(conn)
        if created:
            logger.info(f"Schema: created {len(created)} new tables: {created}")
        migrate_schema(conn)
        seed_all(conn)
        # Clean up expired idempotency keys (>24h)
        conn.execute("DELETE FROM idempotency_keys WHERE created_at < datetime('now', '-24 hours')")
        conn.commit()
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
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request ID + metrics + rate limiting middleware
from app.middleware import RequestIDMiddleware, RateLimiter, metrics
_rate_limiter = RateLimiter(
    max_requests=120,
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
app.include_router(context_notes.router, prefix=router_prefix, dependencies=[Depends(verify_auth)])
app.include_router(updates.router, prefix=router_prefix, dependencies=[Depends(verify_auth)])
app.include_router(lookups.router, prefix=router_prefix, dependencies=[Depends(verify_auth)])
app.include_router(tags.router, prefix=router_prefix, dependencies=[Depends(verify_auth)])
app.include_router(ai_context.router, prefix=router_prefix, dependencies=[Depends(verify_auth)])
app.include_router(batch.router, prefix=router_prefix, dependencies=[Depends(verify_auth)])
app.include_router(schema_version.router, prefix=router_prefix, dependencies=[Depends(verify_auth)])
app.include_router(config.router, prefix=router_prefix, dependencies=[Depends(verify_auth)])


@app.get("/tracker/metrics")
async def get_metrics():
    """Request metrics snapshot."""
    return metrics.snapshot()


@app.get("/tracker/health")
async def health_check():
    """Health check with DB diagnostic info."""
    from app.config import TRACKER_DB_PATH, TRACKER_DB_PATH_SOURCE
    resolved = str(TRACKER_DB_PATH.resolve())
    db_exists = TRACKER_DB_PATH.exists()
    db_size = TRACKER_DB_PATH.stat().st_size if db_exists else 0
    return {
        "status": "ok",
        "db_path": resolved,
        "db_path_source": TRACKER_DB_PATH_SOURCE,
        "db_exists": db_exists,
        "db_size_bytes": db_size,
    }