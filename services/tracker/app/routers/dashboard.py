"""Dashboard endpoints — aggregated views for the tracker homepage."""

from fastapi import APIRouter, Depends
from app.db import get_db

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("")
async def get_dashboard(db=Depends(get_db)):
    """Return dashboard summary data."""
    # Counts by status
    matters_by_status = {}
    for row in db.execute(
        "SELECT status, COUNT(*) as count FROM matters WHERE status IN ('active', 'paused') GROUP BY status"
    ):
        matters_by_status[row["status"]] = row["count"]

    # Counts by priority
    matters_by_priority = {}
    for row in db.execute(
        "SELECT priority, COUNT(*) as count FROM matters WHERE status IN ('active', 'paused') GROUP BY priority"
    ):
        matters_by_priority[row["priority"]] = row["count"]

    # Total open matters
    total_open = db.execute(
        "SELECT COUNT(*) as c FROM matters WHERE status IN ('active', 'paused')"
    ).fetchone()["c"]

    # Total open tasks
    total_tasks = db.execute(
        "SELECT COUNT(*) as c FROM tasks WHERE status NOT IN ('done', 'deferred')"
    ).fetchone()["c"]

    # Overdue tasks
    overdue_tasks = db.execute(
        "SELECT COUNT(*) as c FROM tasks WHERE status NOT IN ('done', 'deferred') AND due_date < date('now') AND due_date IS NOT NULL"
    ).fetchone()["c"]

    # Upcoming deadlines: include overdue (past 90 days) and future (next 90 days)
    raw_deadlines = [
        dict(row)
        for row in db.execute("""
        SELECT m.id, m.title, m.matter_type, m.work_deadline,
               m.external_deadline, m.assigned_to_person_id, m.priority, m.status,
               p.full_name as owner_name
        FROM matters m
        LEFT JOIN people p ON m.assigned_to_person_id = p.id
        WHERE m.status IN ('active', 'paused')
        AND (
            m.work_deadline IS NOT NULL
            OR m.external_deadline IS NOT NULL
        )
        ORDER BY COALESCE(m.external_deadline, m.work_deadline)
        LIMIT 30
    """)
    ]

    # Flatten into one row per deadline type for the frontend
    from datetime import date as date_type

    upcoming_deadlines = []
    for row in raw_deadlines:
        for dtype, field in [
            ("External Deadline", "external_deadline"),
            ("Work Deadline", "work_deadline"),
        ]:
            val = row.get(field)
            if not val:
                continue
            try:
                d_date = date_type.fromisoformat(str(val)[:10])
                days_until = (d_date - date_type.today()).days
            except (ValueError, TypeError):
                continue
            upcoming_deadlines.append(
                {
                    "matter_id": row["id"],
                    "matter_title": row["title"],
                    "deadline_type": dtype,
                    "date": str(val)[:10],
                    "days_until": days_until,
                    "priority": row["priority"],
                    "status": row["status"],
                    "owner_name": row["owner_name"],
                }
            )

    # Sort by date, overdue first
    upcoming_deadlines.sort(key=lambda x: x["date"])
    upcoming_deadlines = upcoming_deadlines[:15]

    # Recent matters (last 5 updated)
    recent_matters = [
        dict(row)
        for row in db.execute("""
        SELECT m.id, m.title, m.matter_type, m.status, m.priority, m.updated_at,
               m.assigned_to_person_id, p.full_name as owner_name
        FROM matters m
        LEFT JOIN people p ON m.assigned_to_person_id = p.id
        WHERE m.status IN ('active', 'paused')
        ORDER BY m.updated_at DESC
        LIMIT 10
    """)
    ]

    # Recent updates
    recent_updates = [
        dict(row)
        for row in db.execute("""
        SELECT mu.id, mu.summary, mu.update_type, mu.created_at,
               m.title as matter_title, m.id as matter_id
        FROM matter_updates mu
        JOIN matters m ON mu.matter_id = m.id
        ORDER BY mu.created_at DESC
        LIMIT 10
    """)
    ]

    # Tasks due soon (next 7 days)
    tasks_due_soon = [
        dict(row)
        for row in db.execute("""
        SELECT t.id, t.title, t.status, t.due_date, t.priority,
               t.assigned_to_person_id, p.full_name as owner_name,
               m.title as matter_title, m.id as matter_id
        FROM tasks t
        LEFT JOIN people p ON t.assigned_to_person_id = p.id
        LEFT JOIN matters m ON t.matter_id = m.id
        WHERE t.status NOT IN ('done', 'deferred')
        AND t.due_date IS NOT NULL
        AND t.due_date <= date('now', '+7 days')
        ORDER BY t.due_date
        LIMIT 10
    """)
    ]

    # Pending decisions — from decisions table only
    pending_decisions = [
        dict(row)
        for row in db.execute("""
        SELECT d.id, d.title, d.status, d.decision_due_date, d.decision_type,
               m.title as matter_title, m.id as matter_id,
               p.full_name as owner_name
        FROM decisions d
        JOIN matters m ON d.matter_id = m.id
        LEFT JOIN people p ON d.decision_assigned_to_person_id = p.id
        WHERE d.status IN ('pending', 'under consideration')
        ORDER BY d.decision_due_date
        LIMIT 15
    """)
    ]

    # Comment periods closing soon (rulemakings)
    comment_periods = [
        dict(row)
        for row in db.execute("""
        SELECT m.id, m.title, m.matter_type, m.priority, m.status,
               mr.current_comment_period_closes,
               mr.workflow_status,
               CASE
                   WHEN mr.current_comment_period_closes >= date('now') THEN 'open'
                   ELSE 'closed'
               END AS comment_period_status,
               julianday(mr.current_comment_period_closes) - julianday('now') AS days_until_close,
               p.full_name as owner_name
        FROM matters m
        JOIN matter_rulemaking mr ON m.id = mr.matter_id
        LEFT JOIN people p ON m.assigned_to_person_id = p.id
        WHERE m.status IN ('active', 'paused')
        AND mr.current_comment_period_closes IS NOT NULL
        ORDER BY mr.current_comment_period_closes
        LIMIT 15
    """)
    ]

    # Blocked matters
    blocked_matters = [
        dict(row)
        for row in db.execute("""
        SELECT m.id, m.title, m.matter_type, m.priority, m.blocker,
               m.assigned_to_person_id, p.full_name as owner_name
        FROM matters m
        LEFT JOIN people p ON m.assigned_to_person_id = p.id
        WHERE m.status = 'active'
        AND m.blocker IS NOT NULL AND m.blocker != ''
        ORDER BY m.priority, m.updated_at DESC
        LIMIT 15
    """)
    ]

    return {
        "total_open_matters": total_open,
        "total_open_tasks": total_tasks,
        "overdue_tasks": overdue_tasks,
        "matters_by_status": matters_by_status,
        "matters_by_priority": matters_by_priority,
        "upcoming_deadlines": upcoming_deadlines,
        "recent_matters": recent_matters,
        "recent_updates": recent_updates,
        "tasks_due_soon": tasks_due_soon,
        "pending_decisions": pending_decisions,
        "comment_periods": comment_periods,
        "blocked_matters": blocked_matters,
    }


@router.get("/stats")
async def get_stats(db=Depends(get_db)):
    """Return table row counts for all tables."""
    tables = [
        "organizations",
        "people",
        "matters",
        "tasks",
        "meetings",
        "documents",
        "decisions",
        "matter_people",
        "matter_organizations",
        "meeting_participants",
        "meeting_matters",
        "matter_updates",
        "task_updates",
        "document_files",
        "tags",
        "matter_tags",
        "rulemaking_publication_status",
        "rulemaking_comment_periods",
        "rulemaking_cba_tracking",
        "system_events",
        "sync_state",
    ]
    counts = {}
    for table in tables:
        try:
            row = db.execute(f"SELECT COUNT(*) as c FROM {table}").fetchone()
            counts[table] = row["c"]
        except Exception:
            counts[table] = -1
    return counts
