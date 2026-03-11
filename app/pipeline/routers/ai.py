"""
AI-powered features: note processing, delegation recommendations, email parsing.
"""

import json
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException

from app.pipeline.db_async import run_db
from app.pipeline.connection import get_connection
from app.work.db import get_connection as get_work_connection, attach_pipeline
from app.pipeline.services import ai_service as ai_svc
from app.pipeline.services import team as team_svc
from app.pipeline.models import (
    NoteProcessRequest,
    DelegationRecommendRequest,
    EmailParseRequest,
    AIUsageResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ai", tags=["AI Features"])


def _pipeline_conn():
    return get_connection()


def _work_conn():
    conn = get_work_connection()
    attach_pipeline(conn)
    return conn


@router.post("/process-notes")
async def process_notes(body: NoteProcessRequest = None):
    """Process unprocessed notes with AI to extract insights."""
    def _query():
        p_conn = _pipeline_conn()
        w_conn = _work_conn()
        try:
            # Get unprocessed notes
            if body and body.note_ids:
                placeholders = ", ".join(["?"] * len(body.note_ids))
                notes = w_conn.execute(
                    f"SELECT * FROM manager_notes WHERE id IN ({placeholders})",
                    body.note_ids,
                ).fetchall()
            else:
                notes = w_conn.execute(
                    "SELECT * FROM manager_notes WHERE processed = 0 ORDER BY created_at"
                ).fetchall()

            results = []
            for note_row in notes:
                note = dict(note_row)

                # Get linked member profile if available
                member = None
                if note.get("linked_member_id"):
                    member = team_svc.get_member(p_conn, note["linked_member_id"])

                # Process with AI
                insights = ai_svc.process_note_insights(p_conn, note, member)

                # Update note record
                key_insight = insights.get("key_insight", "")
                w_conn.execute(
                    "UPDATE manager_notes SET processed = 1, ai_insights = ? WHERE id = ?",
                    (key_insight, note["id"]),
                )

                # Update member profile if insights suggest changes
                if member and not insights.get("error"):
                    profile_updates = {}
                    new_strengths = insights.get("new_strengths", [])
                    if new_strengths:
                        existing = member.get("strengths", [])
                        merged = list(set(existing + new_strengths))
                        profile_updates["strengths"] = json.dumps(merged)

                    new_growth = insights.get("new_growth_areas", [])
                    if new_growth:
                        existing = member.get("growth_areas", [])
                        merged = list(set(existing + new_growth))
                        profile_updates["growth_areas"] = json.dumps(merged)

                    if insights.get("working_style_signal"):
                        profile_updates["working_style"] = insights["working_style_signal"]

                    if insights.get("personal_context_update"):
                        existing = member.get("personal_context") or ""
                        if existing:
                            profile_updates["personal_context"] = f"{existing}\n{insights['personal_context_update']}"
                        else:
                            profile_updates["personal_context"] = insights["personal_context_update"]

                    if profile_updates:
                        set_clause = ", ".join(f"{k} = ?" for k in profile_updates)
                        vals = list(profile_updates.values()) + [member["id"]]
                        p_conn.execute(
                            f"UPDATE team_members SET {set_clause}, updated_at = datetime('now') WHERE id = ?",
                            vals,
                        )
                        p_conn.commit()

                w_conn.commit()
                results.append({
                    "note_id": note["id"],
                    "member_name": member["name"] if member else None,
                    "insights": insights,
                })

            return {"processed": len(results), "results": results}
        finally:
            p_conn.close()
            w_conn.close()

    return await run_db(_query)


@router.post("/recommend-delegation")
async def recommend_delegation(body: DelegationRecommendRequest):
    """Get AI delegation recommendations for a project."""
    def _query():
        p_conn = _pipeline_conn()
        w_conn = _work_conn()
        try:
            # Get project
            project = w_conn.execute(
                "SELECT * FROM projects WHERE id = ?", (body.project_id,)
            ).fetchone()
            if not project:
                return None

            # Get all active team members with profiles
            members = team_svc.list_members(p_conn, active_only=True)

            # Get workloads
            workloads = []
            for m in members:
                wl = team_svc.get_workload(p_conn, m["id"])
                workloads.append(wl or {"active_items": 0})

            result = ai_svc.recommend_delegation(p_conn, dict(project), members, workloads)
            return result
        finally:
            p_conn.close()
            w_conn.close()

    result = await run_db(_query)
    if result is None:
        raise HTTPException(404, "Project not found")
    return result


@router.post("/parse-email")
async def parse_email(body: EmailParseRequest):
    """Parse a forwarded status email into structured updates."""
    def _query():
        p_conn = _pipeline_conn()
        w_conn = _work_conn()
        try:
            members = team_svc.list_members(p_conn, active_only=True)
            projects = w_conn.execute(
                "SELECT id, title FROM projects WHERE status != 'completed'"
            ).fetchall()
            projects_list = [dict(p) for p in projects]

            result = ai_svc.parse_status_email(p_conn, body.email_text, members, projects_list)
            return result
        finally:
            p_conn.close()
            w_conn.close()

    return await run_db(_query)


@router.get("/usage", response_model=AIUsageResponse)
async def get_usage():
    """Get AI usage statistics."""
    def _query():
        conn = _pipeline_conn()
        try:
            return ai_svc.get_ai_usage(conn)
        finally:
            conn.close()
    return await run_db(_query)
