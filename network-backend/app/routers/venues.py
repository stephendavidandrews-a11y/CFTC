"""
CRUD router for venues.
"""

from fastapi import APIRouter, Depends, HTTPException
from typing import List
import sqlite3

from app.database import get_db
from app.models import VenueCreate, VenueUpdate, VenueResponse

router = APIRouter()


def row_to_venue(row: sqlite3.Row) -> dict:
    """Convert a sqlite3.Row to a venue dict."""
    return {
        "id": row["id"],
        "name": row["name"],
        "type": row["type"],
        "neighborhood": row["neighborhood"],
        "vibe": row["vibe"],
        "best_for": row["best_for"],
        "price_range": row["price_range"],
        "notes": row["notes"],
    }


@router.get("", response_model=List[VenueResponse])
def list_venues(db: sqlite3.Connection = Depends(get_db)):
    """List all venues."""
    rows = db.execute("SELECT * FROM venues ORDER BY name ASC").fetchall()
    return [VenueResponse(**row_to_venue(r)) for r in rows]


@router.post("", response_model=VenueResponse, status_code=201)
def create_venue(venue: VenueCreate, db: sqlite3.Connection = Depends(get_db)):
    """Create a new venue."""
    cursor = db.execute(
        """
        INSERT INTO venues (name, type, neighborhood, vibe, best_for, price_range, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        [
            venue.name,
            venue.type,
            venue.neighborhood,
            venue.vibe,
            venue.best_for,
            venue.price_range,
            venue.notes,
        ],
    )
    db.commit()
    new_id = cursor.lastrowid

    row = db.execute("SELECT * FROM venues WHERE id = ?", [new_id]).fetchone()
    return VenueResponse(**row_to_venue(row))


@router.put("/{venue_id}", response_model=VenueResponse)
def update_venue(
    venue_id: int,
    venue: VenueUpdate,
    db: sqlite3.Connection = Depends(get_db),
):
    """Update an existing venue."""
    existing = db.execute("SELECT id FROM venues WHERE id = ?", [venue_id]).fetchone()
    if existing is None:
        raise HTTPException(status_code=404, detail="Venue not found")

    update_data = venue.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")

    updates = []
    params = []
    for col, val in update_data.items():
        updates.append(f"{col} = ?")
        params.append(val)

    params.append(venue_id)
    db.execute(f"UPDATE venues SET {', '.join(updates)} WHERE id = ?", params)
    db.commit()

    row = db.execute("SELECT * FROM venues WHERE id = ?", [venue_id]).fetchone()
    return VenueResponse(**row_to_venue(row))
