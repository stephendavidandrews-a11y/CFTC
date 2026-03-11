"""
Interagency contacts service: CRUD and relationship tracking.
"""

import json
import logging
from datetime import date

logger = logging.getLogger(__name__)


def _deserialize_contact(row) -> dict:
    """Convert a contact row to dict with JSON fields parsed."""
    d = dict(row)
    try:
        d["areas_of_focus"] = json.loads(d.get("areas_of_focus") or "[]")
    except (json.JSONDecodeError, TypeError):
        d["areas_of_focus"] = []
    # Compute days since last contact
    d["days_since_contact"] = None
    if d.get("last_contact_date"):
        try:
            last = date.fromisoformat(d["last_contact_date"])
            d["days_since_contact"] = (date.today() - last).days
        except (ValueError, TypeError):
            pass
    return d


def list_contacts(conn, agency: str = None, relationship_status: str = None) -> list[dict]:
    """List all interagency contacts with optional filters."""
    sql = "SELECT * FROM interagency_contacts WHERE 1=1"
    params = []
    if agency:
        sql += " AND agency = ?"
        params.append(agency)
    if relationship_status:
        sql += " AND relationship_status = ?"
        params.append(relationship_status)
    sql += " ORDER BY agency, name"
    rows = conn.execute(sql, params).fetchall()
    return [_deserialize_contact(r) for r in rows]


def get_contact(conn, contact_id: int) -> dict | None:
    """Get a single contact by ID."""
    row = conn.execute(
        "SELECT * FROM interagency_contacts WHERE id = ?", (contact_id,)
    ).fetchone()
    if not row:
        return None
    return _deserialize_contact(row)


def create_contact(conn, data: dict) -> dict:
    """Create a new interagency contact."""
    if "areas_of_focus" in data and isinstance(data["areas_of_focus"], list):
        data["areas_of_focus"] = json.dumps(data["areas_of_focus"])

    cols = [k for k in data if data[k] is not None]
    placeholders = ", ".join(["?"] * len(cols))
    col_names = ", ".join(cols)
    vals = [data[k] for k in cols]

    cursor = conn.execute(
        f"INSERT INTO interagency_contacts ({col_names}) VALUES ({placeholders})", vals
    )
    conn.commit()
    return get_contact(conn, cursor.lastrowid)


def update_contact(conn, contact_id: int, data: dict) -> dict | None:
    """Update contact fields."""
    existing = get_contact(conn, contact_id)
    if not existing:
        return None

    updates = {}
    for key in ("name", "title", "agency", "email", "phone",
                "relationship_status", "last_contact_date", "notes"):
        if data.get(key) is not None:
            updates[key] = data[key]
    if data.get("areas_of_focus") is not None:
        updates["areas_of_focus"] = json.dumps(data["areas_of_focus"])

    if not updates:
        return existing

    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [contact_id]
    conn.execute(
        f"UPDATE interagency_contacts SET {set_clause}, updated_at = datetime('now') WHERE id = ?",
        values,
    )
    conn.commit()
    return get_contact(conn, contact_id)


def delete_contact(conn, contact_id: int) -> bool:
    """Delete a contact."""
    conn.execute("DELETE FROM interagency_contacts WHERE id = ?", (contact_id,))
    conn.commit()
    return True


def get_dormant_contacts(conn, days: int = 90) -> list[dict]:
    """Get contacts not reached in N+ days (established+ relationships only)."""
    today = date.today().isoformat()
    rows = conn.execute(
        """SELECT * FROM interagency_contacts
           WHERE relationship_status IN ('close_ally', 'regular_contact', 'acquaintance')
             AND (last_contact_date IS NULL
                  OR julianday(?) - julianday(last_contact_date) > ?)
           ORDER BY last_contact_date ASC""",
        (today, days),
    ).fetchall()
    return [_deserialize_contact(r) for r in rows]
