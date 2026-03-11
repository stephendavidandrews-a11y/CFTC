"""
CRUD router for LinkedIn events.
Phase 1: manual entry only, no automated scanning.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional, List
import sqlite3

from app.database import get_db
from app.models import (
    LinkedInEventCreate, LinkedInEventResponse,
    SignificanceLevel,
)

router = APIRouter()


def row_to_linkedin_event(row: sqlite3.Row) -> dict:
    """Convert a sqlite3.Row to a LinkedIn event dict."""
    d = {
        "id": row["id"],
        "contact_id": row["contact_id"],
        "detected_date": row["detected_date"],
        "event_type": row["event_type"],
        "significance": row["significance"],
        "description": row["description"],
        "outreach_hook": row["outreach_hook"],
        "opportunity_flag": row["opportunity_flag"],
        "used_in_outreach": bool(row["used_in_outreach"]),
        "dismissed": bool(row["dismissed"]),
    }
    try:
        d["contact_name"] = row["contact_name"]
    except (IndexError, KeyError):
        d["contact_name"] = None
    return d


@router.get("/events", response_model=List[LinkedInEventResponse])
def list_linkedin_events(
    significance: Optional[SignificanceLevel] = None,
    unprocessed: Optional[bool] = None,
    contact_id: Optional[int] = None,
    db: sqlite3.Connection = Depends(get_db),
):
    """List LinkedIn events with optional filters."""
    query = """
        SELECT le.*, c.name as contact_name
        FROM linkedin_events le
        JOIN contacts c ON le.contact_id = c.id
        WHERE 1=1
    """
    params: list = []

    if significance is not None:
        query += " AND le.significance = ?"
        params.append(significance.value)
    if unprocessed is True:
        query += " AND le.used_in_outreach = 0 AND le.dismissed = 0"
    if contact_id is not None:
        query += " AND le.contact_id = ?"
        params.append(contact_id)

    query += " ORDER BY le.detected_date DESC"
    rows = db.execute(query, params).fetchall()
    return [LinkedInEventResponse(**row_to_linkedin_event(r)) for r in rows]


@router.post("/events", response_model=LinkedInEventResponse, status_code=201)
def create_linkedin_event(
    event: LinkedInEventCreate,
    db: sqlite3.Connection = Depends(get_db),
):
    """Manually create a LinkedIn event."""
    # Validate contact exists
    contact = db.execute(
        "SELECT id FROM contacts WHERE id = ?", [event.contact_id]
    ).fetchone()
    if contact is None:
        raise HTTPException(status_code=404, detail="Contact not found")

    cursor = db.execute(
        """
        INSERT INTO linkedin_events (
            contact_id, detected_date, event_type, significance,
            description, outreach_hook, opportunity_flag
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        [
            event.contact_id,
            event.detected_date.isoformat(),
            event.event_type.value,
            event.significance.value,
            event.description,
            event.outreach_hook,
            event.opportunity_flag,
        ],
    )
    db.commit()
    new_id = cursor.lastrowid

    row = db.execute(
        """
        SELECT le.*, c.name as contact_name
        FROM linkedin_events le
        JOIN contacts c ON le.contact_id = c.id
        WHERE le.id = ?
        """,
        [new_id],
    ).fetchone()
    return LinkedInEventResponse(**row_to_linkedin_event(row))


@router.put("/events/{event_id}/dismiss", response_model=LinkedInEventResponse)
def dismiss_linkedin_event(
    event_id: int,
    db: sqlite3.Connection = Depends(get_db),
):
    """Dismiss a LinkedIn event."""
    existing = db.execute(
        "SELECT id FROM linkedin_events WHERE id = ?", [event_id]
    ).fetchone()
    if existing is None:
        raise HTTPException(status_code=404, detail="LinkedIn event not found")

    db.execute(
        "UPDATE linkedin_events SET dismissed = 1 WHERE id = ?",
        [event_id],
    )
    db.commit()

    row = db.execute(
        """
        SELECT le.*, c.name as contact_name
        FROM linkedin_events le
        JOIN contacts c ON le.contact_id = c.id
        WHERE le.id = ?
        """,
        [event_id],
    ).fetchone()
    return LinkedInEventResponse(**row_to_linkedin_event(row))
