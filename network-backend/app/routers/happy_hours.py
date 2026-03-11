"""
CRUD router for happy hours and attendees.
"""

from fastapi import APIRouter, Depends, HTTPException
from typing import List
import sqlite3

from app.database import get_db
from app.models import (
    HappyHourCreate, HappyHourUpdate, HappyHourResponse, HappyHourDetailResponse,
    AttendeeCreate, AttendeeUpdate, AttendeeResponse,
)

router = APIRouter()


def row_to_happy_hour(row: sqlite3.Row) -> dict:
    """Convert a sqlite3.Row to a happy hour dict."""
    d = {
        "id": row["id"],
        "date": row["date"],
        "venue_id": row["venue_id"],
        "theme": row["theme"],
        "sonnet_reasoning": row["sonnet_reasoning"],
    }
    try:
        d["venue_name"] = row["venue_name"]
    except (IndexError, KeyError):
        d["venue_name"] = None
    return d


def row_to_attendee(row: sqlite3.Row) -> dict:
    """Convert a sqlite3.Row to an attendee dict."""
    d = {
        "id": row["id"],
        "happy_hour_id": row["happy_hour_id"],
        "contact_id": row["contact_id"],
        "role": row["role"],
        "rsvp_status": row["rsvp_status"],
        "brought_guest": bool(row["brought_guest"]),
    }
    try:
        d["contact_name"] = row["contact_name"]
    except (IndexError, KeyError):
        d["contact_name"] = None
    return d


@router.get("", response_model=List[HappyHourResponse])
def list_happy_hours(db: sqlite3.Connection = Depends(get_db)):
    """List all happy hours."""
    rows = db.execute(
        """
        SELECT hh.*, v.name as venue_name
        FROM happy_hours hh
        LEFT JOIN venues v ON hh.venue_id = v.id
        ORDER BY hh.date DESC
        """
    ).fetchall()
    return [HappyHourResponse(**row_to_happy_hour(r)) for r in rows]


@router.get("/{happy_hour_id}", response_model=HappyHourDetailResponse)
def get_happy_hour(happy_hour_id: int, db: sqlite3.Connection = Depends(get_db)):
    """Get a single happy hour with attendees."""
    row = db.execute(
        """
        SELECT hh.*, v.name as venue_name
        FROM happy_hours hh
        LEFT JOIN venues v ON hh.venue_id = v.id
        WHERE hh.id = ?
        """,
        [happy_hour_id],
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Happy hour not found")

    hh = row_to_happy_hour(row)

    # Fetch attendees
    attendee_rows = db.execute(
        """
        SELECT a.*, c.name as contact_name
        FROM happy_hour_attendees a
        JOIN contacts c ON a.contact_id = c.id
        WHERE a.happy_hour_id = ?
        ORDER BY c.name ASC
        """,
        [happy_hour_id],
    ).fetchall()
    attendees = [AttendeeResponse(**row_to_attendee(r)) for r in attendee_rows]

    return HappyHourDetailResponse(**hh, attendees=attendees)


@router.post("", response_model=HappyHourDetailResponse, status_code=201)
def create_happy_hour(
    happy_hour: HappyHourCreate,
    db: sqlite3.Connection = Depends(get_db),
):
    """Create a new happy hour with optional attendees."""
    # Validate venue if provided
    if happy_hour.venue_id is not None:
        venue = db.execute(
            "SELECT id FROM venues WHERE id = ?", [happy_hour.venue_id]
        ).fetchone()
        if venue is None:
            raise HTTPException(status_code=404, detail="Venue not found")

    cursor = db.execute(
        """
        INSERT INTO happy_hours (date, venue_id, theme, sonnet_reasoning)
        VALUES (?, ?, ?, ?)
        """,
        [
            happy_hour.date.isoformat(),
            happy_hour.venue_id,
            happy_hour.theme,
            happy_hour.sonnet_reasoning,
        ],
    )
    hh_id = cursor.lastrowid

    # Add attendees
    if happy_hour.attendees:
        for att in happy_hour.attendees:
            # Validate contact exists
            contact = db.execute(
                "SELECT id FROM contacts WHERE id = ?", [att.contact_id]
            ).fetchone()
            if contact is None:
                db.rollback()
                raise HTTPException(
                    status_code=404,
                    detail=f"Contact {att.contact_id} not found",
                )
            db.execute(
                """
                INSERT INTO happy_hour_attendees (happy_hour_id, contact_id, role, rsvp_status)
                VALUES (?, ?, ?, ?)
                """,
                [
                    hh_id,
                    att.contact_id,
                    att.role.value if att.role else None,
                    att.rsvp_status.value,
                ],
            )

    db.commit()

    # Return the full detail response
    return get_happy_hour(hh_id, db)


@router.put("/{happy_hour_id}", response_model=HappyHourResponse)
def update_happy_hour(
    happy_hour_id: int,
    happy_hour: HappyHourUpdate,
    db: sqlite3.Connection = Depends(get_db),
):
    """Update an existing happy hour."""
    existing = db.execute(
        "SELECT id FROM happy_hours WHERE id = ?", [happy_hour_id]
    ).fetchone()
    if existing is None:
        raise HTTPException(status_code=404, detail="Happy hour not found")

    update_data = happy_hour.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")

    updates = []
    params = []
    for col, val in update_data.items():
        if col == "date" and val is not None:
            val = val.isoformat() if hasattr(val, "isoformat") else str(val)
        updates.append(f"{col} = ?")
        params.append(val)

    params.append(happy_hour_id)
    db.execute(f"UPDATE happy_hours SET {', '.join(updates)} WHERE id = ?", params)
    db.commit()

    row = db.execute(
        """
        SELECT hh.*, v.name as venue_name
        FROM happy_hours hh
        LEFT JOIN venues v ON hh.venue_id = v.id
        WHERE hh.id = ?
        """,
        [happy_hour_id],
    ).fetchone()
    return HappyHourResponse(**row_to_happy_hour(row))


@router.post("/{happy_hour_id}/attendees", response_model=AttendeeResponse, status_code=201)
def add_attendee(
    happy_hour_id: int,
    attendee: AttendeeCreate,
    db: sqlite3.Connection = Depends(get_db),
):
    """Add an attendee to an existing happy hour."""
    # Validate happy hour exists
    hh = db.execute(
        "SELECT id FROM happy_hours WHERE id = ?", [happy_hour_id]
    ).fetchone()
    if hh is None:
        raise HTTPException(status_code=404, detail="Happy hour not found")

    # Validate contact exists
    contact = db.execute(
        "SELECT id FROM contacts WHERE id = ?", [attendee.contact_id]
    ).fetchone()
    if contact is None:
        raise HTTPException(status_code=404, detail="Contact not found")

    # Check if already an attendee
    existing = db.execute(
        "SELECT id FROM happy_hour_attendees WHERE happy_hour_id = ? AND contact_id = ?",
        [happy_hour_id, attendee.contact_id],
    ).fetchone()
    if existing:
        raise HTTPException(status_code=409, detail="Contact is already an attendee")

    db.execute(
        """
        INSERT INTO happy_hour_attendees (happy_hour_id, contact_id, role, rsvp_status)
        VALUES (?, ?, ?, ?)
        """,
        [
            happy_hour_id,
            attendee.contact_id,
            attendee.role.value if attendee.role else None,
            attendee.rsvp_status.value,
        ],
    )
    db.commit()

    row = db.execute(
        """
        SELECT a.*, c.name as contact_name
        FROM happy_hour_attendees a
        JOIN contacts c ON a.contact_id = c.id
        WHERE a.happy_hour_id = ? AND a.contact_id = ?
        """,
        [happy_hour_id, attendee.contact_id],
    ).fetchone()
    return AttendeeResponse(**row_to_attendee(row))


@router.delete("/{happy_hour_id}/attendees/{contact_id}", status_code=204)
def remove_attendee(
    happy_hour_id: int,
    contact_id: int,
    db: sqlite3.Connection = Depends(get_db),
):
    """Remove an attendee from a happy hour."""
    existing = db.execute(
        "SELECT id FROM happy_hour_attendees WHERE happy_hour_id = ? AND contact_id = ?",
        [happy_hour_id, contact_id],
    ).fetchone()
    if existing is None:
        raise HTTPException(status_code=404, detail="Attendee not found for this happy hour")

    db.execute(
        "DELETE FROM happy_hour_attendees WHERE happy_hour_id = ? AND contact_id = ?",
        [happy_hour_id, contact_id],
    )
    db.commit()


@router.put("/{happy_hour_id}/attendees/{contact_id}", response_model=AttendeeResponse)
def update_attendee(
    happy_hour_id: int,
    contact_id: int,
    attendee: AttendeeUpdate,
    db: sqlite3.Connection = Depends(get_db),
):
    """Update an attendee's RSVP status, role, or brought_guest flag."""
    existing = db.execute(
        """
        SELECT id FROM happy_hour_attendees
        WHERE happy_hour_id = ? AND contact_id = ?
        """,
        [happy_hour_id, contact_id],
    ).fetchone()
    if existing is None:
        raise HTTPException(status_code=404, detail="Attendee not found for this happy hour")

    update_data = attendee.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")

    updates = []
    params = []
    for col, val in update_data.items():
        if col == "rsvp_status" and val is not None:
            val = val.value if hasattr(val, "value") else val
        if col == "role" and val is not None:
            val = val.value if hasattr(val, "value") else val
        if col == "brought_guest":
            val = 1 if val else 0
        updates.append(f"{col} = ?")
        params.append(val)

    params.extend([happy_hour_id, contact_id])
    db.execute(
        f"UPDATE happy_hour_attendees SET {', '.join(updates)} WHERE happy_hour_id = ? AND contact_id = ?",
        params,
    )
    db.commit()

    row = db.execute(
        """
        SELECT a.*, c.name as contact_name
        FROM happy_hour_attendees a
        JOIN contacts c ON a.contact_id = c.id
        WHERE a.happy_hour_id = ? AND a.contact_id = ?
        """,
        [happy_hour_id, contact_id],
    ).fetchone()
    return AttendeeResponse(**row_to_attendee(row))
