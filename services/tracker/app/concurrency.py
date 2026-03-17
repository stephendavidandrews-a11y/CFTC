"""Optimistic concurrency control helpers."""
from fastapi import HTTPException, Request


def get_etag(record) -> str:
    """Build ETag from a record's updated_at timestamp."""
    return '"' + record["updated_at"] + '"'


def check_etag(request: Request, current_record):
    """Compare If-Match header against current record's updated_at.
    No-op if If-Match is absent (backward compatible).
    Raises 409 if the record has been modified since the caller last read it.
    Handles weak ETags (W/"...") that nginx may produce when proxying."""
    if_match = request.headers.get("if-match")
    if not if_match:
        return
    # Strip weak-ETag prefix that nginx adds when proxying
    normalized = if_match.removeprefix("W/")
    expected = get_etag(current_record)
    if normalized != expected:
        raise HTTPException(
            status_code=409,
            detail="This record was modified since you last loaded it. "
                   "Please reload the latest version and review before retrying."
        )
