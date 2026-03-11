"""
Cross-database integration endpoints.

Read-only access to cftc_regulatory.db and eo_tracker.db.
Also provides the rulemaking sync endpoint (UA + FR API).
"""

import json
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Path, Query

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


@router.get("/eo-summary")
async def get_eo_summary():
    """Aggregate statistics for the EO reference guide."""
    def _query():
        try:
            conn = get_readonly_eo_connection()
        except FileNotFoundError as e:
            raise HTTPException(503, str(e))
        try:
            total = conn.execute(
                "SELECT COUNT(*) as c FROM presidential_documents"
            ).fetchone()["c"]

            by_president = {}
            for row in conn.execute(
                "SELECT president, COUNT(*) as c FROM presidential_documents GROUP BY president"
            ).fetchall():
                by_president[row["president"]] = row["c"]

            by_status = {}
            for row in conn.execute(
                "SELECT status, COUNT(*) as c FROM presidential_documents GROUP BY status"
            ).fetchall():
                by_status[row["status"]] = row["c"]

            relevance_dist = {}
            for row in conn.execute(
                "SELECT cftc_relevance_score as score, COUNT(*) as c FROM analysis GROUP BY cftc_relevance_score"
            ).fetchall():
                relevance_dist[str(row["score"])] = row["c"]

            high_rel = conn.execute(
                "SELECT COUNT(*) as c FROM analysis WHERE cftc_relevance_score >= 3"
            ).fetchone()["c"]

            upcoming = conn.execute(
                """SELECT COUNT(*) as c FROM implementation_deadlines
                   WHERE calculated_due_date >= date('now')
                     AND calculated_due_date <= date('now', '+90 days')"""
            ).fetchone()["c"]

            open_actions = conn.execute(
                "SELECT COUNT(*) as c FROM action_items WHERE status NOT IN ('completed', 'superseded', 'not_applicable')"
            ).fetchone()["c"]

            return {
                "total_documents": total,
                "by_president": by_president,
                "by_status": by_status,
                "relevance_distribution": relevance_dist,
                "high_relevance_count": high_rel,
                "upcoming_deadlines": upcoming,
                "open_action_items": open_actions,
            }
        finally:
            conn.close()

    return await run_db(_query)


def _parse_json_field(val):
    """Safely parse a JSON string field, returning [] on failure."""
    if not val:
        return []
    try:
        return json.loads(val)
    except (json.JSONDecodeError, TypeError):
        return []


@router.get("/eo-documents")
async def get_eo_documents(
    president: Optional[str] = None,
    status: Optional[str] = None,
    min_relevance: Optional[int] = None,
    search: Optional[str] = None,
):
    """List executive orders with analysis data, server-side filtered."""
    def _query():
        try:
            conn = get_readonly_eo_connection()
        except FileNotFoundError as e:
            raise HTTPException(503, str(e))
        try:
            conditions = []
            params = []

            if president:
                conditions.append("pd.president = ?")
                params.append(president)
            if status:
                conditions.append("pd.status = ?")
                params.append(status)
            if min_relevance is not None:
                conditions.append("COALESCE(a.cftc_relevance_score, 0) >= ?")
                params.append(min_relevance)
            if search:
                conditions.append("pd.title LIKE ?")
                params.append(f"%{search}%")

            where = ""
            if conditions:
                where = "WHERE " + " AND ".join(conditions)

            rows = conn.execute(
                f"""SELECT
                        pd.id, pd.document_number, pd.executive_order_number,
                        pd.document_type, pd.title, pd.president,
                        pd.signing_date, pd.status, pd.html_url, pd.pdf_url,
                        a.cftc_relevance_score,
                        a.cftc_relevance_tags,
                        a.interagency_tags,
                        a.regulatory_relevance_tags,
                        a.selig_priority_alignment,
                        a.crypto_interagency_flag,
                        a.plain_language_summary
                    FROM presidential_documents pd
                    LEFT JOIN analysis a ON pd.id = a.document_id
                    {where}
                    ORDER BY pd.signing_date DESC""",
                params,
            ).fetchall()

            results = []
            for r in rows:
                d = dict(r)
                d["cftc_relevance_score"] = d.get("cftc_relevance_score") or 0
                d["crypto_interagency_flag"] = bool(d.get("crypto_interagency_flag"))
                d["cftc_relevance_tags"] = _parse_json_field(d.get("cftc_relevance_tags"))
                d["interagency_tags"] = _parse_json_field(d.get("interagency_tags"))
                d["regulatory_relevance_tags"] = _parse_json_field(d.get("regulatory_relevance_tags"))
                d["selig_priority_alignment"] = _parse_json_field(d.get("selig_priority_alignment"))
                results.append(d)
            return results
        finally:
            conn.close()

    return await run_db(_query)


@router.get("/eo-documents/{doc_id}")
async def get_eo_document_detail(doc_id: int = Path(...)):
    """Full detail for a single EO: metadata, analysis, deadlines, relationships, authorities, action items."""
    def _query():
        try:
            conn = get_readonly_eo_connection()
        except FileNotFoundError as e:
            raise HTTPException(503, str(e))
        try:
            doc = conn.execute(
                "SELECT * FROM presidential_documents WHERE id = ?", (doc_id,)
            ).fetchone()
            if not doc:
                raise HTTPException(404, f"Document {doc_id} not found")

            doc_dict = dict(doc)
            # Remove large text fields from the response
            doc_dict.pop("full_text", None)
            doc_dict.pop("full_text_html", None)

            # Analysis
            analysis_row = conn.execute(
                "SELECT * FROM analysis WHERE document_id = ?", (doc_id,)
            ).fetchone()
            analysis = None
            if analysis_row:
                analysis = dict(analysis_row)
                for field in ("cftc_relevance_tags", "interagency_tags",
                              "regulatory_relevance_tags", "selig_priority_alignment"):
                    analysis[field] = _parse_json_field(analysis.get(field))
                analysis["crypto_interagency_flag"] = bool(analysis.get("crypto_interagency_flag"))

            # Deadlines
            deadlines = [dict(r) for r in conn.execute(
                "SELECT * FROM implementation_deadlines WHERE document_id = ? ORDER BY calculated_due_date",
                (doc_id,),
            ).fetchall()]

            # Relationships — outgoing (what this doc acts on)
            outgoing = [dict(r) for r in conn.execute(
                """SELECT dr.relationship_type, dr.target_eo_number, dr.target_description,
                          pd.title as target_title, pd.status as target_status
                   FROM document_relationships dr
                   LEFT JOIN presidential_documents pd ON dr.target_document_id = pd.id
                   WHERE dr.source_document_id = ?""",
                (doc_id,),
            ).fetchall()]

            # Relationships — incoming (what acts on this doc)
            incoming = [dict(r) for r in conn.execute(
                """SELECT dr.relationship_type,
                          pd.executive_order_number as source_eo,
                          pd.title as source_title, pd.signing_date as source_date
                   FROM document_relationships dr
                   JOIN presidential_documents pd ON dr.source_document_id = pd.id
                   WHERE dr.target_document_id = ?""",
                (doc_id,),
            ).fetchall()]

            # Statutory authorities
            authorities = [dict(r) for r in conn.execute(
                "SELECT * FROM statutory_authorities WHERE document_id = ?", (doc_id,),
            ).fetchall()]

            # Action items
            action_items = [dict(r) for r in conn.execute(
                "SELECT * FROM action_items WHERE document_id = ? ORDER BY priority DESC",
                (doc_id,),
            ).fetchall()]

            return {
                "document": doc_dict,
                "analysis": analysis,
                "deadlines": deadlines,
                "relationships": {"outgoing": outgoing, "incoming": incoming},
                "authorities": authorities,
                "action_items": action_items,
            }
        finally:
            conn.close()

    return await run_db(_query)


@router.get("/eo-compliance")
async def get_eo_compliance():
    """Serve the Presidential Compliance Checklist (static JSON)."""
    import os
    data_dir = os.path.dirname(os.path.abspath(__file__))
    json_path = os.path.join(data_dir, "..", "data", "compliance_checklist.json")
    json_path = os.path.normpath(json_path)
    if not os.path.exists(json_path):
        raise HTTPException(404, "Compliance checklist data not found")
    with open(json_path, "r", encoding="utf-8") as f:
        return json.load(f)


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
