"""
CRUD router for outreach plans.
Phase 1: manual CRUD only, no AI-generated plans.
"""

from fastapi import APIRouter, Depends, HTTPException
from typing import List
import sqlite3
import calendar
from datetime import datetime, date, timedelta

from app.database import get_db
from app.models import (
    OutreachPlanCreate, OutreachPlanUpdate, OutreachPlanResponse,
    ContactResponse, PlanType,
)
from app.routers.contacts import row_to_contact

router = APIRouter()


def row_to_outreach(row: sqlite3.Row) -> dict:
    """Convert a sqlite3.Row to an outreach plan dict."""
    keys = row.keys()
    d = {
        "id": row["id"],
        "week_of": row["week_of"],
        "contact_id": row["contact_id"],
        "message_draft": row["message_draft"],
        "reasoning": row["reasoning"],
        "message_type": row["message_type"],
        "status": row["status"],
        "sent_at": row["sent_at"],
        "plan_type": row["plan_type"] if "plan_type" in keys else "social_thursday",
    }
    try:
        d["contact_name"] = row["contact_name"]
    except (IndexError, KeyError):
        d["contact_name"] = None
    try:
        d["contact_phone"] = row["contact_phone"]
    except (IndexError, KeyError):
        d["contact_phone"] = None
    return d


def get_current_week_monday() -> str:
    """Get the Monday of the current week as ISO date string."""
    today = date.today()
    monday = today - timedelta(days=today.weekday())
    return monday.isoformat()


@router.get("/current", response_model=List[OutreachPlanResponse])
def current_week_plan(db: sqlite3.Connection = Depends(get_db)):
    """Get the current week's outreach plan."""
    monday = get_current_week_monday()
    rows = db.execute(
        """
        SELECT op.*, c.name as contact_name, c.phone as contact_phone
        FROM outreach_plans op
        JOIN contacts c ON op.contact_id = c.id
        WHERE op.week_of = ?
        ORDER BY
            CASE op.status
                WHEN 'pending' THEN 1
                WHEN 'approved' THEN 2
                WHEN 'sent' THEN 3
                WHEN 'skipped' THEN 4
            END,
            c.name ASC
        """,
        [monday],
    ).fetchall()
    return [OutreachPlanResponse(**row_to_outreach(r)) for r in rows]


@router.post("", response_model=OutreachPlanResponse, status_code=201)
def create_outreach_plan(
    plan: OutreachPlanCreate,
    db: sqlite3.Connection = Depends(get_db),
):
    """Manually create an outreach plan entry."""
    # Validate contact exists
    contact = db.execute(
        "SELECT id FROM contacts WHERE id = ?", [plan.contact_id]
    ).fetchone()
    if contact is None:
        raise HTTPException(status_code=404, detail="Contact not found")

    cursor = db.execute(
        """
        INSERT INTO outreach_plans (week_of, contact_id, message_draft, reasoning, message_type, status, plan_type)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        [
            plan.week_of.isoformat(),
            plan.contact_id,
            plan.message_draft,
            plan.reasoning,
            plan.message_type.value if plan.message_type else None,
            plan.status.value,
            plan.plan_type.value if plan.plan_type else "social_thursday",
        ],
    )
    db.commit()
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
    return OutreachPlanResponse(**row_to_outreach(row))


@router.put("/{plan_id}", response_model=OutreachPlanResponse)
def update_outreach_plan(
    plan_id: int,
    plan: OutreachPlanUpdate,
    db: sqlite3.Connection = Depends(get_db),
):
    """Update an outreach plan (approve, edit, skip)."""
    existing = db.execute(
        "SELECT id FROM outreach_plans WHERE id = ?", [plan_id]
    ).fetchone()
    if existing is None:
        raise HTTPException(status_code=404, detail="Outreach plan not found")

    update_data = plan.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")

    updates = []
    params = []
    for col, val in update_data.items():
        if hasattr(val, "value"):
            val = val.value
        updates.append(f"{col} = ?")
        params.append(val)

    params.append(plan_id)
    db.execute(f"UPDATE outreach_plans SET {', '.join(updates)} WHERE id = ?", params)
    db.commit()

    row = db.execute(
        """
        SELECT op.*, c.name as contact_name, c.phone as contact_phone
        FROM outreach_plans op
        JOIN contacts c ON op.contact_id = c.id
        WHERE op.id = ?
        """,
        [plan_id],
    ).fetchone()
    return OutreachPlanResponse(**row_to_outreach(row))


@router.put("/{plan_id}/send", response_model=OutreachPlanResponse)
def mark_as_sent(
    plan_id: int,
    db: sqlite3.Connection = Depends(get_db),
):
    """
    Mark an outreach plan as sent.
    Also auto-creates an interaction record and updates the contact's last_contact_date.
    """
    existing = db.execute(
        "SELECT * FROM outreach_plans WHERE id = ?", [plan_id]
    ).fetchone()
    if existing is None:
        raise HTTPException(status_code=404, detail="Outreach plan not found")

    if existing["status"] == "sent":
        raise HTTPException(status_code=400, detail="Outreach plan already marked as sent")

    now = datetime.utcnow().isoformat()
    today = date.today().isoformat()

    # Mark outreach as sent
    db.execute(
        "UPDATE outreach_plans SET status = 'sent', sent_at = ? WHERE id = ?",
        [now, plan_id],
    )

    # Auto-create interaction record
    message_type = existing["message_type"] or "outreach"
    db.execute(
        """
        INSERT INTO interactions (contact_id, date, type, who_initiated, summary)
        VALUES (?, ?, 'Text/Call', 'Me', ?)
        """,
        [
            existing["contact_id"],
            today,
            f"Outreach sent ({message_type}): {existing['message_draft'][:200]}",
        ],
    )

    # Auto-update contact's last_contact_date
    db.execute(
        """
        UPDATE contacts
        SET last_contact_date = ?,
            updated_at = datetime('now')
        WHERE id = ?
          AND (last_contact_date IS NULL OR last_contact_date < ?)
        """,
        [today, existing["contact_id"], today],
    )

    db.commit()

    row = db.execute(
        """
        SELECT op.*, c.name as contact_name, c.phone as contact_phone
        FROM outreach_plans op
        JOIN contacts c ON op.contact_id = c.id
        WHERE op.id = ?
        """,
        [plan_id],
    ).fetchone()
    return OutreachPlanResponse(**row_to_outreach(row))


@router.get("/professional/current", response_model=List[OutreachPlanResponse])
def professional_current_month(db: sqlite3.Connection = Depends(get_db)):
    """Get current month's professional outreach plan."""
    today = date.today()
    month_start = today.replace(day=1).isoformat()
    # Last day of the current month
    last_day = calendar.monthrange(today.year, today.month)[1]
    month_end = today.replace(day=last_day).isoformat()

    rows = db.execute(
        """
        SELECT op.*, c.name as contact_name, c.phone as contact_phone
        FROM outreach_plans op
        JOIN contacts c ON op.contact_id = c.id
        WHERE op.plan_type = 'professional_pulse'
          AND op.week_of >= ?
          AND op.week_of <= ?
        ORDER BY op.week_of ASC, c.name ASC
        """,
        [month_start, month_end],
    ).fetchall()
    return [OutreachPlanResponse(**row_to_outreach(r)) for r in rows]


@router.get("/professional/due", response_model=List[ContactResponse])
def professional_due(db: sqlite3.Connection = Depends(get_db)):
    """Get professional contacts due for outreach based on tier cadence.
    Tier 1 = monthly (30 days), Tier 2 = every 6 weeks (42 days), Tier 3 = quarterly (90 days).
    """
    today = date.today()
    tier_cadence = {
        "Tier 1": 30,
        "Tier 2": 42,
        "Tier 3": 90,
    }

    due_contacts = []
    for tier, days in tier_cadence.items():
        cutoff = (today - timedelta(days=days)).isoformat()
        rows = db.execute(
            """
            SELECT * FROM contacts
            WHERE contact_type = 'professional'
              AND professional_tier = ?
              AND (last_contact_date IS NULL OR last_contact_date <= ?)
            ORDER BY last_contact_date ASC
            """,
            [tier, cutoff],
        ).fetchall()
        due_contacts.extend([ContactResponse(**row_to_contact(r)) for r in rows])

    return due_contacts
