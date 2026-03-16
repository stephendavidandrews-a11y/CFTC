"""
Interagency contacts endpoints.
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException

from app.pipeline.db_async import run_db
from app.pipeline.connection import get_connection
from app.pipeline.services import contacts as svc
from app.pipeline.models import (
    InteragencyContactCreate,
    InteragencyContactUpdate,
    InteragencyContactResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/contacts", tags=["Interagency Contacts"])


def _conn():
    return get_connection()


@router.get("", response_model=list[InteragencyContactResponse])
async def list_contacts(agency: Optional[str] = None, relationship_status: Optional[str] = None):
    """List all interagency contacts."""
    def _query():
        conn = _conn()
        try:
            return svc.list_contacts(conn, agency=agency, relationship_status=relationship_status)
        finally:
            conn.close()
    return await run_db(_query)


@router.get("/dormant", response_model=list[InteragencyContactResponse])
async def dormant_contacts(days: int = 90):
    """Get contacts not reached in N+ days."""
    def _query():
        conn = _conn()
        try:
            return svc.get_dormant_contacts(conn, days=days)
        finally:
            conn.close()
    return await run_db(_query)


@router.get("/{contact_id}", response_model=InteragencyContactResponse)
async def get_contact(contact_id: int):
    """Get a single contact."""
    def _query():
        conn = _conn()
        try:
            return svc.get_contact(conn, contact_id)
        finally:
            conn.close()
    result = await run_db(_query)
    if not result:
        raise HTTPException(404, f"Contact {contact_id} not found")
    return result


@router.post("", response_model=InteragencyContactResponse, status_code=201)
async def create_contact(data: InteragencyContactCreate):
    """Create a new interagency contact."""
    def _create():
        conn = _conn()
        try:
            return svc.create_contact(conn, data.model_dump())
        finally:
            conn.close()
    return await run_db(_create)


@router.patch("/{contact_id}", response_model=InteragencyContactResponse)
async def update_contact(contact_id: int, data: InteragencyContactUpdate):
    """Update contact fields."""
    def _update():
        conn = _conn()
        try:
            return svc.update_contact(conn, contact_id, data.model_dump(exclude_unset=True))
        finally:
            conn.close()
    result = await run_db(_update)
    if not result:
        raise HTTPException(404, f"Contact {contact_id} not found")
    return result


@router.delete("/{contact_id}", status_code=204)
async def delete_contact(contact_id: int):
    """Delete a contact."""
    def _delete():
        conn = _conn()
        try:
            svc.delete_contact(conn, contact_id)
        finally:
            conn.close()
    await run_db(_delete)
