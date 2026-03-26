"""Intelligence briefs API router.

Endpoints for listing, viewing, and manually generating daily/weekly briefs.
"""

import json
import logging
from datetime import date

from fastapi import APIRouter, HTTPException, Query

from app.db import get_connection

logger = logging.getLogger(__name__)
router = APIRouter(tags=["intelligence"])


@router.get("/intelligence/briefs")
def list_briefs(
    brief_type: str = Query("daily", description="daily or weekly"),
    limit: int = Query(20, ge=1, le=100),
):
    """List recent intelligence briefs."""
    db = get_connection()
    try:
        rows = db.execute(
            """SELECT id, brief_type, brief_date, model_used, docx_file_path, created_at
               FROM intelligence_briefs
               WHERE brief_type = ?
               ORDER BY brief_date DESC
               LIMIT ?""",
            (brief_type, limit),
        ).fetchall()
        return {"items": [dict(r) for r in rows], "count": len(rows)}
    finally:
        db.close()


@router.get("/intelligence/briefs/{brief_id}")
def get_brief(brief_id: str):
    """Get a specific brief with full content."""
    db = get_connection()
    try:
        row = db.execute(
            "SELECT * FROM intelligence_briefs WHERE id = ?", (brief_id,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Brief not found")
        result = dict(row)
        # Parse JSON content
        if result.get("content"):
            try:
                result["content"] = json.loads(result["content"])
            except (json.JSONDecodeError, TypeError):
                pass
        return result
    finally:
        db.close()


@router.get("/intelligence/briefs/by-date/{brief_type}/{brief_date}")
def get_brief_by_date(brief_type: str, brief_date: str):
    """Get a brief by type and date."""
    db = get_connection()
    try:
        row = db.execute(
            "SELECT * FROM intelligence_briefs WHERE brief_type = ? AND brief_date = ? ORDER BY created_at DESC LIMIT 1",
            (brief_type, brief_date),
        ).fetchone()
        if not row:
            raise HTTPException(
                status_code=404,
                detail=f"No brief found for {brief_type} on {brief_date}",
            )
        result = dict(row)
        if result.get("content"):
            try:
                result["content"] = json.loads(result["content"])
            except (json.JSONDecodeError, TypeError):
                pass
        return result
    finally:
        db.close()


@router.post("/intelligence/generate")
def generate_brief(
    brief_type: str = Query("daily", description="daily, weekly, or dev-report"),
):
    """Manually trigger brief generation.

    This runs synchronously and returns the generated brief.
    Use for testing or ad-hoc generation.
    """
    db = get_connection()
    try:
        if brief_type == "daily":
            from app.jobs.daily_brief import generate_daily_brief, store_brief
            from app.jobs.html_renderer import render_daily_html
            from app.jobs.docx_renderer import render_daily_docx
            from app.jobs.email_sender import send_email

            # Try to get LLM client for meeting prep
            llm_client = None
            try:
                from app.llm.client import get_llm_client

                llm_client = get_llm_client()
            except Exception:
                logger.info("LLM client unavailable, skipping meeting prep narratives")

            data = generate_daily_brief(db, llm_client=llm_client)
            today = date.today().isoformat()

            # Render
            html = render_daily_html(data)
            docx_path = render_daily_docx(data)

            # Store
            model = (
                "haiku"
                if any(m.get("prep_narrative") for m in data.get("meetings", []))
                else None
            )
            brief_id = store_brief(db, "daily", today, data, str(docx_path), model)

            # Send email
            send_email(
                subject=f"CFTC Daily Brief \u2014 {data.get('date_display', today)}",
                html_body=html,
                docx_path=docx_path,
            )

            return {
                "status": "generated",
                "brief_id": brief_id,
                "brief_type": "daily",
                "date": today,
                "sections": {
                    "what_changed": len(data.get("what_changed", [])),
                    "action_list": len(data.get("action_list", [])),
                    "meetings": len(data.get("meetings", [])),
                    "followups": len(data.get("followups", [])),
                },
                "email_sent": True,
                "docx_path": str(docx_path),
            }

        elif brief_type == "weekly":
            from app.jobs.weekly_brief import (
                generate_weekly_brief,
                add_executive_summary,
            )
            from app.jobs.daily_brief import store_brief
            from app.jobs.html_renderer import render_weekly_html
            from app.jobs.docx_renderer import render_weekly_docx
            from app.jobs.email_sender import send_email

            data = generate_weekly_brief(db)

            # Try Sonnet exec summary
            try:
                data = add_executive_summary(data, True)
            except Exception as e:
                logger.warning("Sonnet exec summary failed: %s", e)

            today = date.today().isoformat()
            html = render_weekly_html(data)
            docx_path = render_weekly_docx(data)
            model = "sonnet" if data.get("executive_summary") else None
            brief_id = store_brief(db, "weekly", today, data, str(docx_path), model)

            send_email(
                subject=f"CFTC Weekly Brief \u2014 {data.get('date_display', today)}",
                html_body=html,
                docx_path=docx_path,
            )

            return {
                "status": "generated",
                "brief_id": brief_id,
                "brief_type": "weekly",
                "date": today,
                "sections": {
                    "portfolio_total": data.get("portfolio", {}).get("total_active", 0),
                    "decisions": len(data.get("decisions", [])),
                    "hygiene_score": data.get("hygiene", {}).get("score", 0),
                    "has_exec_summary": data.get("executive_summary") is not None,
                },
                "email_sent": True,
            }

        elif brief_type == "dev-report":
            from app.jobs.dev_report import generate_dev_report
            from app.jobs.daily_brief import store_brief
            from app.jobs.html_renderer import render_dev_report_html
            from app.jobs.email_sender import send_email

            data = generate_dev_report(db)
            today = date.today().isoformat()
            html = render_dev_report_html(data)
            brief_id = store_brief(db, "dev-report", today, data, None, None)

            send_email(
                subject="CFTC App Health — " + data.get("date_display", today),
                html_body=html,
            )

            return {
                "status": "generated",
                "brief_id": brief_id,
                "brief_type": "dev-report",
                "date": today,
                "overall_score": data.get("overall_score", 0),
                "underused_fields": len(data.get("underused", [])),
                "suggestions": len(data.get("suggestions", [])),
                "email_sent": True,
            }

        else:
            return {"error": f"Unknown brief type: {brief_type}"}

    except Exception as e:
        logger.error("Brief generation failed: %s", e, exc_info=True)
        return {"error": str(e)}
    finally:
        db.close()
