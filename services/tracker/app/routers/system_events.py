"""System events read endpoint for intelligence brief consumption."""

import json

from fastapi import APIRouter, Depends, Query

from app.db import get_db

router = APIRouter(prefix="/system-events", tags=["system-events"])

# table_name -> human-friendly entity_type
_TABLE_TO_ENTITY = {
    "matters": "matter",
    "tasks": "task",
    "people": "person",
    "organizations": "organization",
    "decisions": "decision",
    "documents": "document",
    "meetings": "meeting",
    "policy_directives": "directive",
    "comment_topics": "comment_topic",
    "comment_questions": "comment_question",
    "context_notes": "context_note",
    "person_profiles": "person_profile",
    "matter_updates": "matter_update",
}

# table_name -> column holding the human-readable name
_NAME_COLUMN = {
    "matters": "title",
    "tasks": "title",
    "people": "full_name",
    "organizations": "name",
    "decisions": "title",
    "documents": "title",
    "meetings": "title",
    "policy_directives": "directive_title",
    "comment_topics": "topic_title",
}


def _resolve_names(db, rows: list[dict]) -> dict[str, str]:
    """Batch-resolve entity names from source tables.

    Returns {record_id: name} for every row whose table has a name column.
    """
    # Group record_ids by table
    by_table: dict[str, list[str]] = {}
    for r in rows:
        tbl = r["table_name"]
        if tbl in _NAME_COLUMN:
            by_table.setdefault(tbl, []).append(r["record_id"])

    names: dict[str, str] = {}
    for tbl, ids in by_table.items():
        col = _NAME_COLUMN[tbl]
        placeholders = ",".join("?" for _ in ids)
        found = db.execute(
            f"SELECT id, {col} FROM {tbl} WHERE id IN ({placeholders})", ids
        ).fetchall()
        for row in found:
            names[row["id"]] = row[col]
    return names


@router.get("")
async def list_system_events(
    db=Depends(get_db),
    since: str = Query(None, description="ISO timestamp — return events created after this time"),
    table_name: str = Query(None, description="Filter by source table (e.g. matters, tasks)"),
    action: str = Query(None, description="Filter by action (create, update, delete)"),
    limit: int = Query(100, le=500),
    offset: int = Query(0),
):
    """List audit-trail events, newest first."""
    conditions: list[str] = []
    params: list = []

    if since:
        conditions.append("se.created_at > ?")
        params.append(since)
    if table_name:
        conditions.append("se.table_name = ?")
        params.append(table_name)
    if action:
        conditions.append("se.action = ?")
        params.append(action)

    where = "WHERE " + " AND ".join(conditions) if conditions else ""

    total = db.execute(
        f"SELECT COUNT(*) AS c FROM system_events se {where}", params
    ).fetchone()["c"]

    rows = db.execute(
        f"""SELECT se.* FROM system_events se
            {where}
            ORDER BY se.created_at DESC
            LIMIT ? OFFSET ?""",
        params + [limit, offset],
    ).fetchall()

    row_dicts = [dict(r) for r in rows]

    # Batch name resolution
    names = _resolve_names(db, row_dicts)

    items = []
    for rd in row_dicts:
        tbl = rd["table_name"]

        # Parse changed_fields JSON
        cf = rd.get("changed_fields")
        if cf and isinstance(cf, str):
            try:
                cf = json.loads(cf)
            except (json.JSONDecodeError, TypeError):
                pass

        items.append(
            {
                "id": rd["id"],
                "entity_type": _TABLE_TO_ENTITY.get(tbl, tbl),
                "entity_id": rd["record_id"],
                "entity_name": names.get(rd["record_id"], rd["record_id"][:8]),
                "action": rd["action"],
                "source": rd["source"],
                "changed_fields": cf,
                "created_at": rd["created_at"],
            }
        )

    return {"items": items, "total": total, "limit": limit, "offset": offset}
