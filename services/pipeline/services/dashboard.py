"""
Dashboard aggregation queries for the executive summary view.
"""

import logging
from datetime import date, timedelta

logger = logging.getLogger(__name__)


def get_executive_summary(conn) -> dict:
    """Build the executive dashboard summary."""
    today = date.today().isoformat()

    # Active counts by module
    active_rm = conn.execute(
        "SELECT COUNT(*) FROM pipeline_items WHERE module = 'rulemaking' AND status = 'active'"
    ).fetchone()[0]

    active_ra = conn.execute(
        "SELECT COUNT(*) FROM pipeline_items WHERE module = 'regulatory_action' AND status = 'active'"
    ).fetchone()[0]

    # Overdue deadlines
    overdue = conn.execute(
        """SELECT COUNT(*) FROM pipeline_deadlines pd
           JOIN pipeline_items pi ON pd.item_id = pi.id
           WHERE pd.status = 'pending' AND pd.due_date < ?
             AND pi.status = 'active'""",
        (today,),
    ).fetchone()[0]

    # Stalled items (no stage change in 30+ days)
    stall_cutoff = (date.today() - timedelta(days=30)).isoformat()
    stalled = conn.execute(
        """SELECT COUNT(*) FROM pipeline_items
           WHERE status = 'active' AND stage_entered_at < ?""",
        (stall_cutoff,),
    ).fetchone()[0]

    # Upcoming deadlines (next 14 days)
    future = (date.today() + timedelta(days=14)).isoformat()
    upcoming_rows = conn.execute(
        """SELECT pd.id, pd.title, pd.due_date, pd.deadline_type,
                  pd.is_hard_deadline, pi.id as item_id,
                  COALESCE(pi.short_title, pi.title) as item_title
           FROM pipeline_deadlines pd
           JOIN pipeline_items pi ON pd.item_id = pi.id
           WHERE pd.status = 'pending' AND pd.due_date >= ? AND pd.due_date <= ?
             AND pi.status = 'active'
           ORDER BY pd.due_date ASC LIMIT 10""",
        (today, future),
    ).fetchall()
    upcoming = [dict(r) for r in upcoming_rows]

    # Team workload
    members = conn.execute(
        "SELECT id, name, role, max_concurrent FROM team_members WHERE is_active = 1"
    ).fetchall()
    team_workload = []
    for m in members:
        active = conn.execute(
            "SELECT COUNT(*) FROM pipeline_items WHERE lead_attorney_id = ? AND status = 'active'",
            (m["id"],),
        ).fetchone()[0]
        team_workload.append({
            "id": m["id"],
            "name": m["name"],
            "role": m["role"],
            "active_items": active,
            "max_concurrent": m["max_concurrent"],
        })

    # Pipeline distribution (rulemaking by stage)
    rm_dist_rows = conn.execute(
        """SELECT current_stage, COUNT(*) as cnt
           FROM pipeline_items
           WHERE module = 'rulemaking' AND status = 'active'
           GROUP BY current_stage"""
    ).fetchall()
    pipeline_dist = {r["current_stage"]: r["cnt"] for r in rm_dist_rows}

    # Reg action distribution (by item_type)
    ra_dist_rows = conn.execute(
        """SELECT item_type, COUNT(*) as cnt
           FROM pipeline_items
           WHERE module = 'regulatory_action' AND status = 'active'
           GROUP BY item_type"""
    ).fetchall()
    ra_dist = {r["item_type"]: r["cnt"] for r in ra_dist_rows}

    # Recent activity (last 10 decision log entries)
    recent_rows = conn.execute(
        """SELECT dl.*, COALESCE(pi.short_title, pi.title) as item_title
           FROM pipeline_decision_log dl
           JOIN pipeline_items pi ON dl.item_id = pi.id
           ORDER BY dl.created_at DESC LIMIT 10"""
    ).fetchall()
    recent = [dict(r) for r in recent_rows]

    # Unread notifications
    unread = conn.execute(
        "SELECT COUNT(*) FROM pipeline_notifications WHERE is_read = 0"
    ).fetchone()[0]

    return {
        "active_rulemakings": active_rm,
        "active_reg_actions": active_ra,
        "total_overdue_deadlines": overdue,
        "total_stalled_items": stalled,
        "upcoming_deadlines": upcoming,
        "team_workload": team_workload,
        "pipeline_distribution": pipeline_dist,
        "reg_action_distribution": ra_dist,
        "recent_activity": recent,
        "unread_notifications": unread,
    }


def get_metrics(conn) -> dict:
    """Pipeline performance metrics."""
    # Average days in each stage for completed items
    stage_velocity = conn.execute(
        """SELECT current_stage, AVG(julianday('now') - julianday(stage_entered_at)) as avg_days,
                  COUNT(*) as item_count
           FROM pipeline_items
           WHERE status = 'active'
           GROUP BY current_stage"""
    ).fetchall()

    # Throughput: items completed per month (last 6 months)
    throughput = conn.execute(
        """SELECT strftime('%Y-%m', updated_at) as month, COUNT(*) as count
           FROM pipeline_items
           WHERE status = 'completed'
           GROUP BY month
           ORDER BY month DESC LIMIT 6"""
    ).fetchall()

    return {
        "stage_velocity": [dict(r) for r in stage_velocity],
        "throughput": [dict(r) for r in throughput],
    }
