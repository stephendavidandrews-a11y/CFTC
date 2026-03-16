"""
Team management service: CRUD, workload queries, dashboard.
"""

import json
import logging
from datetime import date

logger = logging.getLogger(__name__)

# Fields that store JSON arrays
_JSON_FIELDS = ("specializations", "strengths", "growth_areas", "recent_wins")

# All simple text/int fields on team_members
_SIMPLE_FIELDS = (
    "name", "email", "role", "gs_level", "division", "max_concurrent",
    "background_summary", "working_style", "communication_preference",
    "current_capacity", "personal_context",
)


def _deserialize_member(row) -> dict:
    """Convert a team_members row to dict with JSON fields parsed."""
    m = dict(row)
    m["is_active"] = bool(m.get("is_active", 1))
    for field in _JSON_FIELDS:
        try:
            m[field] = json.loads(m.get(field) or "[]")
        except (json.JSONDecodeError, TypeError):
            m[field] = []
    return m


def list_members(conn, active_only=True):
    """List all team members."""
    sql = "SELECT * FROM team_members"
    if active_only:
        sql += " WHERE is_active = 1"
    sql += " ORDER BY name"
    rows = conn.execute(sql).fetchall()
    return [_deserialize_member(r) for r in rows]


def get_member(conn, member_id: int):
    """Get a single team member by ID."""
    row = conn.execute(
        "SELECT * FROM team_members WHERE id = ?", (member_id,)
    ).fetchone()
    if not row:
        return None
    return _deserialize_member(row)


def create_member(conn, data: dict) -> dict:
    """Create a new team member."""
    cols = ["name", "role"]
    vals = [data["name"], data["role"]]

    # Simple text/int fields
    for key in _SIMPLE_FIELDS:
        if key in ("name", "role"):
            continue
        if data.get(key) is not None:
            cols.append(key)
            vals.append(data[key])

    # JSON array fields
    for key in _JSON_FIELDS:
        if data.get(key) is not None:
            cols.append(key)
            vals.append(json.dumps(data[key]))

    placeholders = ", ".join(["?"] * len(cols))
    col_names = ", ".join(cols)
    cursor = conn.execute(
        f"INSERT INTO team_members ({col_names}) VALUES ({placeholders})", vals
    )
    conn.commit()
    return get_member(conn, cursor.lastrowid)


def update_member(conn, member_id: int, data: dict) -> dict | None:
    """Update team member fields."""
    existing = get_member(conn, member_id)
    if not existing:
        return None

    updates = {}
    for key in _SIMPLE_FIELDS:
        if data.get(key) is not None:
            updates[key] = data[key]
    for key in _JSON_FIELDS:
        if data.get(key) is not None:
            updates[key] = json.dumps(data[key])
    if data.get("is_active") is not None:
        updates["is_active"] = 1 if data["is_active"] else 0

    if not updates:
        return existing

    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [member_id]
    conn.execute(
        f"UPDATE team_members SET {set_clause}, updated_at = datetime('now') WHERE id = ?",
        values,
    )
    conn.commit()
    return get_member(conn, member_id)


def delete_member(conn, member_id: int) -> bool:
    """Soft-delete a team member by marking inactive."""
    existing = get_member(conn, member_id)
    if not existing:
        return False
    conn.execute(
        "UPDATE team_members SET is_active = 0, updated_at = datetime('now') WHERE id = ?",
        (member_id,),
    )
    conn.commit()
    return True


def get_workload(conn, member_id: int) -> dict | None:
    """Get workload summary for a single team member."""
    member = get_member(conn, member_id)
    if not member:
        return None

    # Active items assigned (any role)
    active_items = conn.execute(
        """SELECT COUNT(DISTINCT pia.item_id) FROM pipeline_item_assignments pia
           JOIN pipeline_items pi ON pia.item_id = pi.id
           WHERE pia.team_member_id = ? AND pi.status = 'active'""",
        (member_id,),
    ).fetchone()[0]

    # Lead items
    lead_items = conn.execute(
        """SELECT COUNT(*) FROM pipeline_items
           WHERE lead_attorney_id = ? AND status = 'active'""",
        (member_id,),
    ).fetchone()[0]

    # Overdue deadlines
    today = date.today().isoformat()
    overdue = conn.execute(
        """SELECT COUNT(*) FROM pipeline_deadlines pd
           JOIN pipeline_items pi ON pd.item_id = pi.id
           WHERE pd.owner_id = ? AND pd.status = 'pending'
             AND pd.due_date < ? AND pi.status = 'active'""",
        (member_id, today),
    ).fetchone()[0]

    # Upcoming deadlines (next 30 days)
    upcoming = conn.execute(
        """SELECT pd.id, pd.title, pd.due_date, pd.deadline_type, pd.is_hard_deadline,
                  pi.id as item_id, pi.short_title as item_title
           FROM pipeline_deadlines pd
           JOIN pipeline_items pi ON pd.item_id = pi.id
           WHERE pd.owner_id = ? AND pd.status = 'pending'
             AND pd.due_date >= ? AND pi.status = 'active'
           ORDER BY pd.due_date ASC LIMIT 10""",
        (member_id, today),
    ).fetchall()

    # Items list
    items = conn.execute(
        """SELECT pi.id, pi.title, pi.short_title, pi.module, pi.item_type,
                  pi.current_stage, pi.priority_label, pia.role
           FROM pipeline_item_assignments pia
           JOIN pipeline_items pi ON pia.item_id = pi.id
           WHERE pia.team_member_id = ? AND pi.status = 'active'
           ORDER BY pi.priority_composite DESC""",
        (member_id,),
    ).fetchall()

    return {
        "member": member,
        "active_items": active_items,
        "lead_items": lead_items,
        "overdue_deadlines": overdue,
        "upcoming_deadlines": [dict(u) for u in upcoming],
        "capacity_remaining": max(0, member["max_concurrent"] - active_items),
        "items": [dict(i) for i in items],
    }


def get_team_dashboard(conn) -> dict:
    """Aggregate workload across all active team members."""
    members = list_members(conn, active_only=True)
    today = date.today().isoformat()

    dashboard_members = []
    total_active = 0
    total_overdue = 0

    for m in members:
        active = conn.execute(
            """SELECT COUNT(*) FROM pipeline_items
               WHERE lead_attorney_id = ? AND status = 'active'""",
            (m["id"],),
        ).fetchone()[0]

        overdue = conn.execute(
            """SELECT COUNT(*) FROM pipeline_deadlines pd
               JOIN pipeline_items pi ON pd.item_id = pi.id
               WHERE pd.owner_id = ? AND pd.status = 'pending'
                 AND pd.due_date < ? AND pi.status = 'active'""",
            (m["id"], today),
        ).fetchone()[0]

        dashboard_members.append({
            "id": m["id"],
            "name": m["name"],
            "role": m["role"],
            "current_capacity": m.get("current_capacity", "available"),
            "active_items": active,
            "overdue_deadlines": overdue,
            "max_concurrent": m["max_concurrent"],
            "capacity_remaining": max(0, m["max_concurrent"] - active),
        })
        total_active += active
        total_overdue += overdue

    return {
        "members": dashboard_members,
        "total_active_items": total_active,
        "total_overdue": total_overdue,
    }
