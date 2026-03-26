"""File watcher for inbox directories.

Monitors inbox/pi/, inbox/plaud/, inbox/phone/ for new audio files.
Creates processing jobs when files appear.
"""

import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

from watchdog.events import FileSystemEventHandler, FileCreatedEvent
from watchdog.observers import Observer

from config import INBOX_PI, INBOX_PLAUD, INBOX_PHONE, SUPPORTED_FORMATS
from db.connection import get_connection

logger = logging.getLogger(__name__)


class AudioInboxHandler(FileSystemEventHandler):
    """Handles new audio files appearing in inbox directories."""

    def __init__(self, source: str, on_new_file=None):
        self.source = source
        self.on_new_file = on_new_file

    def on_created(self, event: FileCreatedEvent):
        if event.is_directory:
            return
        path = Path(event.src_path)
        if path.suffix.lower() not in SUPPORTED_FORMATS:
            return
        logger.info(f"New {self.source} audio file: {path.name}")
        self._register_file(path)

    def _register_file(self, path: Path):
        """Register the audio file in DB and queue for processing."""
        conn = get_connection()
        try:
            existing = conn.execute(
                "SELECT id FROM audio_files WHERE file_path = ?", (str(path),)
            ).fetchone()
            if existing:
                logger.info(f"Skipping {path.name} — already registered")
                return

            conversation_id = str(uuid.uuid4())
            audio_id = str(uuid.uuid4())
            now = datetime.now(timezone.utc).isoformat()
            file_size = path.stat().st_size if path.exists() else None

            conn.execute(
                """INSERT INTO conversations (id, source, file_path, processing_status, created_at)
                   VALUES (?, ?, ?, 'pending', ?)""",
                (conversation_id, self.source, str(path), now),
            )

            conn.execute(
                """INSERT INTO audio_files (id, conversation_id, file_path, original_filename,
                   source, format, file_size_bytes, captured_at, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    audio_id,
                    conversation_id,
                    str(path),
                    path.name,
                    self.source,
                    path.suffix.lstrip("."),
                    file_size,
                    now,
                    now,
                ),
            )

            conn.commit()
            logger.info(f"Registered conversation {conversation_id} from {path.name}")

            if self.on_new_file:
                self.on_new_file(conversation_id, path)

        except Exception:
            conn.rollback()
            logger.exception(f"Failed to register {path.name}")
        finally:
            conn.close()


INBOX_SOURCES = [
    (INBOX_PI, "pi"),
    (INBOX_PLAUD, "plaud"),
    (INBOX_PHONE, "phone"),
]


class InboxWatcher:
    """Watches all inbox directories for new audio files."""

    def __init__(self, on_new_file=None):
        self.observer = Observer()
        self.on_new_file = on_new_file

    def start(self):
        for inbox_dir, source in INBOX_SOURCES:
            inbox_dir.mkdir(parents=True, exist_ok=True)
            handler = AudioInboxHandler(source=source, on_new_file=self.on_new_file)
            self.observer.schedule(handler, str(inbox_dir), recursive=False)
            logger.info(f"Watching {inbox_dir} for {source} audio files")
        self.observer.start()

    def stop(self):
        self.observer.stop()
        self.observer.join()
