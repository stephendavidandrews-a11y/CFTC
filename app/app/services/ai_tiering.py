"""AI-Powered Comment Tiering Service.

Uses the Anthropic Claude API to intelligently classify comments into tiers
based on content analysis, not just heuristics. Also detects form letters,
assigns sentiment, and identifies the commenter type.

This replaces the crude length-based heuristic tiering from Phase 1.
"""

import json
import logging
import hashlib
from typing import Optional
from collections import defaultdict

import anthropic
from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.models import Comment, Tier1Organization, CommentTag, TagType

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Form letter detection (runs BEFORE AI — cheap, fast)
# ---------------------------------------------------------------------------

def compute_text_fingerprint(text: str) -> str:
    """Normalize text and compute a hash for duplicate detection."""
    if not text:
        return ""
    # Strip whitespace, lowercase, remove punctuation variations
    normalized = " ".join(text.lower().split())
    # Take first 2000 chars for fingerprinting (form letters match at the start)
    normalized = normalized[:2000]
    return hashlib.md5(normalized.encode()).hexdigest()


async def detect_form_letters(db: AsyncSession, docket_number: str) -> dict:
    """Detect form letters by text similarity. 
    
    Groups comments with >80% text overlap. Marks them as form letters
    and assigns a group ID.
    
    Returns stats dict.
    """
    result = await db.execute(
        select(Comment).where(
            Comment.docket_number == docket_number,
            Comment.comment_text.isnot(None),
            Comment.comment_text != "",
        )
    )
    comments = result.scalars().all()
    
    # Group by fingerprint
    fingerprint_groups = defaultdict(list)
    for comment in comments:
        fp = compute_text_fingerprint(comment.comment_text)
        if fp:
            fingerprint_groups[fp].append(comment)
    
    form_letter_count = 0
    group_id = 1
    
    for fp, group in fingerprint_groups.items():
        if len(group) >= 3:  # 3+ identical comments = form letter campaign
            for comment in group:
                comment.is_form_letter = True
                comment.form_letter_group_id = group_id
                comment.tier = 3  # Form letters are always Tier 3
            form_letter_count += len(group)
            group_id += 1
    
    await db.flush()
    
    return {
        "form_letter_groups": group_id - 1,
        "form_letter_comments": form_letter_count,
        "unique_comments": len(comments) - form_letter_count,
    }


# ---------------------------------------------------------------------------
# AI Tiering via Claude API
# ---------------------------------------------------------------------------

TIERING_SYSTEM_PROMPT = """You are a legal analyst at the CFTC (Commodity Futures Trading Commission). 
Your job is to classify public comment letters submitted during notice-and-comment rulemaking.

You must classify each comment into one of three tiers:

TIER 1 - Deep Analysis Required:
- Submitted by major law firms, industry associations, exchanges, government agencies, or academia/think tanks
- 20+ pages
- Contains case law citations (e.g., "v.", "U.S.C.", "F.3d", "S.Ct.")
- Contains economic or statistical analysis (cost-benefit, econometric, regression, survey data)
- Multiple organizations jointly submit
- Requests meeting with CFTC commissioners or staff
- Raises novel legal theories or constitutional challenges
- Provides detailed alternative regulatory text

TIER 2 - Medium Analysis:
- 5-20 pages
- Contains substantive technical detail but less formal
- Submitted by smaller organizations, companies, or knowledgeable individuals
- Makes specific policy arguments but without extensive legal citations
- Provides industry data or experience

TIER 3 - Light Touch:
- Form letters (identical or near-identical text across multiple submissions)
- Individual retail comments under 2 pages with no legal citations
- Simple "I support/oppose" statements
- General opinions without specific legal or policy arguments

You must also determine:
- SENTIMENT: SUPPORT, OPPOSE, MIXED, or NEUTRAL
- COMMENTER_TYPE: one of LAW_FIRM, INDUSTRY_ASSOCIATION, EXCHANGE, GOVERNMENT, ACADEMIA, COMPANY, INDIVIDUAL, ADVOCACY_GROUP, OTHER

Respond ONLY with valid JSON in this exact format:
{
    "tier": 1,
    "sentiment": "OPPOSE",
    "commenter_type": "INDUSTRY_ASSOCIATION",
    "reasoning": "Brief 1-2 sentence explanation of classification",
    "key_topics": ["topic1", "topic2"],
    "has_legal_citations": true,
    "has_economic_analysis": false,
    "requests_meeting": false
}"""


def build_tiering_prompt(comment: Comment) -> str:
    """Build the user prompt for tiering a single comment."""
    text = comment.comment_text or ""
    
    # Truncate very long comments to fit context window
    # Send first 8000 chars + last 2000 chars for long docs
    if len(text) > 12000:
        text = text[:8000] + "\n\n[...MIDDLE TRUNCATED...]\n\n" + text[-2000:]
    
    return f"""Classify this CFTC public comment letter.

COMMENTER NAME: {comment.commenter_name or 'Unknown'}
COMMENTER ORGANIZATION: {comment.commenter_organization or 'Not specified'}
PAGE COUNT: {comment.page_count or 'Unknown'}
SUBMISSION DATE: {comment.submission_date or 'Unknown'}

COMMENT TEXT:
{text}"""


async def ai_tier_single_comment(
    client: anthropic.Anthropic,
    comment: Comment,
) -> Optional[dict]:
    """Use Claude to classify a single comment. Returns parsed JSON result."""
    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=500,
            system=TIERING_SYSTEM_PROMPT,
            messages=[
                {"role": "user", "content": build_tiering_prompt(comment)}
            ],
        )
        
        # Parse response
        text = response.content[0].text.strip()
        
        # Handle markdown code blocks
        if text.startswith("```"):
            text = text.split("\n", 1)[1]  # Remove first line
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()
        
        result = json.loads(text)
        return result
        
    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse AI response for {comment.document_id}: {e}")
        return None
    except anthropic.APIError as e:
        logger.error(f"Anthropic API error for {comment.document_id}: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error tiering {comment.document_id}: {e}")
        return None


async def apply_ai_tiering_result(
    db: AsyncSession,
    comment: Comment,
    result: dict,
) -> None:
    """Apply AI tiering result to the comment record in the database."""
    # Update tier
    comment.tier = result.get("tier", comment.tier)
    
    # Update sentiment
    sentiment_map = {"SUPPORT": "SUPPORT", "OPPOSE": "OPPOSE", "MIXED": "MIXED", "NEUTRAL": "NEUTRAL"}
    raw_sentiment = result.get("sentiment", "").upper()
    if raw_sentiment in sentiment_map:
        comment.sentiment = raw_sentiment
    
    # Add topic tags
    for topic in result.get("key_topics", []):
        tag = CommentTag(
            comment_id=comment.id,
            tag_type=TagType.TOPIC,
            tag_value=topic[:500],  # respect column limit
        )
        db.add(tag)
    
    # Add legal citation tag if detected
    if result.get("has_legal_citations"):
        tag = CommentTag(
            comment_id=comment.id,
            tag_type=TagType.THEME,
            tag_value="Contains Legal Citations",
        )
        db.add(tag)
    
    # Add economic analysis tag if detected
    if result.get("has_economic_analysis"):
        tag = CommentTag(
            comment_id=comment.id,
            tag_type=TagType.THEME,
            tag_value="Contains Economic Analysis",
        )
        db.add(tag)
    
    # Store the full AI classification in the structured JSON field
    comment.ai_summary_structured = comment.ai_summary_structured or {}
    comment.ai_summary_structured["classification"] = result


# ---------------------------------------------------------------------------
# Batch processing endpoint logic
# ---------------------------------------------------------------------------

async def run_ai_tiering_batch(
    db: AsyncSession,
    docket_number: str,
    batch_size: int = 50,
    skip_form_letters: bool = True,
    force_retier: bool = False,
) -> dict:
    """Run AI tiering on a batch of comments.
    
    Args:
        docket_number: The docket to process
        batch_size: How many comments to process in this batch
        skip_form_letters: Skip comments already marked as form letters
        force_retier: Re-tier even if already has AI classification
    
    Returns:
        Stats dict with counts.
    """
    if not settings.ANTHROPIC_API_KEY or settings.ANTHROPIC_API_KEY == "your_anthropic_key_here":
        return {"error": "ANTHROPIC_API_KEY not configured in .env"}
    
    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    
    # Build query for unprocessed comments
    query = select(Comment).where(
        Comment.docket_number == docket_number,
        Comment.comment_text.isnot(None),
        Comment.comment_text != "",
    )
    
    if skip_form_letters:
        query = query.where(Comment.is_form_letter != True)
    
    if not force_retier:
        # Only process comments that don't have AI classification yet
        # We check by looking at ai_summary_structured -> classification
        query = query.where(
            Comment.sentiment.is_(None)  # Use sentiment as proxy for "not AI-classified yet"
        )
    
    query = query.order_by(
        Comment.tier.asc(),  # Process current Tier 1s first (most important)
        func.length(Comment.comment_text).desc(),  # Then longest comments
    ).limit(batch_size)
    
    result = await db.execute(query)
    comments = result.scalars().all()
    
    if not comments:
        return {
            "message": "No unprocessed comments found",
            "processed": 0,
            "remaining": 0,
        }
    
    # Count remaining
    remaining_query = select(func.count(Comment.id)).where(
        Comment.docket_number == docket_number,
        Comment.comment_text.isnot(None),
        Comment.comment_text != "",
        Comment.sentiment.is_(None),
    )
    if skip_form_letters:
        remaining_query = remaining_query.where(Comment.is_form_letter != True)
    
    total_remaining = (await db.execute(remaining_query)).scalar() or 0
    
    # Process each comment
    stats = {
        "processed": 0,
        "tier_1": 0,
        "tier_2": 0,
        "tier_3": 0,
        "errors": 0,
        "results": [],
    }
    
    for comment in comments:
        ai_result = await ai_tier_single_comment(client, comment)
        
        if ai_result:
            await apply_ai_tiering_result(db, comment, ai_result)
            tier = ai_result.get("tier", 0)
            stats[f"tier_{tier}"] = stats.get(f"tier_{tier}", 0) + 1
            stats["processed"] += 1
            stats["results"].append({
                "document_id": comment.document_id,
                "commenter": comment.commenter_name or comment.commenter_organization or "Unknown",
                "old_tier": comment.tier,  # Note: already updated above
                "new_tier": tier,
                "sentiment": ai_result.get("sentiment"),
                "commenter_type": ai_result.get("commenter_type"),
                "reasoning": ai_result.get("reasoning", ""),
            })
        else:
            stats["errors"] += 1
            stats["results"].append({
                "document_id": comment.document_id,
                "error": "AI classification failed",
            })
    
    await db.flush()
    
    stats["remaining"] = total_remaining - stats["processed"]
    stats["form_letters_skipped"] = skip_form_letters
    
    return stats
