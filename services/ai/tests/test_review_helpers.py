"""Tests for shared review helpers and review router wiring.

Part 1: Unit tests for _review_helpers.py
Part 2: Route-level smoke tests proving wrapper wiring works
"""
import os
import sys
import sqlite3
from pathlib import Path
from unittest.mock import patch, AsyncMock, MagicMock

import pytest

SERVICE_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(SERVICE_ROOT))

os.environ.setdefault("APP_ENV", "development")
os.environ.setdefault("AI_DB_PATH", ":memory:")
os.environ.setdefault("AI_AUTH_USER", "")
os.environ.setdefault("AI_AUTH_PASS", "")
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key-not-real")

from fastapi import HTTPException


class FakeRow(dict):
    pass


class FakeDB:
    def __init__(self, rows=None):
        self._rows = rows

    def execute(self, sql, params=None):
        return self

    def fetchone(self):
        if self._rows is None:
            return None
        return FakeRow(self._rows[0]) if self._rows else None


# ---- Part 1: Unit tests ----

class TestCheckReviewState:

    def test_valid_state_does_not_raise(self):
        from app.routers._review_helpers import check_review_state
        db = FakeDB(rows=[{"processing_status": "awaiting_speaker_review"}])
        valid = {"awaiting_speaker_review", "speaker_review_in_progress"}
        check_review_state(db, "comm-123", valid, "speaker review")

    def test_missing_communication_raises_404(self):
        from app.routers._review_helpers import check_review_state
        db = FakeDB(rows=None)
        with pytest.raises(HTTPException) as exc_info:
            check_review_state(db, "nonexistent", {"x"}, "test")
        assert exc_info.value.status_code == 404

    def test_invalid_state_raises_400(self):
        from app.routers._review_helpers import check_review_state
        db = FakeDB(rows=[{"processing_status": "extracting"}])
        with pytest.raises(HTTPException) as exc_info:
            check_review_state(db, "comm-123", {"awaiting_speaker_review"}, "speaker review")
        assert exc_info.value.status_code == 400
        assert "speaker review" in str(exc_info.value.detail)

    def test_error_message_contains_stage_name(self):
        from app.routers._review_helpers import check_review_state
        db = FakeDB(rows=[{"processing_status": "done"}])
        with pytest.raises(HTTPException) as exc_info:
            check_review_state(db, "c", {"awaiting_entity_review"}, "entity review")
        assert "entity review" in str(exc_info.value.detail)


class TestEnsureInProgress:

    @patch("app.routers._review_helpers.cas_transition")
    def test_calls_cas_transition_with_correct_args(self, mock_cas):
        from app.routers._review_helpers import ensure_in_progress
        db = MagicMock()
        ensure_in_progress(db, "comm-456", "awaiting_speaker_review", "speaker_review_in_progress")
        mock_cas.assert_called_once_with(
            db, "comm-456", "awaiting_speaker_review", "speaker_review_in_progress"
        )


class TestResumePipeline:

    @pytest.mark.asyncio
    async def test_calls_process_communication(self):
        with patch("app.pipeline.orchestrator.process_communication", new_callable=AsyncMock) as mock_proc:
            from app.routers._review_helpers import resume_pipeline
            await resume_pipeline("comm-789")
            mock_proc.assert_called_once_with("comm-789")

    @pytest.mark.asyncio
    async def test_swallows_exceptions_and_logs(self):
        with patch("app.pipeline.orchestrator.process_communication", new_callable=AsyncMock) as mock_proc:
            mock_proc.side_effect = RuntimeError("Pipeline failed")
            from app.routers._review_helpers import resume_pipeline
            await resume_pipeline("comm-err")


# ---- Part 2: Route-level smoke tests ----

@pytest.fixture()
def review_db():
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    from app.schema import init_schema
    init_schema(conn)
    for state in ["awaiting_speaker_review", "awaiting_entity_review", "awaiting_participant_review"]:
        comm_id = "test-" + state
        conn.execute(
            "INSERT INTO communications (id, source_type, processing_status, original_filename, created_at, updated_at) "
            "VALUES (?, 'audio', ?, 'test.wav', datetime('now'), datetime('now'))",
            (comm_id, state),
        )
    conn.commit()
    yield conn
    conn.close()


@pytest.fixture()
def review_client(review_db):
    from app.main import app
    from app.db import get_db
    from fastapi.testclient import TestClient
    import app.main as main_mod

    prev_override = app.dependency_overrides.get(get_db)
    prev_ready = main_mod._ready
    app.dependency_overrides[get_db] = lambda: review_db
    main_mod._ready = True  # bypass readiness middleware
    client = TestClient(app, raise_server_exceptions=False)
    yield client
    # Restore previous state
    if prev_override is not None:
        app.dependency_overrides[get_db] = prev_override
    else:
        app.dependency_overrides.pop(get_db, None)
    main_mod._ready = prev_ready


class TestSpeakerReviewWiring:

    def test_queue_returns_200(self, review_client):
        r = review_client.get("/ai/api/speaker-review/queue")
        assert r.status_code == 200

    def test_wrong_state_returns_400_with_stage_name(self, review_client):
        r = review_client.post(
            "/ai/api/speaker-review/test-awaiting_entity_review/link-speaker",
            json={"participant_id": "p1", "tracker_person_id": "t1"},
        )
        assert r.status_code == 400
        assert "speaker review" in r.json()["detail"]["message"]


class TestEntityReviewWiring:

    def test_queue_returns_200(self, review_client):
        r = review_client.get("/ai/api/entity-review/queue")
        assert r.status_code == 200

    def test_wrong_state_returns_400_with_stage_name(self, review_client):
        r = review_client.post(
            "/ai/api/entity-review/test-awaiting_speaker_review/confirm-entity",
            json={"entity_id": "e1"},
        )
        assert r.status_code == 400
        assert "entity review" in r.json()["detail"]["message"]


class TestParticipantReviewWiring:

    def test_queue_returns_200(self, review_client):
        r = review_client.get("/ai/api/participant-review/queue")
        assert r.status_code == 200

    def test_wrong_state_returns_400_with_stage_name(self, review_client):
        r = review_client.post(
            "/ai/api/participant-review/test-awaiting_speaker_review/confirm",
            json={"participant_id": "p1", "tracker_person_id": "t1"},
        )
        assert r.status_code == 400
        assert "participant review" in r.json()["detail"]["message"]
