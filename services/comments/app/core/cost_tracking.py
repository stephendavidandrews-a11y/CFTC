"""AI cost tracking and spending caps for Claude API calls.

Logs every API call with token counts and estimated cost.
Enforces per-docket and daily spending limits.
"""

import logging
import sqlite3
import time
from datetime import date
from pathlib import Path
from threading import Lock

logger = logging.getLogger(__name__)

# Cost per 1M tokens (March 2026 pricing)
MODEL_COSTS = {
    "claude-opus-4-20250514": {"input": 15.0, "output": 75.0},
    "claude-sonnet-4-20250514": {"input": 3.0, "output": 15.0},
    # Fallback for unknown models
    "default": {"input": 3.0, "output": 15.0},
}

# Spending caps (configurable via environment, these are defaults)
DAILY_CAP_USD = float(__import__("os").environ.get("AI_DAILY_CAP_USD", "25.0"))
PER_DOCKET_CAP_USD = float(__import__("os").environ.get("AI_PER_DOCKET_CAP_USD", "50.0"))

_db_lock = Lock()
_DB_PATH = Path(__file__).parent.parent.parent / "data" / "ai_cost_log.db"


def _get_cost_db():
    """Get or create the cost tracking database."""
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_DB_PATH))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS ai_cost_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL DEFAULT (datetime('now')),
            model TEXT NOT NULL,
            docket_number TEXT,
            operation TEXT NOT NULL,
            input_tokens INTEGER NOT NULL,
            output_tokens INTEGER NOT NULL,
            estimated_cost_usd REAL NOT NULL
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_cost_date
        ON ai_cost_log(timestamp)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_cost_docket
        ON ai_cost_log(docket_number)
    """)
    conn.commit()
    return conn


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Estimate USD cost for a Claude API call."""
    costs = MODEL_COSTS.get(model, MODEL_COSTS["default"])
    return (input_tokens * costs["input"] + output_tokens * costs["output"]) / 1_000_000


def log_api_call(
    model: str,
    input_tokens: int,
    output_tokens: int,
    operation: str,
    docket_number: str | None = None,
) -> float:
    """Log an API call and return estimated cost in USD."""
    cost = estimate_cost(model, input_tokens, output_tokens)
    with _db_lock:
        conn = _get_cost_db()
        try:
            conn.execute(
                """INSERT INTO ai_cost_log
                   (model, docket_number, operation, input_tokens, output_tokens, estimated_cost_usd)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (model, docket_number, operation, input_tokens, output_tokens, cost),
            )
            conn.commit()
        finally:
            conn.close()

    logger.info(
        "AI cost: $%.4f (%s, %d in / %d out) for %s [%s]",
        cost, model, input_tokens, output_tokens, operation, docket_number or "n/a",
    )
    return cost


def check_daily_cap() -> tuple[bool, float, float]:
    """Check if daily spending cap is exceeded.

    Returns (allowed, spent_today, cap).
    """
    today = date.today().isoformat()
    with _db_lock:
        conn = _get_cost_db()
        try:
            row = conn.execute(
                "SELECT COALESCE(SUM(estimated_cost_usd), 0) FROM ai_cost_log WHERE timestamp >= ?",
                (today,),
            ).fetchone()
            spent = row[0] if row else 0.0
        finally:
            conn.close()

    return spent < DAILY_CAP_USD, spent, DAILY_CAP_USD


def check_docket_cap(docket_number: str) -> tuple[bool, float, float]:
    """Check if per-docket spending cap is exceeded.

    Returns (allowed, spent_on_docket, cap).
    """
    with _db_lock:
        conn = _get_cost_db()
        try:
            row = conn.execute(
                "SELECT COALESCE(SUM(estimated_cost_usd), 0) FROM ai_cost_log WHERE docket_number = ?",
                (docket_number,),
            ).fetchone()
            spent = row[0] if row else 0.0
        finally:
            conn.close()

    return spent < PER_DOCKET_CAP_USD, spent, PER_DOCKET_CAP_USD


def get_usage_stats() -> dict:
    """Get cost tracking statistics."""
    today = date.today().isoformat()
    with _db_lock:
        conn = _get_cost_db()
        try:
            daily = conn.execute(
                "SELECT COALESCE(SUM(estimated_cost_usd), 0), COUNT(*) FROM ai_cost_log WHERE timestamp >= ?",
                (today,),
            ).fetchone()
            total = conn.execute(
                "SELECT COALESCE(SUM(estimated_cost_usd), 0), COUNT(*) FROM ai_cost_log",
            ).fetchone()
            by_docket = conn.execute(
                """SELECT docket_number, SUM(estimated_cost_usd), COUNT(*)
                   FROM ai_cost_log
                   WHERE docket_number IS NOT NULL
                   GROUP BY docket_number
                   ORDER BY SUM(estimated_cost_usd) DESC
                   LIMIT 10""",
            ).fetchall()
        finally:
            conn.close()

    return {
        "daily_spent_usd": round(daily[0], 4),
        "daily_calls": daily[1],
        "daily_cap_usd": DAILY_CAP_USD,
        "daily_remaining_usd": round(max(0, DAILY_CAP_USD - daily[0]), 4),
        "total_spent_usd": round(total[0], 4),
        "total_calls": total[1],
        "top_dockets": [
            {"docket": row[0], "spent_usd": round(row[1], 4), "calls": row[2]}
            for row in by_docket
        ],
    }
