"""API routes for proposed rules and comments (SQLite)."""

import json
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from app.core.database import get_connection, run_db
from fastapi import Depends
from app.core.config import settings
from app.core.auth import verify_comment_auth

logger = logging.getLogger(__name__)
router = APIRouter(dependencies=[Depends(verify_comment_auth)])


def _row_to_dict(row):
    """Convert sqlite3.Row to dict, parsing JSON fields."""
    if row is None:
        return None
    d = dict(row)
    # Parse JSON text fields
    for key in ("ai_summary_structured", "name_variations", "statutory_analysis", "narrative_summary"):
        if key in d and isinstance(d[key], str):
            try:
                d[key] = json.loads(d[key])
            except (json.JSONDecodeError, TypeError):
                pass
    # Convert integer booleans
    for key in ("has_attachments", "is_form_letter"):
        if key in d:
            d[key] = bool(d[key])
    return d


# ===========================================================================
# Proposed Rules
# ===========================================================================

@router.get("/rules")
async def list_rules(
    status: Optional[str] = None,
    priority: Optional[str] = None,
):
    def _query():
        conn = get_connection()
        try:
            sql = "SELECT * FROM proposed_rules WHERE deleted_at IS NULL"
            params = []
            if status:
                sql += " AND status = ?"
                params.append(status)
            if priority:
                sql += " AND priority_level = ?"
                params.append(priority)
            sql += """
                ORDER BY
                    CASE WHEN priority_level = 'HIGH' THEN 0 ELSE 1 END,
                    CASE WHEN comment_period_end IS NULL THEN 1 ELSE 0 END,
                    comment_period_end ASC,
                    publication_date DESC
            """
            rows = conn.execute(sql, params).fetchall()
            rules = [_row_to_dict(r) for r in rows]
            return {"rules": rules, "total": len(rules)}
        finally:
            conn.close()
    return await run_db(_query)


@router.get("/rules/{docket_number}")
async def get_rule(docket_number: str):
    def _query():
        conn = get_connection()
        try:
            row = conn.execute(
                "SELECT * FROM proposed_rules WHERE docket_number = ? AND deleted_at IS NULL",
                (docket_number,)
            ).fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Rule not found")
            return _row_to_dict(row)
        finally:
            conn.close()
    return await run_db(_query)


@router.delete("/rules/{docket_number}")
async def soft_delete_rule(docket_number: str):
    """Soft-delete a proposed rule (sets deleted_at timestamp)."""
    def _query():
        conn = get_connection()
        try:
            row = conn.execute(
                "SELECT id FROM proposed_rules WHERE docket_number = ? AND deleted_at IS NULL",
                (docket_number,)
            ).fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Rule not found")
            conn.execute(
                "UPDATE proposed_rules SET deleted_at = datetime('now') WHERE docket_number = ?",
                (docket_number,)
            )
            conn.commit()
            return {"message": f"Soft-deleted rule {docket_number}"}
        finally:
            conn.close()
    return await run_db(_query)


@router.post("/rules/detect-new")
async def detect_new_rules():
    from app.services.ingestion import CommentIngestionPipeline
    def _query():
        conn = get_connection()
        try:
            pipeline = CommentIngestionPipeline(conn)
            new_rules = pipeline.detect_and_store_new_rules()
            return {
                "message": f"Detected {len(new_rules)} new rule(s)",
                "rules": [
                    {"docket_number": r["docket_number"], "title": r["title"], "priority": r.get("priority_level", "STANDARD")}
                    for r in new_rules
                ],
            }
        finally:
            conn.close()
    return await run_db(_query)


@router.post("/rules/add-docket")
async def add_docket(request: dict):
    from app.services.ingestion import CommentIngestionPipeline
    docket_number = request.get("docket_number", "")
    def _query():
        conn = get_connection()
        try:
            pipeline = CommentIngestionPipeline(conn)
            rule = pipeline.add_docket_manually(docket_number)
            if not rule:
                raise HTTPException(status_code=400, detail="Failed to add docket")
            return {"message": f"Added docket {rule['docket_number']}", "rule_id": rule["id"]}
        finally:
            conn.close()
    return await run_db(_query)


@router.post("/rules/refresh-titles")
async def refresh_rule_titles():
    def _query():
        conn = get_connection()
        try:
            rows = conn.execute("SELECT * FROM proposed_rules").fetchall()
            return {"updated": 0, "details": [], "note": "Use detect-new to refresh"}
        finally:
            conn.close()
    return await run_db(_query)


@router.get("/cftc-releases")
async def browse_cftc_releases(year: Optional[int] = None):
    from app.services.cftc_comments import cftc_comments_client
    try:
        if year and year > 0:
            releases = await cftc_comments_client.get_rulemakings_by_year(year)
        else:
            releases = await cftc_comments_client.get_current_rulemakings()
        return {
            "year": year or "current",
            "count": len(releases),
            "releases": [
                {
                    "release_id": r.release_id,
                    "title": r.title,
                    "description": r.description,
                    "category": r.category,
                    "fr_citation": r.fr_citation,
                    "closing_date": r.closing_date.isoformat() if r.closing_date else None,
                    "open_date": r.open_date.isoformat() if r.open_date else None,
                    "comments_url": r.view_comments_url,
                }
                for r in releases
            ],
        }
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Error fetching from CFTC portal: {str(e)}")


# ===========================================================================
# Comments
# ===========================================================================

@router.get("/comments")
async def list_comments(
    docket_number: Optional[str] = None,
    tier: Optional[int] = Query(None, ge=1, le=3),
    sentiment: Optional[str] = None,
    is_form_letter: Optional[bool] = None,
    organization: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    search: Optional[str] = None,
    sort_by: str = Query("submission_date"),
    sort_order: str = Query("desc"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=250),
):
    def _query():
        conn = get_connection()
        try:
            where_clauses = ["deleted_at IS NULL"]
            params = []

            if docket_number:
                where_clauses.append("docket_number = ?")
                params.append(docket_number)
            if tier:
                where_clauses.append("tier = ?")
                params.append(tier)
            if sentiment:
                where_clauses.append("sentiment = ?")
                params.append(sentiment)
            if is_form_letter is not None:
                where_clauses.append("is_form_letter = ?")
                params.append(1 if is_form_letter else 0)
            if organization:
                where_clauses.append("commenter_organization LIKE ?")
                params.append(f"%{organization}%")
            if date_from:
                where_clauses.append("submission_date >= ?")
                params.append(date_from)
            if date_to:
                where_clauses.append("submission_date <= ?")
                params.append(date_to)
            if search:
                where_clauses.append(
                    "(comment_text LIKE ? OR commenter_name LIKE ? OR commenter_organization LIKE ? OR ai_summary LIKE ?)"
                )
                params.extend([f"%{search}%"] * 4)

            where_sql = " AND ".join(where_clauses)

            # Count
            count_sql = f"SELECT COUNT(*) as cnt FROM comments WHERE {where_sql}"
            total = conn.execute(count_sql, params).fetchone()["cnt"]

            # Validate sort column
            allowed_sort = {"submission_date", "page_count", "tier", "commenter_organization"}
            if sort_by not in allowed_sort:
                sort_by_safe = "submission_date"
            else:
                sort_by_safe = sort_by
            order = "DESC" if sort_order == "desc" else "ASC"

            offset = (page - 1) * page_size
            data_sql = f"""
                SELECT id, docket_number, document_id, commenter_name, commenter_organization,
                       submission_date, page_count, tier, sentiment, is_form_letter,
                       ai_summary, has_attachments, pdf_extraction_confidence, created_at
                FROM comments
                WHERE {where_sql}
                ORDER BY {sort_by_safe} {order}
                LIMIT ? OFFSET ?
            """
            rows = conn.execute(data_sql, params + [page_size, offset]).fetchall()
            comments = [_row_to_dict(r) for r in rows]
            return {"comments": comments, "total": total}
        finally:
            conn.close()
    return await run_db(_query)


@router.get("/comments/extraction-status")
async def extraction_status(docket_number: Optional[str] = None):
    def _query():
        conn = get_connection()
        try:
            where = "WHERE deleted_at IS NULL AND docket_number = ?" if docket_number else "WHERE deleted_at IS NULL"
            params = [docket_number] if docket_number else []

            total = conn.execute(
                f"SELECT COUNT(*) as cnt FROM comments {where}", params
            ).fetchone()["cnt"]

            has_text = conn.execute(
                f"SELECT COUNT(*) as cnt FROM comments {where} AND comment_text IS NOT NULL AND comment_text != ''",
                params
            ).fetchone()["cnt"]

            return {
                "docket_number": docket_number or "all",
                "total_comments": total,
                "with_text": has_text,
                "without_text": total - has_text,
                "percent_complete": round(has_text / total * 100, 1) if total > 0 else 0,
            }
        finally:
            conn.close()
    return await run_db(_query)


@router.get("/comments/stats/{docket_number}")
async def get_docket_stats(docket_number: str):
    def _query():
        conn = get_connection()
        try:
            total = conn.execute(
                "SELECT COUNT(*) as cnt FROM comments WHERE docket_number = ? AND deleted_at IS NULL",
                (docket_number,)
            ).fetchone()["cnt"]

            if total == 0:
                return {
                    "docket_number": docket_number, "total_comments": 0,
                    "tier_1_count": 0, "tier_2_count": 0, "tier_3_count": 0,
                    "support_count": 0, "oppose_count": 0, "mixed_count": 0,
                    "neutral_count": 0, "unclassified_count": 0,
                    "form_letter_count": 0, "avg_page_count": None,
                    "tier1_summarized": False,
                }

            tier_counts = {}
            for t in [1, 2, 3]:
                tier_counts[t] = conn.execute(
                    "SELECT COUNT(*) as cnt FROM comments WHERE docket_number = ? AND tier = ? AND deleted_at IS NULL",
                    (docket_number, t)
                ).fetchone()["cnt"]

            sent_counts = {}
            for s in ["SUPPORT", "OPPOSE", "MIXED", "NEUTRAL"]:
                sent_counts[s] = conn.execute(
                    "SELECT COUNT(*) as cnt FROM comments WHERE docket_number = ? AND sentiment = ? AND deleted_at IS NULL",
                    (docket_number, s)
                ).fetchone()["cnt"]

            form_count = conn.execute(
                "SELECT COUNT(*) as cnt FROM comments WHERE docket_number = ? AND is_form_letter = 1 AND deleted_at IS NULL",
                (docket_number,)
            ).fetchone()["cnt"]

            avg_row = conn.execute(
                "SELECT AVG(page_count) as avg_pc FROM comments WHERE docket_number = ? AND page_count IS NOT NULL AND deleted_at IS NULL",
                (docket_number,)
            ).fetchone()
            avg_pages = avg_row["avg_pc"]

            t1_summarized = conn.execute(
                "SELECT COUNT(*) as cnt FROM comments WHERE docket_number = ? AND tier = 1 AND ai_summary IS NOT NULL AND deleted_at IS NULL",
                (docket_number,)
            ).fetchone()["cnt"]

            return {
                "docket_number": docket_number,
                "total_comments": total,
                "tier_1_count": tier_counts.get(1, 0),
                "tier_2_count": tier_counts.get(2, 0),
                "tier_3_count": tier_counts.get(3, 0),
                "support_count": sent_counts.get("SUPPORT", 0),
                "oppose_count": sent_counts.get("OPPOSE", 0),
                "mixed_count": sent_counts.get("MIXED", 0),
                "neutral_count": sent_counts.get("NEUTRAL", 0),
                "unclassified_count": total - sum(sent_counts.values()),
                "form_letter_count": form_count,
                "avg_page_count": round(avg_pages, 1) if avg_pages else None,
                "tier1_summarized": t1_summarized > 0,
            }
        finally:
            conn.close()
    return await run_db(_query)


@router.get("/comments/tier-breakdown/{docket_number}")
async def get_tier_breakdown(docket_number: str):
    def _query():
        conn = get_connection()
        try:
            result = {}
            for tier in [1, 2, 3]:
                sent_counts = {}
                for s in ["SUPPORT", "OPPOSE", "MIXED", "NEUTRAL"]:
                    sent_counts[s.lower()] = conn.execute(
                        "SELECT COUNT(*) as cnt FROM comments WHERE docket_number = ? AND tier = ? AND sentiment = ? AND deleted_at IS NULL",
                        (docket_number, tier, s)
                    ).fetchone()["cnt"]

                total = conn.execute(
                    "SELECT COUNT(*) as cnt FROM comments WHERE docket_number = ? AND tier = ? AND deleted_at IS NULL",
                    (docket_number, tier)
                ).fetchone()["cnt"]

                top_rows = conn.execute(
                    """SELECT COALESCE(commenter_name, commenter_organization, 'Anonymous') as name,
                              sentiment, document_id
                       FROM comments
                       WHERE docket_number = ? AND tier = ? AND deleted_at IS NULL
                       ORDER BY page_count DESC
                       LIMIT 10""",
                    (docket_number, tier)
                ).fetchall()
                top_commenters = [dict(r) for r in top_rows]

                result[f"tier_{tier}"] = {"total": total, **sent_counts, "top_commenters": top_commenters}
            return result
        finally:
            conn.close()
    return await run_db(_query)


@router.get("/comments/statutory-analysis/{docket_number}")
async def get_statutory_analysis(docket_number: str):
    from app.services.export_briefing import _generate_statutory_analysis

    def _get_data():
        conn = get_connection()
        try:
            rule = conn.execute(
                "SELECT * FROM proposed_rules WHERE docket_number = ? AND deleted_at IS NULL", (docket_number,)
            ).fetchone()

            # Check new dedicated column first, then fall back to legacy summary field
            if rule and rule["statutory_analysis"]:
                try:
                    cached = json.loads(rule["statutory_analysis"])
                    if 'disputes' in cached:
                        return {"cached": cached}
                except json.JSONDecodeError:
                    pass
            # Legacy fallback: check summary field
            if rule and rule["summary"] and rule["summary"].startswith('{'):
                try:
                    cached = json.loads(rule["summary"])
                    if 'disputes' in cached:
                        return {"cached": cached, "migrate": True}
                except json.JSONDecodeError:
                    pass

            t1_rows = conn.execute(
                "SELECT * FROM comments WHERE docket_number = ? AND tier = 1 AND deleted_at IS NULL",
                (docket_number,)
            ).fetchall()
            return {"rule": dict(rule) if rule else None, "tier1_comments": [_row_to_dict(r) for r in t1_rows]}
        finally:
            conn.close()

    data = await run_db(_get_data)

    if "cached" in data:
        # Migrate legacy data to new column if needed
        if data.get("migrate"):
            cached_data = data["cached"]
            def _migrate():
                conn = get_connection()
                try:
                    conn.execute(
                        "UPDATE proposed_rules SET statutory_analysis = ? WHERE docket_number = ?",
                        (json.dumps(cached_data), docket_number)
                    )
                    conn.commit()
                finally:
                    conn.close()
            await run_db(_migrate)
        return data["cached"]

    if not data["tier1_comments"]:
        return {"overview": "No Tier 1 comments available for analysis.", "disputes": []}

    # Check cost caps before calling AI
    from app.core.cost_tracking import check_daily_cap, check_docket_cap
    daily_ok, daily_spent, daily_cap = check_daily_cap()
    if not daily_ok:
        raise HTTPException(status_code=429, detail=f"Daily AI spending cap reached (${daily_spent:.2f}/${daily_cap:.2f})")
    docket_ok, docket_spent, docket_cap = check_docket_cap(docket_number)
    if not docket_ok:
        raise HTTPException(status_code=429, detail=f"Per-docket AI spending cap reached for {docket_number} (${docket_spent:.2f}/${docket_cap:.2f})")

    analysis = await _generate_statutory_analysis(data["tier1_comments"])

    if analysis and data["rule"]:
        analysis_json = json.dumps(analysis)
        def _cache():
            conn = get_connection()
            try:
                conn.execute(
                    "UPDATE proposed_rules SET statutory_analysis = ? WHERE docket_number = ?",
                    (analysis_json, docket_number)
                )
                conn.commit()
            finally:
                conn.close()
        await run_db(_cache)

    return analysis or {"overview": "Analysis could not be generated.", "disputes": []}


@router.get("/comments/narrative/{docket_number}")
async def get_comment_narrative(docket_number: str):
    def _get_data():
        conn = get_connection()
        try:
            rule = conn.execute(
                "SELECT * FROM proposed_rules WHERE docket_number = ? AND deleted_at IS NULL", (docket_number,)
            ).fetchone()

            # Check new dedicated column first
            if rule and rule["narrative_summary"]:
                try:
                    cached = json.loads(rule["narrative_summary"])
                    if cached.get('narrative'):
                        return {"cached": {"narrative": cached['narrative'], "saved_at": cached.get('narrative_saved_at')}}
                except json.JSONDecodeError:
                    pass
            # Legacy fallback: check summary field
            if rule and rule["summary"] and rule["summary"].startswith('{'):
                try:
                    cached = json.loads(rule["summary"])
                    if cached.get('narrative'):
                        return {"cached": {"narrative": cached['narrative'], "saved_at": cached.get('narrative_saved_at')}, "migrate": True}
                except json.JSONDecodeError:
                    pass

            rows = conn.execute(
                """SELECT * FROM comments
                   WHERE docket_number = ? AND tier IN (1, 2) AND ai_summary IS NOT NULL AND deleted_at IS NULL
                   ORDER BY tier ASC, page_count DESC""",
                (docket_number,)
            ).fetchall()

            total = conn.execute(
                "SELECT COUNT(*) as cnt FROM comments WHERE docket_number = ? AND deleted_at IS NULL",
                (docket_number,)
            ).fetchone()["cnt"]

            return {
                "comments": [_row_to_dict(r) for r in rows],
                "total": total,
                "rule_summary": rule["summary"] if rule else None,
            }
        finally:
            conn.close()

    data = await run_db(_get_data)

    if "cached" in data:
        # Migrate legacy data to new column if needed
        if data.get("migrate"):
            cached_data = data["cached"]
            def _migrate():
                conn = get_connection()
                try:
                    conn.execute(
                        "UPDATE proposed_rules SET narrative_summary = ? WHERE docket_number = ?",
                        (json.dumps(cached_data), docket_number)
                    )
                    conn.commit()
                finally:
                    conn.close()
            await run_db(_migrate)
        return data["cached"]

    comments = data["comments"]
    if not comments:
        return {"narrative": None, "saved_at": None}

    # Check cost caps before calling AI
    from app.core.cost_tracking import check_daily_cap, check_docket_cap
    daily_ok, daily_spent, daily_cap = check_daily_cap()
    if not daily_ok:
        raise HTTPException(status_code=429, detail=f"Daily AI spending cap reached (${daily_spent:.2f}/${daily_cap:.2f})")
    docket_ok, docket_spent, docket_cap = check_docket_cap(docket_number)
    if not docket_ok:
        raise HTTPException(status_code=429, detail=f"Per-docket AI spending cap reached for {docket_number} (${docket_spent:.2f}/${docket_cap:.2f})")

    # Build context
    context_parts = []
    for c in comments[:60]:
        name = c.get("commenter_name") or c.get("commenter_organization") or 'Anonymous'
        sentiment = c.get("sentiment") or 'Unknown'
        summary = c.get("ai_summary") or ''
        if len(summary) > 500:
            summary = summary[:500] + '...'
        context_parts.append(f"[Tier {c.get('tier')}] {name} ({sentiment}): {summary}")

    combined = "\n\n".join(context_parts)
    if len(combined) > 40000:
        combined = combined[:40000] + "\n...[truncated]"

    if not settings.ANTHROPIC_API_KEY or settings.ANTHROPIC_API_KEY == "your_anthropic_key_here":
        return {"narrative": None, "saved_at": None}

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=3000,
            system=(
                "You are a senior policy analyst at the CFTC writing an internal briefing "
                "narrative about the public comments received on a proposed rule. "
                "Write a flowing 4-6 paragraph narrative that synthesizes the major themes, "
                "key commenters' positions, areas of consensus, and areas of dispute. "
                "Be specific about commenter names, their arguments, and the overall balance "
                "of support vs opposition. Write in the style of an executive summary for "
                "the General Counsel's office."
            ),
            messages=[{
                "role": "user",
                "content": f"Docket: {docket_number}\nTotal comments: {data['total']}\n\nSummarize these major comments into a cohesive narrative:\n\n{combined}",
            }],
        )
        narrative_text = response.content[0].text.strip()

        # Log cost
        from app.core.cost_tracking import log_api_call
        log_api_call(
            model="claude-sonnet-4-20250514",
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            operation="narrative_generation",
            docket_number=docket_number,
        )
    except Exception as e:
        logger.error(f"Error generating narrative: {e}")
        return {"narrative": None, "saved_at": None}

    # Cache in dedicated column
    now = datetime.utcnow().isoformat()
    narrative_data = json.dumps({"narrative": narrative_text, "narrative_saved_at": now})
    def _cache():
        conn = get_connection()
        try:
            conn.execute(
                "UPDATE proposed_rules SET narrative_summary = ? WHERE docket_number = ?",
                (narrative_data, docket_number)
            )
            conn.commit()
        finally:
            conn.close()
    await run_db(_cache)

    return {"narrative": narrative_text, "saved_at": now}


@router.post("/comments/fetch")
async def fetch_comments(request: dict):
    from app.services.ingestion import CommentIngestionPipeline
    docket_number = request.get("docket_number", "")

    def _query():
        conn = get_connection()
        try:
            pipeline = CommentIngestionPipeline(conn)
            count = pipeline.fetch_and_store_comments(docket_number)
            return {"message": f"Fetched {count} new comments", "docket": docket_number}
        finally:
            conn.close()
    return await run_db(_query)


@router.post("/comments/extract-text")
async def extract_text_from_comments(
    docket_number: Optional[str] = None,
    batch_size: int = Query(20, ge=1, le=100),
):
    from app.services.ingestion import CommentIngestionPipeline
    def _query():
        conn = get_connection()
        try:
            pipeline = CommentIngestionPipeline(conn)
            processed, remaining, errors = pipeline.extract_text_batch(
                docket_number=docket_number, batch_size=batch_size,
            )
            return {
                "processed": processed, "remaining": remaining, "errors": errors,
                "message": f"Extracted text from {processed} comments. {remaining} remaining, {errors} errors.",
            }
        finally:
            conn.close()
    return await run_db(_query)


@router.get("/comments/{document_id}")
async def get_comment(document_id: str):
    def _query():
        conn = get_connection()
        try:
            row = conn.execute(
                "SELECT * FROM comments WHERE document_id = ? AND deleted_at IS NULL", (document_id,)
            ).fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Comment not found")
            comment = _row_to_dict(row)

            tags = conn.execute(
                "SELECT tag_type, tag_value FROM comment_tags WHERE comment_id = ?",
                (comment["id"],)
            ).fetchall()
            comment["tags"] = [dict(t) for t in tags]
            return comment
        finally:
            conn.close()
    return await run_db(_query)


@router.delete("/comments/{document_id}")
async def soft_delete_comment(document_id: str):
    """Soft-delete a comment (sets deleted_at timestamp)."""
    def _query():
        conn = get_connection()
        try:
            row = conn.execute(
                "SELECT id FROM comments WHERE document_id = ? AND deleted_at IS NULL",
                (document_id,)
            ).fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Comment not found")
            conn.execute(
                "UPDATE comments SET deleted_at = datetime('now') WHERE document_id = ?",
                (document_id,)
            )
            conn.commit()
            return {"message": f"Soft-deleted comment {document_id}"}
        finally:
            conn.close()
    return await run_db(_query)


# ===========================================================================
# Tier 1 Organizations
# ===========================================================================

@router.get("/tier1-orgs")
async def list_tier1_orgs():
    def _query():
        conn = get_connection()
        try:
            rows = conn.execute(
                "SELECT * FROM tier1_organizations ORDER BY category, name"
            ).fetchall()
            return [_row_to_dict(r) for r in rows]
        finally:
            conn.close()
    return await run_db(_query)


@router.post("/tier1-orgs")
async def add_tier1_org(org: dict):
    def _query():
        conn = get_connection()
        try:
            conn.execute(
                "INSERT INTO tier1_organizations (name, category, name_variations) VALUES (?, ?, ?)",
                (org["name"], org["category"], json.dumps(org.get("name_variations", [])))
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM tier1_organizations WHERE name = ?", (org["name"],)
            ).fetchone()
            return _row_to_dict(row)
        finally:
            conn.close()
    return await run_db(_query)


@router.delete("/tier1-orgs/{org_id}")
async def delete_tier1_org(org_id: int):
    def _query():
        conn = get_connection()
        try:
            row = conn.execute(
                "SELECT name FROM tier1_organizations WHERE id = ?", (org_id,)
            ).fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Organization not found")
            conn.execute("DELETE FROM tier1_organizations WHERE id = ?", (org_id,))
            conn.commit()
            return {"message": f"Deleted {row['name']}"}
        finally:
            conn.close()
    return await run_db(_query)


# ===========================================================================
# AI Processing
# ===========================================================================

@router.post("/comments/detect-form-letters")
async def detect_form_letters_endpoint(
    docket_number: str = Query(..., description="Docket number to process"),
):
    from app.services.ai_tiering import detect_form_letters
    def _query():
        conn = get_connection()
        try:
            stats = detect_form_letters(conn, docket_number)
            conn.commit()
            return stats
        finally:
            conn.close()
    return await run_db(_query)


@router.post("/comments/ai-tier")
async def ai_tier_comments(
    docket_number: str = Query(..., description="Docket number to process"),
    batch_size: int = Query(50, ge=1, le=200),
    skip_form_letters: bool = Query(True),
    force_retier: bool = Query(False),
):
    # Check cost caps before AI processing
    from app.core.cost_tracking import check_daily_cap, check_docket_cap
    daily_ok, daily_spent, daily_cap = check_daily_cap()
    if not daily_ok:
        raise HTTPException(status_code=429, detail=f"Daily AI spending cap reached (${daily_spent:.2f}/${daily_cap:.2f})")
    docket_ok, docket_spent, docket_cap = check_docket_cap(docket_number)
    if not docket_ok:
        raise HTTPException(status_code=429, detail=f"Per-docket AI spending cap reached for {docket_number} (${docket_spent:.2f}/${docket_cap:.2f})")

    from app.services.ai_tiering import run_ai_tiering_batch
    def _query():
        conn = get_connection()
        try:
            stats = run_ai_tiering_batch(
                conn=conn, docket_number=docket_number,
                batch_size=batch_size, skip_form_letters=skip_form_letters,
                force_retier=force_retier,
            )
            conn.commit()
            return stats
        finally:
            conn.close()
    return await run_db(_query)


@router.post("/comments/ai-summarize")
async def ai_summarize_comments(
    docket_number: str = Query(..., description="Docket number to process"),
    tier: Optional[int] = Query(None, ge=1, le=3),
    batch_size: int = Query(10, ge=1, le=300),
    force_resummarize: bool = Query(False),
):
    # Check cost caps before AI processing
    from app.core.cost_tracking import check_daily_cap, check_docket_cap
    daily_ok, daily_spent, daily_cap = check_daily_cap()
    if not daily_ok:
        raise HTTPException(status_code=429, detail=f"Daily AI spending cap reached (${daily_spent:.2f}/${daily_cap:.2f})")
    docket_ok, docket_spent, docket_cap = check_docket_cap(docket_number)
    if not docket_ok:
        raise HTTPException(status_code=429, detail=f"Per-docket AI spending cap reached for {docket_number} (${docket_spent:.2f}/${docket_cap:.2f})")

    from app.services.ai_summarization import run_summarization_batch
    def _query():
        conn = get_connection()
        try:
            stats = run_summarization_batch(
                conn=conn, docket_number=docket_number,
                tier=tier, batch_size=batch_size,
                force_resummarize=force_resummarize,
            )
            conn.commit()
            return stats
        finally:
            conn.close()
    return await run_db(_query)


# ===========================================================================
# Cost Tracking
# ===========================================================================

@router.get("/ai-costs")
async def get_ai_costs():
    """Get AI cost tracking statistics."""
    from app.core.cost_tracking import get_usage_stats
    return await run_db(get_usage_stats)


# ===========================================================================
# Export
# ===========================================================================

@router.get("/export/briefing/{docket_number}")
async def export_briefing_doc(docket_number: str):
    import os
    import tempfile
    from app.services.export_briefing import generate_briefing_doc

    def _query():
        conn = get_connection()
        try:
            output_dir = os.path.join(tempfile.gettempdir(), "cftc_exports")
            os.makedirs(output_dir, exist_ok=True)
            filename = f"briefing_{docket_number.replace('-', '_')}.docx"
            output_path = os.path.join(output_dir, filename)
            generate_briefing_doc(conn, docket_number, output_path)
            return output_path, filename
        finally:
            conn.close()

    output_path, filename = await run_db(_query)
    return FileResponse(
        path=output_path, filename=filename,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )


@router.get("/export/pdfs/{docket_number}")
async def export_all_pdfs(
    docket_number: str,
    tier: Optional[int] = None,
):
    import os
    import zipfile
    import tempfile
    from app.services.storage import storage_service

    def _query():
        conn = get_connection()
        try:
            sql = "SELECT * FROM comments WHERE docket_number = ? AND deleted_at IS NULL"
            params = [docket_number]
            if tier:
                sql += " AND tier = ?"
                params.append(tier)
            rows = conn.execute(sql, params).fetchall()
            return [_row_to_dict(r) for r in rows]
        finally:
            conn.close()

    comments = await run_db(_query)

    if not comments:
        raise HTTPException(status_code=404, detail="No comments found")

    output_dir = os.path.join(tempfile.gettempdir(), "cftc_exports")
    os.makedirs(output_dir, exist_ok=True)
    tier_label = f"_tier{tier}" if tier else ""
    zip_filename = f"pdfs_{docket_number.replace('-', '_')}{tier_label}.zip"
    zip_path = os.path.join(output_dir, zip_filename)

    added = 0
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for comment in comments:
            if not comment.get("original_pdf_url"):
                continue
            pdf_bytes = storage_service.download_pdf(comment["original_pdf_url"])
            if not pdf_bytes:
                continue
            name = (comment.get("commenter_name") or comment.get("commenter_organization") or 'Anonymous').replace('/', '-').replace('\\', '-')
            sentiment = (comment.get("sentiment") or 'unknown').lower()
            tier_num = comment.get("tier") or 0
            archive_name = f"Tier_{tier_num}/{sentiment}/{name}_{comment['document_id']}.pdf"
            zf.writestr(archive_name, pdf_bytes)
            added += 1

    if added == 0:
        raise HTTPException(status_code=404, detail="No PDFs found on disk for this docket")

    return FileResponse(path=zip_path, filename=zip_filename, media_type="application/zip")
