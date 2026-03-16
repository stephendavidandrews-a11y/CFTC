"""AI-Powered Comment Summarization Service (SQLite version).

Uses Claude Opus for Tier 1 deep structured summaries and
Claude Sonnet for Tier 2/3 lighter summaries.
"""

import json
import logging
import sqlite3
from typing import Optional

import anthropic

from app.core.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Model selection
# ---------------------------------------------------------------------------

MODEL_TIER_1 = "claude-opus-4-20250514"       # Deep analysis for important comments
MODEL_TIER_2 = "claude-sonnet-4-20250514"     # Medium analysis
MODEL_TIER_3 = "claude-sonnet-4-20250514"     # Light touch

# ---------------------------------------------------------------------------
# Tier 1: Structured Deep Summary (Opus)
# ---------------------------------------------------------------------------

TIER1_SYSTEM_PROMPT = """You are a senior legal analyst at the CFTC (Commodity Futures Trading Commission).
You are preparing briefing materials for the Deputy General Counsel for Regulation.

Your task is to produce a detailed, structured summary of a public comment letter submitted during
notice-and-comment rulemaking. This summary will be used by attorneys reviewing the comment record
to prepare the final rule preamble.

You must produce a JSON object with the following structure:

{
    "commenter": "Organization or individual name",
    "main_position": "SUPPORT" | "OPPOSE" | "MIXED" | "NEUTRAL",
    "executive_summary": "2-3 sentence high-level summary of the comment's core position and significance",
    "key_arguments": [
        {
            "topic": "Topic or theme name",
            "sub_points": ["Sub-point 1", "Sub-point 2"],
            "requested_action": "What change or action the commenter requests"
        }
    ],
    "legal_challenges": [
        {
            "citation": "Case name or statute (e.g., Loper Bright v. Raimondo, 7 U.S.C. § 7a-2)",
            "theory": "Brief description of the legal argument"
        }
    ],
    "data_evidence": [
        "Description of economic analysis, survey, or statistical evidence provided"
    ],
    "requested_changes": [
        "Specific regulatory text change, exemption, or timeline modification requested"
    ],
    "key_quotes": [
        "1-2 representative direct quotes from the comment, max 2 sentences each"
    ],
    "commenter_type": "LAW_FIRM" | "INDUSTRY_ASSOCIATION" | "EXCHANGE" | "GOVERNMENT" | "ACADEMIA" | "COMPANY" | "INDIVIDUAL" | "ADVOCACY_GROUP" | "OTHER",
    "topics_tags": ["tag1", "tag2", "tag3"]
}

Be thorough but concise. Focus on arguments that the Commission must address in the final rule preamble.
Extract actual case citations and statutory references precisely.
Identify specific requested changes to regulatory text.
Respond ONLY with valid JSON -- no markdown, no explanation."""


TIER1_USER_TEMPLATE = """Produce a detailed structured summary of this Tier 1 CFTC comment letter.

COMMENTER NAME: {commenter_name}
COMMENTER ORGANIZATION: {commenter_org}
PAGE COUNT: {page_count}
SUBMISSION DATE: {submission_date}

FULL COMMENT TEXT:
{text}"""


# ---------------------------------------------------------------------------
# Tier 2: Executive Summary (Sonnet)
# ---------------------------------------------------------------------------

TIER2_SYSTEM_PROMPT = """You are a legal analyst at the CFTC. Produce a concise executive summary
of this public comment letter in exactly this JSON format:

{
    "summary": "One paragraph, 4-6 sentences covering: main position, 2-3 key arguments, any requested changes.",
    "main_position": "SUPPORT" | "OPPOSE" | "MIXED" | "NEUTRAL",
    "key_topics": ["topic1", "topic2"],
    "commenter_type": "LAW_FIRM" | "INDUSTRY_ASSOCIATION" | "EXCHANGE" | "GOVERNMENT" | "ACADEMIA" | "COMPANY" | "INDIVIDUAL" | "ADVOCACY_GROUP" | "OTHER"
}

Respond ONLY with valid JSON."""


TIER2_USER_TEMPLATE = """Summarize this Tier 2 CFTC comment letter.

COMMENTER: {commenter_name} ({commenter_org})
PAGE COUNT: {page_count}

COMMENT TEXT:
{text}"""


# ---------------------------------------------------------------------------
# Tier 3: Basic Summary (Sonnet)
# ---------------------------------------------------------------------------

TIER3_SYSTEM_PROMPT = """You are a legal analyst at the CFTC. Produce a brief summary
of this public comment in exactly this JSON format:

{
    "summary": "2-3 sentences: position (support/oppose) and primary reason stated.",
    "main_position": "SUPPORT" | "OPPOSE" | "MIXED" | "NEUTRAL"
}

Respond ONLY with valid JSON."""


TIER3_USER_TEMPLATE = """Briefly summarize this Tier 3 CFTC comment.

COMMENTER: {commenter_name}

COMMENT TEXT:
{text}"""


# ---------------------------------------------------------------------------
# Core summarization logic
# ---------------------------------------------------------------------------

def truncate_text(text: str, tier: int) -> str:
    """Truncate text based on tier -- Tier 1 gets more context."""
    if not text:
        return ""
    if tier == 1:
        if len(text) > 80000:
            return text[:60000] + "\n\n[...MIDDLE TRUNCATED...]\n\n" + text[-15000:]
        return text
    elif tier == 2:
        if len(text) > 15000:
            return text[:12000] + "\n\n[...TRUNCATED...]\n\n" + text[-3000:]
        return text
    else:
        return text[:3000]


def parse_ai_response(text: str) -> Optional[dict]:
    """Parse JSON from AI response, handling markdown code blocks."""
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def summarize_single_comment(
    client: anthropic.Anthropic,
    comment: dict,
) -> Optional[dict]:
    """Generate AI summary for a single comment based on its tier."""
    tier = comment.get("tier") or 3
    text = truncate_text(comment.get("comment_text") or "", tier)

    if not text:
        return None

    if tier == 1:
        model = MODEL_TIER_1
        system = TIER1_SYSTEM_PROMPT
        user_msg = TIER1_USER_TEMPLATE.format(
            commenter_name=comment.get("commenter_name") or "Unknown",
            commenter_org=comment.get("commenter_organization") or "Not specified",
            page_count=comment.get("page_count") or "Unknown",
            submission_date=comment.get("submission_date") or "Unknown",
            text=text,
        )
        max_tokens = 4000
    elif tier == 2:
        model = MODEL_TIER_2
        system = TIER2_SYSTEM_PROMPT
        user_msg = TIER2_USER_TEMPLATE.format(
            commenter_name=comment.get("commenter_name") or "Unknown",
            commenter_org=comment.get("commenter_organization") or "Not specified",
            page_count=comment.get("page_count") or "Unknown",
            text=text,
        )
        max_tokens = 1000
    else:
        model = MODEL_TIER_3
        system = TIER3_SYSTEM_PROMPT
        user_msg = TIER3_USER_TEMPLATE.format(
            commenter_name=comment.get("commenter_name") or "Unknown",
            text=text,
        )
        max_tokens = 300

    try:
        response = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user_msg}],
        )

        result = parse_ai_response(response.content[0].text)
        if result:
            result["_tier"] = tier
            result["_model"] = model
        return result

    except anthropic.APIError as e:
        logger.error(f"Anthropic API error for {comment.get('document_id')}: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error summarizing {comment.get('document_id')}: {e}")
        return None


def apply_summary_result(
    conn: sqlite3.Connection,
    comment: dict,
    result: dict,
) -> None:
    """Apply AI summary result to the comment record."""
    tier = result.get("_tier", 3)

    if tier == 1:
        # Store the full structured summary
        ai_summary = result.get("executive_summary", "")
        ai_summary_structured = json.dumps(result)

        conn.execute(
            "UPDATE comments SET ai_summary = ?, ai_summary_structured = ? WHERE id = ?",
            (ai_summary, ai_summary_structured, comment["id"])
        )

        # Extract legal citations as tags
        for citation in result.get("legal_challenges", []):
            cite_text = citation.get("citation", "")
            if cite_text:
                conn.execute(
                    "INSERT INTO comment_tags (comment_id, tag_type, tag_value) VALUES (?, ?, ?)",
                    (comment["id"], "LEGAL_CITATION", cite_text[:500])
                )

        # Add topic tags
        for topic in result.get("topics_tags", []):
            conn.execute(
                "INSERT INTO comment_tags (comment_id, tag_type, tag_value) VALUES (?, ?, ?)",
                (comment["id"], "TOPIC", topic[:500])
            )

    elif tier == 2:
        ai_summary = result.get("summary", "")
        ai_summary_structured = json.dumps(result)

        conn.execute(
            "UPDATE comments SET ai_summary = ?, ai_summary_structured = ? WHERE id = ?",
            (ai_summary, ai_summary_structured, comment["id"])
        )

        for topic in result.get("key_topics", []):
            conn.execute(
                "INSERT INTO comment_tags (comment_id, tag_type, tag_value) VALUES (?, ?, ?)",
                (comment["id"], "TOPIC", topic[:500])
            )

    else:
        ai_summary = result.get("summary", "")
        ai_summary_structured = json.dumps(result)

        conn.execute(
            "UPDATE comments SET ai_summary = ?, ai_summary_structured = ? WHERE id = ?",
            (ai_summary, ai_summary_structured, comment["id"])
        )


# ---------------------------------------------------------------------------
# Batch processing
# ---------------------------------------------------------------------------

def run_summarization_batch(
    conn: sqlite3.Connection,
    docket_number: str,
    tier: Optional[int] = None,
    batch_size: int = 10,
    force_resummarize: bool = False,
) -> dict:
    """Run AI summarization on a batch of comments.

    Args:
        conn: SQLite connection
        docket_number: The docket to process
        tier: If specified, only summarize this tier (1, 2, or 3)
        batch_size: How many comments to process in this batch
        force_resummarize: Re-summarize even if already has summary

    Returns:
        Stats dict.
    """
    if not settings.ANTHROPIC_API_KEY or settings.ANTHROPIC_API_KEY == "your_anthropic_key_here":
        return {"error": "ANTHROPIC_API_KEY not configured in .env"}

    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

    # Build query
    where_clauses = [
        "docket_number = ?",
        "comment_text IS NOT NULL",
        "comment_text != ''",
        "(is_form_letter = 0 OR is_form_letter IS NULL)",
    ]
    params = [docket_number]

    if tier:
        where_clauses.append("tier = ?")
        params.append(tier)

    if not force_resummarize:
        where_clauses.append("(ai_summary IS NULL OR ai_summary = '')")

    where_sql = " AND ".join(where_clauses)

    # Process Tier 1 first, then 2, then 3
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
            "message": "No unsummarized comments found",
            "processed": 0,
            "remaining": 0,
        }

    # Count remaining
    remaining_where = [
        "docket_number = ?",
        "comment_text IS NOT NULL",
        "comment_text != ''",
        "(is_form_letter = 0 OR is_form_letter IS NULL)",
        "(ai_summary IS NULL OR ai_summary = '')",
    ]
    remaining_params = [docket_number]
    if tier:
        remaining_where.append("tier = ?")
        remaining_params.append(tier)

    total_remaining = conn.execute(
        f"SELECT COUNT(*) as cnt FROM comments WHERE {' AND '.join(remaining_where)}",
        remaining_params
    ).fetchone()["cnt"]

    # Process
    stats = {
        "processed": 0,
        "tier_1_summarized": 0,
        "tier_2_summarized": 0,
        "tier_3_summarized": 0,
        "errors": 0,
        "results": [],
    }

    for comment in comments:
        # Parse ai_summary_structured if string
        if isinstance(comment.get("ai_summary_structured"), str):
            try:
                comment["ai_summary_structured"] = json.loads(comment["ai_summary_structured"])
            except (json.JSONDecodeError, TypeError):
                comment["ai_summary_structured"] = {}

        ai_result = summarize_single_comment(client, comment)

        if ai_result:
            apply_summary_result(conn, comment, ai_result)
            t = comment.get("tier") or 3
            stats[f"tier_{t}_summarized"] += 1
            stats["processed"] += 1

            result_entry = {
                "document_id": comment["document_id"],
                "commenter": comment.get("commenter_name") or comment.get("commenter_organization") or "Unknown",
                "tier": t,
                "model": ai_result.get("_model", "unknown"),
            }
            if t == 1:
                result_entry["position"] = ai_result.get("main_position")
                result_entry["num_arguments"] = len(ai_result.get("key_arguments", []))
                result_entry["num_legal_citations"] = len(ai_result.get("legal_challenges", []))
            else:
                result_entry["summary_preview"] = (ai_result.get("summary", ""))[:150] + "..."

            stats["results"].append(result_entry)
        else:
            stats["errors"] += 1
            stats["results"].append({
                "document_id": comment["document_id"],
                "error": "Summarization failed",
            })

    conn.commit()

    stats["remaining"] = total_remaining - stats["processed"]

    return stats
