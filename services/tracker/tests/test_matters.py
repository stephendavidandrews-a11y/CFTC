"""Comprehensive tests for the matters router."""

import uuid
from tests.conftest import (
    seed_matter,
    seed_person,
    seed_organization,
    make_id,
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
    resp = client.get(
        "/tracker/matters?limit=2&offset=0&sort_by=title&sort_dir=asc",
        headers=auth_headers,
    )
    data = resp.json()
    assert data["total"] == 5
    assert len(data["items"]) == 2


def test_list_matters_sort_asc(client, auth_headers, db):
    """Sort by title ascending."""
    seed_matter(db, title="Zeta Matter")
    seed_matter(db, title="Alpha Matter")
    resp = client.get(
        "/tracker/matters?sort_by=title&sort_dir=asc", headers=auth_headers
    )
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
        "status": "active",
        "priority": "important this month",
        "sensitivity": "routine",
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
        "status": "active",
        "priority": "important this month",
        "sensitivity": "routine",
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
    resp = client.put(
        f"/tracker/matters/{m['id']}",
        json={"title": "Updated Title"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["updated"] is True


def test_update_matter_not_found(client, auth_headers):
    """PUT /tracker/matters/{id} returns 404 for missing matter."""
    resp = client.put(
        f"/tracker/matters/{make_id()}", json={"title": "X"}, headers=auth_headers
    )
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
    resp = client.post(
        f"/tracker/matters/{m['id']}/people",
        json={"person_id": p["id"], "matter_role": "lead attorney"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    mp_id = resp.json()["id"]

    resp2 = client.get(f"/tracker/matters/{m['id']}/people", headers=auth_headers)
    assert resp2.status_code == 200
    items = resp2.json()
    assert len(items) == 1
    assert items[0]["person_id"] == p["id"]

    # Remove
    resp3 = client.delete(
        f"/tracker/matters/{m['id']}/people/{mp_id}", headers=auth_headers
    )
    assert resp3.status_code == 200
    assert resp3.json()["deleted"] is True


# ---------------------------------------------------------------------------
# Organizations (matter_organizations)
# ---------------------------------------------------------------------------


def test_add_and_list_matter_org(client, auth_headers, db):
    """POST + GET /tracker/matters/{id}/orgs manages linked orgs."""
    m = seed_matter(db)
    org = seed_organization(db)
    resp = client.post(
        f"/tracker/matters/{m['id']}/orgs",
        json={"organization_id": org["id"], "organization_role": "client office"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    mo_id = resp.json()["id"]

    resp2 = client.get(f"/tracker/matters/{m['id']}/orgs", headers=auth_headers)
    assert len(resp2.json()) == 1

    resp3 = client.delete(
        f"/tracker/matters/{m['id']}/orgs/{mo_id}", headers=auth_headers
    )
    assert resp3.json()["deleted"] is True


# ---------------------------------------------------------------------------
# Updates (matter_updates)
# ---------------------------------------------------------------------------


def test_add_and_list_matter_update(client, auth_headers, db):
    """POST + GET /tracker/matters/{id}/updates manages update history."""
    m = seed_matter(db)
    resp = client.post(
        f"/tracker/matters/{m['id']}/updates",
        json={"summary": "Completed initial review", "update_type": "status update"},
        headers=auth_headers,
    )
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
    db.execute(
        "INSERT INTO tags (id, name, tag_type) VALUES (?, ?, ?)",
        (tag_id, "urgent", "priority"),
    )
    db.commit()

    resp = client.post(
        f"/tracker/matters/{m['id']}/tags",
        json={"tag_id": tag_id},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["added"] is True

    # Duplicate add returns exists
    resp2 = client.post(
        f"/tracker/matters/{m['id']}/tags",
        json={"tag_id": tag_id},
        headers=auth_headers,
    )
    assert resp2.json()["exists"] is True

    resp3 = client.get(f"/tracker/matters/{m['id']}/tags", headers=auth_headers)
    assert len(resp3.json()) == 1

    resp4 = client.delete(
        f"/tracker/matters/{m['id']}/tags/{tag_id}", headers=auth_headers
    )
    assert resp4.json()["deleted"] is True


def test_add_tag_missing_tag_id(client, auth_headers, db):
    """POST /tracker/matters/{id}/tags without tag_id returns 400."""
    m = seed_matter(db)
    resp = client.post(
        f"/tracker/matters/{m['id']}/tags", json={}, headers=auth_headers
    )
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Dependencies (matter_dependencies)
# ---------------------------------------------------------------------------


def test_add_and_remove_dependency(client, auth_headers, db):
    """POST + DELETE /tracker/matters/{id}/dependencies manages deps."""
    m1 = seed_matter(db, title="Upstream")
    m2 = seed_matter(db, title="Downstream")
    resp = client.post(
        f"/tracker/matters/{m2['id']}/dependencies",
        json={"depends_on_matter_id": m1["id"]},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    dep_id = resp.json()["id"]

    resp2 = client.delete(
        f"/tracker/matters/{m2['id']}/dependencies/{dep_id}", headers=auth_headers
    )
    assert resp2.json()["deleted"] is True


def test_add_dependency_missing_field(client, auth_headers, db):
    """POST /tracker/matters/{id}/dependencies without depends_on returns 400."""
    m = seed_matter(db)
    resp = client.post(
        f"/tracker/matters/{m['id']}/dependencies", json={}, headers=auth_headers
    )
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Auth required
# ---------------------------------------------------------------------------


def test_matters_auth_required(client):
    """All matter endpoints reject unauthenticated requests."""
    resp = client.get("/tracker/matters")
    assert resp.status_code == 401
"""
Regression tests for matter extension CRUD, type validation, and data integrity.
Appended to tests/test_matters.py to catch bugs B1-B6 and F1-F3.
"""


# ---------------------------------------------------------------------------
# Extension CRUD -- Rulemaking
# ---------------------------------------------------------------------------


def test_create_rulemaking_matter_with_extension(client, auth_headers, db):
    """POST with rulemaking extension creates both rows."""
    payload = {
        "title": "Test Rulemaking Ext",
        "matter_type": "rulemaking",
        "status": "active",
        "priority": "important this month",
        "sensitivity": "routine",
        "next_step": "Draft NPRM",
        "extension": {"rin": "1234-AB56", "regulatory_stage": "proposed rule"},
    }
    resp = client.post("/tracker/matters", json=payload, headers=auth_headers)
    assert resp.status_code == 200, f"Create failed: {resp.text}"
    matter_id = resp.json()["id"]
    detail = client.get(f"/tracker/matters/{matter_id}", headers=auth_headers)
    ext = detail.json()["extension"]
    assert ext is not None
    assert ext["rin"] == "1234-AB56"
    assert ext["regulatory_stage"] == "proposed rule"


# ---------------------------------------------------------------------------
# Extension CRUD -- Enforcement
# ---------------------------------------------------------------------------


def test_create_enforcement_matter_with_extension(client, auth_headers, db):
    """POST with enforcement extension creates both rows."""
    payload = {
        "title": "Test Enforcement Ext",
        "matter_type": "enforcement",
        "status": "active",
        "priority": "important this month",
        "sensitivity": "routine",
        "next_step": "Gather evidence",
        "extension": {"enforcement_reference": "ENF-2026-001", "is_confidential": 1},
    }
    resp = client.post("/tracker/matters", json=payload, headers=auth_headers)
    assert resp.status_code == 200, f"Create failed: {resp.text}"
    matter_id = resp.json()["id"]
    detail = client.get(f"/tracker/matters/{matter_id}", headers=auth_headers)
    ext = detail.json()["extension"]
    assert ext is not None
    assert ext["enforcement_reference"] == "ENF-2026-001"
    assert ext["is_confidential"] == 1


# ---------------------------------------------------------------------------
# Update extension -- INSERT branch (catches B1 update path)
# ---------------------------------------------------------------------------


def test_update_matter_adds_extension_to_existing(client, auth_headers, db):
    """PUT with extension data creates extension row when none exists."""
    from tests.conftest import seed_matter

    m = seed_matter(db, matter_type="guidance")
    resp = client.put(
        f"/tracker/matters/{m['id']}",
        json={"extension": {"instrument_type": "Advisory"}},
        headers=auth_headers,
    )
    assert resp.status_code == 200, f"Update failed: {resp.text}"
    detail = client.get(f"/tracker/matters/{m['id']}", headers=auth_headers)
    ext = detail.json()["extension"]
    assert ext is not None, "Extension row should have been created"
    assert ext["instrument_type"] == "Advisory"


def test_update_matter_modifies_existing_extension(client, auth_headers):
    """PUT with extension data updates existing extension row."""
    payload = {
        "title": "Modify Ext Test",
        "matter_type": "guidance",
        "status": "active",
        "priority": "important this month",
        "sensitivity": "routine",
        "next_step": "Review",
        "extension": {"instrument_type": "No-Action"},
    }
    resp = client.post("/tracker/matters", json=payload, headers=auth_headers)
    assert resp.status_code == 200
    matter_id = resp.json()["id"]

    resp2 = client.put(
        f"/tracker/matters/{matter_id}",
        json={"extension": {"instrument_type": "Advisory"}},
        headers=auth_headers,
    )
    assert resp2.status_code == 200
    detail = client.get(f"/tracker/matters/{matter_id}", headers=auth_headers)
    assert detail.json()["extension"]["instrument_type"] == "Advisory"


# ---------------------------------------------------------------------------
# Matter type change blocked (catches B2)
# ---------------------------------------------------------------------------


def test_update_matter_type_change_rejected(client, auth_headers, db):
    """PUT with different matter_type should be rejected."""
    from tests.conftest import seed_matter

    m = seed_matter(db, matter_type="rulemaking")
    resp = client.put(
        f"/tracker/matters/{m['id']}",
        json={"matter_type": "guidance"},
        headers=auth_headers,
    )
    assert resp.status_code == 400, (
        f"Expected 400 for type change, got {resp.status_code}: {resp.text}"
    )


# ---------------------------------------------------------------------------
# List matters includes extension columns (catches B4)
# ---------------------------------------------------------------------------


def test_list_guidance_matters_includes_extension_fields(client, auth_headers):
    """GET /tracker/matters returns guidance extension fields in list."""
    payload = {
        "title": "Guidance List Test",
        "matter_type": "guidance",
        "status": "active",
        "priority": "important this month",
        "sensitivity": "routine",
        "next_step": "Review",
        "extension": {"instrument_type": "No-Action", "cftc_letter_number": "26-99"},
    }
    resp = client.post("/tracker/matters", json=payload, headers=auth_headers)
    assert resp.status_code == 200

    list_resp = client.get(
        "/tracker/matters?matter_type=guidance", headers=auth_headers
    )
    assert list_resp.status_code == 200
    items = list_resp.json()["items"]
    assert len(items) >= 1
    item = items[0]
    assert "instrument_type" in item, (
        f"Missing instrument_type in list response. Keys: {list(item.keys())}"
    )
    assert item["instrument_type"] == "No-Action"


def test_list_enforcement_matters_includes_extension_fields(client, auth_headers):
    """GET /tracker/matters returns enforcement extension fields in list."""
    payload = {
        "title": "Enforcement List Test",
        "matter_type": "enforcement",
        "status": "active",
        "priority": "important this month",
        "sensitivity": "routine",
        "next_step": "Investigate",
        "extension": {
            "enforcement_reference": "ENF-LIST-001",
            "litigation_stage": "investigation",
        },
    }
    resp = client.post("/tracker/matters", json=payload, headers=auth_headers)
    assert resp.status_code == 200

    list_resp = client.get(
        "/tracker/matters?matter_type=enforcement", headers=auth_headers
    )
    items = list_resp.json()["items"]
    assert len(items) >= 1
    item = items[0]
    assert "enforcement_reference" in item, (
        f"Missing enforcement_reference. Keys: {list(item.keys())}"
    )


# ---------------------------------------------------------------------------
# Sensitivity filter uses hyphens (catches F1)
# ---------------------------------------------------------------------------


def test_sensitivity_uses_hyphens_not_underscores(client, auth_headers, db):
    """The leadership-sensitive value uses hyphens, not underscores."""
    from tests.conftest import seed_matter

    seed_matter(db, title="Sensitive Matter", sensitivity="leadership-sensitive")
    seed_matter(db, title="Normal Matter", sensitivity="routine")

    all_resp = client.get("/tracker/matters", headers=auth_headers)
    items = all_resp.json()["items"]
    sensitive = [i for i in items if i["sensitivity"] == "leadership-sensitive"]
    assert len(sensitive) == 1
    assert sensitive[0]["title"] == "Sensitive Matter"
    wrong = [i for i in items if i["sensitivity"] == "leadership_sensitive"]
    assert len(wrong) == 0


# ---------------------------------------------------------------------------
# All valid matter types accepted (catches F3: missing policy type)
# ---------------------------------------------------------------------------


def test_create_matter_all_valid_types_accepted(client, auth_headers):
    """All canonical matter types should be accepted."""
    for mt in [
        "rulemaking", "guidance", "enforcement", "congressional", "policy", "other",
    ]:
        payload = {
            "title": f"Type Test {mt}",
            "matter_type": mt,
            "status": "active",
            "priority": "important this month",
            "sensitivity": "routine",
            "next_step": "Next",
        }
        resp = client.post("/tracker/matters", json=payload, headers=auth_headers)
        assert resp.status_code == 200, f"Failed for matter_type={mt}: {resp.text}"


def test_create_matter_invalid_type_rejected(client, auth_headers):
    """Invalid matter_type should be rejected with 422."""
    payload = {
        "title": "Bad Type",
        "matter_type": "nonexistent_type",
        "status": "active",
        "priority": "important this month",
        "sensitivity": "routine",
        "next_step": "Next",
    }
    resp = client.post("/tracker/matters", json=payload, headers=auth_headers)
    assert resp.status_code == 422, f"Expected 422, got {resp.status_code}"


# ---------------------------------------------------------------------------
# Cascade delete (catches orphaned extension rows)
# ---------------------------------------------------------------------------


def test_delete_matter_cascades_extension(client, auth_headers, db):
    """Hard-deleting a matter cascades to extension tables."""
    payload = {
        "title": "Cascade Test",
        "matter_type": "guidance",
        "status": "active",
        "priority": "important this month",
        "sensitivity": "routine",
        "next_step": "Review",
        "extension": {"instrument_type": "Advisory"},
    }
    resp = client.post("/tracker/matters", json=payload, headers=auth_headers)
    assert resp.status_code == 200
    matter_id = resp.json()["id"]

    row = db.execute(
        "SELECT * FROM matter_guidance WHERE matter_id = ?", (matter_id,)
    ).fetchone()
    assert row is not None

    db.execute("DELETE FROM matters WHERE id = ?", (matter_id,))
    db.commit()

    row = db.execute(
        "SELECT * FROM matter_guidance WHERE matter_id = ?", (matter_id,)
    ).fetchone()
    assert row is None, "Extension row should be cascaded on delete"


# ---------------------------------------------------------------------------
# Matter number uniqueness (catches stale sequence)
# ---------------------------------------------------------------------------


def test_create_multiple_matters_unique_numbers(client, auth_headers):
    """Creating multiple matters produces unique matter numbers."""
    numbers = []
    for i in range(5):
        payload = {
            "title": f"Seq Test {i}",
            "matter_type": "other",
            "status": "active",
            "priority": "monitoring only",
            "sensitivity": "routine",
            "next_step": "Next",
        }
        resp = client.post("/tracker/matters", json=payload, headers=auth_headers)
        assert resp.status_code == 200
        numbers.append(resp.json()["matter_number"])
    assert len(set(numbers)) == 5, f"Duplicate matter numbers: {numbers}"


# ---------------------------------------------------------------------------
# Empty-string FK fields (catches FK constraint from browser payloads)
# ---------------------------------------------------------------------------


def test_create_guidance_with_empty_string_fk_fields(client, auth_headers, db):
    """Frontend sends empty strings for unfilled FK fields -- must not fail FK check."""
    payload = {
        "title": "Empty String FK Test",
        "matter_type": "guidance",
        "status": "active",
        "priority": "important this month",
        "sensitivity": "routine",
        "next_step": "Review",
        "extension": {
            "instrument_type": "No-Action",
            "workflow_status": "request_received",
            "published_in_fr": 0,
            "cftc_letter_number": "",
            "requestor_name": "",
            "requestor_organization_id": "",
            "issuing_office_id": "",
            "signatory_person_id": "",
            "staff_contact_person_id": "",
            "amends_matter_id": "",
            "prior_letter_number": "",
        },
    }
    resp = client.post("/tracker/matters", json=payload, headers=auth_headers)
    assert resp.status_code == 200, f"FK failure with empty strings: {resp.text}"
    matter_id = resp.json()["id"]

    detail = client.get(f"/tracker/matters/{matter_id}", headers=auth_headers)
    ext = detail.json()["extension"]
    assert ext is not None
    assert ext["instrument_type"] == "No-Action"
    # Empty strings should be stored as NULL
    assert ext["requestor_organization_id"] is None
    assert ext["issuing_office_id"] is None
    assert ext["signatory_person_id"] is None
