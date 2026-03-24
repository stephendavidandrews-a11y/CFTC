"""Comprehensive tests for the tasks router."""
import uuid
from tests.conftest import (
    seed_matter, seed_person, seed_task, make_id,
)


# ---------------------------------------------------------------------------
# List / filter / sort / paginate
# ---------------------------------------------------------------------------

def test_list_tasks_empty(client, auth_headers):
    """GET /tracker/tasks returns empty list when no tasks exist."""
    resp = client.get("/tracker/tasks", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["items"] == []
    assert data["total"] == 0
    assert "summary" in data


def test_list_tasks_returns_seeded(client, auth_headers, db):
    """GET /tracker/tasks returns seeded tasks."""
    m = seed_matter(db)
    seed_task(db, m["id"], title="Task Alpha")
    seed_task(db, m["id"], title="Task Beta")
    resp = client.get("/tracker/tasks", headers=auth_headers)
    assert resp.json()["total"] == 2


def test_list_tasks_filter_status(client, auth_headers, db):
    """Filter by status."""
    m = seed_matter(db)
    seed_task(db, m["id"], title="Open", status="open")
    seed_task(db, m["id"], title="Done", status="done")
    resp = client.get("/tracker/tasks?status=open", headers=auth_headers)
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["title"] == "Open"


def test_list_tasks_filter_matter(client, auth_headers, db):
    """Filter by matter_id."""
    m1 = seed_matter(db, title="Matter A")
    m2 = seed_matter(db, title="Matter B")
    seed_task(db, m1["id"], title="Task for A")
    seed_task(db, m2["id"], title="Task for B")
    resp = client.get(f"/tracker/tasks?matter_id={m1['id']}", headers=auth_headers)
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["title"] == "Task for A"


def test_list_tasks_exclude_done(client, auth_headers, db):
    """exclude_done filters out done/completed/deferred tasks."""
    m = seed_matter(db)
    seed_task(db, m["id"], title="Active", status="open")
    seed_task(db, m["id"], title="Finished", status="done")
    seed_task(db, m["id"], title="Deferred", status="deferred")
    resp = client.get("/tracker/tasks?exclude_done=true", headers=auth_headers)
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["title"] == "Active"


def test_list_tasks_search(client, auth_headers, db):
    """Search filters by title."""
    m = seed_matter(db)
    seed_task(db, m["id"], title="Draft memo for Commissioner")
    seed_task(db, m["id"], title="Review budget proposal")
    resp = client.get("/tracker/tasks?search=Commissioner", headers=auth_headers)
    data = resp.json()
    assert data["total"] == 1


def test_list_tasks_filter_mode(client, auth_headers, db):
    """Filter by task_mode."""
    m = seed_matter(db)
    seed_task(db, m["id"], title="Do it", task_mode="action")
    seed_task(db, m["id"], title="Track it", task_mode="follow_up")
    resp = client.get("/tracker/tasks?mode=follow_up", headers=auth_headers)
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["title"] == "Track it"


def test_list_tasks_pagination(client, auth_headers, db):
    """Pagination with limit and offset."""
    m = seed_matter(db)
    for i in range(5):
        seed_task(db, m["id"], title=f"Task {i}")
    resp = client.get("/tracker/tasks?limit=2&offset=0", headers=auth_headers)
    data = resp.json()
    assert data["total"] == 5
    assert len(data["items"]) == 2


# ---------------------------------------------------------------------------
# Get single task
# ---------------------------------------------------------------------------

def test_get_task_success(client, auth_headers, db):
    """GET /tracker/tasks/{id} returns full detail."""
    m = seed_matter(db)
    t = seed_task(db, m["id"])
    resp = client.get(f"/tracker/tasks/{t['id']}", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == t["id"]
    assert "tracked_by_tasks" in data
    assert "ETag" in resp.headers


def test_get_task_not_found(client, auth_headers):
    """GET /tracker/tasks/{id} returns 404 for missing task."""
    resp = client.get(f"/tracker/tasks/{make_id()}", headers=auth_headers)
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Create task
# ---------------------------------------------------------------------------

def test_create_task_success(client, auth_headers, db):
    """POST /tracker/tasks creates a new task."""
    m = seed_matter(db)
    payload = {
        "title": "New Task",
        "matter_id": m["id"],
        "status": "not started",
        "task_mode": "action",
    }
    resp = client.post("/tracker/tasks", json=payload, headers=auth_headers)
    assert resp.status_code == 200
    assert "id" in resp.json()


def test_create_task_missing_title(client, auth_headers, db):
    """POST /tracker/tasks returns 422 when title is missing."""
    m = seed_matter(db)
    resp = client.post("/tracker/tasks",
                       json={"matter_id": m["id"], "status": "not started", "task_mode": "action"},
                       headers=auth_headers)
    assert resp.status_code == 422


def test_create_task_invalid_mode(client, auth_headers, db):
    """POST /tracker/tasks returns 422 for invalid task_mode literal."""
    m = seed_matter(db)
    resp = client.post("/tracker/tasks",
                       json={"title": "Bad", "matter_id": m["id"],
                             "status": "not started", "task_mode": "invalid_mode"},
                       headers=auth_headers)
    assert resp.status_code == 422


def test_create_task_idempotency(client, auth_headers, db):
    """Same idempotency key returns cached result."""
    m = seed_matter(db)
    idem_key = str(uuid.uuid4())
    payload = {"title": "Idem Task", "matter_id": m["id"],
               "status": "not started", "task_mode": "action"}
    headers = {**auth_headers, "idempotency-key": idem_key}
    resp1 = client.post("/tracker/tasks", json=payload, headers=headers)
    resp2 = client.post("/tracker/tasks", json=payload, headers=headers)
    assert resp1.json()["id"] == resp2.json()["id"]


# ---------------------------------------------------------------------------
# Update task
# ---------------------------------------------------------------------------

def test_update_task_success(client, auth_headers, db):
    """PUT /tracker/tasks/{id} updates the task."""
    m = seed_matter(db)
    t = seed_task(db, m["id"])
    resp = client.put(f"/tracker/tasks/{t['id']}",
                      json={"title": "Updated Task"},
                      headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["updated"] is True


def test_update_task_not_found(client, auth_headers):
    """PUT /tracker/tasks/{id} returns 404 for missing task."""
    resp = client.put(f"/tracker/tasks/{make_id()}",
                      json={"title": "X"}, headers=auth_headers)
    assert resp.status_code == 404


def test_update_task_empty_body(client, auth_headers, db):
    """PUT /tracker/tasks/{id} with no fields returns 400."""
    m = seed_matter(db)
    t = seed_task(db, m["id"])
    resp = client.put(f"/tracker/tasks/{t['id']}", json={}, headers=auth_headers)
    assert resp.status_code == 400


def test_update_task_completion_transitions_tracking(client, auth_headers, db):
    """Marking a task done transitions tracking follow_up tasks to needs review."""
    m = seed_matter(db)
    p = seed_person(db)
    # The tracked (delegated) task
    tracked = seed_task(db, m["id"], title="Delegated work", status="in progress",
                        assigned_to_person_id=p["id"])
    # The follow_up that tracks it
    tracker = seed_task(db, m["id"], title="Follow up on delegation",
                        status="waiting on others", task_mode="follow_up",
                        tracks_task_id=tracked["id"])

    # Complete the tracked task
    resp = client.put(f"/tracker/tasks/{tracked['id']}",
                      json={"status": "done"},
                      headers=auth_headers)
    assert resp.status_code == 200

    # Verify the tracker task transitioned
    row = db.execute("SELECT status FROM tasks WHERE id = ?", (tracker["id"],)).fetchone()
    assert row["status"] == "needs review"


# ---------------------------------------------------------------------------
# Delete task
# ---------------------------------------------------------------------------

def test_delete_task_success(client, auth_headers, db):
    """DELETE /tracker/tasks/{id} hard-deletes the task."""
    m = seed_matter(db)
    t = seed_task(db, m["id"])
    resp = client.delete(f"/tracker/tasks/{t['id']}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["deleted"] is True
    row = db.execute("SELECT id FROM tasks WHERE id = ?", (t["id"],)).fetchone()
    assert row is None


def test_delete_task_not_found(client, auth_headers):
    """DELETE /tracker/tasks/{id} returns 404 for missing task."""
    resp = client.delete(f"/tracker/tasks/{make_id()}", headers=auth_headers)
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Auth required
# ---------------------------------------------------------------------------

def test_tasks_auth_required(client):
    """Task endpoints reject unauthenticated requests."""
    resp = client.get("/tracker/tasks")
    assert resp.status_code == 401
