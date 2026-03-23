"""Comprehensive tests for the people router."""
import uuid
from tests.conftest import (
    seed_person, seed_organization, make_id,
)


# ---------------------------------------------------------------------------
# List / filter / sort / paginate
# ---------------------------------------------------------------------------

def test_list_people_empty(client, auth_headers):
    """GET /tracker/people returns empty list when no people exist."""
    resp = client.get("/tracker/people", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["items"] == []
    assert data["total"] == 0
    assert "summary" in data


def test_list_people_returns_seeded(client, auth_headers, db):
    """GET /tracker/people returns seeded people."""
    seed_person(db, full_name="Alice Adams")
    seed_person(db, full_name="Bob Baker")
    resp = client.get("/tracker/people", headers=auth_headers)
    data = resp.json()
    assert data["total"] == 2


def test_list_people_search(client, auth_headers, db):
    """Search filters by full_name."""
    seed_person(db, full_name="Carol Chen")
    seed_person(db, full_name="Dave Davis")
    resp = client.get("/tracker/people?search=Carol", headers=auth_headers)
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["full_name"] == "Carol Chen"


def test_list_people_filter_organization(client, auth_headers, db):
    """Filter by organization_id."""
    org = seed_organization(db, name="CFTC")
    seed_person(db, full_name="Inside", organization_id=org["id"])
    seed_person(db, full_name="Outside")
    resp = client.get(f"/tracker/people?organization_id={org['id']}", headers=auth_headers)
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["full_name"] == "Inside"


def test_list_people_filter_is_active(client, auth_headers, db):
    """Filter by is_active flag."""
    seed_person(db, full_name="Active", is_active=1)
    seed_person(db, full_name="Inactive", is_active=0)
    resp = client.get("/tracker/people?is_active=true", headers=auth_headers)
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["full_name"] == "Active"


def test_list_people_pagination(client, auth_headers, db):
    """Pagination with limit and offset."""
    for i in range(5):
        seed_person(db, full_name=f"Person {i}")
    resp = client.get("/tracker/people?limit=2&offset=0", headers=auth_headers)
    data = resp.json()
    assert data["total"] == 5
    assert len(data["items"]) == 2


# ---------------------------------------------------------------------------
# Get single person
# ---------------------------------------------------------------------------

def test_get_person_success(client, auth_headers, db):
    """GET /tracker/people/{id} returns full detail with sub-resources."""
    p = seed_person(db)
    resp = client.get(f"/tracker/people/{p['id']}", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == p["id"]
    assert "matters" in data
    assert "tasks" in data
    assert "meetings" in data
    assert "ETag" in resp.headers


def test_get_person_not_found(client, auth_headers):
    """GET /tracker/people/{id} returns 404 for missing person."""
    resp = client.get(f"/tracker/people/{make_id()}", headers=auth_headers)
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Create person
# ---------------------------------------------------------------------------

def test_create_person_success(client, auth_headers):
    """POST /tracker/people creates a new person."""
    resp = client.post("/tracker/people",
                       json={"full_name": "New Person"},
                       headers=auth_headers)
    assert resp.status_code == 200
    assert "id" in resp.json()


def test_create_person_missing_name(client, auth_headers):
    """POST /tracker/people returns 422 when full_name is missing."""
    resp = client.post("/tracker/people", json={}, headers=auth_headers)
    assert resp.status_code == 422


def test_create_person_idempotency(client, auth_headers):
    """Same idempotency key returns cached result."""
    idem_key = str(uuid.uuid4())
    payload = {"full_name": "Idem Person"}
    headers = {**auth_headers, "idempotency-key": idem_key}
    resp1 = client.post("/tracker/people", json=payload, headers=headers)
    resp2 = client.post("/tracker/people", json=payload, headers=headers)
    assert resp1.json()["id"] == resp2.json()["id"]


# ---------------------------------------------------------------------------
# Update person
# ---------------------------------------------------------------------------

def test_update_person_success(client, auth_headers, db):
    """PUT /tracker/people/{id} updates the person."""
    p = seed_person(db)
    resp = client.put(f"/tracker/people/{p['id']}",
                      json={"title": "Senior Director"},
                      headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["updated"] is True


def test_update_person_not_found(client, auth_headers):
    """PUT /tracker/people/{id} returns 404 for missing person."""
    resp = client.put(f"/tracker/people/{make_id()}",
                      json={"title": "X"}, headers=auth_headers)
    assert resp.status_code == 404


def test_update_person_empty_body(client, auth_headers, db):
    """PUT /tracker/people/{id} with no fields returns 400."""
    p = seed_person(db)
    resp = client.put(f"/tracker/people/{p['id']}", json={}, headers=auth_headers)
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Delete (soft-deactivate) person
# ---------------------------------------------------------------------------

def test_delete_person_success(client, auth_headers, db):
    """DELETE /tracker/people/{id} soft-deletes by setting is_active=0."""
    p = seed_person(db)
    resp = client.delete(f"/tracker/people/{p['id']}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["deleted"] is True
    row = db.execute("SELECT is_active FROM people WHERE id = ?", (p["id"],)).fetchone()
    assert row["is_active"] == 0


def test_delete_person_not_found(client, auth_headers):
    """DELETE /tracker/people/{id} returns 404 for missing person."""
    resp = client.delete(f"/tracker/people/{make_id()}", headers=auth_headers)
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Person profile
# ---------------------------------------------------------------------------

def test_get_profile_empty(client, auth_headers, db):
    """GET /tracker/people/{id}/profile returns empty structure when no profile."""
    p = seed_person(db)
    resp = client.get(f"/tracker/people/{p['id']}/profile", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["person_id"] == p["id"]
    assert data["birthday"] is None


def test_upsert_profile_create_then_update(client, auth_headers, db):
    """PUT /tracker/people/{id}/profile creates then updates profile."""
    p = seed_person(db)
    # Create
    resp1 = client.put(f"/tracker/people/{p['id']}/profile",
                       json={"birthday": "1980-01-15", "hometown": "Chicago"},
                       headers=auth_headers)
    assert resp1.status_code == 200
    assert resp1.json()["birthday"] == "1980-01-15"

    # Update
    resp2 = client.put(f"/tracker/people/{p['id']}/profile",
                       json={"interests": "sailing"},
                       headers=auth_headers)
    assert resp2.status_code == 200
    data = resp2.json()
    assert data["interests"] == "sailing"
    assert data["birthday"] == "1980-01-15"  # preserved from first call


def test_profile_404_for_missing_person(client, auth_headers):
    """Profile endpoints return 404 for nonexistent person."""
    fake_id = make_id()
    resp = client.get(f"/tracker/people/{fake_id}/profile", headers=auth_headers)
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Auth required
# ---------------------------------------------------------------------------

def test_people_auth_required(client):
    """People endpoints reject unauthenticated requests."""
    resp = client.get("/tracker/people")
    assert resp.status_code == 401
