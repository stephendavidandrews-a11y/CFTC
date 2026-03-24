"""CFTC Intake Service — audio-to-transcript with speaker review.

FastAPI service on port 8005. API-only — frontend served by Command Center.
"""

from dotenv import load_dotenv
load_dotenv()

import logging
import sqlite3
import threading
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import SERVICE_PORT
from db.schema import init_db
from voice.pipeline.watcher import InboxWatcher
from voice.pipeline.processor import process_conversation

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger("cftc-intake")

# Frontend served by Command Center - this service is API-only
_watcher = None


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

    # Integrity check
    from config import DB_PATH
    _check_db_integrity(DB_PATH, "intake.db")

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
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
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



if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=SERVICE_PORT,
        reload=False,
    )
