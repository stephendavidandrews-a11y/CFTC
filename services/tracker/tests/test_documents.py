"""Tests for documents router — CRUD, file upload, download."""
from tests.conftest import (
    seed_matter, seed_document, make_id,
)


# ── List ──────────────────────────────────────────────────────────────────────


def test_list_documents_empty(client, auth_headers):
    """GET /tracker/documents returns empty list when no documents exist."""
    resp = client.get("/tracker/documents", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["items"] == []
    assert data["total"] == 0


def test_list_documents_with_filters(client, auth_headers, db):
    """GET /tracker/documents filters by status and matter_id."""
    matter = seed_matter(db)
    seed_document(db, matter["id"], title="Draft Doc", status="draft")
    seed_document(db, matter["id"], title="Final Doc", status="final")

    resp = client.get("/tracker/documents?status=draft", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["total"] == 1
    assert resp.json()["items"][0]["title"] == "Draft Doc"


def test_list_documents_search(client, auth_headers, db):
    """GET /tracker/documents?search= filters by title substring."""
    matter = seed_matter(db)
    seed_document(db, matter["id"], title="Policy Memo")
    seed_document(db, matter["id"], title="Budget Report")

    resp = client.get("/tracker/documents?search=Policy", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["total"] == 1


# ── Get ───────────────────────────────────────────────────────────────────────


def test_get_document_success(client, auth_headers, db):
    """GET /tracker/documents/:id returns document with files and ETag."""
    matter = seed_matter(db)
    doc = seed_document(db, matter["id"], title="My Doc")
    resp = client.get(f"/tracker/documents/{doc['id']}", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["title"] == "My Doc"
    assert "files" in body
    assert "etag" in resp.headers


def test_get_document_not_found(client, auth_headers):
    """GET /tracker/documents/:id returns 404 for missing ID."""
    resp = client.get(f"/tracker/documents/{make_id()}", headers=auth_headers)
    assert resp.status_code == 404


# ── Create ────────────────────────────────────────────────────────────────────


def test_create_document_success(client, auth_headers, db):
    """POST /tracker/documents creates a document."""
    matter = seed_matter(db)
    payload = {
        "title": "New Document",
        "document_type": "legal_memo",
        "matter_id": matter["id"],
    }
    resp = client.post("/tracker/documents", json=payload, headers=auth_headers)
    assert resp.status_code == 200
    assert "id" in resp.json()


def test_create_document_validation_error(client, auth_headers):
    """POST /tracker/documents returns 422 when title is missing."""
    payload = {"document_type": "legal_memo"}
    resp = client.post("/tracker/documents", json=payload, headers=auth_headers)
    assert resp.status_code == 422


# ── Update ────────────────────────────────────────────────────────────────────


def test_update_document_success(client, auth_headers, db):
    """PUT /tracker/documents/:id updates fields."""
    matter = seed_matter(db)
    doc = seed_document(db, matter["id"], title="Old Title")
    etag = f'"{doc["updated_at"]}"'
    resp = client.put(
        f"/tracker/documents/{doc['id']}",
        json={"title": "New Title"},
        headers={**auth_headers, "If-Match": etag},
    )
    assert resp.status_code == 200
    assert resp.json()["updated"] is True


def test_update_document_not_found(client, auth_headers):
    """PUT /tracker/documents/:id returns 404 for missing ID."""
    resp = client.put(
        f"/tracker/documents/{make_id()}",
        json={"title": "X"},
        headers={**auth_headers, "If-Match": '"2026-01-01T00:00:00"'},
    )
    assert resp.status_code == 404


def test_update_document_empty_body(client, auth_headers, db):
    """PUT /tracker/documents/:id returns 400 when no fields provided."""
    matter = seed_matter(db)
    doc = seed_document(db, matter["id"])
    etag = f'"{doc["updated_at"]}"'
    resp = client.put(
        f"/tracker/documents/{doc['id']}",
        json={},
        headers={**auth_headers, "If-Match": etag},
    )
    assert resp.status_code == 400


# ── Delete ────────────────────────────────────────────────────────────────────


def test_delete_document_success(client, auth_headers, db):
    """DELETE /tracker/documents/:id removes document."""
    matter = seed_matter(db)
    doc = seed_document(db, matter["id"])
    etag = f'"{doc["updated_at"]}"'
    resp = client.delete(
        f"/tracker/documents/{doc['id']}",
        headers={**auth_headers, "If-Match": etag},
    )
    assert resp.status_code == 200
    assert resp.json()["deleted"] is True
    row = db.execute("SELECT * FROM documents WHERE id = ?", (doc["id"],)).fetchone()
    assert row is None


def test_delete_document_not_found(client, auth_headers):
    """DELETE /tracker/documents/:id returns 404 for missing ID."""
    resp = client.delete(
        f"/tracker/documents/{make_id()}",
        headers={**auth_headers, "If-Match": '"2026-01-01T00:00:00"'},
    )
    assert resp.status_code == 404
