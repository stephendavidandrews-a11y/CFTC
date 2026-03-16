"""
Global exception handlers for the CFTC Pipeline backend.

Catches database integrity errors (SQLite + SQLAlchemy/PostgreSQL) and
unexpected exceptions.  Returns structured JSON responses without leaking
file paths, SQL text, stack traces, or other internals.

Response shape is aligned with the Tracker backend for API consistency:
    {"detail": "...", "errors": [...]}
"""
import logging
import sqlite3

from fastapi import Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# SQLite integrity errors (pipeline + work-management modules)
# ---------------------------------------------------------------------------

async def sqlite_integrity_error_handler(request: Request, exc: sqlite3.IntegrityError):
    """Convert SQLite constraint violations into structured 422 responses."""
    msg = str(exc)

    if "UNIQUE constraint failed" in msg:
        parts = msg.split("UNIQUE constraint failed: ")
        field = parts[1].strip() if len(parts) > 1 else "unknown"
        col = field.split(".")[-1] if "." in field else field
        return JSONResponse(
            status_code=422,
            content={
                "detail": "Duplicate value",
                "errors": [{"field": col, "message": f"A record with this {col} already exists"}],
            },
        )

    if "FOREIGN KEY constraint failed" in msg:
        return JSONResponse(
            status_code=422,
            content={
                "detail": "Invalid reference",
                "errors": [{"field": "unknown", "message": "Referenced record does not exist"}],
            },
        )

    if "NOT NULL constraint failed" in msg:
        parts = msg.split("NOT NULL constraint failed: ")
        field = parts[1].strip() if len(parts) > 1 else "unknown"
        col = field.split(".")[-1] if "." in field else field
        return JSONResponse(
            status_code=422,
            content={
                "detail": "Missing required field",
                "errors": [{"field": col, "message": f"{col} is required"}],
            },
        )

    # Fallback for other SQLite integrity errors
    logger.error(f"SQLite IntegrityError on {request.method} {request.url.path}: {msg}")
    return JSONResponse(
        status_code=422,
        content={
            "detail": "Data constraint violation",
            "errors": [{"field": "unknown", "message": "The submitted data violates a database constraint"}],
        },
    )


# ---------------------------------------------------------------------------
# SQLAlchemy integrity errors (comment system / PostgreSQL)
# ---------------------------------------------------------------------------

async def sqlalchemy_integrity_error_handler(request: Request, exc: Exception):
    """Convert SQLAlchemy IntegrityError into structured 422 responses.

    Accepts generic Exception type so the import is optional — the handler
    is only registered when sqlalchemy is available.
    """
    msg = str(exc)

    # PostgreSQL unique violation
    if "UniqueViolation" in msg or "unique constraint" in msg.lower() or "duplicate key" in msg.lower():
        return JSONResponse(
            status_code=422,
            content={
                "detail": "Duplicate value",
                "errors": [{"field": "unknown", "message": "A record with this value already exists"}],
            },
        )

    # PostgreSQL foreign key violation
    if "ForeignKeyViolation" in msg or "foreign key constraint" in msg.lower():
        return JSONResponse(
            status_code=422,
            content={
                "detail": "Invalid reference",
                "errors": [{"field": "unknown", "message": "Referenced record does not exist"}],
            },
        )

    # PostgreSQL not-null violation
    if "NotNullViolation" in msg or "not-null constraint" in msg.lower() or "null value in column" in msg.lower():
        return JSONResponse(
            status_code=422,
            content={
                "detail": "Missing required field",
                "errors": [{"field": "unknown", "message": "A required field is missing"}],
            },
        )

    # Fallback
    logger.error(f"SQLAlchemy IntegrityError on {request.method} {request.url.path}: {msg}")
    return JSONResponse(
        status_code=422,
        content={
            "detail": "Data constraint violation",
            "errors": [{"field": "unknown", "message": "The submitted data violates a database constraint"}],
        },
    )


# ---------------------------------------------------------------------------
# Generic catch-all (safe 500)
# ---------------------------------------------------------------------------

async def generic_error_handler(request: Request, exc: Exception):
    """Catch-all for unexpected errors.  Logs full detail, returns safe message."""
    logger.error(
        f"Unhandled exception on {request.method} {request.url.path}: {exc}",
        exc_info=True,
    )
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "errors": [],
        },
    )
