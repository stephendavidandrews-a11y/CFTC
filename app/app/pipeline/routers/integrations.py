"""
Cross-database integration endpoints.

Read-only access to cftc_regulatory.db and eo_tracker.db.
Also provides the rulemaking sync endpoint (UA + FR API).
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.pipeline.db_async import run_db
from app.pipeline.connection import (
    get_readonly_regulatory_connection,
    get_readonly_eo_connection,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/integrations", tags=["Pipeline Integrations"])


@router.post("/sync")
async def trigger_sync():
    """
    Trigger a rulemaking sync: pull from Unified Agenda + Federal Register API.
    Creates/updates pipeline items, logs FR documents, and creates deadlines.
    """
    from app.pipeline.services.sync import run_sync

    def _run():
        return run_sync()

    try:
        result = await run_db(_run)
        return result
    except Exception as e:
        logger.error(f"Sync failed: {e}")
        raise HTTPException(500, f"Sync failed: {str(e)}")


@router.get("/stage1-scores/{fr_citation}")
async def get_stage1_scores(fr_citation: str):
    """Pull Stage 1 scores from cftc_regulatory.db by FR citation."""
    def _query():
        try:
            conn = get_readonly_regulatory_connection()
        except FileNotFoundError as e:
            raise HTTPException(503, str(e))
        try:
            # Check stage1_scores (rules)
            rule = conn.execute(
                """SELECT * FROM stage1_scores
                   WHERE fr_citation = ?""",
                (fr_citation,),
            ).fetchone()
            if rule:
                return {"type": "rule", "scores": dict(rule)}

            # Check stage1_guidance_scores
            guidance = conn.execute(
                """SELECT * FROM stage1_guidance_scores
                   WHERE fr_citation = ?""",
                (fr_citation,),
            ).fetchone()
            if guidance:
                return {"type": "guidance", "scores": dict(guidance)}

            return {"type": None, "scores": None}
        finally:
            conn.close()

    return await run_db(_query)


@router.get("/stage1-doc/{doc_id}")
async def get_stage1_by_doc_id(doc_id: str):
    """Pull Stage 1 guidance scores by document ID."""
    def _query():
        try:
            conn = get_readonly_regulatory_connection()
        except FileNotFoundError as e:
            raise HTTPException(503, str(e))
        try:
            row = conn.execute(
                "SELECT * FROM stage1_guidance_scores WHERE doc_id = ?",
                (doc_id,),
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    result = await run_db(_query)
    if not result:
        raise HTTPException(404, f"No Stage 1 scores for doc_id={doc_id}")
    return result


@router.get("/eo-actions")
async def get_eo_actions(
    status: Optional[str] = None,
    cftc_role: Optional[str] = None,
):
    """Pull CFTC-relevant EO action items from eo_tracker.db."""
    def _query():
        try:
            conn = get_readonly_eo_connection()
        except FileNotFoundError as e:
            raise HTTPException(503, str(e))
        try:
            conditions = []
            params = []
            if status:
                conditions.append("status = ?")
                params.append(status)
            if cftc_role:
                conditions.append("cftc_role = ?")
                params.append(cftc_role)

            where = ""
            if conditions:
                where = "WHERE " + " AND ".join(conditions)

            rows = conn.execute(
                f"""SELECT * FROM action_items
                    {where}
                    ORDER BY deadline ASC""",
                params,
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    return await run_db(_query)


@router.get("/eo-deadlines")
async def get_eo_deadlines():
    """Pull upcoming EO implementation deadlines."""
    def _query():
        try:
            conn = get_readonly_eo_connection()
        except FileNotFoundError as e:
            raise HTTPException(503, str(e))
        try:
            rows = conn.execute(
                """SELECT id.*, pd.title as doc_title
                   FROM implementation_deadlines id
                   JOIN presidential_documents pd ON id.document_id = pd.id
                   WHERE id.status = 'pending'
                   ORDER BY id.deadline_date ASC
                   LIMIT 20"""
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    return await run_db(_query)


@router.get("/search")
async def cross_db_search(q: str = Query(..., min_length=2)):
    """Search across pipeline and regulatory databases."""
    def _query():
        results = {"pipeline_items": [], "regulatory_docs": []}
        term = f"%{q}%"

        # Search pipeline items (use regular connection)
        from app.pipeline.connection import get_connection
        conn = get_connection()
        try:
            rows = conn.execute(
                """SELECT id, module, item_type, title, docket_number, status
                   FROM pipeline_items
                   WHERE title LIKE ? OR docket_number LIKE ? OR description LIKE ?
                   LIMIT 20""",
                (term, term, term),
            ).fetchall()
            results["pipeline_items"] = [dict(r) for r in rows]
        finally:
            conn.close()

        # Search cftc_regulatory.db documents
        try:
            reg_conn = get_readonly_regulatory_connection()
            try:
                rows = reg_conn.execute(
                    """SELECT id, doc_type, title, fr_citation, cfr_title
                       FROM documents
                       WHERE title LIKE ? OR fr_citation LIKE ?
                       LIMIT 20""",
                    (term, term),
                ).fetchall()
                results["regulatory_docs"] = [dict(r) for r in rows]
            finally:
                reg_conn.close()
        except FileNotFoundError:
            pass

        return results

    return await run_db(_query)
