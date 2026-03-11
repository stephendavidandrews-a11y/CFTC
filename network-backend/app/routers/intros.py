"""
CRUD router for intros (introductions between contacts).
"""

from fastapi import APIRouter, Depends, HTTPException
from typing import List
import sqlite3

from app.database import get_db
from app.models import IntroCreate, IntroUpdate, IntroResponse

router = APIRouter()


def row_to_intro(row: sqlite3.Row) -> dict:
    """Convert a sqlite3.Row to an intro dict."""
    d = {
        "id": row["id"],
        "person_a_id": row["person_a_id"],
        "person_b_id": row["person_b_id"],
        "date": row["date"],
        "context": row["context"],
        "outcome": row["outcome"],
    }
    try:
        d["person_a_name"] = row["person_a_name"]
    except (IndexError, KeyError):
        d["person_a_name"] = None
    try:
        d["person_b_name"] = row["person_b_name"]
    except (IndexError, KeyError):
        d["person_b_name"] = None
    return d


@router.get("", response_model=List[IntroResponse])
def list_intros(db: sqlite3.Connection = Depends(get_db)):
    """List all intros with contact names."""
    rows = db.execute(
        """
        SELECT i.*,
               ca.name as person_a_name,
               cb.name as person_b_name
        FROM intros i
        JOIN contacts ca ON i.person_a_id = ca.id
        JOIN contacts cb ON i.person_b_id = cb.id
        ORDER BY i.date DESC
        """
    ).fetchall()
    return [IntroResponse(**row_to_intro(r)) for r in rows]


@router.post("", response_model=IntroResponse, status_code=201)
def create_intro(intro: IntroCreate, db: sqlite3.Connection = Depends(get_db)):
    """Create a new intro between two contacts."""
    # Validate both contacts exist
    person_a = db.execute(
        "SELECT id FROM contacts WHERE id = ?", [intro.person_a_id]
    ).fetchone()
    if person_a is None:
        raise HTTPException(status_code=404, detail="Person A (contact) not found")

    person_b = db.execute(
        "SELECT id FROM contacts WHERE id = ?", [intro.person_b_id]
    ).fetchone()
    if person_b is None:
        raise HTTPException(status_code=404, detail="Person B (contact) not found")

    if intro.person_a_id == intro.person_b_id:
        raise HTTPException(status_code=400, detail="Cannot introduce a contact to themselves")

    cursor = db.execute(
        """
        INSERT INTO intros (person_a_id, person_b_id, date, context, outcome)
        VALUES (?, ?, ?, ?, ?)
        """,
        [
            intro.person_a_id,
            intro.person_b_id,
            intro.date.isoformat(),
            intro.context,
            intro.outcome,
        ],
    )
    db.commit()
    new_id = cursor.lastrowid

    row = db.execute(
        """
        SELECT i.*,
               ca.name as person_a_name,
               cb.name as person_b_name
        FROM intros i
        JOIN contacts ca ON i.person_a_id = ca.id
        JOIN contacts cb ON i.person_b_id = cb.id
        WHERE i.id = ?
        """,
        [new_id],
    ).fetchone()
    return IntroResponse(**row_to_intro(row))


@router.put("/{intro_id}", response_model=IntroResponse)
def update_intro(
    intro_id: int,
    intro: IntroUpdate,
    db: sqlite3.Connection = Depends(get_db),
):
    """Update an intro's outcome."""
    existing = db.execute("SELECT id FROM intros WHERE id = ?", [intro_id]).fetchone()
    if existing is None:
        raise HTTPException(status_code=404, detail="Intro not found")

    update_data = intro.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")

    updates = []
    params = []
    for col, val in update_data.items():
        updates.append(f"{col} = ?")
        params.append(val)

    params.append(intro_id)
    db.execute(f"UPDATE intros SET {', '.join(updates)} WHERE id = ?", params)
    db.commit()

    row = db.execute(
        """
        SELECT i.*,
               ca.name as person_a_name,
               cb.name as person_b_name
        FROM intros i
        JOIN contacts ca ON i.person_a_id = ca.id
        JOIN contacts cb ON i.person_b_id = cb.id
        WHERE i.id = ?
        """,
        [intro_id],
    ).fetchone()
    return IntroResponse(**row_to_intro(row))
