"""
AI context snapshot endpoint — provides extraction context to the AI service.

Read-only, purpose-built endpoint. Consumed by services/ai/ before each
Sonnet extraction call. Response is stored in ai_extractions.tracker_context_snapshot.

Excluded by design (privacy/security):
- people.email, phone, assistant_name, assistant_contact
- people.working_style_notes, personality (NEVER sent to AI)
- people.last_interaction_date, next_interaction_* fields
- people.manager_person_id, include_in_team_workload
- All source/source_id/external_refs fields
"""
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, Query
from app.db import get_db

router = APIRouter(prefix="/ai-context", tags=["ai-context"])


@router.get("")
async def get_ai_context(
    db=Depends(get_db),
    include_matters: bool = Query(True),
    include_people: bool = Query(True),
    include_organizations: bool = Query(True),
    include_recent_meetings: bool = Query(True),
    include_standalone_tasks: bool = Query(True),
    meetings_days: int = Query(30),
):
    """Return the full tracker context snapshot for AI extraction."""
    result = {"generated_at": datetime.now().isoformat()}

    if include_matters:
        result["matters"] = _get_matters_with_nested(db)
    if include_people:
        result["people"] = _get_active_people(db)
    if include_organizations:
        result["organizations"] = _get_active_organizations(db)
    if include_recent_meetings:
        result["recent_meetings"] = _get_recent_meetings(db, meetings_days)
    if include_standalone_tasks:
        result["standalone_tasks"] = _get_standalone_tasks(db)

    return result


@router.get("/intelligence-data")
async def get_intelligence_data(
    db=Depends(get_db),
    deadline_warning_days: int = Query(7),
    task_upcoming_days: int = Query(7),
    critical_stale_days: int = Query(5),
    important_stale_days: int = Query(10),
    strategic_stale_days: int = Query(21),
    monitoring_stale_days: int = Query(30),
    workload_multiplier: float = Query(2.0),
):
    """
    Return intelligence data for daily digest / weekly brief generation.
    All threshold parameters come from ai_policy.json and are passed by the AI service.
    """
    deadline_warnings = [dict(row) for row in db.execute("""
        SELECT m.id, m.title, m.priority, m.status,
               m.work_deadline, m.decision_deadline, m.external_deadline,
               p.full_name as owner_name
        FROM matters m
        LEFT JOIN people p ON m.assigned_to_person_id = p.id
        WHERE m.status != 'closed'
        AND (
            m.work_deadline BETWEEN date('now') AND date('now', '+' || ? || ' days')
            OR m.decision_deadline BETWEEN date('now') AND date('now', '+' || ? || ' days')
            OR m.external_deadline BETWEEN date('now') AND date('now', '+' || ? || ' days')
            OR m.work_deadline < date('now')
            OR m.decision_deadline < date('now')
            OR m.external_deadline < date('now')
        )
    """, (deadline_warning_days, deadline_warning_days, deadline_warning_days))]

    overdue_tasks = [dict(row) for row in db.execute("""
        SELECT t.id, t.title, t.due_date, t.status, t.priority,
               m.title as matter_title, m.id as matter_id,
               p.full_name as owner_name
        FROM tasks t
        LEFT JOIN matters m ON t.matter_id = m.id
        LEFT JOIN people p ON t.assigned_to_person_id = p.id
        WHERE t.status NOT IN ('done', 'deferred')
        AND t.due_date < date('now')
        ORDER BY t.due_date
    """)]

    upcoming_tasks = [dict(row) for row in db.execute("""
        SELECT t.id, t.title, t.due_date, t.status, t.priority, t.expected_output,
               m.title as matter_title, p.full_name as owner_name
        FROM tasks t
        LEFT JOIN matters m ON t.matter_id = m.id
        LEFT JOIN people p ON t.assigned_to_person_id = p.id
        WHERE t.status NOT IN ('done', 'deferred')
        AND t.due_date BETWEEN date('now') AND date('now', '+' || ? || ' days')
        ORDER BY t.due_date
    """, (task_upcoming_days,))]

    missed_followups = [dict(row) for row in db.execute("""
        SELECT p.id, p.full_name, p.title, p.next_interaction_needed_date,
               p.next_interaction_type, p.next_interaction_purpose,
               o.name as org_name
        FROM people p
        LEFT JOIN organizations o ON p.organization_id = o.id
        WHERE p.next_interaction_needed_date <= date('now')
        AND p.is_active = 1
        ORDER BY p.next_interaction_needed_date
    """)]

    stale_matters = [dict(row) for row in db.execute("""
        SELECT m.id, m.title, m.priority, m.status,
               m.last_material_update_at,
               julianday('now') - julianday(m.last_material_update_at) as days_since_update,
               p.full_name as owner_name
        FROM matters m
        LEFT JOIN people p ON m.assigned_to_person_id = p.id
        WHERE m.status != 'closed'
        AND m.last_material_update_at IS NOT NULL
        AND (
            (m.priority = 'critical this week' AND julianday('now') - julianday(m.last_material_update_at) > ?)
            OR (m.priority = 'important this month' AND julianday('now') - julianday(m.last_material_update_at) > ?)
            OR (m.priority = 'strategic / slow burn' AND julianday('now') - julianday(m.last_material_update_at) > ?)
            OR (m.priority = 'monitoring only' AND julianday('now') - julianday(m.last_material_update_at) > ?)
        )
        AND m.is_stale_override = 0
    """, (critical_stale_days, important_stale_days, strategic_stale_days, monitoring_stale_days))]

    pending_decisions = [dict(row) for row in db.execute("""
        SELECT d.id, d.title, d.decision_type, d.decision_due_date,
               m.title as matter_title, m.id as matter_id,
               p.full_name as decision_owner_name
        FROM decisions d
        JOIN matters m ON d.matter_id = m.id
        LEFT JOIN people p ON d.decision_assigned_to_person_id = p.id
        WHERE d.status IN ('pending', 'under consideration')
        ORDER BY d.decision_due_date
    """)]

    workload = [dict(row) for row in db.execute("""
        SELECT p.id, p.full_name,
               COUNT(t.id) as open_task_count,
               COUNT(DISTINCT t.matter_id) as matter_count
        FROM people p
        JOIN tasks t ON t.assigned_to_person_id = p.id
        WHERE t.status NOT IN ('done', 'deferred')
        AND p.include_in_team_workload = 1
        GROUP BY p.id
        ORDER BY open_task_count DESC
    """)]

    return {
        "generated_at": datetime.now().isoformat(),
        "deadline_warnings": deadline_warnings,
        "overdue_tasks": overdue_tasks,
        "upcoming_tasks": upcoming_tasks,
        "missed_followups": missed_followups,
        "stale_matters": stale_matters,
        "pending_decisions": pending_decisions,
        "workload": workload,
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_matters_with_nested(db):
    """All open matters with stakeholders, recent updates, open tasks, open decisions."""
    matters = []
    rows = db.execute("""
        SELECT m.id, m.matter_number, m.title, m.matter_type, m.description,
               m.problem_statement, m.why_it_matters, m.status, m.priority,
               m.sensitivity, m.risk_level, m.boss_involvement_level,
               m.assigned_to_person_id, p_owner.full_name as owner_name,
               m.supervisor_person_id, p_sup.full_name as supervisor_name,
               m.next_step_assigned_to_person_id, p_ns.full_name as next_step_owner_name,
               m.next_step, m.pending_decision,
               m.requesting_organization_id, o_req.name as requesting_org_name,
               m.client_organization_id, o_cli.name as client_org_name,
               m.reviewing_organization_id, o_rev.name as reviewing_org_name,
               m.lead_external_org_id, o_lead.name as lead_external_org_name,
               m.work_deadline, m.decision_deadline, m.external_deadline,
               m.revisit_date, m.opened_date, m.last_material_update_at,
               m.rin, m.regulatory_stage, m.docket_number
        FROM matters m
        LEFT JOIN people p_owner ON m.assigned_to_person_id = p_owner.id
        LEFT JOIN people p_sup ON m.supervisor_person_id = p_sup.id
        LEFT JOIN people p_ns ON m.next_step_assigned_to_person_id = p_ns.id
        LEFT JOIN organizations o_req ON m.requesting_organization_id = o_req.id
        LEFT JOIN organizations o_cli ON m.client_organization_id = o_cli.id
        LEFT JOIN organizations o_rev ON m.reviewing_organization_id = o_rev.id
        LEFT JOIN organizations o_lead ON m.lead_external_org_id = o_lead.id
        WHERE m.status != 'closed'
        ORDER BY m.priority, m.title
    """).fetchall()

    for matter_row in rows:
        matter = dict(matter_row)
        mid = matter["id"]

        matter["tags"] = [row["name"] for row in db.execute("""
            SELECT t.name FROM tags t
            JOIN matter_tags mt ON t.id = mt.tag_id
            WHERE mt.matter_id = ?
            ORDER BY t.name
        """, (mid,))]

        matter["stakeholders"] = [dict(row) for row in db.execute("""
            SELECT p.full_name, mp.matter_role, mp.engagement_level
            FROM matter_people mp
            JOIN people p ON mp.person_id = p.id
            WHERE mp.matter_id = ?
        """, (mid,))]

        matter["organizations"] = [dict(row) for row in db.execute("""
            SELECT o.name, mo.organization_role
            FROM matter_organizations mo
            JOIN organizations o ON mo.organization_id = o.id
            WHERE mo.matter_id = ?
        """, (mid,))]

        matter["recent_updates"] = [dict(row) for row in db.execute("""
            SELECT update_type, summary, created_at
            FROM matter_updates
            WHERE matter_id = ?
            ORDER BY created_at DESC
            LIMIT 3
        """, (mid,))]

        matter["open_tasks"] = [dict(row) for row in db.execute("""
            SELECT t.title, p.full_name as assigned_to_name, t.status,
                   t.task_mode, t.due_date, t.expected_output
            FROM tasks t
            LEFT JOIN people p ON t.assigned_to_person_id = p.id
            WHERE t.matter_id = ? AND t.status NOT IN ('done', 'deferred')
            ORDER BY t.due_date
        """, (mid,))]

        matter["open_decisions"] = [dict(row) for row in db.execute("""
            SELECT d.title, d.decision_type, p.full_name as decision_owner_name,
                   d.decision_due_date
            FROM decisions d
            LEFT JOIN people p ON d.decision_assigned_to_person_id = p.id
            WHERE d.matter_id = ? AND d.status IN ('pending', 'under consideration')
        """, (mid,))]

        matters.append(matter)

    return matters


def _get_active_people(db):
    return [dict(row) for row in db.execute("""
        SELECT p.id, p.full_name, p.first_name, p.last_name, p.title,
               p.organization_id, o.name as org_name,
               p.relationship_category, p.relationship_lane, p.substantive_areas
        FROM people p
        LEFT JOIN organizations o ON p.organization_id = o.id
        WHERE p.is_active = 1
        ORDER BY p.full_name
    """)]


def _get_active_organizations(db):
    return [dict(row) for row in db.execute("""
        SELECT o.id, o.name, o.short_name, o.organization_type,
               o.parent_organization_id, po.name as parent_name
        FROM organizations o
        LEFT JOIN organizations po ON o.parent_organization_id = po.id
        WHERE o.is_active = 1
        ORDER BY o.name
    """)]


def _get_recent_meetings(db, days):
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    meetings = []
    rows = db.execute("""
        SELECT id, title, meeting_type, date_time_start
        FROM meetings
        WHERE date_time_start >= ?
        ORDER BY date_time_start DESC
    """, (cutoff,)).fetchall()

    for meeting_row in rows:
        meeting = dict(meeting_row)
        mid = meeting["id"]

        meeting["matter_links"] = [dict(row) for row in db.execute("""
            SELECT mm.matter_id, m.title as matter_title, mm.relationship_type
            FROM meeting_matters mm
            JOIN matters m ON mm.matter_id = m.id
            WHERE mm.meeting_id = ?
        """, (mid,))]

        meeting["participants"] = [dict(row) for row in db.execute("""
            SELECT p.full_name, mp.meeting_role
            FROM meeting_participants mp
            JOIN people p ON mp.person_id = p.id
            WHERE mp.meeting_id = ?
        """, (mid,))]

        meetings.append(meeting)

    return meetings


def _get_standalone_tasks(db):
    return [dict(row) for row in db.execute("""
        SELECT t.id, t.title, t.status, t.task_mode,
               t.assigned_to_person_id, p.full_name as assigned_to_name,
               t.due_date, t.expected_output
        FROM tasks t
        LEFT JOIN people p ON t.assigned_to_person_id = p.id
        WHERE t.matter_id IS NULL
        AND t.status NOT IN ('done', 'deferred')
        ORDER BY t.due_date
    """)]
