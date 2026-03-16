"""
Composite priority calculator.

Weights from config.py:
  eo_alignment: 0.20, chairman_priority: 0.25, pwg_deadline: 0.15,
  stage1_score: 0.15, deadline_proximity: 0.15,
  congressional_interest: 0.05, comment_volume: 0.05
"""

import logging
from datetime import date, timedelta

from app.pipeline.config import PRIORITY_WEIGHTS

logger = logging.getLogger(__name__)


def _normalize_0_10(value, max_val=10.0):
    """Clamp a value to 0-10 range."""
    if value is None:
        return 0.0
    return max(0.0, min(10.0, float(value)))


def compute_priority(conn, item_id: int) -> float:
    """
    Compute composite priority for an item from stored signals.
    Returns 0-100 score. Updates the pipeline_items row.
    """
    item = conn.execute(
        "SELECT * FROM pipeline_items WHERE id = ?", (item_id,)
    ).fetchone()
    if not item:
        return 0.0

    # If manual override, use it directly
    if item["priority_override"] is not None:
        _update_label(conn, item_id, item["priority_override"])
        return item["priority_override"]

    # Gather stored signals
    signals = {}
    rows = conn.execute(
        "SELECT signal_type, signal_value FROM pipeline_priority_signals WHERE item_id = ?",
        (item_id,),
    ).fetchall()
    for r in rows:
        signals[r["signal_type"]] = r["signal_value"]

    # Chairman priority signal (binary: 10 or 0)
    if item["chairman_priority"]:
        signals.setdefault("chairman_priority", 10.0)

    # Deadline proximity signal (auto-compute from nearest deadline)
    nearest = conn.execute(
        """SELECT due_date FROM pipeline_deadlines
           WHERE item_id = ? AND status = 'pending'
           ORDER BY due_date ASC LIMIT 1""",
        (item_id,),
    ).fetchone()
    if nearest:
        try:
            due = date.fromisoformat(nearest["due_date"])
            days_left = (due - date.today()).days
            if days_left <= 0:
                proximity = 10.0
            elif days_left <= 7:
                proximity = 9.0
            elif days_left <= 14:
                proximity = 7.0
            elif days_left <= 30:
                proximity = 5.0
            elif days_left <= 60:
                proximity = 3.0
            else:
                proximity = 1.0
            signals["deadline_proximity"] = proximity
        except (ValueError, TypeError):
            pass

    # Compute weighted sum → 0-100
    composite = 0.0
    for signal_type, weight in PRIORITY_WEIGHTS.items():
        val = _normalize_0_10(signals.get(signal_type, 0.0))
        composite += val * weight

    # Scale to 0-100
    composite = round(composite * 10, 1)

    _update_label(conn, item_id, composite)

    conn.execute(
        "UPDATE pipeline_items SET priority_composite = ?, updated_at = datetime('now') WHERE id = ?",
        (composite, item_id),
    )
    conn.commit()
    return composite


def _update_label(conn, item_id: int, score: float):
    """Set priority_label based on score thresholds."""
    if score >= 75:
        label = "critical"
    elif score >= 50:
        label = "high"
    elif score >= 25:
        label = "medium"
    else:
        label = "low"

    conn.execute(
        "UPDATE pipeline_items SET priority_label = ? WHERE id = ?",
        (label, item_id),
    )


def upsert_signal(
    conn, item_id: int, signal_type: str, signal_value: float,
    source: str = None, detail: str = None,
) -> dict:
    """Insert or update a priority signal for an item."""
    conn.execute(
        """INSERT INTO pipeline_priority_signals
           (item_id, signal_type, signal_value, signal_source, signal_detail, computed_at)
           VALUES (?, ?, ?, ?, ?, datetime('now'))
           ON CONFLICT(item_id, signal_type) DO UPDATE SET
             signal_value = excluded.signal_value,
             signal_source = excluded.signal_source,
             signal_detail = excluded.signal_detail,
             computed_at = excluded.computed_at""",
        (item_id, signal_type, signal_value, source, detail),
    )
    conn.commit()

    # Recompute priority
    new_score = compute_priority(conn, item_id)

    return {
        "item_id": item_id,
        "signal_type": signal_type,
        "signal_value": signal_value,
        "new_composite": new_score,
    }


def recompute_all(conn) -> int:
    """Recompute priority for all active items."""
    rows = conn.execute(
        "SELECT id FROM pipeline_items WHERE status = 'active'"
    ).fetchall()
    count = 0
    for r in rows:
        compute_priority(conn, r["id"])
        count += 1
    return count
