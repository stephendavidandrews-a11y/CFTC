"""SQLite connection manager for the Comment Analysis System."""

import sqlite3
import asyncio
import logging
from functools import partial
from pathlib import Path

logger = logging.getLogger(__name__)

# Database lives next to the app in a data/ directory
DB_PATH = Path(__file__).parent.parent.parent / "data" / "comments.db"


def get_connection(db_path: Path = None) -> sqlite3.Connection:
    path = db_path or DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


async def run_db(func, *args, **kwargs):
    """Run a synchronous DB function in a thread executor."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, partial(func, *args, **kwargs))
