"""Tests for policy_directives and directive_matters endpoints."""

from tests.conftest import seed_matter


def test_create_policy_directive(client, auth_headers, db):
    """POST /tracker/policy-directives creates a directive."""
    payload = {
        "source_document": "PWG Digital Asset Markets Report (July 2025)",
        "source_document_type": "pwg_report",
        "directive_label": "DCM Guidance — Leveraged Spot Retail",
        "priority_tier": "immediate_action",
        "responsible_entity": "cftc",
        "ogc_role": "drafter",
        "implementation_status": "not_started",
    }
    resp = client.post("/tracker/policy-directives", json=payload, headers=auth_headers)
    assert resp.status_code == 200
    assert "id" in resp.json()


def test_list_policy_directives_with_filters(client, auth_headers, db):
    """GET /tracker/policy-directives filters work."""
    for i, status in enumerate(["not_started", "in_progress", "implemented"]):
        client.post(
            "/tracker/policy-directives",
            json={
                "source_document": "Test Doc",
                "source_document_type": "executive_order",
                "directive_label": f"Directive {i}",
                "implementation_status": status,
            },
            headers=auth_headers,
        )

    # Filter by status
    resp = client.get(
        "/tracker/policy-directives",
        params={"implementation_status": "not_started"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["total"] == 1


def test_update_policy_directive(client, auth_headers, db):
    """PUT /tracker/policy-directives/{id} updates a directive."""
    resp = client.post(
        "/tracker/policy-directives",
        json={
            "source_document": "Test",
            "source_document_type": "executive_order",
            "directive_label": "Update Test",
        },
        headers=auth_headers,
    )
    did = resp.json()["id"]

    resp = client.put(
        f"/tracker/policy-directives/{did}",
        json={
            "implementation_status": "scoping",
            "implementation_notes": "Started scoping phase",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["updated"] is True


def test_get_directive_with_linked_matters(client, auth_headers, db):
    """GET /tracker/policy-directives/{id} includes linked matters."""
    matter = seed_matter(db)
    resp = client.post(
        "/tracker/policy-directives",
        json={
            "source_document": "Test",
            "source_document_type": "pwg_report",
            "directive_label": "Link Test",
        },
        headers=auth_headers,
    )
    did = resp.json()["id"]

    # Link matter
    client.post(
        "/tracker/directive-matters",
        json={
            "directive_id": did,
            "matter_id": matter["id"],
            "relationship_type": "implements",
        },
        headers=auth_headers,
    )

    # Get directive
    resp = client.get(f"/tracker/policy-directives/{did}", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["linked_matters"]) == 1
    assert data["linked_matters"][0]["matter_id"] == matter["id"]


def test_delete_directive_cascades_links(client, auth_headers, db):
    """DELETE /tracker/policy-directives/{id} removes links too."""
    matter = seed_matter(db)
    resp = client.post(
        "/tracker/policy-directives",
        json={
            "source_document": "Delete Test",
            "source_document_type": "gao_recommendation",
            "directive_label": "To Delete",
        },
        headers=auth_headers,
    )
    did = resp.json()["id"]

    client.post(
        "/tracker/directive-matters",
        json={"directive_id": did, "matter_id": matter["id"]},
        headers=auth_headers,
    )

    resp = client.delete(f"/tracker/policy-directives/{did}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["links_deleted"] == 1


def test_link_directive_to_matter(client, auth_headers, db):
    """POST /tracker/directive-matters links directive to matter."""
    matter = seed_matter(db)
    resp = client.post(
        "/tracker/policy-directives",
        json={
            "source_document": "Test",
            "source_document_type": "executive_order",
            "directive_label": "Link Test 2",
        },
        headers=auth_headers,
    )
    did = resp.json()["id"]

    resp = client.post(
        "/tracker/directive-matters",
        json={
            "directive_id": did,
            "matter_id": matter["id"],
            "relationship_type": "implements",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert "id" in resp.json()


def test_duplicate_link_rejected(client, auth_headers, db):
    """Cannot link same directive-matter pair twice."""
    matter = seed_matter(db)
    resp = client.post(
        "/tracker/policy-directives",
        json={
            "source_document": "Test",
            "source_document_type": "executive_order",
            "directive_label": "Dup Test",
        },
        headers=auth_headers,
    )
    did = resp.json()["id"]

    payload = {"directive_id": did, "matter_id": matter["id"]}
    resp1 = client.post(
        "/tracker/directive-matters", json=payload, headers=auth_headers
    )
    assert resp1.status_code == 200

    resp2 = client.post(
        "/tracker/directive-matters", json=payload, headers=auth_headers
    )
    assert resp2.status_code == 409


def test_unlink_directive_from_matter(client, auth_headers, db):
    """DELETE /tracker/directive-matters/{id} unlinks."""
    matter = seed_matter(db)
    resp = client.post(
        "/tracker/policy-directives",
        json={
            "source_document": "Test",
            "source_document_type": "executive_order",
            "directive_label": "Unlink Test",
        },
        headers=auth_headers,
    )
    did = resp.json()["id"]

    link = client.post(
        "/tracker/directive-matters",
        json={"directive_id": did, "matter_id": matter["id"]},
        headers=auth_headers,
    )
    lid = link.json()["id"]

    resp = client.delete(f"/tracker/directive-matters/{lid}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["deleted"] is True


def test_reverse_lookup_matter_directives(client, auth_headers, db):
    """GET /tracker/matters/{id}/directives returns linked directives."""
    matter = seed_matter(db)
    resp = client.post(
        "/tracker/policy-directives",
        json={
            "source_document": "Test",
            "source_document_type": "pwg_report",
            "directive_label": "Reverse Lookup",
        },
        headers=auth_headers,
    )
    did = resp.json()["id"]

    client.post(
        "/tracker/directive-matters",
        json={"directive_id": did, "matter_id": matter["id"]},
        headers=auth_headers,
    )

    resp = client.get(
        f"/tracker/matters/{matter['id']}/directives", headers=auth_headers
    )
    assert resp.status_code == 200
    assert resp.json()["total"] == 1
    assert resp.json()["items"][0]["directive_label"] == "Reverse Lookup"


def test_enum_validation_on_directive(client, auth_headers, db):
    """Invalid enum values are rejected."""
    payload = {
        "source_document": "Test",
        "source_document_type": "invalid_type",
        "directive_label": "Bad Enum",
    }
    resp = client.post("/tracker/policy-directives", json=payload, headers=auth_headers)
    assert resp.status_code == 422
