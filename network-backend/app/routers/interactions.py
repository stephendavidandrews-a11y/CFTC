"""
CRUD router for interactions.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional, List
import sqlite3
from datetime import date

from app.database import get_db
from app.models import InteractionCreate, InteractionResponse, InteractionType

router = APIRouter()


def row_to_interaction(row: sqlite3.Row) -> dict:
    """Convert a sqlite3.Row to an interaction dict."""
    d = {
        "id": row["id"],
        "contact_id": row["contact_id"],
        "date": row["date"],
        "type": row["type"],
        "who_initiated": row["who_initiated"],
        "summary": row["summary"],
        "open_loops": row["open_loops"],
        "follow_up_date": row["follow_up_date"],
    }
    try:
        d["contact_name"] = row["contact_name"]
    except (IndexError, KeyError):
        d["contact_name"] = None
    return d


@router.get("", response_model=List[InteractionResponse])
def list_interactions(
    contact_id: Optional[int] = None,
    type: Optional[InteractionType] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    db: sqlite3.Connection = Depends(get_db),
):
    """List interactions with optional filters."""
    query = """
        SELECT i.*, c.name as contact_name
        FROM interactions i
        JOIN contacts c ON i.contact_id = c.id
        WHERE 1=1
    """
    params: list = []

    if contact_id is not None:
        query += " AND i.contact_id = ?"
        params.append(contact_id)
    if type is not None:
        query += " AND i.type = ?"
        params.append(type.value)
    if date_from is not None:
        query += " AND i.date >= ?"
        params.append(date_from.isoformat())
    if date_to is not None:
        query += " AND i.date <= ?"
        params.append(date_to.isoformat())

    query += " ORDER BY i.date DESC"
    rows = db.execute(query, params).fetchall()
    return [InteractionResponse(**row_to_interaction(r)) for r in rows]


@router.get("/open-loops", response_model=List[InteractionResponse])
def open_loops(db: sqlite3.Connection = Depends(get_db)):
    """Get all interactions with open loops that need follow-up."""
    query = """
        SELECT i.*, c.name as contact_name
        FROM interactions i
        JOIN contacts c ON i.contact_id = c.id
        WHERE i.open_loops IS NOT NULL AND i.open_loops != ''
        ORDER BY COALESCE(i.follow_up_date, '9999-12-31') ASC, i.date DESC
    """
    rows = db.execute(query).fetchall()
    return [InteractionResponse(**row_to_interaction(r)) for r in rows]


@router.post("", response_model=InteractionResponse, status_code=201)
def create_interaction(
    interaction: InteractionCreate,
    db: sqlite3.Connection = Depends(get_db),
):
    """
    Log a new interaction.
    Also auto-updates the contact's last_contact_date.
    """
    # Verify contact exists
    contact = db.execute(
        "SELECT id FROM contacts WHERE id = ?", [interaction.contact_id]
    ).fetchone()
    if contact is None:
        raise HTTPException(status_code=404, detail="Contact not found")

    cursor = db.execute(
        """
        INSERT INTO interactions (contact_id, date, type, who_initiated, summary, open_loops, follow_up_date)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        [
            interaction.contact_id,
            interaction.date.isoformat(),
            interaction.type.value,
            interaction.who_initiated.value if interaction.who_initiated else None,
            interaction.summary,
            interaction.open_loops,
            interaction.follow_up_date.isoformat() if interaction.follow_up_date else None,
        ],
    )
    new_id = cursor.lastrowid

    # Auto-update contact's last_contact_date if this interaction is the most recent
    db.execute(
        """
        UPDATE contacts
        SET last_contact_date = ?,
            updated_at = datetime('now')
        WHERE id = ?
          AND (last_contact_date IS NULL OR last_contact_date < ?)
        """,
        [interaction.date.isoformat(), interaction.contact_id, interaction.date.isoformat()],
    )
    db.commit()

    row = db.execute(
        """
        SELECT i.*, c.name as contact_name
        FROM interactions i
        JOIN contacts c ON i.contact_id = c.id
        WHERE i.id = ?
        """,
        [new_id],
    ).fetchone()
    return InteractionResponse(**row_to_interaction(row))
