"""Comprehensive tests for the matters router."""
import uuid
from tests.conftest import (
    seed_matter, seed_person, seed_organization, make_id,
)


# ---------------------------------------------------------------------------
# List / filter / sort / paginate
# ---------------------------------------------------------------------------

def test_list_matters_empty(client, auth_headers):
    """GET /tracker/matters returns empty list when no matters exist."""
    resp = client.get("/tracker/matters", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["items"] == []
    assert data["total"] == 0
    assert "summary" in data


def test_list_matters_returns_seeded(client, auth_headers, db):
    """GET /tracker/matters returns seeded matters."""
    m1 = seed_matter(db, title="Alpha Matter")
    m2 = seed_matter(db, title="Beta Matter")
    resp = client.get("/tracker/matters", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    titles = {item["title"] for item in data["items"]}
    assert titles == {"Alpha Matter", "Beta Matter"}


def test_list_matters_filter_status(client, auth_headers, db):
    """Filter by status returns only matching matters."""
    seed_matter(db, title="Active One", status="active")
    seed_matter(db, title="Closed One", status="closed")
    resp = client.get("/tracker/matters?status=active", headers=auth_headers)
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["title"] == "Active One"


def test_list_matters_filter_priority(client, auth_headers, db):
    """Filter by priority."""
    seed_matter(db, title="High", priority="high")
    seed_matter(db, title="Low", priority="low")
    resp = client.get("/tracker/matters?priority=high", headers=auth_headers)
    assert resp.json()["total"] == 1
    assert resp.json()["items"][0]["title"] == "High"


def test_list_matters_search(client, auth_headers, db):
    """Search matches on title."""
    seed_matter(db, title="Derivatives Reform")
    seed_matter(db, title="Budget Review")
    resp = client.get("/tracker/matters?search=Derivatives", headers=auth_headers)
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["title"] == "Derivatives Reform"


def test_list_matters_pagination(client, auth_headers, db):
    """Pagination with limit and offset."""
    for i in range(5):
        seed_matter(db, title=f"Matter {i}")
    resp = client.get("/tracker/matters?limit=2&offset=0&sort_by=title&sort_dir=asc",
                      headers=auth_headers)
    data = resp.json()
    assert data["total"] == 5
    assert len(data["items"]) == 2


def test_list_matters_sort_asc(client, auth_headers, db):
    """Sort by title ascending."""
    seed_matter(db, title="Zeta Matter")
    seed_matter(db, title="Alpha Matter")
    resp = client.get("/tracker/matters?sort_by=title&sort_dir=asc", headers=auth_headers)
    items = resp.json()["items"]
    assert items[0]["title"] == "Alpha Matter"
    assert items[1]["title"] == "Zeta Matter"


def test_list_matters_summary_counts(client, auth_headers, db):
    """Summary includes open_matters and critical_this_week."""
    seed_matter(db, status="active", priority="critical this week")
    seed_matter(db, status="closed", priority="low")
    resp = client.get("/tracker/matters", headers=auth_headers)
    summary = resp.json()["summary"]
    assert summary["open_matters"] == 1
    assert summary["critical_this_week"] == 1


# ---------------------------------------------------------------------------
# Get single matter
# ---------------------------------------------------------------------------

def test_get_matter_success(client, auth_headers, db):
    """GET /tracker/matters/{id} returns full detail with sub-resources."""
    m = seed_matter(db)
    resp = client.get(f"/tracker/matters/{m['id']}", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == m["id"]
    assert "stakeholders" in data
    assert "tasks" in data
    assert "tags" in data
    assert "dependencies" in data
    assert "ETag" in resp.headers


def test_get_matter_not_found(client, auth_headers):
    """GET /tracker/matters/{id} returns 404 for missing matter."""
    resp = client.get(f"/tracker/matters/{make_id()}", headers=auth_headers)
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Create matter
# ---------------------------------------------------------------------------

def test_create_matter_success(client, auth_headers):
    """POST /tracker/matters creates a new matter."""
    payload = {
        "title": "New Rulemaking",
        "matter_type": "rulemaking",
        "status": "new intake",
        "priority": "important this month",
        "sensitivity": "routine",
        "boss_involvement_level": "keep boss informed",
        "next_step": "Draft proposal",
    }
    resp = client.post("/tracker/matters", json=payload, headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "id" in data
    assert "matter_number" in data
    assert data["matter_number"].startswith("MAT-")


def test_create_matter_missing_required_field(client, auth_headers):
    """POST /tracker/matters returns 422 when title is missing."""
    payload = {"matter_type": "rulemaking"}
    resp = client.post("/tracker/matters", json=payload, headers=auth_headers)
    assert resp.status_code == 422


def test_create_matter_idempotency(client, auth_headers):
    """Same idempotency key + payload returns cached result."""
    idem_key = str(uuid.uuid4())
    payload = {
        "title": "Idem Test",
        "matter_type": "rulemaking",
        "status": "new intake",
        "priority": "important this month",
        "sensitivity": "routine",
        "boss_involvement_level": "keep boss informed",
        "next_step": "Next",
    }
    headers = {**auth_headers, "idempotency-key": idem_key}
    resp1 = client.post("/tracker/matters", json=payload, headers=headers)
    assert resp1.status_code == 200
    resp2 = client.post("/tracker/matters", json=payload, headers=headers)
    assert resp2.status_code == 200
    assert resp1.json()["id"] == resp2.json()["id"]


# ---------------------------------------------------------------------------
# Update matter
# ---------------------------------------------------------------------------

def test_update_matter_success(client, auth_headers, db):
    """PUT /tracker/matters/{id} updates the matter."""
    m = seed_matter(db)
    resp = client.put(f"/tracker/matters/{m['id']}",
                      json={"title": "Updated Title"}, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["updated"] is True


def test_update_matter_not_found(client, auth_headers):
    """PUT /tracker/matters/{id} returns 404 for missing matter."""
    resp = client.put(f"/tracker/matters/{make_id()}",
                      json={"title": "X"}, headers=auth_headers)
    assert resp.status_code == 404


def test_update_matter_empty_body(client, auth_headers, db):
    """PUT /tracker/matters/{id} with no fields returns 400."""
    m = seed_matter(db)
    resp = client.put(f"/tracker/matters/{m['id']}", json={}, headers=auth_headers)
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Delete (soft-close) matter
# ---------------------------------------------------------------------------

def test_delete_matter_success(client, auth_headers, db):
    """DELETE /tracker/matters/{id} soft-deletes by setting status=closed."""
    m = seed_matter(db)
    resp = client.delete(f"/tracker/matters/{m['id']}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["deleted"] is True
    row = db.execute("SELECT status FROM matters WHERE id = ?", (m["id"],)).fetchone()
    assert row["status"] == "closed"


def test_delete_matter_not_found(client, auth_headers):
    """DELETE /tracker/matters/{id} returns 404 for missing matter."""
    resp = client.delete(f"/tracker/matters/{make_id()}", headers=auth_headers)
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Stakeholders (matter_people)
# ---------------------------------------------------------------------------

def test_add_and_list_matter_person(client, auth_headers, db):
    """POST + GET /tracker/matters/{id}/people manages stakeholders."""
    m = seed_matter(db)
    p = seed_person(db)
    resp = client.post(f"/tracker/matters/{m['id']}/people",
                       json={"person_id": p["id"], "matter_role": "lead"},
                       headers=auth_headers)
    assert resp.status_code == 200
    mp_id = resp.json()["id"]

    resp2 = client.get(f"/tracker/matters/{m['id']}/people", headers=auth_headers)
    assert resp2.status_code == 200
    items = resp2.json()
    assert len(items) == 1
    assert items[0]["person_id"] == p["id"]

    # Remove
    resp3 = client.delete(f"/tracker/matters/{m['id']}/people/{mp_id}",
                          headers=auth_headers)
    assert resp3.status_code == 200
    assert resp3.json()["deleted"] is True


# ---------------------------------------------------------------------------
# Organizations (matter_organizations)
# ---------------------------------------------------------------------------

def test_add_and_list_matter_org(client, auth_headers, db):
    """POST + GET /tracker/matters/{id}/orgs manages linked orgs."""
    m = seed_matter(db)
    org = seed_organization(db)
    resp = client.post(f"/tracker/matters/{m['id']}/orgs",
                       json={"organization_id": org["id"], "organization_role": "client"},
                       headers=auth_headers)
    assert resp.status_code == 200
    mo_id = resp.json()["id"]

    resp2 = client.get(f"/tracker/matters/{m['id']}/orgs", headers=auth_headers)
    assert len(resp2.json()) == 1

    resp3 = client.delete(f"/tracker/matters/{m['id']}/orgs/{mo_id}",
                          headers=auth_headers)
    assert resp3.json()["deleted"] is True


# ---------------------------------------------------------------------------
# Updates (matter_updates)
# ---------------------------------------------------------------------------

def test_add_and_list_matter_update(client, auth_headers, db):
    """POST + GET /tracker/matters/{id}/updates manages update history."""
    m = seed_matter(db)
    resp = client.post(f"/tracker/matters/{m['id']}/updates",
                       json={"summary": "Completed initial review", "update_type": "status update"},
                       headers=auth_headers)
    assert resp.status_code == 200

    resp2 = client.get(f"/tracker/matters/{m['id']}/updates", headers=auth_headers)
    items = resp2.json()
    assert len(items) == 1
    assert items[0]["summary"] == "Completed initial review"


# ---------------------------------------------------------------------------
# Tags (matter_tags)
# ---------------------------------------------------------------------------

def test_add_and_list_matter_tag(client, auth_headers, db):
    """POST + GET + DELETE /tracker/matters/{id}/tags manages tags."""
    m = seed_matter(db)
    tag_id = make_id()
    db.execute("INSERT INTO tags (id, name, tag_type) VALUES (?, ?, ?)",
               (tag_id, "urgent", "priority"))
    db.commit()

    resp = client.post(f"/tracker/matters/{m['id']}/tags",
                       json={"tag_id": tag_id}, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["added"] is True

    # Duplicate add returns exists
    resp2 = client.post(f"/tracker/matters/{m['id']}/tags",
                        json={"tag_id": tag_id}, headers=auth_headers)
    assert resp2.json()["exists"] is True

    resp3 = client.get(f"/tracker/matters/{m['id']}/tags", headers=auth_headers)
    assert len(resp3.json()) == 1

    resp4 = client.delete(f"/tracker/matters/{m['id']}/tags/{tag_id}",
                          headers=auth_headers)
    assert resp4.json()["deleted"] is True


def test_add_tag_missing_tag_id(client, auth_headers, db):
    """POST /tracker/matters/{id}/tags without tag_id returns 400."""
    m = seed_matter(db)
    resp = client.post(f"/tracker/matters/{m['id']}/tags",
                       json={}, headers=auth_headers)
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Dependencies (matter_dependencies)
# ---------------------------------------------------------------------------

def test_add_and_remove_dependency(client, auth_headers, db):
    """POST + DELETE /tracker/matters/{id}/dependencies manages deps."""
    m1 = seed_matter(db, title="Upstream")
    m2 = seed_matter(db, title="Downstream")
    resp = client.post(f"/tracker/matters/{m2['id']}/dependencies",
                       json={"depends_on_matter_id": m1["id"]},
                       headers=auth_headers)
    assert resp.status_code == 200
    dep_id = resp.json()["id"]

    resp2 = client.delete(f"/tracker/matters/{m2['id']}/dependencies/{dep_id}",
                          headers=auth_headers)
    assert resp2.json()["deleted"] is True


def test_add_dependency_missing_field(client, auth_headers, db):
    """POST /tracker/matters/{id}/dependencies without depends_on returns 400."""
    m = seed_matter(db)
    resp = client.post(f"/tracker/matters/{m['id']}/dependencies",
                       json={}, headers=auth_headers)
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Auth required
# ---------------------------------------------------------------------------

def test_matters_auth_required(client):
    """All matter endpoints reject unauthenticated requests."""
    resp = client.get("/tracker/matters")
    assert resp.status_code == 401
