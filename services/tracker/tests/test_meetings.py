"""Tests for meetings router — CRUD, participants, matter links."""
from tests.conftest import (
    seed_matter, seed_person, seed_meeting, make_id,
)


# ── List ──────────────────────────────────────────────────────────────────────


def test_list_meetings_empty(client, auth_headers):
    """GET /tracker/meetings returns empty list when no meetings exist."""
    resp = client.get("/tracker/meetings", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["items"] == []
    assert data["total"] == 0


def test_list_meetings_returns_seeded(client, auth_headers, db):
    """GET /tracker/meetings returns seeded meetings."""
    m = seed_meeting(db, title="Budget Review")
    resp = client.get("/tracker/meetings", headers=auth_headers)
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 1
    assert items[0]["title"] == "Budget Review"


def test_list_meetings_search_filter(client, auth_headers, db):
    """GET /tracker/meetings?search= filters by title."""
    seed_meeting(db, title="Alpha Meeting")
    seed_meeting(db, title="Beta Meeting")
    resp = client.get("/tracker/meetings?search=Alpha", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["total"] == 1
    assert resp.json()["items"][0]["title"] == "Alpha Meeting"


def test_list_meetings_filter_by_matter(client, auth_headers, db):
    """GET /tracker/meetings?matter_id= filters by linked matter."""
    matter = seed_matter(db)
    m = seed_meeting(db, title="Linked Meeting")
    # Manually link meeting to matter
    db.execute(
        "INSERT INTO meeting_matters (id, meeting_id, matter_id, relationship_type, created_at, updated_at) "
        "VALUES (?, ?, ?, 'primary topic', datetime('now'), datetime('now'))",
        (make_id(), m["id"], matter["id"]),
    )
    db.commit()
    seed_meeting(db, title="Unlinked Meeting")

    resp = client.get(
        f"/tracker/meetings?matter_id={matter['id']}", headers=auth_headers
    )
    assert resp.status_code == 200
    assert resp.json()["total"] == 1
    assert resp.json()["items"][0]["title"] == "Linked Meeting"


# ── Get ───────────────────────────────────────────────────────────────────────


def test_get_meeting_success(client, auth_headers, db):
    """GET /tracker/meetings/:id returns meeting with ETag."""
    m = seed_meeting(db, title="Standup")
    resp = client.get(f"/tracker/meetings/{m['id']}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["title"] == "Standup"
    assert "etag" in resp.headers


def test_get_meeting_not_found(client, auth_headers):
    """GET /tracker/meetings/:id returns 404 for missing ID."""
    resp = client.get(f"/tracker/meetings/{make_id()}", headers=auth_headers)
    assert resp.status_code == 404


# ── Create ────────────────────────────────────────────────────────────────────


def test_create_meeting_minimal(client, auth_headers):
    """POST /tracker/meetings creates a meeting with required fields only."""
    payload = {
        "title": "New Meeting",
        "date_time_start": "2026-04-01T10:00:00",
    }
    resp = client.post("/tracker/meetings", json=payload, headers=auth_headers)
    assert resp.status_code == 200
    assert "id" in resp.json()


def test_create_meeting_with_participants(client, auth_headers, db):
    """POST /tracker/meetings creates meeting with inline participants."""
    person = seed_person(db)
    payload = {
        "title": "Meeting With People",
        "date_time_start": "2026-04-01T10:00:00",
        "participants": [
            {"person_id": person["id"], "meeting_role": "lead"},
        ],
    }
    resp = client.post("/tracker/meetings", json=payload, headers=auth_headers)
    assert resp.status_code == 200
    mid = resp.json()["id"]
    # Verify participant was created
    row = db.execute(
        "SELECT * FROM meeting_participants WHERE meeting_id = ?", (mid,)
    ).fetchone()
    assert row is not None
    assert row["person_id"] == person["id"]


def test_create_meeting_validation_missing_title(client, auth_headers):
    """POST /tracker/meetings returns 422 when title is missing."""
    payload = {"date_time_start": "2026-04-01T10:00:00"}
    resp = client.post("/tracker/meetings", json=payload, headers=auth_headers)
    assert resp.status_code == 422


# ── Update ────────────────────────────────────────────────────────────────────


def test_update_meeting_success(client, auth_headers, db):
    """PUT /tracker/meetings/:id updates fields."""
    m = seed_meeting(db, title="Old Title")
    etag = f'"{m["updated_at"]}"'
    resp = client.put(
        f"/tracker/meetings/{m['id']}",
        json={"title": "New Title"},
        headers={**auth_headers, "If-Match": etag},
    )
    assert resp.status_code == 200
    assert resp.json()["updated"] is True


def test_update_meeting_not_found(client, auth_headers):
    """PUT /tracker/meetings/:id returns 404 for missing ID."""
    resp = client.put(
        f"/tracker/meetings/{make_id()}",
        json={"title": "X"},
        headers={**auth_headers, "If-Match": '"2026-01-01T00:00:00"'},
    )
    assert resp.status_code == 404


def test_update_meeting_no_fields(client, auth_headers, db):
    """PUT /tracker/meetings/:id returns 400 if body has no fields."""
    m = seed_meeting(db)
    etag = f'"{m["updated_at"]}"'
    resp = client.put(
        f"/tracker/meetings/{m['id']}",
        json={},
        headers={**auth_headers, "If-Match": etag},
    )
    assert resp.status_code == 400


# ── Delete ────────────────────────────────────────────────────────────────────


def test_delete_meeting_success(client, auth_headers, db):
    """DELETE /tracker/meetings/:id removes meeting."""
    m = seed_meeting(db)
    etag = f'"{m["updated_at"]}"'
    resp = client.delete(
        f"/tracker/meetings/{m['id']}",
        headers={**auth_headers, "If-Match": etag},
    )
    assert resp.status_code == 200
    assert resp.json()["deleted"] is True
    # Confirm gone
    row = db.execute("SELECT * FROM meetings WHERE id = ?", (m["id"],)).fetchone()
    assert row is None


def test_delete_meeting_not_found(client, auth_headers):
    """DELETE /tracker/meetings/:id returns 404 for missing ID."""
    resp = client.delete(
        f"/tracker/meetings/{make_id()}",
        headers={**auth_headers, "If-Match": '"2026-01-01T00:00:00"'},
    )
    assert resp.status_code == 404


# ── Participants (post-creation) ──────────────────────────────────────────────


def test_add_participant(client, auth_headers, db):
    """POST /tracker/meetings/:id/participants adds a participant."""
    m = seed_meeting(db)
    person = seed_person(db)
    resp = client.post(
        f"/tracker/meetings/{m['id']}/participants",
        json={"person_id": person["id"], "meeting_role": "presenter"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert "id" in resp.json()


def test_add_participant_missing_person_id(client, auth_headers, db):
    """POST /tracker/meetings/:id/participants returns 400 without person_id."""
    m = seed_meeting(db)
    resp = client.post(
        f"/tracker/meetings/{m['id']}/participants",
        json={"meeting_role": "attendee"},
        headers=auth_headers,
    )
    assert resp.status_code == 400


def test_remove_participant(client, auth_headers, db):
    """DELETE /tracker/meetings/:id/participants/:pid removes participant."""
    m = seed_meeting(db)
    person = seed_person(db)
    pid = make_id()
    db.execute(
        "INSERT INTO meeting_participants (id, meeting_id, person_id, meeting_role) "
        "VALUES (?, ?, ?, 'attendee')",
        (pid, m["id"], person["id"]),
    )
    db.commit()
    resp = client.delete(
        f"/tracker/meetings/{m['id']}/participants/{pid}",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["deleted"] is True


# ── Matters (post-creation) ──────────────────────────────────────────────────


def test_update_meeting_matters(client, auth_headers, db):
    """PUT /tracker/meetings/:id/matters replaces linked matters."""
    m = seed_meeting(db)
    mat1 = seed_matter(db, title="Matter One")
    mat2 = seed_matter(db, title="Matter Two")
    resp = client.put(
        f"/tracker/meetings/{m['id']}/matters",
        json={"matter_ids": [mat1["id"], mat2["id"]]},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["matter_count"] == 2
