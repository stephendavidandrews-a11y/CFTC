"""Email participant resolution — resolve email addresses to tracker people.

Pipeline position: Runs as part of processing_attachments stage (after attachment extraction).

Collects all unique email addresses from communication_messages, attempts to match
against tracker people, creates communication_participants records.
Auto-confirms exact email matches. Leaves fuzzy/no matches for human review.
"""
import json
import logging
import uuid

import httpx

from app.config import TRACKER_BASE_URL, TRACKER_USER, TRACKER_PASS, load_policy

logger = logging.getLogger(__name__)


async def resolve_participants(db, communication_id: str) -> dict:
    """Resolve email participants against tracker people.

    Creates communication_participants records for each unique email address.
    Returns dict with resolution stats and whether all are auto-confirmed.
    """
    # Collect all unique email addresses with their roles
    messages = db.execute("""
        SELECT sender_email, sender_name, recipient_emails, cc_emails, is_new
        FROM communication_messages
        WHERE communication_id = ?
        ORDER BY message_index
    """, (communication_id,)).fetchall()

    # Build participant map: email -> {name, roles}
    participants = {}  # email -> {name, header_roles, is_sender}

    for msg in messages:
        # Only use the newest (primary) message for participant roles
        if not msg["is_new"]:
            continue

        if msg["sender_email"]:
            email_lower = msg["sender_email"].lower().strip()
            if email_lower and email_lower not in participants:
                participants[email_lower] = {
                    "name": msg["sender_name"],
                    "header_role": "from",
                    "participant_role": "sender",
                }

        if msg["recipient_emails"]:
            try:
                for addr in json.loads(msg["recipient_emails"]):
                    email_lower = addr.lower().strip()
                    if email_lower and email_lower not in participants:
                        participants[email_lower] = {
                            "name": None,
                            "header_role": "to",
                            "participant_role": "recipient",
                        }
            except (json.JSONDecodeError, TypeError):
                pass

        if msg["cc_emails"]:
            try:
                for addr in json.loads(msg["cc_emails"]):
                    email_lower = addr.lower().strip()
                    if email_lower and email_lower not in participants:
                        participants[email_lower] = {
                            "name": None,
                            "header_role": "cc",
                            "participant_role": "cc",
                        }
            except (json.JSONDecodeError, TypeError):
                pass

    if not participants:
        logger.warning("[%s] No participants found in email messages", communication_id[:8])
        return {"total": 0, "auto_confirmed": 0, "needs_review": 0, "all_confirmed": True}

    # Check user config for is_from_user
    policy = load_policy()
    user_emails = {e.lower() for e in policy.get("user_config", {}).get("email_addresses", [])}

    # Try to match against tracker people
    auto_confirmed = 0
    needs_review = 0

    for email_addr, info in participants.items():
        part_id = str(uuid.uuid4())

        # Try exact email match against tracker
        tracker_person_id = None
        match_source = "none"
        confirmed = 0
        proposed_name = info["name"]

        try:
            tracker_person = await _match_email_in_tracker(email_addr)
            if tracker_person:
                tracker_person_id = tracker_person["id"]
                proposed_name = tracker_person.get("name") or info["name"]
                match_source = "exact_email"
                confirmed = 1
                auto_confirmed += 1
            else:
                needs_review += 1
        except Exception as e:
            logger.warning("[%s] Tracker email lookup failed for %s: %s",
                          communication_id[:8], email_addr, e)
            needs_review += 1

        db.execute("""
            INSERT INTO communication_participants
                (id, communication_id, participant_email, proposed_name,
                 header_role, participant_role, tracker_person_id,
                 match_source, confirmed, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
        """, (
            part_id, communication_id, email_addr, proposed_name,
            info["header_role"], info["participant_role"],
            tracker_person_id, match_source, confirmed,
        ))

    db.commit()

    all_confirmed = needs_review == 0

    logger.info(
        "[%s] Participant resolution: %d total, %d auto-confirmed, %d need review",
        communication_id[:8], len(participants), auto_confirmed, needs_review,
    )

    return {
        "total": len(participants),
        "auto_confirmed": auto_confirmed,
        "needs_review": needs_review,
        "all_confirmed": all_confirmed,
    }


async def _match_email_in_tracker(email_addr: str) -> dict | None:
    """Query tracker for a person by email address.

    Uses GET /tracker/people?search=<email> with narrow scope.
    Returns person dict or None if no match.
    """
    url = f"{TRACKER_BASE_URL}/people"
    try:
        auth = (TRACKER_USER, TRACKER_PASS) if TRACKER_USER else None
        async with httpx.AsyncClient(timeout=10.0, auth=auth) as client:
            resp = await client.get(url, params={"search": email_addr, "limit": 5})
            resp.raise_for_status()
            data = resp.json()

            # Look for exact email match in results
            items = data.get("items", data) if isinstance(data, dict) else data
            if isinstance(items, list):
                for person in items:
                    person_email = (person.get("email") or "").lower().strip()
                    if person_email == email_addr.lower().strip():
                        return person

            return None
    except Exception as e:
        logger.debug("Tracker people search failed for %s: %s", email_addr, e)
        return None
