"""Characterization tests for the pipeline orchestrator.

Exercises the highest-risk control-flow branches in process_communication:
1. Normal flow advancing through stages to a human gate
2. Budget exhaustion -> paused_budget
3. Recoverable LLM error -> retry (with mock sleep)
4. Connection/API error -> waiting_for_api
5. Lock contention -> skip (no duplicate processing)
6. Non-recoverable error -> error state
7. Terminal state -> no-op
"""
import os
import sys
import sqlite3
import uuid
from pathlib import Path
from unittest.mock import patch, AsyncMock

import pytest

SERVICE_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(SERVICE_ROOT))

os.environ.setdefault("APP_ENV", "development")
os.environ.setdefault("AI_DB_PATH", ":memory:")
os.environ.setdefault("AI_AUTH_USER", "")
os.environ.setdefault("AI_AUTH_PASS", "")
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key-not-real")


class _NoCloseConnection:
    """Wraps a SQLite connection, ignoring .close() so the test fixture stays open."""

    def __init__(self, conn):
        self._conn = conn

    def close(self):
        pass  # process_communication calls close(); we ignore it

    def __getattr__(self, name):
        return getattr(self._conn, name)


@pytest.fixture()
def orch_db():
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    from app.schema import init_schema
    init_schema(conn)
    yield conn
    conn.close()


def _db_factory(conn):
    """Returns a factory that produces no-close wrappers around the test connection."""
    return lambda: _NoCloseConnection(conn)


def _insert_comm(db, cid, status="pending", stype="audio"):
    db.execute(
        "INSERT INTO communications "
        "(id, source_type, processing_status, original_filename, "
        "created_at, updated_at) "
        "VALUES (?, ?, ?, 'test.wav', datetime('now'), datetime('now'))",
        (cid, stype, status),
    )
    db.commit()


def _get_status(db, cid):
    row = db.execute(
        "SELECT processing_status, error_message, error_stage "
        "FROM communications WHERE id = ?",
        (cid,),
    ).fetchone()
    return dict(row) if row else None


# ---------- Test 1: Normal flow to human gate ----------

class TestNormalFlow:

    @pytest.mark.asyncio
    @patch("app.pipeline.orchestrator.publish_event", new_callable=AsyncMock)
    @patch("app.pipeline.orchestrator.run_stage", new_callable=AsyncMock)
    async def test_advances_to_human_gate(self, mock_stage, mock_pub, orch_db):
        from app.pipeline.orchestrator import process_communication
        cid = str(uuid.uuid4())
        _insert_comm(orch_db, cid, "pending", "audio")
        mock_stage.side_effect = [
            "preprocessing", "transcribing", "cleaning",
            "awaiting_speaker_review",
        ]
        await process_communication(cid, db_factory=_db_factory(orch_db))
        state = _get_status(orch_db, cid)
        assert state["processing_status"] == "awaiting_speaker_review"
        assert state["error_message"] is None
        assert mock_stage.call_count == 4

    @pytest.mark.asyncio
    @patch("app.pipeline.orchestrator.publish_event", new_callable=AsyncMock)
    @patch("app.pipeline.orchestrator.run_stage", new_callable=AsyncMock)
    async def test_terminal_state_is_noop(self, mock_stage, mock_pub, orch_db):
        from app.pipeline.orchestrator import process_communication
        cid = str(uuid.uuid4())
        _insert_comm(orch_db, cid, "complete", "audio")
        await process_communication(cid, db_factory=_db_factory(orch_db))
        assert mock_stage.call_count == 0


# ---------- Test 2: Budget exhaustion -> paused_budget ----------

class TestBudgetExhaustion:

    @pytest.mark.asyncio
    @patch("app.pipeline.orchestrator.publish_event", new_callable=AsyncMock)
    @patch("app.pipeline.orchestrator.run_stage", new_callable=AsyncMock)
    async def test_budget_exceeded_pauses(self, mock_stage, mock_pub, orch_db):
        from app.pipeline.orchestrator import process_communication
        from app.llm.client import BudgetExceededError
        cid = str(uuid.uuid4())
        _insert_comm(orch_db, cid, "extracting", "audio")
        mock_stage.side_effect = BudgetExceededError(10.0, 10.0)
        await process_communication(cid, db_factory=_db_factory(orch_db))
        state = _get_status(orch_db, cid)
        assert state["processing_status"] == "paused_budget"
        assert "budget" in state["error_message"].lower()
        assert state["error_stage"] == "extracting"


# ---------- Test 3: Recoverable LLM error -> retry ----------

class TestRecoverableRetry:

    @pytest.mark.asyncio
    @patch("app.pipeline.orchestrator.asyncio.sleep", new_callable=AsyncMock)
    @patch("app.pipeline.orchestrator.publish_event", new_callable=AsyncMock)
    @patch("app.pipeline.orchestrator.run_stage", new_callable=AsyncMock)
    async def test_retries_then_succeeds(self, mock_stage, mock_pub, mock_sleep, orch_db):
        from app.pipeline.orchestrator import process_communication
        from app.llm.client import LLMError
        cid = str(uuid.uuid4())
        _insert_comm(orch_db, cid, "extracting", "audio")
        mock_stage.side_effect = [
            LLMError("overloaded", error_type="overloaded", recoverable=True),
            "awaiting_bundle_review",
        ]
        await process_communication(cid, db_factory=_db_factory(orch_db))
        state = _get_status(orch_db, cid)
        assert state["processing_status"] == "awaiting_bundle_review"
        assert mock_sleep.called
        assert mock_stage.call_count == 2

    @pytest.mark.asyncio
    @patch("app.pipeline.orchestrator.asyncio.sleep", new_callable=AsyncMock)
    @patch("app.pipeline.orchestrator.publish_event", new_callable=AsyncMock)
    @patch("app.pipeline.orchestrator.run_stage", new_callable=AsyncMock)
    async def test_exhausts_retries_to_error(self, mock_stage, mock_pub, mock_sleep, orch_db):
        from app.pipeline.orchestrator import process_communication
        from app.llm.client import LLMError
        cid = str(uuid.uuid4())
        _insert_comm(orch_db, cid, "extracting", "audio")
        err = LLMError("overloaded", error_type="overloaded", recoverable=True)
        mock_stage.side_effect = [err, err, err, err]
        await process_communication(cid, db_factory=_db_factory(orch_db))
        state = _get_status(orch_db, cid)
        assert state["processing_status"] == "error"
        assert mock_stage.call_count == 4


# ---------- Test 4: Connection errors ----------

class TestConnectionError:

    @pytest.mark.asyncio
    @patch("app.pipeline.orchestrator.publish_event", new_callable=AsyncMock)
    @patch("app.pipeline.orchestrator.run_stage", new_callable=AsyncMock)
    async def test_llm_connection_to_waiting(self, mock_stage, mock_pub, orch_db):
        from app.pipeline.orchestrator import process_communication
        from app.llm.client import LLMError
        cid = str(uuid.uuid4())
        _insert_comm(orch_db, cid, "cleaning", "audio")
        mock_stage.side_effect = LLMError(
            "refused", error_type="connection_error", recoverable=False,
        )
        await process_communication(cid, db_factory=_db_factory(orch_db))
        state = _get_status(orch_db, cid)
        assert state["processing_status"] == "waiting_for_api"
        assert state["error_stage"] == "cleaning"

    @pytest.mark.asyncio
    @patch("app.pipeline.orchestrator.publish_event", new_callable=AsyncMock)
    @patch("app.pipeline.orchestrator.run_stage", new_callable=AsyncMock)
    async def test_tracker_error_to_awaiting(self, mock_stage, mock_pub, orch_db):
        from app.pipeline.orchestrator import process_communication
        from app.writeback.tracker_client import TrackerBatchError
        cid = str(uuid.uuid4())
        _insert_comm(orch_db, cid, "committing", "audio")
        mock_stage.side_effect = TrackerBatchError(
            0, "connection_error", "tracker down",
        )
        await process_communication(cid, db_factory=_db_factory(orch_db))
        state = _get_status(orch_db, cid)
        assert state["processing_status"] == "awaiting_tracker"
        assert state["error_stage"] == "committing"


# ---------- Test 5: Lock contention ----------

class TestLockContention:

    @pytest.mark.asyncio
    @patch("app.pipeline.orchestrator.publish_event", new_callable=AsyncMock)
    @patch("app.pipeline.orchestrator.run_stage", new_callable=AsyncMock)
    async def test_locked_comm_is_skipped(self, mock_stage, mock_pub, orch_db):
        from app.pipeline.orchestrator import (
            process_communication, acquire_processing_lock,
        )
        cid = str(uuid.uuid4())
        _insert_comm(orch_db, cid, "pending", "audio")
        token = acquire_processing_lock(orch_db, cid)
        assert token is not None
        await process_communication(cid, db_factory=_db_factory(orch_db))
        assert mock_stage.call_count == 0


# ---------- Test 6: Non-recoverable error ----------

class TestNonRecoverableError:

    @pytest.mark.asyncio
    @patch("app.pipeline.orchestrator.publish_event", new_callable=AsyncMock)
    @patch("app.pipeline.orchestrator.run_stage", new_callable=AsyncMock)
    async def test_generic_exception_to_error(self, mock_stage, mock_pub, orch_db):
        from app.pipeline.orchestrator import process_communication
        cid = str(uuid.uuid4())
        _insert_comm(orch_db, cid, "preprocessing", "audio")
        mock_stage.side_effect = RuntimeError("Disk full")
        await process_communication(cid, db_factory=_db_factory(orch_db))
        state = _get_status(orch_db, cid)
        assert state["processing_status"] == "error"
        assert "Disk full" in state["error_message"]
        assert state["error_stage"] == "preprocessing"
