"""
AI Intelligence router — Phase 2 Sonnet integration endpoints.
All endpoints are POST because they trigger expensive Sonnet API calls.
"""

import calendar
import json
import sqlite3
from datetime import date, datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.database import get_db
from app.models import (
    OutreachPlanResponse,
    OutreachGenerateResponse,
    HappyHourSuggestion,
    HappyHourSuggestResponse,
    FollowUpAnalysis,
    LinkedInEventResponse,
    LinkedInScanResult,
    IntroSuggestion,
    IntroSuggestResponse,
)
from app.routers.contacts import row_to_contact
from app.routers.interactions import row_to_interaction
from app.routers.linkedin import row_to_linkedin_event
from app.routers.outreach import row_to_outreach, get_current_week_monday
from app.sonnet import call_sonnet, parse_json_response
from app.prompts import thursday_outreach, professional_pulse, happy_hour, follow_up, linkedin_scan
from app.services.outreach_service import (
    generate_thursday_plans,
    generate_professional_plans,
    fetch_social_contacts,
    fetch_recent_interactions,
    fetch_open_loops,
    fetch_unprocessed_linkedin_events,
    fetch_recent_happy_hours,
    create_outreach_plan_record,
    mark_linkedin_events_used,
    fetch_professional_contacts,
)

router = APIRouter()


# ── Helper: fetch data for prompts ────────────────────────────────────

def _fetch_social_contacts(db: sqlite3.Connection) -> list[dict]:
    """Fetch all social contacts."""
    rows = db.execute(
        "SELECT * FROM contacts WHERE contact_type = 'social' ORDER BY name ASC"
    ).fetchall()
    return [row_to_contact(r) for r in rows]


def _fetch_professional_contacts(db: sqlite3.Connection) -> list[dict]:
    """Fetch all professional contacts."""
    rows = db.execute(
        "SELECT * FROM contacts WHERE contact_type = 'professional' ORDER BY name ASC"
    ).fetchall()
    return [row_to_contact(r) for r in rows]


def _fetch_recent_interactions(db: sqlite3.Connection, days: int = 30, contact_type: str = None) -> list[dict]:
    """Fetch recent interactions, optionally filtered by contact type."""
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


def _fetch_open_loops(db: sqlite3.Connection) -> list[dict]:
    """Fetch all interactions with open loops."""
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


def _fetch_unprocessed_linkedin_events(db: sqlite3.Connection, contact_type: str = None) -> list[dict]:
    """Fetch unprocessed LinkedIn events, optionally filtered by contact type."""
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


def _fetch_recent_happy_hours(db: sqlite3.Connection, limit: int = 3) -> list[dict]:
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


def _create_outreach_plan_record(
    db: sqlite3.Connection,
    week_of: str,
    contact_id: int,
    message_draft: str,
    reasoning: str,
    message_type: str,
    plan_type: str,
) -> dict:
    """Insert an outreach plan record and return it with contact name."""
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


def _mark_linkedin_events_used(db: sqlite3.Connection, contact_ids: list[int]):
    """Mark LinkedIn events as used in outreach for the given contact IDs."""
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


# ── Endpoints ─────────────────────────────────────────────────────────

@router.post("/outreach/generate", response_model=OutreachGenerateResponse)
async def generate_thursday_outreach(
    force: bool = Query(default=False, description="Force regeneration even if plans exist for this week"),
    db: sqlite3.Connection = Depends(get_db),
):
    """
    Generate Thursday social outreach plan via Sonnet.
    Idempotent: returns existing plans for current week unless force=True.
    """
    try:
        result = await generate_thursday_plans(db, force=force)
    except ValueError as e:
        raise HTTPException(status_code=502, detail=str(e))

    if not result.get("plans") and not result.get("existing"):
        if "No social contacts" in result.get("reasoning", ""):
            raise HTTPException(status_code=404, detail="No social contacts found in database")

    return OutreachGenerateResponse(
        plans=result.get("plans", []),
        reasoning=result.get("reasoning", ""),
    )


@router.post("/professional/generate", response_model=OutreachGenerateResponse)
async def generate_professional_pulse_endpoint(
    force: bool = Query(default=False, description="Force regeneration even if plans exist for this month"),
    db: sqlite3.Connection = Depends(get_db),
):
    """
    Generate monthly Professional Pulse outreach plan via Sonnet.
    Idempotent: returns existing plans for current month unless force=True.
    """
    try:
        result = await generate_professional_plans(db, force=force)
    except ValueError as e:
        raise HTTPException(status_code=502, detail=str(e))

    if not result.get("plans") and not result.get("existing"):
        if "No professional contacts" in result.get("reasoning", ""):
            raise HTTPException(status_code=404, detail="No professional contacts found in database")

    return OutreachGenerateResponse(
        plans=result.get("plans", []),
        reasoning=result.get("reasoning", ""),
    )


@router.post("/happy-hour/suggest", response_model=HappyHourSuggestResponse)
async def suggest_happy_hour_group(db: sqlite3.Connection = Depends(get_db)):
    """
    Get Sonnet's suggested group for this week's happy hour.
    Returns 4-5 invitee suggestions with role assignments and reasoning.
    """
    contacts = fetch_social_contacts(db)
    if not contacts:
        raise HTTPException(status_code=404, detail="No social contacts found in database")

    interactions = fetch_recent_interactions(db, days=30, contact_type="social")
    recent_happy_hours = fetch_recent_happy_hours(db, limit=3)
    today = date.today().isoformat()

    user_prompt = happy_hour.build_user_prompt(
        contacts=contacts,
        interactions=interactions,
        recent_happy_hours=recent_happy_hours,
        today=today,
    )

    try:
        raw_response = await call_sonnet(happy_hour.SYSTEM_PROMPT, user_prompt)
        result = parse_json_response(raw_response)
    except (RuntimeError, ValueError) as e:
        raise HTTPException(status_code=502, detail=f"Sonnet API error: {str(e)}")

    if not isinstance(result, dict):
        raise HTTPException(
            status_code=502,
            detail="Sonnet returned an unexpected format. Expected a JSON object.",
        )

    # Build a contact name lookup
    contact_lookup = {c["id"]: c["name"] for c in contacts}

    # Parse suggestions and attach contact names
    suggestions = []
    for s in result.get("suggestions", []):
        cid = s.get("contact_id")
        contact_name = contact_lookup.get(cid, "Unknown")
        suggestions.append(HappyHourSuggestion(
            contact_id=cid,
            contact_name=contact_name,
            role=s.get("role", "new_edge"),
            reasoning=s.get("reasoning", ""),
        ))

    return HappyHourSuggestResponse(
        suggestions=suggestions,
        theme_suggestion=result.get("theme_suggestion"),
        group_reasoning=result.get("group_reasoning", ""),
    )


@router.post("/follow-up/analyze", response_model=FollowUpAnalysis)
async def analyze_interaction(
    interaction_id: int,
    db: sqlite3.Connection = Depends(get_db),
):
    """
    Analyze an interaction and extract follow-up intelligence.
    Returns open loops, new interests, intro suggestions, and suggested follow-up date.
    """
    # Fetch the interaction
    interaction_row = db.execute(
        """
        SELECT i.*, c.name as contact_name
        FROM interactions i
        JOIN contacts c ON i.contact_id = c.id
        WHERE i.id = ?
        """,
        [interaction_id],
    ).fetchone()
    if interaction_row is None:
        raise HTTPException(status_code=404, detail="Interaction not found")

    interaction = row_to_interaction(interaction_row)

    # Fetch the contact
    contact_row = db.execute(
        "SELECT * FROM contacts WHERE id = ?",
        [interaction["contact_id"]],
    ).fetchone()
    if contact_row is None:
        raise HTTPException(status_code=404, detail="Contact not found for this interaction")

    contact = row_to_contact(contact_row)
    today = date.today().isoformat()

    user_prompt = follow_up.build_user_prompt(
        interaction=interaction,
        contact=contact,
        today=today,
    )

    try:
        raw_response = await call_sonnet(follow_up.SYSTEM_PROMPT, user_prompt)
        result = parse_json_response(raw_response)
    except (RuntimeError, ValueError) as e:
        raise HTTPException(status_code=502, detail=f"Sonnet API error: {str(e)}")

    if not isinstance(result, dict):
        raise HTTPException(
            status_code=502,
            detail="Sonnet returned an unexpected format. Expected a JSON object.",
        )

    return FollowUpAnalysis(
        open_loops=result.get("open_loops", []),
        new_interests=result.get("new_interests", []),
        intro_suggestions=result.get("intro_suggestions", []),
        suggested_follow_up_date=result.get("suggested_follow_up_date"),
    )


@router.post("/linkedin/scan", response_model=LinkedInScanResult)
async def trigger_linkedin_scan(db: sqlite3.Connection = Depends(get_db)):
    """
    Trigger LinkedIn scan for all contacts due for a check based on tier frequency.
    - Cornerstone: every 7 days
    - Developing: every 14 days
    - New/Dormant: every 30 days

    NOTE: Currently uses Sonnet with stored data analysis only.
    TODO: Integrate web search when Anthropic supports tool_use with web_search.
    """
    today_date = date.today()
    today = today_date.isoformat()

    # Tier-based scan frequency (days)
    tier_frequency = {
        "Cornerstone": 7,
        "Developing": 14,
        "New": 30,
        "Dormant": 30,
    }

    due_contacts = []
    for tier, days in tier_frequency.items():
        cutoff = (today_date - timedelta(days=days)).isoformat()
        rows = db.execute(
            """
            SELECT * FROM contacts
            WHERE tier = ?
              AND linkedin_url IS NOT NULL
              AND linkedin_url != ''
              AND (linkedin_last_checked IS NULL OR linkedin_last_checked <= ?)
            ORDER BY linkedin_last_checked ASC
            """,
            [tier, cutoff],
        ).fetchall()
        due_contacts.extend([row_to_contact(r) for r in rows])

    if not due_contacts:
        return LinkedInScanResult(
            contacts_scanned=0,
            events_detected=0,
            high_significance=0,
            events=[],
        )

    all_events = []
    contacts_scanned = 0

    for contact in due_contacts:
        user_prompt = linkedin_scan.build_user_prompt(contact=contact, today=today)

        try:
            raw_response = await call_sonnet(linkedin_scan.SYSTEM_PROMPT, user_prompt)
            result = parse_json_response(raw_response)
        except (RuntimeError, ValueError):
            # If one contact fails, continue with the rest
            continue

        contacts_scanned += 1

        if not isinstance(result, dict):
            continue

        # Update linkedin_last_checked
        db.execute(
            "UPDATE contacts SET linkedin_last_checked = ? WHERE id = ?",
            [today, contact["id"]],
        )

        # Update headline if changed
        if result.get("headline_changed") and result.get("new_headline"):
            db.execute(
                "UPDATE contacts SET linkedin_headline = ?, updated_at = datetime('now') WHERE id = ?",
                [result["new_headline"], contact["id"]],
            )

        # Store detected events
        for event in result.get("events", []):
            cursor = db.execute(
                """
                INSERT INTO linkedin_events (
                    contact_id, detected_date, event_type, significance,
                    description, outreach_hook, opportunity_flag
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    contact["id"],
                    today,
                    event.get("event_type", "general_activity"),
                    event.get("significance", "medium"),
                    event.get("description", ""),
                    event.get("outreach_hook"),
                    event.get("opportunity_flag"),
                ],
            )
            new_id = cursor.lastrowid

            # Fetch the created event with contact name
            event_row = db.execute(
                """
                SELECT le.*, c.name as contact_name
                FROM linkedin_events le
                JOIN contacts c ON le.contact_id = c.id
                WHERE le.id = ?
                """,
                [new_id],
            ).fetchone()
            all_events.append(LinkedInEventResponse(**row_to_linkedin_event(event_row)))

    db.commit()

    high_sig_count = sum(1 for e in all_events if e.significance == "high")

    return LinkedInScanResult(
        contacts_scanned=contacts_scanned,
        events_detected=len(all_events),
        high_significance=high_sig_count,
        events=all_events,
    )


@router.post("/linkedin/scan/{contact_id}", response_model=LinkedInScanResult)
async def scan_single_contact(contact_id: int, db: sqlite3.Connection = Depends(get_db)):
    """
    Scan a single contact's LinkedIn on demand, regardless of when they were last checked.
    """
    contact_row = db.execute(
        "SELECT * FROM contacts WHERE id = ?", [contact_id]
    ).fetchone()
    if contact_row is None:
        raise HTTPException(status_code=404, detail="Contact not found")

    contact = row_to_contact(contact_row)
    today = date.today().isoformat()

    if not contact.get("linkedin_url"):
        raise HTTPException(
            status_code=400,
            detail="Contact does not have a LinkedIn URL. Add one before scanning.",
        )

    user_prompt = linkedin_scan.build_user_prompt(contact=contact, today=today)

    try:
        raw_response = await call_sonnet(linkedin_scan.SYSTEM_PROMPT, user_prompt)
        result = parse_json_response(raw_response)
    except (RuntimeError, ValueError) as e:
        raise HTTPException(status_code=502, detail=f"Sonnet API error: {str(e)}")

    if not isinstance(result, dict):
        raise HTTPException(
            status_code=502,
            detail="Sonnet returned an unexpected format. Expected a JSON object.",
        )

    # Update linkedin_last_checked
    db.execute(
        "UPDATE contacts SET linkedin_last_checked = ? WHERE id = ?",
        [today, contact["id"]],
    )

    # Update headline if changed
    if result.get("headline_changed") and result.get("new_headline"):
        db.execute(
            "UPDATE contacts SET linkedin_headline = ?, updated_at = datetime('now') WHERE id = ?",
            [result["new_headline"], contact["id"]],
        )

    # Store detected events
    created_events = []
    for event in result.get("events", []):
        cursor = db.execute(
            """
            INSERT INTO linkedin_events (
                contact_id, detected_date, event_type, significance,
                description, outreach_hook, opportunity_flag
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                contact["id"],
                today,
                event.get("event_type", "general_activity"),
                event.get("significance", "medium"),
                event.get("description", ""),
                event.get("outreach_hook"),
                event.get("opportunity_flag"),
            ],
        )
        new_id = cursor.lastrowid

        event_row = db.execute(
            """
            SELECT le.*, c.name as contact_name
            FROM linkedin_events le
            JOIN contacts c ON le.contact_id = c.id
            WHERE le.id = ?
            """,
            [new_id],
        ).fetchone()
        created_events.append(LinkedInEventResponse(**row_to_linkedin_event(event_row)))

    db.commit()

    high_sig_count = sum(1 for e in created_events if e.significance == "high")

    return LinkedInScanResult(
        contacts_scanned=1,
        events_detected=len(created_events),
        high_significance=high_sig_count,
        events=created_events,
    )


@router.post("/intros/suggest", response_model=IntroSuggestResponse)
async def suggest_intros(db: sqlite3.Connection = Depends(get_db)):
    """
    Get Sonnet's intro recommendations by scanning the full contact database
    for complementary connections worth introducing to each other.
    """
    # Fetch all contacts (both social and professional)
    all_rows = db.execute(
        "SELECT * FROM contacts ORDER BY name ASC"
    ).fetchall()
    all_contacts = [row_to_contact(r) for r in all_rows]

    if len(all_contacts) < 2:
        raise HTTPException(
            status_code=400,
            detail="Need at least 2 contacts to suggest introductions.",
        )

    # Fetch existing intros to avoid re-suggesting
    existing_intros = db.execute(
        "SELECT person_a_id, person_b_id FROM intros"
    ).fetchall()
    existing_pairs = set()
    for row in existing_intros:
        pair = tuple(sorted([row["person_a_id"], row["person_b_id"]]))
        existing_pairs.add(pair)

    # Build a compact contact summary for the prompt
    contact_lines = []
    for c in all_contacts:
        parts = [
            f"ID:{c['id']}",
            f"Name:{c['name']}",
            f"Type:{c.get('contact_type', 'social')}",
            f"Tier:{c['tier']}",
            f"Domain:{c.get('domain', 'N/A')}",
            f"Role:{c.get('current_role', 'N/A')}",
            f"Interests:{c.get('interests', 'N/A')}",
            f"TheirGoals:{c.get('their_goals', 'N/A')}",
        ]
        contact_lines.append(" | ".join(parts))

    existing_intro_str = "None" if not existing_pairs else ", ".join(
        f"({a},{b})" for a, b in existing_pairs
    )

    system_prompt = """You are a relationship connector analyst. Your job is to scan a contact database and identify 1-2 pairs of people who would benefit from being introduced to each other.

YOUR OUTPUT must be a JSON object with a "suggestions" array. Each suggestion has:
- "person_a_id" (int): database ID of the first person
- "person_b_id" (int): database ID of the second person
- "reasoning" (string): why these two should meet — what shared interests, complementary goals, or mutual value exists
- "shared_context" (string): a suggested intro context or message framing

RULES:
- Only suggest introductions that create genuine mutual value
- Look for complementary domains (e.g., policy + industry), shared interests, or aligned goals
- Do NOT suggest pairs that already exist in the "already introduced" list
- Maximum 2 suggestions — quality over quantity
- Each person should appear in at most 1 suggestion

OUTPUT FORMAT: Return ONLY valid JSON. No markdown code fences."""

    user_prompt = f"""CONTACTS DATABASE:
{chr(10).join(contact_lines)}

ALREADY INTRODUCED PAIRS (do not re-suggest):
{existing_intro_str}

Suggest 1-2 introduction pairs as a JSON object with a "suggestions" array."""

    try:
        raw_response = await call_sonnet(system_prompt, user_prompt)
        result = parse_json_response(raw_response)
    except (RuntimeError, ValueError) as e:
        raise HTTPException(status_code=502, detail=f"Sonnet API error: {str(e)}")

    if not isinstance(result, dict):
        raise HTTPException(
            status_code=502,
            detail="Sonnet returned an unexpected format. Expected a JSON object.",
        )

    # Build contact name lookup
    contact_lookup = {c["id"]: c["name"] for c in all_contacts}
    valid_ids = set(contact_lookup.keys())

    suggestions = []
    for s in result.get("suggestions", []):
        a_id = s.get("person_a_id")
        b_id = s.get("person_b_id")
        if a_id not in valid_ids or b_id not in valid_ids:
            continue
        # Skip if already introduced
        pair = tuple(sorted([a_id, b_id]))
        if pair in existing_pairs:
            continue

        suggestions.append(IntroSuggestion(
            person_a_id=a_id,
            person_a_name=contact_lookup.get(a_id, "Unknown"),
            person_b_id=b_id,
            person_b_name=contact_lookup.get(b_id, "Unknown"),
            reasoning=s.get("reasoning", ""),
            shared_context=s.get("shared_context"),
        ))

    return IntroSuggestResponse(suggestions=suggestions)
