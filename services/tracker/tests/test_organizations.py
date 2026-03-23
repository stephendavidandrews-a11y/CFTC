"""Comprehensive tests for the organizations router."""
import uuid
from tests.conftest import (
    seed_organization, make_id,
)


# ---------------------------------------------------------------------------
# List / filter / sort / paginate
# ---------------------------------------------------------------------------

def test_list_orgs_empty(client, auth_headers):
    """GET /tracker/organizations returns empty list when no orgs exist."""
    resp = client.get("/tracker/organizations", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["items"] == []
    assert data["total"] == 0
    assert "summary" in data


def test_list_orgs_returns_seeded(client, auth_headers, db):
    """GET /tracker/organizations returns seeded orgs."""
    seed_organization(db, name="Org Alpha")
    seed_organization(db, name="Org Beta")
    resp = client.get("/tracker/organizations", headers=auth_headers)
    assert resp.json()["total"] == 2


def test_list_orgs_search(client, auth_headers, db):
    """Search filters by name."""
    seed_organization(db, name="Securities Exchange Commission", short_name="SEC")
    seed_organization(db, name="Treasury Department")
    resp = client.get("/tracker/organizations?search=SEC", headers=auth_headers)
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["short_name"] == "SEC"


def test_list_orgs_filter_type(client, auth_headers, db):
    """Filter by organization_type."""
    seed_organization(db, name="CFTC OGC", organization_type="CFTC office")
    seed_organization(db, name="CME Group", organization_type="Exchange")
    resp = client.get("/tracker/organizations?organization_type=Exchange", headers=auth_headers)
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["name"] == "CME Group"


def test_list_orgs_pagination(client, auth_headers, db):
    """Pagination with limit and offset."""
    for i in range(5):
        seed_organization(db, name=f"Org {i}")
    resp = client.get("/tracker/organizations?limit=2&offset=0", headers=auth_headers)
    data = resp.json()
    assert data["total"] == 5
    assert len(data["items"]) == 2


def test_list_orgs_summary(client, auth_headers, db):
    """Summary counts by category."""
    seed_organization(db, name="OGC", organization_type="CFTC office")
    seed_organization(db, name="CME", organization_type="Exchange")
    resp = client.get("/tracker/organizations", headers=auth_headers)
    summary = resp.json()["summary"]
    assert summary["total_active"] == 2
    assert summary["cftc_internal"] == 1
    assert summary["external"] == 1


# ---------------------------------------------------------------------------
# Get single organization
# ---------------------------------------------------------------------------

def test_get_org_success(client, auth_headers, db):
    """GET /tracker/organizations/{id} returns full detail with sub-resources."""
    org = seed_organization(db)
    resp = client.get(f"/tracker/organizations/{org['id']}", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == org["id"]
    assert "people" in data
    assert "matters" in data
    assert "children" in data
    assert "meetings" in data
    assert "ETag" in resp.headers


def test_get_org_not_found(client, auth_headers):
    """GET /tracker/organizations/{id} returns 404 for missing org."""
    resp = client.get(f"/tracker/organizations/{make_id()}", headers=auth_headers)
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Create organization
# ---------------------------------------------------------------------------

def test_create_org_success(client, auth_headers):
    """POST /tracker/organizations creates a new org."""
    resp = client.post("/tracker/organizations",
                       json={"name": "New Agency"},
                       headers=auth_headers)
    assert resp.status_code == 200
    assert "id" in resp.json()


def test_create_org_missing_name(client, auth_headers):
    """POST /tracker/organizations returns 422 when name is missing."""
    resp = client.post("/tracker/organizations", json={}, headers=auth_headers)
    assert resp.status_code == 422


def test_create_org_idempotency(client, auth_headers):
    """Same idempotency key returns cached result."""
    idem_key = str(uuid.uuid4())
    payload = {"name": "Idem Org"}
    headers = {**auth_headers, "idempotency-key": idem_key}
    resp1 = client.post("/tracker/organizations", json=payload, headers=headers)
    resp2 = client.post("/tracker/organizations", json=payload, headers=headers)
    assert resp1.json()["id"] == resp2.json()["id"]


# ---------------------------------------------------------------------------
# Update organization
# ---------------------------------------------------------------------------

def test_update_org_success(client, auth_headers, db):
    """PUT /tracker/organizations/{id} updates the org."""
    org = seed_organization(db)
    resp = client.put(f"/tracker/organizations/{org['id']}",
                      json={"short_name": "NEW"},
                      headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["updated"] is True


def test_update_org_not_found(client, auth_headers):
    """PUT /tracker/organizations/{id} returns 404 for missing org."""
    resp = client.put(f"/tracker/organizations/{make_id()}",
                      json={"name": "X"}, headers=auth_headers)
    assert resp.status_code == 404


def test_update_org_empty_body(client, auth_headers, db):
    """PUT /tracker/organizations/{id} with no fields returns 400."""
    org = seed_organization(db)
    resp = client.put(f"/tracker/organizations/{org['id']}",
                      json={}, headers=auth_headers)
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Delete (soft-deactivate) organization
# ---------------------------------------------------------------------------

def test_delete_org_success(client, auth_headers, db):
    """DELETE /tracker/organizations/{id} soft-deletes by setting is_active=0."""
    org = seed_organization(db)
    resp = client.delete(f"/tracker/organizations/{org['id']}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["deleted"] is True
    row = db.execute("SELECT is_active FROM organizations WHERE id = ?",
                     (org["id"],)).fetchone()
    assert row["is_active"] == 0


def test_delete_org_not_found(client, auth_headers):
    """DELETE /tracker/organizations/{id} returns 404 for missing org."""
    resp = client.delete(f"/tracker/organizations/{make_id()}", headers=auth_headers)
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Auth required
# ---------------------------------------------------------------------------

def test_orgs_auth_required(client):
    """Organization endpoints reject unauthenticated requests."""
    resp = client.get("/tracker/organizations")
    assert resp.status_code == 401
