"""Research notes sub-routes for policy directives — appended to policy_directives.py."""

import uuid
from datetime import datetime
from fastapi import Depends, HTTPException, Query
from app.db import get_db
from app.validators import CreateDirectiveResearchNote, UpdateDirectiveResearchNote


def register_research_notes(router):
    """Register research notes endpoints on the given router."""

    @router.get("/{directive_id}/research-notes")
    async def list_research_notes(
        directive_id: str,
        db=Depends(get_db),
        needs_reading: int = Query(None),
        promote: int = Query(None),
    ):
        conditions = ["directive_id = ?"]
        params = [directive_id]
        if needs_reading is not None:
            conditions.append("needs_reg_reading = ?")
            params.append(needs_reading)
        if promote is not None:
            conditions.append("promote_to_matter = ?")
            params.append(promote)
        where = "WHERE " + " AND ".join(conditions)
        rows = db.execute(
            "SELECT * FROM directive_research_notes "
            + where
            + " ORDER BY composite_score DESC, fr_citation",
            params,
        ).fetchall()
        return [dict(r) for r in rows]

    @router.post("/{directive_id}/research-notes")
    async def add_research_note(
        directive_id: str,
        body: CreateDirectiveResearchNote,
        db=Depends(get_db),
    ):
        if not db.execute(
            "SELECT 1 FROM policy_directives WHERE id = ?", (directive_id,)
        ).fetchone():
            raise HTTPException(status_code=404, detail="Directive not found")
        note_id = str(uuid.uuid4())
        now = datetime.now().isoformat()
        db.execute(
            "INSERT INTO directive_research_notes "
            "(id, directive_id, fr_citation, rule_title, cfr_parts, "
            "statutory_authority, action_category, composite_score, "
            "relationship_basis, analysis_summary, regulation_text_excerpt, "
            "needs_reg_reading, reg_reading_done, reg_reading_notes, "
            "promote_to_matter, matter_id, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                note_id,
                directive_id,
                body.fr_citation,
                body.rule_title,
                body.cfr_parts,
                body.statutory_authority,
                body.action_category,
                body.composite_score,
                body.relationship_basis,
                body.analysis_summary,
                body.regulation_text_excerpt,
                body.needs_reg_reading,
                body.reg_reading_done,
                body.reg_reading_notes,
                body.promote_to_matter,
                body.matter_id,
                now,
                now,
            ),
        )
        db.commit()
        return {"id": note_id}

    @router.put("/{directive_id}/research-notes/{note_id}")
    async def update_research_note(
        directive_id: str,
        note_id: str,
        body: UpdateDirectiveResearchNote,
        db=Depends(get_db),
    ):
        old = db.execute(
            "SELECT * FROM directive_research_notes WHERE id = ? AND directive_id = ?",
            (note_id, directive_id),
        ).fetchone()
        if not old:
            raise HTTPException(status_code=404, detail="Research note not found")
        data = body.model_dump(exclude_unset=True)
        if not data:
            raise HTTPException(status_code=400, detail="No fields to update")
        now = datetime.now().isoformat()
        set_clauses = ", ".join(k + " = ?" for k in data)
        params = list(data.values())
        set_clauses += ", updated_at = ?"
        params.extend([now, note_id, directive_id])
        db.execute(
            "UPDATE directive_research_notes SET "
            + set_clauses
            + " WHERE id = ? AND directive_id = ?",
            params,
        )
        db.commit()
        return {"id": note_id, "updated": True}

    @router.delete("/{directive_id}/research-notes/{note_id}")
    async def delete_research_note(directive_id: str, note_id: str, db=Depends(get_db)):
        db.execute(
            "DELETE FROM directive_research_notes WHERE id = ? AND directive_id = ?",
            (note_id, directive_id),
        )
        db.commit()
        return {"deleted": True}
