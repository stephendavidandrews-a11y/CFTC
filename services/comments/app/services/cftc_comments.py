"""Client for the CFTC Public Comments portal (comments.cftc.gov).

The CFTC does NOT use Regulations.gov for public comments. Instead, they
host their own ASP.NET WebForms portal at comments.cftc.gov. This client
scrapes comment listings and downloads comment PDFs from that portal.

URL Patterns:
- Proposed rules listing: https://comments.cftc.gov/PublicComments/ReleasesWithComments.aspx?Type=ListAll&Year={year}
- Upcoming deadlines:     https://comments.cftc.gov/PublicComments/ReleasesWithComments.aspx
- Comment list for rule:  https://comments.cftc.gov/PublicComments/CommentList.aspx?id={release_id}
- Individual comment PDF: https://comments.cftc.gov/Handlers/PdfHandler.ashx?id={comment_id}
- Search all comments:    https://comments.cftc.gov/PublicComments/CommentList.aspx
"""

import asyncio
import logging
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional
from html.parser import HTMLParser

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import settings

logger = logging.getLogger(__name__)


def _clean_html_entities(text: str) -> str:
    """Clean HTML entities from text."""
    import html
    text = html.unescape(text)
    text = text.replace('&nbsp;', ' ')
    text = text.replace('\xa0', ' ')
    return text.strip()

BASE_URL = "https://comments.cftc.gov"

# Be polite — 2 seconds between requests to .gov site
REQUEST_DELAY = 2.0


# ---------------------------------------------------------------------------
# Data classes for scraped results
# ---------------------------------------------------------------------------

@dataclass
class CftcRuleEntry:
    """A rulemaking entry from the CFTC comments portal."""
    release_id: int  # The numeric ID used in CommentList.aspx?id=
    title: str
    description: str = ""
    fr_citation: str = ""
    open_date: Optional[date] = None
    closing_date: Optional[date] = None
    extended_date: Optional[date] = None
    category: str = ""  # "Proposed Rule", "Public Information Collection", etc.
    comment_url: str = ""
    view_comments_url: str = ""


@dataclass
class CftcComment:
    """A single public comment scraped from the CFTC portal."""
    comment_id: int  # The numeric ID for PdfHandler.ashx?id=
    commenter_name: str = ""
    organization: str = ""
    submission_date: Optional[date] = None
    pdf_url: str = ""
    release_id: int = 0  # Which rulemaking this belongs to


# ---------------------------------------------------------------------------
# HTML Parsers
# ---------------------------------------------------------------------------

class ReleaseListParser(HTMLParser):
    """Parse the ReleasesWithComments.aspx page to extract rulemaking entries.

    The page has a table structure. Each rulemaking row contains:
    - A deadline date
    - A category + FR citation link
    - The title text
    - Open/Closing/Extended dates
    - Submit Comments link (with id param)
    - View Comments link (with id param)
    """

    def __init__(self):
        super().__init__()
        self.rules: list[CftcRuleEntry] = []
        self._in_td = False
        self._current_text = ""
        self._current_rule: Optional[dict] = None
        self._link_hrefs: list[str] = []

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        if tag == "td":
            self._in_td = True
            self._current_text = ""
        elif tag == "a" and self._in_td:
            href = attrs_dict.get("href", "")
            self._link_hrefs.append(href)
            # Extract release ID from View Comments links
            if "CommentList.aspx?id=" in href:
                match = re.search(r'id=(\d+)', href)
                if match and self._current_rule is not None:
                    self._current_rule["release_id"] = int(match.group(1))
                    self._current_rule["view_comments_url"] = f"{BASE_URL}/PublicComments/{href}"

    def handle_data(self, data):
        if self._in_td:
            self._current_text += data.strip()

    def handle_endtag(self, tag):
        if tag == "td":
            self._in_td = False
        elif tag == "tr":
            # Try to construct a rule from accumulated data
            pass


class CommentListParser(HTMLParser):
    """Parse the CommentList.aspx page to extract individual comments.

    Each comment row typically contains:
    - Comment number / link to PDF
    - Commenter name
    - Organization
    - Date received
    """

    def __init__(self):
        super().__init__()
        self.comments: list[CftcComment] = []
        self._in_td = False
        self._in_tr = False
        self._current_text = ""
        self._current_row: list[str] = []
        self._current_links: list[str] = []
        self._row_count = 0

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        if tag == "tr":
            self._in_tr = True
            self._current_row = []
            self._current_links = []
        elif tag == "td":
            self._in_td = True
            self._current_text = ""
        elif tag == "a" and self._in_td:
            href = attrs_dict.get("href", "")
            if href:
                self._current_links.append(href)

    def handle_data(self, data):
        if self._in_td:
            self._current_text += data.strip() + " "

    def handle_endtag(self, tag):
        if tag == "td":
            self._in_td = False
            self._current_row.append(self._current_text.strip())
        elif tag == "tr":
            self._in_tr = False
            self._row_count += 1
            self._try_parse_comment_row()

    def _try_parse_comment_row(self):
        """Try to parse a table row as a comment entry."""
        if len(self._current_row) < 2:
            return

        # Look for PDF handler links to identify comment rows
        comment_id = None
        for link in self._current_links:
            match = re.search(r'PdfHandler\.ashx\?id=(\d+)', link)
            if match:
                comment_id = int(match.group(1))
                break

        if comment_id is None:
            # Also check for ViewComment links
            for link in self._current_links:
                match = re.search(r'ViewComment\.aspx\?id=(\d+)', link)
                if match:
                    comment_id = int(match.group(1))
                    break

        if comment_id is None:
            return

        comment = CftcComment(
            comment_id=comment_id,
            pdf_url=f"{BASE_URL}/Handlers/PdfHandler.ashx?id={comment_id}",
        )

        # Try to extract fields from the row cells
        # The exact column layout varies, but typically:
        # [number, name, org, date] or [name/org, date, link]
        for i, cell in enumerate(self._current_row):
            # Try to detect date cells
            date_match = re.search(r'(\d{1,2}/\d{1,2}/\d{4})', cell)
            if date_match:
                try:
                    comment.submission_date = datetime.strptime(
                        date_match.group(1), "%m/%d/%Y"
                    ).date()
                except ValueError:
                    pass
                continue

            # Skip very short cells (just numbers, etc.)
            if len(cell) < 3:
                continue

            # First substantial text cell is likely the commenter name/org
            if not comment.commenter_name and not cell.isdigit():
                # If cell contains a comma or "on behalf of", split name/org
                if " on behalf of " in cell.lower():
                    parts = re.split(r' on behalf of ', cell, flags=re.IGNORECASE)
                    comment.commenter_name = parts[0].strip()
                    comment.organization = parts[1].strip() if len(parts) > 1 else ""
                else:
                    comment.commenter_name = cell
            elif comment.commenter_name and not comment.organization and not cell.isdigit():
                comment.organization = cell

        self.comments.append(comment)


# ---------------------------------------------------------------------------
# Main Client
# ---------------------------------------------------------------------------

class CftcCommentsClient:
    """Async client for scraping the CFTC Public Comments portal."""

    def __init__(self):
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=60.0,
                follow_redirects=True,
                headers={
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.9",
                    "Accept-Encoding": "gzip, deflate, br",
                    "Cache-Control": "no-cache",
                    "Sec-Ch-Ua": '"Chromium";v="131", "Not_A Brand";v="24"',
                    "Sec-Ch-Ua-Mobile": "?0",
                    "Sec-Ch-Ua-Platform": '"macOS"',
                    "Sec-Fetch-Dest": "document",
                    "Sec-Fetch-Mode": "navigate",
                    "Sec-Fetch-Site": "none",
                    "Sec-Fetch-User": "?1",
                    "Upgrade-Insecure-Requests": "1",
                },
            )
        return self._client

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=15))
    async def _get_html(self, url: str) -> str:
        """Fetch an HTML page with rate limiting."""
        await asyncio.sleep(REQUEST_DELAY)
        client = await self._get_client()
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.text

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=15))
    async def _get_bytes(self, url: str) -> bytes:
        """Download raw bytes (PDFs) with rate limiting."""
        await asyncio.sleep(REQUEST_DELAY)
        client = await self._get_client()
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.content

    # -------------------------------------------------------------------
    # Rulemaking Listings
    # -------------------------------------------------------------------

    async def get_upcoming_comment_deadlines(self) -> list[CftcRuleEntry]:
        """Get all rulemakings with upcoming comment deadlines (main page)."""
        html = await self._get_html(
            f"{BASE_URL}/PublicComments/ReleasesWithComments.aspx"
        )
        return self._parse_releases_page(html)

    async def get_rulemakings_by_year(self, year: int) -> list[CftcRuleEntry]:
        """Get all rulemakings for a given year."""
        html = await self._get_html(
            f"{BASE_URL}/PublicComments/ReleasesWithComments.aspx?Type=ListAll&Year={year}"
        )
        return self._parse_releases_page(html)

    async def get_current_rulemakings(self) -> list[CftcRuleEntry]:
        """Get current/upcoming rulemakings from the main page."""
        html = await self._get_html(
            f"{BASE_URL}/PublicComments/ReleasesWithComments.aspx"
        )
        return self._parse_releases_page(html)

    def _parse_releases_page(self, html: str) -> list[CftcRuleEntry]:
        """Parse a releases page to extract rulemaking entries.

        The CFTC site uses a repeating structure where each release is in a
        <div class="row"> containing:
        - column-date div with the date
        - column-item div with:
          - First <p>: release type, FR citation link, PDF link
          - Second <p>: the TITLE of the rulemaking
          - Date wrappers with open/closing dates
          - View Comments button with the release ID
        """
        rules = []
        seen_ids = set()

        # Split by row divs to get individual entries
        rows = re.split(r'<div\s+class="row">', html)

        for row in rows:
            # Find release ID from CommentList link
            id_match = re.search(r'CommentList\.aspx\?id=(\d+)', row)
            if not id_match:
                continue

            release_id = int(id_match.group(1))

            # Skip duplicates (each release can appear in multiple links)
            if release_id in seen_ids:
                continue
            seen_ids.add(release_id)

            # Extract FR citation from the hlReleaseLink anchor text
            fr_match = re.search(r'hlReleaseLink_\d+"[^>]*>(\d+\s+FR\s+\d+)</a>', row)
            fr_citation = fr_match.group(1) if fr_match else ""

            # Extract release type from spanReleaseType
            type_match = re.search(r'spanReleaseType_\d+">\s*(.+?)(?:&nbsp;|\s)*</span>', row, re.DOTALL)
            release_type = ""
            if type_match:
                release_type = re.sub(r'<[^>]+>', '', type_match.group(1)).strip()

            # Extract title from the hlReleaseLink anchor text (this is the actual title)
            # On the main page, this contains the rule title
            # On year pages, it contains just the FR citation
            title_link_match = re.search(r'hlReleaseLink_\d+"[^>]*>([^<]+)</a>', row)
            title_from_link = ""
            if title_link_match:
                title_from_link = title_link_match.group(1).strip()
                # If it's just an FR citation (e.g., "88 FR 88376"), it's not a real title
                if re.match(r'^\d+\s+FR\s+\d+$', title_from_link):
                    title_from_link = ""

            # Extract text from the second <p> tag inside column-item
            # On year pages: this is the title/description
            # On main page: this is the description (title is in the link above)
            p_tags = re.findall(r'<p>\s*(.*?)\s*</p>', row, re.DOTALL)
            description = ""
            p2_text = ""
            if len(p_tags) >= 2:
                raw = re.sub(r'<[^>]+>', '', p_tags[1])
                raw = _clean_html_entities(raw)
                raw = re.sub(r'\s+', ' ', raw).strip()
                if raw:
                    p2_text = raw

            # Determine title and description
            if title_from_link:
                # Main page style: title from link, description from second <p>
                title = _clean_html_entities(title_from_link)
                description = p2_text
            elif p2_text:
                # Year page style: title from second <p>
                title = p2_text
            else:
                title = f"CFTC Release #{release_id}"

            # Extract open/closing dates
            open_date = None
            closing_date = None

            open_match = re.search(r'Open\s+Date:\s*(\d{1,2}/\d{1,2}/\d{4})', row)
            close_match = re.search(r'Closing\s+Date:\s*(\d{1,2}/\d{1,2}/\d{4})', row)

            if open_match:
                try:
                    open_date = datetime.strptime(open_match.group(1), "%m/%d/%Y").date()
                except ValueError:
                    pass
            if close_match:
                try:
                    closing_date = datetime.strptime(close_match.group(1), "%m/%d/%Y").date()
                except ValueError:
                    pass

            # Truncate very long titles
            if len(title) > 300:
                title = title[:297] + "..."

            rule = CftcRuleEntry(
                release_id=release_id,
                title=title,
                description=description,
                fr_citation=fr_citation,
                category=release_type,
                open_date=open_date,
                closing_date=closing_date,
                view_comments_url=f"{BASE_URL}/PublicComments/CommentList.aspx?id={release_id}",
            )
            rules.append(rule)

        logger.info(f"Parsed {len(rules)} rulemaking entries from CFTC portal")
        return rules

    # -------------------------------------------------------------------
    # Comment Listings
    # -------------------------------------------------------------------

    async def fetch_comments_for_release(self, release_id: int) -> list[CftcComment]:
        """Fetch all comments for a specific rulemaking, handling Telerik RadGrid pagination.

        Args:
            release_id: The CFTC internal ID (e.g., 7512 for event contracts)

        Returns:
            List of CftcComment objects with metadata and PDF URLs.
        """
        url = f"{BASE_URL}/PublicComments/CommentList.aspx?id={release_id}"
        all_comments = []

        # Page 1: normal GET request
        html = await self._get_html(url)
        page_comments = self._parse_comment_list(html, release_id)
        all_comments.extend(page_comments)
        logger.info(f"Release {release_id} page 1: {len(page_comments)} comments")

        # Check for pagination
        max_page = self._detect_max_page(html)
        if max_page <= 1:
            logger.info(f"Fetched {len(all_comments)} total comments for release {release_id}")
            return all_comments

        # Detect the pagination query parameter name
        change_page_param = self._detect_change_page_param(html)
        logger.info(f"Release {release_id} has {max_page} pages. Fetching all via URL pagination...")

        # Pages 2+: simple GET requests with page parameter
        for page_num in range(2, max_page + 1):
            try:
                html = await self._fetch_page_by_url(release_id, page_num, change_page_param)
                page_comments = self._parse_comment_list(html, release_id)
                all_comments.extend(page_comments)
                logger.info(f"Release {release_id} page {page_num}/{max_page}: {len(page_comments)} comments")
            except Exception as e:
                logger.error(f"Error fetching page {page_num} for release {release_id}: {e}")
                break

        # Deduplicate
        seen = set()
        unique = []
        for c in all_comments:
            if c.comment_id not in seen:
                seen.add(c.comment_id)
                unique.append(c)

        logger.info(f"Fetched {len(unique)} total comments for release {release_id} ({max_page} pages)")
        return unique

    def _detect_max_page(self, html: str) -> int:
        """Detect the maximum page number from Telerik RadGrid pagination.

        The CFTC uses Telerik RadGrid which shows page info like:
          '<strong>822</strong> items in <strong>83</strong> pages'
        and uses SEO-friendly URL pagination like:
          CommentList.aspx?id=7512&ctl00_ctl00_..._gvCommentListChangePage=83
        """
        # Method 1: Look for "X items in Y pages" text
        pages_match = re.search(
            r'items\s+in\s+<strong>(\d+)</strong>\s+pages',
            html,
            re.IGNORECASE,
        )
        if pages_match:
            return int(pages_match.group(1))

        # Method 2: Find max page from ChangePage URL params
        page_numbers = re.findall(
            r'gvCommentListChangePage=(\d+)',
            html,
        )
        if page_numbers:
            return max(int(p) for p in page_numbers)

        return 1

    def _detect_change_page_param(self, html: str) -> str:
        """Extract the full query parameter name used for pagination.

        Returns something like 'ctl00_ctl00_cphContentMain_MainContent_gvCommentListChangePage'
        """
        match = re.search(
            r'(ctl[\w]+_gvCommentListChangePage)=\d+',
            html,
        )
        if match:
            return match.group(1)
        return "ctl00_ctl00_cphContentMain_MainContent_gvCommentListChangePage"

    async def _fetch_page_by_url(self, release_id: int, page_num: int, change_page_param: str) -> str:
        """Fetch a specific page using Telerik RadGrid's SEO URL pagination.

        The CFTC Telerik grid supports simple GET requests with a query parameter:
          CommentList.aspx?id=7512&ctl00_..._gvCommentListChangePage=2
        """
        url = (
            f"{BASE_URL}/PublicComments/CommentList.aspx"
            f"?id={release_id}"
            f"&{change_page_param}={page_num}"
        )
        return await self._get_html(url)

    @staticmethod
    def _extract_hidden_field(html: str, field_name: str) -> str:
        """Extract an ASP.NET hidden field value from HTML."""
        # Try id-based match first
        match = re.search(rf'id="{field_name}"\s+value="([^"]*)"', html)
        if match:
            return match.group(1)
        # Try name-based match
        match = re.search(rf'name="{field_name}"\s+value="([^"]*)"', html)
        if match:
            return match.group(1)
        # Try reversed attribute order
        match = re.search(rf'value="([^"]*)"\s+(?:name|id)="{field_name}"', html)
        return match.group(1) if match else ""

    def _parse_comment_list(self, html: str, release_id: int) -> list[CftcComment]:
        """Parse a CommentList.aspx page to extract comment entries.

        Uses regex extraction for reliability with ASP.NET HTML.
        """
        comments = []

        # Strategy: Find all PDF handler links and extract comment data
        # from surrounding table cells
        #
        # Pattern 1: PdfHandler.ashx?id=XXXXX (direct PDF links)
        # Pattern 2: ViewComment.aspx?id=XXXXX (comment detail page)

        # Find all comment IDs from PDF links
        pdf_pattern = re.compile(r'PdfHandler\.ashx\?id=(\d+)', re.IGNORECASE)
        view_pattern = re.compile(r'ViewComment\.aspx\?id=(\d+)', re.IGNORECASE)

        comment_ids = set()
        for match in pdf_pattern.finditer(html):
            comment_ids.add(int(match.group(1)))
        for match in view_pattern.finditer(html):
            comment_ids.add(int(match.group(1)))

        if not comment_ids:
            logger.warning(f"No comment IDs found on page for release {release_id}")
            return comments

        # Now extract the table rows containing these comments
        # Split by <tr> tags and look for rows with comment IDs
        rows = re.split(r'<tr[^>]*>', html, flags=re.IGNORECASE)

        for row_html in rows:
            # Check if this row contains a comment link
            row_comment_id = None
            for pattern in [pdf_pattern, view_pattern]:
                match = pattern.search(row_html)
                if match:
                    row_comment_id = int(match.group(1))
                    break

            if row_comment_id is None:
                continue

            # Extract cell contents
            cells = re.findall(r'<td[^>]*>(.*?)</td>', row_html, re.DOTALL | re.IGNORECASE)
            clean_cells = []
            for cell in cells:
                # Strip HTML tags
                clean = re.sub(r'<[^>]+>', ' ', cell)
                clean = re.sub(r'&nbsp;', ' ', clean)
                clean = re.sub(r'\s+', ' ', clean).strip()
                clean_cells.append(clean)

            comment = CftcComment(
                comment_id=row_comment_id,
                release_id=release_id,
                pdf_url=f"{BASE_URL}/Handlers/PdfHandler.ashx?id={row_comment_id}",
            )

            # CFTC comment list columns: [Date, FR Citation, First Name, Last Name, Organization, (link)]
            if len(clean_cells) >= 5:
                # Positional extraction
                date_text = clean_cells[0]
                # clean_cells[1] is FR citation — skip
                first_name = clean_cells[2].strip()
                last_name = clean_cells[3].strip()
                org = clean_cells[4].strip()

                date_match = re.search(r'(\d{1,2}/\d{1,2}/\d{4})', date_text)
                if date_match:
                    try:
                        comment.submission_date = datetime.strptime(
                            date_match.group(1), "%m/%d/%Y"
                        ).date()
                    except ValueError:
                        pass

                name_parts = [p for p in [first_name, last_name] if p]
                comment.commenter_name = " ".join(name_parts) if name_parts else ""
                comment.organization = org
            else:
                # Fallback: auto-detect from cells
                for cell_text in clean_cells:
                    if not cell_text:
                        continue
                    date_match = re.search(r'(\d{1,2}/\d{1,2}/\d{4})', cell_text)
                    if date_match and not comment.submission_date:
                        try:
                            comment.submission_date = datetime.strptime(
                                date_match.group(1), "%m/%d/%Y"
                            ).date()
                        except ValueError:
                            pass
                        continue
                    if len(cell_text) < 3 or cell_text.isdigit():
                        continue
                    if re.match(r'^\d+\s+FR\s+\d+$', cell_text):
                        continue
                    if not comment.commenter_name:
                        comment.commenter_name = cell_text
                    elif not comment.organization:
                        comment.organization = cell_text

            comments.append(comment)

        # Deduplicate by comment_id
        seen = set()
        unique_comments = []
        for c in comments:
            if c.comment_id not in seen:
                seen.add(c.comment_id)
                unique_comments.append(c)

        return unique_comments

    # -------------------------------------------------------------------
    # PDF Download
    # -------------------------------------------------------------------

    async def download_comment_pdf(self, comment_id: int) -> bytes:
        """Download a comment PDF by its attachment ID (NOT comment ID).

        Note: The attachment ID is different from the comment ID.
        Use get_comment_detail() to get the correct attachment ID first.
        """
        url = f"{BASE_URL}/Handlers/PdfHandler.ashx?id={comment_id}"
        logger.info(f"Downloading comment PDF: {url}")
        pdf_bytes = await self._get_bytes(url)
        logger.info(f"PDF response for attachment {comment_id}: {len(pdf_bytes)} bytes")
        return pdf_bytes

    async def get_comment_detail(self, comment_id: int) -> dict:
        """Scrape full comment details from the ViewComment page.

        Returns dict with:
          - comment_text: str (the text visible on the page)
          - attachment_ids: list[int] (IDs for PdfHandler.ashx downloads)
          - attachment_filenames: list[str]
        """
        import re
        url = f"{BASE_URL}/PublicComments/ViewComment.aspx?id={comment_id}"
        html = await self._get_html(url)

        result = {
            "comment_text": "",
            "attachment_ids": [],
            "attachment_filenames": [],
        }

        # Extract comment text from the "Comment Text:" section
        # Pattern: <strong>Comment Text:</strong></p> ... </div>
        text_match = re.search(
            r'<strong>Comment Text:</strong>\s*</p>\s*<p>\s*(.*?)\s*</p>\s*</div>',
            html,
            re.DOTALL | re.IGNORECASE,
        )
        if text_match:
            text = text_match.group(1)
            # Clean HTML
            text = re.sub(r'<br\s*/?>', '\n', text)
            text = re.sub(r'<[^>]+>', '', text)
            # Decode HTML entities
            text = text.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
            text = text.replace('&quot;', '"').replace('&#39;', "'").replace('&nbsp;', ' ')
            text = text.replace('\u2018', "'").replace('\u2019', "'")
            text = text.replace('\u201c', '"').replace('\u201d', '"')
            text = text.strip()
            if len(text) > 10:
                result["comment_text"] = text
                logger.info(f"Extracted {len(text)} chars of comment text for comment {comment_id}")

        # Extract PDF attachment IDs from PdfHandler links
        # Pattern: href="../Handlers/PdfHandler.ashx?id=35378">filename.pdf</a>
        attachment_matches = re.findall(
            r'PdfHandler\.ashx\?id=(\d+)"[^>]*>([^<]+)</a>',
            html,
        )
        for att_id, filename in attachment_matches:
            result["attachment_ids"].append(int(att_id))
            result["attachment_filenames"].append(filename.strip())

        logger.info(
            f"Comment {comment_id}: {len(result['comment_text'])} chars text, "
            f"{len(result['attachment_ids'])} attachments"
        )
        return result

    # -------------------------------------------------------------------
    # Convenience Methods
    # -------------------------------------------------------------------

    async def find_release_id_by_keyword(self, keyword: str, year: int = None) -> list[CftcRuleEntry]:
        """Search for a rulemaking by keyword in the title.

        Searches across multiple years if no year specified.
        """
        results = []
        years_to_check = [year] if year else list(range(2026, 2019, -1))

        for y in years_to_check:
            try:
                rules = await self.get_rulemakings_by_year(y)
                for rule in rules:
                    if keyword.lower() in rule.title.lower():
                        results.append(rule)
            except Exception as e:
                logger.warning(f"Error fetching {y} rulemakings: {e}")

        return results


# Module-level convenience instance
cftc_comments_client = CftcCommentsClient()
