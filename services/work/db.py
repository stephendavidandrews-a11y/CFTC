"""
Database connection manager for the Work Management module.
Mirrors the pipeline connection pattern.
"""

import sqlite3
from pathlib import Path
from contextlib import contextmanager

from app.work.config import WORK_DB_PATH, PIPELINE_DB_PATH


def get_connection(db_path: Path = None) -> sqlite3.Connection:
    """Open a SQLite connection with WAL mode and FK enforcement."""
    path = db_path or WORK_DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextmanager
def managed_connection(db_path: Path = None):
    """Context manager that opens, yields, commits, and closes a connection."""
    conn = get_connection(db_path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def attach_pipeline(conn: sqlite3.Connection):
    """Attach pipeline.db so we can query team_members."""
    if PIPELINE_DB_PATH.exists():
        conn.execute(f"ATTACH DATABASE '{PIPELINE_DB_PATH}' AS pipeline")
