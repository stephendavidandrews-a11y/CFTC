"""Shared request-scoped dependencies for tracker routers."""

from fastapi import Request

from app.contracts import ENUMS


_SOURCE_ALIASES = {
    "human": "manual",
    "fr_pipeline": "federal_register",
    "test": "manual",
}
_VALID_WRITE_SOURCES = set(ENUMS["source"])



def get_write_source(request: Request) -> str:
    """Extract and normalize write source from X-Write-Source."""
    raw = (request.headers.get("x-write-source") or "").strip().lower()
    if not raw:
        return "manual"
    normalized = _SOURCE_ALIASES.get(raw, raw)
    return normalized if normalized in _VALID_WRITE_SOURCES else "manual"
