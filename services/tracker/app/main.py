"""
CFTC Regulatory Ops Tracker — FastAPI Application
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
import sqlite3
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import hashlib
import hmac
import secrets
import time

from app.config import CORS_ORIGINS, AUTH_USER, AUTH_PASS, UPLOAD_DIR
from app.db import get_connection
from app.schema import init_schema, migrate_schema
from app.seed import seed_all, seed_schema_v2_defaults

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
    directive_documents,
    system_events,
)
from app.jobs.capture_rollup import rollup_and_prune
from app.routers import capture
from app.routers import config as config_router

logger = logging.getLogger(__name__)

_SESSION_COOKIE = "tracker_session"
_SESSION_MAX_AGE = 7 * 24 * 3600  # 7 days
# Derive a signing key from the credentials so cookie invalidates if creds change
_SIGN_KEY = hashlib.sha256(f"{AUTH_USER}:{AUTH_PASS}".encode()).digest()


def _sign_session(username: str) -> str:
    """Create a signed session token: username|expiry|signature."""
    expiry = int(time.time()) + _SESSION_MAX_AGE
    payload = f"{username}|{expiry}"
    sig = hmac.new(_SIGN_KEY, payload.encode(), hashlib.sha256).hexdigest()[:32]
    return f"{payload}|{sig}"


def _verify_session(token: str) -> str | None:
    """Verify a session token. Returns username if valid, None otherwise."""
    try:
        parts = token.split("|")
        if len(parts) != 3:
            return None
        username, expiry_str, sig = parts
        expiry = int(expiry_str)
        if time.time() > expiry:
            return None
        expected_payload = f"{username}|{expiry_str}"
        expected_sig = hmac.new(_SIGN_KEY, expected_payload.encode(), hashlib.sha256).hexdigest()[:32]
        if not hmac.compare_digest(sig, expected_sig):
            return None
        return username
    except Exception:
        return None


async def verify_auth(request: Request):
    """Check session cookie first, fall back to HTTP Basic Auth header.

    Does NOT use FastAPI's HTTPBasic scheme to avoid WWW-Authenticate
    headers that trigger browser native auth popups.
    """
    # Check session cookie
    cookie = request.cookies.get(_SESSION_COOKIE)
    if cookie:
        username = _verify_session(cookie)
        if username:
            return username

    # Check Authorization header manually (for AI service, curl, etc.)
    auth_header = request.headers.get("authorization", "")
    if auth_header.startswith("Basic "):
        try:
            import base64
            decoded = base64.b64decode(auth_header[6:]).decode("utf-8")
            username, password = decoded.split(":", 1)
            if (
                AUTH_USER
                and AUTH_PASS
                and secrets.compare_digest(username.encode(), AUTH_USER.encode())
                and secrets.compare_digest(password.encode(), AUTH_PASS.encode())
            ):
                request.state.set_session_cookie = username
                return username
        except Exception:
            pass

    # No valid auth
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required",
    )


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


async def _rollup_scheduler():
    """Run capture rollup daily at 2:00 AM UTC."""
    while True:
        now = datetime.now(timezone.utc)
        target = now.replace(hour=2, minute=0, second=0, microsecond=0)
        if target <= now:
            target += timedelta(days=1)
        wait_s = (target - now).total_seconds()
        logger.info("Rollup scheduled in %.0f seconds (at %s)", wait_s, target.isoformat())
        await asyncio.sleep(wait_s)
        try:
            db = get_connection()
            try:
                result = rollup_and_prune(db)
                logger.info("Rollup result: %s", result)
            finally:
                db.close()
        except Exception:
            logger.exception("Rollup failed")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database on startup."""
    logger.info("Starting CFTC Tracker...")
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    conn = get_connection()
    try:
        created = init_schema(conn)
        migrate_schema(conn)
        if created:
            logger.info(f"Schema: created {len(created)} new tables: {created}")
        seed_all(conn)
        seed_schema_v2_defaults(conn)
        # Clean up expired idempotency keys (>24h)
        conn.execute(
            "DELETE FROM idempotency_keys WHERE created_at < datetime('now', '-24 hours')"
        )
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
    _staleness_task = asyncio.create_task(capture.staleness_checker())
    _rollup_task = asyncio.create_task(_rollup_scheduler())
    _alert_task = asyncio.create_task(capture.alert_evaluator())
    yield
    _staleness_task.cancel()
    _rollup_task.cancel()
    _alert_task.cancel()
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
    allow_headers=[
        "Content-Type",
        "Authorization",
        "X-Write-Source",
        "X-Request-ID",
        "If-Match",
    ],
)


@app.exception_handler(401)
async def auth_redirect_handler(request: Request, exc):
    """Redirect browsers to login page on 401, return JSON for API clients."""
    accept = request.headers.get("accept", "")
    if "text/html" in accept and "/tracker/login" not in str(request.url):
        from starlette.responses import RedirectResponse
        return RedirectResponse(url="/tracker/login", status_code=303)
    return JSONResponse(
        status_code=401,
        content={"detail": getattr(exc, "detail", "Authentication required")},
    )


@app.middleware("http")
async def session_cookie_middleware(request: Request, call_next):
    """Set session cookie after successful Basic Auth login."""
    response = await call_next(request)
    username = getattr(request.state, "set_session_cookie", None)
    if username:
        token = _sign_session(username)
        response.set_cookie(
            key=_SESSION_COOKIE,
            value=token,
            max_age=_SESSION_MAX_AGE,
            httponly=True,
            samesite="lax",
            secure=True,
            path="/",
        )
    return response

# ── Login routes (no auth required) ──────────────────────────────────────

_LOGIN_HTML = """<!DOCTYPE html>
<html><head>
<title>CFTC Command Center — Login</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
  body { background: #0a0f1a; color: #e0e0e0; font-family: -apple-system, BlinkMacSystemFont, sans-serif;
         display: flex; align-items: center; justify-content: center; min-height: 100vh; margin: 0; }
  .card { background: #111827; border: 1px solid #1e293b; border-radius: 12px; padding: 40px;
          width: 340px; box-shadow: 0 8px 32px rgba(0,0,0,0.4); }
  h1 { font-size: 18px; margin: 0 0 24px; color: #93c5fd; text-align: center; }
  label { display: block; font-size: 12px; font-weight: 600; color: #94a3b8; margin-bottom: 4px; }
  input { width: 100%; padding: 10px 12px; border-radius: 6px; border: 1px solid #334155;
          background: #1e293b; color: #e2e8f0; font-size: 14px; box-sizing: border-box; margin-bottom: 16px; }
  input:focus { outline: none; border-color: #3b82f6; }
  button { width: 100%; padding: 10px; border-radius: 8px; border: none; background: #3b82f6;
           color: #fff; font-size: 14px; font-weight: 600; cursor: pointer; }
  button:hover { background: #2563eb; }
  .error { color: #ef4444; font-size: 13px; text-align: center; margin-bottom: 12px; display: none; }
</style></head><body>
<div class="card">
  <h1>CFTC Command Center</h1>
  <div class="error" id="err">Invalid credentials</div>
  <form method="POST" action="/tracker/login" id="form">
    <label>Username</label><input name="username" autocomplete="username" required autofocus>
    <label>Password</label><input name="password" type="password" autocomplete="current-password" required>
    <button type="submit">Sign In</button>
  </form>
</div>
<script>
  const params = new URLSearchParams(location.search);
  if (params.get('error') === '1') document.getElementById('err').style.display = 'block';
</script>
</body></html>"""


@app.get("/tracker/login", response_class=HTMLResponse, include_in_schema=False)
async def login_page():
    return _LOGIN_HTML


@app.post("/tracker/login", include_in_schema=False)
async def login_submit(request: Request):
    form = await request.form()
    username = form.get("username", "")
    password = form.get("password", "")

    if (
        AUTH_USER
        and AUTH_PASS
        and secrets.compare_digest(username.encode(), AUTH_USER.encode())
        and secrets.compare_digest(password.encode(), AUTH_PASS.encode())
    ):
        token = _sign_session(username)
        response = JSONResponse(
            content={"ok": True},
            status_code=303,
            headers={"Location": "/"},
        )
        response.set_cookie(
            key=_SESSION_COOKIE,
            value=token,
            max_age=_SESSION_MAX_AGE,
            httponly=True,
            samesite="lax",
            secure=True,
            path="/",
        )
        return response
    else:
        return HTMLResponse(
            status_code=303,
            content="",
            headers={"Location": "/tracker/login?error=1"},
        )


# Mount routers — all under /tracker/ prefix, all require auth
router_prefix = "/tracker"
app.include_router(
    dashboard.router, prefix=router_prefix, dependencies=[Depends(verify_auth)]
)
app.include_router(
    matters.router, prefix=router_prefix, dependencies=[Depends(verify_auth)]
)
app.include_router(
    tasks.router, prefix=router_prefix, dependencies=[Depends(verify_auth)]
)
app.include_router(
    people.router, prefix=router_prefix, dependencies=[Depends(verify_auth)]
)
app.include_router(
    organizations.router, prefix=router_prefix, dependencies=[Depends(verify_auth)]
)
app.include_router(
    meetings.router, prefix=router_prefix, dependencies=[Depends(verify_auth)]
)
app.include_router(
    documents.router, prefix=router_prefix, dependencies=[Depends(verify_auth)]
)
app.include_router(
    decisions.router, prefix=router_prefix, dependencies=[Depends(verify_auth)]
)
app.include_router(
    updates.router, prefix=router_prefix, dependencies=[Depends(verify_auth)]
)
app.include_router(
    lookups.router, prefix=router_prefix, dependencies=[Depends(verify_auth)]
)
app.include_router(
    tags.router, prefix=router_prefix, dependencies=[Depends(verify_auth)]
)
app.include_router(
    ai_context.router, prefix=router_prefix, dependencies=[Depends(verify_auth)]
)
app.include_router(
    batch.router, prefix=router_prefix, dependencies=[Depends(verify_auth)]
)
app.include_router(
    schema_version.router, prefix=router_prefix, dependencies=[Depends(verify_auth)]
)
app.include_router(
    export.router, prefix=router_prefix, dependencies=[Depends(verify_auth)]
)
app.include_router(
    context_notes.router, prefix=router_prefix, dependencies=[Depends(verify_auth)]
)
app.include_router(
    comment_topics.router, prefix=router_prefix, dependencies=[Depends(verify_auth)]
)
app.include_router(
    policy_directives.router, prefix=router_prefix, dependencies=[Depends(verify_auth)]
)
app.include_router(
    directive_matters.router, prefix=router_prefix, dependencies=[Depends(verify_auth)]
)
app.include_router(
    directive_documents.router,
    prefix=router_prefix,
    dependencies=[Depends(verify_auth)],
)
app.include_router(
    config_router.router, prefix=router_prefix, dependencies=[Depends(verify_auth)]
)
app.include_router(
    system_events.router, prefix=router_prefix, dependencies=[Depends(verify_auth)]
)
# Capture monitoring: WS endpoints handle their own auth
app.include_router(capture.router, prefix=router_prefix)


# -- Global exception handler --
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    from fastapi import HTTPException as _HTTPException
    if isinstance(exc, _HTTPException):
        raise exc
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
        checks["db"] = "error"
        status = "degraded"

    # Disk check
    try:
        usage = shutil.disk_usage("/")
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
            checks["ai_service"] = "degraded"
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
