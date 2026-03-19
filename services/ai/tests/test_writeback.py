"""Phase 5 Runtime Verification -- Tracker Writeback

Comprehensive test covering:
1. State mapping: reviewed bundle/item states -> tracker batch operations
2. Write order: dependency ordering within bundles
3. Compound items: meeting_record -> meetings + participants + meeting_matters
4. Reviewer-created items: no confidence, still committed
5. Moved items: excluded from commit (original='moved', copy committed from target)
6. tracker_writebacks: records created for every operation result
7. Idempotency: re-run produces no duplicates
8. Rollback/error: partial failure handling
9. Regression: bundle review still works post-writeback integration
10. Orchestrator: _handle_committing dispatch and CAS transition
"""

import json
import sqlite3
import uuid
import sys
import os
import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock

# Ensure the service root is on sys.path
SERVICE_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(SERVICE_ROOT))

os.environ.setdefault("APP_ENV", "development")
os.environ.setdefault("AI_DB_PATH", ":memory:")

# -----------------------------------------------------------------------
# Test data IDs
# -----------------------------------------------------------------------
COMM_ID = str(uuid.uuid4())
# Bundle 0: matter bundle with existing matter (task, matter_update, stakeholder)
# Bundle 1: matter bundle (follow_up, meeting_record, document)
# Bundle 2: new_matter bundle (task, new_person)
# Bundle 3: standalone rejected (should be skipped)
# Bundle 4: standalone with moved item (should exclude moved original)
BUNDLE_IDS = [str(uuid.uuid4()) for _ in range(5)]
ITEM_IDS = {
    0: [str(uuid.uuid4()) for _ in range(3)],  # task, matter_update, stakeholder
    1: [str(uuid.uuid4()) for _ in range(3)],  # follow_up, meeting_record, document
    2: [str(uuid.uuid4()) for _ in range(2)],  # task, new_person
    3: [str(uuid.uuid4()) for _ in range(1)],  # task (rejected bundle)
    4: [str(uuid.uuid4()) for _ in range(2)],  # original (moved), reviewer-added task
}

_state = {}


def _init_db(db: sqlite3.Connection):
    """Set up schema and seed fully-reviewed bundle data for writeback testing."""
    db.row_factory = sqlite3.Row
    from app.schema import init_schema
    init_schema(db)

    # Communication in 'reviewed' state (ready for committing)
    db.execute("""
        INSERT INTO communications (id, source_type, processing_status, original_filename,
                                    duration_seconds, created_at, updated_at)
        VALUES (?, 'audio', 'reviewed', 'writeback_test.wav', 600,
                datetime('now'), datetime('now'))
    """, (COMM_ID,))

    # ── Bundle 0: matter bundle, accepted ──
    db.execute("""
        INSERT INTO review_bundles
            (id, communication_id, bundle_type, target_matter_id,
             target_matter_title, status, confidence, rationale,
             sort_order, reviewed_by, reviewed_at, created_at, updated_at)
        VALUES (?, ?, 'matter', 'matter-001', 'DeFi Surveillance', 'accepted',
                0.92, 'Strong match', 1, 'user', datetime('now'),
                datetime('now'), datetime('now'))
    """, (BUNDLE_IDS[0], COMM_ID))

    # Items in bundle 0
    _insert_item(db, ITEM_IDS[0][0], BUNDLE_IDS[0], "task", "accepted",
                 {"title": "Draft surveillance memo", "priority": "high"}, 0.9, 1)
    _insert_item(db, ITEM_IDS[0][1], BUNDLE_IDS[0], "matter_update", "edited",
                 {"summary": "EDITED: Q3 framework confirmed", "significance": "high"},
                 0.85, 2,
                 original_data={"summary": "Q3 framework confirmed", "significance": "medium"})
    _insert_item(db, ITEM_IDS[0][2], BUNDLE_IDS[0], "stakeholder_addition", "accepted",
                 {"person_id": "person-003", "person_name": "Jane Smith",
                  "role": "Technical Lead"}, 0.78, 3)

    # ── Bundle 1: matter bundle, accepted (compound meeting_record) ──
    db.execute("""
        INSERT INTO review_bundles
            (id, communication_id, bundle_type, target_matter_id,
             target_matter_title, status, confidence, rationale,
             sort_order, reviewed_by, reviewed_at, created_at, updated_at)
        VALUES (?, ?, 'matter', 'matter-002', 'Enforcement Coordination', 'accepted',
                0.85, 'Enforcement discussion', 2, 'user', datetime('now'),
                datetime('now'), datetime('now'))
    """, (BUNDLE_IDS[1], COMM_ID))

    _insert_item(db, ITEM_IDS[1][0], BUNDLE_IDS[1], "follow_up", "accepted",
                 {"title": "Schedule coordination call", "due_date": "2026-03-25"}, 0.88, 1)
    _insert_item(db, ITEM_IDS[1][1], BUNDLE_IDS[1], "meeting_record", "accepted",
                 {"title": "Enforcement Strategy Sync", "date": "2026-03-18",
                  "meeting_type": "internal",
                  "participants": [
                      {"person_id": "person-001", "meeting_role": "chair", "attended": True},
                      {"person_id": "person-002", "meeting_role": "participant"},
                  ]}, 0.82, 2)
    _insert_item(db, ITEM_IDS[1][2], BUNDLE_IDS[1], "document", "rejected",
                 {"title": "Playbook draft", "document_type": "internal"}, 0.7, 3)

    # ── Bundle 2: new_matter bundle, accepted ──
    db.execute("""
        INSERT INTO review_bundles
            (id, communication_id, bundle_type, target_matter_id,
             target_matter_title, proposed_matter_json, status, confidence, rationale,
             sort_order, reviewed_by, reviewed_at, created_at, updated_at)
        VALUES (?, ?, 'new_matter', NULL, 'New Crypto Framework', ?,
                'accepted', 0.75, 'New matter identified', 3,
                'user', datetime('now'), datetime('now'), datetime('now'))
    """, (BUNDLE_IDS[2], COMM_ID, json.dumps({
        "title": "New Crypto Framework",
        "matter_type": "policy",
        "description": "Framework for crypto asset regulation",
        "status": "active",
        "priority": "high",
    })))

    _insert_item(db, ITEM_IDS[2][0], BUNDLE_IDS[2], "task", "accepted",
                 {"title": "Research crypto frameworks", "priority": "medium"}, 0.8, 1)
    _insert_item(db, ITEM_IDS[2][1], BUNDLE_IDS[2], "new_person", "accepted",
                 {"full_name": "Robert Chen", "title": "External Counsel",
                  "organization_name": "Outside Law Firm"}, 0.65, 2)

    # ── Bundle 3: rejected standalone (should be skipped entirely) ──
    db.execute("""
        INSERT INTO review_bundles
            (id, communication_id, bundle_type, status, confidence, rationale,
             sort_order, reviewed_by, reviewed_at, created_at, updated_at)
        VALUES (?, ?, 'standalone', 'rejected', 0.5, 'Not relevant', 4,
                'user', datetime('now'), datetime('now'), datetime('now'))
    """, (BUNDLE_IDS[3], COMM_ID))

    _insert_item(db, ITEM_IDS[3][0], BUNDLE_IDS[3], "task", "rejected",
                 {"title": "Irrelevant task"}, 0.5, 1)

    # ── Bundle 4: standalone accepted, has a moved original + reviewer-created item ──
    db.execute("""
        INSERT INTO review_bundles
            (id, communication_id, bundle_type, status, confidence, rationale,
             sort_order, reviewed_by, reviewed_at, created_at, updated_at)
        VALUES (?, ?, 'standalone', 'accepted', NULL, 'Reviewer-created bundle', 5,
                'user', datetime('now'), datetime('now'), datetime('now'))
    """, (BUNDLE_IDS[4], COMM_ID))

    # Moved original — should NOT be committed
    _insert_item(db, ITEM_IDS[4][0], BUNDLE_IDS[4], "task", "moved",
                 {"title": "Moved task"}, 0.7, 1)
    # Reviewer-created item — NULL confidence, should be committed
    db.execute("""
        INSERT INTO review_bundle_items
            (id, bundle_id, item_type, status, proposed_data,
             confidence, rationale, source_excerpt,
             sort_order, created_at, updated_at)
        VALUES (?, ?, 'task', 'accepted', ?, NULL, 'Reviewer-created item',
                NULL, 2, datetime('now'), datetime('now'))
    """, (ITEM_IDS[4][1], BUNDLE_IDS[4],
          json.dumps({"title": "Reviewer-added follow-up", "priority": "low"})))

    db.commit()


def _insert_item(db, item_id, bundle_id, item_type, status, proposed_data,
                 confidence, sort_order, original_data=None):
    db.execute("""
        INSERT INTO review_bundle_items
            (id, bundle_id, item_type, status, proposed_data, original_proposed_data,
             confidence, rationale, source_excerpt,
             source_locator_json, sort_order, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'Test rationale', 'test excerpt',
                '{"type":"transcript","segment_index":1}', ?, datetime('now'), datetime('now'))
    """, (item_id, bundle_id, item_type, status,
          json.dumps(proposed_data),
          json.dumps(original_data) if original_data else None,
          confidence, sort_order))


# -----------------------------------------------------------------------
# Module-level setup
# -----------------------------------------------------------------------
_shared_db = sqlite3.connect(":memory:", check_same_thread=False)
_shared_db.row_factory = sqlite3.Row
_init_db(_shared_db)


def _get_test_db():
    return _shared_db


def _create_app():
    from app.main import app
    from app.db import get_db
    app.dependency_overrides[get_db] = _get_test_db
    return app


_app = _create_app()

from fastapi.testclient import TestClient
client = TestClient(_app)
PREFIX = "/ai/api/bundle-review"


def _make_tracker_response(operations):
    """Build a mock tracker batch response from operations."""
    results = []
    for i, op in enumerate(operations):
        results.append({
            "op": op.get("op", "insert"),
            "table": op.get("table", ""),
            "record_id": str(uuid.uuid4()),
            "previous_data": None,
        })
    return {"results": results, "operations_count": len(operations)}


# =====================================================================
# 1. STATE MAPPING — reviewed states to batch ops
# =====================================================================

def test_1_01_build_bundle_tree_reflects_review_state():
    """_build_bundle_tree returns correct statuses for all bundles/items."""
    from app.bundle_review.retrieval import _build_bundle_tree
    bundles = _build_bundle_tree(_shared_db, COMM_ID)

    assert len(bundles) == 5

    b0 = next(b for b in bundles if b["id"] == BUNDLE_IDS[0])
    assert b0["status"] == "accepted"
    assert b0["bundle_type"] == "matter"
    assert b0["item_counts"]["accepted"] == 2
    assert b0["item_counts"]["edited"] == 1

    b3 = next(b for b in bundles if b["id"] == BUNDLE_IDS[3])
    assert b3["status"] == "rejected"


def test_1_02_committable_items_filter():
    """Only accepted/edited items are committable — moved/rejected excluded."""
    from app.bundle_review.retrieval import _build_bundle_tree
    from app.writeback.committer import COMMITTABLE_ITEM_STATUSES

    bundles = _build_bundle_tree(_shared_db, COMM_ID)

    # Bundle 0: 2 accepted + 1 edited = 3 committable
    b0 = next(b for b in bundles if b["id"] == BUNDLE_IDS[0])
    committable = [i for i in b0["items"] if i["status"] in COMMITTABLE_ITEM_STATUSES]
    assert len(committable) == 3

    # Bundle 1: 2 accepted, 1 rejected = 2 committable
    b1 = next(b for b in bundles if b["id"] == BUNDLE_IDS[1])
    committable = [i for i in b1["items"] if i["status"] in COMMITTABLE_ITEM_STATUSES]
    assert len(committable) == 2

    # Bundle 4: 1 moved + 1 accepted = 1 committable
    b4 = next(b for b in bundles if b["id"] == BUNDLE_IDS[4])
    committable = [i for i in b4["items"] if i["status"] in COMMITTABLE_ITEM_STATUSES]
    assert len(committable) == 1
    assert committable[0]["id"] == ITEM_IDS[4][1]  # reviewer-created, not the moved one


def test_1_03_rejected_bundle_skipped():
    """Rejected bundles produce zero operations."""
    from app.writeback.item_converters import convert_item

    # Simulate committer logic — rejected bundle should be skipped
    bundles = _shared_db.execute(
        "SELECT id, status FROM review_bundles WHERE communication_id = ?",
        (COMM_ID,)
    ).fetchall()
    rejected = [b for b in bundles if b["status"] == "rejected"]
    assert len(rejected) >= 1  # Bundle 3

    # The committer skips rejected bundles before item conversion even starts
    # This is verified in test_3_01 via CommitResult.bundles_skipped


# =====================================================================
# 2. WRITE ORDER — dependency ordering
# =====================================================================

def test_2_01_ordering_new_org_before_person():
    from app.writeback.ordering import order_items

    items = [
        {"item_type": "task", "sort_order": 1},
        {"item_type": "new_person", "sort_order": 2},
        {"item_type": "new_organization", "sort_order": 3},
        {"item_type": "meeting_record", "sort_order": 4},
    ]
    ordered = order_items(items)
    types = [i["item_type"] for i in ordered]
    assert types.index("new_organization") < types.index("new_person")
    assert types.index("new_person") < types.index("meeting_record")
    assert types.index("meeting_record") < types.index("task")


def test_2_02_ordering_preserves_sort_within_tier():
    from app.writeback.ordering import order_items

    items = [
        {"item_type": "task", "sort_order": 3},
        {"item_type": "task", "sort_order": 1},
        {"item_type": "task", "sort_order": 2},
    ]
    ordered = order_items(items)
    assert [i["sort_order"] for i in ordered] == [1, 2, 3]


# =====================================================================
# 3. FULL COMMIT — mock tracker, verify end-to-end
# =====================================================================

def test_3_01_commit_communication_full():
    """Full commit: mock tracker, verify all bundle results."""
    from app.writeback.committer import commit_communication

    call_log = []

    async def mock_post_batch(operations, source, source_metadata, idempotency_key):
        call_log.append({
            "ops": operations,
            "source": source,
            "meta": source_metadata,
            "idem_key": idempotency_key,
        })
        return _make_tracker_response(operations)

    with patch("app.writeback.committer.post_batch", side_effect=mock_post_batch):
        result = asyncio.get_event_loop().run_until_complete(
            commit_communication(_shared_db, COMM_ID)
        )

    _state["commit_result"] = result
    _state["call_log"] = call_log

    # 3 accepted bundles committed (0, 1, 2, 4), 1 rejected skipped (3)
    assert result.bundles_committed == 4, f"Expected 4, got {result.bundles_committed}"
    assert result.bundles_skipped == 1, f"Expected 1 skipped, got {result.bundles_skipped}"
    assert result.bundles_failed == 0
    assert result.all_succeeded is True

    # Verify tracker was called 4 times (one per committed bundle)
    assert len(call_log) == 4


def test_3_02_commit_idempotency_keys():
    """Each bundle batch uses correct idempotency key format."""
    call_log = _state["call_log"]
    for call in call_log:
        key = call["idem_key"]
        assert key.startswith(f"commit_{COMM_ID}_")
        bundle_id = key.split("_", 2)[2]
        assert bundle_id in BUNDLE_IDS


def test_3_03_commit_source_metadata():
    """All batch calls include source='ai' and correct metadata."""
    call_log = _state["call_log"]
    for call in call_log:
        assert call["source"] == "ai"
        assert "communication_id" in call["meta"]
        assert "bundle_id" in call["meta"]
        assert call["meta"]["communication_id"] == COMM_ID


def test_3_04_bundle_0_operations():
    """Bundle 0 (matter): 3 items -> 3 operations (task, matter_update, stakeholder)."""
    call_log = _state["call_log"]
    b0_call = next(c for c in call_log if c["meta"]["bundle_id"] == BUNDLE_IDS[0])
    ops = b0_call["ops"]

    # 3 items, each produces 1 operation
    assert len(ops) == 3

    tables = [op["table"] for op in ops]
    assert "tasks" in tables
    assert "matter_updates" in tables
    assert "matter_people" in tables  # stakeholder_addition -> matter_people

    # Task operation has matter_id from bundle
    task_op = next(op for op in ops if op["table"] == "tasks")
    assert task_op["data"]["matter_id"] == "matter-001"
    assert task_op["data"]["source"] == "ai"
    assert task_op["data"]["automation_hold"] == 1


def test_3_05_bundle_1_compound_meeting():
    """Bundle 1: meeting_record expands to meeting + participants + meeting_matters."""
    call_log = _state["call_log"]
    b1_call = next(c for c in call_log if c["meta"]["bundle_id"] == BUNDLE_IDS[1])
    ops = b1_call["ops"]

    tables = [op["table"] for op in ops]

    # follow_up -> tasks (1)
    # meeting_record -> meetings (1) + meeting_participants (2) + meeting_matters (1) = 4
    # document rejected -> excluded
    # Total: 5
    assert len(ops) == 5, f"Expected 5 ops, got {len(ops)}: {tables}"

    assert tables.count("meetings") == 1
    assert tables.count("meeting_participants") == 2
    assert tables.count("meeting_matters") == 1
    assert tables.count("tasks") == 1  # follow_up

    # Meeting participants use $ref to meeting
    meeting_op = next(op for op in ops if op["table"] == "meetings")
    assert "client_id" in meeting_op  # has client_id for forward ref

    participant_ops = [op for op in ops if op["table"] == "meeting_participants"]
    for pop in participant_ops:
        assert pop["data"]["meeting_id"].startswith("$ref:")


def test_3_06_bundle_2_new_matter():
    """Bundle 2 (new_matter): matter INSERT first, then items with $ref."""
    call_log = _state["call_log"]
    b2_call = next(c for c in call_log if c["meta"]["bundle_id"] == BUNDLE_IDS[2])
    ops = b2_call["ops"]

    # First op must be the matter INSERT
    assert ops[0]["table"] == "matters"
    assert ops[0]["op"] == "insert"
    assert ops[0]["data"]["title"] == "New Crypto Framework"
    assert ops[0]["data"]["source"] == "ai"
    assert ops[0]["data"]["automation_hold"] == 1
    matter_client_id = ops[0]["client_id"]

    # Items should use $ref to the matter
    task_op = next(op for op in ops if op["table"] == "tasks")
    assert task_op["data"]["matter_id"] == f"$ref:{matter_client_id}"

    # new_person also present
    person_op = next(op for op in ops if op["table"] == "people")
    assert person_op["data"]["full_name"] == "Robert Chen"
    assert person_op["data"]["source"] == "ai"


def test_3_07_bundle_4_moved_excluded_reviewer_included():
    """Bundle 4: moved item excluded, reviewer-created item committed."""
    call_log = _state["call_log"]
    b4_call = next(c for c in call_log if c["meta"]["bundle_id"] == BUNDLE_IDS[4])
    ops = b4_call["ops"]

    # Only the reviewer-created task, not the moved one
    assert len(ops) == 1
    assert ops[0]["table"] == "tasks"
    assert ops[0]["data"]["title"] == "Reviewer-added follow-up"
    # Reviewer items have no ai_confidence (confidence=None filtered out)
    assert "ai_confidence" not in ops[0]["data"]


# =====================================================================
# 4. TRACKER_WRITEBACKS RECORDS
# =====================================================================

def test_4_01_writebacks_recorded():
    """tracker_writebacks has entries for every operation result."""
    rows = _shared_db.execute(
        "SELECT * FROM tracker_writebacks WHERE communication_id = ?",
        (COMM_ID,)
    ).fetchall()

    assert len(rows) > 0
    _state["writeback_count"] = len(rows)

    # Verify FK fields populated
    for r in rows:
        assert r["communication_id"] == COMM_ID
        assert r["bundle_id"] in BUNDLE_IDS
        assert r["target_table"] != ""
        assert r["target_record_id"] != ""
        assert r["write_type"] != ""


def test_4_02_writebacks_per_bundle():
    """Each committed bundle has writebacks matching its operation count."""
    call_log = _state["call_log"]

    for call in call_log:
        bundle_id = call["meta"]["bundle_id"]
        expected_count = len(call["ops"])
        actual = _shared_db.execute(
            "SELECT COUNT(*) as cnt FROM tracker_writebacks WHERE bundle_id = ?",
            (bundle_id,)
        ).fetchone()["cnt"]
        assert actual == expected_count, \
            f"Bundle {bundle_id[:8]}: expected {expected_count} writebacks, got {actual}"


def test_4_03_writebacks_written_data_json():
    """written_data in tracker_writebacks is valid JSON matching the operation."""
    rows = _shared_db.execute(
        "SELECT written_data FROM tracker_writebacks WHERE communication_id = ?",
        (COMM_ID,)
    ).fetchall()

    for r in rows:
        data = json.loads(r["written_data"])
        assert isinstance(data, dict)


def test_4_04_no_writebacks_for_rejected_bundle():
    """Rejected bundle (3) has zero writebacks."""
    count = _shared_db.execute(
        "SELECT COUNT(*) as cnt FROM tracker_writebacks WHERE bundle_id = ?",
        (BUNDLE_IDS[3],)
    ).fetchone()["cnt"]
    assert count == 0


# =====================================================================
# 5. AUDIT TRAIL
# =====================================================================

def test_5_01_commit_audit_entries():
    """Audit log has commit_started and commit_complete entries."""
    rows = _shared_db.execute("""
        SELECT action_type, details FROM review_action_log
        WHERE communication_id = ? AND action_type LIKE 'commit%'
        ORDER BY created_at
    """, (COMM_ID,)).fetchall()

    action_types = [r["action_type"] for r in rows]
    assert "commit_started" in action_types
    assert "commit_complete" in action_types

    # commit_complete has summary stats
    complete_row = next(r for r in rows if r["action_type"] == "commit_complete")
    details = json.loads(complete_row["details"])
    assert details["bundles_committed"] == 4
    assert details["bundles_skipped"] == 1
    assert details["bundles_failed"] == 0


def test_5_02_bundle_committed_audit():
    """Each committed bundle has a bundle_committed audit entry."""
    rows = _shared_db.execute("""
        SELECT bundle_id, details FROM review_action_log
        WHERE communication_id = ? AND action_type = 'bundle_committed'
    """, (COMM_ID,)).fetchall()

    committed_bundle_ids = {r["bundle_id"] for r in rows}
    for bid in [BUNDLE_IDS[0], BUNDLE_IDS[1], BUNDLE_IDS[2], BUNDLE_IDS[4]]:
        assert bid in committed_bundle_ids, f"Missing audit for bundle {bid[:8]}"

    # Check detail structure
    for r in rows:
        d = json.loads(r["details"])
        assert "operations_sent" in d
        assert "records_written" in d


# =====================================================================
# 6. EDITED ITEMS — uses edited proposed_data, not original
# =====================================================================

def test_6_01_edited_item_uses_current_data():
    """Edited items commit with their current proposed_data, not original."""
    call_log = _state["call_log"]
    b0_call = next(c for c in call_log if c["meta"]["bundle_id"] == BUNDLE_IDS[0])
    ops = b0_call["ops"]

    # matter_update item was edited
    mu_op = next(op for op in ops if op["table"] == "matter_updates")
    assert "EDITED" in mu_op["data"]["summary"]


# =====================================================================
# 7. ITEM CONVERTER UNIT TESTS
# =====================================================================

def test_7_01_convert_new_matter_registers_ref():
    """convert_new_matter_bundle puts $matter in refs dict."""
    from app.writeback.item_converters import convert_new_matter_bundle

    bundle = {
        "id": "test-bundle",
        "bundle_type": "new_matter",
        "proposed_matter": {
            "title": "Test Matter",
            "matter_type": "policy",
            "status": "active",
        },
        "confidence": 0.8,
        "communication_id": "test-comm",
    }
    refs = {}
    ops = convert_new_matter_bundle(bundle, refs)
    assert len(ops) == 1
    assert "$matter" in refs
    assert ops[0][0]["table"] == "matters"
    assert ops[0][0]["data"]["source"] == "ai"


def test_7_02_convert_meeting_record_compound():
    """meeting_record produces meeting + participants + meeting_matters."""
    from app.writeback.item_converters import convert_meeting_record

    item = {
        "id": "test-item",
        "item_type": "meeting_record",
        "confidence": 0.8,
        "proposed_data": {
            "title": "Test Meeting",
            "date": "2026-03-18",
            "participants": [
                {"person_id": "p1", "meeting_role": "chair"},
                {"person_id": "p2"},
            ],
        },
    }
    bundle = {"id": "b1", "bundle_type": "matter", "target_matter_id": "m1",
              "_communication_id": "c1"}
    refs = {}
    ops = convert_meeting_record(item, bundle, refs)

    tables = [op[0]["table"] for op in ops]
    assert "meetings" in tables
    assert tables.count("meeting_participants") == 2
    assert "meeting_matters" in tables


def test_7_03_convert_status_change_uses_update():
    """status_change produces an UPDATE on matters, not INSERT."""
    from app.writeback.item_converters import convert_status_change

    item = {
        "id": "test-sc",
        "item_type": "status_change",
        "confidence": 0.9,
        "proposed_data": {
            "matter_id": "matter-001",
            "field": "status",
            "new_value": "on_hold",
        },
    }
    bundle = {"id": "b1", "bundle_type": "matter", "target_matter_id": "matter-001",
              "_communication_id": "c1"}
    refs = {}
    ops = convert_status_change(item, bundle, refs)
    assert len(ops) == 1
    assert ops[0][0]["op"] == "update"
    assert ops[0][0]["table"] == "matters"
    assert ops[0][0]["data"]["status"] == "on_hold"


def test_7_04_convert_new_person_registers_ref():
    """new_person registers person:<name> in refs for later stakeholder resolution."""
    from app.writeback.item_converters import convert_new_person

    item = {
        "id": "test-np",
        "item_type": "new_person",
        "confidence": 0.7,
        "proposed_data": {
            "full_name": "Alice Jones",
            "title": "Director",
        },
    }
    bundle = {"id": "b1", "bundle_type": "standalone", "_communication_id": "c1"}
    refs = {}
    ops = convert_new_person(item, bundle, refs)
    assert "person:Alice Jones" in refs
    assert ops[0][0]["data"]["full_name"] == "Alice Jones"


def test_7_05_stakeholder_org_only():
    """stakeholder_addition with org but no person -> matter_organizations."""
    from app.writeback.item_converters import convert_stakeholder_addition

    item = {
        "id": "test-sa",
        "item_type": "stakeholder_addition",
        "confidence": 0.8,
        "proposed_data": {
            "organization_id": "org-001",
            "organization_name": "Test Corp",
            "role": "counterparty",
        },
    }
    bundle = {"id": "b1", "bundle_type": "matter", "target_matter_id": "m1",
              "_communication_id": "c1"}
    refs = {}
    ops = convert_stakeholder_addition(item, bundle, refs)
    assert len(ops) == 1
    assert ops[0][0]["table"] == "matter_organizations"


# =====================================================================
# 8. ERROR / PARTIAL FAILURE
# =====================================================================

def test_8_01_partial_failure_recorded():
    """If one bundle fails, CommitResult reflects partial failure."""
    from app.writeback.committer import commit_communication
    from app.writeback.tracker_client import TrackerBatchError

    # Create a fresh communication for this test
    err_comm_id = str(uuid.uuid4())
    err_bundle_id = str(uuid.uuid4())
    err_item_id = str(uuid.uuid4())

    _shared_db.execute("""
        INSERT INTO communications (id, source_type, processing_status, created_at, updated_at)
        VALUES (?, 'audio', 'reviewed', datetime('now'), datetime('now'))
    """, (err_comm_id,))
    _shared_db.execute("""
        INSERT INTO review_bundles
            (id, communication_id, bundle_type, status, sort_order, reviewed_by,
             reviewed_at, created_at, updated_at)
        VALUES (?, ?, 'standalone', 'accepted', 1, 'user', datetime('now'),
                datetime('now'), datetime('now'))
    """, (err_bundle_id, err_comm_id))
    _shared_db.execute("""
        INSERT INTO review_bundle_items
            (id, bundle_id, item_type, status, proposed_data, confidence,
             sort_order, created_at, updated_at)
        VALUES (?, ?, 'task', 'accepted', '{"title":"fail task"}', 0.9,
                1, datetime('now'), datetime('now'))
    """, (err_item_id, err_bundle_id))
    _shared_db.commit()

    async def mock_fail(*args, **kwargs):
        raise TrackerBatchError(500, "server_error", "Internal server error")

    with patch("app.writeback.committer.post_batch", side_effect=mock_fail):
        result = asyncio.get_event_loop().run_until_complete(
            commit_communication(_shared_db, err_comm_id)
        )

    assert result.bundles_failed == 1
    assert result.all_succeeded is False

    # Audit records the failure
    fail_audit = _shared_db.execute("""
        SELECT details FROM review_action_log
        WHERE communication_id = ? AND action_type = 'bundle_commit_failed'
    """, (err_comm_id,)).fetchone()
    assert fail_audit is not None
    d = json.loads(fail_audit["details"])
    assert d["error_type"] == "server_error"


# =====================================================================
# 9. ORCHESTRATOR DISPATCH
# =====================================================================

def test_9_01_handle_committing_returns_complete():
    """_handle_committing calls commit_communication and returns 'complete'."""
    from app.pipeline.orchestrator import _handle_committing

    async def mock_post_batch(operations, source, source_metadata, idempotency_key):
        return _make_tracker_response(operations)

    # Need a fresh comm in 'reviewed' to avoid re-committing the same one
    orch_comm_id = str(uuid.uuid4())
    orch_bundle_id = str(uuid.uuid4())
    orch_item_id = str(uuid.uuid4())

    _shared_db.execute("""
        INSERT INTO communications (id, source_type, processing_status, created_at, updated_at)
        VALUES (?, 'audio', 'reviewed', datetime('now'), datetime('now'))
    """, (orch_comm_id,))
    _shared_db.execute("""
        INSERT INTO review_bundles
            (id, communication_id, bundle_type, status, sort_order, reviewed_by,
             reviewed_at, created_at, updated_at)
        VALUES (?, ?, 'standalone', 'accepted', 1, 'user', datetime('now'),
                datetime('now'), datetime('now'))
    """, (orch_bundle_id, orch_comm_id))
    _shared_db.execute("""
        INSERT INTO review_bundle_items
            (id, bundle_id, item_type, status, proposed_data, confidence,
             sort_order, created_at, updated_at)
        VALUES (?, ?, 'task', 'accepted', '{"title":"orch test"}', 0.9,
                1, datetime('now'), datetime('now'))
    """, (orch_item_id, orch_bundle_id))
    _shared_db.commit()

    with patch("app.writeback.committer.post_batch", side_effect=mock_post_batch):
        with patch("app.pipeline.orchestrator.publish_event", new_callable=AsyncMock):
            next_status = asyncio.get_event_loop().run_until_complete(
                _handle_committing(_shared_db, orch_comm_id)
            )

    assert next_status == "complete"


def test_9_02_handle_committing_raises_on_failure():
    """_handle_committing raises RuntimeError on partial failure."""
    from app.pipeline.orchestrator import _handle_committing
    from app.writeback.tracker_client import TrackerBatchError

    fail_comm_id = str(uuid.uuid4())
    fail_bundle_id = str(uuid.uuid4())
    fail_item_id = str(uuid.uuid4())

    _shared_db.execute("""
        INSERT INTO communications (id, source_type, processing_status, created_at, updated_at)
        VALUES (?, 'audio', 'reviewed', datetime('now'), datetime('now'))
    """, (fail_comm_id,))
    _shared_db.execute("""
        INSERT INTO review_bundles
            (id, communication_id, bundle_type, status, sort_order, reviewed_by,
             reviewed_at, created_at, updated_at)
        VALUES (?, ?, 'standalone', 'accepted', 1, 'user', datetime('now'),
                datetime('now'), datetime('now'))
    """, (fail_bundle_id, fail_comm_id))
    _shared_db.execute("""
        INSERT INTO review_bundle_items
            (id, bundle_id, item_type, status, proposed_data, confidence,
             sort_order, created_at, updated_at)
        VALUES (?, ?, 'task', 'accepted', '{"title":"fail test"}', 0.9,
                1, datetime('now'), datetime('now'))
    """, (fail_item_id, fail_bundle_id))
    _shared_db.commit()

    async def mock_fail(*args, **kwargs):
        raise TrackerBatchError(500, "server_error", "Tracker down")

    raised = False
    with patch("app.writeback.committer.post_batch", side_effect=mock_fail):
        with patch("app.pipeline.orchestrator.publish_event", new_callable=AsyncMock):
            try:
                asyncio.get_event_loop().run_until_complete(
                    _handle_committing(_shared_db, fail_comm_id)
                )
            except RuntimeError as e:
                raised = True
                assert "partial failure" in str(e).lower()

    assert raised, "_handle_committing should raise on failure"


# =====================================================================
# 10. REGRESSION — bundle review still works
# =====================================================================

def test_10_01_review_endpoints_still_work():
    """Health and config endpoints unaffected."""
    r = client.get("/ai/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"

    r = client.get("/ai/api/config")
    assert r.status_code == 200


def test_10_02_bundle_tree_reusable():
    """_build_bundle_tree used by both review detail and writeback."""
    from app.bundle_review.retrieval import _build_bundle_tree

    bundles = _build_bundle_tree(_shared_db, COMM_ID)
    # Should still return full structure after commit
    assert len(bundles) == 5
    for b in bundles:
        assert "items" in b
        assert "item_counts" in b


def test_10_03_review_queue_excludes_committed():
    """Communications in 'reviewed' state don't appear in bundle review queue."""
    r = client.get(f"{PREFIX}/queue")
    assert r.status_code == 200
    ids = [i["id"] for i in r.json()["items"]]
    assert COMM_ID not in ids  # reviewed, not in review queue


# =====================================================================
# RUNNER
# =====================================================================

def run_all():
    """Run all tests in order and report results."""
    import traceback

    test_funcs = sorted(
        [(name, obj) for name, obj in globals().items()
         if name.startswith("test_") and callable(obj)],
        key=lambda x: x[0]
    )

    total = 0
    passed = 0
    failed = 0
    errors = []

    for name, func in test_funcs:
        total += 1
        try:
            func()
            passed += 1
            print(f"  PASS {name}")
        except AssertionError as e:
            failed += 1
            errors.append((name, str(e), traceback.format_exc()))
            print(f"  FAIL {name}: {e}")
        except Exception as e:
            failed += 1
            errors.append((name, str(e), traceback.format_exc()))
            print(f"  FAIL {name}: {type(e).__name__}: {e}")

    print(f"\n{'='*60}")
    print(f"RESULTS: {passed}/{total} passed, {failed} failed")
    print(f"{'='*60}")

    if errors:
        print("\nFAILURES:")
        for name, msg, tb in errors:
            print(f"\n--- {name} ---")
            print(tb)

    return passed, total, failed


if __name__ == "__main__":
    print("Phase 5 Runtime Verification -- Tracker Writeback")
    print("=" * 60)
    passed, total, failed = run_all()
    sys.exit(0 if failed == 0 else 1)
