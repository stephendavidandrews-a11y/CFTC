"""
Business logic for work items (tree operations).
"""

import sqlite3
from datetime import datetime

from app.work.services.progress import compute_progress, effective_deadline


def _resolve_assignees(conn: sqlite3.Connection, item_id: int) -> list[dict]:
    """Get assignees for a work item with resolved names."""
    rows = conn.execute(
        "SELECT wia.id, wia.team_member_id, wia.role "
        "FROM work_item_assignments wia WHERE wia.work_item_id = ?",
        (item_id,)
    ).fetchall()

    result = []
    for r in rows:
        name = ""
        try:
            member = conn.execute(
                "SELECT name FROM pipeline.team_members WHERE id = ?",
                (r["team_member_id"],)
            ).fetchone()
            if member:
                name = member["name"]
        except Exception:
            pass
        result.append({
            "id": r["id"],
            "team_member_id": r["team_member_id"],
            "name": name,
            "role": r["role"],
        })
    return result


def _enrich_item(row: sqlite3.Row, conn: sqlite3.Connection) -> dict:
    """Convert a work item row to enriched dict."""
    d = dict(row)
    d["assignees"] = _resolve_assignees(conn, d["id"])
    progress = compute_progress(d["id"], conn)
    d["progress_completed"] = progress["completed"]
    d["progress_total"] = progress["total"]
    d["effective_deadline"] = effective_deadline(d["id"], conn)
    d["children"] = []
    d["depth"] = d.get("depth", 0)
    return d


def get_items_tree(conn: sqlite3.Connection, project_id: int) -> list[dict]:
    """Get all work items for a project as a flat list (frontend builds tree)."""
    rows = conn.execute(
        "SELECT *, 0 as depth FROM work_items WHERE project_id = ? ORDER BY sort_order",
        (project_id,)
    ).fetchall()
    return [_enrich_item(r, conn) for r in rows]


def create_item(conn: sqlite3.Connection, project_id: int, data: dict) -> dict:
    """Create a work item."""
    data["project_id"] = project_id

    # Get next sort_order among siblings
    parent_id = data.get("parent_id")
    if parent_id:
        max_sort = conn.execute(
            "SELECT COALESCE(MAX(sort_order), 0) FROM work_items WHERE parent_id = ?",
            (parent_id,)
        ).fetchone()[0]
    else:
        max_sort = conn.execute(
            "SELECT COALESCE(MAX(sort_order), 0) FROM work_items WHERE project_id = ? AND parent_id IS NULL",
            (project_id,)
        ).fetchone()[0]
    data["sort_order"] = max_sort + 1

    cols = [k for k in data if data[k] is not None]
    placeholders = ", ".join(["?"] * len(cols))
    col_names = ", ".join(cols)
    vals = [data[k] for k in cols]

    cur = conn.execute(f"INSERT INTO work_items ({col_names}) VALUES ({placeholders})", vals)
    conn.commit()
    return get_item(conn, cur.lastrowid)


def get_item(conn: sqlite3.Connection, item_id: int) -> dict | None:
    """Get a single work item enriched."""
    row = conn.execute("SELECT *, 0 as depth FROM work_items WHERE id = ?", (item_id,)).fetchone()
    if not row:
        return None
    return _enrich_item(row, conn)


def update_item(conn: sqlite3.Connection, item_id: int, data: dict) -> dict | None:
    """Update work item fields."""
    updates = {k: v for k, v in data.items() if v is not None}
    if not updates:
        return get_item(conn, item_id)

    updates["updated_at"] = datetime.utcnow().isoformat()

    # Handle status change to completed
    if updates.get("status") == "completed":
        updates["completed_at"] = datetime.utcnow().isoformat()
    elif updates.get("status") and updates["status"] != "completed":
        updates["completed_at"] = None

    set_clause = ", ".join(f"{k} = ?" for k in updates)
    vals = list(updates.values()) + [item_id]
    conn.execute(f"UPDATE work_items SET {set_clause} WHERE id = ?", vals)
    conn.commit()
    return get_item(conn, item_id)


def delete_item(conn: sqlite3.Connection, item_id: int) -> bool:
    """Delete work item and cascade to descendants."""
    conn.execute("DELETE FROM work_items WHERE id = ?", (item_id,))
    conn.commit()
    return True


def reorder_items(conn: sqlite3.Connection, items: list[dict]):
    """Update sort_order for siblings."""
    for item in items:
        conn.execute("UPDATE work_items SET sort_order = ? WHERE id = ?",
                      (item["sort_order"], item["id"]))
    conn.commit()


def move_item(conn: sqlite3.Connection, item_id: int, parent_id: int | None, project_id: int | None) -> dict | None:
    """Move item to different parent or project."""
    updates = {"updated_at": datetime.utcnow().isoformat()}
    if parent_id is not None:
        updates["parent_id"] = parent_id if parent_id != 0 else None
    if project_id is not None:
        updates["project_id"] = project_id
        # Also move all descendants to new project
        _move_descendants_project(conn, item_id, project_id)

    set_clause = ", ".join(f"{k} = ?" for k in updates)
    vals = list(updates.values()) + [item_id]
    conn.execute(f"UPDATE work_items SET {set_clause} WHERE id = ?", vals)
    conn.commit()
    return get_item(conn, item_id)


def _move_descendants_project(conn: sqlite3.Connection, parent_id: int, project_id: int):
    """Recursively update project_id for all descendants."""
    children = conn.execute(
        "SELECT id FROM work_items WHERE parent_id = ?", (parent_id,)
    ).fetchall()
    for child in children:
        conn.execute("UPDATE work_items SET project_id = ? WHERE id = ?",
                      (project_id, child["id"]))
        _move_descendants_project(conn, child["id"], project_id)


# ── Assignments ─────────────────────────────────────────────────────

def list_assignments(conn: sqlite3.Connection, item_id: int) -> list[dict]:
    """List assignments for a work item."""
    rows = conn.execute(
        "SELECT * FROM work_item_assignments WHERE work_item_id = ? ORDER BY role, assigned_at",
        (item_id,)
    ).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        try:
            member = conn.execute(
                "SELECT name FROM pipeline.team_members WHERE id = ?",
                (r["team_member_id"],)
            ).fetchone()
            d["member_name"] = member["name"] if member else ""
        except Exception:
            d["member_name"] = ""
        result.append(d)
    return result


def add_assignment(conn: sqlite3.Connection, item_id: int, team_member_id: int, role: str = "assigned") -> dict:
    """Add an assignment."""
    cur = conn.execute(
        "INSERT OR IGNORE INTO work_item_assignments (work_item_id, team_member_id, role) VALUES (?, ?, ?)",
        (item_id, team_member_id, role)
    )
    conn.commit()
    # Return the assignment
    row = conn.execute(
        "SELECT * FROM work_item_assignments WHERE work_item_id = ? AND team_member_id = ? AND role = ?",
        (item_id, team_member_id, role)
    ).fetchone()
    d = dict(row)
    try:
        member = conn.execute(
            "SELECT name FROM pipeline.team_members WHERE id = ?", (team_member_id,)
        ).fetchone()
        d["member_name"] = member["name"] if member else ""
    except Exception:
        d["member_name"] = ""
    return d


def remove_assignment(conn: sqlite3.Connection, assignment_id: int) -> bool:
    """Remove an assignment."""
    conn.execute("DELETE FROM work_item_assignments WHERE id = ?", (assignment_id,))
    conn.commit()
    return True


def get_member_items(conn: sqlite3.Connection, member_id: int) -> list[dict]:
    """Get all work items assigned to a team member across all projects."""
    rows = conn.execute(
        "SELECT wi.*, wia.role as assignment_role, 0 as depth "
        "FROM work_items wi "
        "JOIN work_item_assignments wia ON wi.id = wia.work_item_id "
        "WHERE wia.team_member_id = ? "
        "ORDER BY wi.project_id, wi.sort_order",
        (member_id,)
    ).fetchall()
    result = []
    for r in rows:
        d = _enrich_item(r, conn)
        d["assignment_role"] = r["assignment_role"]
        # Add project title
        proj = conn.execute("SELECT title FROM projects WHERE id = ?", (d["project_id"],)).fetchone()
        d["project_title"] = proj["title"] if proj else ""
        result.append(d)
    return result


# ── Dependencies ────────────────────────────────────────────────────

def add_dependency(conn: sqlite3.Connection, blocked_id: int, blocking_id: int, description: str = None) -> dict:
    """Add a dependency."""
    conn.execute(
        "INSERT OR IGNORE INTO work_item_dependencies (blocked_item_id, blocking_item_id, description) VALUES (?, ?, ?)",
        (blocked_id, blocking_id, description)
    )
    conn.commit()
    row = conn.execute(
        "SELECT * FROM work_item_dependencies WHERE blocked_item_id = ? AND blocking_item_id = ?",
        (blocked_id, blocking_id)
    ).fetchone()
    d = dict(row)
    blocking = conn.execute("SELECT title FROM work_items WHERE id = ?", (blocking_id,)).fetchone()
    d["blocking_item_title"] = blocking["title"] if blocking else ""
    d["resolved"] = bool(d["resolved"])
    return d


def remove_dependency(conn: sqlite3.Connection, dep_id: int) -> bool:
    """Remove a dependency."""
    conn.execute("DELETE FROM work_item_dependencies WHERE id = ?", (dep_id,))
    conn.commit()
    return True
