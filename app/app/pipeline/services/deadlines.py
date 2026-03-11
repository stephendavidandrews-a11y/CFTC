"""
Deadline engine: CRUD, backward calculation, overdue detection, extensions.
"""

import logging
from datetime import date, datetime, timedelta

logger = logging.getLogger(__name__)


def _enrich_deadline(conn, row):
    """Add computed fields to a deadline row."""
    dl = dict(row)

    # Owner name
    dl["owner_name"] = None
    if dl.get("owner_id"):
        tm = conn.execute(
            "SELECT name FROM team_members WHERE id = ?", (dl["owner_id"],)
        ).fetchone()
        if tm:
            dl["owner_name"] = tm["name"]

    # Item title
    dl["item_title"] = None
    if dl.get("item_id"):
        item = conn.execute(
            "SELECT short_title, title FROM pipeline_items WHERE id = ?",
            (dl["item_id"],),
        ).fetchone()
        if item:
            dl["item_title"] = item["short_title"] or item["title"]

    # Days remaining + severity
    dl["days_remaining"] = None
    dl["severity"] = "ok"
    if dl.get("due_date") and dl["status"] == "pending":
        try:
            due = date.fromisoformat(dl["due_date"])
            days_left = (due - date.today()).days
            dl["days_remaining"] = days_left
            if days_left < 0:
                dl["severity"] = "overdue"
            elif days_left <= (dl.get("days_critical") or 3):
                dl["severity"] = "critical"
            elif days_left <= (dl.get("days_warning") or 14):
                dl["severity"] = "warning"
        except (ValueError, TypeError):
            pass

    dl["is_hard_deadline"] = bool(dl.get("is_hard_deadline", 1))
    return dl


def create_deadline(conn, data: dict) -> dict:
    """Create a new deadline for an item."""
    cursor = conn.execute(
        """INSERT INTO pipeline_deadlines
           (item_id, deadline_type, title, due_date, source, source_detail,
            is_hard_deadline, days_warning, days_critical, owner_id)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            data["item_id"],
            data["deadline_type"],
            data["title"],
            data["due_date"],
            data.get("source"),
            data.get("source_detail"),
            1 if data.get("is_hard_deadline", True) else 0,
            data.get("days_warning", 14),
            data.get("days_critical", 3),
            data.get("owner_id"),
        ),
    )
    conn.commit()

    # Log to decision log
    conn.execute(
        """INSERT INTO pipeline_decision_log
           (item_id, action_type, description, new_value)
           VALUES (?, 'deadline_change', ?, ?)""",
        (data["item_id"], f"Deadline added: {data['title']}", data["due_date"]),
    )
    conn.commit()

    row = conn.execute(
        "SELECT * FROM pipeline_deadlines WHERE id = ?", (cursor.lastrowid,)
    ).fetchone()
    return _enrich_deadline(conn, row)


def get_deadline(conn, deadline_id: int):
    """Get a single deadline by ID."""
    row = conn.execute(
        "SELECT * FROM pipeline_deadlines WHERE id = ?", (deadline_id,)
    ).fetchone()
    if not row:
        return None
    return _enrich_deadline(conn, row)


def list_deadlines(
    conn, item_id=None, deadline_type=None, status=None,
    due_before=None, due_after=None, overdue_only=False,
    page=1, page_size=50,
) -> tuple[list[dict], int]:
    """List deadlines with filters."""
    conditions = []
    params = []

    if item_id:
        conditions.append("pd.item_id = ?")
        params.append(item_id)
    if deadline_type:
        conditions.append("pd.deadline_type = ?")
        params.append(deadline_type)
    if status:
        conditions.append("pd.status = ?")
        params.append(status)
    if due_before:
        conditions.append("pd.due_date <= ?")
        params.append(due_before)
    if due_after:
        conditions.append("pd.due_date >= ?")
        params.append(due_after)
    if overdue_only:
        today = date.today().isoformat()
        conditions.append("pd.due_date < ?")
        conditions.append("pd.status = 'pending'")
        params.append(today)

    where = ""
    if conditions:
        where = "WHERE " + " AND ".join(conditions)

    total = conn.execute(
        f"SELECT COUNT(*) FROM pipeline_deadlines pd {where}", params
    ).fetchone()[0]

    offset = (page - 1) * page_size
    rows = conn.execute(
        f"""SELECT pd.* FROM pipeline_deadlines pd
            {where} ORDER BY pd.due_date ASC
            LIMIT ? OFFSET ?""",
        params + [page_size, offset],
    ).fetchall()

    return [_enrich_deadline(conn, r) for r in rows], total


def update_deadline(conn, deadline_id: int, data: dict) -> dict | None:
    """Update deadline fields."""
    existing = conn.execute(
        "SELECT * FROM pipeline_deadlines WHERE id = ?", (deadline_id,)
    ).fetchone()
    if not existing:
        return None

    updates = {}
    for key in ("title", "due_date", "deadline_type", "status", "owner_id",
                "days_warning", "days_critical"):
        if data.get(key) is not None:
            updates[key] = data[key]
    if data.get("is_hard_deadline") is not None:
        updates["is_hard_deadline"] = 1 if data["is_hard_deadline"] else 0

    if not updates:
        return _enrich_deadline(conn, existing)

    # Log changes
    for key, new_val in updates.items():
        old_val = existing[key] if key in existing.keys() else None
        if str(old_val) != str(new_val):
            conn.execute(
                """INSERT INTO pipeline_decision_log
                   (item_id, action_type, description, old_value, new_value)
                   VALUES (?, 'deadline_change', ?, ?, ?)""",
                (existing["item_id"], f"Deadline updated: {key}", str(old_val), str(new_val)),
            )

    updates["updated_at"] = datetime.now().isoformat()
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [deadline_id]
    conn.execute(
        f"UPDATE pipeline_deadlines SET {set_clause} WHERE id = ?", values
    )

    if updates.get("status") == "met":
        conn.execute(
            "UPDATE pipeline_deadlines SET completed_at = datetime('now') WHERE id = ?",
            (deadline_id,),
        )

    conn.commit()
    return get_deadline(conn, deadline_id)


def extend_deadline(conn, deadline_id: int, new_due_date: str, reason: str) -> dict | None:
    """Extend a deadline with reason."""
    existing = conn.execute(
        "SELECT * FROM pipeline_deadlines WHERE id = ?", (deadline_id,)
    ).fetchone()
    if not existing:
        return None

    conn.execute(
        """UPDATE pipeline_deadlines
           SET extended_to = ?, extension_reason = ?, due_date = ?,
               updated_at = datetime('now')
           WHERE id = ?""",
        (new_due_date, reason, new_due_date, deadline_id),
    )

    conn.execute(
        """INSERT INTO pipeline_decision_log
           (item_id, action_type, description, old_value, new_value, rationale)
           VALUES (?, 'deadline_change', ?, ?, ?, ?)""",
        (
            existing["item_id"],
            f"Deadline extended: {existing['title']}",
            existing["due_date"],
            new_due_date,
            reason,
        ),
    )
    conn.commit()
    return get_deadline(conn, deadline_id)


def get_upcoming(conn, days=30, limit=20) -> list[dict]:
    """Get upcoming deadlines for the executive dashboard."""
    today = date.today().isoformat()
    future = (date.today() + timedelta(days=days)).isoformat()

    rows = conn.execute(
        """SELECT pd.* FROM pipeline_deadlines pd
           JOIN pipeline_items pi ON pd.item_id = pi.id
           WHERE pd.status = 'pending'
             AND pd.due_date >= ? AND pd.due_date <= ?
             AND pi.status = 'active'
           ORDER BY pd.due_date ASC
           LIMIT ?""",
        (today, future, limit),
    ).fetchall()
    return [_enrich_deadline(conn, r) for r in rows]


def backward_calculate(conn, item_id: int, final_date: str, item_type: str) -> list[dict]:
    """
    Given a final deadline date and item type, generate predecessor
    deadlines by walking backward through stage SLA days.
    """
    item = conn.execute(
        "SELECT * FROM pipeline_items WHERE id = ?", (item_id,)
    ).fetchone()
    if not item:
        return []

    stages = conn.execute(
        """SELECT stage_key, stage_label, sla_days, stage_order
           FROM stage_templates
           WHERE module = ? AND item_type = ?
           ORDER BY stage_order DESC""",
        (item["module"], item_type),
    ).fetchall()

    if not stages:
        return []

    created = []
    current_due = date.fromisoformat(final_date)

    for stage in stages:
        sla = stage["sla_days"]
        if not sla:
            continue

        title = f"{stage['stage_label']} completion"
        due_str = current_due.isoformat()

        cursor = conn.execute(
            """INSERT INTO pipeline_deadlines
               (item_id, deadline_type, title, due_date, source, is_hard_deadline,
                days_warning, days_critical)
               VALUES (?, 'internal', ?, ?, 'Backward calculation', 0, 14, 3)""",
            (item_id, title, due_str),
        )
        conn.commit()

        dl = get_deadline(conn, cursor.lastrowid)
        created.append(dl)

        # Move backward by SLA days
        current_due = current_due - timedelta(days=sla)

    # Log the backward calculation
    conn.execute(
        """INSERT INTO pipeline_decision_log
           (item_id, action_type, description, new_value)
           VALUES (?, 'deadline_change', ?, ?)""",
        (item_id, f"Backward-calculated {len(created)} deadlines", final_date),
    )
    conn.commit()

    return created
