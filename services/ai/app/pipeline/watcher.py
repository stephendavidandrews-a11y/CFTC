"""File watcher for audio inbox directory.

Monitors audio-inbox/ for new audio files and creates communication records.
Both the watcher and the upload endpoint converge on the same
create_communication() -> process_communication() path.

Adapted from services/intake/voice/pipeline/watcher.py for the AI service.
"""
import asyncio
import hashlib
import logging
import shutil
import threading
from datetime import datetime
from pathlib import Path

from watchdog.events import FileSystemEventHandler, FileCreatedEvent
from watchdog.observers import Observer

from app.pipeline.stages.preprocessing import ACCEPTED_FORMATS

logger = logging.getLogger(__name__)

# Stable-file detection: check file size at intervals until it stops changing
SETTLE_CHECK_INTERVAL = 5.0    # seconds between size checks
SETTLE_MAX_WAIT = 120.0        # max seconds to wait for stability


class _AudioFileHandler(FileSystemEventHandler):
    """Handles new audio files appearing in the inbox directory."""

    def __init__(self):
        self._pending: dict[str, asyncio.TimerHandle] = {}

    def on_created(self, event: FileCreatedEvent):
        if event.is_directory:
            return
        path = Path(event.src_path)
        if path.suffix.lower() not in ACCEPTED_FORMATS:
            logger.debug("Ignoring non-audio file: %s", path.name)
            return
        # Ignore hidden/temp files
        if path.name.startswith(".") or path.name.startswith("~"):
            return

        logger.info("New audio file detected: %s", path.name)
        # Queue for processing after debounce
        self._schedule_ingest(path)

    def _schedule_ingest(self, path: Path):
        """Wait for file size to stabilize, then ingest."""
        def _wait_and_ingest():
            import time
            elapsed = 0.0
            prev_size = -1
            while elapsed < SETTLE_MAX_WAIT:
                if not path.exists():
                    logger.warning("File disappeared before ingestion: %s", path.name)
                    return
                curr_size = path.stat().st_size
                if curr_size == prev_size and curr_size > 0:
                    # Size stable — file is ready
                    break
                prev_size = curr_size
                time.sleep(SETTLE_CHECK_INTERVAL)
                elapsed += SETTLE_CHECK_INTERVAL
            else:
                logger.warning("File %s not stable after %ds — quarantining", path.name, int(SETTLE_MAX_WAIT))
                _quarantine_file(path, "size not stable after %ds" % int(SETTLE_MAX_WAIT))
                return

            try:
                self._ingest_file(path)
            except Exception:
                logger.exception("Failed to ingest file: %s", path.name)

        t = threading.Thread(target=_wait_and_ingest, daemon=True)
        t.start()

    def _ingest_file(self, path: Path):
        """Create communication record and start pipeline."""
        from app.db import get_connection
        from app.routers.communications import create_communication

        db = get_connection()
        try:
            # Check for duplicate by file path
            existing = db.execute(
                "SELECT id FROM audio_files WHERE file_path = ?", (str(path),)
            ).fetchone()
            if existing:
                logger.info("Skipping %s — path already registered", path.name)
                return

            # Content-based dedup: check hash of first 1MB + file size
            content_hash = _compute_content_hash(path)
            hash_match = db.execute(
                "SELECT id, file_path FROM audio_files WHERE content_hash = ?",
                (content_hash,)
            ).fetchone()
            if hash_match:
                logger.info("Skipping %s — content matches %s (hash dedup)",
                            path.name, hash_match["file_path"])
                return

            # Determine source from subdirectory name
            source_type = _detect_source(path)

            comm_id = create_communication(
                db=db,
                original_path=path,
                source_type=source_type,
                source_metadata={"ingestion": "watcher", "inbox_path": str(path)},
            )

            logger.info("Watcher: created communication %s from %s", comm_id[:8], path.name)

            # Start pipeline in a new event loop (watcher runs in a thread)
            from app.pipeline.orchestrator import process_communication
            try:
                loop = asyncio.new_event_loop()
                loop.run_until_complete(process_communication(comm_id))
            except Exception as e:
                logger.error("Pipeline failed for watcher-ingested %s: %s", comm_id[:8], e)
            finally:
                loop.close()

        except Exception:
            db.rollback()
            logger.exception("Failed to create communication from %s", path.name)
        finally:
            db.close()


def _detect_source(path: Path) -> str:
    """Detect audio source from subdirectory name."""
    parent = path.parent.name.lower()
    source_map = {
        "pi": "audio_pi",
        "plaud": "audio_plaud",
        "phone": "audio_phone",
        "iphone": "audio_iphone",
    }
    return source_map.get(parent, "audio_inbox")


def _compute_content_hash(path: Path, chunk_size: int = 1024 * 1024) -> str:
    """SHA-256 of first 1MB + file size. Fast content-based dedup."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        h.update(f.read(chunk_size))
    h.update(str(path.stat().st_size).encode())
    return h.hexdigest()


def _quarantine_file(path: Path, reason: str):
    """Move file to _quarantine/ directory with timestamp prefix."""
    quarantine_dir = path.parent.parent / "_quarantine"
    quarantine_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    dest = quarantine_dir / ("%s_%s" % (ts, path.name))
    try:
        shutil.move(str(path), str(dest))
        logger.warning("Quarantined %s → %s (reason: %s)", path.name, dest.name, reason)
    except Exception as e:
        logger.error("Failed to quarantine %s: %s", path.name, e)


class AudioInboxWatcher:
    """Watches the audio inbox directory for new files."""

    def __init__(self, watch_dir: Path):
        self.watch_dir = watch_dir
        self.observer = Observer()
        self.handler = _AudioFileHandler()

    def start(self):
        """Start watching. Creates subdirectories if needed."""
        self.watch_dir.mkdir(parents=True, exist_ok=True)

        # Watch recursively (for pi/, plaud/, phone/ subdirs)
        self.observer.schedule(self.handler, str(self.watch_dir), recursive=True)
        self.observer.start()
        logger.info("Audio inbox watcher started: %s", self.watch_dir)

    def stop(self):
        """Stop watching."""
        self.observer.stop()
        self.observer.join(timeout=5)
        logger.info("Audio inbox watcher stopped")
