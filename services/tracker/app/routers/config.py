"""System configuration endpoints."""

from fastapi import APIRouter, Depends
from app.db import get_db

router = APIRouter(prefix="/config", tags=["config"])


@router.get("")
async def get_config(db=Depends(get_db)):
    """Return all system configuration as a key-value map."""
    rows = db.execute("SELECT key, value FROM system_config").fetchall()
    return {row["key"]: row["value"] for row in rows}
