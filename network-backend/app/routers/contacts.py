"""
CRUD router for contacts.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional, List
import sqlite3
from datetime import datetime, date, timedelta

from app.database import get_db
from app.models import (
    ContactCreate, ContactUpdate, ContactResponse, ContactDetailResponse,
    InteractionResponse, TierEnum, DomainEnum, ContactType, ProfessionalTier,
)

router = APIRouter()


def row_to_contact(row: sqlite3.Row) -> dict:
    """Convert a sqlite3.Row to a contact dict."""
    keys = row.keys()
    return {
        "id": row["id"],
        "name": row["name"],
        "phone": row["phone"],
        "email": row["email"],
        "how_we_met": row["how_we_met"],
        "current_role": row["current_role"],
        "domain": row["domain"],
        "tier": row["tier"],
        "is_super_connector": bool(row["is_super_connector"]),
        "relationship_status": row["relationship_status"],
        "interests": row["interests"],
        "their_goals": row["their_goals"],
        "what_i_offer": row["what_i_offer"],
        "activity_prefs": row["activity_prefs"],
        "last_contact_date": row["last_contact_date"],
        "next_action": row["next_action"],
        "notes": row["notes"],
        "linkedin_url": row["linkedin_url"],
        "linkedin_headline": row["linkedin_headline"],
        "linkedin_last_checked": row["linkedin_last_checked"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "contact_type": row["contact_type"] if "contact_type" in keys else "social",
        "professional_tier": row["professional_tier"] if "professional_tier" in keys else None,
    }


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
    # contact_name may or may not be present depending on query
    try:
        d["contact_name"] = row["contact_name"]
    except (IndexError, KeyError):
        d["contact_name"] = None
    return d


@router.get("", response_model=List[ContactResponse])
def list_contacts(
    tier: Optional[TierEnum] = None,
    domain: Optional[DomainEnum] = None,
    is_super_connector: Optional[bool] = None,
    contact_type: Optional[ContactType] = None,
    search: Optional[str] = None,
    db: sqlite3.Connection = Depends(get_db),
):
    """List all contacts with optional filters."""
    query = "SELECT * FROM contacts WHERE 1=1"
    params: list = []

    if tier is not None:
        query += " AND tier = ?"
        params.append(tier.value)
    if domain is not None:
        query += " AND domain = ?"
        params.append(domain.value)
    if is_super_connector is not None:
        query += " AND is_super_connector = ?"
        params.append(1 if is_super_connector else 0)
    if contact_type is not None:
        query += " AND contact_type = ?"
        params.append(contact_type.value)
    if search is not None:
        query += " AND name LIKE ?"
        params.append(f"%{search}%")

    query += " ORDER BY name ASC"
    rows = db.execute(query, params).fetchall()
    return [ContactResponse(**row_to_contact(r)) for r in rows]


@router.get("/going-cold", response_model=List[ContactResponse])
def going_cold(
    days: int = Query(default=14, ge=1, description="Days since last contact to consider 'cold'"),
    db: sqlite3.Connection = Depends(get_db),
):
    """Get contacts with no interaction in 2+ weeks (configurable)."""
    cutoff = (date.today() - timedelta(days=days)).isoformat()
    query = """
        SELECT * FROM contacts
        WHERE (last_contact_date IS NOT NULL AND last_contact_date <= ?)
           OR (last_contact_date IS NULL AND created_at <= ?)
        ORDER BY last_contact_date ASC
    """
    rows = db.execute(query, [cutoff, cutoff]).fetchall()
    return [ContactResponse(**row_to_contact(r)) for r in rows]


@router.get("/super-connectors", response_model=List[ContactResponse])
def super_connectors(db: sqlite3.Connection = Depends(get_db)):
    """Get all super-connectors."""
    rows = db.execute(
        "SELECT * FROM contacts WHERE is_super_connector = 1 ORDER BY name ASC"
    ).fetchall()
    return [ContactResponse(**row_to_contact(r)) for r in rows]


@router.get("/{contact_id}", response_model=ContactDetailResponse)
def get_contact(contact_id: int, db: sqlite3.Connection = Depends(get_db)):
    """Get a single contact with full interaction history."""
    row = db.execute("SELECT * FROM contacts WHERE id = ?", [contact_id]).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Contact not found")

    contact = row_to_contact(row)

    # Fetch interaction history
    interaction_rows = db.execute(
        "SELECT * FROM interactions WHERE contact_id = ? ORDER BY date DESC",
        [contact_id],
    ).fetchall()
    interactions = [InteractionResponse(**row_to_interaction(r)) for r in interaction_rows]

    return ContactDetailResponse(**contact, interactions=interactions)


@router.post("", response_model=ContactResponse, status_code=201)
def create_contact(contact: ContactCreate, db: sqlite3.Connection = Depends(get_db)):
    """Create a new contact."""
    now = datetime.utcnow().isoformat()
    cursor = db.execute(
        """
        INSERT INTO contacts (
            name, phone, email, how_we_met, current_role, domain, tier,
            is_super_connector, relationship_status, interests, their_goals,
            what_i_offer, activity_prefs, next_action, notes,
            linkedin_url, linkedin_headline, contact_type, professional_tier,
            created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            contact.name,
            contact.phone,
            contact.email,
            contact.how_we_met,
            contact.current_role,
            contact.domain.value if contact.domain else None,
            contact.tier.value,
            1 if contact.is_super_connector else 0,
            contact.relationship_status,
            contact.interests,
            contact.their_goals,
            contact.what_i_offer,
            contact.activity_prefs,
            contact.next_action,
            contact.notes,
            contact.linkedin_url,
            contact.linkedin_headline,
            contact.contact_type.value if contact.contact_type else "social",
            contact.professional_tier.value if contact.professional_tier else None,
            now,
            now,
        ],
    )
    db.commit()
    new_id = cursor.lastrowid

    row = db.execute("SELECT * FROM contacts WHERE id = ?", [new_id]).fetchone()
    return ContactResponse(**row_to_contact(row))


@router.put("/{contact_id}", response_model=ContactResponse)
def update_contact(
    contact_id: int,
    contact: ContactUpdate,
    db: sqlite3.Connection = Depends(get_db),
):
    """Update an existing contact."""
    existing = db.execute("SELECT * FROM contacts WHERE id = ?", [contact_id]).fetchone()
    if existing is None:
        raise HTTPException(status_code=404, detail="Contact not found")

    # Build dynamic update
    updates = []
    params = []
    update_data = contact.model_dump(exclude_unset=True)

    field_map = {
        "name": "name",
        "phone": "phone",
        "email": "email",
        "how_we_met": "how_we_met",
        "current_role": "current_role",
        "domain": "domain",
        "tier": "tier",
        "is_super_connector": "is_super_connector",
        "relationship_status": "relationship_status",
        "interests": "interests",
        "their_goals": "their_goals",
        "what_i_offer": "what_i_offer",
        "activity_prefs": "activity_prefs",
        "next_action": "next_action",
        "notes": "notes",
        "linkedin_url": "linkedin_url",
        "linkedin_headline": "linkedin_headline",
        "contact_type": "contact_type",
        "professional_tier": "professional_tier",
    }

    for field_name, col_name in field_map.items():
        if field_name in update_data:
            value = update_data[field_name]
            if field_name in ("domain", "tier", "contact_type", "professional_tier") and value is not None:
                value = value.value if hasattr(value, "value") else value
            if field_name == "is_super_connector":
                value = 1 if value else 0
            updates.append(f"{col_name} = ?")
            params.append(value)

    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    updates.append("updated_at = ?")
    params.append(datetime.utcnow().isoformat())
    params.append(contact_id)

    db.execute(
        f"UPDATE contacts SET {', '.join(updates)} WHERE id = ?",
        params,
    )
    db.commit()

    row = db.execute("SELECT * FROM contacts WHERE id = ?", [contact_id]).fetchone()
    return ContactResponse(**row_to_contact(row))


@router.put("/{contact_id}/migrate", response_model=ContactResponse)
def migrate_contact(
    contact_id: int,
    contact_type: ContactType,
    professional_tier: Optional[ProfessionalTier] = None,
    db: sqlite3.Connection = Depends(get_db),
):
    """Migrate a contact between social and professional pools."""
    existing = db.execute("SELECT * FROM contacts WHERE id = ?", [contact_id]).fetchone()
    if existing is None:
        raise HTTPException(status_code=404, detail="Contact not found")

    # If migrating to professional, a tier is required
    if contact_type == ContactType.professional and professional_tier is None:
        raise HTTPException(
            status_code=400,
            detail="professional_tier is required when migrating to professional",
        )

    # If migrating to social, clear the professional tier
    tier_value = professional_tier.value if professional_tier else None
    if contact_type == ContactType.social:
        tier_value = None

    db.execute(
        """
        UPDATE contacts
        SET contact_type = ?, professional_tier = ?, updated_at = datetime('now')
        WHERE id = ?
        """,
        [contact_type.value, tier_value, contact_id],
    )
    db.commit()

    row = db.execute("SELECT * FROM contacts WHERE id = ?", [contact_id]).fetchone()
    return ContactResponse(**row_to_contact(row))


@router.delete("/{contact_id}", status_code=204)
def delete_contact(contact_id: int, db: sqlite3.Connection = Depends(get_db)):
    """Delete a contact and all related records (cascading)."""
    existing = db.execute("SELECT id FROM contacts WHERE id = ?", [contact_id]).fetchone()
    if existing is None:
        raise HTTPException(status_code=404, detail="Contact not found")

    db.execute("DELETE FROM contacts WHERE id = ?", [contact_id])
    db.commit()
    return None
