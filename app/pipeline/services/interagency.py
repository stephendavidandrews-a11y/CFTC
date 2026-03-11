"""
Interagency rulemakings service: CRUD and tracking.
"""

import json
import logging

logger = logging.getLogger(__name__)


def _deserialize_rulemaking(row) -> dict:
    """Convert a rulemaking row to dict with JSON fields parsed."""
    d = dict(row)
    for field in ("topics", "linked_pipeline_ids"):
        try:
            d[field] = json.loads(d.get(field) or "[]")
        except (json.JSONDecodeError, TypeError):
            d[field] = []
    try:
        d["key_dates"] = json.loads(d.get("key_dates") or "{}")
    except (json.JSONDecodeError, TypeError):
        d["key_dates"] = {}
    return d


def list_rulemakings(conn, agency: str = None, status: str = None) -> list[dict]:
    """List interagency rulemakings with optional filters."""
    sql = "SELECT * FROM interagency_rulemakings WHERE 1=1"
    params = []
    if agency:
        sql += " AND agency = ?"
        params.append(agency)
    if status:
        sql += " AND status = ?"
        params.append(status)
    sql += " ORDER BY updated_at DESC"
    rows = conn.execute(sql, params).fetchall()
    return [_deserialize_rulemaking(r) for r in rows]


def get_rulemaking(conn, rulemaking_id: int) -> dict | None:
    """Get a single rulemaking by ID."""
    row = conn.execute(
        "SELECT * FROM interagency_rulemakings WHERE id = ?", (rulemaking_id,)
    ).fetchone()
    if not row:
        return None
    return _deserialize_rulemaking(row)


def create_rulemaking(conn, data: dict) -> dict:
    """Create a new interagency rulemaking."""
    for field in ("topics", "linked_pipeline_ids"):
        if field in data and isinstance(data[field], list):
            data[field] = json.dumps(data[field])
    if "key_dates" in data and isinstance(data["key_dates"], dict):
        data["key_dates"] = json.dumps(data["key_dates"])

    cols = [k for k in data if data[k] is not None]
    placeholders = ", ".join(["?"] * len(cols))
    col_names = ", ".join(cols)
    vals = [data[k] for k in cols]

    cursor = conn.execute(
        f"INSERT INTO interagency_rulemakings ({col_names}) VALUES ({placeholders})", vals
    )
    conn.commit()
    return get_rulemaking(conn, cursor.lastrowid)


def update_rulemaking(conn, rulemaking_id: int, data: dict) -> dict | None:
    """Update rulemaking fields."""
    existing = get_rulemaking(conn, rulemaking_id)
    if not existing:
        return None

    updates = {}
    for key in ("title", "agency", "rulemaking_type", "status", "url",
                "summary", "cftc_position", "impact_on_cftc_work"):
        if data.get(key) is not None:
            updates[key] = data[key]
    for field in ("topics", "linked_pipeline_ids"):
        if data.get(field) is not None:
            updates[field] = json.dumps(data[field])
    if data.get("key_dates") is not None:
        updates["key_dates"] = json.dumps(data["key_dates"])

    if not updates:
        return existing

    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [rulemaking_id]
    conn.execute(
        f"UPDATE interagency_rulemakings SET {set_clause}, updated_at = datetime('now') WHERE id = ?",
        values,
    )
    conn.commit()
    return get_rulemaking(conn, rulemaking_id)


def delete_rulemaking(conn, rulemaking_id: int) -> bool:
    """Delete a rulemaking."""
    conn.execute("DELETE FROM interagency_rulemakings WHERE id = ?", (rulemaking_id,))
    conn.commit()
    return True
