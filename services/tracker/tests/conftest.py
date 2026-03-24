"""
Shared test fixtures for the CFTC Tracker service.

Provides:
  - In-memory SQLite DB with full schema
  - FastAPI TestClient with auth
  - Factory functions for creating test entities
"""
import sqlite3
import uuid
from datetime import datetime

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Database fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def db():
    """In-memory SQLite database with full tracker schema."""
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")

    from app.schema import init_schema, migrate_schema

    init_schema(conn)
    migrate_schema(conn)
    yield conn
    conn.close()


@pytest.fixture
def client(db):
    """FastAPI TestClient wired to the in-memory DB, with valid auth."""
    import os

    os.environ["TRACKER_USER"] = "testuser"
    os.environ["TRACKER_PASS"] = "testpass"

    from app.main import app
    from app.db import get_db

    def override_get_db():
        try:
            yield db
        finally:
            pass  # Don't close -- fixture manages lifecycle

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def auth_headers():
    """HTTP Basic auth headers for test requests."""
    import base64

    creds = base64.b64encode(b"testuser:testpass").decode()
    return {"Authorization": f"Basic {creds}"}


@pytest.fixture
def unauth_headers():
    """No auth -- for testing 401 responses."""
    return {}


# ---------------------------------------------------------------------------
# Factory helpers
# ---------------------------------------------------------------------------


def make_id() -> str:
    return str(uuid.uuid4())


def seed_organization(db, **overrides) -> dict:
    """Insert an organization and return its dict."""
    org = {
        "id": make_id(),
        "name": "Test Organization",
        "short_name": "TestOrg",
        "organization_type": "Federal agency",
        "is_active": 1,
        "source": "manual",
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
    }
    org.update(overrides)
    db.execute(
        """INSERT INTO organizations (id, name, short_name, organization_type,
           is_active, source, created_at, updated_at)
           VALUES (:id, :name, :short_name, :organization_type,
           :is_active, :source, :created_at, :updated_at)""",
        org,
    )
    db.commit()
    return org


def seed_person(db, **overrides) -> dict:
    """Insert a person and return its dict."""
    person = {
        "id": make_id(),
        "full_name": "Jane Doe",
        "first_name": "Jane",
        "last_name": "Doe",
        "title": "Director",
        "is_active": 1,
        "source": "manual",
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
    }
    person.update(overrides)
    cols = ", ".join(person.keys())
    placeholders = ", ".join(f":{k}" for k in person.keys())
    db.execute(f"INSERT INTO people ({cols}) VALUES ({placeholders})", person)
    db.commit()
    return person


def seed_matter(db, **overrides) -> dict:
    """Insert a matter and return its dict."""
    matter = {
        "id": make_id(),
        "matter_number": f"MAT-2026-{uuid.uuid4().hex[:4].upper()}",
        "title": "Test Matter",
        "matter_type": "rulemaking",
        "status": "framing issue",
        "priority": "important this month",
        "sensitivity": "routine",
        "boss_involvement_level": "keep boss informed",
        "next_step": "Draft initial proposal",
        "source": "manual",
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
    }
    matter.update(overrides)
    cols = ", ".join(matter.keys())
    placeholders = ", ".join(f":{k}" for k in matter.keys())
    db.execute(f"INSERT INTO matters ({cols}) VALUES ({placeholders})", matter)
    db.commit()
    return matter


def seed_task(db, matter_id: str, **overrides) -> dict:
    """Insert a task linked to a matter and return its dict."""
    task = {
        "id": make_id(),
        "matter_id": matter_id,
        "title": "Test Task",
        "status": "not started",
        "task_mode": "action",
        "priority": "normal",
        "source": "manual",
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
    }
    task.update(overrides)
    cols = ", ".join(task.keys())
    placeholders = ", ".join(f":{k}" for k in task.keys())
    db.execute(f"INSERT INTO tasks ({cols}) VALUES ({placeholders})", task)
    db.commit()
    return task


def seed_meeting(db, **overrides) -> dict:
    """Insert a meeting and return its dict."""
    meeting = {
        "id": make_id(),
        "title": "Test Meeting",
        "meeting_type": "internal working meeting",
        "date_time_start": datetime.now().isoformat(),
        "source": "manual",
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
    }
    meeting.update(overrides)
    cols = ", ".join(meeting.keys())
    placeholders = ", ".join(f":{k}" for k in meeting.keys())
    db.execute(f"INSERT INTO meetings ({cols}) VALUES ({placeholders})", meeting)
    db.commit()
    return meeting


def seed_document(db, matter_id: str, **overrides) -> dict:
    """Insert a document and return its dict."""
    doc = {
        "id": make_id(),
        "matter_id": matter_id,
        "title": "Test Document",
        "document_type": "legal_memo",
        "status": "drafting",
        "source": "manual",
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
    }
    doc.update(overrides)
    cols = ", ".join(doc.keys())
    placeholders = ", ".join(f":{k}" for k in doc.keys())
    db.execute(f"INSERT INTO documents ({cols}) VALUES ({placeholders})", doc)
    db.commit()
    return doc


def seed_decision(db, matter_id: str, **overrides) -> dict:
    """Insert a decision and return its dict."""
    dec = {
        "id": make_id(),
        "matter_id": matter_id,
        "title": "Test Decision",
        "decision_type": "policy",
        "status": "pending",
        "source": "manual",
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
    }
    dec.update(overrides)
    cols = ", ".join(dec.keys())
    placeholders = ", ".join(f":{k}" for k in dec.keys())
    db.execute(f"INSERT INTO decisions ({cols}) VALUES ({placeholders})", dec)
    db.commit()
    return dec
