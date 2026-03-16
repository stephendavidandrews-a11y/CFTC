"""Idempotency key support for POST create operations."""
import hashlib
import json


def _hash_body(body):
    """Deterministic hash of the request body for comparison."""
    return hashlib.sha256(
        json.dumps(body, sort_keys=True, default=str).encode()
    ).hexdigest()


def claim_idempotency_key(db, key, request_body, path):
    """
    Attempt to claim an idempotency key with first-pass ownership.

    Returns:
    - None: key claimed successfully, caller should proceed with create
    - dict: cached response from previous completed request, return it
    - "conflict": same key used with a different payload -> 409
    - "pending": key is claimed by another in-progress request -> 409 retry
    """
    if not key:
        return None

    body_hash = _hash_body(request_body)

    # Attempt atomic claim via INSERT OR IGNORE
    cursor = db.execute("""
        INSERT OR IGNORE INTO idempotency_keys
            (key, method, path, request_hash, status_code, response_body)
        VALUES (?, 'POST', ?, ?, NULL, NULL)
    """, (key, path, body_hash))

    if cursor.rowcount == 1:
        return None  # we own it

    # Key exists - determine state
    row = db.execute(
        "SELECT request_hash, status_code, response_body FROM idempotency_keys WHERE key = ?",
        (key,)
    ).fetchone()

    if not row:
        return None  # deleted between INSERT and SELECT (edge case)

    if row["request_hash"] != body_hash:
        return "conflict"
    if row["status_code"] is None:
        return "pending"
    return {"status_code": row["status_code"], "body": row["response_body"]}


def finalize_idempotency_key(db, key, status_code, response_body):
    """Finalize a claimed key with the actual response. Called before commit."""
    if not key:
        return
    db.execute("""
        UPDATE idempotency_keys SET status_code = ?, response_body = ?
        WHERE key = ? AND status_code IS NULL
    """, (status_code, json.dumps(response_body, default=str), key))
