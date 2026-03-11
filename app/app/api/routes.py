"""API routes for proposed rules and comments."""

import logging
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, desc, asc, case
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.models.models import (
    ProposedRule, Comment, CommentTag, Tier1Organization,
    PriorityLevel, RuleStatus, Sentiment,
)
from app.schemas.schemas import (
    ProposedRuleResponse, ProposedRuleListResponse, ProposedRuleCreate,
    CommentResponse, CommentDetailResponse, CommentListResponse,
    Tier1OrgCreate, Tier1OrgResponse,
    FetchCommentsRequest, AddDocketRequest, DocketStatsResponse,
)
from app.services.ingestion import CommentIngestionPipeline

logger = logging.getLogger(__name__)

router = APIRouter()


# ===========================================================================
# Proposed Rules
# ===========================================================================

@router.get("/rules", response_model=ProposedRuleListResponse)
async def list_rules(
    status: Optional[RuleStatus] = None,
    priority: Optional[PriorityLevel] = None,
    db: AsyncSession = Depends(get_db),
):
    """List all tracked proposed rules.

    Sorted per spec: HIGH priority first, then by closest comment deadline,
    then newest first.
    """
    query = select(ProposedRule)

    if status:
        query = query.where(ProposedRule.status == status)
    if priority:
        query = query.where(ProposedRule.priority_level == priority)

    # Spec-defined sort order
    query = query.order_by(
        case(
            (ProposedRule.priority_level == PriorityLevel.HIGH, 0),
            else_=1,
        ),
        asc(ProposedRule.comment_period_end).nulls_last(),
        desc(ProposedRule.publication_date),
    )

    result = await db.execute(query)
    rules = result.scalars().all()

    count_result = await db.execute(
        select(func.count(ProposedRule.id))
        .where(True if not status else ProposedRule.status == status)
    )

    return ProposedRuleListResponse(
        rules=[ProposedRuleResponse.model_validate(r) for r in rules],
        total=len(rules),
    )


@router.get("/rules/{docket_number}", response_model=ProposedRuleResponse)
async def get_rule(docket_number: str, db: AsyncSession = Depends(get_db)):
    """Get details for a specific proposed rule."""
    result = await db.execute(
        select(ProposedRule).where(ProposedRule.docket_number == docket_number)
    )
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    return ProposedRuleResponse.model_validate(rule)


@router.post("/rules/detect-new")
async def detect_new_rules(db: AsyncSession = Depends(get_db)):
    """Manually trigger detection of new CFTC proposed rules from Federal Register."""
    pipeline = CommentIngestionPipeline(db)
    new_rules = await pipeline.detect_and_store_new_rules()
    return {
        "message": f"Detected {len(new_rules)} new rule(s)",
        "rules": [
            {"docket_number": r.docket_number, "title": r.title, "priority": r.priority_level.value}
            for r in new_rules
        ],
    }


@router.post("/rules/add-docket")
async def add_docket(request: AddDocketRequest, db: AsyncSession = Depends(get_db)):
    """Manually add a docket to track.

    Use the CFTC release ID (the number from the comments.cftc.gov URL).
    For example, the Event Contracts rule is release ID 7624:
    https://comments.cftc.gov/PublicComments/CommentList.aspx?id=7624

    Accepted formats:
    - "7624" (raw release ID)
    - "CFTC-RELEASE-7624" (our internal format)
    """
    pipeline = CommentIngestionPipeline(db)
    rule = await pipeline.add_docket_manually(request.docket_number)
    if not rule:
        raise HTTPException(status_code=400, detail="Failed to add docket")
    return {"message": f"Added docket {rule.docket_number}", "rule_id": rule.id}


@router.get("/cftc-releases")
async def browse_cftc_releases(year: int = 2024):
    """Browse available CFTC rulemakings from comments.cftc.gov for a given year.

    Use this to find the release ID you need for add-docket and fetch-comments.
    """
    from app.services.cftc_comments import cftc_comments_client
    try:
        releases = await cftc_comments_client.get_rulemakings_by_year(year)
        return {
            "year": year,
            "count": len(releases),
            "releases": [
                {
                    "release_id": r.release_id,
                    "title": r.title,
                    "fr_citation": r.fr_citation,
                    "closing_date": r.closing_date.isoformat() if r.closing_date else None,
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

@router.get("/comments", response_model=CommentListResponse)
async def list_comments(
    docket_number: Optional[str] = None,
    tier: Optional[int] = Query(None, ge=1, le=3),
    sentiment: Optional[Sentiment] = None,
    is_form_letter: Optional[bool] = None,
    organization: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    search: Optional[str] = None,
    sort_by: str = Query("submission_date", regex="^(submission_date|page_count|tier|commenter_organization)$"),
    sort_order: str = Query("desc", regex="^(asc|desc)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=250),
    db: AsyncSession = Depends(get_db),
):
    """Search and filter comments across all tracked dockets."""
    query = select(Comment)

    # Filters
    if docket_number:
        query = query.where(Comment.docket_number == docket_number)
    if tier:
        query = query.where(Comment.tier == tier)
    if sentiment:
        query = query.where(Comment.sentiment == sentiment)
    if is_form_letter is not None:
        query = query.where(Comment.is_form_letter == is_form_letter)
    if organization:
        query = query.where(Comment.commenter_organization.ilike(f"%{organization}%"))
    if date_from:
        query = query.where(Comment.submission_date >= date_from)
    if date_to:
        query = query.where(Comment.submission_date <= date_to)
    if search:
        query = query.where(
            Comment.comment_text.ilike(f"%{search}%")
            | Comment.commenter_name.ilike(f"%{search}%")
            | Comment.commenter_organization.ilike(f"%{search}%")
            | Comment.ai_summary.ilike(f"%{search}%")
        )

    # Count total before pagination
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    # Sort
    sort_col = getattr(Comment, sort_by)
    query = query.order_by(desc(sort_col) if sort_order == "desc" else asc(sort_col))

    # Paginate
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    comments = result.scalars().all()

    return CommentListResponse(
        comments=[CommentResponse.model_validate(c) for c in comments],
        total=total,
    )


@router.get("/comments/extraction-status")
async def extraction_status(
    docket_number: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """Check how many comments have/need text extraction."""
    query_base = select(Comment)
    if docket_number:
        query_base = query_base.where(Comment.docket_number == docket_number)

    total = (await db.execute(
        select(func.count()).select_from(query_base.subquery())
    )).scalar() or 0

    has_text = (await db.execute(
        select(func.count()).where(
            Comment.comment_text.isnot(None),
            Comment.comment_text != "",
            *([Comment.docket_number == docket_number] if docket_number else []),
        )
    )).scalar() or 0

    return {
        "docket_number": docket_number or "all",
        "total_comments": total,
        "with_text": has_text,
        "without_text": total - has_text,
        "percent_complete": round(has_text / total * 100, 1) if total > 0 else 0,
    }


@router.get("/comments/stats/{docket_number}", response_model=DocketStatsResponse)
async def get_docket_stats(docket_number: str, db: AsyncSession = Depends(get_db)):
    """Get comment statistics for a docket."""
    base = select(Comment).where(Comment.docket_number == docket_number)

    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar() or 0

    if total == 0:
        raise HTTPException(status_code=404, detail="No comments found for this docket")

    # Tier counts
    tier_counts = {}
    for t in [1, 2, 3]:
        q = select(func.count()).where(Comment.docket_number == docket_number, Comment.tier == t)
        tier_counts[t] = (await db.execute(q)).scalar() or 0

    # Sentiment counts
    sent_counts = {}
    for s in Sentiment:
        q = select(func.count()).where(Comment.docket_number == docket_number, Comment.sentiment == s)
        sent_counts[s.value] = (await db.execute(q)).scalar() or 0

    unclassified = total - sum(sent_counts.values())

    # Form letter count
    form_q = select(func.count()).where(
        Comment.docket_number == docket_number, Comment.is_form_letter == True  # noqa
    )
    form_count = (await db.execute(form_q)).scalar() or 0

    # Avg page count
    avg_q = select(func.avg(Comment.page_count)).where(
        Comment.docket_number == docket_number, Comment.page_count.isnot(None)
    )
    avg_pages = (await db.execute(avg_q)).scalar()

    return DocketStatsResponse(
        docket_number=docket_number,
        total_comments=total,
        tier_1_count=tier_counts.get(1, 0),
        tier_2_count=tier_counts.get(2, 0),
        tier_3_count=tier_counts.get(3, 0),
        support_count=sent_counts.get("SUPPORT", 0),
        oppose_count=sent_counts.get("OPPOSE", 0),
        mixed_count=sent_counts.get("MIXED", 0),
        neutral_count=sent_counts.get("NEUTRAL", 0),
        unclassified_count=unclassified,
        form_letter_count=form_count,
        avg_page_count=round(avg_pages, 1) if avg_pages else None,
    )


@router.post("/comments/fetch")
async def fetch_comments(request: FetchCommentsRequest, db: AsyncSession = Depends(get_db)):
    """Fetch comments from comments.cftc.gov for a specific release.

    Use the CFTC release ID (e.g., "7512" for Event Contracts).
    Find release IDs via GET /api/v1/cftc-releases?year=2024.
    """
    pipeline = CommentIngestionPipeline(db)
    count = await pipeline.fetch_and_store_comments(request.docket_number)
    return {"message": f"Fetched {count} new comments", "docket": request.docket_number}


@router.post("/comments/extract-text")
async def extract_text_from_comments(
    docket_number: Optional[str] = None,
    batch_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Download PDFs and extract text for comments that don't have text yet.

    Processes comments in batches. Call repeatedly until all are done.
    Pass docket_number to limit to a specific docket, or omit for all.

    Returns count of processed comments and how many remain.
    """
    pipeline = CommentIngestionPipeline(db)
    processed, remaining, errors = await pipeline.extract_text_batch(
        docket_number=docket_number,
        batch_size=batch_size,
    )
    return {
        "processed": processed,
        "remaining": remaining,
        "errors": errors,
        "message": (
            f"Extracted text from {processed} comments. "
            f"{remaining} remaining, {errors} errors."
        ),
    }


@router.get("/comments/{document_id}", response_model=CommentDetailResponse)
async def get_comment(document_id: str, db: AsyncSession = Depends(get_db)):
    """Get full details for a specific comment, including text and tags."""
    result = await db.execute(
        select(Comment)
        .where(Comment.document_id == document_id)
        .options(selectinload(Comment.tags))
    )
    comment = result.scalar_one_or_none()
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")
    return CommentDetailResponse.model_validate(comment)


# ===========================================================================
# Tier 1 Organizations
# ===========================================================================

@router.get("/tier1-orgs", response_model=list[Tier1OrgResponse])
async def list_tier1_orgs(db: AsyncSession = Depends(get_db)):
    """List all Tier 1 organizations."""
    result = await db.execute(
        select(Tier1Organization).order_by(Tier1Organization.category, Tier1Organization.name)
    )
    return [Tier1OrgResponse.model_validate(o) for o in result.scalars().all()]


@router.post("/tier1-orgs", response_model=Tier1OrgResponse)
async def add_tier1_org(org: Tier1OrgCreate, db: AsyncSession = Depends(get_db)):
    """Add a new Tier 1 organization."""
    new_org = Tier1Organization(
        name=org.name,
        category=org.category,
        name_variations=org.name_variations,
    )
    db.add(new_org)
    await db.flush()
    return Tier1OrgResponse.model_validate(new_org)


@router.delete("/tier1-orgs/{org_id}")
async def delete_tier1_org(org_id: int, db: AsyncSession = Depends(get_db)):
    """Remove a Tier 1 organization."""
    result = await db.execute(select(Tier1Organization).where(Tier1Organization.id == org_id))
    org = result.scalar_one_or_none()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    await db.delete(org)
    return {"message": f"Deleted {org.name}"}


# ===========================================================================
# AI Processing (Phase 2)
# ===========================================================================

@router.post("/comments/detect-form-letters")
async def detect_form_letters_endpoint(
    docket_number: str = Query(..., description="Docket number to process"),
    db: AsyncSession = Depends(get_db),
):
    """Detect and flag form letter campaigns using text fingerprinting.
    
    Run this BEFORE AI tiering to skip form letters (saves API costs).
    """
    from app.services.ai_tiering import detect_form_letters
    stats = await detect_form_letters(db, docket_number)
    await db.commit()
    return stats


@router.post("/comments/ai-tier")
async def ai_tier_comments(
    docket_number: str = Query(..., description="Docket number to process"),
    batch_size: int = Query(50, ge=1, le=200, description="Comments per batch"),
    skip_form_letters: bool = Query(True, description="Skip form letters"),
    force_retier: bool = Query(False, description="Re-tier already classified comments"),
    db: AsyncSession = Depends(get_db),
):
    """Run AI-powered tiering on a batch of comments using Claude API.
    
    Classifies comments into Tier 1/2/3, assigns sentiment, and extracts topics.
    Call repeatedly until 'remaining' is 0.
    """
    from app.services.ai_tiering import run_ai_tiering_batch
    stats = await run_ai_tiering_batch(
        db=db,
        docket_number=docket_number,
        batch_size=batch_size,
        skip_form_letters=skip_form_letters,
        force_retier=force_retier,
    )
    await db.commit()
    return stats


@router.post("/comments/ai-summarize")
async def ai_summarize_comments(
    docket_number: str = Query(..., description="Docket number to process"),
    tier: Optional[int] = Query(None, ge=1, le=3, description="Only summarize this tier"),
    batch_size: int = Query(10, ge=1, le=300, description="Comments per batch (max 300 for tier 3)"),
    force_resummarize: bool = Query(False, description="Re-summarize already summarized comments"),
    db: AsyncSession = Depends(get_db),
):
    """Run AI-powered summarization on comments.
    
    Uses Claude Opus for Tier 1 (deep structured summaries) and
    Claude Sonnet for Tier 2/3 (lighter summaries).
    
    Recommended: Start with tier=1 to get your briefing materials first.
    Call repeatedly until 'remaining' is 0.
    """
    from app.services.ai_summarization import run_summarization_batch
    stats = await run_summarization_batch(
        db=db,
        docket_number=docket_number,
        tier=tier,
        batch_size=batch_size,
        force_resummarize=force_resummarize,
    )
    await db.commit()
    return stats
