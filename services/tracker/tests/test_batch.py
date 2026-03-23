"""Tests for batch write endpoint — atomic multi-record operations."""
import uuid
from tests.conftest import (
    seed_matter, seed_person, seed_organization, make_id,
)


def _batch(client, auth_headers, operations, idempotency_key=None, source="ai"):
    """Helper to POST /tracker/batch."""
    body = {"operations": operations, "source": source}
    if idempotency_key:
        body["idempotency_key"] = idempotency_key
    return client.post("/tracker/batch", json=body, headers=auth_headers)


# ── Basic insert ──────────────────────────────────────────────────────────────


def test_batch_single_insert(client, auth_headers, db):
    """Batch insert creates a record and returns its ID."""
    resp = _batch(client, auth_headers, [
        {"op": "insert", "table": "organizations", "data": {
            "name": "Batch Org", "organization_type": "federal_agency",
        }},
    ])
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert len(body["results"]) == 1
    assert body["results"][0]["op"] == "insert"
    rid = body["results"][0]["record_id"]
    row = db.execute("SELECT * FROM organizations WHERE id = ?", (rid,)).fetchone()
    assert row["name"] == "Batch Org"


def test_batch_multi_insert(client, auth_headers, db):
    """Batch inserts multiple records atomically."""
    resp = _batch(client, auth_headers, [
        {"op": "insert", "table": "organizations", "data": {"name": "Org A"}},
        {"op": "insert", "table": "organizations", "data": {"name": "Org B"}},
    ])
    assert resp.status_code == 200
    assert len(resp.json()["results"]) == 2


# ── Update ────────────────────────────────────────────────────────────────────


def test_batch_update(client, auth_headers, db):
    """Batch update modifies an existing record."""
    org = seed_organization(db, name="Old Name")
    resp = _batch(client, auth_headers, [
        {"op": "update", "table": "organizations", "record_id": org["id"],
         "data": {"name": "New Name"}},
    ])
    assert resp.status_code == 200
    row = db.execute("SELECT name FROM organizations WHERE id = ?", (org["id"],)).fetchone()
    assert row["name"] == "New Name"


def test_batch_update_missing_record(client, auth_headers):
    """Batch update returns 404 for nonexistent record."""
    resp = _batch(client, auth_headers, [
        {"op": "update", "table": "organizations", "record_id": make_id(),
         "data": {"name": "X"}},
    ])
    assert resp.status_code == 404
    assert resp.json()["detail"]["error_type"] == "missing_record"


# ── Delete ────────────────────────────────────────────────────────────────────


def test_batch_hard_delete_junction(client, auth_headers, db):
    """Batch delete hard-deletes from junction tables."""
    matter = seed_matter(db)
    person = seed_person(db)
    mp_id = make_id()
    db.execute(
        "INSERT INTO matter_people (id, matter_id, person_id, matter_role, created_at, updated_at) "
        "VALUES (?, ?, ?, 'stakeholder', datetime('now'), datetime('now'))",
        (mp_id, matter["id"], person["id"]),
    )
    db.commit()
    resp = _batch(client, auth_headers, [
        {"op": "delete", "table": "matter_people", "record_id": mp_id},
    ])
    assert resp.status_code == 200
    row = db.execute("SELECT * FROM matter_people WHERE id = ?", (mp_id,)).fetchone()
    assert row is None


def test_batch_soft_delete(client, auth_headers, db):
    """Batch delete on 'organizations' sets is_active=0 (soft delete)."""
    org = seed_organization(db)
    resp = _batch(client, auth_headers, [
        {"op": "delete", "table": "organizations", "record_id": org["id"]},
    ])
    assert resp.status_code == 200
    row = db.execute("SELECT is_active FROM organizations WHERE id = ?", (org["id"],)).fetchone()
    assert row["is_active"] == 0


def test_batch_delete_missing_record(client, auth_headers):
    """Batch delete returns 404 for nonexistent record."""
    resp = _batch(client, auth_headers, [
        {"op": "delete", "table": "matter_people", "record_id": make_id()},
    ])
    assert resp.status_code == 404


# ── Forward references ($ref) ────────────────────────────────────────────────


def test_batch_forward_reference(client, auth_headers, db):
    """Batch supports $ref: to link a child to a parent created earlier."""
    resp = _batch(client, auth_headers, [
        {"op": "insert", "table": "matters", "client_id": "m1",
         "data": {"title": "Ref Matter", "matter_type": "rulemaking",
                  "status": "active", "priority": "high",
                  "sensitivity": "normal",
                  "boss_involvement_level": "informed",
                  "next_step": "Draft"}},
        {"op": "insert", "table": "tasks",
         "data": {"title": "Ref Task", "matter_id": "$ref:m1",
                  "status": "open", "task_mode": "action", "priority": "medium"}},
    ])
    assert resp.status_code == 200
    results = resp.json()["results"]
    matter_id = results[0]["record_id"]
    task_id = results[1]["record_id"]
    task_row = db.execute("SELECT matter_id FROM tasks WHERE id = ?", (task_id,)).fetchone()
    assert task_row["matter_id"] == matter_id


def test_batch_unresolved_reference(client, auth_headers):
    """Batch rejects unresolved $ref: references."""
    resp = _batch(client, auth_headers, [
        {"op": "insert", "table": "tasks",
         "data": {"title": "Bad Ref", "matter_id": "$ref:nonexistent",
                  "status": "open", "task_mode": "action", "priority": "medium"}},
    ])
    assert resp.status_code == 400
    assert resp.json()["detail"]["error_type"] == "reference_resolution_failure"


# ── Validation ────────────────────────────────────────────────────────────────


def test_batch_empty_operations(client, auth_headers):
    """Batch rejects empty operations list."""
    resp = _batch(client, auth_headers, [])
    assert resp.status_code == 400


def test_batch_forbidden_table(client, auth_headers):
    """Batch rejects writes to unknown tables."""
    resp = _batch(client, auth_headers, [
        {"op": "insert", "table": "nonexistent_table", "data": {"x": 1}},
    ])
    assert resp.status_code == 400
    assert resp.json()["detail"]["error_type"] == "forbidden_table"


def test_batch_invalid_op(client, auth_headers):
    """Batch rejects unknown op types."""
    resp = _batch(client, auth_headers, [
        {"op": "upsert", "table": "organizations", "data": {"name": "X"}},
    ])
    assert resp.status_code == 400
    assert resp.json()["detail"]["error_type"] == "validation_failure"


def test_batch_update_missing_record_id(client, auth_headers):
    """Batch rejects update without record_id."""
    resp = _batch(client, auth_headers, [
        {"op": "update", "table": "organizations", "data": {"name": "X"}},
    ])
    assert resp.status_code == 400


def test_batch_invalid_columns(client, auth_headers):
    """Batch rejects data with columns not in the table schema."""
    resp = _batch(client, auth_headers, [
        {"op": "insert", "table": "organizations",
         "data": {"name": "OK", "fake_column": "bad"}},
    ])
    assert resp.status_code == 400
    assert resp.json()["detail"]["error_type"] == "schema_mismatch"


def test_batch_enum_constraint_violation(client, auth_headers, db):
    """Batch rejects invalid enum values (e.g. task_mode)."""
    matter = seed_matter(db)
    resp = _batch(client, auth_headers, [
        {"op": "insert", "table": "tasks",
         "data": {"title": "Bad Mode", "matter_id": matter["id"],
                  "status": "open", "task_mode": "invalid_mode", "priority": "medium"}},
    ])
    assert resp.status_code == 400
    assert resp.json()["detail"]["error_type"] == "validation_failure"


# ── Idempotency ──────────────────────────────────────────────────────────────


def test_batch_idempotency_replay(client, auth_headers, db):
    """Same idempotency_key + payload replays the original response."""
    key = str(uuid.uuid4())
    ops = [{"op": "insert", "table": "organizations", "data": {"name": "Idem Org"}}]
    resp1 = _batch(client, auth_headers, ops, idempotency_key=key)
    assert resp1.status_code == 200
    resp2 = _batch(client, auth_headers, ops, idempotency_key=key)
    assert resp2.status_code == 200
    # Should return same result (replay)
    assert resp1.json()["results"][0]["record_id"] == resp2.json()["results"][0]["record_id"]


def test_batch_idempotency_conflict(client, auth_headers, db):
    """Same idempotency_key with different payload raises 409."""
    key = str(uuid.uuid4())
    ops1 = [{"op": "insert", "table": "organizations", "data": {"name": "Org One"}}]
    ops2 = [{"op": "insert", "table": "organizations", "data": {"name": "Org Two"}}]
    resp1 = _batch(client, auth_headers, ops1, idempotency_key=key)
    assert resp1.status_code == 200
    resp2 = _batch(client, auth_headers, ops2, idempotency_key=key)
    assert resp2.status_code == 409


# ── Rollback on failure ──────────────────────────────────────────────────────


def test_batch_rollback_on_failure(client, auth_headers, db):
    """If a later operation fails, earlier operations are rolled back."""
    count_before = db.execute("SELECT COUNT(*) as c FROM organizations").fetchone()["c"]
    resp = _batch(client, auth_headers, [
        {"op": "insert", "table": "organizations", "data": {"name": "Should Rollback"}},
        {"op": "update", "table": "organizations", "record_id": make_id(),
         "data": {"name": "X"}},  # This will fail — missing record
    ])
    assert resp.status_code == 404
    count_after = db.execute("SELECT COUNT(*) as c FROM organizations").fetchone()["c"]
    assert count_after == count_before  # Rolled back
