"""Lookup/enum endpoints for the tracker."""

from fastapi import APIRouter, HTTPException

from app.contracts import ENUMS, ENUM_ALIASES

router = APIRouter(prefix="/lookups", tags=["lookups"])


@router.get("/enums")
async def get_all_enums():
    """Return all enum values. Used by Sauron and other integrations for validation."""
    return ENUMS


@router.get("/enums/{enum_name}")
async def get_enum(enum_name: str):
    """Return values for a specific enum."""
    resolved = ENUM_ALIASES.get(enum_name, enum_name)
    if resolved not in ENUMS:
        raise HTTPException(status_code=404, detail=f"Unknown enum: {enum_name}")
    return ENUMS[resolved]
