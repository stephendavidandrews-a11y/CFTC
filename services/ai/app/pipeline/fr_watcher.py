"""
Federal Register Watcher — polls for new CFTC publications.

Fetches from the public Federal Register API, deduplicates against
fr_documents, classifies into routing tiers, and stages for processing.
"""
import uuid
import json
import logging
from datetime import datetime, timedelta
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

FR_API_BASE = "https://www.federalregister.gov/api/v1"

# Fields to request from the API
FR_FIELDS = [
    "document_number", "title", "type", "action", "abstract",
    "publication_date", "agencies", "comments_close_on",
    "docket_ids", "regulation_id_numbers", "cfr_references",
    "html_url", "pdf_url", "body_html_url", "raw_text_url",
    "full_text_xml_url", "start_page", "end_page",
]

# ── Routing classifier ──────────────────────────────────────────────────────

# Tier 1: Create matter + extract comment topics
TIER1_ACTIONS = [
    "advance notice", "notice of proposed rulemaking", "proposed rule",
    "proposed order", "concept release", "request for comment",
]

# Tier 2: Update existing matter or flag for review
TIER2_ACTIONS = [
    "final rule", "interpretation", "guidance", "withdrawal",
    "exemptive order", "exemptive relief",
]

# Default CFR parts OGC owns — Tier 3 docs referencing these get promoted to Tier 2
DEFAULT_OGC_CFR_PARTS = ["23", "40", "140", "145"]


def classify_tier(
    fr_type: str,
    action: Optional[str],
    cfr_references: list,
    promote_cfr_parts: Optional[list] = None,
) -> int:
    """
    Classify a Federal Register document into a routing tier.

    Tier 1: Proposed rules, ANPRMs, concept releases — create matter + extract
    Tier 2: Final rules, interpretations, withdrawals — update or flag
    Tier 3: PRA notices, corrections, technical amendments — log only

    CFR override: Tier 3 docs referencing OGC-owned CFR parts → promoted to Tier 2.
    """
    action_lower = (action or "").lower()
    fr_type_lower = (fr_type or "").lower()

    # Withdrawal override: withdrawals are never Tier 1, even if fr_type is "Proposed Rule"
    if "withdrawal" in action_lower:
        return 2

    # Tier 1: proposed rules and comment solicitations
    if fr_type_lower == "proposed rule":
        return 1
    if any(kw in action_lower for kw in TIER1_ACTIONS):
        return 1

    # Tier 2: final rules, interpretations, withdrawals, exemptive orders
    if fr_type_lower == "rule":
        if any(kw in action_lower for kw in TIER2_ACTIONS):
            return 2
        # Generic "Rule" with no matching action → still Tier 2
        return 2
    if any(kw in action_lower for kw in TIER2_ACTIONS):
        return 2

    # Default: Tier 3 (log only)
    tier = 3

    # CFR override: promote to Tier 2 if document references OGC-owned CFR parts
    if tier == 3 and cfr_references:
        parts = promote_cfr_parts or DEFAULT_OGC_CFR_PARTS
        for ref in cfr_references:
            part = str(ref.get("part", "")) if isinstance(ref, dict) else ""
            if part in parts:
                logger.info("Promoting Tier 3 → 2 due to CFR Part %s reference", part)
                return 2

    return tier


# ── API poller ───────────────────────────────────────────────────────────────

async def fetch_fr_documents(
    since_date: str,
    per_page: int = 100,
) -> list[dict]:
    """
    Fetch CFTC documents from the Federal Register API.

    Args:
        since_date: ISO date string (YYYY-MM-DD) — fetch docs published on or after
        per_page: results per page (max 1000)

    Returns list of document dicts from the API.
    """
    params = {
        "conditions[agencies][]": "commodity-futures-trading-commission",
        "conditions[publication_date][gte]": since_date,
        "per_page": str(per_page),
    }
    # Add field params
    for field in FR_FIELDS:
        params["fields[]"] = field  # httpx handles repeated keys via list

    # Build URL manually since httpx doesn't handle repeated keys well
    field_params = "&".join(f"fields%5B%5D={f}" for f in FR_FIELDS)
    url = (
        f"{FR_API_BASE}/documents.json"
        f"?conditions%5Bagencies%5D%5B%5D=commodity-futures-trading-commission"
        f"&conditions%5Bpublication_date%5D%5Bgte%5D={since_date}"
        f"&{field_params}"
        f"&per_page={per_page}"
    )

    all_results = []
    async with httpx.AsyncClient(timeout=30.0) as client:
        while url:
            logger.info("Fetching FR API: %s", url[:120])
            resp = await client.get(url, follow_redirects=True)
            resp.raise_for_status()
            data = resp.json()

            results = data.get("results", [])
            all_results.extend(results)
            logger.info("Got %d documents (total so far: %d)", len(results), len(all_results))

            url = data.get("next_page_url")

    return all_results


async def fetch_full_text(doc: dict) -> Optional[str]:
    """Fetch full text for a document via raw_text_url or body_html_url.

    The raw_text_url sometimes returns a short HTML wrapper (~713 bytes)
    instead of the full document. When that happens, fall back to body_html_url.
    Minimum useful document length threshold: 1000 chars.
    """
    raw_url = doc.get("raw_text_url")
    html_url = doc.get("body_html_url")
    min_length = 1000  # Short responses are redirect pages, not real content

    async with httpx.AsyncClient(timeout=60.0) as client:
        # Try raw text first
        if raw_url:
            try:
                resp = await client.get(raw_url, follow_redirects=True)
                resp.raise_for_status()
                text = resp.text
                if text and len(text) > min_length:
                    return text
                else:
                    logger.info("raw_text_url returned only %d chars for %s, trying body_html_url",
                                len(text) if text else 0, doc.get("document_number"))
            except Exception as e:
                logger.warning("Failed to fetch raw text for %s: %s",
                               doc.get("document_number"), e)

        # Fall back to HTML body
        if html_url:
            try:
                resp = await client.get(html_url, follow_redirects=True)
                resp.raise_for_status()
                text = resp.text
                if text and len(text) > min_length:
                    return text
                else:
                    logger.warning("body_html_url also short (%d chars) for %s",
                                   len(text) if text else 0, doc.get("document_number"))
            except Exception as e:
                logger.warning("Failed to fetch HTML for %s: %s",
                               doc.get("document_number"), e)

    return None


# ── Database operations ──────────────────────────────────────────────────────

def get_existing_doc_numbers(db) -> set:
    """Get all document_number values already in fr_documents."""
    rows = db.execute("SELECT document_number FROM fr_documents").fetchall()
    return {row["document_number"] for row in rows}


def get_last_poll_date(db) -> Optional[str]:
    """Get the last poll date from fr_documents, or None if never polled."""
    try:
        row = db.execute(
            "SELECT MAX(publication_date) as last_date FROM fr_documents"
        ).fetchone()
        if row and row["last_date"]:
            return row["last_date"]
    except Exception:
        pass
    return None


def update_sync_state(db, items_created: int, status: str = "success", error: str = None):
    """Update sync_state if it exists (tracker db), or log to fr_documents metadata."""
    now = datetime.now().isoformat()
    try:
        db.execute("""
            INSERT INTO sync_state (sync_type, last_run_at, last_status, last_error,
                                    items_created, items_updated, next_run_at)
            VALUES ('federal_register', ?, ?, ?, ?, 0, ?)
            ON CONFLICT(sync_type) DO UPDATE SET
                last_run_at = excluded.last_run_at,
                last_status = excluded.last_status,
                last_error = excluded.last_error,
                items_created = excluded.items_created,
                next_run_at = excluded.next_run_at
        """, (now, status, error, items_created, now))
        db.commit()
    except Exception:
        # sync_state table may not exist in ai.db; that is fine
        logger.debug("sync_state table not available, skipping state update")


def stage_document(db, doc: dict, tier: int, full_text: Optional[str] = None) -> str:
    """Insert a document into fr_documents. Returns the new row's ID."""
    doc_id = str(uuid.uuid4())
    now = datetime.now().isoformat()

    db.execute("""
        INSERT INTO fr_documents (
            id, document_number, title, fr_type, action, abstract,
            publication_date, agencies_json, comments_close_on,
            docket_ids_json, regulation_id_numbers_json, cfr_references_json,
            html_url, pdf_url, body_html_url, raw_text_url,
            full_text, routing_tier, processing_status,
            created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        doc_id,
        doc.get("document_number"),
        doc.get("title"),
        doc.get("type"),
        doc.get("action"),
        doc.get("abstract"),
        doc.get("publication_date"),
        json.dumps(doc.get("agencies", [])),
        doc.get("comments_close_on"),
        json.dumps(doc.get("docket_ids", [])),
        json.dumps(doc.get("regulation_id_numbers", [])),
        json.dumps(doc.get("cfr_references", [])),
        doc.get("html_url"),
        doc.get("pdf_url"),
        doc.get("body_html_url"),
        doc.get("raw_text_url"),
        full_text,
        tier,
        "pending" if tier <= 2 else "skipped",
        now,
        now,
    ))
    db.commit()
    return doc_id


# ── Main watcher entry point ────────────────────────────────────────────────

async def run_watcher(db, config: dict = None):
    """
    Main watcher entry point. Polls FR API, deduplicates, classifies, stages.

    Args:
        db: sqlite3 connection to ai.db
        config: federal_register config dict from ai_policy.json

    Returns dict with counts: {new, skipped_existing, tier_1, tier_2, tier_3, errors}
    """
    config = config or {}
    if not config.get("enabled", False):
        logger.info("Federal Register watcher is disabled")
        return {"new": 0, "skipped_existing": 0, "status": "disabled"}

    promote_cfr_parts = config.get("tier3_promote_cfr_parts", DEFAULT_OGC_CFR_PARTS)

    # Determine poll window
    last_poll = get_last_poll_date(db)
    if last_poll:
        since_date = last_poll
    else:
        # First run: look back 90 days
        since_date = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")
    logger.info("Polling Federal Register for CFTC docs since %s", since_date)

    # Fetch from API
    try:
        documents = await fetch_fr_documents(since_date)
    except Exception as e:
        logger.error("FR API fetch failed: %s", e)
        update_sync_state(db, 0, status="error", error=str(e))
        return {"new": 0, "error": str(e)}

    # Deduplicate
    existing = get_existing_doc_numbers(db)
    new_docs = [d for d in documents if d.get("document_number") not in existing]
    skipped = len(documents) - len(new_docs)

    logger.info("FR poll: %d total, %d new, %d already seen",
                len(documents), len(new_docs), skipped)

    # Classify and stage
    counts = {"new": 0, "skipped_existing": skipped,
              "tier_1": 0, "tier_2": 0, "tier_3": 0, "errors": 0}
    for doc in new_docs:
        try:
            cfr_refs = doc.get("cfr_references", []) or []
            tier = classify_tier(doc.get("type", ""), doc.get("action"),
                                 cfr_refs, promote_cfr_parts)

            # Fetch full text for Tier 1 and 2
            full_text = None
            if tier <= 2:
                full_text = await fetch_full_text(doc)

            stage_document(db, doc, tier, full_text)

            counts["new"] += 1
            counts[f"tier_{tier}"] += 1
            logger.info("Staged %s [Tier %d]: %s",
                        doc.get("document_number"), tier,
                        doc.get("title", "")[:60])
        except Exception as e:
            logger.error("Failed to stage %s: %s", doc.get("document_number"), e)
            counts["errors"] += 1

    update_sync_state(db, counts["new"])
    logger.info("FR watcher complete: %s", counts)
    return counts
