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

    yield

    # Shutdown
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
