"""
Notification service: generation, retrieval, and management.
"""

import logging
from datetime import date

logger = logging.getLogger(__name__)


def create_notification(
    conn, recipient_id: int = None, item_id: int = None,
    notification_type: str = "info", title: str = "",
    message: str = None, severity: str = "info",
) -> dict:
    """Create a notification."""
    cursor = conn.execute(
        """INSERT INTO pipeline_notifications
           (recipient_id, item_id, notification_type, title, message, severity)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (recipient_id, item_id, notification_type, title, message, severity),
    )
    conn.commit()
    row = conn.execute(
        "SELECT * FROM pipeline_notifications WHERE id = ?", (cursor.lastrowid,)
    ).fetchone()
    return _enrich_notification(conn, row)


def _enrich_notification(conn, row):
    """Add item_title to notification."""
    n = dict(row)
    n["is_read"] = bool(n.get("is_read", 0))
    n["item_title"] = None
    if n.get("item_id"):
        item = conn.execute(
            "SELECT short_title, title FROM pipeline_items WHERE id = ?",
            (n["item_id"],),
        ).fetchone()
        if item:
            n["item_title"] = item["short_title"] or item["title"]
    return n


def list_notifications(conn, recipient_id=None, unread_only=False, limit=50):
    """List notifications with optional filters."""
    conditions = []
    params = []
    if recipient_id:
        conditions.append("recipient_id = ?")
        params.append(recipient_id)
    if unread_only:
        conditions.append("is_read = 0")

    where = ""
    if conditions:
        where = "WHERE " + " AND ".join(conditions)

    rows = conn.execute(
        f"""SELECT * FROM pipeline_notifications
            {where} ORDER BY created_at DESC LIMIT ?""",
        params + [limit],
    ).fetchall()
    return [_enrich_notification(conn, r) for r in rows]


def mark_read(conn, notification_id: int) -> dict | None:
    """Mark a notification as read."""
    conn.execute(
        "UPDATE pipeline_notifications SET is_read = 1 WHERE id = ?",
        (notification_id,),
    )
    conn.commit()
    row = conn.execute(
        "SELECT * FROM pipeline_notifications WHERE id = ?", (notification_id,)
    ).fetchone()
    if not row:
        return None
    return _enrich_notification(conn, row)


def count_unread(conn, recipient_id=None) -> int:
    """Count unread notifications."""
    if recipient_id:
        return conn.execute(
            "SELECT COUNT(*) FROM pipeline_notifications WHERE is_read = 0 AND recipient_id = ?",
            (recipient_id,),
        ).fetchone()[0]
    return conn.execute(
        "SELECT COUNT(*) FROM pipeline_notifications WHERE is_read = 0"
    ).fetchone()[0]


def generate_overdue_notifications(conn) -> int:
    """Check for overdue deadlines and create notifications."""
    today = date.today().isoformat()
    overdue = conn.execute(
        """SELECT pd.*, pi.title as item_title, pi.lead_attorney_id
           FROM pipeline_deadlines pd
           JOIN pipeline_items pi ON pd.item_id = pi.id
           WHERE pd.status = 'pending' AND pd.due_date < ?
             AND pi.status = 'active'""",
        (today,),
    ).fetchall()

    created = 0
    for dl in overdue:
        # Check if already notified today
        existing = conn.execute(
            """SELECT id FROM pipeline_notifications
               WHERE item_id = ? AND notification_type = 'deadline_overdue'
                 AND date(created_at) = date('now')""",
            (dl["item_id"],),
        ).fetchone()
        if existing:
            continue

        create_notification(
            conn,
            recipient_id=dl["lead_attorney_id"],
            item_id=dl["item_id"],
            notification_type="deadline_overdue",
            title=f"OVERDUE: {dl['title']}",
            message=f"Deadline was {dl['due_date']} for {dl['item_title']}",
            severity="critical",
        )
        created += 1

    return created
