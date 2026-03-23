"""Context Notes CRUD endpoints."""
import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from app.db import get_db
from app.validators import CreateContextNote, UpdateContextNote, CreateContextNoteLink
import json
from fastapi import Request
from fastapi.responses import JSONResponse
from app.deps import get_write_source
from app.audit import log_event
from app.concurrency import get_etag, check_etag
from app.idempotency import claim_idempotency_key, finalize_idempotency_key

router = APIRouter(prefix="/context-notes", tags=["context-notes"])

# ── Enum validation sets ─────────────────────────────────────────────────────

VALID_CATEGORIES = {
    "people_insight", "institutional_knowledge", "process_note",
    "policy_operating_rule", "strategic_context", "culture_climate",
    "relationship_dynamic",
}

VALID_POSTURES = {
    "factual", "attributed_view", "tentative", "interpretive", "sensitive",
}

VALID_DURABILITIES = {"ephemeral", "medium_term", "durable"}

VALID_SENSITIVITIES = {"low", "moderate", "high"}

VALID_ENTITY_TYPES = {
    "person", "organization", "matter", "meeting", "task", "document", "decision",
}

VALID_RELATIONSHIP_ROLES = {
    "subject", "source", "relevant_to", "affects", "mentioned_in",
    "action_context", "supervisory_context", "stakeholder_context",
}


def _validate_enums(data: dict, is_create: bool = True):
    """Validate enum fields. On create, category/posture are required."""
    if "category" in data and data["category"] not in VALID_CATEGORIES:
        raise HTTPException(400, detail=f"Invalid category '{data['category']}'. Must be one of: {sorted(VALID_CATEGORIES)}")
    if "posture" in data and data["posture"] not in VALID_POSTURES:
        raise HTTPException(400, detail=f"Invalid posture '{data['posture']}'. Must be one of: {sorted(VALID_POSTURES)}")
    if "durability" in data and data["durability"] not in VALID_DURABILITIES:
        raise HTTPException(400, detail=f"Invalid durability '{data['durability']}'. Must be one of: {sorted(VALID_DURABILITIES)}")
    if "sensitivity" in data and data["sensitivity"] not in VALID_SENSITIVITIES:
        raise HTTPException(400, detail=f"Invalid sensitivity '{data['sensitivity']}'. Must be one of: {sorted(VALID_SENSITIVITIES)}")


def _validate_link_enums(entity_type: str, relationship_role: str):
    """Validate entity_type and relationship_role for links."""
    if entity_type not in VALID_ENTITY_TYPES:
        raise HTTPException(400, detail=f"Invalid entity_type '{entity_type}'. Must be one of: {sorted(VALID_ENTITY_TYPES)}")
    if relationship_role not in VALID_RELATIONSHIP_ROLES:
        raise HTTPException(400, detail=f"Invalid relationship_role '{relationship_role}'. Must be one of: {sorted(VALID_RELATIONSHIP_ROLES)}")


# ── List ─────────────────────────────────────────────────────────────────────

@router.get("")
async def list_context_notes(
    db=Depends(get_db),
    search: str = Query(None),
    category: str = Query(None),
    posture: str = Query(None),
    durability: str = Query(None),
    sensitivity: str = Query(None),
    matter_id: str = Query(None),
    entity_type: str = Query(None),
    entity_id: str = Query(None),
    source_type: str = Query(None),
    stale: bool = Query(None),
    sort_by: str = Query("created_at"),
    sort_dir: str = Query("desc"),
    limit: int = Query(100, le=500),
    offset: int = Query(0),
):
    # If filtering by entity, we need to join context_note_links
    join_links = entity_type and entity_id

    conditions, params = ["cn.is_active = 1"], []

    if search:
        conditions.append("(cn.title LIKE ? OR cn.body LIKE ?)")
        params.extend([f"%{search}%", f"%{search}%"])
    if category:
        conditions.append("cn.category = ?")
        params.append(category)
    if posture:
        conditions.append("cn.posture = ?")
        params.append(posture)
    if durability:
        conditions.append("cn.durability = ?")
        params.append(durability)
    if sensitivity:
        conditions.append("cn.sensitivity = ?")
        params.append(sensitivity)
    if matter_id:
        conditions.append("cn.matter_id = ?")
        params.append(matter_id)
    if source_type:
        conditions.append("cn.source_type = ?")
        params.append(source_type)
    if stale is True:
        conditions.append("cn.stale_after IS NOT NULL AND cn.stale_after <= datetime('now')")
    elif stale is False:
        conditions.append("(cn.stale_after IS NULL OR cn.stale_after > datetime('now'))")
    if join_links:
        conditions.append("cnl.entity_type = ? AND cnl.entity_id = ?")
        params.extend([entity_type, entity_id])

    where = "WHERE " + " AND ".join(conditions)

    link_join = "JOIN context_note_links cnl ON cn.id = cnl.context_note_id" if join_links else ""

    allowed_sorts = {"created_at", "title", "category", "posture", "sensitivity", "durability", "updated_at"}
    if sort_by not in allowed_sorts:
        sort_by = "created_at"
    direction = "DESC" if sort_dir.lower() == "desc" else "ASC"

    total = db.execute(f"""
        SELECT COUNT(DISTINCT cn.id) as c FROM context_notes cn {link_join} {where}
    """, params).fetchone()["c"]

    rows = db.execute(f"""
        SELECT DISTINCT cn.*
        FROM context_notes cn
        {link_join}
        {where}
        ORDER BY cn.{sort_by} {direction}
        LIMIT ? OFFSET ?
    """, params + [limit, offset]).fetchall()

    items = []
    for row in rows:
        item = dict(row)
        # Attach links
        links = db.execute("""
            SELECT cnl.id, cnl.entity_type, cnl.entity_id, cnl.relationship_role
            FROM context_note_links cnl
            WHERE cnl.context_note_id = ?
        """, (item["id"],)).fetchall()
        item["links"] = [dict(link) for link in links]
        items.append(item)

    return {"items": items, "total": total, "limit": limit, "offset": offset}


# ── By Entity (convenience) ─────────────────────────────────────────────────

@router.get("/by-entity/{entity_type}/{entity_id}")
async def get_context_notes_by_entity(
    entity_type: str,
    entity_id: str,
    db=Depends(get_db),
    category: str = Query(None),
    posture: str = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0),
):
    if entity_type not in VALID_ENTITY_TYPES:
        raise HTTPException(400, detail=f"Invalid entity_type '{entity_type}'")

    conditions = ["cn.is_active = 1", "cnl.entity_type = ?", "cnl.entity_id = ?"]
    params = [entity_type, entity_id]

    if category:
        conditions.append("cn.category = ?")
        params.append(category)
    if posture:
        conditions.append("cn.posture = ?")
        params.append(posture)

    where = "WHERE " + " AND ".join(conditions)

    rows = db.execute(f"""
        SELECT cn.*, cnl.relationship_role as link_role
        FROM context_notes cn
        JOIN context_note_links cnl ON cn.id = cnl.context_note_id
        {where}
        ORDER BY cn.created_at DESC
        LIMIT ? OFFSET ?
    """, params + [limit, offset]).fetchall()

    items = []
    for row in rows:
        item = dict(row)
        links = db.execute("""
            SELECT cnl.id, cnl.entity_type, cnl.entity_id, cnl.relationship_role
            FROM context_note_links cnl WHERE cnl.context_note_id = ?
        """, (item["id"],)).fetchall()
        item["links"] = [dict(link) for link in links]
        items.append(item)

    return {"items": items, "total": len(items)}


# ── Get ──────────────────────────────────────────────────────────────────────

@router.get("/{note_id}")
async def get_context_note(note_id: str, db=Depends(get_db)):
    row = db.execute("""
        SELECT cn.* FROM context_notes cn WHERE cn.id = ? AND cn.is_active = 1
    """, (note_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Context note not found")

    result = dict(row)

    # Attach links with resolved entity names
    links = db.execute("""
        SELECT cnl.id, cnl.entity_type, cnl.entity_id, cnl.relationship_role
        FROM context_note_links cnl WHERE cnl.context_note_id = ?
    """, (note_id,)).fetchall()

    resolved_links = []
    for link in links:
        ld = dict(link)
        # Resolve entity name
        ld["entity_name"] = _resolve_entity_name(db, ld["entity_type"], ld["entity_id"])
        resolved_links.append(ld)

    result["links"] = resolved_links

    return JSONResponse(content=result, headers={"ETag": get_etag(row)})


def _resolve_entity_name(db, entity_type: str, entity_id: str) -> str:
    """Resolve an entity ID to a display name."""
    table_map = {
        "person": ("people", "full_name"),
        "organization": ("organizations", "name"),
        "matter": ("matters", "title"),
        "meeting": ("meetings", "title"),
        "task": ("tasks", "title"),
        "document": ("documents", "title"),
        "decision": ("decisions", "title"),
    }
    if entity_type not in table_map:
        return None
    table, col = table_map[entity_type]
    row = db.execute(f"SELECT {col} FROM {table} WHERE id = ?", (entity_id,)).fetchone()
    return row[col] if row else None


# ── Create ───────────────────────────────────────────────────────────────────

@router.post("")
async def create_context_note(body: CreateContextNote, request: Request, db=Depends(get_db),
                               write_source: str = Depends(get_write_source)):
    idem_key = request.headers.get("idempotency-key")
    cached = claim_idempotency_key(db, idem_key, body.model_dump(), "/tracker/context-notes")
    if cached == "conflict":
        raise HTTPException(409, detail="Idempotency key reused with different payload")
    if cached == "pending":
        raise HTTPException(409, detail="Request with this idempotency key is still in progress")
    if isinstance(cached, dict):
        return JSONResponse(status_code=cached["status_code"], content=json.loads(cached["body"]))

    data = body.model_dump()
    _validate_enums(data, is_create=True)

    nid = str(uuid.uuid4())
    now = datetime.now().isoformat()
    source_val = write_source if body.source == "manual" else body.source

    db.execute("""
        INSERT INTO context_notes (
            id, title, body, category, posture, durability, sensitivity, status,
            confidence, source_type, source_id, source_excerpt,
            source_timestamp_start, source_timestamp_end, speaker_attribution,
            created_by_type, created_by_person_id, effective_date, stale_after,
            notes_visibility, matter_id, source_communication_id,
            is_active, source, ai_confidence, automation_hold, external_refs,
            created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        nid, body.title, body.body, body.category, body.posture,
        body.durability, body.sensitivity, body.status,
        body.confidence, body.source_type, body.source_id, body.source_excerpt,
        body.source_timestamp_start, body.source_timestamp_end, body.speaker_attribution,
        body.created_by_type, body.created_by_person_id, body.effective_date, body.stale_after,
        body.notes_visibility, body.matter_id, body.source_communication_id,
        1, source_val, body.ai_confidence, body.automation_hold, body.external_refs,
        now, now,
    ))

    new_data = data.copy()
    new_data.update({"id": nid, "source": source_val, "created_at": now, "updated_at": now})
    log_event(db, table_name="context_notes", record_id=nid, action="create",
              source=write_source, new_data=new_data)

    result = {"id": nid}
    finalize_idempotency_key(db, idem_key, 200, result)
    db.commit()
    return result


# ── Update ───────────────────────────────────────────────────────────────────

@router.put("/{note_id}")
async def update_context_note(note_id: str, body: UpdateContextNote, request: Request,
                               db=Depends(get_db), write_source: str = Depends(get_write_source)):
    old = db.execute("SELECT * FROM context_notes WHERE id = ? AND is_active = 1", (note_id,)).fetchone()
    if not old:
        raise HTTPException(status_code=404, detail="Context note not found")
    check_etag(request, old)

    data = body.model_dump(exclude_unset=True)
    if not data:
        raise HTTPException(status_code=400, detail="No fields to update")
    _validate_enums(data, is_create=False)

    now = datetime.now().isoformat()
    sets = [f"{k} = ?" for k in data]
    params = list(data.values())
    sets.append("updated_at = ?")
    params.extend([now, note_id])

    db.execute(f"UPDATE context_notes SET {', '.join(sets)} WHERE id = ?", params)
    log_event(db, table_name="context_notes", record_id=note_id, action="update",
              source=write_source, old_record=old, new_data=data)
    db.commit()
    return {"id": note_id, "updated": True}


# ── Delete (soft) ────────────────────────────────────────────────────────────

@router.delete("/{note_id}")
async def delete_context_note(note_id: str, request: Request, db=Depends(get_db),
                               write_source: str = Depends(get_write_source)):
    old = db.execute("SELECT * FROM context_notes WHERE id = ? AND is_active = 1", (note_id,)).fetchone()
    if not old:
        raise HTTPException(status_code=404, detail="Context note not found")
    check_etag(request, old)

    now = datetime.now().isoformat()
    db.execute("UPDATE context_notes SET is_active = 0, updated_at = ? WHERE id = ?", (now, note_id))
    log_event(db, table_name="context_notes", record_id=note_id, action="delete",
              source=write_source, old_record=old)
    db.commit()
    return {"id": note_id, "deleted": True}


# ── Links ────────────────────────────────────────────────────────────────────

@router.post("/{note_id}/links")
async def add_context_note_link(note_id: str, body: CreateContextNoteLink,
                                 db=Depends(get_db), write_source: str = Depends(get_write_source)):
    note = db.execute("SELECT id FROM context_notes WHERE id = ? AND is_active = 1", (note_id,)).fetchone()
    if not note:
        raise HTTPException(status_code=404, detail="Context note not found")

    _validate_link_enums(body.entity_type, body.relationship_role)

    lid = str(uuid.uuid4())
    now = datetime.now().isoformat()
    db.execute("""
        INSERT INTO context_note_links (id, context_note_id, entity_type, entity_id, relationship_role, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (lid, note_id, body.entity_type, body.entity_id, body.relationship_role, now))

    log_event(db, table_name="context_note_links", record_id=lid, action="create",
              source=write_source, new_data={
                  "context_note_id": note_id, "entity_type": body.entity_type,
                  "entity_id": body.entity_id, "relationship_role": body.relationship_role,
              })
    db.commit()
    return {"id": lid}


@router.delete("/{note_id}/links/{link_id}")
async def remove_context_note_link(note_id: str, link_id: str,
                                    db=Depends(get_db), write_source: str = Depends(get_write_source)):
    link = db.execute("""
        SELECT * FROM context_note_links WHERE id = ? AND context_note_id = ?
    """, (link_id, note_id)).fetchone()
    if not link:
        raise HTTPException(status_code=404, detail="Link not found")

    db.execute("DELETE FROM context_note_links WHERE id = ?", (link_id,))
    log_event(db, table_name="context_note_links", record_id=link_id, action="delete",
              source=write_source, old_record=link)
    db.commit()
    return {"id": link_id, "deleted": True}
