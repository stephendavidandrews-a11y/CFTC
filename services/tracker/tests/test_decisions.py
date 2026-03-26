"""Tests for decisions router — CRUD operations."""

from tests.conftest import (
    seed_matter,
    seed_decision,
    make_id,
)


# ── List ──────────────────────────────────────────────────────────────────────


def test_list_decisions_empty(client, auth_headers):
    """GET /tracker/decisions returns empty list when no decisions exist."""
    resp = client.get("/tracker/decisions", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["items"] == []
    assert data["total"] == 0


def test_list_decisions_with_filters(client, auth_headers, db):
    """GET /tracker/decisions filters by status and matter_id."""
    matter = seed_matter(db)
    seed_decision(db, matter["id"], title="Decision A", status="pending")
    seed_decision(db, matter["id"], title="Decision B", status="made")

    resp = client.get("/tracker/decisions?status=pending", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["total"] == 1
    assert resp.json()["items"][0]["title"] == "Decision A"


def test_list_decisions_search(client, auth_headers, db):
    """GET /tracker/decisions?search= filters by title."""
    matter = seed_matter(db)
    seed_decision(db, matter["id"], title="Budget Allocation")
    seed_decision(db, matter["id"], title="Staffing Plan")

    resp = client.get("/tracker/decisions?search=Budget", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["total"] == 1


# ── Get ───────────────────────────────────────────────────────────────────────


def test_get_decision_success(client, auth_headers, db):
    """GET /tracker/decisions/:id returns decision with ETag."""
    matter = seed_matter(db)
    dec = seed_decision(db, matter["id"], title="My Decision")
    resp = client.get(f"/tracker/decisions/{dec['id']}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["title"] == "My Decision"
    assert "etag" in resp.headers


def test_get_decision_not_found(client, auth_headers):
    """GET /tracker/decisions/:id returns 404 for missing ID."""
    resp = client.get(f"/tracker/decisions/{make_id()}", headers=auth_headers)
    assert resp.status_code == 404


# ── Create ────────────────────────────────────────────────────────────────────


def test_create_decision_success(client, auth_headers, db):
    """POST /tracker/decisions creates a decision."""
    matter = seed_matter(db)
    payload = {
        "title": "New Decision",
        "matter_id": matter["id"],
    }
    resp = client.post("/tracker/decisions", json=payload, headers=auth_headers)
    assert resp.status_code == 200
    assert "id" in resp.json()


def test_create_decision_validation_error(client, auth_headers, db):
    """POST /tracker/decisions returns 422 when title is missing."""
    matter = seed_matter(db)
    payload = {"matter_id": matter["id"]}
    resp = client.post("/tracker/decisions", json=payload, headers=auth_headers)
    assert resp.status_code == 422


# ── Update ────────────────────────────────────────────────────────────────────


def test_update_decision_success(client, auth_headers, db):
    """PUT /tracker/decisions/:id updates fields."""
    matter = seed_matter(db)
    dec = seed_decision(db, matter["id"], title="Old Title")
    etag = f'"{dec["updated_at"]}"'
    resp = client.put(
        f"/tracker/decisions/{dec['id']}",
        json={"title": "New Title"},
        headers={**auth_headers, "If-Match": etag},
    )
    assert resp.status_code == 200
    assert resp.json()["updated"] is True


def test_update_decision_not_found(client, auth_headers):
    """PUT /tracker/decisions/:id returns 404 for missing ID."""
    resp = client.put(
        f"/tracker/decisions/{make_id()}",
        json={"title": "X"},
        headers={**auth_headers, "If-Match": '"2026-01-01T00:00:00"'},
    )
    assert resp.status_code == 404


# ── Delete ────────────────────────────────────────────────────────────────────


def test_delete_decision_success(client, auth_headers, db):
    """DELETE /tracker/decisions/:id removes decision."""
    matter = seed_matter(db)
    dec = seed_decision(db, matter["id"])
    etag = f'"{dec["updated_at"]}"'
    resp = client.delete(
        f"/tracker/decisions/{dec['id']}",
        headers={**auth_headers, "If-Match": etag},
    )
    assert resp.status_code == 200
    assert resp.json()["deleted"] is True
    row = db.execute("SELECT * FROM decisions WHERE id = ?", (dec["id"],)).fetchone()
    assert row is None


def test_delete_decision_not_found(client, auth_headers):
    """DELETE /tracker/decisions/:id returns 404 for missing ID."""
    resp = client.delete(
        f"/tracker/decisions/{make_id()}",
        headers={**auth_headers, "If-Match": '"2026-01-01T00:00:00"'},
    )
    assert resp.status_code == 404
