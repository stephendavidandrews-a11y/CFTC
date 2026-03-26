"""
Database connection manager for ai.db.
WAL mode, foreign keys ON, Row factory.
"""

import sqlite3
import logging
from pathlib import Path
from contextlib import contextmanager

from app.config import AI_DB_PATH

logger = logging.getLogger(__name__)


def get_connection(db_path: Path = None) -> sqlite3.Connection:
    """Open a SQLite connection with WAL mode and FK enforcement."""
    path = db_path or AI_DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextmanager
def managed_connection(db_path: Path = None):
    """Context manager with auto-commit/rollback."""
    conn = get_connection(db_path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_db():
    """FastAPI dependency that yields a DB connection."""
    conn = get_connection()
    try:
        yield conn
    finally:
        conn.close()
