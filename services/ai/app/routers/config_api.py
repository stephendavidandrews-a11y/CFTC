"""Configuration API — read/update ai_policy.json with audit logging."""
import logging
from fastapi import APIRouter, Depends, HTTPException
from app.db import get_db
from app.config import load_policy, update_policy_section

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/config", tags=["config"])


@router.get("")
async def get_config():
    """Return the full current AI policy configuration."""
    return load_policy()


@router.put("/{section}")
async def update_config_section(section: str, body: dict, db=Depends(get_db)):
    """Update a single section of the AI policy.
    Writes to disk, logs to config_audit_log, takes effect on next pipeline run.
    """
    try:
        policy = update_policy_section(section, body, db=db)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"status": "saved", "section": section, "config": policy}


@router.get("/audit")
async def get_config_audit(db=Depends(get_db), limit: int = 100):
    """Return recent config change history."""
    rows = db.execute("""
        SELECT id, section, field, old_value, new_value, created_at
        FROM config_audit_log
        ORDER BY created_at DESC
        LIMIT ?
    """, (limit,)).fetchall()
    return [dict(r) for r in rows]


@router.get("/stats")
async def get_config_stats(db=Depends(get_db)):
    """Return acceptance/edit rates per action type (rolling 90 days).
    Used by the trust configuration UI to suggest auto-commit readiness.
    """
    rows = db.execute("""
        SELECT
            rbi.item_type,
            COUNT(*) as total,
            SUM(CASE WHEN rbi.status IN ('approved', 'auto_committed') THEN 1 ELSE 0 END) as approved,
            SUM(CASE WHEN rbi.status = 'rejected' THEN 1 ELSE 0 END) as rejected,
            SUM(CASE WHEN rbi.status = 'edited' THEN 1 ELSE 0 END) as edited
        FROM review_bundle_items rbi
        JOIN review_bundles rb ON rbi.bundle_id = rb.id
        JOIN communications c ON rb.communication_id = c.id
        WHERE c.created_at >= datetime('now', '-90 days')
        GROUP BY rbi.item_type
    """).fetchall()

    stats = {}
    for r in rows:
        total = r["total"]
        approved = r["approved"]
        edited = r["edited"]
        stats[r["item_type"]] = {
            "total": total,
            "approved": approved,
            "rejected": r["rejected"],
            "edited": edited,
            "acceptance_rate": round(approved / total, 3) if total > 0 else None,
            "edit_rate": round(edited / max(approved, 1), 3) if approved > 0 else None,
        }
    return stats
