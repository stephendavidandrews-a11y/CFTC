"""
Outreach generation service — core business logic extracted from ai.py.
Used by both HTTP endpoints and APScheduler jobs.
"""

import calendar
import sqlite3
from datetime import date, timedelta

from app.models import OutreachPlanResponse
from app.routers.contacts import row_to_contact
from app.routers.interactions import row_to_interaction
from app.routers.linkedin import row_to_linkedin_event
from app.routers.outreach import row_to_outreach, get_current_week_monday
from app.sonnet import call_sonnet, parse_json_response
from app.prompts import thursday_outreach, professional_pulse


# ── Shared data-fetch helpers ──────────────────────────────────────────

def fetch_social_contacts(db: sqlite3.Connection) -> list[dict]:
    rows = db.execute(
        "SELECT * FROM contacts WHERE contact_type = 'social' ORDER BY name ASC"
    ).fetchall()
    return [row_to_contact(r) for r in rows]


def fetch_professional_contacts(db: sqlite3.Connection) -> list[dict]:
    rows = db.execute(
        "SELECT * FROM contacts WHERE contact_type = 'professional' ORDER BY name ASC"
    ).fetchall()
    return [row_to_contact(r) for r in rows]


def fetch_recent_interactions(db: sqlite3.Connection, days: int = 30, contact_type: str = None) -> list[dict]:
    cutoff = (date.today() - timedelta(days=days)).isoformat()
    if contact_type:
        rows = db.execute(
            """
            SELECT i.*, c.name as contact_name
            FROM interactions i
            JOIN contacts c ON i.contact_id = c.id
            WHERE i.date >= ? AND c.contact_type = ?
            ORDER BY i.date DESC
            """,
            [cutoff, contact_type],
        ).fetchall()
    else:
        rows = db.execute(
            """
            SELECT i.*, c.name as contact_name
            FROM interactions i
            JOIN contacts c ON i.contact_id = c.id
            WHERE i.date >= ?
            ORDER BY i.date DESC
            """,
            [cutoff],
        ).fetchall()
    return [row_to_interaction(r) for r in rows]


def fetch_open_loops(db: sqlite3.Connection) -> list[dict]:
    rows = db.execute(
        """
        SELECT i.*, c.name as contact_name
        FROM interactions i
        JOIN contacts c ON i.contact_id = c.id
        WHERE i.open_loops IS NOT NULL AND i.open_loops != ''
        ORDER BY COALESCE(i.follow_up_date, '9999-12-31') ASC, i.date DESC
        """
    ).fetchall()
    return [row_to_interaction(r) for r in rows]


def fetch_unprocessed_linkedin_events(db: sqlite3.Connection, contact_type: str = None) -> list[dict]:
    if contact_type:
        rows = db.execute(
            """
            SELECT le.*, c.name as contact_name
            FROM linkedin_events le
            JOIN contacts c ON le.contact_id = c.id
            WHERE le.used_in_outreach = 0 AND le.dismissed = 0
              AND c.contact_type = ?
            ORDER BY le.detected_date DESC
            """,
            [contact_type],
        ).fetchall()
    else:
        rows = db.execute(
            """
            SELECT le.*, c.name as contact_name
            FROM linkedin_events le
            JOIN contacts c ON le.contact_id = c.id
            WHERE le.used_in_outreach = 0 AND le.dismissed = 0
            ORDER BY le.detected_date DESC
            """
        ).fetchall()
    return [row_to_linkedin_event(r) for r in rows]


def fetch_recent_happy_hours(db: sqlite3.Connection, limit: int = 3) -> list[dict]:
    """Fetch recent happy hours with attendees."""
    hh_rows = db.execute(
        """
        SELECT hh.*, v.name as venue_name
        FROM happy_hours hh
        LEFT JOIN venues v ON hh.venue_id = v.id
        ORDER BY hh.date DESC
        LIMIT ?
        """,
        [limit],
    ).fetchall()

    results = []
    for hh_row in hh_rows:
        hh = {
            "id": hh_row["id"],
            "date": hh_row["date"],
            "theme": hh_row["theme"],
        }
        att_rows = db.execute(
            """
            SELECT a.*, c.name as contact_name
            FROM happy_hour_attendees a
            JOIN contacts c ON a.contact_id = c.id
            WHERE a.happy_hour_id = ?
            """,
            [hh_row["id"]],
        ).fetchall()
        hh["attendees"] = [
            {"contact_id": a["contact_id"], "contact_name": a["contact_name"]}
            for a in att_rows
        ]
        results.append(hh)
    return results


def create_outreach_plan_record(
    db: sqlite3.Connection,
    week_of: str,
    contact_id: int,
    message_draft: str,
    reasoning: str,
    message_type: str,
    plan_type: str,
) -> dict:
    cursor = db.execute(
        """
        INSERT INTO outreach_plans (week_of, contact_id, message_draft, reasoning, message_type, status, plan_type)
        VALUES (?, ?, ?, ?, ?, 'pending', ?)
        """,
        [week_of, contact_id, message_draft, reasoning, message_type, plan_type],
    )
    new_id = cursor.lastrowid
    row = db.execute(
        """
        SELECT op.*, c.name as contact_name, c.phone as contact_phone
        FROM outreach_plans op
        JOIN contacts c ON op.contact_id = c.id
        WHERE op.id = ?
        """,
        [new_id],
    ).fetchone()
    return row_to_outreach(row)


def mark_linkedin_events_used(db: sqlite3.Connection, contact_ids: list[int]):
    if not contact_ids:
        return
    placeholders = ",".join("?" for _ in contact_ids)
    db.execute(
        f"""
        UPDATE linkedin_events
        SET used_in_outreach = 1
        WHERE contact_id IN ({placeholders})
          AND used_in_outreach = 0
          AND dismissed = 0
        """,
        contact_ids,
    )


# ── Core generation functions (called by endpoints AND scheduler) ─────

async def generate_thursday_plans(db: sqlite3.Connection, force: bool = False) -> dict:
    """
    Generate Thursday social outreach plans.
    Returns {"plans": [...], "reasoning": "...", "count": N}.
    """
    monday = get_current_week_monday()

    # Idempotency check
    if not force:
        existing_rows = db.execute(
            """
            SELECT op.*, c.name as contact_name, c.phone as contact_phone
            FROM outreach_plans op
            JOIN contacts c ON op.contact_id = c.id
            WHERE op.week_of = ? AND op.plan_type = 'social_thursday'
            ORDER BY c.name ASC
            """,
            [monday],
        ).fetchall()
        if existing_rows:
            plans = [OutreachPlanResponse(**row_to_outreach(r)) for r in existing_rows]
            return {
                "plans": plans,
                "reasoning": "Returning existing plans for this week.",
                "count": len(plans),
                "existing": True,
            }

    # Force: delete existing
    if force:
        db.execute(
            "DELETE FROM outreach_plans WHERE week_of = ? AND plan_type = 'social_thursday'",
            [monday],
        )
        db.commit()

    # Gather data
    contacts = fetch_social_contacts(db)
    if not contacts:
        return {"plans": [], "reasoning": "No social contacts found.", "count": 0}

    interactions = fetch_recent_interactions(db, days=30, contact_type="social")
    open_loops = fetch_open_loops(db)
    linkedin_events = fetch_unprocessed_linkedin_events(db, contact_type="social")
    today = date.today().isoformat()

    user_prompt = thursday_outreach.build_user_prompt(
        contacts=contacts,
        interactions=interactions,
        open_loops=open_loops,
        linkedin_events=linkedin_events,
        today=today,
    )

    raw_response = await call_sonnet(thursday_outreach.SYSTEM_PROMPT, user_prompt)
    recommendations = parse_json_response(raw_response)

    if not isinstance(recommendations, list):
        raise ValueError("Sonnet returned unexpected format. Expected JSON array.")

    valid_contact_ids = {c["id"] for c in contacts}
    used_contact_ids = []
    created_plans = []

    for rec in recommendations:
        cid = rec.get("contact_id")
        if cid not in valid_contact_ids:
            continue
        plan_dict = create_outreach_plan_record(
            db=db,
            week_of=monday,
            contact_id=cid,
            message_draft=rec.get("message_draft", ""),
            reasoning=rec.get("reasoning", ""),
            message_type=rec.get("message_type", "weekend_checkin"),
            plan_type="social_thursday",
        )
        created_plans.append(OutreachPlanResponse(**plan_dict))
        used_contact_ids.append(cid)

    mark_linkedin_events_used(db, used_contact_ids)
    db.commit()

    return {
        "plans": created_plans,
        "reasoning": f"Generated {len(created_plans)} outreach plans for week of {monday}.",
        "count": len(created_plans),
    }


async def generate_professional_plans(db: sqlite3.Connection, force: bool = False) -> dict:
    """
    Generate monthly Professional Pulse outreach plans.
    Returns {"plans": [...], "reasoning": "...", "count": N}.
    """
    today_date = date.today()
    month_start = today_date.replace(day=1).isoformat()
    last_day = calendar.monthrange(today_date.year, today_date.month)[1]
    month_end = today_date.replace(day=last_day).isoformat()

    # Idempotency check
    if not force:
        existing_rows = db.execute(
            """
            SELECT op.*, c.name as contact_name, c.phone as contact_phone
            FROM outreach_plans op
            JOIN contacts c ON op.contact_id = c.id
            WHERE op.plan_type = 'professional_pulse'
              AND op.week_of >= ? AND op.week_of <= ?
            ORDER BY c.name ASC
            """,
            [month_start, month_end],
        ).fetchall()
        if existing_rows:
            plans = [OutreachPlanResponse(**row_to_outreach(r)) for r in existing_rows]
            return {
                "plans": plans,
                "reasoning": "Returning existing professional plans for this month.",
                "count": len(plans),
                "existing": True,
            }

    if force:
        db.execute(
            "DELETE FROM outreach_plans WHERE plan_type = 'professional_pulse' AND week_of >= ? AND week_of <= ?",
            [month_start, month_end],
        )
        db.commit()

    contacts = fetch_professional_contacts(db)
    if not contacts:
        return {"plans": [], "reasoning": "No professional contacts found.", "count": 0}

    interactions = fetch_recent_interactions(db, days=90, contact_type="professional")
    linkedin_events = fetch_unprocessed_linkedin_events(db, contact_type="professional")
    today = today_date.isoformat()

    user_prompt = professional_pulse.build_user_prompt(
        contacts=contacts,
        interactions=interactions,
        linkedin_events=linkedin_events,
        today=today,
    )

    raw_response = await call_sonnet(professional_pulse.SYSTEM_PROMPT, user_prompt)
    recommendations = parse_json_response(raw_response)

    if not isinstance(recommendations, list):
        raise ValueError("Sonnet returned unexpected format. Expected JSON array.")

    valid_contact_ids = {c["id"] for c in contacts}
    used_contact_ids = []
    created_plans = []

    for rec in recommendations:
        cid = rec.get("contact_id")
        if cid not in valid_contact_ids:
            continue
        plan_dict = create_outreach_plan_record(
            db=db,
            week_of=month_start,
            contact_id=cid,
            message_draft=rec.get("message_draft", ""),
            reasoning=rec.get("reasoning", ""),
            message_type=rec.get("message_type", "warm_reconnection"),
            plan_type="professional_pulse",
        )
        created_plans.append(OutreachPlanResponse(**plan_dict))
        used_contact_ids.append(cid)

    mark_linkedin_events_used(db, used_contact_ids)
    db.commit()

    return {
        "plans": created_plans,
        "reasoning": f"Generated {len(created_plans)} professional plans for {today_date.strftime('%B %Y')}.",
        "count": len(created_plans),
    }


async def check_due_contacts_and_generate(db: sqlite3.Connection) -> dict:
    """
    Check for social contacts going cold (14+ days since last contact)
    and generate ad-hoc outreach for them.
    Returns {"plans": [...], "count": N}.
    """
    today_date = date.today()
    monday = get_current_week_monday()
    cutoff = (today_date - timedelta(days=14)).isoformat()

    # Find social contacts going cold that don't already have pending/approved plans
    rows = db.execute(
        """
        SELECT c.* FROM contacts c
        WHERE c.contact_type = 'social'
          AND (c.last_contact_date IS NULL OR c.last_contact_date <= ?)
          AND c.id NOT IN (
            SELECT op.contact_id FROM outreach_plans op
            WHERE op.status IN ('pending', 'approved')
          )
        ORDER BY c.last_contact_date ASC
        LIMIT 5
        """,
        [cutoff],
    ).fetchall()

    cold_contacts = [row_to_contact(r) for r in rows]
    if not cold_contacts:
        return {"plans": [], "count": 0, "reasoning": "No contacts due for outreach."}

    # Get context for these contacts
    interactions = fetch_recent_interactions(db, days=60, contact_type="social")
    open_loops = fetch_open_loops(db)
    linkedin_events = fetch_unprocessed_linkedin_events(db, contact_type="social")
    today = today_date.isoformat()

    user_prompt = thursday_outreach.build_user_prompt(
        contacts=cold_contacts,
        interactions=interactions,
        open_loops=open_loops,
        linkedin_events=linkedin_events,
        today=today,
    )

    raw_response = await call_sonnet(thursday_outreach.SYSTEM_PROMPT, user_prompt)
    recommendations = parse_json_response(raw_response)

    if not isinstance(recommendations, list):
        return {"plans": [], "count": 0, "reasoning": "Sonnet returned unexpected format."}

    valid_contact_ids = {c["id"] for c in cold_contacts}
    used_contact_ids = []
    created_plans = []

    for rec in recommendations:
        cid = rec.get("contact_id")
        if cid not in valid_contact_ids:
            continue
        plan_dict = create_outreach_plan_record(
            db=db,
            week_of=monday,
            contact_id=cid,
            message_draft=rec.get("message_draft", ""),
            reasoning=rec.get("reasoning", ""),
            message_type=rec.get("message_type", "follow_up"),
            plan_type="ad_hoc_due",
        )
        created_plans.append(OutreachPlanResponse(**plan_dict))
        used_contact_ids.append(cid)

    mark_linkedin_events_used(db, used_contact_ids)
    db.commit()

    return {
        "plans": created_plans,
        "count": len(created_plans),
        "reasoning": f"Generated {len(created_plans)} ad-hoc outreach plans for cold contacts.",
    }


async def generate_happy_hour_invites(db: sqlite3.Connection) -> dict:
    """
    Check if there's a happy hour scheduled 9 days from now (next-next Tuesday).
    If so, generate invite messages for suggested attendees.
    """
    today_date = date.today()
    # Look for a happy hour exactly 9 days from now
    target_date = (today_date + timedelta(days=9)).isoformat()

    hh_row = db.execute(
        "SELECT * FROM happy_hours WHERE date = ?", [target_date]
    ).fetchone()

    if not hh_row:
        return {"plans": [], "count": 0, "reasoning": f"No happy hour scheduled for {target_date}."}

    hh_id = hh_row["id"]

    # Get attendees for this happy hour
    att_rows = db.execute(
        """
        SELECT a.*, c.name as contact_name, c.phone as contact_phone
        FROM happy_hour_attendees a
        JOIN contacts c ON a.contact_id = c.id
        WHERE a.happy_hour_id = ?
        """,
        [hh_id],
    ).fetchall()

    if not att_rows:
        return {"plans": [], "count": 0, "reasoning": "No attendees assigned to this happy hour yet."}

    # Generate invite messages for each attendee who hasn't been invited yet
    monday = get_current_week_monday()
    created_plans = []

    for att in att_rows:
        # Check if an invite plan already exists for this contact + happy hour
        existing = db.execute(
            """
            SELECT id FROM outreach_plans
            WHERE contact_id = ? AND plan_type = 'happy_hour_invite'
              AND week_of >= ? AND status != 'skipped'
            """,
            [att["contact_id"], (today_date - timedelta(days=14)).isoformat()],
        ).fetchone()

        if existing:
            continue  # Already invited

        venue_name = None
        if hh_row["venue_id"]:
            v_row = db.execute("SELECT name FROM venues WHERE id = ?", [hh_row["venue_id"]]).fetchone()
            venue_name = v_row["name"] if v_row else None

        # Create a personalized invite message
        theme = hh_row["theme"] or "happy hour"
        venue_str = f" at {venue_name}" if venue_name else ""
        message = f"Hey {att['contact_name'].split()[0]}! I'm putting together a {theme}{venue_str} next Tuesday ({target_date}). Would love for you to come hang! Let me know if you're in."

        plan_dict = create_outreach_plan_record(
            db=db,
            week_of=monday,
            contact_id=att["contact_id"],
            message_draft=message,
            reasoning=f"Happy hour invite for {target_date}. Role: {att.get('role', 'guest')}.",
            message_type="happy_hour_invite",
            plan_type="happy_hour_invite",
        )
        created_plans.append(OutreachPlanResponse(**plan_dict))

    db.commit()
    return {
        "plans": created_plans,
        "count": len(created_plans),
        "reasoning": f"Generated {len(created_plans)} happy hour invites for {target_date}.",
    }


async def generate_happy_hour_reminders(db: sqlite3.Connection) -> dict:
    """
    Check if there's a happy hour 2 days from now (upcoming Tuesday).
    If so, generate reminder messages for confirmed attendees.
    """
    today_date = date.today()
    target_date = (today_date + timedelta(days=2)).isoformat()

    hh_row = db.execute(
        "SELECT * FROM happy_hours WHERE date = ?", [target_date]
    ).fetchone()

    if not hh_row:
        return {"plans": [], "count": 0, "reasoning": f"No happy hour scheduled for {target_date}."}

    hh_id = hh_row["id"]

    # Get confirmed attendees
    att_rows = db.execute(
        """
        SELECT a.*, c.name as contact_name, c.phone as contact_phone
        FROM happy_hour_attendees a
        JOIN contacts c ON a.contact_id = c.id
        WHERE a.happy_hour_id = ? AND a.rsvp_status IN ('confirmed', 'attended')
        """,
        [hh_id],
    ).fetchall()

    if not att_rows:
        return {"plans": [], "count": 0, "reasoning": "No confirmed attendees for this happy hour."}

    monday = get_current_week_monday()
    created_plans = []

    for att in att_rows:
        # Check if a reminder already exists
        existing = db.execute(
            """
            SELECT id FROM outreach_plans
            WHERE contact_id = ? AND plan_type = 'happy_hour_reminder'
              AND week_of >= ? AND status != 'skipped'
            """,
            [att["contact_id"], (today_date - timedelta(days=7)).isoformat()],
        ).fetchone()

        if existing:
            continue

        venue_name = None
        if hh_row["venue_id"]:
            v_row = db.execute("SELECT name FROM venues WHERE id = ?", [hh_row["venue_id"]]).fetchone()
            venue_name = v_row["name"] if v_row else None

        venue_str = f" at {venue_name}" if venue_name else ""
        message = f"Hey {att['contact_name'].split()[0]}! Just a reminder about happy hour this Tuesday{venue_str}. Still good? Looking forward to it!"

        plan_dict = create_outreach_plan_record(
            db=db,
            week_of=monday,
            contact_id=att["contact_id"],
            message_draft=message,
            reasoning=f"Happy hour reminder for {target_date}.",
            message_type="happy_hour_invite",
            plan_type="happy_hour_reminder",
        )
        created_plans.append(OutreachPlanResponse(**plan_dict))

    db.commit()
    return {
        "plans": created_plans,
        "count": len(created_plans),
        "reasoning": f"Generated {len(created_plans)} happy hour reminders for {target_date}.",
    }


async def check_professional_due(db: sqlite3.Connection) -> dict:
    """
    Check professional contacts due for outreach based on tier cadence.
    If any are due and don't have pending plans, generate outreach.
    """
    today_date = date.today()
    tier_cadence = {
        "Tier 1": 30,
        "Tier 2": 42,
        "Tier 3": 90,
    }

    due_contacts = []
    for tier, days in tier_cadence.items():
        cutoff = (today_date - timedelta(days=days)).isoformat()
        rows = db.execute(
            """
            SELECT * FROM contacts
            WHERE contact_type = 'professional'
              AND professional_tier = ?
              AND (last_contact_date IS NULL OR last_contact_date <= ?)
              AND id NOT IN (
                SELECT contact_id FROM outreach_plans
                WHERE status IN ('pending', 'approved')
                  AND plan_type IN ('professional_pulse', 'ad_hoc_due')
              )
            ORDER BY last_contact_date ASC
            """,
            [tier, cutoff],
        ).fetchall()
        due_contacts.extend([row_to_contact(r) for r in rows])

    if not due_contacts:
        return {"plans": [], "count": 0, "reasoning": "No professional contacts due for outreach."}

    # Use existing professional pulse generation for these contacts
    interactions = fetch_recent_interactions(db, days=90, contact_type="professional")
    linkedin_events = fetch_unprocessed_linkedin_events(db, contact_type="professional")
    today = today_date.isoformat()
    monday = get_current_week_monday()

    user_prompt = professional_pulse.build_user_prompt(
        contacts=due_contacts,
        interactions=interactions,
        linkedin_events=linkedin_events,
        today=today,
    )

    raw_response = await call_sonnet(professional_pulse.SYSTEM_PROMPT, user_prompt)
    recommendations = parse_json_response(raw_response)

    if not isinstance(recommendations, list):
        return {"plans": [], "count": 0, "reasoning": "Sonnet returned unexpected format."}

    valid_contact_ids = {c["id"] for c in due_contacts}
    used_contact_ids = []
    created_plans = []

    for rec in recommendations:
        cid = rec.get("contact_id")
        if cid not in valid_contact_ids:
            continue
        plan_dict = create_outreach_plan_record(
            db=db,
            week_of=monday,
            contact_id=cid,
            message_draft=rec.get("message_draft", ""),
            reasoning=rec.get("reasoning", ""),
            message_type=rec.get("message_type", "warm_reconnection"),
            plan_type="ad_hoc_due",
        )
        created_plans.append(OutreachPlanResponse(**plan_dict))
        used_contact_ids.append(cid)

    mark_linkedin_events_used(db, used_contact_ids)
    db.commit()

    return {
        "plans": created_plans,
        "count": len(created_plans),
        "reasoning": f"Generated {len(created_plans)} professional outreach plans for due contacts.",
    }
