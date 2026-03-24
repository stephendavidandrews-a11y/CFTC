"""Shared pytest fixtures for AI service tests.

Provides:
- `db`: in-memory SQLite with full schema
- `client`: FastAPI TestClient with DB override (auth disabled)

Existing test files create their own DBs at module level, so these
fixtures only activate when explicitly requested via function args.
"""
import os
import sys
import sqlite3
from pathlib import Path

import pytest

# Ensure AI service root is on sys.path
SERVICE_ROOT = Path(__file__).parent.parent
AI_SERVICE = SERVICE_ROOT  # Already at services/ai level when deployed
sys.path.insert(0, str(AI_SERVICE))

# Must set env vars before importing app modules
os.environ.setdefault("APP_ENV", "development")
os.environ.setdefault("AI_DB_PATH", ":memory:")
os.environ.setdefault("AI_AUTH_USER", "")
os.environ.setdefault("AI_AUTH_PASS", "")
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key-not-real")


@pytest.fixture()
def db():
    """Yield an in-memory SQLite connection with full AI schema."""
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    from app.schema import init_schema
    init_schema(conn)
    yield conn
    conn.close()


_SENTINEL = object()


@pytest.fixture()
def client(db):
    """FastAPI TestClient with the in-memory DB injected.

    Auth is disabled because AI_AUTH_USER / AI_AUTH_PASS are empty.
    Saves and restores any pre-existing get_db override so that
    existing test modules that set their own overrides are not affected.

    IMPORTANT: The TestClient context manager triggers the app lifespan,
    which sets the module-level _ready flag in app.main. On exit, the
    lifespan sets _ready = False. We must restore it afterward so that
    test files running later (e.g., test_bundle_review.py with its own
    module-level TestClient) are not poisoned by a stale _ready = False.
    """
    from app.main import app
    from app.db import get_db
    from fastapi.testclient import TestClient

    previous = app.dependency_overrides.get(get_db, _SENTINEL)

    def _override_db():
        return db

    app.dependency_overrides[get_db] = _override_db
    with TestClient(app) as c:
        yield c

    # Restore the readiness flag that the lifespan shutdown cleared.
    # Without this, any later test module using a shared TestClient
    # will see _ready=False and the readiness middleware will 503.
    import app.main as _main_mod
    _main_mod._ready = True

    # Restore previous dependency override state
    if previous is _SENTINEL:
        app.dependency_overrides.pop(get_db, None)
    else:
        app.dependency_overrides[get_db] = previous
