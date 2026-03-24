"""Phase 4C Runtime Verification -- Bundle Review Backend

Comprehensive test exercising all 15 endpoints of the bundle review router
against a live FastAPI TestClient with an in-memory SQLite database.

Verification categories (per Phase 4C spec):
1. Retrieval -- queue + detail with suppression visibility
2. Item actions -- accept, reject, edit, restore, add
3. Bundle actions -- accept (cascade), reject (cascade), edit, accept-all
4. Restructuring -- move-item, create-bundle, merge-bundles
5. Completion -- blocker validation, CAS transition, pipeline resume
6. Audit/provenance -- review_action_log entries, original_proposed_data, moved_from_bundle_id
7. Regression -- prior stages (health, config, communications) still work
8. Edge cases -- double-accept, reject-moved-item, edit-rejected-bundle, etc.
"""

import json
import sqlite3
import uuid
import sys
import os
from pathlib import Path

# Ensure the service root is on sys.path
SERVICE_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(SERVICE_ROOT))

# Must set env vars before importing app modules
os.environ.setdefault("APP_ENV", "development")
os.environ.setdefault("AI_DB_PATH", ":memory:")

# -----------------------------------------------------------------------
# Shared fixtures
# -----------------------------------------------------------------------

COMM_ID = str(uuid.uuid4())
BUNDLE_IDS = [str(uuid.uuid4()) for _ in range(3)]
ITEM_IDS = [[str(uuid.uuid4()) for _ in range(3)] for _ in range(3)]

# State shared between ordered tests
_state = {}


def _init_db(db: sqlite3.Connection):
    """Set up schema and seed realistic bundle review data."""
    db.row_factory = sqlite3.Row
    from app.schema import init_schema
    init_schema(db)

    # Communication in awaiting_bundle_review
    db.execute("""
        INSERT INTO communications (id, source_type, processing_status, original_filename,
                                    duration_seconds, topic_segments_json,
                                    sensitivity_flags, created_at, updated_at)
        VALUES (?, 'audio', 'awaiting_bundle_review', 'test_meeting.wav', 1234,
                ?, ?, datetime('now'), datetime('now'))
    """, (
        COMM_ID,
        json.dumps({
            "summary": "Discussion about DeFi market surveillance and enforcement actions.",
            "topics": [
                {"topic": "DeFi surveillance framework", "start_time": 0, "end_time": 300},
                {"topic": "Enforcement coordination", "start_time": 300, "end_time": 600},
            ]
        }),
        json.dumps({"enforcement_sensitive": True, "deliberative": False}),
    ))

    # Extraction record with suppressed_observations and post-processing
    extraction_id = str(uuid.uuid4())
    db.execute("""
        INSERT INTO ai_extractions (id, communication_id, model_used, prompt_version,
                                    raw_output, input_tokens, output_tokens,
                                    processing_seconds, extracted_at)
        VALUES (?, ?, 'claude-sonnet-4-20250514', 'v1.0.0', ?, 5000, 1200, 8.5, datetime('now'))
    """, (
        extraction_id, COMM_ID,
        json.dumps({
            "extraction_summary": "2 matters identified with 9 proposals.",
            "suppressed_observations": [
                {"type": "decision", "reason": "propose_decisions disabled in policy",
                 "description": "Commissioner voted to defer rulemaking"},
            ],
            "_post_processing": {
                "code_suppressed_items": [
                    {"item_type": "status_change", "reason": "propose_status_changes disabled"},
                ],
                "dedup_warnings": [
                    {"item_type": "task", "title": "Draft surveillance memo",
                     "reason": "similar task already exists in matter"},
                ],
                "invalid_references_cleaned": [
                    {"field": "person_id", "original": "nonexistent-id", "action": "set to null"},
                ],
            }
        }),
    ))

    # 3 bundles
    bundle_data = [
        {"id": BUNDLE_IDS[0], "bundle_type": "matter", "target_matter_id": "matter-001",
         "target_matter_title": "DeFi Surveillance", "confidence": 0.92, "sort_order": 1,
         "rationale": "Strong match to existing matter",
         "intelligence_notes": "Key developments in DeFi oversight"},
        {"id": BUNDLE_IDS[1], "bundle_type": "matter", "target_matter_id": "matter-002",
         "target_matter_title": "Enforcement Coordination", "confidence": 0.85, "sort_order": 2,
         "rationale": "Discussion references ongoing enforcement"},
        {"id": BUNDLE_IDS[2], "bundle_type": "standalone", "target_matter_id": None,
         "target_matter_title": None, "confidence": 0.6, "sort_order": 3,
         "rationale": "Standalone tasks not tied to specific matters"},
    ]
    for bd in bundle_data:
        db.execute("""
            INSERT INTO review_bundles
                (id, communication_id, bundle_type, target_matter_id,
                 target_matter_title, status, confidence, rationale,
                 intelligence_notes, sort_order, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, 'proposed', ?, ?, ?, ?, datetime('now'), datetime('now'))
        """, (bd["id"], COMM_ID, bd["bundle_type"], bd.get("target_matter_id"),
              bd.get("target_matter_title"), bd["confidence"],
              bd["rationale"], bd.get("intelligence_notes"), bd["sort_order"]))

    # Items per bundle
    items_b0 = [
        {"id": ITEM_IDS[0][0], "item_type": "task", "confidence": 0.9,
         "proposed_data": {"title": "Draft DeFi surveillance memo", "priority": "high"},
         "source_excerpt": "we need to draft that surveillance memo by Friday",
         "source_locator_json": json.dumps({"type": "transcript", "segment_index": 2,
                                             "start_seconds": 45.0, "end_seconds": 52.0})},
        {"id": ITEM_IDS[0][1], "item_type": "matter_update", "confidence": 0.85,
         "proposed_data": {"summary": "DeFi team confirmed new monitoring framework will be ready Q3",
                           "significance": "high"},
         "source_excerpt": "the monitoring framework will be ready by Q3",
         "source_locator_json": json.dumps({"type": "transcript", "segment_index": 5,
                                             "start_seconds": 120.0, "end_seconds": 128.0})},
        {"id": ITEM_IDS[0][2], "item_type": "stakeholder_addition", "confidence": 0.78,
         "proposed_data": {"person_id": "person-003", "person_name": "Jane Smith",
                           "role": "Technical Lead", "stance": "supportive"},
         "source_excerpt": "Jane Smith from tech will be leading the implementation",
         "source_locator_json": json.dumps({"type": "transcript", "segment_index": 7,
                                             "start_seconds": 200.0, "end_seconds": 208.0})},
    ]
    items_b1 = [
        {"id": ITEM_IDS[1][0], "item_type": "follow_up", "confidence": 0.88,
         "proposed_data": {"title": "Schedule enforcement coordination call",
                           "due_date": "2026-03-25"},
         "source_excerpt": "let's schedule that coordination call for next week",
         "source_locator_json": json.dumps({"type": "transcript", "segment_index": 9,
                                             "start_seconds": 350.0, "end_seconds": 358.0})},
        {"id": ITEM_IDS[1][1], "item_type": "meeting_record", "confidence": 0.82,
         "proposed_data": {"title": "Enforcement Strategy Sync", "date": "2026-03-18"},
         "source_excerpt": "summary of enforcement strategy sync",
         "source_locator_json": json.dumps({"type": "transcript", "segment_index": 0,
                                             "start_seconds": 0.0, "end_seconds": 600.0})},
        {"id": ITEM_IDS[1][2], "item_type": "document", "confidence": 0.7,
         "proposed_data": {"title": "Enforcement playbook draft", "document_type": "internal"},
         "source_excerpt": "the playbook draft is in final review",
         "source_locator_json": json.dumps({"type": "transcript", "segment_index": 11,
                                             "start_seconds": 500.0, "end_seconds": 510.0})},
    ]
    items_b2 = [
        {"id": ITEM_IDS[2][0], "item_type": "new_person", "confidence": 0.65,
         "proposed_data": {"full_name": "Robert Chen", "title": "External Counsel",
                           "organization_name": "Outside Law Firm"},
         "source_excerpt": "Robert Chen from outside counsel mentioned...",
         "source_locator_json": json.dumps({"type": "transcript", "segment_index": 4,
                                             "start_seconds": 90.0, "end_seconds": 95.0})},
    ]

    for bundle_idx, items in enumerate([items_b0, items_b1, items_b2]):
        for sort_i, item in enumerate(items):
            db.execute("""
                INSERT INTO review_bundle_items
                    (id, bundle_id, item_type, status, proposed_data,
                     confidence, rationale, source_excerpt,
                     source_locator_json, sort_order, created_at, updated_at)
                VALUES (?, ?, ?, 'proposed', ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
            """, (item["id"], BUNDLE_IDS[bundle_idx], item["item_type"],
                  json.dumps(item["proposed_data"]), item["confidence"],
                  "Test rationale", item["source_excerpt"],
                  item.get("source_locator_json"), sort_i + 1))

    db.commit()


import pytest
from fastapi.testclient import TestClient


def _get_test_db():
    return _shared_db


# Module-level DB setup (fast — done once at import)
_shared_db = sqlite3.connect(":memory:", check_same_thread=False)
_shared_db.row_factory = sqlite3.Row
_init_db(_shared_db)

# Lazy app reference
_app = None
PREFIX = "/ai/api/bundle-review"


def _ensure_app():
    """Get the app singleton with our DB override applied."""
    global _app
    from app.main import app
    from app.db import get_db
    app.dependency_overrides[get_db] = _get_test_db
    _app = app
    return app


@pytest.fixture(autouse=True)
def _rebind_db():
    """Re-apply our DB override before every test.

    This is the root-cause fix: other test files share the app singleton
    and may reset dependency_overrides. By re-binding per-test, we
    guarantee our _shared_db is always active.
    """
    _ensure_app()
    yield


# Module-level client for use in test functions
# (re-created with override in place via the autouse fixture above)
_ensure_app()
client = TestClient(_app)


# =====================================================================
# ORDERED TEST SEQUENCE
# Tests are numbered to enforce execution order within each category
# =====================================================================

def test_1_01_queue_returns_communication():
    r = client.get(f"{PREFIX}/queue")
    assert r.status_code == 200
    data = r.json()
    assert data["total"] >= 1
    comm = next(i for i in data["items"] if i["id"] == COMM_ID)
    assert comm["processing_status"] in ("awaiting_bundle_review", "bundle_review_in_progress")
    assert comm["bundle_count"] == 3
    assert comm["item_count"] == 7


def test_1_02_detail_returns_full_structure():
    r = client.get(f"{PREFIX}/{COMM_ID}")
    assert r.status_code == 200
    d = r.json()
    assert d["communication_id"] == COMM_ID
    assert d["original_filename"] == "test_meeting.wav"
    assert d["summary"] is not None
    assert d["extraction_meta"]["model_used"] == "claude-sonnet-4-20250514"
    assert d["extraction_meta"]["input_tokens"] == 5000
    assert len(d["bundles"]) == 3
    assert d["bundle_counts"]["total"] == 3
    b0 = next(b for b in d["bundles"] if b["id"] == BUNDLE_IDS[0])
    assert b0["item_counts"]["total"] == 3
    assert b0["target_matter_title"] == "DeFi Surveillance"


def test_1_03_suppression_visibility():
    r = client.get(f"{PREFIX}/{COMM_ID}")
    d = r.json()
    assert len(d["suppressed_observations"]) == 1
    assert d["suppressed_observations"][0]["type"] == "decision"
    assert len(d["code_suppressions"]) == 1
    assert d["code_suppressions"][0]["item_type"] == "status_change"
    assert len(d["dedup_warnings"]) == 1
    assert len(d["invalid_refs_cleaned"]) == 1


def test_1_04_sensitivity_flags_parsed():
    r = client.get(f"{PREFIX}/{COMM_ID}")
    d = r.json()
    assert d["sensitivity_flags"]["enforcement_sensitive"] is True


def test_1_05_readiness_blockers():
    r = client.get(f"{PREFIX}/{COMM_ID}")
    d = r.json()
    assert d["ready_to_complete"] is False
    assert len(d["completion_blockers"]) > 0


def test_1_06_detail_404_for_nonexistent():
    r = client.get(f"{PREFIX}/nonexistent-id")
    assert r.status_code == 404


# -- Item actions --

def test_2_01_accept_item():
    r = client.post(f"{PREFIX}/{COMM_ID}/accept-item", json={
        "bundle_id": BUNDLE_IDS[0], "item_id": ITEM_IDS[0][0],
    })
    assert r.status_code == 200
    assert r.json()["new_status"] == "accepted"
    row = _shared_db.execute(
        "SELECT status FROM review_bundle_items WHERE id = ?", (ITEM_IDS[0][0],)
    ).fetchone()
    assert row["status"] == "accepted"


def test_2_02_reject_item():
    r = client.post(f"{PREFIX}/{COMM_ID}/reject-item", json={
        "bundle_id": BUNDLE_IDS[1], "item_id": ITEM_IDS[1][2],
        "reason": "Not relevant to this matter",
    })
    assert r.status_code == 200
    assert r.json()["new_status"] == "rejected"


def test_2_03_edit_item_preserves_original():
    item_id = ITEM_IDS[0][1]
    original_data = json.loads(
        _shared_db.execute(
            "SELECT proposed_data FROM review_bundle_items WHERE id = ?", (item_id,)
        ).fetchone()["proposed_data"]
    )

    # First edit
    new_data = {"summary": "EDITED: DeFi Q3 framework update", "significance": "critical"}
    r = client.post(f"{PREFIX}/{COMM_ID}/edit-item", json={
        "bundle_id": BUNDLE_IDS[0], "item_id": item_id, "proposed_data": new_data,
    })
    assert r.status_code == 200
    assert r.json()["new_status"] == "edited"

    row = _shared_db.execute(
        "SELECT proposed_data, original_proposed_data FROM review_bundle_items WHERE id = ?",
        (item_id,)
    ).fetchone()
    assert json.loads(row["original_proposed_data"]) == original_data

    # Second edit -- original NOT overwritten
    second_data = {"summary": "SECOND EDIT: DeFi Q4 update", "significance": "high"}
    r2 = client.post(f"{PREFIX}/{COMM_ID}/edit-item", json={
        "bundle_id": BUNDLE_IDS[0], "item_id": item_id, "proposed_data": second_data,
    })
    assert r2.status_code == 200
    row2 = _shared_db.execute(
        "SELECT proposed_data, original_proposed_data FROM review_bundle_items WHERE id = ?",
        (item_id,)
    ).fetchone()
    assert json.loads(row2["original_proposed_data"]) == original_data
    assert json.loads(row2["proposed_data"]) == second_data


def test_2_04_restore_item():
    item_id = ITEM_IDS[0][1]
    r = client.post(f"{PREFIX}/{COMM_ID}/restore-item", json={
        "bundle_id": BUNDLE_IDS[0], "item_id": item_id,
    })
    assert r.status_code == 200
    assert r.json()["new_status"] == "proposed"
    row = _shared_db.execute(
        "SELECT status, original_proposed_data FROM review_bundle_items WHERE id = ?",
        (item_id,)
    ).fetchone()
    assert row["status"] == "proposed"
    assert row["original_proposed_data"] is None


def test_2_05_restore_unedited_fails():
    r = client.post(f"{PREFIX}/{COMM_ID}/restore-item", json={
        "bundle_id": BUNDLE_IDS[0], "item_id": ITEM_IDS[0][0],
    })
    assert r.status_code == 400
    assert r.json()["detail"]["error_type"] == "validation_failure"


def test_2_06_add_reviewer_item():
    r = client.post(f"{PREFIX}/{COMM_ID}/add-item", json={
        "bundle_id": BUNDLE_IDS[0], "item_type": "task",
        "proposed_data": {"title": "Reviewer-added follow-up task", "priority": "medium"},
        "rationale": "Reviewer-created item for completeness",
        "source_excerpt": "related discussion at 5:30",
        "source_start_time": 330.0, "source_end_time": 340.0,
    })
    assert r.status_code == 200
    new_id = r.json()["item_id"]
    assert r.json()["new_status"] == "accepted"

    row = _shared_db.execute(
        "SELECT confidence, status, source_locator_json FROM review_bundle_items WHERE id = ?",
        (new_id,)
    ).fetchone()
    assert row["confidence"] is None  # reviewer-created
    assert row["status"] == "accepted"
    locator = json.loads(row["source_locator_json"])
    assert locator["type"] == "reviewer"


def test_2_07_add_invalid_type_fails():
    r = client.post(f"{PREFIX}/{COMM_ID}/add-item", json={
        "bundle_id": BUNDLE_IDS[0], "item_type": "invalid_type",
        "proposed_data": {"title": "test"},
    })
    assert r.status_code == 400
    assert "Invalid item_type" in r.json()["detail"]["message"]


def test_2_08_edit_item_validation():
    r = client.post(f"{PREFIX}/{COMM_ID}/edit-item", json={
        "bundle_id": BUNDLE_IDS[0], "item_id": ITEM_IDS[0][0],
        "proposed_data": {"priority": "low"},  # missing 'title' for task
    })
    assert r.status_code == 400
    assert "title" in r.json()["detail"]["message"]


# -- Bundle actions --

def test_3_01_accept_bundle_cascades():
    r = client.post(f"{PREFIX}/{COMM_ID}/accept-bundle", json={
        "bundle_id": BUNDLE_IDS[1],
    })
    assert r.status_code == 200
    d = r.json()
    assert d["new_status"] == "accepted"
    assert d["auto_accepted_items"] >= 1

    # Bundle is accepted
    row = _shared_db.execute(
        "SELECT status FROM review_bundles WHERE id = ?", (BUNDLE_IDS[1],)
    ).fetchone()
    assert row["status"] == "accepted"

    # Already-rejected item stays rejected
    rej = _shared_db.execute(
        "SELECT status FROM review_bundle_items WHERE id = ?", (ITEM_IDS[1][2],)
    ).fetchone()
    assert rej["status"] == "rejected"


def test_3_02_accept_already_terminal_fails():
    r = client.post(f"{PREFIX}/{COMM_ID}/accept-bundle", json={
        "bundle_id": BUNDLE_IDS[1],
    })
    assert r.status_code == 400
    assert r.json()["detail"]["error_type"] == "invalid_state"


def test_3_03_reject_bundle_cascades():
    r = client.post(f"{PREFIX}/{COMM_ID}/reject-bundle", json={
        "bundle_id": BUNDLE_IDS[2], "reason": "Standalone items not needed",
    })
    assert r.status_code == 200
    d = r.json()
    assert d["new_status"] == "rejected"
    assert d["auto_rejected_items"] >= 1


def test_3_04_edit_bundle_metadata():
    r = client.post(f"{PREFIX}/{COMM_ID}/edit-bundle", json={
        "bundle_id": BUNDLE_IDS[0],
        "target_matter_title": "DeFi Surveillance Framework (Updated)",
        "intelligence_notes": "Reviewer updated notes",
    })
    assert r.status_code == 200
    row = _shared_db.execute(
        "SELECT target_matter_title, intelligence_notes FROM review_bundles WHERE id = ?",
        (BUNDLE_IDS[0],)
    ).fetchone()
    assert row["target_matter_title"] == "DeFi Surveillance Framework (Updated)"
    assert row["intelligence_notes"] == "Reviewer updated notes"


def test_3_05_edit_rejected_bundle_fails():
    r = client.post(f"{PREFIX}/{COMM_ID}/edit-bundle", json={
        "bundle_id": BUNDLE_IDS[2], "rationale": "test",
    })
    assert r.status_code == 400


# -- Restructuring --

def test_4_01_create_bundle():
    r = client.post(f"{PREFIX}/{COMM_ID}/create-bundle", json={
        "bundle_type": "standalone",
        "target_matter_title": "New Reviewer Bundle",
        "rationale": "Reviewer-created bundle for overflow items",
    })
    assert r.status_code == 200
    new_bundle_id = r.json()["bundle_id"]
    _state["new_bundle_id"] = new_bundle_id

    row = _shared_db.execute(
        "SELECT * FROM review_bundles WHERE id = ?", (new_bundle_id,)
    ).fetchone()
    assert row["bundle_type"] == "standalone"
    assert row["status"] == "proposed"
    assert row["confidence"] is None


def test_4_02_create_bundle_invalid_type_fails():
    r = client.post(f"{PREFIX}/{COMM_ID}/create-bundle", json={
        "bundle_type": "invalid_type",
    })
    assert r.status_code == 400


def test_4_03_move_item():
    new_bundle_id = _state["new_bundle_id"]
    item_to_move = ITEM_IDS[0][2]  # stakeholder_addition

    r = client.post(f"{PREFIX}/{COMM_ID}/move-item", json={
        "item_id": item_to_move,
        "from_bundle_id": BUNDLE_IDS[0],
        "to_bundle_id": new_bundle_id,
    })
    assert r.status_code == 200
    d = r.json()
    new_item_id = d["new_item_id"]
    _state["moved_item_new_id"] = new_item_id

    # Original is moved
    orig = _shared_db.execute(
        "SELECT status FROM review_bundle_items WHERE id = ?", (item_to_move,)
    ).fetchone()
    assert orig["status"] == "moved"

    # Copy in target with provenance
    copy = _shared_db.execute(
        "SELECT * FROM review_bundle_items WHERE id = ?", (new_item_id,)
    ).fetchone()
    assert copy["bundle_id"] == new_bundle_id
    assert copy["moved_from_bundle_id"] == BUNDLE_IDS[0]
    assert copy["status"] == "proposed"
    assert copy["source_locator_json"] is not None


def test_4_04_move_already_moved_fails():
    new_bundle_id = _state["new_bundle_id"]
    r = client.post(f"{PREFIX}/{COMM_ID}/move-item", json={
        "item_id": ITEM_IDS[0][2],
        "from_bundle_id": BUNDLE_IDS[0],
        "to_bundle_id": new_bundle_id,
    })
    assert r.status_code == 400
    assert "already been moved" in r.json()["detail"]["message"]


def test_4_05_move_to_same_bundle_fails():
    r = client.post(f"{PREFIX}/{COMM_ID}/move-item", json={
        "item_id": ITEM_IDS[0][0],
        "from_bundle_id": BUNDLE_IDS[0],
        "to_bundle_id": BUNDLE_IDS[0],
    })
    assert r.status_code == 400


def test_4_06_merge_bundles():
    new_bundle_id = _state["new_bundle_id"]
    moved_item_id = _state["moved_item_new_id"]

    # Accept the moved item first
    client.post(f"{PREFIX}/{COMM_ID}/accept-item", json={
        "bundle_id": new_bundle_id, "item_id": moved_item_id,
    })

    r = client.post(f"{PREFIX}/{COMM_ID}/merge-bundles", json={
        "source_bundle_id": new_bundle_id,
        "target_bundle_id": BUNDLE_IDS[0],
    })
    assert r.status_code == 200
    d = r.json()
    assert d["items_moved"] >= 1

    # Source bundle rejected
    src = _shared_db.execute(
        "SELECT status FROM review_bundles WHERE id = ?", (new_bundle_id,)
    ).fetchone()
    assert src["status"] == "rejected"


# -- Completion --

def test_5_01_complete_blocked_by_unresolved():
    r = client.post(f"{PREFIX}/{COMM_ID}/complete")
    assert r.status_code == 400
    d = r.json()["detail"]
    assert d["error_type"] == "validation_failure"
    assert len(d["blockers"]) > 0


def test_5_02_resolve_then_complete():
    # Accept remaining bundles and items
    bundles = _shared_db.execute(
        "SELECT id, status FROM review_bundles WHERE communication_id = ?",
        (COMM_ID,)
    ).fetchall()
    for b in bundles:
        if b["status"] not in ("accepted", "rejected"):
            client.post(f"{PREFIX}/{COMM_ID}/accept-bundle", json={"bundle_id": b["id"]})

    remaining = _shared_db.execute("""
        SELECT ri.id, ri.bundle_id FROM review_bundle_items ri
        JOIN review_bundles rb ON ri.bundle_id = rb.id
        WHERE rb.communication_id = ? AND ri.status = 'proposed'
    """, (COMM_ID,)).fetchall()
    for ri in remaining:
        client.post(f"{PREFIX}/{COMM_ID}/accept-item", json={
            "bundle_id": ri["bundle_id"], "item_id": ri["id"],
        })

    # Complete
    r = client.post(f"{PREFIX}/{COMM_ID}/complete")
    assert r.status_code == 200, f"Complete failed: {r.json()}"
    d = r.json()
    assert d["status"] == "reviewed"
    assert d["communication_id"] == COMM_ID

    # CAS transition verified
    row = _shared_db.execute(
        "SELECT processing_status FROM communications WHERE id = ?", (COMM_ID,)
    ).fetchone()
    assert row["processing_status"] == "reviewed"


def test_5_03_complete_on_reviewed_fails():
    r = client.post(f"{PREFIX}/{COMM_ID}/complete")
    assert r.status_code == 400


# -- Audit & provenance --

def test_6_01_audit_log_populated():
    rows = _shared_db.execute("""
        SELECT * FROM review_action_log WHERE communication_id = ?
        ORDER BY created_at
    """, (COMM_ID,)).fetchall()
    assert len(rows) > 0
    action_types = {r["action_type"] for r in rows}
    expected = {"accept_item", "reject_item", "edit_item", "restore_item",
                "add_item", "accept_bundle", "reject_bundle", "edit_bundle",
                "move_item", "create_bundle", "merge_bundles", "complete_bundle_review"}
    missing = expected - action_types
    assert not missing, f"Missing audit types: {missing}"


def test_6_02_audit_has_fk_ids():
    rows = _shared_db.execute("""
        SELECT * FROM review_action_log
        WHERE communication_id = ? AND action_type = 'accept_item'
    """, (COMM_ID,)).fetchall()
    for r in rows:
        assert r["bundle_id"] is not None
        assert r["item_id"] is not None


def test_6_03_audit_details_json():
    rows = _shared_db.execute("""
        SELECT details FROM review_action_log
        WHERE communication_id = ? AND action_type = 'move_item'
    """, (COMM_ID,)).fetchall()
    for r in rows:
        d = json.loads(r["details"])
        assert "from_bundle_id" in d
        assert "to_bundle_id" in d
        assert "new_item_id" in d


# -- Regression --

def test_7_01_health_endpoint():
    r = client.get("/ai/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_7_02_config_endpoint():
    r = client.get("/ai/api/config")
    assert r.status_code == 200
    d = r.json()
    assert "extraction_policy" in d
    assert "trust_config" in d


def test_7_03_communications_list():
    r = client.get("/ai/api/communications")
    assert r.status_code == 200


# -- Edge cases --

def test_8_01_actions_on_non_review_state():
    r = client.post(f"{PREFIX}/{COMM_ID}/accept-item", json={
        "bundle_id": BUNDLE_IDS[0], "item_id": ITEM_IDS[0][0],
    })
    assert r.status_code == 400


def test_8_02_item_bundle_mismatch():
    test_comm_id = str(uuid.uuid4())
    test_bundle_id = str(uuid.uuid4())
    test_item_id = str(uuid.uuid4())
    wrong_bundle_id = str(uuid.uuid4())

    _shared_db.execute("""
        INSERT INTO communications (id, source_type, processing_status, created_at, updated_at)
        VALUES (?, 'audio', 'awaiting_bundle_review', datetime('now'), datetime('now'))
    """, (test_comm_id,))
    _shared_db.execute("""
        INSERT INTO review_bundles (id, communication_id, bundle_type, status,
                                    sort_order, created_at, updated_at)
        VALUES (?, ?, 'standalone', 'proposed', 1, datetime('now'), datetime('now'))
    """, (test_bundle_id, test_comm_id))
    _shared_db.execute("""
        INSERT INTO review_bundles (id, communication_id, bundle_type, status,
                                    sort_order, created_at, updated_at)
        VALUES (?, ?, 'standalone', 'proposed', 2, datetime('now'), datetime('now'))
    """, (wrong_bundle_id, test_comm_id))
    _shared_db.execute("""
        INSERT INTO review_bundle_items (id, bundle_id, item_type, status,
                                          proposed_data, sort_order, created_at, updated_at)
        VALUES (?, ?, 'task', 'proposed', '{"title":"test"}', 1, datetime('now'), datetime('now'))
    """, (test_item_id, test_bundle_id))
    _shared_db.commit()

    r = client.post(f"{PREFIX}/{test_comm_id}/accept-item", json={
        "bundle_id": wrong_bundle_id, "item_id": test_item_id,
    })
    assert r.status_code == 404


def test_8_03_reject_moved_item_fails():
    test_comm_id = str(uuid.uuid4())
    test_bundle_id = str(uuid.uuid4())
    moved_item_id = str(uuid.uuid4())

    _shared_db.execute("""
        INSERT INTO communications (id, source_type, processing_status, created_at, updated_at)
        VALUES (?, 'audio', 'bundle_review_in_progress', datetime('now'), datetime('now'))
    """, (test_comm_id,))
    _shared_db.execute("""
        INSERT INTO review_bundles (id, communication_id, bundle_type, status,
                                    sort_order, created_at, updated_at)
        VALUES (?, ?, 'standalone', 'proposed', 1, datetime('now'), datetime('now'))
    """, (test_bundle_id, test_comm_id))
    _shared_db.execute("""
        INSERT INTO review_bundle_items (id, bundle_id, item_type, status,
                                          proposed_data, sort_order, created_at, updated_at)
        VALUES (?, ?, 'task', 'moved', '{"title":"test"}', 1, datetime('now'), datetime('now'))
    """, (moved_item_id, test_bundle_id))
    _shared_db.commit()

    r = client.post(f"{PREFIX}/{test_comm_id}/reject-item", json={
        "bundle_id": test_bundle_id, "item_id": moved_item_id,
    })
    assert r.status_code == 400
    assert "moved" in r.json()["detail"]["message"].lower()


# =====================================================================
# RUNNER
# =====================================================================

def run_all():
    """Run all tests in order and report results."""
    import traceback

    # Get all test functions sorted by name (numbered prefixes enforce order)
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
    print("Phase 4C Runtime Verification -- Bundle Review Backend")
    print("=" * 60)
    passed, total, failed = run_all()
    sys.exit(0 if failed == 0 else 1)
