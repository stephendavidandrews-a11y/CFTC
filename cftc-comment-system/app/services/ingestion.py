"""Comment Ingestion Pipeline.

Orchestrates the full flow of:
1. Fetching comments from the CFTC Public Comments portal (comments.cftc.gov)
2. Downloading comment PDFs
3. Extracting text from PDFs
4. Storing everything in DB + S3
5. Running initial classification (Tier 1 org matching)

NOTE: The CFTC does NOT use Regulations.gov for public comments.
All comments are hosted at comments.cftc.gov.
"""

import re
import logging
from datetime import date, datetime
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.models.models import (
    ProposedRule, Comment, Tier1Organization, RuleStatus, PriorityLevel,
)
from app.services.cftc_comments import cftc_comments_client, CftcComment
from app.services.federal_register import federal_register_client
from app.services.pdf_extraction import extract_text_from_pdf
from app.services.storage import storage_service

logger = logging.getLogger(__name__)


class CommentIngestionPipeline:
    """Orchestrates fetching, processing, and storing comments."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # -------------------------------------------------------------------
    # Rule Detection & Storage
    # -------------------------------------------------------------------

    async def detect_and_store_new_rules(self) -> list[ProposedRule]:
        """Check Federal Register for new CFTC proposed rules and store them."""
        new_rules_data = await federal_register_client.check_new_rules_today()
        stored_rules = []

        for rule_data in new_rules_data:
            rule = await self._upsert_rule(rule_data)
            if rule:
                stored_rules.append(rule)
                logger.info(f"Stored new rule: {rule.docket_number} - {rule.title}")

        return stored_rules

    async def add_docket_manually(self, docket_number: str) -> Optional[ProposedRule]:
        """Manually add a docket/release by number.

        Accepts either:
        - A CFTC release ID (numeric, e.g., "7624")
        - Our internal format (e.g., "CFTC-RELEASE-7624")
        - A traditional docket number (e.g., "CFTC-2024-0007")
        """
        # Normalize: if raw numeric, convert to our format
        release_id = self._extract_release_id(docket_number)
        if release_id:
            docket_number = f"CFTC-RELEASE-{release_id}"

        # Check if already exists
        result = await self.db.execute(
            select(ProposedRule).where(ProposedRule.docket_number == docket_number)
        )
        existing = result.scalar_one_or_none()
        if existing:
            logger.info(f"Docket {docket_number} already exists")
            return existing

        # Try to fetch the actual title from CFTC site
        title = f"CFTC Release #{release_id}" if release_id else f"Docket {docket_number}"
        summary = ""
        fr_citation = ""
        try:
            if release_id:
                from app.services.cftc_comments import cftc_comments_client
                # Check current/upcoming first, then recent years
                for year_or_current in [None, 2026, 2025, 2024, 2023]:
                    try:
                        if year_or_current is None:
                            releases = await cftc_comments_client.get_current_rulemakings()
                        else:
                            releases = await cftc_comments_client.get_rulemakings_by_year(year_or_current)
                        match = next((r for r in releases if r.release_id == release_id), None)
                        if match:
                            title = match.title
                            summary = match.description or ""
                            fr_citation = match.fr_citation or ""
                            logger.info(f"Found title for release {release_id}: {title}")
                            break
                    except Exception:
                        continue
        except Exception as e:
            logger.warning(f"Could not fetch title for {docket_number}: {e}")

        rule = ProposedRule(
            docket_number=docket_number,
            title=title,
            summary=summary,
            federal_register_citation=fr_citation,
            status=RuleStatus.CLOSED,
            priority_level=PriorityLevel.STANDARD,
            regulations_gov_url=(
                f"https://comments.cftc.gov/PublicComments/CommentList.aspx?id={release_id}"
                if release_id else None
            ),
        )
        self.db.add(rule)
        await self.db.flush()
        logger.info(f"Added docket {docket_number} — {title}")
        return rule

    async def _upsert_rule(self, rule_data: dict) -> Optional[ProposedRule]:
        """Insert or update a proposed rule."""
        try:
            stmt = pg_insert(ProposedRule).values(
                docket_number=rule_data["docket_number"],
                rin=rule_data.get("rin"),
                title=rule_data["title"],
                publication_date=rule_data.get("publication_date"),
                comment_period_start=rule_data.get("comment_period_start"),
                comment_period_end=rule_data.get("comment_period_end"),
                federal_register_citation=rule_data.get("federal_register_citation"),
                federal_register_doc_number=rule_data.get("federal_register_doc_number"),
                priority_level=rule_data.get("priority_level", PriorityLevel.STANDARD),
                status=rule_data.get("status", RuleStatus.OPEN),
                full_text_url=rule_data.get("full_text_url"),
                summary=rule_data.get("summary"),
                regulations_gov_url=rule_data.get("regulations_gov_url"),
                page_count=rule_data.get("page_count"),
            ).on_conflict_do_update(
                index_elements=["docket_number"],
                set_={
                    "title": rule_data["title"],
                    "comment_period_end": rule_data.get("comment_period_end"),
                    "status": rule_data.get("status", RuleStatus.OPEN),
                    "updated_at": datetime.utcnow(),
                },
            ).returning(ProposedRule)

            result = await self.db.execute(stmt)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error upserting rule: {e}", exc_info=True)
            return None

    # -------------------------------------------------------------------
    # Comment Fetching from CFTC Portal
    # -------------------------------------------------------------------

    async def fetch_and_store_comments(
        self,
        docket_number: str,
        incremental: bool = True,
    ) -> int:
        """Fetch comments for a docket from comments.cftc.gov.

        This is the main entry point called by API routes.
        Accepts docket numbers in multiple formats:
        - "CFTC-RELEASE-7624" (our internal format)
        - "7624" (raw release ID)
        """
        release_id = self._extract_release_id(docket_number)

        if not release_id:
            # Check if stored rule has a URL we can parse
            result = await self.db.execute(
                select(ProposedRule).where(ProposedRule.docket_number == docket_number)
            )
            rule = result.scalar_one_or_none()
            if rule and rule.regulations_gov_url:
                match = re.search(r'id=(\d+)', rule.regulations_gov_url)
                if match:
                    release_id = int(match.group(1))

        if not release_id:
            logger.error(
                f"Cannot fetch comments for '{docket_number}'. "
                f"Use a CFTC release ID (e.g., '7624' or 'CFTC-RELEASE-7624'). "
                f"Find IDs at https://comments.cftc.gov"
            )
            return 0

        normalized_docket = f"CFTC-RELEASE-{release_id}"

        # Ensure the rule record exists
        result = await self.db.execute(
            select(ProposedRule).where(ProposedRule.docket_number == normalized_docket)
        )
        rule = result.scalar_one_or_none()
        if not rule:
            rule = await self.add_docket_manually(str(release_id))

        # Scrape comment list from CFTC portal
        cftc_comments = await cftc_comments_client.fetch_comments_for_release(release_id)

        new_count = 0
        for cftc_comment in cftc_comments:
            stored = await self._process_cftc_comment(
                cftc_comment, normalized_docket,
                fr_citation=rule.federal_register_citation or "",
            )
            if stored:
                new_count += 1

        # Update rule metadata
        rule.last_comment_pull = datetime.utcnow()
        rule.total_comments = await self._count_comments(normalized_docket)
        await self.db.flush()

        logger.info(f"Stored {new_count} new comments for release {release_id}")
        return new_count

    async def _process_cftc_comment(
        self,
        cftc_comment: CftcComment,
        docket_number: str,
        fr_citation: str = "",
    ) -> Optional[Comment]:
        """Process a single CFTC comment: download PDF, extract text, store."""
        document_id = f"CFTC-COMMENT-{cftc_comment.comment_id}"

        # Check if already exists
        result = await self.db.execute(
            select(Comment).where(Comment.document_id == document_id)
        )
        if result.scalar_one_or_none():
            return None  # skip duplicates

        # Download and process PDF
        pdf_text = ""
        pdf_confidence = None
        pdf_method = None
        s3_key = None
        page_count = None

        try:
            pdf_bytes = await cftc_comments_client.download_comment_pdf(
                cftc_comment.comment_id
            )
            if pdf_bytes and len(pdf_bytes) > 100:
                # Store in S3
                s3_key = storage_service.build_comment_pdf_key(
                    docket_number, document_id,
                    commenter_name=cftc_comment.commenter_name or cftc_comment.organization or "",
                    fr_citation=fr_citation,
                    comment_id=cftc_comment.comment_id,
                )
                storage_service.upload_pdf(s3_key, pdf_bytes)

                # Extract text
                extraction = extract_text_from_pdf(pdf_bytes)
                pdf_text = extraction.text
                pdf_confidence = extraction.confidence
                pdf_method = extraction.method
                page_count = extraction.page_count

                logger.debug(
                    f"Extracted {len(pdf_text)} chars from comment "
                    f"{cftc_comment.comment_id} ({pdf_method}, "
                    f"confidence={pdf_confidence:.2f})"
                )
        except Exception as e:
            logger.warning(
                f"Error processing comment {cftc_comment.comment_id}: {e}"
            )

        # Initial tier classification
        tier = await self._classify_tier_initial(
            cftc_comment.organization or "",
            cftc_comment.commenter_name or "",
            page_count or 0,
            pdf_text,
        )

        comment = Comment(
            docket_number=docket_number,
            document_id=document_id,
            commenter_name=cftc_comment.commenter_name,
            commenter_organization=cftc_comment.organization,
            submission_date=cftc_comment.submission_date,
            comment_text=pdf_text,
            original_pdf_url=s3_key,
            page_count=page_count,
            has_attachments=True,
            attachment_count=1,
            tier=tier,
            pdf_extraction_confidence=pdf_confidence,
            pdf_extraction_method=pdf_method,
            regulations_gov_url=cftc_comment.pdf_url,
        )

        self.db.add(comment)
        await self.db.flush()
        return comment

    # -------------------------------------------------------------------
    # PDF Text Extraction (batch processing for existing comments)
    # -------------------------------------------------------------------

    async def extract_text_batch(
        self,
        docket_number: Optional[str] = None,
        batch_size: int = 20,
    ) -> tuple[int, int, int]:
        """Download PDFs and extract text for comments without text.

        Returns: (processed_count, remaining_count, error_count)
        """
        # Find comments without extracted text (including failed ones we should retry)
        query = select(Comment).where(
            (Comment.comment_text.is_(None))
            | (Comment.comment_text == "")
            | (Comment.pdf_extraction_method == "failed")
        )
        if docket_number:
            query = query.where(Comment.docket_number == docket_number)

        query = query.limit(batch_size)
        result = await self.db.execute(query)
        comments = result.scalars().all()

        if not comments:
            # Count remaining
            count_q = select(func.count(Comment.id)).where(
                (Comment.comment_text.is_(None))
                | (Comment.comment_text == "")
                | (Comment.pdf_extraction_method == "failed")
            )
            if docket_number:
                count_q = count_q.where(Comment.docket_number == docket_number)
            remaining = (await self.db.execute(count_q)).scalar() or 0
            return 0, remaining, 0

        processed = 0
        errors = 0

        for comment in comments:
            try:
                success = await self._extract_text_for_comment(comment)
                if success:
                    processed += 1
                    await self.db.flush()
                else:
                    errors += 1
            except Exception as e:
                logger.error(f"Error extracting text for {comment.document_id}: {e}")
                await self.db.rollback()
                errors += 1

        # Count remaining
        count_q = select(func.count(Comment.id)).where(
            (Comment.comment_text.is_(None))
            | (Comment.comment_text == "")
            | (Comment.pdf_extraction_method == "failed")
        )
        if docket_number:
            count_q = count_q.where(Comment.docket_number == docket_number)
        remaining = (await self.db.execute(count_q)).scalar() or 0

        return processed, remaining, errors

    async def _extract_text_for_comment(self, comment: Comment) -> bool:
        """Download PDF and extract text for a single existing comment.

        Strategy:
        1. Scrape the ViewComment page for inline text AND attachment IDs
        2. If there's a PDF attachment, download it using the attachment ID
        3. Combine: prefer PDF text if available, fall back to page text

        Returns True if successful.
        """
        # Extract the CFTC comment ID from our document_id format
        match = re.search(r'CFTC-COMMENT-(\d+)', comment.document_id)
        if not match:
            logger.warning(f"Cannot parse comment ID from {comment.document_id}")
            return False

        cftc_comment_id = int(match.group(1))

        # Step 1: Scrape the ViewComment page for text + attachment info
        try:
            detail = await cftc_comments_client.get_comment_detail(cftc_comment_id)
        except Exception as e:
            logger.error(f"Failed to scrape ViewComment for {comment.document_id}: {e}")
            return False

        page_text = detail.get("comment_text", "")
        attachment_ids = detail.get("attachment_ids", [])
        pdf_text = ""

        # Step 2: Download and extract PDF if attachment exists
        if attachment_ids:
            s3_key = storage_service.build_comment_pdf_key(
                comment.docket_number, comment.document_id
            )

            pdf_bytes = None
            if storage_service.pdf_exists(s3_key):
                pdf_bytes = storage_service.download_pdf(s3_key)

            if not pdf_bytes:
                try:
                    # Use the ATTACHMENT ID, not the comment ID
                    pdf_bytes = await cftc_comments_client.download_comment_pdf(attachment_ids[0])
                    if pdf_bytes and len(pdf_bytes) > 100:
                        storage_service.upload_pdf(s3_key, pdf_bytes)
                        logger.info(
                            f"Downloaded PDF attachment {attachment_ids[0]} "
                            f"for {comment.document_id} ({len(pdf_bytes)} bytes)"
                        )
                except Exception as e:
                    logger.warning(f"PDF download failed for {comment.document_id}: {e}")

            if pdf_bytes and len(pdf_bytes) > 100:
                try:
                    extraction = extract_text_from_pdf(pdf_bytes)
                    pdf_text = extraction.text
                    comment.pdf_extraction_confidence = extraction.confidence
                    comment.pdf_extraction_method = extraction.method
                    comment.page_count = extraction.page_count
                    comment.original_pdf_url = s3_key
                except Exception as e:
                    logger.warning(f"PDF extraction failed for {comment.document_id}: {e}")

        # Step 3: Use the best available text
        # Prefer PDF text (more complete), fall back to page text
        if pdf_text and len(pdf_text) > len(page_text):
            comment.comment_text = pdf_text
        elif page_text:
            comment.comment_text = page_text
            if not comment.pdf_extraction_method or comment.pdf_extraction_method == "failed":
                comment.pdf_extraction_method = "web_scrape"
                comment.pdf_extraction_confidence = 0.9
                comment.page_count = max(1, len(page_text) // 3000)
        else:
            comment.comment_text = ""
            comment.pdf_extraction_method = "failed"
            comment.pdf_extraction_confidence = 0.0
            return False

        # Sanitize: remove null bytes and other chars PostgreSQL can't handle
        if comment.comment_text:
            comment.comment_text = comment.comment_text.replace('\x00', '')

        # Re-classify tier now that we have text
        comment.tier = await self._classify_tier_initial(
            comment.commenter_organization or "",
            comment.commenter_name or "",
            comment.page_count or 0,
            comment.comment_text,
        )

        logger.info(
            f"Extracted {len(comment.comment_text)} chars for {comment.document_id} "
            f"(method={comment.pdf_extraction_method}, tier={comment.tier})"
        )
        return True

    # -------------------------------------------------------------------
    # Classification
    # -------------------------------------------------------------------

    async def _classify_tier_initial(
        self,
        organization: str,
        name: str,
        page_count: int,
        text: str,
    ) -> int:
        """Initial tier classification based on rules in the spec."""
        combined_identity = f"{organization} {name}".lower()

        # Check Tier 1 organization list
        result = await self.db.execute(select(Tier1Organization))
        tier1_orgs = result.scalars().all()
        for org in tier1_orgs:
            if org.name.lower() in combined_identity:
                return 1
            for variation in (org.name_variations or []):
                if variation.lower() in combined_identity:
                    return 1

        # Check .edu for academic submissions
        if ".edu" in combined_identity:
            return 1

        # Check page count threshold
        if page_count and page_count >= 20:
            return 1

        # Check for legal citations
        if text:
            legal_patterns = [
                r'\bv\.\s+\w+',
                r'\bU\.S\.C\.',
                r'\bF\.\d[a-z]{1,2}\b',
                r'\bS\.\s*Ct\.',
            ]
            legal_hit_count = sum(
                1 for pat in legal_patterns if re.search(pat, text)
            )
            if legal_hit_count >= 2:
                return 1

        # Tier 2: medium-length
        if page_count and 5 <= page_count < 20:
            return 2

        # Default: Tier 3
        return 3

    # -------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------

    @staticmethod
    def _extract_release_id(docket_number: str) -> Optional[int]:
        """Try to extract a CFTC release ID from various input formats."""
        # Format: "CFTC-RELEASE-7624"
        match = re.match(r'CFTC-RELEASE-(\d+)', docket_number, re.IGNORECASE)
        if match:
            return int(match.group(1))

        # Format: raw numeric "7624"
        if docket_number.strip().isdigit():
            return int(docket_number.strip())

        return None

    async def _count_comments(self, docket_number: str) -> int:
        """Count total comments for a docket."""
        result = await self.db.execute(
            select(func.count(Comment.id)).where(
                Comment.docket_number == docket_number
            )
        )
        return result.scalar() or 0
