"""
Recursive progress and deadline computation for work items.
"""

import sqlite3
from datetime import datetime, date


def compute_progress(item_id: int, conn: sqlite3.Connection) -> dict:
    """
    Compute recursive progress for a work item.
    Counts leaf nodes only: completed leaves / total leaves.
    """
    children = conn.execute(
        "SELECT id, status FROM work_items WHERE parent_id = ?", (item_id,)
    ).fetchall()

    if not children:
        # Leaf node
        status = conn.execute(
            "SELECT status FROM work_items WHERE id = ?", (item_id,)
        ).fetchone()
        is_done = status and status["status"] == "completed"
        return {"completed": 1 if is_done else 0, "total": 1}

    result = {"completed": 0, "total": 0}
    for child in children:
        child_progress = compute_progress(child["id"], conn)
        result["completed"] += child_progress["completed"]
        result["total"] += child_progress["total"]
    return result


def compute_project_progress(project_id: int, conn: sqlite3.Connection) -> dict:
    """Compute progress across all work items in a project (leaf-node based)."""
    top_items = conn.execute(
        "SELECT id FROM work_items WHERE project_id = ? AND parent_id IS NULL",
        (project_id,)
    ).fetchall()

    result = {"completed": 0, "total": 0}
    for item in top_items:
        item_progress = compute_progress(item["id"], conn)
        result["completed"] += item_progress["completed"]
        result["total"] += item_progress["total"]
    return result


def effective_deadline(item_id: int, conn: sqlite3.Connection) -> str | None:
    """
    Compute effective deadline: earliest pending due_date among
    item and all its pending descendants.
    """
    item = conn.execute(
        "SELECT due_date, status FROM work_items WHERE id = ?", (item_id,)
    ).fetchone()
    if not item:
        return None

    dates = []
    if item["due_date"] and item["status"] != "completed":
        dates.append(item["due_date"])

    children = conn.execute(
        "SELECT id, status FROM work_items WHERE parent_id = ?", (item_id,)
    ).fetchall()

    for child in children:
        if child["status"] != "completed":
            child_deadline = effective_deadline(child["id"], conn)
            if child_deadline:
                dates.append(child_deadline)

    return min(dates) if dates else None


def project_effective_deadline(project_id: int, conn: sqlite3.Connection) -> str | None:
    """Earliest pending deadline across all items in a project."""
    top_items = conn.execute(
        "SELECT id, status, due_date FROM work_items WHERE project_id = ? AND parent_id IS NULL",
        (project_id,)
    ).fetchall()

    dates = []
    for item in top_items:
        if item["status"] != "completed":
            dl = effective_deadline(item["id"], conn)
            if dl:
                dates.append(dl)
    return min(dates) if dates else None


def count_blocked(project_id: int, conn: sqlite3.Connection) -> int:
    """Count blocked work items in a project."""
    row = conn.execute(
        "SELECT COUNT(*) as cnt FROM work_items WHERE project_id = ? AND status = 'blocked'",
        (project_id,)
    ).fetchone()
    return row["cnt"] if row else 0
