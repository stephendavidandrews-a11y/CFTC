"""Tests for dashboard endpoints — stats and summary data."""
from tests.conftest import (
    seed_matter, seed_task, seed_decision,
)


def test_dashboard_returns_structure(client, auth_headers):
    """GET /tracker/dashboard returns all expected top-level keys."""
    resp = client.get("/tracker/dashboard", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    expected_keys = {
        "total_open_matters", "total_open_tasks", "overdue_tasks",
        "matters_by_status", "matters_by_priority",
        "upcoming_deadlines", "recent_matters", "recent_updates",
        "tasks_due_soon", "pending_decisions",
    }
    assert expected_keys <= set(body.keys())


def test_dashboard_counts_open_matters(client, auth_headers, db):
    """Dashboard counts only open (non-closed) matters."""
    seed_matter(db, status="active")
    seed_matter(db, status="active")
    seed_matter(db, status="closed")
    resp = client.get("/tracker/dashboard", headers=auth_headers)
    assert resp.json()["total_open_matters"] == 2


def test_dashboard_counts_open_tasks(client, auth_headers, db):
    """Dashboard counts only open (non-done, non-deferred) tasks."""
    matter = seed_matter(db)
    seed_task(db, matter["id"], status="open")
    seed_task(db, matter["id"], status="in progress")
    seed_task(db, matter["id"], status="done")
    seed_task(db, matter["id"], status="deferred")
    resp = client.get("/tracker/dashboard", headers=auth_headers)
    assert resp.json()["total_open_tasks"] == 2


def test_dashboard_pending_decisions(client, auth_headers, db):
    """Dashboard lists pending decisions."""
    matter = seed_matter(db)
    seed_decision(db, matter["id"], status="pending", title="Pending Dec")
    seed_decision(db, matter["id"], status="made", title="Made Dec")
    resp = client.get("/tracker/dashboard", headers=auth_headers)
    pending = resp.json()["pending_decisions"]
    titles = [d["title"] for d in pending]
    assert "Pending Dec" in titles


def test_stats_returns_table_counts(client, auth_headers, db):
    """GET /tracker/dashboard/stats returns row counts for all tables."""
    seed_matter(db)
    resp = client.get("/tracker/dashboard/stats", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert "matters" in body
    assert body["matters"] >= 1
    # Should have all standard tables
    assert "organizations" in body
    assert "people" in body
    assert "tasks" in body
