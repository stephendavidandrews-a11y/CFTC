"""
Batch write endpoint - atomic multi-record writes for the AI layer.

Supports:
- Ordered operations (insert, update, delete)
- Forward references via client_id / $ref
- Full rollback on failure
- Idempotency key support with persisted receipts
- Typed error responses
"""

import hashlib
import json
import logging
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException

from app.audit import log_event
from app.contracts import (
    AI_WRITABLE_ENUM_COLUMNS,
    AI_WRITABLE_TABLES,
    BATCH_DELETE_ALLOWED_TABLES,
    BATCH_SOFT_DELETE_TABLES,
    BATCH_UPSERT_RULES,
    ENUMS,
)
from app.db import get_db
from app.deps import get_write_source

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/batch", tags=["batch"])

ALLOWED_TABLES = set(AI_WRITABLE_TABLES)
DELETE_ALLOWED_TABLES = set(BATCH_DELETE_ALLOWED_TABLES)
SOFT_DELETE_TABLES = dict(BATCH_SOFT_DELETE_TABLES)


def _get_table_columns(db, table):
    """Get column names for a table."""
    rows = db.execute(f"PRAGMA table_info({table})").fetchall()
    return {row["name"] for row in rows}


def _hash_body(body):
    """Deterministic hash of the request body."""
    return hashlib.sha256(
        json.dumps(body, sort_keys=True, default=str).encode()
    ).hexdigest()


def _normalize_upsert_by(upsert_by):
    if upsert_by is None:
        return ()
    if isinstance(upsert_by, str):
        return (upsert_by,)
    if isinstance(upsert_by, (list, tuple)) and all(isinstance(column, str) for column in upsert_by):
        return tuple(upsert_by)
    raise ValueError("upsert_by must be a string or list of strings")


def _validate_meta(meta, op_type: str, table: str, valid_columns: set[str], data: dict, op_index: int):
    if not meta:
        return

    unsupported_keys = set(meta.keys()) - {"expected_updated_at", "upsert_by"}
    if unsupported_keys:
        raise _typed_error(
            400,
            "validation_failure",
            op_index,
            f"Unsupported _meta keys: {sorted(unsupported_keys)}",
        )

    if meta.get("expected_updated_at") and op_type != "update":
        raise _typed_error(
            400,
            "validation_failure",
            op_index,
            "_meta.expected_updated_at is only supported on update operations",
        )

    upsert_by = meta.get("upsert_by")
    if upsert_by is None:
        return

    if op_type != "insert":
        raise _typed_error(
            400,
            "validation_failure",
            op_index,
            "_meta.upsert_by is only supported on insert operations",
        )

    try:
        upsert_columns = _normalize_upsert_by(upsert_by)
    except ValueError as exc:
        raise _typed_error(400, "validation_failure", op_index, str(exc)) from exc

    allowed_upsert = tuple(BATCH_UPSERT_RULES.get(table, ()))
    if upsert_columns != allowed_upsert:
        raise _typed_error(
            400,
            "validation_failure",
            op_index,
            f"_meta.upsert_by is not supported for {table}: {list(upsert_columns)}",
        )

    missing_data = [column for column in upsert_columns if column not in data]
    if missing_data:
        raise _typed_error(
            400,
            "validation_failure",
            op_index,
            f"Upsert columns missing from {table} insert: {missing_data}",
        )

    invalid_upsert_columns = [column for column in upsert_columns if column not in valid_columns]
    if invalid_upsert_columns:
        raise _typed_error(
            400,
            "schema_mismatch",
            op_index,
            f"Invalid upsert columns for {table}: {invalid_upsert_columns}",
        )


def _validate_enum_values(table: str, data: dict, op_index: int):
    for column, enum_name in AI_WRITABLE_ENUM_COLUMNS.get(table, {}).items():
        value = data.get(column)
        if value is None:
            continue
        if value not in ENUMS[enum_name]:
            raise _typed_error(
                400,
                "validation_failure",
                op_index,
                f"Invalid value for {table}.{column}: {value!r}. Allowed values: {ENUMS[enum_name]}",
            )


def _with_source_default(valid_columns: set[str], data: dict, source: str) -> dict:
    data_with_defaults = dict(data)
    if "source" in valid_columns:
        data_with_defaults.setdefault("source", source)
    return data_with_defaults


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
    if source not in ENUMS["source"]:
        raise HTTPException(status_code=400, detail={
            "error_type": "validation_failure",
            "message": f"Invalid source: {source!r}. Allowed values: {ENUMS['source']}",
        })

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
                return json.loads(existing["response_body"])
            raise HTTPException(status_code=409, detail={
                "error_type": "conflict",
                "message": "Batch is still being processed (pending)"
            })

        db.execute("""
            INSERT INTO idempotency_keys (key, method, path, request_hash, status_code, response_body)
            VALUES (?, 'POST', '/tracker/batch', ?, NULL, NULL)
        """, (idempotency_key, body_hash))
        db.commit()

    column_cache = {}
    for i, op in enumerate(operations):
        table = op.get("table")
        op_type = op.get("op")
        data = dict(op.get("data", {}))
        meta = op.get("_meta") or {}

        if table not in ALLOWED_TABLES:
            raise _typed_error(400, "forbidden_table", i,
                               f"Table '{table}' not allowed in batch")
        if op_type not in ("insert", "update", "delete"):
            raise _typed_error(400, "validation_failure", i,
                               "op must be 'insert', 'update', or 'delete'")
        if op_type in ("update", "delete") and not op.get("record_id"):
            raise _typed_error(400, "validation_failure", i,
                               f"'{op_type}' requires record_id")
        if op_type == "delete" and table not in DELETE_ALLOWED_TABLES and table not in SOFT_DELETE_TABLES:
            raise _typed_error(400, "forbidden_table", i,
                               f"Delete not allowed on '{table}'")

        if table not in column_cache:
            column_cache[table] = _get_table_columns(db, table)
        valid_columns = column_cache[table]

        if data:
            invalid = set(data.keys()) - valid_columns - {"id", "created_at", "updated_at"}
            if invalid:
                raise _typed_error(400, "schema_mismatch", i,
                                   f"Invalid columns for {table}: {sorted(invalid)}")
            _validate_enum_values(table, _with_source_default(valid_columns, data, source), i)

        _validate_meta(meta, op_type, table, valid_columns, data, i)

    results = []
    id_map = {}
    current_op = 0

    db.execute("BEGIN IMMEDIATE")

    try:
        for i, op in enumerate(operations):
            current_op = i
            table = op["table"]
            data = dict(op.get("data", {}))
            op_type = op["op"]
            meta = op.get("_meta") or {}
            valid_columns = column_cache[table]

            for key, value in list(data.items()):
                if isinstance(value, str) and value.startswith("$ref:"):
                    ref_key = value[5:]
                    if ref_key not in id_map:
                        raise _typed_error(400, "reference_resolution_failure", i,
                                           f"Unresolved reference '{ref_key}'")
                    data[key] = id_map[ref_key]

            now = datetime.now().isoformat()

            if op_type == "insert":
                upsert_columns = _normalize_upsert_by(meta.get("upsert_by"))
                if upsert_columns:
                    where_clause = " AND ".join(f"{column} = ?" for column in upsert_columns)
                    existing = db.execute(
                        f"SELECT * FROM {table} WHERE {where_clause}",
                        [data[column] for column in upsert_columns],
                    ).fetchone()
                    if existing:
                        record_id = existing["id"]
                        previous_data = dict(existing)
                        update_data = dict(data)
                        if "updated_at" in valid_columns:
                            update_data["updated_at"] = now

                        sets = [f"{key} = ?" for key in update_data]
                        params = list(update_data.values()) + [record_id]
                        db.execute(f"UPDATE {table} SET {', '.join(sets)} WHERE id = ?", params)

                        if op.get("client_id"):
                            id_map[op["client_id"]] = record_id

                        log_event(
                            db,
                            table_name=table,
                            record_id=record_id,
                            action="update",
                            source=source,
                            old_record=existing,
                            new_data=update_data,
                        )

                        results.append({
                            "op": "update",
                            "table": table,
                            "record_id": record_id,
                            "client_id": op.get("client_id"),
                            "previous_data": previous_data,
                        })
                        continue

                record_id = str(uuid.uuid4())
                data["id"] = record_id
                data["created_at"] = now
                if "updated_at" in valid_columns:
                    data["updated_at"] = now
                if "source" in valid_columns:
                    data.setdefault("source", source)

                columns = ", ".join(data.keys())
                placeholders = ", ".join(["?"] * len(data))
                db.execute(
                    f"INSERT INTO {table} ({columns}) VALUES ({placeholders})",
                    list(data.values())
                )

                if op.get("client_id"):
                    id_map[op["client_id"]] = record_id

                log_event(db, table_name=table, record_id=record_id,
                          action="create", source=source, new_data=data)

                results.append({
                    "op": "insert",
                    "table": table,
                    "record_id": record_id,
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

                if "updated_at" in valid_columns:
                    data["updated_at"] = now
                sets = [f"{key} = ?" for key in data]
                params = list(data.values()) + [record_id]

                expected_updated_at = meta.get("expected_updated_at")
                if expected_updated_at:
                    cursor = db.execute(
                        f"UPDATE {table} SET {', '.join(sets)} WHERE id = ? AND updated_at = ?",
                        params + [expected_updated_at],
                    )
                    if cursor.rowcount == 0:
                        raise _typed_error(
                            409,
                            "concurrent_modification",
                            i,
                            f"Record {record_id} in {table} was modified since read "
                            f"(expected updated_at={expected_updated_at})",
                        )
                else:
                    db.execute(f"UPDATE {table} SET {', '.join(sets)} WHERE id = ?", params)

                log_event(db, table_name=table, record_id=record_id,
                          action="update", source=source, old_record=old, new_data=data)

                results.append({
                    "op": "update",
                    "table": table,
                    "record_id": record_id,
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
                        if "updated_at" in valid_columns:
                            db.execute(
                                f"UPDATE {table} SET {field} = ?, updated_at = ? WHERE id = ?",
                                (value, now, record_id),
                            )
                        else:
                            db.execute(
                                f"UPDATE {table} SET {field} = ? WHERE id = ?",
                                (value, record_id),
                            )

                log_event(db, table_name=table, record_id=record_id,
                          action="delete", source=source, old_record=old)

                results.append({
                    "op": "delete",
                    "table": table,
                    "record_id": record_id,
                    "previous_data": previous_data,
                })

        db.commit()
        response = {"success": True, "results": results}

        if idempotency_key:
            db.execute("""
                UPDATE idempotency_keys SET status_code = ?, response_body = ?
                WHERE key = ? AND status_code IS NULL
            """, (200, json.dumps(response, default=str), idempotency_key))
            db.commit()

        return response

    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        logger.error("Batch failed at operation %d: %s", current_op, str(exc))
        raise HTTPException(status_code=500, detail={
            "error_type": "internal_error",
            "message": f"Batch failed at operation {current_op}: {str(exc)}",
            "operation_index": current_op,
        }) from exc


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
