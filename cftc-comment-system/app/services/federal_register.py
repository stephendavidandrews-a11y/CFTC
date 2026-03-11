"""Client for the Federal Register API.

Used to detect new CFTC proposed rules and fetch rule metadata.
API docs: https://www.federalregister.gov/developers/api/v1
"""

import logging
from datetime import date, timedelta
from typing import Optional
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import settings
from app.models.models import PriorityLevel

logger = logging.getLogger(__name__)

# Keywords that trigger HIGH priority classification
HIGH_PRIORITY_KEYWORDS = [
    "digital asset",
    "cryptocurrency", "crypto asset",
    "virtual currency",
    "distributed ledger", "blockchain",
    "event contract",
    "prediction market",
    "political contract",
    "tokenized",
    "decentralized finance", "defi",
    "stablecoin",
]

# Compound keyword rules (both terms must appear)
HIGH_PRIORITY_COMPOUND = [
    ({"spot"}, {"bitcoin", "ether", "crypto"}),
]


def classify_priority(title: str, summary: str = "", page_count: int = 0) -> PriorityLevel:
    """Determine if a proposed rule is HIGH or STANDARD priority."""
    combined = f"{title} {summary}".lower()

    # Check simple keywords
    for keyword in HIGH_PRIORITY_KEYWORDS:
        if keyword in combined:
            return PriorityLevel.HIGH

    # Check compound keywords
    for set_a, set_b in HIGH_PRIORITY_COMPOUND:
        if any(w in combined for w in set_a) and any(w in combined for w in set_b):
            return PriorityLevel.HIGH

    # Check page count threshold
    if page_count >= 50:
        return PriorityLevel.HIGH

    return PriorityLevel.STANDARD


class FederalRegisterClient:
    """Async client for the Federal Register API."""

    BASE_URL = settings.FEDERAL_REGISTER_BASE_URL

    def __init__(self):
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.BASE_URL,
                timeout=30.0,
                headers={"Accept": "application/json"},
            )
        return self._client

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    async def _get(self, path: str, params: dict | None = None) -> dict:
        client = await self._get_client()
        resp = await client.get(path, params=params)
        resp.raise_for_status()
        return resp.json()

    async def search_cftc_proposed_rules(
        self,
        publication_date_gte: date | None = None,
        publication_date_lte: date | None = None,
        page: int = 1,
        per_page: int = 20,
    ) -> dict:
        """Search for CFTC proposed rules in the Federal Register.

        Returns the raw API response with 'results' and 'count' keys.
        """
        params = {
            "conditions[agencies][]": "commodity-futures-trading-commission",
            "conditions[type][]": "PRORULE",  # Proposed Rule
            "per_page": per_page,
            "page": page,
            "order": "newest",
        }
        if publication_date_gte:
            params["conditions[publication_date][gte]"] = publication_date_gte.isoformat()
        if publication_date_lte:
            params["conditions[publication_date][lte]"] = publication_date_lte.isoformat()

        logger.info(f"Searching Federal Register: {params}")
        return await self._get("/documents.json", params=params)

    async def get_document(self, document_number: str) -> dict:
        """Get full details for a specific Federal Register document."""
        return await self._get(f"/documents/{document_number}.json")

    async def check_new_rules_today(self) -> list[dict]:
        """Check for any new CFTC proposed rules published in the last 24 hours.

        Returns a list of parsed rule dicts ready for database insertion.
        """
        today = date.today()
        yesterday = today - timedelta(days=1)

        data = await self.search_cftc_proposed_rules(
            publication_date_gte=yesterday,
            publication_date_lte=today,
        )

        rules = []
        for doc in data.get("results", []):
            rule = self._parse_document(doc)
            if rule:
                rules.append(rule)

        logger.info(f"Found {len(rules)} new CFTC proposed rule(s)")
        return rules

    async def fetch_all_cftc_proposed_rules(
        self,
        since: date = date(2020, 1, 1),
    ) -> list[dict]:
        """Fetch all CFTC proposed rules since a given date. Used for historical pre-population."""
        all_rules = []
        page = 1

        while True:
            data = await self.search_cftc_proposed_rules(
                publication_date_gte=since,
                page=page,
                per_page=50,
            )

            results = data.get("results", [])
            if not results:
                break

            for doc in results:
                rule = self._parse_document(doc)
                if rule:
                    all_rules.append(rule)

            total_pages = data.get("total_pages", 1)
            if page >= total_pages:
                break
            page += 1

        logger.info(f"Fetched {len(all_rules)} total CFTC proposed rules since {since}")
        return all_rules

    def _parse_document(self, doc: dict) -> dict | None:
        """Parse a Federal Register API document into our rule format."""
        try:
            title = doc.get("title", "")
            abstract = doc.get("abstract", "")
            page_length = doc.get("page_length", 0) or 0

            # Extract docket numbers — FR API returns a list of regulation_id_numbers
            docket_ids = doc.get("docket_ids", [])
            docket_number = docket_ids[0] if docket_ids else None

            # Some rules may not have a docket number in the API response
            # Use the document number as a fallback identifier
            if not docket_number:
                docket_number = f"FR-{doc.get('document_number', 'UNKNOWN')}"

            # Extract RIN
            rin_list = doc.get("regulation_id_numbers", [])
            rin = rin_list[0] if rin_list else None

            # Parse comment period dates
            comment_start = doc.get("comments_open_on")
            comment_end = doc.get("comments_close_on")

            priority = classify_priority(title, abstract, page_length)

            return {
                "docket_number": docket_number,
                "rin": rin,
                "title": title,
                "publication_date": doc.get("publication_date"),
                "comment_period_start": comment_start,
                "comment_period_end": comment_end,
                "federal_register_citation": f"{doc.get('volume', '')} FR {doc.get('start_page', '')}",
                "federal_register_doc_number": doc.get("document_number"),
                "priority_level": priority,
                "status": RuleStatus.OPEN if comment_end and date.fromisoformat(comment_end) >= date.today() else RuleStatus.CLOSED,
                "full_text_url": doc.get("raw_text_url") or doc.get("html_url"),
                "summary": abstract,
                "regulations_gov_url": doc.get("regulations_dot_gov_url"),
                "page_count": page_length,
            }
        except Exception as e:
            logger.error(f"Error parsing FR document: {e}", exc_info=True)
            return None


# Module-level convenience instance
from app.models.models import RuleStatus  # noqa: E402
federal_register_client = FederalRegisterClient()
