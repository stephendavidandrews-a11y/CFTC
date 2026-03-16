"""Comment Ingestion Pipeline (SQLite version)."""

import re
import json
import logging
from datetime import datetime
from typing import Optional

from app.services.cftc_comments import cftc_comments_client
from app.services.pdf_extraction import extract_text_from_pdf
from app.services.storage import storage_service

logger = logging.getLogger(__name__)


def _sync_fetch_comments(release_id: int) -> list:
    """Synchronous wrapper to fetch comments from CFTC portal."""
    import asyncio
    try:
        loop = asyncio.new_event_loop()
        result = loop.run_until_complete(cftc_comments_client.fetch_comments_for_release(release_id))
        loop.close()
        return result
    except Exception as e:
        logger.error(f"Error fetching comments for release {release_id}: {e}")
        return []


def _sync_download_pdf(comment_id: int) -> bytes:
    """Synchronous wrapper to download PDF."""
    import asyncio
    try:
        loop = asyncio.new_event_loop()
        result = loop.run_until_complete(cftc_comments_client.download_comment_pdf(comment_id))
        loop.close()
        return result
    except Exception as e:
        logger.warning(f"Error downloading PDF for comment {comment_id}: {e}")
        return b""


def _sync_get_comment_detail(comment_id: int) -> dict:
    """Synchronous wrapper for comment detail."""
    import asyncio
    try:
        loop = asyncio.new_event_loop()
        result = loop.run_until_complete(cftc_comments_client.get_comment_detail(comment_id))
        loop.close()
        return result
    except Exception as e:
        logger.warning(f"Error getting comment detail for {comment_id}: {e}")
        return {"comment_text": "", "attachment_ids": [], "attachment_filenames": []}


def _sync_detect_new_rules():
    """Synchronous wrapper for Federal Register check."""
    import asyncio
    from app.services.federal_register import federal_register_client
    try:
        loop = asyncio.new_event_loop()
        result = loop.run_until_complete(federal_register_client.check_new_rules_today())
        loop.close()
        return result
    except Exception as e:
        logger.error(f"Error detecting new rules: {e}")
        return []


def _sync_get_rulemakings(year_or_current):
    """Synchronous wrapper for CFTC rulemaking lookup."""
    import asyncio
    try:
        loop = asyncio.new_event_loop()
        if year_or_current is None:
            result = loop.run_until_complete(cftc_comments_client.get_current_rulemakings())
        else:
            result = loop.run_until_complete(cftc_comments_client.get_rulemakings_by_year(year_or_current))
        loop.close()
        return result
    except Exception as e:
        logger.error(f"Error getting rulemakings: {e}")
        return []


class CommentIngestionPipeline:
    def __init__(self, conn):
        self.conn = conn

    def detect_and_store_new_rules(self) -> list:
        new_rules_data = _sync_detect_new_rules()
        stored = []
        for rule_data in new_rules_data:
            rule = self._upsert_rule(rule_data)
            if rule:
                stored.append(rule)
                logger.info(f"Stored new rule: {rule['docket_number']} - {rule['title']}")
        return stored

    def add_docket_manually(self, docket_number: str) -> Optional[dict]:
        release_id = self._extract_release_id(docket_number)
        if release_id:
            docket_number = f"CFTC-RELEASE-{release_id}"

        existing = self.conn.execute(
            "SELECT * FROM proposed_rules WHERE docket_number = ?", (docket_number,)
        ).fetchone()
        if existing:
            return dict(existing)

        title = f"CFTC Release #{release_id}" if release_id else f"Docket {docket_number}"
        summary = ""
        fr_citation = ""

        if release_id:
            for year_or_current in [None, 2026, 2025, 2024, 2023]:
                try:
                    releases = _sync_get_rulemakings(year_or_current)
                    match = next((r for r in releases if r.release_id == release_id), None)
                    if match:
                        title = match.title
                        summary = match.description or ""
                        fr_citation = match.fr_citation or ""
                        break
                except Exception:
                    continue

        regs_url = f"https://comments.cftc.gov/PublicComments/CommentList.aspx?id={release_id}" if release_id else None

        self.conn.execute(
            """INSERT INTO proposed_rules
               (docket_number, title, summary, federal_register_citation, status, priority_level, regulations_gov_url)
               VALUES (?, ?, ?, ?, 'CLOSED', 'STANDARD', ?)""",
            (docket_number, title, summary, fr_citation, regs_url)
        )
        self.conn.commit()

        row = self.conn.execute(
            "SELECT * FROM proposed_rules WHERE docket_number = ?", (docket_number,)
        ).fetchone()
        return dict(row) if row else None

    def _upsert_rule(self, rule_data: dict) -> Optional[dict]:
        try:
            existing = self.conn.execute(
                "SELECT id FROM proposed_rules WHERE docket_number = ?",
                (rule_data["docket_number"],)
            ).fetchone()

            if existing:
                self.conn.execute(
                    """UPDATE proposed_rules SET
                       rin = ?, title = ?, publication_date = ?, comment_period_start = ?,
                       comment_period_end = ?, federal_register_citation = ?,
                       federal_register_doc_number = ?, priority_level = ?, status = ?,
                       full_text_url = ?, summary = ?, regulations_gov_url = ?,
                       page_count = ?, updated_at = datetime('now')
                       WHERE docket_number = ?""",
                    (
                        rule_data.get("rin"), rule_data["title"],
                        rule_data.get("publication_date"), rule_data.get("comment_period_start"),
                        rule_data.get("comment_period_end"), rule_data.get("federal_register_citation"),
                        rule_data.get("federal_register_doc_number"),
                        rule_data.get("priority_level", "STANDARD"),
                        rule_data.get("status", "OPEN"),
                        rule_data.get("full_text_url"), rule_data.get("summary"),
                        rule_data.get("regulations_gov_url"), rule_data.get("page_count"),
                        rule_data["docket_number"],
                    )
                )
            else:
                self.conn.execute(
                    """INSERT INTO proposed_rules
                       (docket_number, rin, title, publication_date, comment_period_start,
                        comment_period_end, federal_register_citation, federal_register_doc_number,
                        priority_level, status, full_text_url, summary, regulations_gov_url, page_count)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        rule_data["docket_number"], rule_data.get("rin"), rule_data["title"],
                        rule_data.get("publication_date"), rule_data.get("comment_period_start"),
                        rule_data.get("comment_period_end"), rule_data.get("federal_register_citation"),
                        rule_data.get("federal_register_doc_number"),
                        rule_data.get("priority_level", "STANDARD"),
                        rule_data.get("status", "OPEN"),
                        rule_data.get("full_text_url"), rule_data.get("summary"),
                        rule_data.get("regulations_gov_url"), rule_data.get("page_count"),
                    )
                )

            self.conn.commit()
            row = self.conn.execute(
                "SELECT * FROM proposed_rules WHERE docket_number = ?",
                (rule_data["docket_number"],)
            ).fetchone()
            return dict(row) if row else None
        except Exception as e:
            logger.error(f"Error upserting rule: {e}", exc_info=True)
            return None

    def fetch_and_store_comments(self, docket_number: str) -> int:
        release_id = self._extract_release_id(docket_number)

        if not release_id:
            row = self.conn.execute(
                "SELECT regulations_gov_url FROM proposed_rules WHERE docket_number = ?",
                (docket_number,)
            ).fetchone()
            if row and row["regulations_gov_url"]:
                match = re.search(r'id=(\d+)', row["regulations_gov_url"])
                if match:
                    release_id = int(match.group(1))

        if not release_id:
            logger.error(f"Cannot fetch comments for '{docket_number}'.")
            return 0

        normalized_docket = f"CFTC-RELEASE-{release_id}"

        rule = self.conn.execute(
            "SELECT * FROM proposed_rules WHERE docket_number = ?", (normalized_docket,)
        ).fetchone()
        if not rule:
            self.add_docket_manually(str(release_id))
            rule = self.conn.execute(
                "SELECT * FROM proposed_rules WHERE docket_number = ?", (normalized_docket,)
            ).fetchone()

        cftc_comments = _sync_fetch_comments(release_id)

        new_count = 0
        for cftc_comment in cftc_comments:
            stored = self._process_cftc_comment(
                cftc_comment, normalized_docket,
                fr_citation=rule["federal_register_citation"] or "" if rule else "",
            )
            if stored:
                new_count += 1

        now = datetime.utcnow().isoformat()
        total = self.conn.execute(
            "SELECT COUNT(*) as cnt FROM comments WHERE docket_number = ?", (normalized_docket,)
        ).fetchone()["cnt"]

        self.conn.execute(
            "UPDATE proposed_rules SET last_comment_pull = ?, total_comments = ? WHERE docket_number = ?",
            (now, total, normalized_docket)
        )
        self.conn.commit()

        logger.info(f"Stored {new_count} new comments for release {release_id}")
        return new_count

    def _process_cftc_comment(self, cftc_comment, docket_number, fr_citation=""):
        document_id = f"CFTC-COMMENT-{cftc_comment.comment_id}"

        existing = self.conn.execute(
            "SELECT id FROM comments WHERE document_id = ?", (document_id,)
        ).fetchone()
        if existing:
            return None

        pdf_text = ""
        pdf_confidence = None
        pdf_method = None
        s3_key = None
        page_count = None

        # PDF download skipped during initial fetch — Cloudflare blocks direct
        # programmatic access to PdfHandler.ashx. Use extract-text endpoint
        # later to retry individually, or download manually.
        logger.debug(f"Skipping PDF download for comment {cftc_comment.comment_id} (Cloudflare)")

        tier = self._classify_tier_initial(
            cftc_comment.organization or "",
            cftc_comment.commenter_name or "",
            page_count or 0,
            pdf_text,
        )

        sub_date = cftc_comment.submission_date.isoformat() if cftc_comment.submission_date else None

        self.conn.execute(
            """INSERT INTO comments
               (docket_number, document_id, commenter_name, commenter_organization,
                submission_date, comment_text, original_pdf_url, page_count,
                has_attachments, attachment_count, tier,
                pdf_extraction_confidence, pdf_extraction_method, regulations_gov_url)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, 1, ?, ?, ?, ?)""",
            (
                docket_number, document_id,
                cftc_comment.commenter_name, cftc_comment.organization,
                sub_date, pdf_text, s3_key, page_count, tier,
                pdf_confidence, pdf_method, cftc_comment.pdf_url,
            )
        )
        self.conn.commit()
        return True

    def extract_text_batch(self, docket_number=None, batch_size=20):
        where = "WHERE (comment_text IS NULL OR comment_text = '' OR pdf_extraction_method = 'failed')"
        params = []
        if docket_number:
            where += " AND docket_number = ?"
            params.append(docket_number)

        rows = self.conn.execute(
            f"SELECT * FROM comments {where} LIMIT ?", params + [batch_size]
        ).fetchall()

        if not rows:
            remaining = self.conn.execute(
                f"SELECT COUNT(*) as cnt FROM comments {where}", params
            ).fetchone()["cnt"]
            return 0, remaining, 0

        processed = 0
        errors = 0

        for row in rows:
            try:
                success = self._extract_text_for_comment(dict(row))
                if success:
                    processed += 1
                else:
                    errors += 1
            except Exception as e:
                logger.error(f"Error extracting text for {row['document_id']}: {e}")
                errors += 1

        remaining = self.conn.execute(
            f"SELECT COUNT(*) as cnt FROM comments {where}", params
        ).fetchone()["cnt"]

        return processed, remaining, errors

    def _extract_text_for_comment(self, comment: dict) -> bool:
        match = re.search(r'CFTC-COMMENT-(\d+)', comment["document_id"])
        if not match:
            return False

        cftc_comment_id = int(match.group(1))

        try:
            detail = _sync_get_comment_detail(cftc_comment_id)
        except Exception as e:
            logger.error(f"Failed to scrape ViewComment for {comment['document_id']}: {e}")
            return False

        page_text = detail.get("comment_text", "")
        attachment_ids = detail.get("attachment_ids", [])
        pdf_text = ""

        if attachment_ids:
            s3_key = storage_service.build_comment_pdf_key(
                comment["docket_number"], comment["document_id"]
            )

            pdf_bytes = None
            if storage_service.pdf_exists(s3_key):
                pdf_bytes = storage_service.download_pdf(s3_key)

            if not pdf_bytes:
                try:
                    pdf_bytes = _sync_download_pdf(attachment_ids[0])
                    if pdf_bytes and len(pdf_bytes) > 100:
                        storage_service.upload_pdf(s3_key, pdf_bytes)
                except Exception as e:
                    logger.warning(f"PDF download failed for {comment['document_id']}: {e}")

            if pdf_bytes and len(pdf_bytes) > 100:
                try:
                    extraction = extract_text_from_pdf(pdf_bytes)
                    pdf_text = extraction.text
                    update_fields = {
                        "pdf_extraction_confidence": extraction.confidence,
                        "pdf_extraction_method": extraction.method,
                        "page_count": extraction.page_count,
                        "original_pdf_url": s3_key,
                    }
                except Exception:
                    update_fields = {}
            else:
                update_fields = {}
        else:
            update_fields = {}

        # Choose best text
        if pdf_text and len(pdf_text) > len(page_text):
            final_text = pdf_text
        elif page_text:
            final_text = page_text
            update_fields.setdefault("pdf_extraction_method", "web_scrape")
            update_fields.setdefault("pdf_extraction_confidence", 0.9)
            update_fields.setdefault("page_count", max(1, len(page_text) // 3000))
        else:
            self.conn.execute(
                "UPDATE comments SET comment_text = '', pdf_extraction_method = 'failed', pdf_extraction_confidence = 0.0 WHERE id = ?",
                (comment["id"],)
            )
            self.conn.commit()
            return False

        final_text = final_text.replace('\x00', '')

        tier = self._classify_tier_initial(
            comment.get("commenter_organization") or "",
            comment.get("commenter_name") or "",
            update_fields.get("page_count", comment.get("page_count") or 0),
            final_text,
        )

        set_parts = ["comment_text = ?", "tier = ?"]
        set_params = [final_text, tier]
        for k, v in update_fields.items():
            set_parts.append(f"{k} = ?")
            set_params.append(v)
        set_params.append(comment["id"])

        self.conn.execute(
            f"UPDATE comments SET {', '.join(set_parts)} WHERE id = ?",
            set_params
        )
        self.conn.commit()
        return True

    def _classify_tier_initial(self, organization, name, page_count, text):
        combined = f"{organization} {name}".lower()

        rows = self.conn.execute("SELECT * FROM tier1_organizations").fetchall()
        for org in rows:
            if org["name"].lower() in combined:
                return 1
            variations = json.loads(org["name_variations"]) if org["name_variations"] else []
            for v in variations:
                if v.lower() in combined:
                    return 1

        if ".edu" in combined:
            return 1
        if page_count and page_count >= 20:
            return 1
        if text:
            legal_patterns = [r'\bv\.\s+\w+', r'\bU\.S\.C\.', r'\bF\.\d[a-z]{1,2}\b', r'\bS\.\s*Ct\.']
            hits = sum(1 for p in legal_patterns if re.search(p, text))
            if hits >= 2:
                return 1
        if page_count and 5 <= page_count < 20:
            return 2
        return 3

    @staticmethod
    def _extract_release_id(docket_number):
        match = re.match(r'CFTC-RELEASE-(\d+)', docket_number, re.IGNORECASE)
        if match:
            return int(match.group(1))
        if docket_number.strip().isdigit():
            return int(docket_number.strip())
        return None
