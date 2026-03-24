"""
AI context snapshot endpoint — provides extraction context to the AI service.

Read-only, purpose-built endpoint. Consumed by services/ai/ before each
Sonnet extraction call. Response is stored in ai_extractions.tracker_context_snapshot.

All active people fields are included.
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
    matters_limit: int = Query(100, ge=1, le=500, description="Max matters to return"),
    people_limit: int = Query(500, ge=1, le=2000, description="Max people to return"),
    organizations_limit: int = Query(200, ge=1, le=1000, description="Max organizations to return"),
    tasks_limit: int = Query(200, ge=1, le=1000, description="Max standalone tasks to return"),
):
    """Return the tracker context snapshot for AI extraction.

    Includes optional per-section limits to control payload size.
    The _meta block in the response shows total counts and whether
    any section was truncated.
    """
    result = {"generated_at": datetime.now().isoformat()}
    meta = {}

    if include_matters:
        all_matters = _get_matters_with_nested(db)
        meta["matters_total"] = len(all_matters)
        meta["matters_truncated"] = len(all_matters) > matters_limit
        result["matters"] = all_matters[:matters_limit]
    if include_people:
        all_people = _get_active_people(db)
        meta["people_total"] = len(all_people)
        meta["people_truncated"] = len(all_people) > people_limit
        result["people"] = all_people[:people_limit]
    if include_organizations:
        all_orgs = _get_active_organizations(db)
        meta["organizations_total"] = len(all_orgs)
        meta["organizations_truncated"] = len(all_orgs) > organizations_limit
        result["organizations"] = all_orgs[:organizations_limit]
    if include_recent_meetings:
        all_meetings = _get_recent_meetings(db, meetings_days)
        meta["recent_meetings_total"] = len(all_meetings)
        result["recent_meetings"] = all_meetings
    if include_standalone_tasks:
        all_tasks = _get_standalone_tasks(db)
        meta["standalone_tasks_total"] = len(all_tasks)
        meta["standalone_tasks_truncated"] = len(all_tasks) > tasks_limit
        result["standalone_tasks"] = all_tasks[:tasks_limit]

    result["_meta"] = meta
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
    """All open matters with stakeholders, updates, tasks, decisions.

    Uses batch queries (7 total) instead of per-matter sub-queries
    to avoid N+1 performance issues.
    """
    from collections import defaultdict

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

    matter_ids = [row["id"] for row in rows]
    if not matter_ids:
        return []

    placeholders = ",".join("?" * len(matter_ids))

    # Batch query: tags
    tags_by_matter = defaultdict(list)
    for row in db.execute(f"""
        SELECT mt.matter_id, t.name
        FROM matter_tags mt JOIN tags t ON t.id = mt.tag_id
        WHERE mt.matter_id IN ({placeholders})
        ORDER BY t.name
    """, matter_ids):
        tags_by_matter[row["matter_id"]].append(row["name"])

    # Batch query: stakeholders
    stakeholders_by_matter = defaultdict(list)
    for row in db.execute(f"""
        SELECT mp.matter_id, mp.person_id, p.full_name, mp.matter_role, mp.engagement_level
        FROM matter_people mp JOIN people p ON mp.person_id = p.id
        WHERE mp.matter_id IN ({placeholders})
    """, matter_ids):
        stakeholders_by_matter[row["matter_id"]].append(dict(row))

    # Batch query: organizations
    orgs_by_matter = defaultdict(list)
    for row in db.execute(f"""
        SELECT mo.matter_id, mo.organization_id, o.name, mo.organization_role
        FROM matter_organizations mo JOIN organizations o ON mo.organization_id = o.id
        WHERE mo.matter_id IN ({placeholders})
    """, matter_ids):
        orgs_by_matter[row["matter_id"]].append(dict(row))

    # Batch query: recent updates (top 3 per matter via window function)
    updates_by_matter = defaultdict(list)
    for row in db.execute(f"""
        SELECT matter_id, update_type, summary, created_at
        FROM (
            SELECT *, ROW_NUMBER() OVER (PARTITION BY matter_id ORDER BY created_at DESC) as rn
            FROM matter_updates
            WHERE matter_id IN ({placeholders})
        ) WHERE rn <= 3
    """, matter_ids):
        updates_by_matter[row["matter_id"]].append(dict(row))

    # Batch query: open tasks
    tasks_by_matter = defaultdict(list)
    for row in db.execute(f"""
        SELECT t.matter_id, t.id, t.title, t.description, t.status, t.task_mode,
               t.priority, t.assigned_to_person_id, p.full_name as assigned_to_name,
               t.due_date, t.deadline_type,
               t.waiting_on_person_id, t.waiting_on_org_id, t.waiting_on_description,
               t.trigger_description, t.expected_output, t.tracks_task_id,
               t.next_follow_up_date
        FROM tasks t
        LEFT JOIN people p ON t.assigned_to_person_id = p.id
        WHERE t.matter_id IN ({placeholders}) AND t.status NOT IN ('done', 'deferred')
        ORDER BY t.due_date
    """, matter_ids):
        tasks_by_matter[row["matter_id"]].append(dict(row))

    # Batch query: open decisions
    decisions_by_matter = defaultdict(list)
    for row in db.execute(f"""
        SELECT d.matter_id, d.id, d.title, d.decision_type, d.status,
               d.decision_assigned_to_person_id, p.full_name as decision_owner_name,
               d.decision_due_date, d.options_summary, d.recommended_option
        FROM decisions d
        LEFT JOIN people p ON d.decision_assigned_to_person_id = p.id
        WHERE d.matter_id IN ({placeholders}) AND d.status IN ('pending', 'under consideration')
    """, matter_ids):
        decisions_by_matter[row["matter_id"]].append(dict(row))

    # Batch query: comment topics with nested questions
    topics_by_matter = defaultdict(list)
    questions_by_topic = defaultdict(list)
    for row in db.execute(f"""
        SELECT ct.matter_id, ct.id, ct.topic_label, ct.topic_area,
               ct.position_status, ct.position_summary, ct.priority,
               ct.due_date, ct.assigned_to_person_id, p.full_name as assigned_to_name,
               ct.source_fr_doc_number, ct.source_document_type
        FROM comment_topics ct
        LEFT JOIN people p ON ct.assigned_to_person_id = p.id
        WHERE ct.matter_id IN ({placeholders})
        ORDER BY ct.sort_order ASC NULLS LAST
    """, matter_ids):
        topics_by_matter[row["matter_id"]].append(dict(row))

    # Fetch questions for all topics
    topic_ids = []
    for tlist in topics_by_matter.values():
        topic_ids.extend(t["id"] for t in tlist)
    if topic_ids:
        q_placeholders = ",".join("?" * len(topic_ids))
        for row in db.execute(f"""
            SELECT comment_topic_id, id, question_number, question_text, sort_order
            FROM comment_questions
            WHERE comment_topic_id IN ({q_placeholders})
            ORDER BY sort_order ASC NULLS LAST, question_number ASC
        """, topic_ids):
            questions_by_topic[row["comment_topic_id"]].append(dict(row))

    # Nest questions into topics
    for tlist in topics_by_matter.values():
        for topic in tlist:
            topic["questions"] = questions_by_topic.get(topic["id"], [])

    # Batch query: linked directives
    directives_by_matter = defaultdict(list)
    for row in db.execute(f"""
        SELECT dm.matter_id, pd.id, pd.directive_label, pd.source_document,
               pd.implementation_status, pd.priority_tier, pd.responsible_entity,
               dm.relationship_type
        FROM directive_matters dm
        JOIN policy_directives pd ON dm.directive_id = pd.id
        WHERE dm.matter_id IN ({placeholders})
        ORDER BY pd.sort_order ASC NULLS LAST
    """, matter_ids):
        directives_by_matter[row["matter_id"]].append(dict(row))

    # Assemble
    matters = []
    for matter_row in rows:
        matter = dict(matter_row)
        mid = matter["id"]
        matter["tags"] = tags_by_matter.get(mid, [])
        matter["stakeholders"] = stakeholders_by_matter.get(mid, [])
        matter["organizations"] = orgs_by_matter.get(mid, [])
        matter["recent_updates"] = updates_by_matter.get(mid, [])
        matter["open_tasks"] = tasks_by_matter.get(mid, [])
        matter["open_decisions"] = decisions_by_matter.get(mid, [])
        matter["comment_topics"] = topics_by_matter.get(mid, [])
        matter["linked_directives"] = directives_by_matter.get(mid, [])
        matters.append(matter)

    return matters


def _get_active_people(db):
    return [dict(row) for row in db.execute("""
        SELECT p.*, o.name as org_name
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
    """Recent meetings with matter links and participants (batch queries)."""
    from collections import defaultdict

    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    rows = db.execute("""
        SELECT id, title, meeting_type, date_time_start
        FROM meetings WHERE date_time_start >= ?
        ORDER BY date_time_start DESC
    """, (cutoff,)).fetchall()

    meeting_ids = [row["id"] for row in rows]
    if not meeting_ids:
        return []

    placeholders = ",".join("?" * len(meeting_ids))

    matter_links_by_meeting = defaultdict(list)
    for row in db.execute(f"""
        SELECT mm.meeting_id, mm.matter_id, m.title as matter_title, mm.relationship_type
        FROM meeting_matters mm JOIN matters m ON mm.matter_id = m.id
        WHERE mm.meeting_id IN ({placeholders})
    """, meeting_ids):
        matter_links_by_meeting[row["meeting_id"]].append(dict(row))

    participants_by_meeting = defaultdict(list)
    for row in db.execute(f"""
        SELECT mp.meeting_id, p.full_name, mp.meeting_role
        FROM meeting_participants mp JOIN people p ON mp.person_id = p.id
        WHERE mp.meeting_id IN ({placeholders})
    """, meeting_ids):
        participants_by_meeting[row["meeting_id"]].append(dict(row))

    meetings = []
    for meeting_row in rows:
        meeting = dict(meeting_row)
        mid = meeting["id"]
        meeting["matter_links"] = matter_links_by_meeting.get(mid, [])
        meeting["participants"] = participants_by_meeting.get(mid, [])
        meetings.append(meeting)

    return meetings


def _get_standalone_tasks(db):
    return [dict(row) for row in db.execute("""
        SELECT t.id, t.title, t.description, t.status, t.task_mode,
               t.priority, t.assigned_to_person_id, p.full_name as assigned_to_name,
               t.due_date, t.deadline_type,
               t.waiting_on_person_id, t.waiting_on_org_id, t.waiting_on_description,
               t.trigger_description, t.expected_output, t.tracks_task_id,
               t.next_follow_up_date
        FROM tasks t
        LEFT JOIN people p ON t.assigned_to_person_id = p.id
        WHERE t.matter_id IS NULL
        AND t.status NOT IN ('done', 'deferred')
        ORDER BY t.due_date
    """)]
