"""
Batch write endpoint — atomic multi-record writes for the AI layer.

Supports:
- Ordered operations (insert, update, delete)
- Forward references via client_id / $ref
- Full rollback on failure
- Idempotency key support with persisted receipts
- Typed error responses
"""
import json
import uuid
import hashlib
import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from app.db import get_db
from app.deps import get_write_source
from app.audit import log_event

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/batch", tags=["batch"])

# Tables allowed for batch writes
ALLOWED_TABLES = {
    "organizations", "people", "matters", "tasks", "meetings",
    "meeting_participants", "meeting_matters", "documents", "document_files",
    "decisions", "matter_people", "matter_organizations", "matter_updates",
    "context_notes", "context_note_links", "person_profiles",
}

# Tables allowed for hard delete (junction/child tables)
DELETE_ALLOWED_TABLES = {
    "matter_people", "matter_organizations", "meeting_participants",
    "meeting_matters", "matter_updates", "context_note_links",
}

# Tables where delete is a soft-delete
SOFT_DELETE_TABLES = {
    "organizations": ("is_active", 0),
    "people": ("is_active", 0),
    "matters": ("status", "closed"),
    "tasks": ("status", "deferred"),
    "meetings": None,  # hard delete allowed
    "documents": ("status", "archived"),
    "decisions": ("status", "no longer needed"),
    "context_notes": ("is_active", 0),
}


def _get_table_columns(db, table):
    """Get column names for a table."""
    rows = db.execute(f"PRAGMA table_info({table})").fetchall()
    return {row["name"] for row in rows}


def _hash_body(body):
    """Deterministic hash of the request body."""
    return hashlib.sha256(
        json.dumps(body, sort_keys=True, default=str).encode()
    ).hexdigest()


@router.post("")
async def batch_write(body: dict, db=Depends(get_db),
                      write_source: str = Depends(get_write_source)):
    """
    Execute an ordered array of write operations atomically.

    Body:
    {
        "operations": [...],
        "source": "ai",
        "source_metadata": {"communication_id": "...", "bundle_id": "..."},
        "idempotency_key": "optional-unique-key"
    }
    """
    operations = body.get("operations", [])
    source = body.get("source", write_source)
    source_metadata = body.get("source_metadata", {})
    idempotency_key = body.get("idempotency_key")

    if not operations:
        raise HTTPException(status_code=400, detail={
            "error_type": "validation_failure",
            "message": "No operations provided"
        })

    # --- Idempotency check ---
    if idempotency_key:
        body_hash = _hash_body({"operations": operations, "source": source,
                                "source_metadata": source_metadata})
        existing = db.execute(
            "SELECT request_hash, status_code, response_body FROM idempotency_keys WHERE key = ?",
            (idempotency_key,)
        ).fetchone()

        if existing:
            if existing["request_hash"] != body_hash:
                raise HTTPException(status_code=409, detail={
                    "error_type": "conflict",
                    "message": "Idempotency key used with different payload"
                })
            if existing["status_code"] is not None:
                # Replay: return prior result
                return json.loads(existing["response_body"])
            else:
                raise HTTPException(status_code=409, detail={
                    "error_type": "conflict",
                    "message": "Batch is still being processed (pending)"
                })

        # Claim the key
        db.execute("""
            INSERT INTO idempotency_keys (key, method, path, request_hash, status_code, response_body)
            VALUES (?, 'POST', '/tracker/batch', ?, NULL, NULL)
        """, (idempotency_key, body_hash))
        db.commit()

    # --- Validate all operations before executing ---
    for i, op in enumerate(operations):
        table = op.get("table")
        op_type = op.get("op")

        if table not in ALLOWED_TABLES:
            raise _typed_error(400, "forbidden_table", i,
                               f"Table '{table}' not allowed in batch")
        if op_type not in ("insert", "update", "delete"):
            raise _typed_error(400, "validation_failure", i,
                               f"op must be 'insert', 'update', or 'delete'")
        if op_type in ("update", "delete") and not op.get("record_id"):
            raise _typed_error(400, "validation_failure", i,
                               f"'{op_type}' requires record_id")
        if op_type == "delete" and table not in DELETE_ALLOWED_TABLES and table not in SOFT_DELETE_TABLES:
            raise _typed_error(400, "forbidden_table", i,
                               f"Delete not allowed on '{table}'")

    # --- Execute batch ---
    results = []
    id_map = {}  # client_id -> generated UUID
    _column_cache = {}
    current_op = 0

    try:
        for i, op in enumerate(operations):
            current_op = i
            table = op["table"]
            data = dict(op.get("data", {}))
            meta = op.get("_meta", {})
            op_type = op["op"]

            # Resolve $ref: references
            for key, value in list(data.items()):
                if isinstance(value, str) and value.startswith("$ref:"):
                    ref_key = value[5:]
                    if ref_key not in id_map:
                        raise _typed_error(400, "reference_resolution_failure", i,
                                           f"Unresolved reference '{ref_key}'")
                    data[key] = id_map[ref_key]

            # Validate column names
            if table not in _column_cache:
                _column_cache[table] = _get_table_columns(db, table)
            valid_columns = _column_cache[table]

            if data:
                invalid = set(data.keys()) - valid_columns - {"id"}
                if invalid:
                    raise _typed_error(400, "schema_mismatch", i,
                                       f"Invalid columns for {table}: {sorted(invalid)}")

            now = datetime.now().isoformat()

            if op_type == "insert":
                record_id = str(uuid.uuid4())
                data["id"] = record_id
                if "created_at" in valid_columns:
                    data["created_at"] = now
                if "updated_at" in valid_columns:
                    data["updated_at"] = now
                if "source" in valid_columns:
                    data.setdefault("source", source)

                # Auto-set include_in_team_workload for Direct reports
                if table == "people" and data.get("relationship_category") in ("Direct report", "Indirect report"):
                    data.setdefault("include_in_team_workload", 1)

                columns = ", ".join(data.keys())
                placeholders = ", ".join(["?"] * len(data))

                upsert_col = meta.get("upsert_by")
                if upsert_col and upsert_col in valid_columns and upsert_col in data:
                    # Upsert: check if record exists by the upsert key
                    existing = db.execute(
                        f"SELECT id FROM {table} WHERE {upsert_col} = ?",
                        (data[upsert_col],)
                    ).fetchone()
                    if existing:
                        # Update existing record
                        record_id = existing["id"]
                        upd = {k: v for k, v in data.items()
                               if k not in ("id", upsert_col, "created_at")}
                        upd["updated_at"] = now
                        sets = [f"{k} = ?" for k in upd]
                        db.execute(
                            f"UPDATE {table} SET {', '.join(sets)} WHERE id = ?",
                            list(upd.values()) + [record_id]
                        )
                        data["id"] = record_id

                        log_event(db, table_name=table, record_id=record_id,
                                  action="update", source=source, new_data=upd)

                        results.append({
                            "op": "upsert_update", "table": table,
                            "record_id": record_id,
                            "client_id": op.get("client_id"),
                            "previous_data": None,
                        })
                    else:
                        db.execute(
                            f"INSERT INTO {table} ({columns}) VALUES ({placeholders})",
                            list(data.values())
                        )

                        if op.get("client_id"):
                            id_map[op["client_id"]] = record_id

                        log_event(db, table_name=table, record_id=record_id,
                                  action="create", source=source, new_data=data)

                        results.append({
                            "op": "insert", "table": table, "record_id": record_id,
                            "client_id": op.get("client_id"),
                            "previous_data": None,
                        })
                else:
                    db.execute(
                        f"INSERT INTO {table} ({columns}) VALUES ({placeholders})",
                        list(data.values())
                    )

                    if op.get("client_id"):
                        id_map[op["client_id"]] = record_id

                    log_event(db, table_name=table, record_id=record_id,
                              action="create", source=source, new_data=data)

                    results.append({
                        "op": "insert", "table": table, "record_id": record_id,
                        "client_id": op.get("client_id"),
                        "previous_data": None,
                    })

            elif op_type == "update":
                record_id = op["record_id"]
                old = db.execute(f"SELECT * FROM {table} WHERE id = ?", (record_id,)).fetchone()
                if not old:
                    raise _typed_error(404, "missing_record", i,
                                       f"Record {record_id} not found in {table}")
                previous_data = dict(old)

                data["updated_at"] = now

                # Auto-set include_in_team_workload for Direct reports (only if not explicitly set in payload or DB)
                if table == "people" and data.get("relationship_category") in ("Direct report", "Indirect report"):
                    if "include_in_team_workload" not in data and not previous_data.get("include_in_team_workload"):
                        data["include_in_team_workload"] = 1

                sets = [f"{k} = ?" for k in data]
                params = list(data.values()) + [record_id]
                db.execute(f"UPDATE {table} SET {', '.join(sets)} WHERE id = ?", params)

                log_event(db, table_name=table, record_id=record_id,
                          action="update", source=source, old_record=old, new_data=data)

                results.append({
                    "op": "update", "table": table, "record_id": record_id,
                    "previous_data": previous_data,
                })

            elif op_type == "delete":
                record_id = op["record_id"]
                old = db.execute(f"SELECT * FROM {table} WHERE id = ?", (record_id,)).fetchone()
                if not old:
                    raise _typed_error(404, "missing_record", i,
                                       f"Record {record_id} not found in {table}")
                previous_data = dict(old)

                if table in DELETE_ALLOWED_TABLES:
                    db.execute(f"DELETE FROM {table} WHERE id = ?", (record_id,))
                elif table in SOFT_DELETE_TABLES:
                    soft = SOFT_DELETE_TABLES[table]
                    if soft is None:
                        db.execute(f"DELETE FROM {table} WHERE id = ?", (record_id,))
                    else:
                        field, value = soft
                        db.execute(f"UPDATE {table} SET {field} = ?, updated_at = ? WHERE id = ?",
                                   (value, now, record_id))

                log_event(db, table_name=table, record_id=record_id,
                          action="delete", source=source, old_record=old)

                results.append({
                    "op": "delete", "table": table, "record_id": record_id,
                    "previous_data": previous_data,
                })

        # Build response before commit so idempotency finalization is atomic
        response = {"success": True, "results": results}

        # Finalize idempotency key in same transaction as the operations
        if idempotency_key:
            db.execute("""
                UPDATE idempotency_keys SET status_code = ?, response_body = ?
                WHERE key = ? AND status_code IS NULL
            """, (200, json.dumps(response, default=str), idempotency_key))

        db.commit()
        return response

    except HTTPException:
        db.rollback()
        if idempotency_key:
            _release_idempotency_key(db, idempotency_key)
        raise
    except Exception as e:
        db.rollback()
        if idempotency_key:
            _release_idempotency_key(db, idempotency_key)
        logger.error("Batch failed at operation %d: %s", current_op, str(e))
        raise HTTPException(status_code=500, detail={
            "error_type": "internal_error",
            "message": f"Batch failed at operation {current_op}: {str(e)}",
            "operation_index": current_op,
        })


def _release_idempotency_key(db, key: str):
    """Release a pending idempotency key so retries are not blocked."""
    try:
        db.execute(
            "DELETE FROM idempotency_keys WHERE key = ? AND status_code IS NULL",
            (key,),
        )
        db.commit()
    except Exception:
        pass  # Best effort — do not mask the original error


def _typed_error(status_code: int, error_type: str, operation_index: int,
                 message: str) -> HTTPException:
    """Create a typed error response for batch operations."""
    return HTTPException(
        status_code=status_code,
        detail={
            "error_type": error_type,
            "message": message,
            "operation_index": operation_index,
        }
    )
