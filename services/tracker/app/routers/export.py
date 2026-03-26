"""Data export endpoint — full JSON dump of all tracker tables."""

import json
import logging
from datetime import datetime
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from app.db import get_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/export", tags=["export"])

# Tables to export (order matters for FK dependencies)
EXPORT_TABLES = [
    "organizations",
    "people",
    "person_profiles",
    "matters",
    "tasks",
    "meetings",
    "meeting_participants",
    "meeting_matters",
    "documents",
    "document_files",
    "decisions",
    "matter_people",
    "matter_organizations",
    "matter_updates",
    "context_notes",
    "context_note_links",
    "tags",
    "matter_tags",
]


def _table_to_dicts(db, table_name: str) -> list[dict]:
    """Read all rows from a table as list of dicts."""
    try:
        rows = db.execute("SELECT * FROM %s" % table_name).fetchall()
        return [dict(row) for row in rows]
    except Exception as e:
        logger.warning("Export: skipping table %s: %s", table_name, e)
        return []


@router.get("")
async def export_all(db=Depends(get_db)):
    """Export all tracker tables as a JSON document.

    Response includes schema_version for forward compatibility.
    Streams the response to avoid loading everything into memory at once.
    """

    def generate():
        yield '{"schema_version":"1.0.0","exported_at":"%s","tables":{' % (
            datetime.utcnow().isoformat() + "Z"
        )
        first = True
        for table in EXPORT_TABLES:
            if not first:
                yield ","
            first = False
            rows = _table_to_dicts(db, table)
            yield '"%s":%s' % (table, json.dumps(rows, default=str))
        yield "}}"

    return StreamingResponse(
        generate(),
        media_type="application/json",
        headers={
            "Content-Disposition": 'attachment; filename="tracker_export_%s.json"'
            % datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        },
    )


@router.get("/stats")
async def export_stats(db=Depends(get_db)):
    """Quick row counts for all exported tables."""
    counts = {}
    for table in EXPORT_TABLES:
        try:
            row = db.execute("SELECT COUNT(*) as n FROM %s" % table).fetchone()
            counts[table] = row["n"]
        except Exception:
            counts[table] = -1
    return {"tables": counts, "total_rows": sum(v for v in counts.values() if v > 0)}
