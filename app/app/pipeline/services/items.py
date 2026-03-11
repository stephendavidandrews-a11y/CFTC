"""
Pipeline item CRUD and business logic.

All functions take an open sqlite3.Connection and are synchronous.
The router layer wraps them in run_in_executor for async FastAPI.
"""

import json
import logging
from datetime import datetime, date

logger = logging.getLogger(__name__)


def _resolve_stage_label(conn, module, item_type, stage_key):
    """Look up the display label and color for a stage_key."""
    row = conn.execute(
        """SELECT stage_label, stage_color FROM stage_templates
           WHERE module = ? AND item_type = ? AND stage_key = ?""",
        (module, item_type, stage_key),
    ).fetchone()
    if row:
        return row["stage_label"], row["stage_color"]
    return stage_key, "#6b7280"


def _get_first_stage(conn, module, item_type):
    """Get the first stage_key for an item type from templates."""
    row = conn.execute(
        """SELECT stage_key FROM stage_templates
           WHERE module = ? AND item_type = ?
           ORDER BY stage_order ASC LIMIT 1""",
        (module, item_type),
    ).fetchone()
    if not row:
        raise ValueError(
            f"No stage templates found for module={module}, item_type={item_type}"
        )
    return row["stage_key"]


def _get_next_stage(conn, module, item_type, current_stage):
    """Get the next stage_key after the current one."""
    row = conn.execute(
        """SELECT stage_order FROM stage_templates
           WHERE module = ? AND item_type = ? AND stage_key = ?""",
        (module, item_type, current_stage),
    ).fetchone()
    if not row:
        return None

    next_row = conn.execute(
        """SELECT stage_key FROM stage_templates
           WHERE module = ? AND item_type = ? AND stage_order > ?
           ORDER BY stage_order ASC LIMIT 1""",
        (module, item_type, row["stage_order"]),
    ).fetchone()
    return next_row["stage_key"] if next_row else None


def _days_since(dt_str):
    """Calculate days since an ISO datetime string."""
    if not dt_str:
        return 0
    try:
        dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        return (datetime.now() - dt.replace(tzinfo=None)).days
    except (ValueError, TypeError):
        return 0


def _enrich_item(conn, row):
    """Add computed fields to a pipeline_items row."""
    item = dict(row)

    # Resolve stage label/color
    label, color = _resolve_stage_label(
        conn, item["module"], item["item_type"], item["current_stage"]
    )
    item["stage_label"] = label
    item["stage_color"] = color

    # Days in stage
    item["days_in_stage"] = _days_since(item.get("stage_entered_at"))

    # Lead attorney name
    item["lead_attorney_name"] = None
    if item.get("lead_attorney_id"):
        tm = conn.execute(
            "SELECT name FROM team_members WHERE id = ?",
            (item["lead_attorney_id"],),
        ).fetchone()
        if tm:
            item["lead_attorney_name"] = tm["name"]

    # Next deadline
    dl = conn.execute(
        """SELECT title, due_date FROM pipeline_deadlines
           WHERE item_id = ? AND status = 'pending'
           ORDER BY due_date ASC LIMIT 1""",
        (item["id"],),
    ).fetchone()
    if dl:
        item["next_deadline_date"] = dl["due_date"]
        item["next_deadline_title"] = dl["title"]
        try:
            due = date.fromisoformat(dl["due_date"])
            days_left = (due - date.today()).days
            if days_left < 0:
                item["deadline_severity"] = "overdue"
            elif days_left <= 3:
                item["deadline_severity"] = "critical"
            elif days_left <= 14:
                item["deadline_severity"] = "warning"
            else:
                item["deadline_severity"] = "ok"
        except (ValueError, TypeError):
            item["deadline_severity"] = None
    else:
        item["next_deadline_date"] = None
        item["next_deadline_title"] = None
        item["deadline_severity"] = None

    # FR URL — look up most recent FR publication from decision log
    item["fr_url"] = None
    fr_log = conn.execute(
        """SELECT new_value FROM pipeline_decision_log
           WHERE item_id = ? AND action_type = 'fr_publication'
           ORDER BY created_at DESC LIMIT 1""",
        (item["id"],),
    ).fetchone()
    if fr_log and fr_log["new_value"]:
        try:
            fr_data = json.loads(fr_log["new_value"])
            item["fr_url"] = fr_data.get("html_url") or None
            # Backfill fr_citation if missing on the item
            if not item.get("fr_citation") and fr_data.get("citation"):
                item["fr_citation"] = fr_data["citation"]
        except (json.JSONDecodeError, TypeError):
            pass

    # Boolean coercion
    item["chairman_priority"] = bool(item.get("chairman_priority", 0))

    return item


def create_item(conn, data: dict) -> dict:
    """Create a new pipeline item."""
    first_stage = _get_first_stage(conn, data["module"], data["item_type"])

    cursor = conn.execute(
        """INSERT INTO pipeline_items
           (module, item_type, title, short_title, description,
            docket_number, rin, fr_citation, fr_doc_number,
            current_stage, stage_entered_at,
            chairman_priority, lead_attorney_id, backup_attorney_id,
            action_subtype, requesting_party, related_rulemaking_id,
            stage1_fr_citation, stage1_doc_id, eo_action_item_id, comment_docket,
            status, created_by)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'),
                   ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', ?)""",
        (
            data["module"],
            data["item_type"],
            data["title"],
            data.get("short_title"),
            data.get("description"),
            data.get("docket_number"),
            data.get("rin"),
            data.get("fr_citation"),
            data.get("fr_doc_number"),
            first_stage,
            1 if data.get("chairman_priority") else 0,
            data.get("lead_attorney_id"),
            data.get("backup_attorney_id"),
            data.get("action_subtype"),
            data.get("requesting_party"),
            data.get("related_rulemaking_id"),
            data.get("stage1_fr_citation"),
            data.get("stage1_doc_id"),
            data.get("eo_action_item_id"),
            data.get("comment_docket"),
            data.get("created_by"),
        ),
    )
    item_id = cursor.lastrowid

    # Log creation
    conn.execute(
        """INSERT INTO pipeline_decision_log
           (item_id, action_type, description, new_value)
           VALUES (?, 'status_change', 'Item created', 'active')""",
        (item_id,),
    )

    # Create lead assignment if specified
    if data.get("lead_attorney_id"):
        conn.execute(
            """INSERT OR IGNORE INTO pipeline_item_assignments
               (item_id, team_member_id, role) VALUES (?, ?, 'lead')""",
            (item_id, data["lead_attorney_id"]),
        )

    conn.commit()

    row = conn.execute(
        "SELECT * FROM pipeline_items WHERE id = ?", (item_id,)
    ).fetchone()
    return _enrich_item(conn, row)


def get_item(conn, item_id: int) -> dict | None:
    """Get a single item by ID with full detail."""
    row = conn.execute(
        "SELECT * FROM pipeline_items WHERE id = ?", (item_id,)
    ).fetchone()
    if not row:
        return None

    item = _enrich_item(conn, row)

    # Backup attorney name
    item["backup_attorney_name"] = None
    if item.get("backup_attorney_id"):
        tm = conn.execute(
            "SELECT name FROM team_members WHERE id = ?",
            (item["backup_attorney_id"],),
        ).fetchone()
        if tm:
            item["backup_attorney_name"] = tm["name"]

    # Assignments
    assignments = conn.execute(
        """SELECT pia.role, pia.assigned_at, tm.id as member_id, tm.name
           FROM pipeline_item_assignments pia
           JOIN team_members tm ON pia.team_member_id = tm.id
           WHERE pia.item_id = ?""",
        (item_id,),
    ).fetchall()
    item["assignments"] = [dict(a) for a in assignments]

    # Deadlines
    deadlines = conn.execute(
        """SELECT pd.*, tm.name as owner_name
           FROM pipeline_deadlines pd
           LEFT JOIN team_members tm ON pd.owner_id = tm.id
           WHERE pd.item_id = ?
           ORDER BY pd.due_date ASC""",
        (item_id,),
    ).fetchall()
    item["deadlines"] = [dict(d) for d in deadlines]

    # Recent decisions (last 10)
    decisions = conn.execute(
        """SELECT * FROM pipeline_decision_log
           WHERE item_id = ? ORDER BY created_at DESC LIMIT 10""",
        (item_id,),
    ).fetchall()
    item["recent_decisions"] = [dict(d) for d in decisions]

    # Stages from template
    stages = conn.execute(
        """SELECT stage_order, stage_key, stage_label, stage_color, is_terminal, sla_days
           FROM stage_templates
           WHERE module = ? AND item_type = ?
           ORDER BY stage_order""",
        (item["module"], item["item_type"]),
    ).fetchall()
    item["stages"] = [dict(s) for s in stages]

    # Boolean coercions
    item["enforcement_referral"] = bool(item.get("enforcement_referral", 0))

    return item


def list_items(
    conn,
    module=None, item_type=None, stage=None, status="active",
    assigned_to=None, priority_label=None, search=None,
    sort_by="priority_composite", sort_order="desc",
    page=1, page_size=50,
) -> tuple[list[dict], int]:
    """List items with filters. Returns (items, total_count)."""
    conditions = []
    params = []

    if module:
        conditions.append("pi.module = ?")
        params.append(module)
    if item_type:
        conditions.append("pi.item_type = ?")
        params.append(item_type)
    if stage:
        conditions.append("pi.current_stage = ?")
        params.append(stage)
    if status:
        conditions.append("pi.status = ?")
        params.append(status)
    if assigned_to:
        conditions.append("pi.lead_attorney_id = ?")
        params.append(assigned_to)
    if priority_label:
        conditions.append("pi.priority_label = ?")
        params.append(priority_label)
    if search:
        conditions.append(
            "(pi.title LIKE ? OR pi.docket_number LIKE ? OR pi.description LIKE ?)"
        )
        term = f"%{search}%"
        params.extend([term, term, term])

    where = ""
    if conditions:
        where = "WHERE " + " AND ".join(conditions)

    # Allowed sort columns (prevent injection)
    allowed_sorts = {
        "priority_composite", "updated_at", "created_at", "title", "due_date",
    }
    if sort_by not in allowed_sorts:
        sort_by = "priority_composite"

    direction = "DESC" if sort_order == "desc" else "ASC"

    # Count
    count_sql = f"SELECT COUNT(*) FROM pipeline_items pi {where}"
    total = conn.execute(count_sql, params).fetchone()[0]

    # Fetch
    offset = (page - 1) * page_size
    query = f"""
        SELECT pi.* FROM pipeline_items pi
        {where}
        ORDER BY pi.{sort_by} {direction}
        LIMIT ? OFFSET ?
    """
    rows = conn.execute(query, params + [page_size, offset]).fetchall()

    items = [_enrich_item(conn, r) for r in rows]
    return items, total


def get_kanban(conn, module: str, item_type=None, status="active") -> dict:
    """Get items grouped by stage for Kanban rendering."""
    # Get stage template
    conditions = ["module = ?"]
    params = [module]
    if item_type:
        conditions.append("item_type = ?")
        params.append(item_type)

    stages = conn.execute(
        f"""SELECT DISTINCT stage_key, stage_label, stage_color, stage_order
            FROM stage_templates
            WHERE {' AND '.join(conditions)}
            ORDER BY stage_order""",
        params,
    ).fetchall()

    # If no item_type filter, we get duplicates — deduplicate by stage_key
    seen = set()
    unique_stages = []
    for s in stages:
        if s["stage_key"] not in seen:
            seen.add(s["stage_key"])
            unique_stages.append(dict(s))

    # Get items
    item_conditions = ["pi.module = ?", "pi.status = ?"]
    item_params = [module, status]
    if item_type:
        item_conditions.append("pi.item_type = ?")
        item_params.append(item_type)

    items_query = f"""
        SELECT pi.* FROM pipeline_items pi
        WHERE {' AND '.join(item_conditions)}
        ORDER BY pi.priority_composite DESC
    """
    rows = conn.execute(items_query, item_params).fetchall()
    enriched = [_enrich_item(conn, r) for r in rows]

    # Group by stage
    columns = []
    total = 0
    for stage in unique_stages:
        stage_items = [i for i in enriched if i["current_stage"] == stage["stage_key"]]
        columns.append({
            "stage_key": stage["stage_key"],
            "stage_label": stage["stage_label"],
            "stage_color": stage["stage_color"],
            "stage_order": stage["stage_order"],
            "items": stage_items,
            "count": len(stage_items),
        })
        total += len(stage_items)

    return {
        "module": module,
        "item_type": item_type,
        "columns": columns,
        "total_items": total,
    }


def update_item(conn, item_id: int, data: dict, decided_by=None) -> dict | None:
    """Update item fields. Logs changes to decision_log."""
    existing = conn.execute(
        "SELECT * FROM pipeline_items WHERE id = ?", (item_id,)
    ).fetchone()
    if not existing:
        return None

    updates = {}
    for key, value in data.items():
        if value is not None and key in {
            "title", "short_title", "description", "docket_number", "rin",
            "fr_citation", "current_stage", "priority_override", "priority_label",
            "chairman_priority", "lead_attorney_id", "backup_attorney_id",
            "status", "action_subtype", "requesting_party", "related_rulemaking_id",
            "unified_agenda_rin", "stage1_fr_citation", "stage1_doc_id",
            "eo_action_item_id", "comment_docket",
        }:
            if key == "chairman_priority":
                value = 1 if value else 0
            updates[key] = value

    if not updates:
        row = conn.execute(
            "SELECT * FROM pipeline_items WHERE id = ?", (item_id,)
        ).fetchone()
        return _enrich_item(conn, row)

    # Log significant changes
    for key, new_val in updates.items():
        old_val = existing[key] if key in existing.keys() else None
        if str(old_val) != str(new_val):
            action_type = "note"
            if key == "current_stage":
                action_type = "stage_change"
            elif key in ("priority_override", "priority_label", "chairman_priority"):
                action_type = "priority_change"
            elif key in ("lead_attorney_id", "backup_attorney_id"):
                action_type = "assignment_change"
            elif key == "status":
                action_type = "status_change"

            conn.execute(
                """INSERT INTO pipeline_decision_log
                   (item_id, action_type, description, old_value, new_value, decided_by)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    item_id,
                    action_type,
                    f"Changed {key}",
                    str(old_val) if old_val is not None else None,
                    str(new_val),
                    decided_by,
                ),
            )

    # Handle stage change timestamp
    if "current_stage" in updates:
        updates["stage_entered_at"] = datetime.now().isoformat()

    updates["updated_at"] = datetime.now().isoformat()

    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [item_id]
    conn.execute(
        f"UPDATE pipeline_items SET {set_clause} WHERE id = ?", values
    )

    # Update lead assignment if changed
    if "lead_attorney_id" in updates and updates["lead_attorney_id"]:
        conn.execute(
            "DELETE FROM pipeline_item_assignments WHERE item_id = ? AND role = 'lead'",
            (item_id,),
        )
        conn.execute(
            """INSERT OR IGNORE INTO pipeline_item_assignments
               (item_id, team_member_id, role) VALUES (?, ?, 'lead')""",
            (item_id, updates["lead_attorney_id"]),
        )

    conn.commit()

    row = conn.execute(
        "SELECT * FROM pipeline_items WHERE id = ?", (item_id,)
    ).fetchone()
    return _enrich_item(conn, row)


def advance_stage(conn, item_id: int, rationale=None, decided_by=None) -> dict | None:
    """Move an item to its next stage."""
    existing = conn.execute(
        "SELECT * FROM pipeline_items WHERE id = ?", (item_id,)
    ).fetchone()
    if not existing:
        return None

    next_stage = _get_next_stage(
        conn, existing["module"], existing["item_type"], existing["current_stage"]
    )
    if not next_stage:
        return None  # Already at terminal stage

    old_label, _ = _resolve_stage_label(
        conn, existing["module"], existing["item_type"], existing["current_stage"]
    )
    new_label, _ = _resolve_stage_label(
        conn, existing["module"], existing["item_type"], next_stage
    )

    now = datetime.now().isoformat()
    conn.execute(
        """UPDATE pipeline_items
           SET current_stage = ?, stage_entered_at = ?, updated_at = ?
           WHERE id = ?""",
        (next_stage, now, now, item_id),
    )

    conn.execute(
        """INSERT INTO pipeline_decision_log
           (item_id, action_type, description, old_value, new_value,
            decided_by, rationale)
           VALUES (?, 'stage_change', ?, ?, ?, ?, ?)""",
        (
            item_id,
            f"Advanced from {old_label} to {new_label}",
            existing["current_stage"],
            next_stage,
            decided_by,
            rationale,
        ),
    )

    conn.commit()

    row = conn.execute(
        "SELECT * FROM pipeline_items WHERE id = ?", (item_id,)
    ).fetchone()
    return _enrich_item(conn, row)


def get_decision_log(conn, item_id: int, limit=50) -> list[dict]:
    """Get decision log entries for an item."""
    rows = conn.execute(
        """SELECT * FROM pipeline_decision_log
           WHERE item_id = ? ORDER BY created_at DESC LIMIT ?""",
        (item_id, limit),
    ).fetchall()
    return [dict(r) for r in rows]


def add_decision_log(conn, item_id: int, data: dict) -> dict:
    """Add a manual decision log entry."""
    cursor = conn.execute(
        """INSERT INTO pipeline_decision_log
           (item_id, action_type, description, decided_by, rationale)
           VALUES (?, ?, ?, ?, ?)""",
        (
            item_id,
            data["action_type"],
            data["description"],
            data.get("decided_by"),
            data.get("rationale"),
        ),
    )
    conn.commit()
    row = conn.execute(
        "SELECT * FROM pipeline_decision_log WHERE id = ?",
        (cursor.lastrowid,),
    ).fetchone()
    return dict(row)
