"""AI-Powered Comment Tiering Service (SQLite version).

Uses the Anthropic Claude API to intelligently classify comments into tiers
based on content analysis, not just heuristics. Also detects form letters,
assigns sentiment, and identifies the commenter type.
"""

import json
import logging
import hashlib
import sqlite3
from typing import Optional
from collections import defaultdict

import anthropic

from app.core.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Form letter detection (runs BEFORE AI -- cheap, fast)
# ---------------------------------------------------------------------------

def compute_text_fingerprint(text: str) -> str:
    """Normalize text and compute a hash for duplicate detection."""
    if not text:
        return ""
    normalized = " ".join(text.lower().split())
    normalized = normalized[:2000]
    return hashlib.md5(normalized.encode()).hexdigest()


def detect_form_letters(conn: sqlite3.Connection, docket_number: str) -> dict:
    """Detect form letters by text similarity.

    Groups comments with >80% text overlap. Marks them as form letters
    and assigns a group ID.

    Returns stats dict.
    """
    rows = conn.execute(
        "SELECT id, comment_text FROM comments WHERE docket_number = ? AND comment_text IS NOT NULL AND comment_text != ''",
        (docket_number,)
    ).fetchall()

    # Group by fingerprint
    fingerprint_groups = defaultdict(list)
    for row in rows:
        fp = compute_text_fingerprint(row["comment_text"])
        if fp:
            fingerprint_groups[fp].append(row["id"])

    form_letter_count = 0
    group_id = 1

    for fp, comment_ids in fingerprint_groups.items():
        if len(comment_ids) >= 3:  # 3+ identical comments = form letter campaign
            placeholders = ",".join("?" * len(comment_ids))
            conn.execute(
                f"UPDATE comments SET is_form_letter = 1, form_letter_group_id = ?, tier = 3 WHERE id IN ({placeholders})",
                [group_id] + comment_ids
            )
            form_letter_count += len(comment_ids)
            group_id += 1

    conn.commit()

    return {
        "form_letter_groups": group_id - 1,
        "form_letter_comments": form_letter_count,
        "unique_comments": len(rows) - form_letter_count,
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


def build_tiering_prompt(comment: dict) -> str:
    """Build the user prompt for tiering a single comment."""
    text = comment.get("comment_text") or ""

    # Truncate very long comments to fit context window
    if len(text) > 12000:
        text = text[:8000] + "\n\n[...MIDDLE TRUNCATED...]\n\n" + text[-2000:]

    return f"""Classify this CFTC public comment letter.

COMMENTER NAME: {comment.get('commenter_name') or 'Unknown'}
COMMENTER ORGANIZATION: {comment.get('commenter_organization') or 'Not specified'}
PAGE COUNT: {comment.get('page_count') or 'Unknown'}
SUBMISSION DATE: {comment.get('submission_date') or 'Unknown'}

COMMENT TEXT:
{text}"""


def ai_tier_single_comment(
    client: anthropic.Anthropic,
    comment: dict,
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

        text = response.content[0].text.strip()

        # Handle markdown code blocks
        if text.startswith("```"):
            text = text.split("\n", 1)[1]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()

        result = json.loads(text)
        return result

    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse AI response for {comment.get('document_id')}: {e}")
        return None
    except anthropic.APIError as e:
        logger.error(f"Anthropic API error for {comment.get('document_id')}: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error tiering {comment.get('document_id')}: {e}")
        return None


def apply_ai_tiering_result(
    conn: sqlite3.Connection,
    comment: dict,
    result: dict,
) -> None:
    """Apply AI tiering result to the comment record in the database."""
    tier = result.get("tier", comment.get("tier"))
    sentiment = None
    sentiment_map = {"SUPPORT", "OPPOSE", "MIXED", "NEUTRAL"}
    raw_sentiment = result.get("sentiment", "").upper()
    if raw_sentiment in sentiment_map:
        sentiment = raw_sentiment

    # Update tier and sentiment
    conn.execute(
        "UPDATE comments SET tier = ?, sentiment = ? WHERE id = ?",
        (tier, sentiment, comment["id"])
    )

    # Add topic tags
    for topic in result.get("key_topics", []):
        conn.execute(
            "INSERT INTO comment_tags (comment_id, tag_type, tag_value) VALUES (?, ?, ?)",
            (comment["id"], "TOPIC", topic[:500])
        )

    # Add legal citation tag if detected
    if result.get("has_legal_citations"):
        conn.execute(
            "INSERT INTO comment_tags (comment_id, tag_type, tag_value) VALUES (?, ?, ?)",
            (comment["id"], "THEME", "Contains Legal Citations")
        )

    # Add economic analysis tag if detected
    if result.get("has_economic_analysis"):
        conn.execute(
            "INSERT INTO comment_tags (comment_id, tag_type, tag_value) VALUES (?, ?, ?)",
            (comment["id"], "THEME", "Contains Economic Analysis")
        )

    # Store the full AI classification in the structured JSON field
    existing_structured = comment.get("ai_summary_structured")
    if isinstance(existing_structured, str):
        try:
            existing_structured = json.loads(existing_structured)
        except (json.JSONDecodeError, TypeError):
            existing_structured = {}
    if not isinstance(existing_structured, dict):
        existing_structured = {}

    existing_structured["classification"] = result
    conn.execute(
        "UPDATE comments SET ai_summary_structured = ? WHERE id = ?",
        (json.dumps(existing_structured), comment["id"])
    )


# ---------------------------------------------------------------------------
# Batch processing endpoint logic
# ---------------------------------------------------------------------------

def run_ai_tiering_batch(
    conn: sqlite3.Connection,
    docket_number: str,
    batch_size: int = 50,
    skip_form_letters: bool = True,
    force_retier: bool = False,
) -> dict:
    """Run AI tiering on a batch of comments.

    Args:
        conn: SQLite connection
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
    where_clauses = [
        "docket_number = ?",
        "comment_text IS NOT NULL",
        "comment_text != ''",
    ]
    params = [docket_number]

    if skip_form_letters:
        where_clauses.append("(is_form_letter = 0 OR is_form_letter IS NULL)")

    if not force_retier:
        where_clauses.append("sentiment IS NULL")

    where_sql = " AND ".join(where_clauses)

    rows = conn.execute(
        f"""SELECT * FROM comments
            WHERE {where_sql}
            ORDER BY
                CASE WHEN tier = 1 THEN 0 WHEN tier = 2 THEN 1 ELSE 2 END,
                LENGTH(comment_text) DESC
            LIMIT ?""",
        params + [batch_size]
    ).fetchall()
    comments = [dict(r) for r in rows]

    if not comments:
        return {
            "message": "No unprocessed comments found",
            "processed": 0,
            "remaining": 0,
        }

    # Count remaining
    remaining_where = [
        "docket_number = ?",
        "comment_text IS NOT NULL",
        "comment_text != ''",
        "sentiment IS NULL",
    ]
    remaining_params = [docket_number]
    if skip_form_letters:
        remaining_where.append("(is_form_letter = 0 OR is_form_letter IS NULL)")

    total_remaining = conn.execute(
        f"SELECT COUNT(*) as cnt FROM comments WHERE {' AND '.join(remaining_where)}",
        remaining_params
    ).fetchone()["cnt"]

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
        # Parse ai_summary_structured if it's a string
        if isinstance(comment.get("ai_summary_structured"), str):
            try:
                comment["ai_summary_structured"] = json.loads(comment["ai_summary_structured"])
            except (json.JSONDecodeError, TypeError):
                comment["ai_summary_structured"] = {}

        ai_result = ai_tier_single_comment(client, comment)

        if ai_result:
            apply_ai_tiering_result(conn, comment, ai_result)
            tier = ai_result.get("tier", 0)
            stats[f"tier_{tier}"] = stats.get(f"tier_{tier}", 0) + 1
            stats["processed"] += 1
            stats["results"].append({
                "document_id": comment["document_id"],
                "commenter": comment.get("commenter_name") or comment.get("commenter_organization") or "Unknown",
                "old_tier": comment.get("tier"),
                "new_tier": tier,
                "sentiment": ai_result.get("sentiment"),
                "commenter_type": ai_result.get("commenter_type"),
                "reasoning": ai_result.get("reasoning", ""),
            })
        else:
            stats["errors"] += 1
            stats["results"].append({
                "document_id": comment["document_id"],
                "error": "AI classification failed",
            })

    conn.commit()

    stats["remaining"] = total_remaining - stats["processed"]
    stats["form_letters_skipped"] = skip_form_letters

    return stats
