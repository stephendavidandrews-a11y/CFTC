"""Tests for context_notes router — CRUD, links, by-entity queries."""
from tests.conftest import (
    seed_person, make_id,
)


def _seed_context_note(db, **overrides):
    """Insert a context note directly into the DB and return its dict."""
    from datetime import datetime

    note = {
        "id": make_id(),
        "title": "Test Note",
        "body": "Some context about this thing.",
        "category": "institutional_knowledge",
        "posture": "factual",
        "durability": "durable",
        "sensitivity": "low",
        "status": "active",
        "created_by_type": "human",
        "notes_visibility": "normal",
        "is_active": 1,
        "source": "manual",
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
    }
    note.update(overrides)
    cols = ", ".join(note.keys())
    placeholders = ", ".join(f":{k}" for k in note.keys())
    db.execute(f"INSERT INTO context_notes ({cols}) VALUES ({placeholders})", note)
    db.commit()
    return note


def _seed_link(db, note_id, entity_type, entity_id, role="subject"):
    """Insert a context_note_link row."""
    from datetime import datetime

    lid = make_id()
    db.execute(
        "INSERT INTO context_note_links (id, context_note_id, entity_type, entity_id, "
        "relationship_role, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (lid, note_id, entity_type, entity_id, role, datetime.now().isoformat()),
    )
    db.commit()
    return lid


# ── List ──────────────────────────────────────────────────────────────────────


def test_list_context_notes_empty(client, auth_headers):
    """GET /tracker/context-notes returns empty list when none exist."""
    resp = client.get("/tracker/context-notes", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["total"] == 0


def test_list_context_notes_returns_seeded(client, auth_headers, db):
    """GET /tracker/context-notes returns seeded notes."""
    _seed_context_note(db, title="Note Alpha")
    resp = client.get("/tracker/context-notes", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["total"] == 1
    assert resp.json()["items"][0]["title"] == "Note Alpha"


def test_list_context_notes_filter_by_category(client, auth_headers, db):
    """GET /tracker/context-notes?category= filters correctly."""
    _seed_context_note(db, title="A", category="people_insight")
    _seed_context_note(db, title="B", category="process_note")
    resp = client.get(
        "/tracker/context-notes?category=people_insight", headers=auth_headers
    )
    assert resp.status_code == 200
    assert resp.json()["total"] == 1


def test_list_context_notes_search(client, auth_headers, db):
    """GET /tracker/context-notes?search= filters by title/body."""
    _seed_context_note(db, title="Important Insight", body="x")
    _seed_context_note(db, title="Other Note", body="y")
    resp = client.get(
        "/tracker/context-notes?search=Important", headers=auth_headers
    )
    assert resp.status_code == 200
    assert resp.json()["total"] == 1


# ── By Entity ─────────────────────────────────────────────────────────────────


def test_get_by_entity(client, auth_headers, db):
    """GET /tracker/context-notes/by-entity/:type/:id returns linked notes."""
    person = seed_person(db)
    note = _seed_context_note(db, title="Person Insight")
    _seed_link(db, note["id"], "person", person["id"])

    resp = client.get(
        f"/tracker/context-notes/by-entity/person/{person['id']}",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert len(resp.json()["items"]) == 1
    assert resp.json()["items"][0]["title"] == "Person Insight"


def test_get_by_entity_invalid_type(client, auth_headers):
    """GET /tracker/context-notes/by-entity/:type/:id rejects invalid type."""
    resp = client.get(
        f"/tracker/context-notes/by-entity/widget/{make_id()}",
        headers=auth_headers,
    )
    assert resp.status_code == 400


# ── Get ───────────────────────────────────────────────────────────────────────


def test_get_context_note_success(client, auth_headers, db):
    """GET /tracker/context-notes/:id returns note with links and ETag."""
    note = _seed_context_note(db, title="Deep Insight")
    resp = client.get(f"/tracker/context-notes/{note['id']}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["title"] == "Deep Insight"
    assert "links" in resp.json()
    assert "etag" in resp.headers


def test_get_context_note_not_found(client, auth_headers):
    """GET /tracker/context-notes/:id returns 404 for missing ID."""
    resp = client.get(f"/tracker/context-notes/{make_id()}", headers=auth_headers)
    assert resp.status_code == 404


# ── Create ────────────────────────────────────────────────────────────────────


def test_create_context_note_success(client, auth_headers):
    """POST /tracker/context-notes creates a note."""
    payload = {
        "title": "New Note",
        "body": "Some important context.",
        "category": "strategic_context",
    }
    resp = client.post("/tracker/context-notes", json=payload, headers=auth_headers)
    assert resp.status_code == 200
    assert "id" in resp.json()


def test_create_context_note_invalid_category(client, auth_headers):
    """POST /tracker/context-notes rejects invalid category via enum check."""
    payload = {
        "title": "Bad Note",
        "body": "text",
        "category": "nonexistent_category",
    }
    resp = client.post("/tracker/context-notes", json=payload, headers=auth_headers)
    assert resp.status_code == 400


def test_create_context_note_validation_missing_body(client, auth_headers):
    """POST /tracker/context-notes returns 422 when body is missing."""
    payload = {"title": "No Body", "category": "people_insight"}
    resp = client.post("/tracker/context-notes", json=payload, headers=auth_headers)
    assert resp.status_code == 422


# ── Update ────────────────────────────────────────────────────────────────────


def test_update_context_note_success(client, auth_headers, db):
    """PUT /tracker/context-notes/:id updates fields."""
    note = _seed_context_note(db, title="Old Title")
    etag = f'"{note["updated_at"]}"'
    resp = client.put(
        f"/tracker/context-notes/{note['id']}",
        json={"title": "New Title"},
        headers={**auth_headers, "If-Match": etag},
    )
    assert resp.status_code == 200
    assert resp.json()["updated"] is True


def test_update_context_note_invalid_posture(client, auth_headers, db):
    """PUT /tracker/context-notes/:id rejects invalid posture."""
    note = _seed_context_note(db)
    etag = f'"{note["updated_at"]}"'
    resp = client.put(
        f"/tracker/context-notes/{note['id']}",
        json={"posture": "aggressive"},
        headers={**auth_headers, "If-Match": etag},
    )
    assert resp.status_code == 400


# ── Delete (soft) ─────────────────────────────────────────────────────────────


def test_delete_context_note_soft(client, auth_headers, db):
    """DELETE /tracker/context-notes/:id soft-deletes (is_active=0)."""
    note = _seed_context_note(db)
    etag = f'"{note["updated_at"]}"'
    resp = client.delete(
        f"/tracker/context-notes/{note['id']}",
        headers={**auth_headers, "If-Match": etag},
    )
    assert resp.status_code == 200
    assert resp.json()["deleted"] is True
    row = db.execute(
        "SELECT is_active FROM context_notes WHERE id = ?", (note["id"],)
    ).fetchone()
    assert row["is_active"] == 0


# ── Links ─────────────────────────────────────────────────────────────────────


def test_add_link(client, auth_headers, db):
    """POST /tracker/context-notes/:id/links creates a link."""
    note = _seed_context_note(db)
    person = seed_person(db)
    payload = {
        "entity_type": "person",
        "entity_id": person["id"],
        "relationship_role": "subject",
    }
    resp = client.post(
        f"/tracker/context-notes/{note['id']}/links",
        json=payload,
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert "id" in resp.json()


def test_add_link_invalid_entity_type(client, auth_headers, db):
    """POST /tracker/context-notes/:id/links rejects invalid entity_type."""
    note = _seed_context_note(db)
    payload = {
        "entity_type": "widget",
        "entity_id": make_id(),
        "relationship_role": "subject",
    }
    resp = client.post(
        f"/tracker/context-notes/{note['id']}/links",
        json=payload,
        headers=auth_headers,
    )
    assert resp.status_code == 400


def test_remove_link(client, auth_headers, db):
    """DELETE /tracker/context-notes/:id/links/:lid removes a link."""
    note = _seed_context_note(db)
    person = seed_person(db)
    lid = _seed_link(db, note["id"], "person", person["id"])
    resp = client.delete(
        f"/tracker/context-notes/{note['id']}/links/{lid}",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["deleted"] is True


def test_remove_link_not_found(client, auth_headers, db):
    """DELETE /tracker/context-notes/:id/links/:lid returns 404 for missing link."""
    note = _seed_context_note(db)
    resp = client.delete(
        f"/tracker/context-notes/{note['id']}/links/{make_id()}",
        headers=auth_headers,
    )
    assert resp.status_code == 404
