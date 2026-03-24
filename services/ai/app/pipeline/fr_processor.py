"""
Federal Register Processor — deterministic extraction from staged FR documents.

No LLM needed. Uses API metadata + regex to:
1. Match/create matters via tracker API
2. Create comment period records
3. Create publication status records
4. Extract numbered questions from full text
5. Stage questions into comment_topics for human clustering

Runs on fr_documents with processing_status = 'pending'.
"""
import re
import json
import logging
from datetime import datetime
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


# ── Question extraction ──────────────────────────────────────────────────────

# Pattern 1: "Question N:" or "Question N."  (NPRM style)
RE_QUESTION_LABEL = re.compile(
    r"^\s{0,8}(?:Question|Q\.?)\s*(\d+[a-z]?)\s*[:.]?\s*(.+)",
    re.IGNORECASE,
)

# Pattern 2: Numbered with optional sub-letter "    1. " or "    2a. " (ANPRM style)
# Only matches at start of paragraph (4+ spaces indent), followed by a question sentence
RE_NUMBERED = re.compile(
    r"^\s{4,}(\d+[a-z]?)\.\s+(.+)",
)

# Pattern 3: Sub-letter only "    a. " or "    b. " (ANPRM sub-questions)
RE_SUBLETTER = re.compile(
    r"^\s{4,}([a-h])\.\s+(.+)",
)

# FR page break / footnote markers to strip
RE_PAGE_BREAK = re.compile(r"\[\[Page \d+\]\]")
RE_FOOTNOTE_REF = re.compile(r"\\(\d+)\\")
RE_FOOTNOTE_BLOCK = re.compile(
    r"^-{10,}\n\n\s+\\\d+\\.*?(?=\n-{10,}|\n\n\s{4,}\d+\.|\n\n\s{4,}[a-h]\.|\n\nB\.|$)",
    re.MULTILINE | re.DOTALL,
)

# Section headings: "A. Core Principles", "B. DCO Core Principles", etc.
RE_SECTION_HEADING = re.compile(r"^([A-Z])\.\s+(.+?)$", re.MULTILINE)


def _strip_html(text: str) -> str:
    """Strip HTML tags from FR text. Handles <pre>-wrapped content."""
    if not text or "<" not in text:
        return text
    # Extract content from <pre> blocks (most common FR HTML format)
    pre_match = re.search(r"<pre[^>]*>(.*?)</pre>", text, re.DOTALL | re.IGNORECASE)
    if pre_match:
        text = pre_match.group(1)
    else:
        # Generic HTML tag stripping
        text = re.sub(r"<[^>]+>", "", text)
    # Decode common HTML entities
    text = text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    text = text.replace("&quot;", '"').replace("&#39;", "'").replace("&nbsp;", " ")
    return text


def _find_comment_section(text: str) -> str:
    """Extract the portion of FR text that contains comment questions.

    Strategy (priority order):
    1. Look for "Question N:" patterns — most reliable for NPRMs
    2. Look for explicit section headers ("Questions and Request for Comment")
    3. Look for "The Commission requests comment" near numbered paragraphs
    4. If none found, return empty (no questions in this document)

    For documents with questions scattered throughout, returns everything
    from slightly before the first question to the last question.
    """
    # Phase 1: Look for numbered question patterns first (most reliable)
    q_label_matches = list(re.finditer(
        r"\n\s{0,8}Question\s+(\d+[a-z]?)\s*:", text, re.IGNORECASE
    ))
    if q_label_matches:
        # Found "Question N:" patterns — return from first to last + buffer
        first = q_label_matches[0].start()
        last = q_label_matches[-1].start()
        # Back up 500 chars before first to capture any preamble
        start = max(0, first - 500)
        # Forward 3000 chars after last question start to capture full text
        end = min(len(text), last + 3000)
        # But try to find a real end marker
        tail = text[last:]
        for pat in [
            r"\nList\s+of\s+Subjects",
            r"\nRegulatory\s+Flexibility\s+Act",
            r"\nSection\s+15\(a\)",
            r"\nConsideration\s+of\s+the\s+Costs",
            r"\nCost.Benefit\s+Consideration",
            r"\nAppendix\s+[A-Z]",
            r"\nAuthority:",
            r"\nPART\s+\d+",
            r"\nIssued\s+in\s+Washington",
            r"\nDated:",
        ]:
            m = re.search(pat, tail[200:], re.IGNORECASE)
            if m:
                end = last + 200 + m.start()
                break
        return text[start:end]

    # Phase 2: Try explicit section headers (ANPRM style)
    header_patterns = [
        r"(?:II|III|IV|V|VI)\.\s*Questions?\s+(?:and\s+)?Request\s+for\s+Comment",
        r"Solicitation\s+of\s+Comments?",
        r"Questions?\s+for\s+(?:Public\s+)?Comment",
    ]

    best_start = -1
    for pat in header_patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            if best_start == -1 or m.start() < best_start:
                best_start = m.start()

    if best_start != -1:
        section_text = text[best_start:]
        for pat in [
            r"\nList\s+of\s+Subjects",
            r"\nRegulatory\s+Flexibility\s+Act",
            r"\nSection\s+15\(a\)",
            r"\nConsideration\s+of\s+the\s+Costs",
            r"\nCost.Benefit\s+Consideration",
            r"\nAppendix\s+[A-Z]",
            r"\nAuthority:",
            r"\nPART\s+\d+",
            r"\nIssued\s+in\s+Washington",
            r"\nDated:",
        ]:
            m = re.search(pat, section_text[500:], re.IGNORECASE)
            if m:
                section_text = section_text[:500 + m.start()]
                break
        return section_text

    # Phase 3: Look for numbered paragraph patterns near "Commission requests comment"
    m = re.search(
        r"The\s+Commission\s+(?:is\s+)?request(?:s|ing)\s+comment",
        text, re.IGNORECASE
    )
    if m:
        nearby = text[m.start():m.start() + 10000]
        if re.search(r"^\s{4,}\d+[a-z]?\.\s+\w", nearby, re.MULTILINE):
            start = m.start()
            section_text = text[start:]
            for pat in [
                r"\nList\s+of\s+Subjects",
                r"\nRegulatory\s+Flexibility",
                r"\nConsideration\s+of\s+the\s+Costs",
                r"\nAuthority:",
                r"\nIssued\s+in\s+Washington",
                r"\nDated:",
            ]:
                m2 = re.search(pat, section_text[500:], re.IGNORECASE)
                if m2:
                    section_text = section_text[:500 + m2.start()]
                    break
            return section_text

    return ""


def _clean_text(text: str) -> str:
    """Remove FR formatting artifacts from text."""
    text = _strip_html(text)
    text = RE_PAGE_BREAK.sub("", text)
    text = RE_FOOTNOTE_REF.sub("", text)
    # Remove footnote blocks (dashed lines + footnote text)
    text = RE_FOOTNOTE_BLOCK.sub("", text)
    # Collapse multiple newlines
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _join_continuation_lines(lines: list[str]) -> str:
    """Join wrapped continuation lines into a single paragraph."""
    # FR text wraps at ~72 chars with leading whitespace
    parts = []
    for line in lines:
        stripped = line.strip()
        if stripped:
            parts.append(stripped)
    return " ".join(parts)


def extract_questions(full_text: str, fr_type: str = "", action: str = "") -> list[dict]:
    """
    Extract numbered questions from FR document full text.

    Only extracts from documents that actively solicit comments (proposed rules,
    ANPRMs, concept releases). Final rules, corrections, and withdrawals are
    skipped even if they reference prior comment periods.

    Returns list of {question_number, question_text, section_heading, sort_order}.
    """
    if not full_text:
        return []

    # Skip document types that don't solicit new comments
    action_lower = (action or "").lower()
    fr_type_lower = (fr_type or "").lower()
    if fr_type_lower == "rule" and "request for comment" not in action_lower:
        # Final rules discussing prior comments — not a current solicitation
        return []
    if "withdrawal" in action_lower and "comment" not in action_lower:
        return []
    if "correction" in action_lower or "correcting" in action_lower:
        return []

    # Strip HTML first
    stripped = _strip_html(full_text)

    # Try to scope to comment/question sections only
    comment_section = _find_comment_section(stripped)
    if comment_section:
        cleaned = _clean_text(comment_section)
    else:
        # No comment section found
        return []
    lines = cleaned.split("\n")

    questions = []
    current_section = None
    current_q_num = None
    current_q_lines = []
    parent_num = None  # Track parent question number for sub-letters

    def flush_question():
        nonlocal current_q_num, current_q_lines
        if current_q_num and current_q_lines:
            text = _join_continuation_lines(current_q_lines)
            # Only keep if it looks like a question (contains ? or "comment on" or "consider")
            if "?" in text or "comment on" in text.lower() or "consider" in text.lower() or "request" in text.lower():
                questions.append({
                    "question_number": current_q_num,
                    "question_text": text,
                    "section_heading": current_section,
                    "sort_order": len(questions) + 1,
                })
        current_q_num = None
        current_q_lines = []

    for i, line in enumerate(lines):
        # Check for section headings
        m_section = RE_SECTION_HEADING.match(line)
        if m_section:
            flush_question()
            current_section = m_section.group(2).strip()
            continue

        # Check for "Question N:" pattern (NPRM style)
        m_label = RE_QUESTION_LABEL.match(line)
        if m_label:
            flush_question()
            current_q_num = m_label.group(1)
            current_q_lines = [m_label.group(2)]
            parent_num = current_q_num
            continue

        # Check for numbered pattern "    1. " (ANPRM style)
        m_num = RE_NUMBERED.match(line)
        if m_num:
            num_part = m_num.group(1)
            text_part = m_num.group(2)
            # Avoid matching section numbers that aren't questions
            # (e.g., "1. Background" in a non-question section)
            if True:  # Inside a scoped comment section, numbered paragraphs are questions
                flush_question()
                current_q_num = num_part
                current_q_lines = [text_part]
                parent_num = num_part.rstrip("abcdefgh")
                continue
            elif current_q_num:
                # Could be a numbered point within a question
                current_q_lines.append(line)
                continue

        # Check for sub-letter "    a. " (ANPRM sub-questions)
        m_sub = RE_SUBLETTER.match(line)
        if m_sub and parent_num:
            letter = m_sub.group(1)
            text_part = m_sub.group(2)
            flush_question()
            current_q_num = f"{parent_num}{letter}"
            current_q_lines = [text_part]
            continue

        # Continuation line — belongs to current question if indented
        if current_q_num and line.strip():
            current_q_lines.append(line)
        elif current_q_num and not line.strip():
            # Blank line — might be end of question or just a paragraph break
            # Look ahead: if next non-blank line is a new question, flush
            # Otherwise, treat as paragraph break within the question
            next_content = ""
            for j in range(i + 1, min(i + 5, len(lines))):
                if lines[j].strip():
                    next_content = lines[j]
                    break
            if next_content and (RE_QUESTION_LABEL.match(next_content) or
                                  RE_NUMBERED.match(next_content) or
                                  RE_SUBLETTER.match(next_content) or
                                  RE_SECTION_HEADING.match(next_content)):
                flush_question()
            elif next_content and next_content.strip().startswith("---"):
                # Footnote block — end of question
                flush_question()
            else:
                current_q_lines.append("")  # Preserve paragraph break

    flush_question()
    return questions


# ── Matter matching ──────────────────────────────────────────────────────────

async def find_matching_matter(tracker_client, doc: dict) -> Optional[dict]:
    """
    Try to match an FR document to an existing tracker matter.

    Match priority: RIN > docket_number > fr_doc_number > title substring.
    """
    rins = doc.get("regulation_id_numbers_json")
    if isinstance(rins, str):
        rins = json.loads(rins)
    dockets = doc.get("docket_ids_json")
    if isinstance(dockets, str):
        dockets = json.loads(dockets)

    # Try RIN match first
    if rins:
        for rin in rins:
            rin_str = rin.get("regulation_id_number", rin) if isinstance(rin, dict) else str(rin)
            matters = await tracker_client.search_matters(rin=rin_str)
            if matters:
                return matters[0]

    # Try docket match
    if dockets:
        for docket in dockets:
            matters = await tracker_client.search_matters(docket_number=str(docket))
            if matters:
                return matters[0]

    # Try FR doc number match
    doc_num = doc.get("document_number")
    if doc_num:
        matters = await tracker_client.search_matters(fr_doc_number=doc_num)
        if matters:
            return matters[0]

    return None


# ── Tracker client helper ────────────────────────────────────────────────────

class TrackerAPI:
    """Lightweight async client for the tracker API."""

    def __init__(self, base_url: str, auth: tuple):
        self.base_url = base_url.rstrip("/")
        self.auth = auth

    async def search_matters(self, rin=None, docket_number=None, fr_doc_number=None,
                             search=None) -> list:
        params = {}
        if search:
            params["search"] = search
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                f"{self.base_url}/tracker/matters",
                params=params,
                auth=self.auth,
            )
            resp.raise_for_status()
            data = resp.json()
            items = data.get("items", [])

        # Filter by specific field matches
        if rin:
            items = [m for m in items if m.get("rin") == rin]
        if docket_number:
            items = [m for m in items if m.get("docket_number") == docket_number]
        if fr_doc_number:
            items = [m for m in items if m.get("fr_doc_number") == fr_doc_number]
        return items

    async def create_matter(self, data: dict) -> dict:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{self.base_url}/tracker/matters",
                json=data,
                auth=self.auth,
            )
            resp.raise_for_status()
            return resp.json()

    async def create_comment_topic(self, matter_id: str, data: dict) -> dict:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{self.base_url}/tracker/matters/{matter_id}/comment-topics",
                json=data,
                auth=self.auth,
            )
            resp.raise_for_status()
            return resp.json()

    async def create_comment_question(self, topic_id: str, data: dict) -> dict:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{self.base_url}/tracker/comment-topics/{topic_id}/questions",
                json=data,
                auth=self.auth,
            )
            resp.raise_for_status()
            return resp.json()

    async def batch_write(self, operations: list) -> dict:
        """Execute batch operations via the tracker batch API."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{self.base_url}/tracker/batch",
                json={"operations": operations},
                auth=self.auth,
                headers={"X-Write-Source": "federal_register"},
            )
            resp.raise_for_status()
            return resp.json()


# ── Document type mapping ────────────────────────────────────────────────────

def _infer_matter_type(fr_type: str, action: str) -> str:
    return "rulemaking"


def _infer_regulatory_stage(fr_type: str, action: str) -> str:
    action_lower = (action or "").lower()
    if "advance notice" in action_lower or "concept release" in action_lower:
        return "concept"
    if "proposed" in action_lower or "notice of proposed" in action_lower:
        return "proposed"
    if "final rule" in action_lower:
        return "published"
    if "withdrawal" in action_lower:
        return "withdrawn"
    if "interpretation" in action_lower or "guidance" in action_lower:
        return "published"
    return "concept"


def _infer_source_document_type(fr_type: str, action: str) -> str:
    action_lower = (action or "").lower()
    if "advance notice" in action_lower:
        return "anprm"
    if "proposed" in action_lower:
        return "nprm"
    if "concept release" in action_lower:
        return "concept_release"
    if "interpretation" in action_lower or "guidance" in action_lower:
        return "interpretive_release"
    if "final rule" in action_lower:
        return "final_rule_with_comment"
    return "nprm"


def _infer_comment_period_type(fr_type: str, action: str) -> str:
    action_lower = (action or "").lower()
    if "advance notice" in action_lower:
        return "anprm"
    if "proposed" in action_lower:
        return "nprm"
    if "concept release" in action_lower:
        return "concept_release"
    return "original"



def _infer_topic_area(section_label: str) -> str:
    """Infer comment_topic_area enum value from section heading."""
    label_lower = section_label.lower()
    mapping = {
        "core principle": "core_principles",
        "public interest": "public_interest",
        "market structure": "market_structure",
        "disclosure": "disclosure",
        "registration": "registration",
        "clearing": "clearing",
        "margin": "margin",
        "reporting": "reporting",
        "surveillance": "surveillance",
        "position limit": "position_limits",
        "cost": "cost_benefit",
        "benefit": "cost_benefit",
        "definition": "definitional",
        "classification": "definitional",
        "jurisdiction": "jurisdictional",
        "technology": "technology",
        "blockchain": "technology",
        "consumer": "consumer_protection",
        "procedural": "procedural",
        "gaming": "public_interest",
        "terrorism": "public_interest",
        "manipulation": "surveillance",
        "inside information": "surveillance",
        "wash sale": "surveillance",
        "swap": "market_structure",
        "special entity": "special_entity",
    }
    for keyword, area in mapping.items():
        if keyword in label_lower:
            return area
    return "other"

# ── Main processor ───────────────────────────────────────────────────────────

async def process_fr_document(
    db,
    doc_row: dict,
    tracker_api: TrackerAPI,
) -> dict:
    """
    Process a single staged FR document deterministically.

    Args:
        db: ai.db connection
        doc_row: row from fr_documents table
        tracker_api: TrackerAPI client instance

    Returns dict with processing results.
    """
    doc_num = doc_row["document_number"]
    tier = doc_row["routing_tier"]
    fr_type = doc_row["fr_type"] or ""
    action = doc_row["action"] or ""
    full_text = doc_row["full_text"] or ""

    result = {
        "document_number": doc_num,
        "tier": tier,
        "matter_matched": False,
        "matter_created": False,
        "matter_id": None,
        "questions_extracted": 0,
        "topic_created": False,
        "topics_created": 0,
    }

    logger.info("Processing FR doc %s [Tier %d]: %s", doc_num, tier,
                doc_row["title"][:60])

    # 1. Match or create matter
    existing = await find_matching_matter(tracker_api, doc_row)
    if existing:
        result["matter_matched"] = True
        result["matter_id"] = existing["id"]
        logger.info("Matched to existing matter: %s", existing.get("title", "")[:40])
    elif tier == 1:
        # Create new matter from API metadata
        rins = json.loads(doc_row.get("regulation_id_numbers_json") or "[]")
        rin_str = None
        if rins:
            rin_str = rins[0].get("regulation_id_number", rins[0]) if isinstance(rins[0], dict) else str(rins[0])

        matter_data = {
            "title": doc_row["title"],
            "matter_type": _infer_matter_type(fr_type, action),
            "regulatory_stage": _infer_regulatory_stage(fr_type, action),
            "status": "awaiting comments" if doc_row.get("comments_close_on") else "new intake",
            "priority": "important this month",
            "sensitivity": "deliberative / predecisional",
            "boss_involvement_level": "keep boss informed",
            "next_step": f"Review FR publication {doc_num} and develop positions",
            "rin": rin_str,
            "fr_doc_number": doc_num,
            "federal_register_citation": doc_row.get("html_url"),
            "source": "federal_register",
            "external_deadline": doc_row.get("comments_close_on"),
        }
        try:
            new_matter = await tracker_api.create_matter(matter_data)
            result["matter_created"] = True
            result["matter_id"] = new_matter["id"]
            logger.info("Created new matter: %s", new_matter["id"][:8])
        except Exception as e:
            logger.error("Failed to create matter for %s: %s", doc_num, e)

    # 2. Create rulemaking metadata records if we have a matter
    if result["matter_id"]:
        matter_id = result["matter_id"]
        batch_ops = []

        # Comment period record (if document has comment deadline)
        if doc_row.get("comments_close_on"):
            batch_ops.append({
                "table": "rulemaking_comment_periods",
                "op": "insert",
                "data": {
                    "matter_id": matter_id,
                    "comment_period_type": _infer_comment_period_type(fr_type, action),
                    "opens_at": doc_row.get("publication_date"),
                    "closes_at": doc_row["comments_close_on"],
                    "fr_doc_number": doc_num,
                    "notes": f"Auto-created from FR doc {doc_num}",
                },
            })

        # Publication status record
        batch_ops.append({
            "table": "rulemaking_publication_status",
            "op": "insert",
            "data": {
                "matter_id": matter_id,
                "ofr_publication_date": doc_row.get("publication_date"),
                "ofr_doc_number": doc_num,
                "notes": f"Auto-created from FR doc {doc_num}",
            },
            "_meta": {"upsert_by": ["matter_id"]},
        })

        if batch_ops:
            try:
                await tracker_api.batch_write(batch_ops)
                logger.info("Created %d rulemaking records for matter %s",
                            len(batch_ops), matter_id[:8])
            except Exception as e:
                # Non-fatal — matter and questions are more important
                logger.warning("Failed to create rulemaking records for %s: %s",
                               doc_num, e)

    # 3. Extract questions if we have full text and a matter
    if full_text and result["matter_id"]:
        questions = extract_questions(full_text, fr_type=fr_type, action=action)
        result["questions_extracted"] = len(questions)

        if questions:
            # Group questions by section heading into topics
            section_groups = {}
            ungrouped = []
            for q in questions:
                section = q.get("section_heading") or ""
                if section:
                    section_groups.setdefault(section, []).append(q)
                else:
                    ungrouped.append(q)

            # If no sections found, use a single topic
            if not section_groups and ungrouped:
                section_groups["General Questions"] = ungrouped
                ungrouped = []

            # If there are ungrouped questions, add them to an "Other" group
            if ungrouped:
                section_groups["Other Questions"] = ungrouped

            source_doc_type = _infer_source_document_type(fr_type, action)
            topics_created = 0
            total_qs_created = 0

            for section_label, section_qs in section_groups.items():
                topic_data = {
                    "matter_id": result["matter_id"],
                    "topic_label": section_label,
                    "topic_area": _infer_topic_area(section_label),
                    "position_status": "open",
                    "source_fr_doc_number": doc_num,
                    "source_document_type": source_doc_type,
                    "source": "federal_register",
                    "sort_order": topics_created + 1,
                    "notes": f"Auto-extracted {len(section_qs)} questions from FR doc {doc_num}.",
                }
                try:
                    topic = await tracker_api.create_comment_topic(
                        result["matter_id"], topic_data
                    )
                    topic_id = topic["id"]
                    topics_created += 1

                    for q in section_qs:
                        try:
                            await tracker_api.create_comment_question(topic_id, {
                                "question_number": q["question_number"],
                                "question_text": q["question_text"],
                                "sort_order": q["sort_order"],
                                "source": "federal_register",
                            })
                            total_qs_created += 1
                        except Exception as e:
                            logger.warning("Failed to create question %s: %s",
                                           q["question_number"], e)
                except Exception as e:
                    logger.error("Failed to create topic '%s' for %s: %s",
                                 section_label, doc_num, e)

            result["topics_created"] = topics_created
            result["topic_created"] = topics_created > 0
            logger.info("Created %d topics with %d questions for matter %s",
                        topics_created, total_qs_created, result["matter_id"][:8])

    # 4. Update fr_documents status
    now = datetime.now().isoformat()
    new_status = "complete" if result["matter_id"] else "awaiting_review"
    db.execute(
        "UPDATE fr_documents SET processing_status = ?, matter_id = ?, updated_at = ? WHERE id = ?",
        (new_status, result["matter_id"], now, doc_row["id"]),
    )
    db.commit()

    return result


async def run_processor(db, tracker_api: TrackerAPI) -> list[dict]:
    """
    Process all pending FR documents.

    Returns list of per-document result dicts.
    """
    rows = db.execute("""
        SELECT * FROM fr_documents
        WHERE processing_status = 'pending' AND routing_tier <= 2
        ORDER BY publication_date ASC
    """).fetchall()

    if not rows:
        logger.info("No pending FR documents to process")
        return []

    logger.info("Processing %d pending FR documents", len(rows))
    results = []
    for row in rows:
        try:
            result = await process_fr_document(db, dict(row), tracker_api)
            results.append(result)
        except Exception as e:
            logger.error("Failed to process %s: %s", row["document_number"], e)
            results.append({
                "document_number": row["document_number"],
                "error": str(e),
            })

    logger.info("FR processor complete: %d documents processed", len(results))
    return results
