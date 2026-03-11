"""
Loper Bright Vulnerability Analyzer — API router.

Read-only endpoints for browsing Stage 1 scores, Stage 2 assessments,
challenge history, and analytics. All data comes from cftc_regulatory.db.
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.pipeline.db_async import run_db
from app.pipeline.connection import get_readonly_regulatory_connection

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/loper", tags=["Loper Bright Analyzer"])


def _with_reg_conn(fn):
    """Wrap a function that needs a regulatory DB connection."""
    def wrapper():
        try:
            conn = get_readonly_regulatory_connection()
        except FileNotFoundError as e:
            raise HTTPException(503, str(e))
        try:
            return fn(conn)
        finally:
            conn.close()
    return wrapper


# ── Rules ─────────────────────────────────────────────────────────────

@router.get("/rules")
async def list_rules(
    action_category: Optional[str] = None,
    vulnerability: Optional[str] = None,
    min_score: Optional[float] = None,
    max_score: Optional[float] = None,
    search: Optional[str] = None,
    has_challenge: Optional[bool] = None,
    has_dissent: Optional[bool] = None,
    validation: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    sort: str = "composite_score",
    order: str = "desc",
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    """Paginated, filtered, sorted rules list with Stage 2 data."""
    from app.pipeline.services.loper import list_rules as _list

    def _query():
        conn = get_readonly_regulatory_connection()
        try:
            items, total = _list(
                conn,
                action_category=action_category,
                vulnerability=vulnerability,
                min_score=min_score,
                max_score=max_score,
                search=search,
                has_challenge=has_challenge,
                has_dissent=has_dissent,
                validation=validation,
                date_from=date_from,
                date_to=date_to,
                sort=sort,
                order=order,
                page=page,
                page_size=page_size,
            )
            return {"items": items, "total": total, "page": page, "page_size": page_size}
        finally:
            conn.close()

    return await run_db(_query)


@router.get("/rules/{fr_citation}")
async def get_rule(fr_citation: str):
    """Full rule detail with S2 assessments, challenges, related items."""
    from app.pipeline.services.loper import get_rule_detail

    def _query():
        conn = get_readonly_regulatory_connection()
        try:
            result = get_rule_detail(conn, fr_citation)
            if not result:
                raise HTTPException(404, f"No rule found for {fr_citation}")
            return result
        finally:
            conn.close()

    return await run_db(_query)


# ── Guidance ──────────────────────────────────────────────────────────

@router.get("/guidance")
async def list_guidance_endpoint(
    action_category: Optional[str] = None,
    document_type: Optional[str] = None,
    division: Optional[str] = None,
    min_score: Optional[float] = None,
    max_score: Optional[float] = None,
    min_binding: Optional[float] = None,
    vulnerability: Optional[str] = None,
    search: Optional[str] = None,
    sort: str = "composite_score",
    order: str = "desc",
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    """Paginated, filtered, sorted guidance list."""
    from app.pipeline.services.loper import list_guidance as _list

    def _query():
        conn = get_readonly_regulatory_connection()
        try:
            items, total = _list(
                conn,
                action_category=action_category,
                document_type=document_type,
                division=division,
                min_score=min_score,
                max_score=max_score,
                min_binding=min_binding,
                vulnerability=vulnerability,
                search=search,
                sort=sort,
                order=order,
                page=page,
                page_size=page_size,
            )
            return {"items": items, "total": total, "page": page, "page_size": page_size}
        finally:
            conn.close()

    return await run_db(_query)


@router.get("/guidance/{doc_id}")
async def get_guidance(doc_id: str):
    """Full guidance detail with parent rules and related guidance."""
    from app.pipeline.services.loper import get_guidance_detail

    def _query():
        conn = get_readonly_regulatory_connection()
        try:
            result = get_guidance_detail(conn, doc_id)
            if not result:
                raise HTTPException(404, f"No guidance found for {doc_id}")
            return result
        finally:
            conn.close()

    return await run_db(_query)


# ── Dashboard ─────────────────────────────────────────────────────────

@router.get("/dashboard")
async def get_dashboard():
    """Aggregated dashboard metrics for the overview page."""
    from app.pipeline.services.loper import (
        get_dashboard_stats,
        get_heatmap_data,
        get_active_challenges,
    )

    def _query():
        conn = get_readonly_regulatory_connection()
        try:
            stats = get_dashboard_stats(conn)
            heatmap = get_heatmap_data(conn)
            challenges = get_active_challenges(conn)
            return {
                **stats,
                "heatmap_data": heatmap,
                "active_challenge_details": challenges,
            }
        finally:
            conn.close()

    return await run_db(_query)


# ── Analytics ─────────────────────────────────────────────────────────

@router.get("/analytics/{analysis_type}")
async def get_analytics(analysis_type: str):
    """Analytics data by type: by_theory, by_provision, by_era,
    dimension_correlation, compound_vulnerability."""
    from app.pipeline.services import loper as svc

    handlers = {
        "by_theory": svc.get_analytics_by_theory,
        "by_provision": svc.get_analytics_by_provision,
        "by_era": svc.get_analytics_by_era,
        "dimension_correlation": svc.get_analytics_dimension_correlation,
        "compound_vulnerability": svc.get_analytics_compound_vulnerability,
    }

    handler = handlers.get(analysis_type)
    if not handler:
        raise HTTPException(400, f"Unknown analysis type: {analysis_type}")

    def _query():
        conn = get_readonly_regulatory_connection()
        try:
            return {"type": analysis_type, "data": handler(conn)}
        finally:
            conn.close()

    return await run_db(_query)
