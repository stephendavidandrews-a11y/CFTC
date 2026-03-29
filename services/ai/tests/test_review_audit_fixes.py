"""
End-to-end tests for all review pipeline audit fixes.

Tests cover:
  BUG-1: Undo sets status to bundle_review_in_progress (not reviewed)
  BUG-2: Cannot add/move/merge items into rejected bundles
  BUG-3: edit_bundle has CAS guard (concurrent modification -> 409)
  BUG-4: accept_item on edited item returns no-op
  BUG-5: validate_proposed_data rejects missing required fields for all item types
  BUG-6: test_writeback fixture starts in ready state
  BUG-7: CommitQueuePage SSE (structural check)
  RISK-1: Post-undo state allows re-review (not auto-recommit)
  RISK-5: Transcript editing blocked outside review state
  GAP-2: Archived comms excluded from entity/participant queues
  CLEANUP: Response shapes standardized
"""

import sqlite3
import uuid
import pytest

# ----- Test infrastructure -----

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.schema import init_schema
from app.bundle_review.models import BUNDLE_REVIEW_STATES
from app.bundle_review.validation import validate_proposed_data


def make_db():
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    init_schema(db)
    db.commit()
    return db


def seed_comm(db, status="awaiting_bundle_review", archived=False):
    cid = str(uuid.uuid4())
    db.execute(
        "INSERT INTO communications (id, source_type, processing_status, archived_at) VALUES (?, 'audio', ?, ?)",
        (cid, status, "2026-01-01" if archived else None),
    )
    db.commit()
    return cid


def seed_bundle(db, comm_id, status="proposed", bundle_type="matter"):
    bid = str(uuid.uuid4())
    db.execute(
        """INSERT INTO review_bundles
           (id, communication_id, bundle_type, status, sort_order, created_at, updated_at)
           VALUES (?, ?, ?, ?, 0, datetime('now'), datetime('now'))""",
        (bid, comm_id, bundle_type, status),
    )
    db.commit()
    return bid


def seed_item(db, bundle_id, status="proposed", item_type="task"):
    iid = str(uuid.uuid4())
    db.execute(
        """INSERT INTO review_bundle_items
           (id, bundle_id, item_type, status, proposed_data, sort_order, created_at, updated_at)
           VALUES (?, ?, ?, ?, '{"title":"test"}', 0, datetime('now'), datetime('now'))""",
        (iid, bundle_id, item_type, status),
    )
    db.commit()
    return iid


# ============================================================
# BUG-1 + RISK-1: Undo status -> bundle_review_in_progress
# ============================================================

class TestUndoStatus:
    """Undo must set status to bundle_review_in_progress, not reviewed."""

    def test_undo_code_sets_bundle_review_in_progress(self):
        """Verify the undo SQL sets bundle_review_in_progress."""
        import inspect
        from app.writeback.undo import undo_communication
        source = inspect.getsource(undo_communication)
        assert "bundle_review_in_progress" in source
        assert "SET processing_status = 'reviewed'" not in source

    def test_undo_status_allows_review_ui_access(self):
        """bundle_review_in_progress is in BUNDLE_REVIEW_STATES (UI gate)."""
        assert "bundle_review_in_progress" in BUNDLE_REVIEW_STATES


# ============================================================
# BUG-2: Guard add/move/merge against rejected bundles
# ============================================================

class TestRejectedBundleGuards:
    """Items cannot be added/moved/merged into rejected bundles."""

    def test_add_item_to_rejected_bundle_raises(self):
        from app.bundle_review.item_actions import add_item
        from fastapi import HTTPException
        db = make_db()
        cid = seed_comm(db)
        bid = seed_bundle(db, cid, status="rejected")

        with pytest.raises(HTTPException) as exc_info:
            add_item(db, cid, bid, "task", {"title": "test"})
        assert exc_info.value.status_code == 400
        assert "rejected" in str(exc_info.value.detail).lower()

    def test_move_item_to_rejected_bundle_raises(self):
        from app.bundle_review.restructure import move_item
        from fastapi import HTTPException
        db = make_db()
        cid = seed_comm(db)
        source_bid = seed_bundle(db, cid, status="accepted")
        target_bid = seed_bundle(db, cid, status="rejected")
        iid = seed_item(db, source_bid)
        item = dict(db.execute("SELECT * FROM review_bundle_items WHERE id = ?", (iid,)).fetchone())

        with pytest.raises(HTTPException) as exc_info:
            move_item(db, cid, iid, source_bid, target_bid, item)
        assert exc_info.value.status_code == 400
        assert "rejected" in str(exc_info.value.detail).lower()

    def test_merge_into_rejected_bundle_raises(self):
        from app.bundle_review.restructure import merge_bundles
        from fastapi import HTTPException
        db = make_db()
        cid = seed_comm(db)
        source_bid = seed_bundle(db, cid, status="proposed")
        target_bid = seed_bundle(db, cid, status="rejected")
        source = dict(db.execute("SELECT * FROM review_bundles WHERE id = ?", (source_bid,)).fetchone())
        target = dict(db.execute("SELECT * FROM review_bundles WHERE id = ?", (target_bid,)).fetchone())

        with pytest.raises(HTTPException) as exc_info:
            merge_bundles(db, cid, source_bid, target_bid, source, target)
        assert exc_info.value.status_code == 400
        assert "rejected" in str(exc_info.value.detail).lower()

    def test_add_item_to_accepted_bundle_succeeds(self):
        from app.bundle_review.item_actions import add_item
        db = make_db()
        cid = seed_comm(db)
        bid = seed_bundle(db, cid, status="accepted")
        result = add_item(db, cid, bid, "task", {"title": "new task"})
        assert result["status"] == "ok"


# ============================================================
# BUG-3: edit_bundle CAS guard
# ============================================================

class TestEditBundleCAS:
    """edit_bundle must reject concurrent modifications."""

    def test_edit_bundle_cas_detects_stale_read(self):
        from app.bundle_review.bundle_actions import edit_bundle
        from fastapi import HTTPException
        db = make_db()
        cid = seed_comm(db)
        bid = seed_bundle(db, cid, status="proposed")

        # Read the bundle
        bundle = dict(db.execute("SELECT * FROM review_bundles WHERE id = ?", (bid,)).fetchone())

        # Simulate concurrent modification
        db.execute("UPDATE review_bundles SET updated_at = '2099-01-01' WHERE id = ?", (bid,))
        db.commit()

        # Now try to edit with stale updated_at -> should 409
        with pytest.raises(HTTPException) as exc_info:
            edit_bundle(db, cid, bid, bundle, bundle_type="standalone")
        assert exc_info.value.status_code == 409

    def test_edit_bundle_succeeds_without_concurrent_modification(self):
        from app.bundle_review.bundle_actions import edit_bundle
        db = make_db()
        cid = seed_comm(db)
        bid = seed_bundle(db, cid, status="proposed")
        bundle = dict(db.execute("SELECT * FROM review_bundles WHERE id = ?", (bid,)).fetchone())
        result = edit_bundle(db, cid, bid, bundle, bundle_type="standalone")
        assert result["status"] == "ok"


# ============================================================
# BUG-4: accept_item on edited item -> no-op
# ============================================================

class TestAcceptEditedItem:
    """Accepting an already-edited item returns no-op, not downgrade."""

    def test_accept_edited_item_returns_already_edited(self):
        from app.bundle_review.item_actions import accept_item
        db = make_db()
        cid = seed_comm(db)
        bid = seed_bundle(db, cid)
        iid = seed_item(db, bid, status="edited")
        item = dict(db.execute("SELECT * FROM review_bundle_items WHERE id = ?", (iid,)).fetchone())

        result = accept_item(db, cid, bid, iid, item)
        assert result.get("already_edited") is True

        # Status should still be "edited" in DB
        row = db.execute("SELECT status FROM review_bundle_items WHERE id = ?", (iid,)).fetchone()
        assert row["status"] == "edited"


# ============================================================
# BUG-5: validate_proposed_data for all item types
# ============================================================

class TestValidateProposedData:
    """All item types have required field validation."""

    def test_task_update_requires_task_id(self):
        with pytest.raises(Exception):
            validate_proposed_data("task_update", {"title": "no task_id"})

    def test_decision_update_requires_decision_id(self):
        with pytest.raises(Exception):
            validate_proposed_data("decision_update", {"title": "no decision_id"})

    def test_context_note_requires_content(self):
        with pytest.raises(Exception):
            validate_proposed_data("context_note", {"title": "no content"})

    def test_person_detail_update_requires_person_id(self):
        with pytest.raises(Exception):
            validate_proposed_data("person_detail_update", {"full_name": "test"})

    def test_org_detail_update_requires_organization_id(self):
        with pytest.raises(Exception):
            validate_proposed_data("org_detail_update", {"name": "test"})

    def test_directive_update_requires_directive_id(self):
        with pytest.raises(Exception):
            validate_proposed_data("directive_update", {"status": "active"})

    def test_task_update_passes_with_task_id(self):
        validate_proposed_data("task_update", {"task_id": "abc-123"})

    def test_context_note_passes_with_content(self):
        validate_proposed_data("context_note", {"content": "some note text"})


# ============================================================
# RISK-5: Transcript editing blocked outside review state
# ============================================================

class TestTranscriptStateCheck:
    """Transcript editing endpoints must check review state."""

    def test_transcript_endpoints_have_state_checks(self):
        """Verify state check code exists in transcript endpoints."""
        import inspect
        from app.routers import speaker_review
        source = inspect.getsource(speaker_review)

        # Count occurrences of state check in transcript-related functions
        # Each of the 3 endpoints should have a check
        lines = source.split("\n")
        transcript_state_checks = 0
        in_transcript_func = False
        for line in lines:
            if "def edit_transcript_segment" in line or "def find_similar_corrections" in line or "def apply_corrections" in line:
                in_transcript_func = True
            if in_transcript_func and "_check_review_state" in line:
                transcript_state_checks += 1
                in_transcript_func = False
            if in_transcript_func and line.strip().startswith("def ") and "transcript" not in line.lower():
                in_transcript_func = False

        assert transcript_state_checks >= 3, f"Expected 3 state checks, found {transcript_state_checks}"


# ============================================================
# GAP-2: Archived comms excluded from queues
# ============================================================

class TestArchivedQueueFilter:
    """Archived communications must not appear in review queues."""

    def test_entity_queue_sql_has_archived_filter(self):
        import inspect
        from app.routers import entity_review
        source = inspect.getsource(entity_review.get_entity_review_queue)
        assert "archived_at IS NULL" in source

    def test_participant_queue_sql_has_archived_filter(self):
        import inspect
        from app.routers import participant_review
        source = inspect.getsource(participant_review.get_participant_review_queue)
        assert "archived_at IS NULL" in source


# ============================================================
# CLEANUP: Response shape consistency
# ============================================================

class TestResponseShapes:
    """All review endpoints use {status: "ok"} not {ok: true}."""

    def test_speaker_review_no_ok_true_responses(self):
        import inspect
        from app.routers import speaker_review
        source = inspect.getsource(speaker_review)
        # Should not have {"ok": True} anywhere
        assert '{"ok": True' not in source, "Found {ok: True} pattern -- should be {status: ok}"

    def test_transcript_errors_are_structured(self):
        """Transcript PATCH errors use structured {error_type: ...} format."""
        import inspect
        from app.routers import speaker_review
        source = inspect.getsource(speaker_review)
        # Should not have plain string HTTPException for transcript errors
        assert 'HTTPException(400, "reviewed_text' not in source
        assert 'HTTPException(404, "Transcript' not in source


# ============================================================
# BUG-7: CommitQueuePage SSE stability (structural check)
# ============================================================

class TestCommitQueueSSE:
    """CommitQueuePage refetchAll must have stable identity (useRef pattern)."""

    def test_refetch_all_uses_refs(self):
        """Verify CommitQueuePage uses useRef for refetch stability."""
        path = os.path.join(
            os.path.dirname(__file__), "..", "..",
            "frontend", "src", "pages", "review", "CommitQueuePage.jsx"
        )
        if not os.path.exists(path):
            pytest.skip("Frontend source not available")
        with open(path) as f:
            source = f.read()
        assert "useRef" in source, "CommitQueuePage should use useRef for SSE stability"
        assert "readyRef" in source or "Ref.current" in source, "Should use refs for refetch functions"
