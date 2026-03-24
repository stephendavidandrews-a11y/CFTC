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
            "name": "Batch Org", "organization_type": "Federal agency",
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
                  "status": "framing issue", "priority": "important this month",
                  "sensitivity": "routine",
                  "boss_involvement_level": "keep boss informed",
                  "next_step": "Draft"}},
        {"op": "insert", "table": "tasks",
         "data": {"title": "Ref Task", "matter_id": "$ref:m1",
                  "status": "not started", "task_mode": "action", "priority": "normal"}},
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
                  "status": "not started", "task_mode": "action", "priority": "normal"}},
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
                  "status": "not started", "task_mode": "invalid_mode", "priority": "normal"}},
    ])
    assert resp.status_code == 400
    assert resp.json()["detail"]["error_type"] == "validation_failure"


def test_batch_rejects_invalid_meeting_relationship_enum(client, auth_headers, db):
    """Batch validates enum-backed relationship_type on meeting_matters."""
    matter = seed_matter(db)
    meeting_id = make_id()
    db.execute(
        "INSERT INTO meetings (id, title, date_time_start, meeting_type, source, created_at, updated_at) "
        "VALUES (?, 'Test Meeting', datetime('now'), 'leadership meeting', 'manual', datetime('now'), datetime('now'))",
        (meeting_id,),
    )
    db.commit()

    resp = _batch(client, auth_headers, [
        {"op": "insert", "table": "meeting_matters", "data": {
            "meeting_id": meeting_id,
            "matter_id": matter["id"],
            "relationship_type": "discussed",
        }},
    ])
    assert resp.status_code == 400
    assert resp.json()["detail"]["error_type"] == "validation_failure"


def test_batch_accepts_context_note_and_links(client, auth_headers, db):
    """Batch supports context_notes and context_note_links as first-class AI writes."""
    matter = seed_matter(db)
    resp = _batch(client, auth_headers, [
        {"op": "insert", "table": "context_notes", "client_id": "note1", "data": {
            "title": "Leadership preference",
            "body": "Keep drafts tight and decision-oriented.",
            "category": "policy_operating_rule",
            "matter_id": matter["id"],
        }},
        {"op": "insert", "table": "context_note_links", "data": {
            "context_note_id": "$ref:note1",
            "entity_type": "matter",
            "entity_id": matter["id"],
            "relationship_role": "subject",
        }},
    ])
    assert resp.status_code == 200
    note_id = resp.json()["results"][0]["record_id"]
    note = db.execute("SELECT * FROM context_notes WHERE id = ?", (note_id,)).fetchone()
    link = db.execute("SELECT * FROM context_note_links WHERE context_note_id = ?", (note_id,)).fetchone()
    assert note["matter_id"] == matter["id"]
    assert link["entity_id"] == matter["id"]


def test_batch_rejects_unsupported_org_stakeholder_shape(client, auth_headers, db):
    """Batch rejects stale AI shapes that send nonexistent matter_organizations columns."""
    matter = seed_matter(db)
    org = seed_organization(db)
    resp = _batch(client, auth_headers, [
        {"op": "insert", "table": "matter_organizations", "data": {
            "matter_id": matter["id"],
            "organization_id": org["id"],
            "organization_role": "partner agency",
            "engagement_level": "consulted",
        }},
    ])
    assert resp.status_code == 400
    assert resp.json()["detail"]["error_type"] == "schema_mismatch"


def test_batch_upserts_person_profile_by_person_id(client, auth_headers, db):
    """Repeated person_profiles inserts upsert deterministically by person_id."""
    person = seed_person(db)

    first = _batch(client, auth_headers, [
        {"op": "insert", "table": "person_profiles", "data": {
            "person_id": person["id"],
            "education_summary": "Georgetown Law",
        }, "_meta": {"upsert_by": "person_id"}},
    ])
    assert first.status_code == 200

    second = _batch(client, auth_headers, [
        {"op": "insert", "table": "person_profiles", "data": {
            "person_id": person["id"],
            "education_summary": "Georgetown Law",
            "prior_roles_summary": "SEC Division of Trading and Markets",
        }, "_meta": {"upsert_by": "person_id"}},
    ])
    assert second.status_code == 200

    rows = db.execute("SELECT * FROM person_profiles WHERE person_id = ?", (person["id"],)).fetchall()
    assert len(rows) == 1
    assert rows[0]["prior_roles_summary"] == "SEC Division of Trading and Markets"
    assert second.json()["results"][0]["op"] == "update"


def test_schema_version_reports_stabilized_contract(client, auth_headers):
    """Schema handshake advertises the live contract tables and capabilities."""
    resp = client.get("/tracker/schema/version", headers=auth_headers)
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["schema_version"] == "1.2.0"
    assert "context_notes" in payload["ai_writable_tables"]
    assert "context_note_links" in payload["ai_writable_tables"]
    assert "person_profiles" in payload["ai_writable_tables"]
    assert "enum_validation" in payload["capabilities"]
    assert "upsert_by" in payload["capabilities"]


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
