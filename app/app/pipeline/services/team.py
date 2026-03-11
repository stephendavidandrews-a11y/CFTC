"""
Team management service: CRUD, workload queries, dashboard.
"""

import json
import logging
from datetime import date

logger = logging.getLogger(__name__)


def list_members(conn, active_only=True):
    """List all team members."""
    sql = "SELECT * FROM team_members"
    if active_only:
        sql += " WHERE is_active = 1"
    sql += " ORDER BY name"
    rows = conn.execute(sql).fetchall()
    result = []
    for r in rows:
        m = dict(r)
        m["is_active"] = bool(m.get("is_active", 1))
        try:
            m["specializations"] = json.loads(m.get("specializations") or "[]")
        except (json.JSONDecodeError, TypeError):
            m["specializations"] = []
        result.append(m)
    return result


def get_member(conn, member_id: int):
    """Get a single team member by ID."""
    row = conn.execute(
        "SELECT * FROM team_members WHERE id = ?", (member_id,)
    ).fetchone()
    if not row:
        return None
    m = dict(row)
    m["is_active"] = bool(m.get("is_active", 1))
    try:
        m["specializations"] = json.loads(m.get("specializations") or "[]")
    except (json.JSONDecodeError, TypeError):
        m["specializations"] = []
    return m


def create_member(conn, data: dict) -> dict:
    """Create a new team member."""
    specs = json.dumps(data.get("specializations", []))
    cursor = conn.execute(
        """INSERT INTO team_members
           (name, email, role, gs_level, division, specializations, max_concurrent)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            data["name"],
            data.get("email"),
            data["role"],
            data.get("gs_level"),
            data.get("division", "Regulation"),
            specs,
            data.get("max_concurrent", 5),
        ),
    )
    conn.commit()
    return get_member(conn, cursor.lastrowid)


def update_member(conn, member_id: int, data: dict) -> dict | None:
    """Update team member fields."""
    existing = get_member(conn, member_id)
    if not existing:
        return None

    updates = {}
    for key in ("name", "email", "role", "gs_level", "division", "max_concurrent"):
        if data.get(key) is not None:
            updates[key] = data[key]
    if data.get("specializations") is not None:
        updates["specializations"] = json.dumps(data["specializations"])
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
