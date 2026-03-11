"""
Business logic for projects.
"""

import sqlite3
import json
from datetime import datetime

from app.work.services.progress import (
    compute_project_progress,
    project_effective_deadline,
    count_blocked,
)


def _resolve_attorney_name(conn: sqlite3.Connection, attorney_id: int | None) -> str | None:
    """Look up attorney name from pipeline.team_members."""
    if not attorney_id:
        return None
    try:
        row = conn.execute(
            "SELECT name FROM pipeline.team_members WHERE id = ?", (attorney_id,)
        ).fetchone()
        return row["name"] if row else None
    except Exception:
        return None


def _resolve_type_label(conn: sqlite3.Connection, type_key: str) -> str:
    """Look up project type label."""
    row = conn.execute(
        "SELECT label FROM project_types WHERE type_key = ?", (type_key,)
    ).fetchone()
    return row["label"] if row else type_key


def _enrich_project(row: sqlite3.Row, conn: sqlite3.Connection) -> dict:
    """Convert a project row to enriched dict with computed fields."""
    d = dict(row)
    d["lead_attorney_name"] = _resolve_attorney_name(conn, d.get("lead_attorney_id"))
    d["type_label"] = _resolve_type_label(conn, d.get("project_type", ""))

    progress = compute_project_progress(d["id"], conn)
    d["progress_completed"] = progress["completed"]
    d["progress_total"] = progress["total"]
    d["effective_deadline"] = project_effective_deadline(d["id"], conn)
    d["blocked_count"] = count_blocked(d["id"], conn)
    return d


def list_projects(conn: sqlite3.Connection, **filters) -> list[dict]:
    """List projects with optional filters."""
    sql = "SELECT * FROM projects WHERE 1=1"
    params = []

    if filters.get("status"):
        sql += " AND status = ?"
        params.append(filters["status"])
    if filters.get("project_type"):
        sql += " AND project_type = ?"
        params.append(filters["project_type"])
    if filters.get("priority_label"):
        sql += " AND priority_label = ?"
        params.append(filters["priority_label"])
    if filters.get("lead_attorney_id"):
        sql += " AND lead_attorney_id = ?"
        params.append(int(filters["lead_attorney_id"]))
    if filters.get("search"):
        sql += " AND (title LIKE ? OR short_title LIKE ? OR description LIKE ?)"
        s = f"%{filters['search']}%"
        params.extend([s, s, s])

    sort_by = filters.get("sort_by", "sort_order")
    sort_dir = filters.get("sort_dir", "asc")
    allowed_sorts = {"sort_order", "priority_label", "title", "created_at", "updated_at"}
    if sort_by not in allowed_sorts:
        sort_by = "sort_order"
    sql += f" ORDER BY {sort_by} {'DESC' if sort_dir == 'desc' else 'ASC'}"

    rows = conn.execute(sql, params).fetchall()
    return [_enrich_project(r, conn) for r in rows]


def get_project(conn: sqlite3.Connection, project_id: int) -> dict | None:
    """Get a single project with enriched data."""
    row = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
    if not row:
        return None
    return _enrich_project(row, conn)


def create_project(conn: sqlite3.Connection, data: dict) -> dict:
    """Create a new project, optionally applying template."""
    apply_template = data.pop("apply_template", False)

    # Get next sort_order
    max_sort = conn.execute("SELECT COALESCE(MAX(sort_order), 0) FROM projects").fetchone()[0]
    data["sort_order"] = max_sort + 1

    cols = [k for k in data if data[k] is not None]
    placeholders = ", ".join(["?"] * len(cols))
    col_names = ", ".join(cols)
    vals = [data[k] for k in cols]

    cur = conn.execute(f"INSERT INTO projects ({col_names}) VALUES ({placeholders})", vals)
    project_id = cur.lastrowid

    if apply_template:
        _apply_template(conn, project_id, data.get("project_type", ""))

    conn.commit()
    return get_project(conn, project_id)


def _apply_template(conn: sqlite3.Connection, project_id: int, project_type: str):
    """Create work items from the project type template."""
    templates = conn.execute(
        "SELECT item_title, item_description, item_sort_order, parent_ref "
        "FROM project_type_templates WHERE project_type = ? ORDER BY item_sort_order",
        (project_type,)
    ).fetchall()

    title_to_id = {}
    for t in templates:
        parent_id = title_to_id.get(t["parent_ref"]) if t["parent_ref"] else None
        cur = conn.execute(
            "INSERT INTO work_items (project_id, parent_id, title, description, sort_order) "
            "VALUES (?, ?, ?, ?, ?)",
            (project_id, parent_id, t["item_title"], t["item_description"], t["item_sort_order"])
        )
        title_to_id[t["item_title"]] = cur.lastrowid


def update_project(conn: sqlite3.Connection, project_id: int, data: dict) -> dict | None:
    """Update project fields."""
    updates = {k: v for k, v in data.items() if v is not None}
    if not updates:
        return get_project(conn, project_id)

    updates["updated_at"] = datetime.utcnow().isoformat()
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    vals = list(updates.values()) + [project_id]
    conn.execute(f"UPDATE projects SET {set_clause} WHERE id = ?", vals)
    conn.commit()
    return get_project(conn, project_id)


def delete_project(conn: sqlite3.Connection, project_id: int) -> bool:
    """Delete a project and cascade."""
    conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))
    conn.commit()
    return True


def reorder_projects(conn: sqlite3.Connection, items: list[dict]):
    """Update sort_order for multiple projects."""
    for item in items:
        conn.execute("UPDATE projects SET sort_order = ? WHERE id = ?",
                      (item["sort_order"], item["id"]))
    conn.commit()
