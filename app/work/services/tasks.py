"""
Business logic for personal tasks.
"""

import sqlite3
import json
from datetime import datetime


def _enrich_task(row: sqlite3.Row, conn: sqlite3.Connection) -> dict:
    """Enrich a task with resolved names."""
    d = dict(row)
    # Parse tags from JSON string
    try:
        d["tags"] = json.loads(d.get("tags") or "[]")
    except (json.JSONDecodeError, TypeError):
        d["tags"] = []

    # Resolve project title
    if d.get("project_id"):
        proj = conn.execute("SELECT title FROM projects WHERE id = ?", (d["project_id"],)).fetchone()
        d["project_title"] = proj["title"] if proj else None
    else:
        d["project_title"] = None

    # Resolve member name
    if d.get("linked_member_id"):
        try:
            member = conn.execute(
                "SELECT name FROM pipeline.team_members WHERE id = ?",
                (d["linked_member_id"],)
            ).fetchone()
            d["member_name"] = member["name"] if member else None
        except Exception:
            d["member_name"] = None
    else:
        d["member_name"] = None

    d["children"] = []
    return d


def _build_task_tree(flat: list[dict]) -> list[dict]:
    """Build a nested tree from flat task list using parent_id."""
    by_id = {t["id"]: t for t in flat}
    roots = []
    for t in flat:
        pid = t.get("parent_id")
        if pid and pid in by_id:
            by_id[pid]["children"].append(t)
        else:
            roots.append(t)
    return roots


def list_tasks(conn: sqlite3.Connection, **filters) -> list[dict]:
    """List tasks with optional filters."""
    sql = "SELECT * FROM tasks WHERE 1=1"
    params = []

    if filters.get("status"):
        sql += " AND status = ?"
        params.append(filters["status"])
    if filters.get("priority_label"):
        sql += " AND priority_label = ?"
        params.append(filters["priority_label"])
    if filters.get("project_id"):
        sql += " AND project_id = ?"
        params.append(int(filters["project_id"]))
    if filters.get("work_item_id"):
        sql += " AND work_item_id = ?"
        params.append(int(filters["work_item_id"]))
    if filters.get("linked_member_id"):
        sql += " AND linked_member_id = ?"
        params.append(int(filters["linked_member_id"]))
    if filters.get("due_before"):
        sql += " AND due_date <= ?"
        params.append(filters["due_before"])
    if filters.get("due_after"):
        sql += " AND due_date >= ?"
        params.append(filters["due_after"])
    if filters.get("tags"):
        # Search within JSON tags
        sql += " AND tags LIKE ?"
        params.append(f"%{filters['tags']}%")

    sql += " ORDER BY CASE status WHEN 'in_progress' THEN 0 WHEN 'todo' THEN 1 WHEN 'deferred' THEN 2 WHEN 'done' THEN 3 END, due_date ASC NULLS LAST"

    rows = conn.execute(sql, params).fetchall()
    flat = [_enrich_task(r, conn) for r in rows]

    # If filtering by work_item_id, return nested tree
    if filters.get("work_item_id"):
        return _build_task_tree(flat)
    return flat


def list_tasks_for_work_item(conn: sqlite3.Connection, work_item_id: int) -> list[dict]:
    """Get all tasks for a work item as a nested tree."""
    rows = conn.execute(
        "SELECT * FROM tasks WHERE work_item_id = ? "
        "ORDER BY CASE status WHEN 'in_progress' THEN 0 WHEN 'todo' THEN 1 WHEN 'deferred' THEN 2 WHEN 'done' THEN 3 END, created_at",
        (work_item_id,)
    ).fetchall()
    flat = [_enrich_task(r, conn) for r in rows]
    return _build_task_tree(flat)


def create_task(conn: sqlite3.Connection, data: dict) -> dict:
    """Create a task."""
    if "tags" in data and isinstance(data["tags"], list):
        data["tags"] = json.dumps(data["tags"])

    cols = [k for k in data if data[k] is not None]
    placeholders = ", ".join(["?"] * len(cols))
    col_names = ", ".join(cols)
    vals = [data[k] for k in cols]

    cur = conn.execute(f"INSERT INTO tasks ({col_names}) VALUES ({placeholders})", vals)
    conn.commit()
    return get_task(conn, cur.lastrowid)


def get_task(conn: sqlite3.Connection, task_id: int) -> dict | None:
    """Get a single task."""
    row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if not row:
        return None
    return _enrich_task(row, conn)


def update_task(conn: sqlite3.Connection, task_id: int, data: dict) -> dict | None:
    """Update task fields."""
    updates = {k: v for k, v in data.items() if v is not None}
    if not updates:
        return get_task(conn, task_id)

    if "tags" in updates and isinstance(updates["tags"], list):
        updates["tags"] = json.dumps(updates["tags"])

    updates["updated_at"] = datetime.utcnow().isoformat()

    if updates.get("status") == "done":
        updates["completed_at"] = datetime.utcnow().isoformat()
    elif updates.get("status") and updates["status"] != "done":
        updates["completed_at"] = None

    set_clause = ", ".join(f"{k} = ?" for k in updates)
    vals = list(updates.values()) + [task_id]
    conn.execute(f"UPDATE tasks SET {set_clause} WHERE id = ?", vals)
    conn.commit()
    return get_task(conn, task_id)


def delete_task(conn: sqlite3.Connection, task_id: int) -> bool:
    """Delete a task."""
    conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    conn.commit()
    return True
