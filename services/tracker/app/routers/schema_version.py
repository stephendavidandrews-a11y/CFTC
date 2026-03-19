"""
Schema/version handshake endpoints for contract verification.

Allows the AI service and frontend to verify compatibility with the tracker.
"""
from fastapi import APIRouter, Depends
from app.db import get_db
from app.routers.lookups import ENUMS

router = APIRouter(prefix="/schema", tags=["schema"])

# Increment when tracker schema changes in ways that affect AI/frontend contracts
TRACKER_SCHEMA_VERSION = "1.0.0"

# Tables that the AI layer may write to via /tracker/batch
AI_WRITABLE_TABLES = [
    "organizations", "people", "matters", "tasks", "meetings",
    "meeting_participants", "meeting_matters", "documents", "document_files",
    "decisions", "matter_people", "matter_organizations", "matter_updates",
]

# Capabilities supported by this tracker version
CAPABILITIES = [
    "batch_writes",
    "idempotency_keys",
    "ai_context_snapshot",
    "intelligence_data",
    "typed_batch_errors",
    "forward_references",
    "soft_delete",
    "audit_logging",
    "etag_concurrency",
]


@router.get("/version")
async def get_schema_version():
    """Return the current tracker schema version and capabilities."""
    return {
        "schema_version": TRACKER_SCHEMA_VERSION,
        "service": "cftc-tracker",
        "capabilities": CAPABILITIES,
        "ai_writable_tables": AI_WRITABLE_TABLES,
    }


@router.get("/enums")
async def get_schema_enums():
    """Return all enum definitions for contract validation."""
    return ENUMS


@router.get("/capabilities")
async def get_capabilities():
    """Return detailed capability descriptions."""
    return {
        "capabilities": CAPABILITIES,
        "batch_write": {
            "endpoint": "POST /tracker/batch",
            "allowed_tables": AI_WRITABLE_TABLES,
            "supports_idempotency": True,
            "supports_forward_refs": True,
            "supports_soft_delete": True,
            "atomic": True,
        },
        "ai_context": {
            "endpoint": "GET /tracker/ai-context",
            "includes": ["matters", "people", "organizations",
                         "recent_meetings", "standalone_tasks"],
        },
        "intelligence_data": {
            "endpoint": "GET /tracker/ai-context/intelligence-data",
            "includes": ["deadline_warnings", "overdue_tasks", "upcoming_tasks",
                         "missed_followups", "stale_matters", "pending_decisions",
                         "workload"],
        },
    }


@router.get("/tables/{table_name}/columns")
async def get_table_columns(table_name: str, db=Depends(get_db)):
    """Return column definitions for a specific table. Used for contract validation."""
    if table_name not in AI_WRITABLE_TABLES:
        return {"error": f"Table '{table_name}' not in AI-writable tables"}

    rows = db.execute(f"PRAGMA table_info({table_name})").fetchall()
    columns = []
    for row in rows:
        columns.append({
            "name": row["name"],
            "type": row["type"],
            "notnull": bool(row["notnull"]),
            "default_value": row["dflt_value"],
            "pk": bool(row["pk"]),
        })
    return {"table": table_name, "columns": columns}
