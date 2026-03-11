"""Client for the Regulations.gov REST API v4.

Used to fetch public comments and their attachments for CFTC dockets.
API docs: https://open.gsa.gov/api/regulationsgov/
"""

import asyncio
import logging
from typing import Optional
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.core.config import settings

logger = logging.getLogger(__name__)

# Rate limit: 1000 requests/hour → ~0.28 req/sec → sleep 3.6s between requests
# We'll be conservative and use a 4-second delay
RATE_LIMIT_DELAY = 4.0


class RegulationsGovClient:
    """Async client for the Regulations.gov v4 API."""

    BASE_URL = settings.REGULATIONS_GOV_BASE_URL

    def __init__(self):
        self._client: Optional[httpx.AsyncClient] = None
        self._api_key = settings.REGULATIONS_GOV_API_KEY

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.BASE_URL,
                timeout=60.0,
                headers={
                    "X-Api-Key": self._api_key,
                    "Accept": "application/json",
                },
            )
        return self._client

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(min=2, max=30),
        retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.ConnectError)),
    )
    async def _get(self, path: str, params: dict | None = None) -> dict:
        """Make a rate-limited GET request to the API."""
        client = await self._get_client()
        await asyncio.sleep(RATE_LIMIT_DELAY)  # respect rate limits
        resp = await client.get(path, params=params)

        if resp.status_code == 429:
            logger.warning("Rate limited by Regulations.gov. Sleeping 60s...")
            await asyncio.sleep(60)
            resp = await client.get(path, params=params)

        resp.raise_for_status()
        return resp.json()

    async def _get_raw(self, url: str) -> bytes:
        """Download raw bytes (e.g., PDF) from a URL."""
        client = await self._get_client()
        await asyncio.sleep(RATE_LIMIT_DELAY)
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.content

    # -----------------------------------------------------------------------
    # Docket Operations
    # -----------------------------------------------------------------------

    async def get_docket(self, docket_id: str) -> dict:
        """Get metadata about a specific docket."""
        data = await self._get(f"/dockets/{docket_id}")
        return data.get("data", {})

    # -----------------------------------------------------------------------
    # Comment Operations
    # -----------------------------------------------------------------------

    async def fetch_comments_for_docket(
        self,
        docket_id: str,
        page_size: int = 250,
        last_modified_after: str | None = None,
    ) -> list[dict]:
        """Fetch all public submission comments for a docket.

        Paginates through all results automatically.

        Args:
            docket_id: e.g., "CFTC-2024-0007"
            page_size: results per page (max 250)
            last_modified_after: ISO datetime string to only get new/updated comments

        Returns:
            List of parsed comment dicts.
        """
        all_comments = []
        page_number = 1

        while True:
            params = {
                "filter[docketId]": docket_id,
                "filter[documentType]": "Public Submission",
                "page[size]": min(page_size, 250),
                "page[number]": page_number,
                "sort": "postedDate",
            }
            if last_modified_after:
                params["filter[lastModifiedDate][ge]"] = last_modified_after

            logger.info(f"Fetching comments for {docket_id}, page {page_number}")
            data = await self._get("/documents", params=params)

            results = data.get("data", [])
            if not results:
                break

            for doc in results:
                parsed = self._parse_comment_listing(doc, docket_id)
                if parsed:
                    all_comments.append(parsed)

            # Check for next page
            meta = data.get("meta", {})
            total_elements = meta.get("totalElements", 0)
            if page_number * page_size >= total_elements:
                break
            page_number += 1

        logger.info(f"Fetched {len(all_comments)} comments for docket {docket_id}")
        return all_comments

    async def get_comment_detail(self, document_id: str) -> dict:
        """Get full details for a specific comment document.

        The listing endpoint doesn't return full text — you need this
        detail call to get attachment info and the comment text.
        """
        data = await self._get(f"/documents/{document_id}")
        doc = data.get("data", {})
        attrs = doc.get("attributes", {})

        return {
            "document_id": document_id,
            "comment_text": attrs.get("comment", ""),
            "commenter_name": self._extract_submitter_name(attrs),
            "commenter_organization": attrs.get("organization", ""),
            "submission_date": attrs.get("postedDate", ""),
            "page_count": attrs.get("pageCount"),
            "has_attachments": bool(attrs.get("fileFormats")),
            "regulations_gov_url": f"https://www.regulations.gov/comment/{document_id}",
        }

    async def get_comment_attachments(self, document_id: str) -> list[dict]:
        """Get attachment URLs for a comment document.

        Returns list of dicts with 'format' and 'url' keys.
        """
        data = await self._get(f"/documents/{document_id}")
        doc = data.get("data", {})
        attrs = doc.get("attributes", {})

        attachments = []
        file_formats = attrs.get("fileFormats", [])
        if file_formats:
            for fmt in file_formats:
                if isinstance(fmt, dict):
                    attachments.append({
                        "format": fmt.get("format", "unknown"),
                        "url": fmt.get("fileUrl", ""),
                    })
                elif isinstance(fmt, str):
                    # Sometimes the API returns just URLs
                    attachments.append({
                        "format": "pdf" if fmt.lower().endswith(".pdf") else "unknown",
                        "url": fmt,
                    })
        return attachments

    async def download_attachment(self, url: str) -> bytes:
        """Download a PDF or other attachment from Regulations.gov."""
        return await self._get_raw(url)

    # -----------------------------------------------------------------------
    # Parsing Helpers
    # -----------------------------------------------------------------------

    def _parse_comment_listing(self, doc: dict, docket_id: str) -> dict | None:
        """Parse a document from the listing endpoint into our format."""
        try:
            attrs = doc.get("attributes", {})
            doc_id = doc.get("id", "")

            return {
                "document_id": doc_id,
                "docket_number": docket_id,
                "commenter_name": self._extract_submitter_name(attrs),
                "commenter_organization": attrs.get("organization", ""),
                "submission_date": attrs.get("postedDate", ""),
                "page_count": attrs.get("pageCount"),
                "has_attachments": bool(attrs.get("fileFormats")),
                "regulations_gov_url": f"https://www.regulations.gov/comment/{doc_id}",
            }
        except Exception as e:
            logger.error(f"Error parsing comment listing: {e}", exc_info=True)
            return None

    @staticmethod
    def _extract_submitter_name(attrs: dict) -> str:
        """Extract the submitter name from document attributes."""
        # The API has several possible fields
        first = attrs.get("firstName", "")
        last = attrs.get("lastName", "")
        if first or last:
            return f"{first} {last}".strip()
        return attrs.get("submitterName", "") or attrs.get("title", "")


# Module-level convenience instance
regulations_gov_client = RegulationsGovClient()
