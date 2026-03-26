"""Auto-advance audit logging."""

import logging
import uuid
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def log_auto_advance(conn, conversation_id: str, decisions: list[dict]):
    """Log auto-advance decisions for audit trail.

    Args:
        conn: SQLite connection.
        conversation_id: Conversation ID.
        decisions: List of dicts with speaker_label, tracker_person_id, confidence, method.
    """
    now = datetime.now(timezone.utc).isoformat()
    for d in decisions:
        conn.execute(
            """INSERT INTO auto_advance_log
               (id, conversation_id, speaker_label, tracker_person_id, confidence, method, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                str(uuid.uuid4()),
                conversation_id,
                d["speaker_label"],
                d["tracker_person_id"],
                d["confidence"],
                d["method"],
                now,
            ),
        )
    logger.info(
        f"[{conversation_id[:8]}] Auto-advance logged: {len(decisions)} speakers"
    )
