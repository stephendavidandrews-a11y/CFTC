"""Health and operational status endpoints."""
import logging
from datetime import datetime
from fastapi import APIRouter, Depends
from app.db import get_db
from app.config import load_policy

logger = logging.getLogger(__name__)
router = APIRouter(tags=["health"])

AI_SERVICE_VERSION = "0.5.0"


@router.get("/health")
async def health(db=Depends(get_db)):
    """Service health and queue stats."""
    # Count communications by status for queue overview
    status_counts = {}
    rows = db.execute("""
        SELECT processing_status, COUNT(*) as cnt
        FROM communications
        GROUP BY processing_status
    """).fetchall()
    for r in rows:
        status_counts[r["processing_status"]] = r["cnt"]

    # Today's LLM spend
    spend_row = db.execute("""
        SELECT COALESCE(SUM(cost_usd), 0.0) as today_spend
        FROM llm_usage
        WHERE created_at >= date('now')
    """).fetchone()
    today_spend = spend_row["today_spend"] if spend_row else 0.0

    policy = load_policy()
    daily_budget = policy.get("model_config", {}).get("daily_budget_usd", 10.0)

    return {
        "status": "ok",
        "service": "cftc-ai",
        "version": AI_SERVICE_VERSION,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "queue": status_counts,
        "spend": {
            "today_usd": round(today_spend, 4),
            "daily_budget_usd": daily_budget,
            "budget_remaining_usd": round(daily_budget - today_spend, 4),
            "paused": today_spend >= daily_budget,
        },
    }
