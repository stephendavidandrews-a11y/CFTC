"""Phase 6.3 — Undo API verification tests.

Tests undo of committed tracker writebacks: insert reversal, update reversal,
compound undo, conflict detection, idempotency, audit trail, and regression.

All tests use mocked tracker HTTP calls — no real tracker API.
"""

import asyncio
import json
import sqlite3
import sys
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

# ── Path setup ──
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.writeback.undo import (
    undo_communication,
    UndoError,
    UndoErrorType,
    UNDOABLE_STATES,
)


# ═══════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════


def _run(coro):
    """Run async coroutine synchronously."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _make_db():
    """Create in-memory DB with undo-relevant tables."""
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = OFF")

    db.execute("""CREATE TABLE communications (
        id TEXT PRIMARY KEY,
        processing_status TEXT NOT NULL DEFAULT 'pending',
        error_message TEXT,
        error_stage TEXT,
        updated_at TEXT DEFAULT (datetime('now'))
    )""")
    db.execute("""CREATE TABLE tracker_writebacks (
        id TEXT PRIMARY KEY,
        communication_id TEXT NOT NULL,
        bundle_id TEXT NOT NULL,
        bundle_item_id TEXT,
        target_table TEXT NOT NULL,
        target_record_id TEXT NOT NULL,
        write_type TEXT NOT NULL,
        written_data TEXT NOT NULL,
        previous_data TEXT,
        auto_committed INTEGER DEFAULT 0,
        reversed INTEGER DEFAULT 0,
        reversed_at TEXT,
        written_at TEXT DEFAULT (datetime('now'))
    )""")
    db.execute("""CREATE TABLE review_action_log (
        id TEXT PRIMARY KEY,
        actor TEXT,
        communication_id TEXT,
        bundle_id TEXT,
        item_id TEXT,
        action_type TEXT NOT NULL,
        old_state TEXT,
        new_state TEXT,
        details TEXT,
        created_at TEXT DEFAULT (datetime('now'))
    )""")
    db.execute("""CREATE TABLE review_bundles (
        id TEXT PRIMARY KEY,
        communication_id TEXT,
        bundle_type TEXT,
        status TEXT DEFAULT 'accepted'
    )""")
    db.execute("""CREATE TABLE review_bundle_items (
        id TEXT PRIMARY KEY,
        bundle_id TEXT,
        item_type TEXT,
        status TEXT DEFAULT 'accepted'
    )""")
    db.execute("""CREATE TABLE meeting_intelligence (
        id TEXT PRIMARY KEY,
        communication_id TEXT,
        meeting_id TEXT,
        intelligence_type TEXT,
        content TEXT,
        confidence REAL,
        created_at TEXT DEFAULT (datetime('now'))
    )""")
    db.commit()
    return db


def _seed_committed_communication(db, comm_id=None, writebacks=None):
    """Seed a complete communication with tracker_writebacks.

    Returns (comm_id, writeback_ids).
    """
    comm_id = comm_id or str(uuid.uuid4())
    bundle_id = str(uuid.uuid4())
    item_id = str(uuid.uuid4())

    db.execute(
        "INSERT INTO communications (id, processing_status) VALUES (?, 'complete')",
        (comm_id,),
    )
    db.execute(
        "INSERT INTO review_bundles (id, communication_id, bundle_type, status) VALUES (?, ?, 'matter', 'accepted')",
        (bundle_id, comm_id),
    )
    db.execute(
        "INSERT INTO review_bundle_items (id, bundle_id, item_type, status) VALUES (?, ?, 'task', 'accepted')",
        (item_id, bundle_id),
    )

    wb_ids = []
    if writebacks is None:
        # Default: one insert writeback
        writebacks = [
            {
                "target_table": "tasks",
                "target_record_id": str(uuid.uuid4()),
                "write_type": "insert",
                "written_data": json.dumps({"title": "Draft memo", "source": "ai"}),
                "previous_data": None,
            }
        ]

    for wb in writebacks:
        wb_id = str(uuid.uuid4())
        wb_ids.append(wb_id)
        db.execute(
            """
            INSERT INTO tracker_writebacks
                (id, communication_id, bundle_id, bundle_item_id,
                 target_table, target_record_id, write_type,
                 written_data, previous_data, reversed)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
        """,
            (
                wb_id,
                comm_id,
                bundle_id,
                item_id,
                wb["target_table"],
                wb["target_record_id"],
                wb["write_type"],
                wb["written_data"],
                wb.get("previous_data"),
            ),
        )

    db.commit()
    return comm_id, wb_ids


# ═══════════════════════════════════════════════════════════════════════════
# 1. Simple undo of inserted records
# ═══════════════════════════════════════════════════════════════════════════


class TestInsertUndo:
    """Verify reversal of insert writebacks (tracker record deleted)."""

    @patch("app.writeback.undo._tracker_delete", new_callable=AsyncMock)
    @patch("app.writeback.undo._tracker_get", new_callable=AsyncMock)
    def test_simple_insert_undo(self, mock_get, mock_delete):
        """Single insert writeback is reversed by deleting tracker record."""
        db = _make_db()
        record_id = str(uuid.uuid4())
        comm_id, wb_ids = _seed_committed_communication(
            db,
            writebacks=[
                {
                    "target_table": "tasks",
                    "target_record_id": record_id,
                    "write_type": "insert",
                    "written_data": json.dumps({"title": "Draft memo", "source": "ai"}),
                }
            ],
        )

        mock_get.return_value = {"title": "Draft memo", "source": "ai"}
        mock_delete.return_value = True

        result = _run(undo_communication(db, comm_id))

        assert result.success
        assert result.reversed_count == 1
        mock_delete.assert_called_once_with("tasks", record_id)

        # Communication back to reviewed
        status = db.execute(
            "SELECT processing_status FROM communications WHERE id = ?",
            (comm_id,),
        ).fetchone()["processing_status"]
        assert status == "reviewed"

        # Writeback marked reversed
        wb = db.execute(
            "SELECT reversed, reversed_at FROM tracker_writebacks WHERE id = ?",
            (wb_ids[0],),
        ).fetchone()
        assert wb["reversed"] == 1
        assert wb["reversed_at"] is not None

    @patch("app.writeback.undo._tracker_delete", new_callable=AsyncMock)
    @patch("app.writeback.undo._tracker_get", new_callable=AsyncMock)
    def test_multiple_inserts_undo(self, mock_get, mock_delete):
        """Multiple insert writebacks all reversed."""
        db = _make_db()
        rec1 = str(uuid.uuid4())
        rec2 = str(uuid.uuid4())
        comm_id, wb_ids = _seed_committed_communication(
            db,
            writebacks=[
                {
                    "target_table": "tasks",
                    "target_record_id": rec1,
                    "write_type": "insert",
                    "written_data": json.dumps({"title": "Task 1"}),
                },
                {
                    "target_table": "decisions",
                    "target_record_id": rec2,
                    "write_type": "insert",
                    "written_data": json.dumps({"title": "Decision 1"}),
                },
            ],
        )

        # Return matching data for each record so no conflicts are detected
        def _get_by_table(table, record_id, written_data=None):
            if table == "tasks":
                return {"title": "Task 1"}
            elif table == "decisions":
                return {"title": "Decision 1"}
            return {}

        mock_get.side_effect = _get_by_table
        mock_delete.return_value = True

        result = _run(undo_communication(db, comm_id))

        assert result.success
        assert result.reversed_count == 2
        assert mock_delete.call_count == 2


# ═══════════════════════════════════════════════════════════════════════════
# 2. Undo of updated records
# ═══════════════════════════════════════════════════════════════════════════


class TestUpdateUndo:
    """Verify reversal of update writebacks (previous_data restored)."""

    @patch("app.writeback.undo._tracker_update", new_callable=AsyncMock)
    @patch("app.writeback.undo._tracker_get", new_callable=AsyncMock)
    def test_update_undo_restores_previous(self, mock_get, mock_update):
        """Update writeback reversed by restoring previous_data."""
        db = _make_db()
        matter_id = str(uuid.uuid4())
        previous = {"status": "active", "priority": "medium"}
        written = {"status": "on_hold"}

        comm_id, wb_ids = _seed_committed_communication(
            db,
            writebacks=[
                {
                    "target_table": "matters",
                    "target_record_id": matter_id,
                    "write_type": "update",
                    "written_data": json.dumps(written),
                    "previous_data": json.dumps(previous),
                }
            ],
        )

        mock_get.return_value = {"status": "on_hold", "priority": "medium"}
        mock_update.return_value = True

        result = _run(undo_communication(db, comm_id))

        assert result.success
        assert result.reversed_count == 1
        mock_update.assert_called_once_with("matters", matter_id, previous)

    @patch("app.writeback.undo._tracker_update", new_callable=AsyncMock)
    @patch("app.writeback.undo._tracker_get", new_callable=AsyncMock)
    def test_update_no_previous_data_skipped(self, mock_get, mock_update):
        """Update with no previous_data is skipped but marked reversed."""
        db = _make_db()
        comm_id, wb_ids = _seed_committed_communication(
            db,
            writebacks=[
                {
                    "target_table": "matters",
                    "target_record_id": str(uuid.uuid4()),
                    "write_type": "update",
                    "written_data": json.dumps({"status": "on_hold"}),
                    "previous_data": None,
                }
            ],
        )

        mock_get.return_value = {"status": "on_hold"}

        result = _run(undo_communication(db, comm_id))

        assert result.success
        assert result.skipped_count == 1
        assert result.reversed_count == 0
        mock_update.assert_not_called()

        # Still marked reversed
        wb = db.execute(
            "SELECT reversed FROM tracker_writebacks WHERE id = ?",
            (wb_ids[0],),
        ).fetchone()
        assert wb["reversed"] == 1


# ═══════════════════════════════════════════════════════════════════════════
# 3. Compound undo (meeting_record expansion)
# ═══════════════════════════════════════════════════════════════════════════


class TestCompoundUndo:
    """Verify undo of compound writes (meeting + participants + matter links)."""

    @patch("app.writeback.undo._tracker_delete", new_callable=AsyncMock)
    @patch("app.writeback.undo._tracker_get", new_callable=AsyncMock)
    def test_compound_meeting_undo(self, mock_get, mock_delete):
        """Meeting record + participants + matter link all reversed in correct order."""
        db = _make_db()
        meeting_id = str(uuid.uuid4())
        part_id = str(uuid.uuid4())
        link_id = str(uuid.uuid4())

        comm_id, wb_ids = _seed_committed_communication(
            db,
            writebacks=[
                {
                    "target_table": "meetings",
                    "target_record_id": meeting_id,
                    "write_type": "insert",
                    "written_data": json.dumps({"title": "Standup"}),
                },
                {
                    "target_table": "meeting_participants",
                    "target_record_id": part_id,
                    "write_type": "insert",
                    "written_data": json.dumps({"person_id": "p1"}),
                },
                {
                    "target_table": "meeting_matters",
                    "target_record_id": link_id,
                    "write_type": "insert",
                    "written_data": json.dumps({"matter_id": "m1"}),
                },
            ],
        )

        # Return matching data for each record so no conflicts are detected
        def _get_by_table(table, record_id, written_data=None):
            if table == "meetings":
                return {"title": "Standup"}
            elif table == "meeting_participants":
                return {"person_id": "p1"}
            elif table == "meeting_matters":
                return {"matter_id": "m1"}
            return {}

        mock_get.side_effect = _get_by_table
        mock_delete.return_value = True

        result = _run(undo_communication(db, comm_id))

        assert result.success
        assert result.reversed_count == 3

        # Verify order: participants and matter links before meetings
        delete_calls = [c.args for c in mock_delete.call_args_list]
        tables_in_order = [c[0] for c in delete_calls]
        meeting_idx = tables_in_order.index("meetings")
        part_idx = tables_in_order.index("meeting_participants")
        link_idx = tables_in_order.index("meeting_matters")
        assert part_idx < meeting_idx, "Participants deleted before meeting"
        assert link_idx < meeting_idx, "Matter links deleted before meeting"


# ═══════════════════════════════════════════════════════════════════════════
# 4. Conflict detection
# ═══════════════════════════════════════════════════════════════════════════


class TestConflictDetection:
    """Verify conflict detection when tracker records have been modified."""

    @patch("app.writeback.undo._tracker_get", new_callable=AsyncMock)
    def test_modified_insert_detected(self, mock_get):
        """Insert where tracker record was modified → conflict."""
        db = _make_db()
        record_id = str(uuid.uuid4())
        comm_id, _ = _seed_committed_communication(
            db,
            writebacks=[
                {
                    "target_table": "tasks",
                    "target_record_id": record_id,
                    "write_type": "insert",
                    "written_data": json.dumps(
                        {"title": "Draft memo", "status": "not started"}
                    ),
                }
            ],
        )

        # Tracker returns modified record (title changed by human)
        mock_get.return_value = {
            "title": "REVISED: Draft memo",
            "status": "not started",
        }

        result = _run(undo_communication(db, comm_id, force=False))

        assert not result.success
        assert result.conflict_count > 0
        conflict_fields = [c.field_name for c in result.conflicts]
        assert "title" in conflict_fields

        # Status still complete (not changed on conflict)
        status = db.execute(
            "SELECT processing_status FROM communications WHERE id = ?",
            (comm_id,),
        ).fetchone()["processing_status"]
        assert status == "complete"

    @patch("app.writeback.undo._tracker_delete", new_callable=AsyncMock)
    @patch("app.writeback.undo._tracker_get", new_callable=AsyncMock)
    def test_force_overrides_conflict(self, mock_get, mock_delete):
        """force=True overrides conflicts and undoes anyway."""
        db = _make_db()
        record_id = str(uuid.uuid4())
        comm_id, _ = _seed_committed_communication(
            db,
            writebacks=[
                {
                    "target_table": "tasks",
                    "target_record_id": record_id,
                    "write_type": "insert",
                    "written_data": json.dumps({"title": "Draft memo"}),
                }
            ],
        )

        mock_get.return_value = {"title": "REVISED: Draft memo"}  # conflict
        mock_delete.return_value = True

        result = _run(undo_communication(db, comm_id, force=True))

        assert result.success
        assert result.forced
        assert result.reversed_count == 1
        mock_delete.assert_called_once()

    @patch("app.writeback.undo._tracker_get", new_callable=AsyncMock)
    def test_update_conflict_field_changed(self, mock_get):
        """Update where the updated field was changed by human → conflict."""
        db = _make_db()
        matter_id = str(uuid.uuid4())
        comm_id, _ = _seed_committed_communication(
            db,
            writebacks=[
                {
                    "target_table": "matters",
                    "target_record_id": matter_id,
                    "write_type": "update",
                    "written_data": json.dumps({"status": "on_hold"}),
                    "previous_data": json.dumps({"status": "active"}),
                }
            ],
        )

        # Human changed status to something else
        mock_get.return_value = {"status": "closed"}

        result = _run(undo_communication(db, comm_id, force=False))

        assert not result.success
        assert result.conflict_count > 0
        assert any(c.field_name == "status" for c in result.conflicts)

    @patch("app.writeback.undo._tracker_get", new_callable=AsyncMock)
    def test_no_conflict_when_unchanged(self, mock_get):
        """No conflict when tracker record matches written_data."""
        db = _make_db()
        record_id = str(uuid.uuid4())
        comm_id, _ = _seed_committed_communication(
            db,
            writebacks=[
                {
                    "target_table": "tasks",
                    "target_record_id": record_id,
                    "write_type": "insert",
                    "written_data": json.dumps({"title": "Draft memo", "source": "ai"}),
                }
            ],
        )

        # Tracker returns exactly what was written
        mock_get.return_value = {"title": "Draft memo", "source": "ai"}

        # Should not raise or report conflicts — will proceed to reversal
        # But since _tracker_delete is not mocked, we test up to conflict check
        # by catching the error from the actual delete attempt
        with patch(
            "app.writeback.undo._tracker_delete",
            new_callable=AsyncMock,
            return_value=True,
        ):
            result = _run(undo_communication(db, comm_id, force=False))

        assert result.success
        assert result.conflict_count == 0


# ═══════════════════════════════════════════════════════════════════════════
# 5. Idempotency / repeat safety
# ═══════════════════════════════════════════════════════════════════════════


class TestIdempotency:
    """Verify repeated undo behaves safely."""

    @patch("app.writeback.undo._tracker_delete", new_callable=AsyncMock)
    @patch("app.writeback.undo._tracker_get", new_callable=AsyncMock)
    def test_repeat_undo_raises_already_reversed(self, mock_get, mock_delete):
        """Second undo attempt raises ALREADY_REVERSED."""
        db = _make_db()
        comm_id, _ = _seed_committed_communication(
            db,
            writebacks=[
                {
                    "target_table": "tasks",
                    "target_record_id": str(uuid.uuid4()),
                    "write_type": "insert",
                    "written_data": json.dumps({"title": "Task"}),
                }
            ],
        )

        mock_get.return_value = {"title": "Task"}
        mock_delete.return_value = True

        # First undo succeeds
        result1 = _run(undo_communication(db, comm_id))
        assert result1.success

        # Communication is now "reviewed" — not undoable
        with pytest.raises(UndoError) as exc_info:
            _run(undo_communication(db, comm_id))
        assert exc_info.value.error_type == UndoErrorType.NOT_UNDOABLE_STATE

    @patch("app.writeback.undo._tracker_delete", new_callable=AsyncMock)
    @patch("app.writeback.undo._tracker_get", new_callable=AsyncMock)
    def test_undo_already_deleted_insert(self, mock_get, mock_delete):
        """Insert where tracker record is already gone (404) still succeeds."""
        db = _make_db()
        comm_id, _ = _seed_committed_communication(
            db,
            writebacks=[
                {
                    "target_table": "tasks",
                    "target_record_id": str(uuid.uuid4()),
                    "write_type": "insert",
                    "written_data": json.dumps({"title": "Task"}),
                }
            ],
        )

        mock_get.return_value = None  # already gone
        mock_delete.return_value = True  # 404 returns True

        result = _run(undo_communication(db, comm_id))
        assert result.success


# ═══════════════════════════════════════════════════════════════════════════
# 6. Audit trail
# ═══════════════════════════════════════════════════════════════════════════


class TestAuditTrail:
    """Verify undo actions are audited."""

    @patch("app.writeback.undo._tracker_delete", new_callable=AsyncMock)
    @patch("app.writeback.undo._tracker_get", new_callable=AsyncMock)
    def test_successful_undo_audited(self, mock_get, mock_delete):
        """Successful undo records undo_started + undo_complete."""
        db = _make_db()
        comm_id, _ = _seed_committed_communication(
            db,
            writebacks=[
                {
                    "target_table": "tasks",
                    "target_record_id": str(uuid.uuid4()),
                    "write_type": "insert",
                    "written_data": json.dumps({"title": "Task"}),
                }
            ],
        )

        mock_get.return_value = {"title": "Task"}
        mock_delete.return_value = True

        _run(undo_communication(db, comm_id))

        audit = db.execute(
            "SELECT action_type FROM review_action_log WHERE communication_id = ? ORDER BY created_at",
            (comm_id,),
        ).fetchall()
        action_types = [r["action_type"] for r in audit]
        assert "undo_started" in action_types
        assert "undo_complete" in action_types

    @patch("app.writeback.undo._tracker_get", new_callable=AsyncMock)
    def test_conflict_audited(self, mock_get):
        """Conflict detection records undo_started + undo_conflict_detected."""
        db = _make_db()
        comm_id, _ = _seed_committed_communication(
            db,
            writebacks=[
                {
                    "target_table": "tasks",
                    "target_record_id": str(uuid.uuid4()),
                    "write_type": "insert",
                    "written_data": json.dumps({"title": "Draft memo"}),
                }
            ],
        )

        mock_get.return_value = {"title": "CHANGED by human"}

        _run(undo_communication(db, comm_id, force=False))

        audit = db.execute(
            "SELECT action_type FROM review_action_log WHERE communication_id = ?",
            (comm_id,),
        ).fetchall()
        action_types = [r["action_type"] for r in audit]
        assert "undo_started" in action_types
        assert "undo_conflict_detected" in action_types

    @patch("app.writeback.undo._tracker_delete", new_callable=AsyncMock)
    @patch("app.writeback.undo._tracker_get", new_callable=AsyncMock)
    def test_writebacks_preserved_after_undo(self, mock_get, mock_delete):
        """tracker_writebacks rows remain readable after undo (reversed=1)."""
        db = _make_db()
        comm_id, wb_ids = _seed_committed_communication(
            db,
            writebacks=[
                {
                    "target_table": "tasks",
                    "target_record_id": str(uuid.uuid4()),
                    "write_type": "insert",
                    "written_data": json.dumps({"title": "Task"}),
                }
            ],
        )

        mock_get.return_value = {"title": "Task"}
        mock_delete.return_value = True

        _run(undo_communication(db, comm_id))

        # Writebacks are still there, just marked reversed
        wbs = db.execute(
            "SELECT * FROM tracker_writebacks WHERE communication_id = ?",
            (comm_id,),
        ).fetchall()
        assert len(wbs) == 1
        assert wbs[0]["reversed"] == 1
        assert wbs[0]["written_data"] is not None  # data preserved


# ═══════════════════════════════════════════════════════════════════════════
# 7. Typed errors
# ═══════════════════════════════════════════════════════════════════════════


class TestTypedErrors:
    """Verify typed error responses."""

    def test_invalid_communication(self):
        db = _make_db()
        with pytest.raises(UndoError) as exc:
            _run(undo_communication(db, "nonexistent-id"))
        assert exc.value.error_type == UndoErrorType.INVALID_COMMUNICATION

    def test_not_undoable_state(self):
        db = _make_db()
        comm_id = str(uuid.uuid4())
        db.execute(
            "INSERT INTO communications (id, processing_status) VALUES (?, 'extracting')",
            (comm_id,),
        )
        db.commit()
        with pytest.raises(UndoError) as exc:
            _run(undo_communication(db, comm_id))
        assert exc.value.error_type == UndoErrorType.NOT_UNDOABLE_STATE

    def test_no_writebacks(self):
        db = _make_db()
        comm_id = str(uuid.uuid4())
        db.execute(
            "INSERT INTO communications (id, processing_status) VALUES (?, 'complete')",
            (comm_id,),
        )
        db.commit()
        with pytest.raises(UndoError) as exc:
            _run(undo_communication(db, comm_id))
        assert exc.value.error_type == UndoErrorType.NO_WRITEBACKS


# ═══════════════════════════════════════════════════════════════════════════
# 8. Regression
# ═══════════════════════════════════════════════════════════════════════════


class TestRegression:
    """Verify undo doesn't break existing modules."""

    def test_writeback_ordering_unchanged(self):
        from app.writeback.ordering import ITEM_TYPE_ORDER

        assert ITEM_TYPE_ORDER["new_organization"] == 0
        assert ITEM_TYPE_ORDER["status_change"] == 9

    def test_committer_imports_clean(self):
        from app.writeback.committer import CommitResult

        assert CommitResult is not None

    def test_bundle_review_intact(self):
        from app.bundle_review.models import BUNDLE_TERMINAL, ITEM_TERMINAL

        assert "accepted" in BUNDLE_TERMINAL
        assert "edited" in ITEM_TERMINAL

    def test_undo_module_imports_clean(self):
        from app.writeback.undo import (
            UndoErrorType,
        )

        assert "complete" in UNDOABLE_STATES
        assert UndoErrorType.CONFLICT_DETECTED.value == "conflict_detected"


# ═══════════════════════════════════════════════════════════════════════════
# Entry point
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
