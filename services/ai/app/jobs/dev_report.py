"""Weekly dev report generator.

Analyzes field completeness, enum distributions, pipeline quality,
and page visit telemetry. Zero LLM cost — pure database queries.

For months 1-2: verbose format with purpose + distribution + impact per field.
After month 2: compact format (percentages and trends only).
"""
import json
import logging
import os
import uuid
from datetime import date, datetime, timedelta

import httpx

try:
    from dotenv import load_dotenv
    import os as _os
    load_dotenv(_os.path.join(_os.path.dirname(_os.path.dirname(_os.path.dirname(__file__))), ".env"))
except ImportError:
    pass

logger = logging.getLogger(__name__)

TRACKER_BASE_URL = os.environ.get("TRACKER_BASE_URL", "http://localhost:8004/tracker")
TRACKER_USER = os.environ.get("TRACKER_USER", "")
TRACKER_PASS = os.environ.get("TRACKER_PASS", "")


def _tracker_get(path, params=None):
    url = f"{TRACKER_BASE_URL}{path}"
    auth = (TRACKER_USER, TRACKER_PASS) if TRACKER_USER else None
    try:
        r = httpx.get(url, auth=auth, params=params, timeout=30)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        logger.error("Tracker GET %s failed: %s", path, e)
        return {}


def _items(resp):
    if isinstance(resp, list):
        return resp
    return resp.get("items", [])


# ═══════════════════════════════════════════════════════════════════════════
# Field definitions: what to track, why, and who should populate
# ═══════════════════════════════════════════════════════════════════════════

MATTER_FIELDS = [
    {"field": "status", "purpose": "Current state of the matter", "source": "manual", "impact": "Brief cannot assess portfolio health", "weight": 3},
    {"field": "priority", "purpose": "Relative importance for triage", "source": "manual", "impact": "Brief cannot rank matters; all treated equally", "weight": 2},
    {"field": "sensitivity", "purpose": "Leadership/enforcement/congressional flags", "source": "manual", "impact": "Risk register section is empty", "weight": 2},
    {"field": "boss_involvement_level", "purpose": "What level of boss attention needed", "source": "manual", "impact": "Boss queue in daily brief cannot function", "weight": 3},
    {"field": "next_step", "purpose": "What happens next on this matter", "source": "manual", "impact": "No execution spine; portfolio health degrades", "weight": 3},
    {"field": "next_step_assigned_to_person_id", "purpose": "Who is responsible for next action", "source": "manual", "impact": "Accountability gap; team view cannot flag drift", "weight": 3},
    {"field": "work_deadline", "purpose": "Internal delivery deadline", "source": "manual", "impact": "Deadline section misses internal dates", "weight": 2},
    {"field": "decision_deadline", "purpose": "When a decision must be made", "source": "manual", "impact": "Decision docket has no urgency signal", "weight": 2},
    {"field": "external_deadline", "purpose": "Court/statutory/regulatory deadline", "source": "manual", "impact": "Hardest deadlines missed in horizon scan", "weight": 2},
    {"field": "risk_level", "purpose": "Red/yellow/green posture", "source": "manual", "impact": "Portfolio health view has no risk signal", "weight": 1},
    {"field": "revisit_date", "purpose": "When to re-evaluate parked matters", "source": "manual", "impact": "Parked matters go permanently dark", "weight": 1},
    {"field": "matter_type", "purpose": "Category of work", "source": "manual", "impact": "No portfolio grouping by type", "weight": 1},
]

TASK_FIELDS = [
    {"field": "task_mode", "purpose": "action/follow_up/monitoring", "source": "manual", "impact": "All tasks look alike; no supervisory signal", "weight": 2, "is_enum": True,
     "enum_values": ["action", "follow_up", "monitoring"]},
    {"field": "expected_output", "purpose": "What done looks like", "source": "ai", "impact": "Completion is ambiguous", "weight": 2},
    {"field": "waiting_on_person_id", "purpose": "Who is blocking this task", "source": "ai", "impact": "Blocked work invisible", "weight": 1},
    {"field": "due_date", "purpose": "When the task is due", "source": "manual", "impact": "No overdue detection; deadline section incomplete", "weight": 3},
    {"field": "assigned_to_person_id", "purpose": "Who owns the task", "source": "manual", "impact": "Team workload view broken", "weight": 3},
    {"field": "matter_id", "purpose": "Which matter this serves", "source": "ai", "impact": "Orphan tasks have no context", "weight": 2},
    {"field": "task_type", "purpose": "Category of task", "source": "manual", "impact": "No task type analysis", "weight": 1, "is_enum": True},
]

PEOPLE_FIELDS = [
    {"field": "relationship_category", "purpose": "Role type (Boss, Leadership, etc.)", "source": "manual", "impact": "Brief cannot distinguish stakeholder types", "weight": 2, "is_enum": True,
     "enum_values": ["Boss", "Leadership", "Direct report", "Indirect report", "OGC peer", "Internal client", "Commissioner office", "Partner agency", "Hill", "Outside party"]},
    {"field": "relationship_lane", "purpose": "Decision role (maker, blocker, etc.)", "source": "manual", "impact": "Meeting prep cannot flag who matters most", "weight": 2, "is_enum": True,
     "enum_values": ["Decision-maker", "Recommender", "Drafter", "Blocker", "Influencer", "FYI only"]},
    {"field": "last_interaction_date", "purpose": "When you last engaged", "source": "manual", "impact": "Relationship neglect invisible", "weight": 2},
    {"field": "next_interaction_needed_date", "purpose": "When to follow up", "source": "manual", "impact": "Follow-up section of brief is empty", "weight": 2},
    {"field": "next_interaction_type", "purpose": "How to follow up", "source": "manual", "impact": "Follow-ups are vague", "weight": 1},
    {"field": "working_style_notes", "purpose": "How this person operates (private)", "source": "manual", "impact": "No prep context for meetings", "weight": 1},
    {"field": "substantive_areas", "purpose": "What this person works on", "source": "manual", "impact": "Extraction cannot route to relevant people", "weight": 1},
    {"field": "manager_person_id", "purpose": "Org chart hierarchy", "source": "manual", "impact": "No supervisory chain reasoning", "weight": 1},
    {"field": "title", "purpose": "Job title", "source": "manual", "impact": "No role context in briefs", "weight": 1},
    {"field": "organization_id", "purpose": "Which org they belong to", "source": "manual", "impact": "No org grouping", "weight": 1},
]

MEETING_FIELDS = [
    {"field": "meeting_type", "purpose": "1:1/group/congressional/etc.", "source": "manual", "impact": "Meeting intelligence cannot tier (core vs full)", "weight": 2, "is_enum": True},
    {"field": "readout_summary", "purpose": "Post-meeting capture", "source": "manual", "impact": "Meetings produce no record", "weight": 3},
    {"field": "prep_needed", "purpose": "Flag for pre-meeting prep", "source": "manual", "impact": "Daily brief cannot flag meetings needing prep", "weight": 1},
    {"field": "purpose", "purpose": "Why the meeting exists", "source": "manual", "impact": "No meeting context", "weight": 1},
]

DECISION_FIELDS = [
    {"field": "decision_assigned_to_person_id", "purpose": "Who must decide", "source": "manual", "impact": "No accountability for pending decisions", "weight": 2},
    {"field": "decision_due_date", "purpose": "When decision is needed", "source": "manual", "impact": "Decision docket has no urgency", "weight": 2},
    {"field": "options_summary", "purpose": "What the choices are", "source": "manual", "impact": "Decisions are titles only", "weight": 1},
]


def _analyze_fields(items, field_defs, entity_name):
    """Analyze field completeness for a set of items."""
    total = len(items)
    if total == 0:
        return {"entity": entity_name, "total": 0, "fields": [], "message": f"No {entity_name} to analyze."}

    results = []
    for fd in field_defs:
        field = fd["field"]
        populated = sum(1 for item in items if item.get(field))
        pct = round(populated / total * 100) if total > 0 else 0

        result = {
            "field": field,
            "purpose": fd["purpose"],
            "source": fd["source"],
            "impact": fd["impact"],
            "weight": fd["weight"],
            "populated": populated,
            "total": total,
            "pct": pct,
        }

        # Enum distribution
        if fd.get("is_enum"):
            dist = {}
            for item in items:
                val = item.get(field) or "NOT SET"
                dist[val] = dist.get(val, 0) + 1
            result["distribution"] = dict(sorted(dist.items(), key=lambda x: -x[1]))

        results.append(result)

    results.sort(key=lambda x: x["pct"])
    return {"entity": entity_name, "total": total, "fields": results}


def _analyze_pipeline_quality(db):
    """Analyze AI pipeline quality from review_action_log and llm_usage."""
    week_ago = (date.today() - timedelta(days=7)).isoformat()

    # Review actions
    actions = db.execute(
        "SELECT action_type as action, COUNT(*) as cnt FROM review_action_log WHERE created_at >= ? GROUP BY action_type",
        (week_ago,),
    ).fetchall()
    action_counts = {row["action"]: row["cnt"] for row in actions}

    total_actions = sum(action_counts.values())
    accept = action_counts.get("accept", 0) + action_counts.get("approve", 0)
    edit = action_counts.get("edit", 0) + action_counts.get("modify", 0)
    reject = action_counts.get("reject", 0)

    accept_rate = round(accept / total_actions * 100) if total_actions > 0 else 0
    edit_rate = round(edit / total_actions * 100) if total_actions > 0 else 0
    reject_rate = round(reject / total_actions * 100) if total_actions > 0 else 0

    # LLM spend
    spend_rows = db.execute(
        "SELECT model as model_used, SUM(cost_usd) as total_cost, COUNT(*) as calls FROM llm_usage WHERE created_at >= ? GROUP BY model",
        (week_ago,),
    ).fetchall()
    spend = {row["model_used"]: {"cost": round(row["total_cost"] or 0, 4), "calls": row["calls"]} for row in spend_rows}
    total_spend = sum(s["cost"] for s in spend.values())

    # Communications processed
    comms = db.execute(
        "SELECT COUNT(*) as cnt FROM communications WHERE created_at >= ?",
        (week_ago,),
    ).fetchone()

    return {
        "total_review_actions": total_actions,
        "accept_rate": accept_rate,
        "edit_rate": edit_rate,
        "reject_rate": reject_rate,
        "action_counts": action_counts,
        "llm_spend": spend,
        "total_spend": round(total_spend, 2),
        "communications_processed": comms["cnt"] if comms else 0,
    }


def _analyze_page_visits(db):
    """Analyze page visit telemetry."""
    week_ago = (date.today() - timedelta(days=7)).isoformat()
    try:
        db.execute("CREATE TABLE IF NOT EXISTS page_visits (id TEXT PRIMARY KEY, page TEXT NOT NULL, timestamp TEXT NOT NULL, session_id TEXT)")
        rows = db.execute(
            "SELECT page, COUNT(*) as visits FROM page_visits WHERE timestamp >= ? GROUP BY page ORDER BY visits DESC",
            (week_ago,),
        ).fetchall()
        return [{"page": row["page"], "visits": row["visits"]} for row in rows]
    except Exception as e:
        logger.warning("Page visits query failed: %s", e)
        return []


def _analyze_context_notes():
    """Analyze context note generation."""
    notes = _items(_tracker_get("/context-notes"))

    total = len(notes)
    if total == 0:
        return {"total": 0, "by_source": {}, "by_category": {}, "avg_links": 0}

    by_source = {}
    by_category = {}
    total_links = 0

    for n in notes:
        src = n.get("created_by_type", "unknown")
        by_source[src] = by_source.get(src, 0) + 1
        cat = n.get("category", "unknown")
        by_category[cat] = by_category.get(cat, 0) + 1
        total_links += len(n.get("links", []))

    return {
        "total": total,
        "by_source": by_source,
        "by_category": by_category,
        "avg_links": round(total_links / total, 1) if total > 0 else 0,
    }


def generate_dev_report(db):
    """Generate the full weekly dev report."""
    logger.info("Generating dev report")

    # Fetch all entity data from tracker
    matters = _items(_tracker_get("/matters"))
    active_matters = [m for m in matters if m.get("status") not in ("closed", "archived", "withdrawn")]
    tasks = _items(_tracker_get("/tasks", {"exclude_done": "true"}))
    people = _items(_tracker_get("/people"))
    active_people = [p for p in people if p.get("is_active", True)]
    meetings = _items(_tracker_get("/meetings"))
    decisions = _items(_tracker_get("/decisions"))
    open_decisions = [d for d in decisions if d.get("status") not in ("decided", "implemented", "closed")]

    # Field analysis per entity
    matter_analysis = _analyze_fields(active_matters, MATTER_FIELDS, "matters")
    task_analysis = _analyze_fields(tasks, TASK_FIELDS, "tasks")
    people_analysis = _analyze_fields(active_people, PEOPLE_FIELDS, "people")
    meeting_analysis = _analyze_fields(meetings, MEETING_FIELDS, "meetings")
    decision_analysis = _analyze_fields(open_decisions, DECISION_FIELDS, "decisions")

    # Pipeline quality
    pipeline = _analyze_pipeline_quality(db)

    # Page visits
    page_visits = _analyze_page_visits(db)

    # Context notes
    context_notes = _analyze_context_notes()

    # Compute overall completeness
    all_fields = []
    for analysis in [matter_analysis, task_analysis, people_analysis, meeting_analysis, decision_analysis]:
        all_fields.extend(analysis.get("fields", []))

    if all_fields:
        total_weight = sum(f["weight"] for f in all_fields)
        weighted_sum = sum(f["pct"] * f["weight"] for f in all_fields)
        overall_score = round(weighted_sum / total_weight) if total_weight > 0 else 0
    else:
        overall_score = 0

    # Find underused features (< 20% populated)
    underused = [f for f in all_fields if f["pct"] < 20]

    # Suggestions
    suggestions = []
    for f in underused[:5]:
        if f["source"] == "ai":
            suggestions.append(f"'{f['field']}' is {f['pct']}% populated — extraction prompt may need tuning")
        else:
            suggestions.append(f"'{f['field']}' is {f['pct']}% populated — manual entry needed. Impact: {f['impact']}")

    if pipeline.get("edit_rate", 0) > 25:
        suggestions.append(f"Edit rate is {pipeline['edit_rate']}% — review extraction prompt quality")

    # Unvisited pages
    visited_pages = {pv["page"] for pv in page_visits}
    important_pages = {"/tasks", "/people", "/matters", "/meetings", "/decisions",
                       "/context-notes", "/review/speakers", "/review/entities",
                       "/review/bundles", "/intelligence/daily", "/intelligence/weekly",
                       "/settings/ai", "/workload"}
    unvisited = important_pages - visited_pages
    if unvisited:
        suggestions.append(f"Unvisited pages this week: {', '.join(sorted(unvisited))}")

    data = {
        "date": date.today().isoformat(),
        "date_display": f"Week of {date.today().strftime('%B %d, %Y')}",
        "overall_score": overall_score,
        "entity_analyses": {
            "matters": matter_analysis,
            "tasks": task_analysis,
            "people": people_analysis,
            "meetings": meeting_analysis,
            "decisions": decision_analysis,
        },
        "context_notes": context_notes,
        "pipeline": pipeline,
        "page_visits": page_visits,
        "underused": [{"field": f"{f.get('entity', '')}.{f['field']}" if 'entity' not in f else f['field'], "pct": f["pct"], "source": f["source"], "impact": f["impact"]} for f in underused],
        "suggestions": suggestions,
    }

    logger.info("Dev report: overall score %d%%, %d underused fields, %d suggestions",
                overall_score, len(underused), len(suggestions))
    return data
