"""CFTC Intake Service — audio-to-transcript with speaker review.

FastAPI service on port 8005. API-only — frontend served by Command Center.
"""

from dotenv import load_dotenv
load_dotenv()

import logging
import threading
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from config import SERVICE_PORT
from db.schema import init_db
from voice.pipeline.watcher import InboxWatcher
from voice.pipeline.processor import process_conversation

from logging_config import setup_logging
setup_logging("intake")
logger = logging.getLogger("cftc-intake")

# Frontend served by Command Center - this service is API-only
_watcher = None


def _on_new_file(conversation_id: str, path):
    """Callback when a new audio file is detected."""
    logger.info(f"New file detected: {path.name} -> {conversation_id[:8]}")
    thread = threading.Thread(
        target=process_conversation,
        args=(conversation_id,),
        daemon=True,
    )
    thread.start()


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _watcher

    # Initialize database
    init_db()
    logger.info("Database initialized")

    # Start file watcher
    _watcher = InboxWatcher(on_new_file=_on_new_file)
    _watcher.start()
    logger.info("Inbox watcher started")

    # Process any stuck pending conversations
    from db.connection import get_connection
    conn = get_connection()
    try:
        pending = conn.execute(
            "SELECT id FROM conversations WHERE processing_status IN ('pending', 'transcribing') ORDER BY created_at"
        ).fetchall()
    finally:
        conn.close()

    if pending:
        logger.info(f"Startup: {len(pending)} pending conversations — processing in background")
        def _process_batch(conv_ids):
            import time
            for cid in conv_ids:
                try:
                    process_conversation(cid)
                except Exception as exc:
                    logger.error(f"Startup processing failed for {cid[:8]}: {exc}")
                time.sleep(2)
        t = threading.Thread(
            target=_process_batch,
            args=([r["id"] for r in pending],),
            daemon=True,
        )
        t.start()

    yield

    if _watcher:
        _watcher.stop()
        logger.info("Inbox watcher stopped")


app = FastAPI(
    title="CFTC Intake Service",
    description="Audio ingestion, transcription, and speaker review",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8080", "http://localhost:3000", "https://cftc.stephenandrews.org"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request ID + metrics + rate limiting middleware
from middleware import RequestIDMiddleware, RateLimiter, metrics as request_metrics
_rate_limiter = RateLimiter(
    max_requests=120,
    window_seconds=60,
    exclude_paths={"/health", "/metrics"},
)
app.add_middleware(RequestIDMiddleware, rate_limiter=_rate_limiter)


# ── 8A: Standard error response format ──
from fastapi.exceptions import RequestValidationError
from starlette.responses import JSONResponse as _JSONResponse
import logging as _logging
_err_logger = _logging.getLogger("cftc-intake")


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
    _err_logger.error("unhandled_exception: %s", exc, exc_info=True)
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

# Register API routers
from api.conversations import router as conversations_router
from api.speakers import router as speakers_router
from api.audio import router as audio_router
from api.pipeline import router as pipeline_router
from api.transcribe import router as transcribe_router

app.include_router(conversations_router, prefix="/intake/api")
app.include_router(speakers_router, prefix="/intake/api")
app.include_router(audio_router, prefix="/intake/api")
app.include_router(pipeline_router, prefix="/intake/api")
app.include_router(transcribe_router, prefix="/intake/api")


@app.get("/intake/api/health")
def health_check():
    from db.connection import get_connection
    conn = get_connection()
    try:
        total = conn.execute("SELECT COUNT(*) as n FROM conversations").fetchone()["n"]
        pending = conn.execute(
            "SELECT COUNT(*) as n FROM conversations WHERE processing_status = 'pending'"
        ).fetchone()["n"]
        voice_profiles = conn.execute("SELECT COUNT(DISTINCT tracker_person_id) as n FROM speaker_voice_profiles").fetchone()["n"]
    finally:
        conn.close()

    return {
        "service": "cftc-intake",
        "version": "0.1.0",
        "status": "operational",
        "conversations": {"total": total, "pending": pending},
        "voice_profiles": voice_profiles,
    }



@app.get("/intake/api/metrics")
async def get_metrics():
    """Request metrics snapshot."""
    return request_metrics.snapshot()


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=SERVICE_PORT,
        reload=False,
    )
