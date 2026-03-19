"""File watcher for audio inbox directory.

Monitors audio-inbox/ for new audio files and creates communication records.
Both the watcher and the upload endpoint converge on the same
create_communication() -> process_communication() path.

Adapted from services/intake/voice/pipeline/watcher.py for the AI service.
"""
import asyncio
import logging
import threading
from pathlib import Path

from watchdog.events import FileSystemEventHandler, FileCreatedEvent
from watchdog.observers import Observer

from app.pipeline.stages.preprocessing import ACCEPTED_FORMATS

logger = logging.getLogger(__name__)

# Debounce: wait for file to settle (some sources write in chunks)
SETTLE_SECONDS = 2.0


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
        """Schedule ingestion after a debounce period."""
        # Use a thread to wait, since watchdog runs in its own thread
        def _delayed():
            import time
            time.sleep(SETTLE_SECONDS)
            if not path.exists():
                logger.warning("File disappeared before ingestion: %s", path.name)
                return
            try:
                self._ingest_file(path)
            except Exception:
                logger.exception("Failed to ingest file: %s", path.name)

        t = threading.Thread(target=_delayed, daemon=True)
        t.start()

    def _ingest_file(self, path: Path):
        """Create communication record and start pipeline."""
        from app.db import get_connection
        from app.routers.communications import create_communication

        db = get_connection()
        try:
            # Check for duplicate (same filename already registered)
            existing = db.execute(
                "SELECT id FROM audio_files WHERE file_path = ?", (str(path),)
            ).fetchone()
            if existing:
                logger.info("Skipping %s — already registered", path.name)
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
