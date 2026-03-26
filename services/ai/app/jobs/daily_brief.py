"""Daily brief data assembly and generation.

Queries tracker and AI databases to assemble the 7-section daily brief:
1. What Changed Overnight (system_events delta)
2. Today's Action List (merged priority: boss, deadline, blocked, overdue, review)
3. Today's Meetings (with Haiku prep narratives)
4. Follow-Ups Due (people + uncommitted action items)
5. Team Pulse (overdue by assignee, waiting, overload)
6. Comment Deadlines (comment periods closing within 30 days + topic progress)
7. Directives Watch (new or approaching-deadline directives)

Cost: ~$0.02/day (one Haiku call for meeting prep narratives).
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import date, datetime, timedelta

import httpx

logger = logging.getLogger(__name__)

TRACKER_BASE_URL = os.environ.get("TRACKER_BASE_URL", "http://localhost:8004/tracker")
TRACKER_USER = os.environ.get("TRACKER_USER", "")
TRACKER_PASS = os.environ.get("TRACKER_PASS", "")


def _tracker_get(path: str, params: dict | None = None) -> dict | list:
    """GET request to tracker service."""
    url = f"{TRACKER_BASE_URL}{path}"
    auth = (TRACKER_USER, TRACKER_PASS) if TRACKER_USER else None
    try:
        r = httpx.get(url, auth=auth, params=params, timeout=30)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        logger.error("Tracker GET %s failed: %s", path, e)
        return {}


def _get_last_brief_time(db) -> str:
    """Get timestamp of last daily brief, or 24 hours ago."""
    row = db.execute(
        "SELECT created_at FROM intelligence_briefs WHERE brief_type = 'daily' ORDER BY created_at DESC LIMIT 1"
    ).fetchone()
    if row:
        return row["created_at"]
    return (datetime.utcnow() - timedelta(hours=24)).isoformat()


def _assemble_what_changed(db, since: str) -> list[dict]:
    """Section 1: system_events since last brief."""
    # Query tracker for recent events
    events = _tracker_get("/system-events", {"since": since, "limit": "100"})
    if isinstance(events, dict):
        events = events.get("items", [])

    changes = []
    for ev in events:
        changes.append(
            {
                "entity_type": ev.get("entity_type", "unknown"),
                "entity_id": ev.get("entity_id"),
                "action": ev.get("action", ""),
                "changed_fields": ev.get("changed_fields"),
                "summary": _summarize_event(ev),
                "timestamp": ev.get("created_at"),
            }
        )
    return changes


def _summarize_event(ev: dict) -> str:
    """Human-readable one-line summary of a system event."""
    action = ev.get("action", "")
    entity = ev.get("entity_type", "")
    name = ev.get("entity_name", ev.get("entity_id", "")[:8])
    fields = ev.get("changed_fields")

    if action == "create":
        return f"New {entity}: {name}"
    elif action == "update" and fields:
        field_list = ", ".join(fields) if isinstance(fields, list) else str(fields)
        return f"Updated {entity} '{name}': {field_list}"
    elif action == "delete":
        return f"Deleted {entity}: {name}"
    return f"{action} {entity}: {name}"


def _assemble_action_list(db) -> list[dict]:
    """Section 2: merged priority action list."""
    intel_data = _tracker_get("/ai-context/intelligence-data")
    if not intel_data:
        return []

    actions = []

    # Boss-touching items (highest priority)
    for d in intel_data.get("pending_decisions", []):
        actions.append(
            {
                "tag": "BOSS",
                "priority": 0,
                "title": d.get("title", "Untitled decision"),
                "matter": d.get("matter_title", ""),
                "detail": f"Owner: {d.get('owner_name', 'unassigned')}, Due: {d.get('due_date', 'no date')}",
                "entity_type": "decision",
                "entity_id": d.get("id"),
                "sort_key": d.get("due_date", "9999"),
            }
        )

    # Deadline items
    for m in intel_data.get("deadline_warnings", []):
        deadline = (
            m.get("work_deadline")
            or m.get("decision_deadline")
            or m.get("external_deadline")
            or ""
        )
        deadline_type = (
            "work"
            if m.get("work_deadline")
            else "decision"
            if m.get("decision_deadline")
            else "external"
        )
        actions.append(
            {
                "tag": "DEADLINE",
                "priority": 1,
                "title": m.get("title", ""),
                "matter": "",
                "detail": f"{deadline_type.title()} deadline: {deadline}, Owner: {m.get('owner_name', '')}",
                "entity_type": "matter",
                "entity_id": m.get("id"),
                "sort_key": deadline,
            }
        )

    # Overdue tasks
    for t in intel_data.get("overdue_tasks", []):
        days = t.get("days_overdue", 0)
        actions.append(
            {
                "tag": "OVERDUE",
                "priority": 3,
                "title": t.get("title", ""),
                "matter": t.get("matter_title", ""),
                "detail": f"Assigned: {t.get('assignee_name', 'unassigned')}, {days} days overdue",
                "entity_type": "task",
                "entity_id": t.get("id"),
                "sort_key": str(1000 - days).zfill(4),  # Most overdue first
            }
        )

    # Review-pending communications
    rows = db.execute(
        "SELECT id, title, processing_status, source_type, created_at FROM communications WHERE processing_status LIKE 'awaiting%'"
    ).fetchall()
    for row in rows:
        created = row["created_at"] or ""
        actions.append(
            {
                "tag": "REVIEW",
                "priority": 4,
                "title": row["title"] or f"{row['source_type']} communication",
                "matter": "",
                "detail": f"Stage: {row['processing_status']}, Since: {created[:10]}",
                "entity_type": "communication",
                "entity_id": row["id"],
                "sort_key": created,
            }
        )

    # Sort: by priority tier, then by sort_key within tier
    actions.sort(key=lambda a: (a["priority"], a["sort_key"]))
    return actions


def _assemble_meetings() -> list[dict]:
    """Section 3: today's meetings from tracker."""
    today = date.today().isoformat()
    meetings_data = _tracker_get("/meetings", {"date": today})
    if isinstance(meetings_data, dict):
        meetings_data = meetings_data.get("items", [])

    meetings = []
    for m in meetings_data:
        meetings.append(
            {
                "id": m.get("id"),
                "title": m.get("title", "Untitled"),
                "meeting_type": m.get("meeting_type", ""),
                "start_time": m.get("start_time", ""),
                "end_time": m.get("end_time", ""),
                "location": m.get("location", ""),
                "participants": m.get("participants", []),
                "linked_matters": m.get("matters", []),
                "prep_needed": m.get("prep_needed", False),
                "has_external": any(
                    p.get("is_external", False) for p in m.get("participants", [])
                ),
                "prep_narrative": None,  # Filled by Haiku in step 3
            }
        )
    return meetings


def _assemble_followups() -> list[dict]:
    """Section 4: people needing follow-up + uncommitted action items."""
    cutoff = (date.today() + timedelta(days=3)).isoformat()
    people = _tracker_get(
        "/people",
        {"next_interaction_before": cutoff, "sort": "next_interaction_needed_date"},
    )
    if isinstance(people, dict):
        people = people.get("items", [])

    followups = []
    for p in people:
        followups.append(
            {
                "person_id": p.get("id"),
                "name": p.get("full_name", ""),
                "organization": p.get("org_name", ""),
                "category": p.get("relationship_category", ""),
                "lane": p.get("relationship_category", ""),
                "next_date": p.get("next_interaction_needed_date", ""),
                "interaction_type": p.get("next_interaction_type", ""),
                "purpose": p.get("next_interaction_purpose", ""),
            }
        )
    return followups


def _assemble_team_pulse(intel_data: dict | None = None) -> dict:
    """Section 5: team execution summary."""
    if not intel_data:
        intel_data = _tracker_get("/ai-context/intelligence-data")

    overdue = intel_data.get("overdue_tasks", [])
    workload = intel_data.get("workload", [])

    # Group overdue by assignee
    by_assignee = {}
    for t in overdue:
        name = t.get("assignee_name", "Unassigned")
        by_assignee.setdefault(name, []).append(t.get("title", ""))

    # Find overloaded people
    overloaded = [w for w in workload if w.get("open_task_count", 0) > 8]

    return {
        "overdue_count": len(overdue),
        "overdue_by_assignee": {k: len(v) for k, v in by_assignee.items()},
        "overloaded_people": [
            {"name": w.get("full_name", ""), "task_count": w.get("open_task_count", 0)}
            for w in overloaded
        ],
    }


def _assemble_comment_deadlines() -> list[dict]:
    """Section 6: Comment periods closing within 30 days with topic progress."""
    today = date.today()
    horizon = (today + timedelta(days=30)).isoformat()
    matters = _tracker_get("/matters", {"limit": "200"})
    if isinstance(matters, dict):
        matters = matters.get("items", [])

    results = []
    for m in matters:
        status = m.get("status", "")
        if status in ("closed", "archived", "withdrawn"):
            continue
        deadline = m.get("external_deadline")
        if not deadline:
            continue
        # Include if:
        # - deadline in future and within 60 days (upcoming)
        # - OR deadline in past but within 30 days (recently expired, may still need work)
        past_cutoff = (today - timedelta(days=30)).isoformat()
        future_cutoff = (today + timedelta(days=60)).isoformat()
        if deadline < past_cutoff or deadline > future_cutoff:
            continue

        try:
            dl_date = date.fromisoformat(deadline)
            days_remaining = (dl_date - today).days
        except (ValueError, TypeError):
            continue

        # Fetch comment topics for this matter
        topics_resp = _tracker_get(f"/matters/{m['id']}/comment-topics")
        topics = topics_resp.get("items", []) if isinstance(topics_resp, dict) else []

        total_topics = len(topics)
        total_questions = 0
        status_counts = {}
        for t in topics:
            ps = t.get("position_status", "open")
            status_counts[ps] = status_counts.get(ps, 0) + 1
            # Count questions from nested list if present
            questions = t.get("questions", [])
            total_questions += len(questions)

        results.append(
            {
                "matter_id": m.get("id"),
                "matter_title": m.get("title", ""),
                "comment_deadline": deadline,
                "days_remaining": days_remaining,
                "total_topics": total_topics,
                "total_questions": total_questions,
                "status_counts": status_counts,
                "position_taken": status_counts.get("position_taken", 0),
                "owner": m.get("next_step_owner_name") or m.get("owner_name", ""),
                "priority": m.get("priority", ""),
            }
        )

    results.sort(key=lambda x: x["days_remaining"])
    return results


def _assemble_directives_watch() -> list[dict]:
    """Section 7: Policy directives with approaching deadlines or recent additions."""
    today = date.today()
    horizon = (today + timedelta(days=14)).isoformat()
    directives_resp = _tracker_get("/policy-directives", {"limit": "50"})
    directives = (
        directives_resp.get("items", []) if isinstance(directives_resp, dict) else []
    )

    watch_items = []
    for d in directives:
        impl_status = d.get("implementation_status", "")
        if impl_status in ("implemented", "superseded"):
            continue

        deadline = d.get("compliance_deadline")
        days_remaining = None
        if deadline:
            try:
                dl_date = date.fromisoformat(deadline)
                days_remaining = (dl_date - today).days
            except (ValueError, TypeError):
                pass

        # Include if deadline within 14 days or recently created (within 7 days)
        created = d.get("created_at", "")[:10]
        is_recent = (
            created >= (today - timedelta(days=7)).isoformat() if created else False
        )
        is_approaching = days_remaining is not None and 0 <= days_remaining <= 14

        if is_recent or is_approaching:
            watch_items.append(
                {
                    "id": d.get("id"),
                    "title": d.get("directive_title", ""),
                    "source_type": d.get("source_document_type", ""),
                    "issued_by": d.get("issuing_authority", ""),
                    "compliance_deadline": deadline,
                    "days_remaining": days_remaining,
                    "implementation_status": impl_status,
                    "priority_level": d.get("priority_level", ""),
                    "is_recent": is_recent,
                }
            )

    # Sort: approaching deadlines first, then recent additions
    watch_items.sort(
        key=lambda x: x["days_remaining"] if x["days_remaining"] is not None else 999
    )
    return watch_items


def assemble_daily_data(db) -> dict:
    """Assemble all 7 sections of the daily brief.

    Args:
        db: AI service database connection (sqlite3).

    Returns:
        Dict with keys: date, what_changed, action_list, meetings, followups, team_pulse.
    """
    since = _get_last_brief_time(db)
    today = date.today()

    logger.info(
        "Assembling daily brief for %s (delta since %s)", today.isoformat(), since[:19]
    )

    data = {
        "date": today.isoformat(),
        "date_display": today.strftime("%A, %B %d, %Y"),
        "what_changed": _assemble_what_changed(db, since),
        "action_list": _assemble_action_list(db),
        "meetings": _assemble_meetings(),
        "followups": _assemble_followups(),
        "team_pulse": _assemble_team_pulse(),
        "comment_deadlines": _assemble_comment_deadlines(),
        "directives_watch": _assemble_directives_watch(),
    }

    logger.info(
        "Daily data: %d changes, %d actions, %d meetings, %d follow-ups, %d comment deadlines, %d directives",
        len(data["what_changed"]),
        len(data["action_list"]),
        len(data["meetings"]),
        len(data["followups"]),
        len(data["comment_deadlines"]),
        len(data["directives_watch"]),
    )
    return data


def add_meeting_prep(data: dict, llm_client) -> dict:
    """Add Haiku prep narratives to meetings.

    Args:
        data: Daily brief data from assemble_daily_data().
        llm_client: LLM client instance with call_haiku() method.

    Returns:
        Same data dict with meetings[].prep_narrative populated.
    """
    meetings = data.get("meetings", [])
    if not meetings:
        return data

    for meeting in meetings:
        participants = meeting.get("participants", [])
        matters = meeting.get("linked_matters", [])

        if not participants and not matters:
            meeting["prep_narrative"] = None
            continue

        # Gather context for this meeting
        participant_names = [
            p.get("full_name", p.get("name", "")) for p in participants
        ]
        matter_titles = [m.get("title", "") for m in matters]

        # Fetch recent context notes for key participants
        context_snippets = []
        for p in participants[:5]:  # Limit to 5 to control prompt size
            pid = p.get("person_id", p.get("id"))
            if pid:
                notes = _tracker_get(f"/context-notes/by-entity/person/{pid}")
                if isinstance(notes, dict):
                    notes = notes.get("items", [])
                for note in notes[:3]:
                    excerpt = note.get("source_excerpt") or note.get("body", "")
                    if excerpt:
                        context_snippets.append(
                            f"[{note.get('category', '')}] About {p.get('full_name', '')}: {excerpt[:200]}"
                        )

        prompt = f"""Write 2-3 concise prep sentences for this meeting.

Meeting: {meeting.get("title", "")}
Type: {meeting.get("meeting_type", "")}
Participants: {", ".join(participant_names)}
Linked matters: {", ".join(matter_titles) if matter_titles else "None"}

Recent context:
{chr(10).join(context_snippets[:8]) if context_snippets else "No recent context notes."}

Focus on: who matters most in this meeting, what was committed last time, and what to watch for. Be specific and actionable. No preamble."""

        try:
            result = llm_client.call_haiku(prompt, purpose="daily_brief_prep")
            meeting["prep_narrative"] = result.get("content", "")
        except Exception as e:
            logger.warning("Haiku prep failed for meeting %s: %s", meeting.get("id"), e)
            meeting["prep_narrative"] = None

    return data


def generate_daily_brief(db, llm_client=None) -> dict:
    """Full daily brief generation pipeline.

    1. Assemble data from tracker + AI DBs
    2. Add Haiku meeting prep (if llm_client provided)
    3. Return data ready for rendering

    Args:
        db: AI service database connection.
        llm_client: Optional LLM client for meeting prep.

    Returns:
        Complete daily brief data dict.
    """
    data = assemble_daily_data(db)

    if llm_client and data.get("meetings"):
        data = add_meeting_prep(data, llm_client)

    return data


def store_brief(
    db,
    brief_type: str,
    brief_date: str,
    content: dict,
    docx_path: str | None = None,
    model_used: str | None = None,
) -> str:
    """Store a generated brief in the intelligence_briefs table.

    Returns the brief ID.
    """
    brief_id = str(uuid.uuid4())
    db.execute(
        """INSERT INTO intelligence_briefs (id, brief_type, brief_date, content, model_used, docx_file_path)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (brief_id, brief_type, brief_date, json.dumps(content), model_used, docx_path),
    )
    db.commit()
    logger.info("Stored %s brief %s for %s", brief_type, brief_id, brief_date)
    return brief_id
