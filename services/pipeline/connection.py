"""
Database connection manager for the Pipeline module.

Provides SQLite connections matching the existing Stage 1 pattern:
WAL mode, foreign keys enforced, Row factory for dict-like access.

The pipeline module uses its OWN database (pipeline.db), separate from
cftc_regulatory.db. Read-only connections to cftc_regulatory.db and
eo_tracker.db are available for cross-database queries.
"""

import sqlite3
from pathlib import Path
from contextlib import contextmanager

from app.pipeline.config import (
    PIPELINE_DB_PATH,
    CFTC_REGULATORY_DB_PATH,
    EO_TRACKER_DB_PATH,
)


def get_connection(db_path: Path = None) -> sqlite3.Connection:
    """
    Open or create a SQLite connection with WAL mode and FK enforcement.

    Args:
        db_path: Path to the SQLite database file.
                 Defaults to pipeline.db.

    Returns:
        sqlite3.Connection with Row factory enabled.
        Caller is responsible for closing.
    """
    path = db_path or PIPELINE_DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextmanager
def managed_connection(db_path: Path = None):
    """
    Context manager that opens, yields, commits, and closes a connection.

    Usage:
        with managed_connection() as conn:
            conn.execute("SELECT ...")
    """
    conn = get_connection(db_path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_readonly_regulatory_connection() -> sqlite3.Connection:
    """Open a read-only connection to cftc_regulatory.db."""
    if not CFTC_REGULATORY_DB_PATH.exists():
        raise FileNotFoundError(
            f"cftc_regulatory.db not found at: {CFTC_REGULATORY_DB_PATH}"
        )
    uri = f"file:{CFTC_REGULATORY_DB_PATH}?mode=ro&immutable=1"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def get_readonly_eo_connection() -> sqlite3.Connection:
    """Open a read-only connection to eo_tracker.db."""
    if not EO_TRACKER_DB_PATH.exists():
        raise FileNotFoundError(
            f"eo_tracker.db not found at: {EO_TRACKER_DB_PATH}"
        )
    uri = f"file:{EO_TRACKER_DB_PATH}?mode=ro&immutable=1"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn
