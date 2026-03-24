"""Weekly brief data assembly, calibration, and generation.

Queries tracker and AI databases to assemble the 12-section weekly brief:
0. What I Got Wrong (calibration)
1. Executive Summary (Sonnet)
2. Portfolio Health by Matter
3. Decision Docket
4. Team Management View
5. Stakeholder & Relationship Management
6. Deadlines & Horizon Scan
7. Documents & Deliverables Pipeline
8. Risk & Escalation Register
9. Data Hygiene Score
10. Rulemaking Comment Progress (topic status by matter, question coverage)
11. Policy Directives Status (implementation tracking, overdue compliance)

Cost: ~$0.15/week (one Sonnet call for executive summary).
"""
from __future__ import annotations

import json
import logging
import os
from datetime import date, timedelta

import httpx

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
    """Extract items list from tracker response."""
    if isinstance(resp, list):
        return resp
    return resp.get("items", [])


# ═══════════════════════════════════════════════════════════════════════════
# Section 0: Calibration — What I Got Wrong
# ═══════════════════════════════════════════════════════════════════════════

def _assemble_calibration(db):
    """Compare last week's daily brief flags against actual outcomes."""
    week_ago = (date.today() - timedelta(days=7)).isoformat()

    # Load this week's daily briefs
    rows = db.execute(
        "SELECT content FROM intelligence_briefs WHERE brief_type = 'daily' AND brief_date >= ? ORDER BY brief_date",
        (week_ago,),
    ).fetchall()

    if not rows:
        return {"has_data": False, "message": "No daily briefs from this week to calibrate against."}

    # Extract all flags from daily briefs
    flagged_items = []
    for row in rows:
        try:
            content = json.loads(row["content"]) if isinstance(row["content"], str) else row["content"]
        except (json.JSONDecodeError, TypeError):
            continue
        for action in content.get("action_list", []):
            flagged_items.append({
                "tag": action.get("tag", ""),
                "title": action.get("title", ""),
                "entity_type": action.get("entity_type", ""),
                "entity_id": action.get("entity_id", ""),
                "detail": action.get("detail", ""),
            })

    if not flagged_items:
        return {"has_data": False, "message": "No action items flagged in daily briefs this week."}

    # Deduplicate by entity_id
    seen = set()
    unique_flags = []
    for f in flagged_items:
        key = f.get("entity_id") or f.get("title")
        if key not in seen:
            seen.add(key)
            unique_flags.append(f)

    # Check current status of flagged items
    # For tasks: check if still overdue or resolved
    # For decisions: check if still pending or decided
    materialized = 0
    resolved = 0
    still_open = 0

    for f in unique_flags:
        etype = f.get("entity_type", "")
        eid = f.get("entity_id", "")
        if not eid:
            still_open += 1
            continue

        if etype == "task":
            task = _tracker_get(f"/tasks/{eid}")
            if isinstance(task, dict) and task.get("id"):
                status = task.get("status", "")
                if status in ("done", "completed"):
                    resolved += 1
                elif status in ("deferred",):
                    resolved += 1  # Handled by deferral
                else:
                    materialized += 1  # Still open = flag materialized
            else:
                still_open += 1

        elif etype == "decision":
            decision = _tracker_get(f"/decisions/{eid}")
            if isinstance(decision, dict) and decision.get("id"):
                status = decision.get("status", "")
                if status in ("decided", "implemented", "closed"):
                    resolved += 1
                else:
                    materialized += 1
            else:
                still_open += 1

        elif etype == "matter":
            # Matters flagged for deadlines — check if deadline passed
            materialized += 1  # Conservative: deadline flags usually materialize

        else:
            still_open += 1

    total = len(unique_flags)
    wrong = max(0, total - materialized - resolved - still_open)
    score = round((materialized + resolved) / total * 100) if total > 0 else 0

    return {
        "has_data": True,
        "total_flags": total,
        "materialized": materialized,
        "resolved": resolved,
        "still_open": still_open,
        "wrong": wrong,
        "score": score,
        "score_label": "Good" if score >= 70 else "Fair" if score >= 50 else "Needs tuning",
    }


# ═══════════════════════════════════════════════════════════════════════════
# Section 2: Portfolio Health
# ═══════════════════════════════════════════════════════════════════════════

def _assemble_portfolio():
    """Active matters grouped by posture."""
    matters = _items(_tracker_get("/matters"))
    today = date.today()

    critical = []  # Deadlines in 7 days, blocked, boss-decision-pending
    important = []  # Deadlines in 30 days, active work
    strategic = []  # Long-running, monitoring
    monitoring = []

    for m in matters:
        status = m.get("status", "")
        if status in ("closed", "archived", "withdrawn"):
            continue

        priority = m.get("priority", "")
        # Check nearest deadline
        deadlines = [m.get("work_deadline"), m.get("decision_deadline"), m.get("external_deadline")]
        nearest = min((d for d in deadlines if d), default=None)
        days_to_deadline = None
        if nearest:
            try:
                dl = date.fromisoformat(nearest)
                days_to_deadline = (dl - today).days
            except (ValueError, TypeError):
                pass

        item = {
            "id": m.get("id"),
            "title": m.get("title", ""),
            "status": status,
            "priority": priority,
            "matter_number": m.get("matter_number", ""),
            "next_step": m.get("next_step", ""),
            "next_step_owner": m.get("next_step_owner_name", m.get("next_step_owner", "")),
            "nearest_deadline": nearest,
            "days_to_deadline": days_to_deadline,
            "sensitivity": m.get("sensitivity", ""),
            "boss_involvement": m.get("boss_involvement", ""),
            "updated_at": m.get("updated_at", ""),
        }

        if days_to_deadline is not None and days_to_deadline <= 7:
            critical.append(item)
        elif priority in ("critical", "high") or (days_to_deadline is not None and days_to_deadline <= 30):
            important.append(item)
        elif status in ("parked / monitoring",):
            monitoring.append(item)
        else:
            strategic.append(item)

    # Sort each group by deadline
    for group in [critical, important, strategic, monitoring]:
        group.sort(key=lambda x: x.get("nearest_deadline") or "9999")

    return {
        "critical": critical,
        "important": important,
        "strategic": strategic,
        "monitoring": monitoring,
        "total_active": len(critical) + len(important) + len(strategic) + len(monitoring),
    }


# ═══════════════════════════════════════════════════════════════════════════
# Section 3: Decision Docket
# ═══════════════════════════════════════════════════════════════════════════

def _assemble_decisions():
    """All open decisions."""
    decisions = _items(_tracker_get("/decisions"))
    open_decisions = []
    for d in decisions:
        status = d.get("status", "")
        if status in ("decided", "implemented", "closed"):
            continue
        open_decisions.append({
            "id": d.get("id"),
            "title": d.get("title", ""),
            "matter_title": d.get("matter_title", ""),
            "decision_owner": d.get("owner_name", d.get("decision_owner", "")),
            "due_date": d.get("due_date"),
            "status": status,
            "options_summary": d.get("options_summary", ""),
            "recommended_option": d.get("recommended_option", ""),
        })
    open_decisions.sort(key=lambda x: x.get("due_date") or "9999")
    return open_decisions


# ═══════════════════════════════════════════════════════════════════════════
# Section 4: Team Management View
# ═══════════════════════════════════════════════════════════════════════════

def _assemble_team():
    """Workload and execution by person, including comment topic assignments."""
    intel = _tracker_get("/ai-context/intelligence-data")
    workload = intel.get("workload", [])
    overdue = intel.get("overdue_tasks", [])

    # Group overdue by assignee
    overdue_by_person = {}
    for t in overdue:
        name = t.get("assignee_name", "Unassigned")
        overdue_by_person.setdefault(name, []).append(t.get("title", ""))

    # Count open comment topics per person by iterating matters
    topics_by_person = {}
    matters = _items(_tracker_get("/matters", {"limit": "200"}))
    today = date.today()
    drifting = []
    for m in matters:
        status = m.get("status", "")
        if status in ("closed", "archived", "withdrawn"):
            continue

        # Check for drifting (no update in 14+ days)
        if status != "parked / monitoring":
            updated = m.get("updated_at", "")
            if updated:
                try:
                    updated_date = date.fromisoformat(updated[:10])
                    days_stale = (today - updated_date).days
                    if days_stale >= 14:
                        drifting.append({
                            "title": m.get("title", ""),
                            "owner": m.get("next_step_owner_name", ""),
                            "days_stale": days_stale,
                        })
                except (ValueError, TypeError):
                    pass

        # Fetch topics for this matter to count per-person assignments
        topics_resp = _tracker_get(f"/matters/{m['id']}/comment-topics")
        topics = _items(topics_resp)
        for t in topics:
            if t.get("position_status") in ("position_taken",):
                continue
            assignee = t.get("assigned_to_name", "")
            if assignee:
                topics_by_person[assignee] = topics_by_person.get(assignee, 0) + 1

    drifting.sort(key=lambda x: -x.get("days_stale", 0))

    return {
        "workload": [
            {
                "name": w.get("full_name", ""),
                "open_tasks": w.get("open_task_count", 0),
                "open_matters": w.get("matter_count", 0),
                "overdue": len(overdue_by_person.get(w.get("full_name", ""), [])),
                "open_topics": topics_by_person.get(w.get("full_name", ""), 0),
            }
            for w in workload
        ],
        "topics_by_person": topics_by_person,
        "overdue_by_person": {k: len(v) for k, v in overdue_by_person.items()},
        "drifting_matters": drifting[:10],
    }


# ═══════════════════════════════════════════════════════════════════════════
# Section 5: Stakeholders & Relationships
# ═══════════════════════════════════════════════════════════════════════════

def _assemble_stakeholders():
    """People needing attention."""
    people = _items(_tracker_get("/people"))
    today = date.today()
    week_out = (today + timedelta(days=7)).isoformat()

    touchpoints_due = []
    neglected = []

    for p in people:
        next_date = p.get("next_interaction_needed_date")
        last_date = p.get("last_interaction_date")
        category = p.get("relationship_category", "")

        # Due touchpoints
        if next_date and next_date <= week_out:
            touchpoints_due.append({
                "name": p.get("full_name", ""),
                "organization": p.get("org_name", ""),
                "category": category,
                "lane": p.get("relationship_category", ""),
                "next_date": next_date,
                "purpose": p.get("next_interaction_purpose", ""),
            })

        # Neglected: important relationships with no interaction in 30+ days
        if category in ("Boss", "Leadership", "Internal client", "Commissioner office") and last_date:
            try:
                last = date.fromisoformat(last_date[:10])
                days_since = (today - last).days
                if days_since >= 30:
                    neglected.append({
                        "name": p.get("full_name", ""),
                        "organization": p.get("org_name", ""),
                        "category": category,
                        "days_since": days_since,
                    })
            except (ValueError, TypeError):
                pass

    touchpoints_due.sort(key=lambda x: x.get("next_date", ""))
    neglected.sort(key=lambda x: -x.get("days_since", 0))

    return {
        "touchpoints_due": touchpoints_due,
        "neglected": neglected[:10],
    }


# ═══════════════════════════════════════════════════════════════════════════
# Section 6: Deadlines & Horizon Scan
# ═══════════════════════════════════════════════════════════════════════════

def _assemble_deadlines():
    """Forward-looking deadline view."""
    matters = _items(_tracker_get("/matters"))
    today = date.today()
    two_weeks = (today + timedelta(days=14)).isoformat()
    thirty_days = (today + timedelta(days=30)).isoformat()
    ninety_days = (today + timedelta(days=90)).isoformat()

    deadlines = {"two_weeks": [], "thirty_days": [], "ninety_days": []}

    for m in matters:
        status = m.get("status", "")
        if status in ("closed", "archived", "withdrawn"):
            continue

        for dl_type in ["work_deadline", "decision_deadline", "external_deadline"]:
            dl = m.get(dl_type)
            if not dl:
                continue

            item = {
                "matter_title": m.get("title", ""),
                "deadline_type": dl_type.replace("_deadline", ""),
                "date": dl,
                "owner": m.get("next_step_owner_name", ""),
            }

            if dl <= two_weeks:
                deadlines["two_weeks"].append(item)
            elif dl <= thirty_days:
                deadlines["thirty_days"].append(item)
            elif dl <= ninety_days:
                deadlines["ninety_days"].append(item)

    for bucket in deadlines.values():
        bucket.sort(key=lambda x: x.get("date", ""))

    return deadlines


# ═══════════════════════════════════════════════════════════════════════════
# Section 7: Documents & Deliverables
# ═══════════════════════════════════════════════════════════════════════════

def _assemble_documents():
    """Document pipeline status."""
    docs = _items(_tracker_get("/documents"))

    by_status = {}
    for d in docs:
        status = d.get("status", "unknown")
        by_status.setdefault(status, []).append({
            "title": d.get("title", ""),
            "matter_title": d.get("matter_title", ""),
        })

    return by_status


# ═══════════════════════════════════════════════════════════════════════════
# Section 8: Risk & Escalation
# ═══════════════════════════════════════════════════════════════════════════

def _assemble_risks():
    """High-sensitivity items and bottlenecks."""
    matters = _items(_tracker_get("/matters"))

    high_sensitivity = []
    for m in matters:
        status = m.get("status", "")
        if status in ("closed", "archived", "withdrawn"):
            continue
        if m.get("sensitivity") in ("high", "leadership", "congressional", "enforcement"):
            high_sensitivity.append({
                "title": m.get("title", ""),
                "sensitivity": m.get("sensitivity", ""),
                "status": status,
                "boss_involvement": m.get("boss_involvement", ""),
            })

    return {"high_sensitivity": high_sensitivity}


# ═══════════════════════════════════════════════════════════════════════════
# Section 9: Data Hygiene Score
# ═══════════════════════════════════════════════════════════════════════════

def _assemble_hygiene():
    """Weighted completeness score."""
    matters = _items(_tracker_get("/matters"))
    tasks = _items(_tracker_get("/tasks", {"exclude_done": "true"}))
    meetings = _items(_tracker_get("/meetings"))
    decisions = _items(_tracker_get("/decisions"))
    people = _items(_tracker_get("/people"))

    active_matters = [m for m in matters if m.get("status") not in ("closed", "archived", "withdrawn")]

    checks = []

    # Matters: next_step_owner (weight 3)
    if active_matters:
        has_owner = sum(1 for m in active_matters if m.get("next_step_owner") or m.get("next_step_owner_name"))
        checks.append({"field": "matter.next_step_owner", "pct": round(has_owner / len(active_matters) * 100), "weight": 3, "count": has_owner, "total": len(active_matters)})

    # Tasks: due_date (weight 2)
    if tasks:
        has_due = sum(1 for t in tasks if t.get("due_date"))
        checks.append({"field": "task.due_date", "pct": round(has_due / len(tasks) * 100), "weight": 2, "count": has_due, "total": len(tasks)})

    # Meetings: readout (weight 2) — only past meetings
    today_str = date.today().isoformat()
    past_meetings = [m for m in meetings if (m.get("meeting_date") or m.get("start_time", "")[:10] or "") < today_str]
    if past_meetings:
        has_readout = sum(1 for m in past_meetings if m.get("readout_summary"))
        checks.append({"field": "meeting.readout_summary", "pct": round(has_readout / len(past_meetings) * 100), "weight": 2, "count": has_readout, "total": len(past_meetings)})

    # Decisions: due_date (weight 2)
    open_decisions = [d for d in decisions if d.get("status") not in ("decided", "implemented", "closed")]
    if open_decisions:
        has_due = sum(1 for d in open_decisions if d.get("due_date"))
        checks.append({"field": "decision.due_date", "pct": round(has_due / len(open_decisions) * 100), "weight": 2, "count": has_due, "total": len(open_decisions)})

    # People: relationship_category (weight 1)
    if people:
        has_cat = sum(1 for p in people if p.get("relationship_category"))
        checks.append({"field": "person.relationship_category", "pct": round(has_cat / len(people) * 100), "weight": 1, "count": has_cat, "total": len(people)})

    # Matters: updated in 30 days (weight 3)
    if active_matters:
        today = date.today()
        recently_updated = 0
        for m in active_matters:
            updated = m.get("updated_at", "")
            if updated:
                try:
                    u_date = date.fromisoformat(updated[:10])
                    if (today - u_date).days <= 30:
                        recently_updated += 1
                except (ValueError, TypeError):
                    pass
        checks.append({"field": "matter.updated_30d", "pct": round(recently_updated / len(active_matters) * 100), "weight": 3, "count": recently_updated, "total": len(active_matters)})

    # Compute weighted score
    if checks:
        total_weight = sum(c["weight"] for c in checks)
        weighted_sum = sum(c["pct"] * c["weight"] for c in checks)
        score = round(weighted_sum / total_weight) if total_weight > 0 else 0
    else:
        score = 0

    return {
        "score": score,
        "checks": checks,
    }


# ═══════════════════════════════════════════════════════════════════════════
# Section 10: Rulemaking Comment Progress
# ═══════════════════════════════════════════════════════════════════════════

def _assemble_comment_progress():
    """Comment topic status and question coverage by matter."""
    matters = _items(_tracker_get("/matters", {"limit": "200"}))
    today = date.today()

    rulemaking_matters = []
    overall_status = {"open": 0, "drafting": 0, "final_review": 0, "position_taken": 0, "not_started": 0}
    total_topics_all = 0
    total_questions_all = 0

    for m in matters:
        status = m.get("status", "")
        if status in ("closed", "archived", "withdrawn"):
            continue

        # Fetch topics for this matter
        topics_resp = _tracker_get(f"/matters/{m['id']}/comment-topics")
        topics = _items(topics_resp)
        if not topics:
            continue

        total_topics = len(topics)
        total_questions = 0
        status_counts = {}
        topic_summaries = []
        for t in topics:
            ps = t.get("position_status", "open")
            status_counts[ps] = status_counts.get(ps, 0) + 1
            overall_status[ps] = overall_status.get(ps, 0) + 1
            questions = t.get("questions", [])
            total_questions += len(questions)
            topic_summaries.append({
                "label": t.get("topic_label", ""),
                "status": ps,
                "question_count": len(questions),
                "assignee": t.get("assigned_to_name", ""),
                "due_date": t.get("due_date"),
            })

        total_topics_all += total_topics
        total_questions_all += total_questions

        deadline = m.get("external_deadline")
        days_remaining = None
        if deadline:
            try:
                dl_date = date.fromisoformat(deadline)
                days_remaining = (dl_date - today).days
            except (ValueError, TypeError):
                pass

        rulemaking_matters.append({
            "matter_id": m.get("id"),
            "matter_title": m.get("title", ""),
            "comment_deadline": deadline,
            "days_remaining": days_remaining,
            "total_topics": total_topics,
            "total_questions": total_questions,
            "status_counts": status_counts,
            "completion_pct": round(status_counts.get("position_taken", 0) / total_topics * 100) if total_topics else 0,
            "topics": topic_summaries,
        })

    rulemaking_matters.sort(key=lambda x: x.get("days_remaining") or 9999)

    return {
        "matters": rulemaking_matters,
        "totals": {
            "matters_with_topics": len(rulemaking_matters),
            "total_topics": total_topics_all,
            "total_questions": total_questions_all,
            "status_breakdown": overall_status,
        },
    }


# ═══════════════════════════════════════════════════════════════════════════
# Section 11: Policy Directives Status
# ═══════════════════════════════════════════════════════════════════════════

def _assemble_directives_status():
    """Policy directive tracking — implementation status and compliance deadlines."""
    directives = _items(_tracker_get("/policy-directives", {"limit": "100"}))
    today = date.today()

    if not directives:
        return {"has_data": False, "message": "No policy directives tracked."}

    by_status = {}
    overdue = []
    upcoming = []

    for d in directives:
        impl = d.get("implementation_status", "pending")
        by_status[impl] = by_status.get(impl, 0) + 1

        deadline = d.get("compliance_deadline")
        if deadline and impl not in ("implemented", "superseded"):
            try:
                dl_date = date.fromisoformat(deadline)
                days_remaining = (dl_date - today).days
                item = {
                    "title": d.get("directive_title", ""),
                    "source_type": d.get("source_document_type", ""),
                    "issued_by": d.get("issuing_authority", ""),
                    "deadline": deadline,
                    "days_remaining": days_remaining,
                    "status": impl,
                    "priority": d.get("priority_level", ""),
                }
                if days_remaining < 0:
                    overdue.append(item)
                elif days_remaining <= 30:
                    upcoming.append(item)
            except (ValueError, TypeError):
                pass

    overdue.sort(key=lambda x: x["days_remaining"])
    upcoming.sort(key=lambda x: x["days_remaining"])

    return {
        "has_data": True,
        "total": len(directives),
        "by_status": by_status,
        "overdue": overdue,
        "upcoming": upcoming,
    }


# ═══════════════════════════════════════════════════════════════════════════
# Main Assembly
# ═══════════════════════════════════════════════════════════════════════════

def assemble_weekly_data(db):
    """Assemble all 10 sections of the weekly brief."""
    today = date.today()
    logger.info("Assembling weekly brief for week of %s", today.isoformat())

    data = {
        "date": today.isoformat(),
        "date_display": f"Week of {today.strftime('%B %d, %Y')}",
        "calibration": _assemble_calibration(db),
        "portfolio": _assemble_portfolio(),
        "decisions": _assemble_decisions(),
        "team": _assemble_team(),
        "stakeholders": _assemble_stakeholders(),
        "deadlines": _assemble_deadlines(),
        "documents": _assemble_documents(),
        "risks": _assemble_risks(),
        "hygiene": _assemble_hygiene(),
        "comment_progress": _assemble_comment_progress(),
        "directives_status": _assemble_directives_status(),
        "executive_summary": None,  # Filled by Sonnet
    }

    comment_totals = data["comment_progress"]["totals"]
    logger.info(
        "Weekly data: %d matters, %d decisions, %d touchpoints, hygiene=%d%%, %d topics across %d rulemakings, %d directives",
        data["portfolio"]["total_active"],
        len(data["decisions"]),
        len(data["stakeholders"]["touchpoints_due"]),
        data["hygiene"]["score"],
        comment_totals["total_topics"],
        comment_totals["matters_with_topics"],
        data["directives_status"].get("total", 0),
    )
    return data


def add_executive_summary(data, llm_client):
    """Generate Sonnet executive summary for the weekly brief."""
    if not llm_client:
        return data

    # Build context for Sonnet
    portfolio = data.get("portfolio", {})
    calibration = data.get("calibration", {})
    team = data.get("team", {})
    hygiene = data.get("hygiene", {})
    decisions = data.get("decisions", [])
    stakeholders = data.get("stakeholders", {})

    context_parts = []

    # Calibration
    if calibration.get("has_data"):
        context_parts.append(
            f"Last week's brief accuracy: {calibration['score']}% "
            f"({calibration['materialized']} materialized, {calibration['resolved']} resolved, "
            f"{calibration.get('wrong', 0)} wrong out of {calibration['total_flags']} flags)"
        )

    # Portfolio
    context_parts.append(
        f"Portfolio: {len(portfolio.get('critical', []))} critical, "
        f"{len(portfolio.get('important', []))} important, "
        f"{len(portfolio.get('strategic', []))} strategic, "
        f"{len(portfolio.get('monitoring', []))} monitoring"
    )
    for m in portfolio.get("critical", [])[:5]:
        context_parts.append(f"  CRITICAL: {m['title']} — {m.get('status', '')} — deadline {m.get('nearest_deadline', 'none')}")

    # Decisions
    context_parts.append(f"Open decisions: {len(decisions)}")
    for d in decisions[:5]:
        context_parts.append(f"  {d['title']} — owner: {d.get('decision_owner', 'unassigned')} — due: {d.get('due_date', 'no date')}")

    # Team
    drifting = team.get("drifting_matters", [])
    if drifting:
        context_parts.append(f"Drifting matters (no update 14+ days): {len(drifting)}")
        for dm in drifting[:3]:
            context_parts.append(f"  {dm['title']} — {dm['days_stale']} days stale — owner: {dm.get('owner', '')}")

    # Stakeholders
    neglected = stakeholders.get("neglected", [])
    if neglected:
        context_parts.append(f"Neglected key relationships: {len(neglected)}")

    # Hygiene
    context_parts.append(f"Data hygiene score: {hygiene.get('score', 0)}%")

    # Comment progress
    comment = data.get("comment_progress", {})
    comment_totals = comment.get("totals", {})
    if comment_totals.get("total_topics", 0) > 0:
        sb = comment_totals.get("status_breakdown", {})
        context_parts.append(
            f"Rulemaking comments: {comment_totals['total_topics']} topics across "
            f"{comment_totals['matters_with_topics']} matters — "
            f"{sb.get('position_taken', 0)} positions taken, "
            f"{sb.get('drafting', 0) + sb.get('final_review', 0)} in progress, "
            f"{sb.get('open', 0) + sb.get('not_started', 0)} not started"
        )
        for cm in comment.get("matters", [])[:3]:
            dr = cm.get("days_remaining")
            dr_str = f"{dr} days remaining" if dr is not None else "no deadline"
            context_parts.append(
                f"  {cm['matter_title'][:50]}: {cm['total_topics']} topics, "
                f"{cm['completion_pct']}% complete, {dr_str}"
            )

    # Directives
    dir_data = data.get("directives_status", {})
    if dir_data.get("has_data"):
        context_parts.append(f"Policy directives: {dir_data['total']} tracked")
        if dir_data.get("overdue"):
            context_parts.append(f"  {len(dir_data['overdue'])} overdue directives")

    context = "\n".join(context_parts)

    prompt = f"""You are the AI chief of staff for a CFTC Deputy General Counsel. Write a concise executive summary (4-6 sentences) for this week's management brief.

This week's data:
{context}

Focus on:
1. What moved this week (or didn't)
2. What is on track vs at risk
3. What needs leadership attention next week
4. What requires reprioritization

Write as a confident, direct chief-of-staff note. No preamble, no bullet points — flowing prose. Be specific about matters and people by name."""

    try:
        # Use call_llm since there's no call_sonnet shortcut
        from app.llm.client import call_llm
        import asyncio
        result = asyncio.get_event_loop().run_until_complete(
            call_llm(
                prompt=prompt,
                model="claude-sonnet-4-20250514",
                purpose="weekly_brief_summary",
                max_tokens=500,
            )
        )
        summary = ""
        for block in result.get("content", []):
            if hasattr(block, "text"):
                summary += block.text
            elif isinstance(block, dict) and "text" in block:
                summary += block["text"]
        data["executive_summary"] = summary.strip()
        logger.info("Sonnet executive summary generated (%d chars)", len(data["executive_summary"]))
    except Exception as e:
        logger.error("Sonnet executive summary failed: %s", e, exc_info=True)
        data["executive_summary"] = None

    return data


def generate_weekly_brief(db, llm_client=None):
    """Full weekly brief generation pipeline."""
    data = assemble_weekly_data(db)
    if llm_client:
        data = add_executive_summary(data, llm_client)
    return data
