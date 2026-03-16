"""Tag CRUD endpoints."""
import uuid
from typing import Optional
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from app.db import get_db

router = APIRouter(prefix="/tags", tags=["tags"])


class CreateTag(BaseModel):
    name: str
    tag_type: Optional[str] = None


@router.get("")
async def list_tags(tag_type: Optional[str] = None, db=Depends(get_db)):
    """List all tags, optionally filtered by type."""
    query = "SELECT id, name, tag_type FROM tags"
    params = []
    if tag_type:
        query += " WHERE tag_type = ?"
        params.append(tag_type)
    query += " ORDER BY name"
    rows = db.execute(query, params).fetchall()
    items = [dict(r) for r in rows]
    return {"items": items, "total": len(items)}


@router.post("")
async def create_tag(body: CreateTag, db=Depends(get_db)):
    """Create a new tag."""
    tag_id = str(uuid.uuid4())
    db.execute("INSERT INTO tags (id, name, tag_type) VALUES (?, ?, ?)",
               (tag_id, body.name, body.tag_type))
    db.commit()
    return {"id": tag_id}


@router.delete("/{tag_id}")
async def delete_tag(tag_id: str, db=Depends(get_db)):
    """Delete a tag and all its matter associations."""
    db.execute("DELETE FROM matter_tags WHERE tag_id = ?", (tag_id,))
    db.execute("DELETE FROM tags WHERE id = ?", (tag_id,))
    db.commit()
    return {"deleted": True}
