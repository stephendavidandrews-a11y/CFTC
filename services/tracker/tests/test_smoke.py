"""Smoke test: verify conftest fixtures work."""
from tests.conftest import seed_matter


def test_schema_creates_tables(db):
    """init_schema creates all expected tables."""
    tables = {
        row[0]
        for row in db.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    for expected in [
        "organizations", "people", "matters", "tasks", "meetings",
        "documents", "decisions", "system_events", "idempotency_keys",
        "context_notes", "context_note_links", "matter_people",
    ]:
        assert expected in tables, f"Missing table: {expected}"


def test_seed_matter(db):
    """seed_matter inserts a valid matter row."""
    m = seed_matter(db)
    row = db.execute("SELECT * FROM matters WHERE id = ?", (m["id"],)).fetchone()
    assert row is not None
    assert row["title"] == "Test Matter"


def test_health_endpoint(client, auth_headers):
    """Health check returns 200."""
    resp = client.get("/tracker/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_auth_required(client):
    """Endpoints reject unauthenticated requests."""
    resp = client.get("/tracker/matters")
    assert resp.status_code == 401
