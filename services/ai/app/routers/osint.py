"""OSINT feed API router.

Endpoints for the OSINT Feed page: browse tagged items, manage
sources, and trigger manual refreshes.
"""

import json
import logging
import sqlite3
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.db import get_db
from app.osint.topics import TOPICS

logger = logging.getLogger(__name__)
router = APIRouter(tags=["osint"])

# Module-level singleton so the dependency isn't re-created per signature (B008)
DbDep = Depends(get_db)


def _now() -> str:
    return datetime.now(timezone.utc).replace(tzinfo=None).isoformat(timespec="seconds")


def _item_dict(row) -> dict:
    item = dict(row)
    try:
        item["topics"] = json.loads(item.get("topics") or "[]")
    except (json.JSONDecodeError, TypeError):
        item["topics"] = []
    return item


def _source_dict(row) -> dict:
    src = dict(row)
    try:
        src["default_topics"] = json.loads(src.get("default_topics") or "[]")
    except (json.JSONDecodeError, TypeError):
        src["default_topics"] = []
    return src


# ── Items ───────────────────────────────────────────────────────────────────


@router.get("/osint/items")
def list_items(
    topic: str | None = Query(None, description="Topic slug filter"),
    source_id: str | None = Query(None),
    q: str | None = Query(None, description="Search in title/summary"),
    unread_only: bool = Query(False),
    starred_only: bool = Query(False),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: sqlite3.Connection = DbDep,
):
    """List OSINT items, newest first, with source names joined."""
    where = ["1=1"]
    params: list = []
    if topic:
        if topic not in TOPICS:
            raise HTTPException(status_code=422, detail=f"Unknown topic: {topic}")
        where.append("i.topics LIKE ?")
        params.append(f'%"{topic}"%')
    if source_id:
        where.append("i.source_id = ?")
        params.append(source_id)
    if q:
        where.append("(i.title LIKE ? OR i.summary LIKE ?)")
        like = f"%{q}%"
        params.extend([like, like])
    if unread_only:
        where.append("i.is_read = 0")
    if starred_only:
        where.append("i.is_starred = 1")

    where_sql = " AND ".join(where)
    total = db.execute(
        f"SELECT COUNT(*) FROM osint_items i WHERE {where_sql}", params
    ).fetchone()[0]
    rows = db.execute(
        f"""SELECT i.*, s.name AS source_name, s.category AS source_category
            FROM osint_items i
            JOIN osint_sources s ON s.id = i.source_id
            WHERE {where_sql}
            ORDER BY COALESCE(i.published_at, i.fetched_at) DESC
            LIMIT ? OFFSET ?""",
        params + [limit, offset],
    ).fetchall()
    return {"items": [_item_dict(r) for r in rows], "total": total, "limit": limit, "offset": offset}


@router.get("/osint/topics")
def list_topics(db: sqlite3.Connection = DbDep):
    """Topic taxonomy with item and unread counts (for filter chips)."""
    out = []
    for slug, label in TOPICS.items():
        row = db.execute(
            """SELECT COUNT(*) AS total, SUM(CASE WHEN is_read = 0 THEN 1 ELSE 0 END) AS unread
               FROM osint_items WHERE topics LIKE ?""",
            (f'%"{slug}"%',),
        ).fetchone()
        out.append({"slug": slug, "label": label, "total": row["total"], "unread": row["unread"] or 0})
    all_row = db.execute(
        "SELECT COUNT(*) AS total, SUM(CASE WHEN is_read = 0 THEN 1 ELSE 0 END) AS unread FROM osint_items"
    ).fetchone()
    return {"topics": out, "all": {"total": all_row["total"], "unread": all_row["unread"] or 0}}


class ReadUpdate(BaseModel):
    is_read: bool = True


@router.post("/osint/items/{item_id}/read")
def set_item_read(item_id: str, body: ReadUpdate, db: sqlite3.Connection = DbDep):
    cur = db.execute(
        "UPDATE osint_items SET is_read = ? WHERE id = ?", (int(body.is_read), item_id)
    )
    if cur.rowcount == 0:
        raise HTTPException(status_code=404, detail="Item not found")
    db.commit()
    return {"id": item_id, "is_read": body.is_read}


class StarUpdate(BaseModel):
    is_starred: bool = True


@router.post("/osint/items/{item_id}/star")
def set_item_starred(item_id: str, body: StarUpdate, db: sqlite3.Connection = DbDep):
    cur = db.execute(
        "UPDATE osint_items SET is_starred = ? WHERE id = ?", (int(body.is_starred), item_id)
    )
    if cur.rowcount == 0:
        raise HTTPException(status_code=404, detail="Item not found")
    db.commit()
    return {"id": item_id, "is_starred": body.is_starred}


@router.post("/osint/items/mark-all-read")
def mark_all_read(
    topic: str | None = Query(None),
    source_id: str | None = Query(None),
    db: sqlite3.Connection = DbDep,
):
    """Mark all currently unread items as read, optionally scoped to a topic/source."""
    where = ["is_read = 0"]
    params: list = []
    if topic:
        if topic not in TOPICS:
            raise HTTPException(status_code=422, detail=f"Unknown topic: {topic}")
        where.append("topics LIKE ?")
        params.append(f'%"{topic}"%')
    if source_id:
        where.append("source_id = ?")
        params.append(source_id)
    cur = db.execute(f"UPDATE osint_items SET is_read = 1 WHERE {' AND '.join(where)}", params)
    db.commit()
    return {"marked_read": cur.rowcount}


# ── Sources ─────────────────────────────────────────────────────────────────


@router.get("/osint/sources")
def list_sources(db: sqlite3.Connection = DbDep):
    rows = db.execute(
        """SELECT s.*, COUNT(i.id) AS item_count
           FROM osint_sources s
           LEFT JOIN osint_items i ON i.source_id = s.id
           GROUP BY s.id
           ORDER BY s.name COLLATE NOCASE"""
    ).fetchall()
    return {"sources": [_source_dict(r) for r in rows], "count": len(rows)}


class SourceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    url: str = Field(min_length=8, max_length=2000)
    category: str = Field("news", max_length=50)
    default_topics: list[str] = Field(default_factory=list)


@router.post("/osint/sources", status_code=201)
def create_source(body: SourceCreate, db: sqlite3.Connection = DbDep):
    if not body.url.startswith(("http://", "https://")):
        raise HTTPException(status_code=422, detail="URL must start with http:// or https://")
    bad = [t for t in body.default_topics if t not in TOPICS]
    if bad:
        raise HTTPException(status_code=422, detail=f"Unknown topics: {bad}")
    source_id = str(uuid.uuid4())
    try:
        db.execute(
            """INSERT INTO osint_sources (id, name, url, category, default_topics)
               VALUES (?, ?, ?, ?, ?)""",
            (source_id, body.name, body.url, body.category, json.dumps(body.default_topics)),
        )
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="A source with this URL already exists")
    db.commit()
    row = db.execute("SELECT * FROM osint_sources WHERE id = ?", (source_id,)).fetchone()
    return _source_dict(row)


class SourceUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    url: str | None = Field(None, min_length=8, max_length=2000)
    category: str | None = Field(None, max_length=50)
    default_topics: list[str] | None = None
    enabled: bool | None = None


@router.patch("/osint/sources/{source_id}")
def update_source(source_id: str, body: SourceUpdate, db: sqlite3.Connection = DbDep):
    row = db.execute("SELECT * FROM osint_sources WHERE id = ?", (source_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Source not found")

    updates: dict = {}
    if body.name is not None:
        updates["name"] = body.name
    if body.url is not None:
        if not body.url.startswith(("http://", "https://")):
            raise HTTPException(status_code=422, detail="URL must start with http:// or https://")
        updates["url"] = body.url
        # New URL means cached validators no longer apply
        updates["etag"] = None
        updates["last_modified"] = None
    if body.category is not None:
        updates["category"] = body.category
    if body.default_topics is not None:
        bad = [t for t in body.default_topics if t not in TOPICS]
        if bad:
            raise HTTPException(status_code=422, detail=f"Unknown topics: {bad}")
        updates["default_topics"] = json.dumps(body.default_topics)
    if body.enabled is not None:
        updates["enabled"] = int(body.enabled)

    if updates:
        updates["updated_at"] = _now()
        set_sql = ", ".join(f"{k} = ?" for k in updates)
        try:
            db.execute(
                f"UPDATE osint_sources SET {set_sql} WHERE id = ?",
                list(updates.values()) + [source_id],
            )
        except sqlite3.IntegrityError:
            raise HTTPException(status_code=409, detail="A source with this URL already exists")
        db.commit()

    row = db.execute("SELECT * FROM osint_sources WHERE id = ?", (source_id,)).fetchone()
    return _source_dict(row)


@router.delete("/osint/sources/{source_id}", status_code=204)
def delete_source(source_id: str, db: sqlite3.Connection = DbDep):
    cur = db.execute("DELETE FROM osint_sources WHERE id = ?", (source_id,))
    if cur.rowcount == 0:
        raise HTTPException(status_code=404, detail="Source not found")
    db.commit()


@router.post("/osint/sources/seed-defaults")
def seed_defaults(db: sqlite3.Connection = DbDep):
    """Re-insert any missing curated default sources (never overwrites edits)."""
    from app.osint.sources import seed_default_sources

    inserted = seed_default_sources(db)
    return {"inserted": inserted}


# ── Refresh ─────────────────────────────────────────────────────────────────


@router.post("/osint/refresh")
def refresh(
    source_id: str | None = Query(None, description="Refresh a single source"),
    db: sqlite3.Connection = DbDep,
):
    """Fetch enabled sources now. Synchronous; returns per-source results."""
    from app.osint.fetcher import refresh_sources

    if source_id:
        row = db.execute("SELECT id FROM osint_sources WHERE id = ?", (source_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Source not found")
    return refresh_sources(db, source_id=source_id)
