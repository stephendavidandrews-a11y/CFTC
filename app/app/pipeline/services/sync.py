"""
Rulemaking pipeline sync service.

Pulls active CFTC rulemakings from:
  1. Unified Regulatory Agenda (reginfo.gov) — XML bulk download, agency 3038
  2. Federal Register API (federalregister.gov) — PRORULE + RULE documents

Merges by RIN, creates/updates pipeline_items, logs FR documents,
creates deadline entries, and flags EO 14192 discrepancies.

Designed to run daily via background task.
"""

import json
import logging
import re
import xml.etree.ElementTree as ET
from datetime import datetime, date, timedelta
from typing import Optional

import httpx

from app.pipeline.connection import get_connection

logger = logging.getLogger(__name__)

# ─── Constants ───

CFTC_AGENCY_CODE = "3038"
CFTC_FR_SLUG = "commodity-futures-trading-commission"

FR_API_BASE = "https://www.federalregister.gov/api/v1"
UA_XML_URL = "https://www.reginfo.gov/public/do/XMLViewFileAction?f=REGINFO_RIN_DATA_202504.xml"

FR_FIELDS = [
    "title", "type", "action", "document_number", "publication_date",
    "regulation_id_numbers", "docket_ids", "comments_close_on",
    "effective_on", "abstract", "html_url", "pdf_url",
    "citation", "volume", "start_page",
]

# Map Unified Agenda stage → (item_type, default_stage)
UA_STAGE_MAP = {
    "Prerule Stage":      ("ANPRM", "concept"),
    "Proposed Rule Stage": ("NPRM", "drafting"),
    "Final Rule Stage":    ("final_rule", "final_drafting"),
    "Long-Term Actions":   ("NPRM", "concept"),
    "Completed Actions":   ("final_rule", "published"),
}

# Map FR action patterns → pipeline effects
# Order matters — first match wins. Withdrawal patterns must come before "final rule"
# because "withdrawal of Commission Guidance" has type=Rule.
FR_ACTION_MAP = [
    (r"advance notice of proposed rulemaking", "anprm"),
    (r"extension of comment period", "extension"),
    (r"reopening of comment period", "reopening"),
    (r"supplemental notice|further notice", "supplemental"),
    (r"withdrawal of proposed rule", "withdrawal"),
    (r"withdrawal of commission guidance", "withdrawal"),
    (r"withdrawal", "withdrawal"),
    (r"interim final rule", "ifr"),
    (r"direct final rule", "dfr"),
    (r"correcting amendment|correction", "correction"),
    (r"delay of effective date", "delay"),
    (r"final rule", "final"),
    (r"proposed rule|notice of proposed rulemaking", "nprm"),
    (r"petition for rulemaking", "petition"),
    (r"request for comment", "rfc"),
]


# ─── Unified Agenda Parser ───

def fetch_unified_agenda() -> list[dict]:
    """
    Download and parse the Unified Regulatory Agenda XML.
    Returns list of CFTC-only entries.
    """
    logger.info("Fetching Unified Regulatory Agenda XML...")
    try:
        with httpx.Client(timeout=120.0) as client:
            resp = client.get(UA_XML_URL)
            resp.raise_for_status()
    except Exception as e:
        logger.error(f"Failed to fetch UA XML: {e}")
        return []

    try:
        root = ET.fromstring(resp.content)
    except ET.ParseError as e:
        logger.error(f"Failed to parse UA XML: {e}")
        return []

    entries = []

    # XML structure: <REGINFO_RIN_DATA><RIN_INFO>...<AGENCY><CODE>3038</CODE>...
    for rin_info in root.iter('RIN_INFO'):
        # Check agency code
        agency_code_elem = rin_info.find('.//AGENCY/CODE')
        if agency_code_elem is None or not agency_code_elem.text:
            continue
        if agency_code_elem.text.strip() != CFTC_AGENCY_CODE:
            continue

        rin_elem = rin_info.find('RIN')
        if rin_elem is None or not rin_elem.text:
            continue

        rin = rin_elem.text.strip()
        entry = _parse_ua_entry(rin_info, rin)
        entries.append(entry)

    logger.info(f"Unified Agenda: found {len(entries)} CFTC entries")
    return entries


def _parse_ua_entry(elem, rin: str) -> dict:
    """Extract fields from a single UA XML entry."""
    def _text(tag):
        el = elem.find(f'.//{tag}')
        return el.text.strip() if el is not None and el.text else None

    # Parse timetable entries (XML uses TIMETABLE_LIST > TIMETABLE > TTBL_ACTION/TTBL_DATE)
    timetable = []
    for tt in elem.iter('TIMETABLE'):
        action = _text_in(tt, 'TTBL_ACTION')
        dt = _text_in(tt, 'TTBL_DATE')
        fr_cite = _text_in(tt, 'FR_CITATION')
        if action and dt:
            entry = {"action": action, "date": dt}
            if fr_cite:
                entry["fr_citation"] = fr_cite
            timetable.append(entry)

    # Get legal authorities (may be multiple)
    legal_authorities = []
    for la in elem.iter('LEGAL_AUTHORITY'):
        if la.text and la.text.strip():
            legal_authorities.append(la.text.strip())

    # Get CFR citations
    cfr_citations = []
    for cfr in elem.iter('CFR'):
        if cfr.text and cfr.text.strip():
            cfr_citations.append(cfr.text.strip())

    # Get contact info
    contact_parts = []
    first_name = _text('FIRST_NAME')
    last_name = _text('LAST_NAME')
    if first_name and last_name:
        contact_parts.append(f"{first_name} {last_name}")
    phone = _text('PHONE')
    if phone:
        contact_parts.append(phone)

    # Clean abstract (may contain HTML/CDATA)
    abstract_raw = _text('ABSTRACT') or ""
    # Strip HTML tags from abstract
    abstract = re.sub(r'<[^>]+>', '', abstract_raw).strip()
    # Clean up HTML entities
    abstract = abstract.replace('&nbsp;', ' ').replace('&amp;', '&')

    return {
        "rin": rin,
        "title": _text('RULE_TITLE') or "Unknown",
        "abstract": abstract,
        "priority": _text('PRIORITY_CATEGORY'),
        "stage": _text('RULE_STAGE'),
        "legal_authority": "; ".join(legal_authorities) if legal_authorities else None,
        "cfr_citation": "; ".join(cfr_citations) if cfr_citations else None,
        "timetable": timetable,
        "contact": "; ".join(contact_parts) if contact_parts else None,
        "major_rule": _text('MAJOR') == 'Yes',
        "eo_14192": _text('EO_13771_DESIGNATION'),
    }


def _text_in(elem, tag):
    """Get text from a child element."""
    el = elem.find(f'.//{tag}')
    return el.text.strip() if el is not None and el.text else None


# ─── Federal Register API ───

def fetch_federal_register(since_date: Optional[str] = None) -> list[dict]:
    """
    Query the Federal Register API for CFTC rulemaking documents.

    Args:
        since_date: ISO date string (YYYY-MM-DD). If None, fetches last 3 years.

    Returns:
        List of FR document dicts.
    """
    if not since_date:
        since_date = (date.today() - timedelta(days=365 * 3)).isoformat()

    all_docs = []

    for doc_type in ["PRORULE", "RULE"]:
        page = 1
        while True:
            params = {
                "conditions[agencies][]": CFTC_FR_SLUG,
                "conditions[type][]": doc_type,
                "conditions[publication_date][gte]": since_date,
                "fields[]": FR_FIELDS,
                "per_page": 100,
                "page": page,
                "order": "newest",
            }

            try:
                with httpx.Client(timeout=30.0) as client:
                    resp = client.get(f"{FR_API_BASE}/documents.json", params=params)
                    resp.raise_for_status()
                    data = resp.json()
            except Exception as e:
                logger.error(f"FR API error (type={doc_type}, page={page}): {e}")
                break

            results = data.get("results", [])
            if not results:
                break

            all_docs.extend(results)
            logger.info(f"FR API: fetched page {page} for {doc_type} ({len(results)} docs)")

            # Check if there are more pages
            total_pages = data.get("total_pages", 1)
            if page >= total_pages:
                break
            page += 1

    logger.info(f"Federal Register: fetched {len(all_docs)} CFTC documents")
    return all_docs


def _extract_rin(doc: dict) -> Optional[str]:
    """Extract RIN from an FR document."""
    rin_info = doc.get("regulation_id_numbers") or []
    for rin in rin_info:
        if isinstance(rin, str) and rin.startswith(CFTC_AGENCY_CODE):
            return rin
        if isinstance(rin, dict):
            rin_str = rin.get("regulation_id_number", "")
            if rin_str.startswith(CFTC_AGENCY_CODE):
                return rin_str
    return None


def _classify_fr_action(action: str) -> str:
    """Classify an FR document's action field into a lifecycle event type."""
    if not action:
        return "other"
    action_lower = action.lower()
    for pattern, event_type in FR_ACTION_MAP:
        if re.search(pattern, action_lower):
            return event_type
    return "other"


# ─── Sync Logic ───

def run_sync(incremental_since: Optional[str] = None) -> dict:
    """
    Main sync function. Pulls from both sources, merges, and updates pipeline.

    Args:
        incremental_since: ISO date for incremental FR sync. None = full sync.

    Returns:
        Summary dict with counts.
    """
    stats = {
        "unified_agenda_count": 0,
        "federal_register_count": 0,
        "created": 0,
        "updated": 0,
        "events_logged": 0,
        "deadlines_created": 0,
        "discrepancies": 0,
        "errors": [],
    }

    # 1. Fetch from both sources
    ua_entries = fetch_unified_agenda()
    fr_docs = fetch_federal_register(incremental_since)

    stats["unified_agenda_count"] = len(ua_entries)
    stats["federal_register_count"] = len(fr_docs)

    # 2. Index UA entries by RIN
    ua_by_rin = {}
    for entry in ua_entries:
        ua_by_rin[entry["rin"]] = entry

    # 3. Group FR docs by RIN
    fr_by_rin = {}
    fr_no_rin = []
    for doc in fr_docs:
        rin = _extract_rin(doc)
        if rin:
            fr_by_rin.setdefault(rin, []).append(doc)
        else:
            fr_no_rin.append(doc)

    # 4. Merge: all RINs from both sources
    all_rins = set(ua_by_rin.keys()) | set(fr_by_rin.keys())

    conn = get_connection()
    try:
        for rin in all_rins:
            ua_entry = ua_by_rin.get(rin)
            fr_docs_for_rin = fr_by_rin.get(rin, [])

            on_ua = ua_entry is not None
            on_fr = len(fr_docs_for_rin) > 0

            # Flag discrepancies
            if on_fr and not on_ua:
                stats["discrepancies"] += 1

            try:
                result = _sync_single_rin(
                    conn, rin, ua_entry, fr_docs_for_rin, on_ua, on_fr
                )
                stats["created"] += result.get("created", 0)
                stats["updated"] += result.get("updated", 0)
                stats["events_logged"] += result.get("events_logged", 0)
                stats["deadlines_created"] += result.get("deadlines_created", 0)
            except Exception as e:
                logger.error(f"Error syncing RIN {rin}: {e}")
                stats["errors"].append(f"RIN {rin}: {str(e)}")

        # Log the sync in notifications (decision_log requires item_id NOT NULL)
        conn.execute(
            """INSERT INTO pipeline_notifications
               (notification_type, title, message, severity)
               VALUES ('system_sync', 'Rulemaking sync completed', ?, 'info')""",
            (json.dumps({k: v for k, v in stats.items() if k != "errors"}),),
        )
        conn.commit()

    finally:
        conn.close()

    logger.info(
        f"Sync complete: {stats['created']} created, {stats['updated']} updated, "
        f"{stats['events_logged']} events, {stats['deadlines_created']} deadlines, "
        f"{stats['discrepancies']} discrepancies"
    )
    return stats


def _sync_single_rin(
    conn, rin: str, ua_entry: Optional[dict],
    fr_docs: list[dict], on_ua: bool, on_fr: bool,
) -> dict:
    """Sync a single RIN number."""
    result = {"created": 0, "updated": 0, "events_logged": 0, "deadlines_created": 0}

    # Check if item already exists
    existing = conn.execute(
        "SELECT id, current_stage, item_type, status FROM pipeline_items WHERE rin = ?",
        (rin,),
    ).fetchone()

    if existing:
        item_id = existing["id"]
        result["updated"] += 1
        _update_existing_item(conn, item_id, existing, ua_entry, fr_docs, on_ua, on_fr)
    else:
        item_id = _create_new_item(conn, rin, ua_entry, fr_docs, on_ua, on_fr)
        result["created"] += 1

    # Log FR documents as events
    result["events_logged"] += _log_fr_events(conn, item_id, fr_docs)

    # Create/update deadlines
    result["deadlines_created"] += _sync_deadlines(conn, item_id, ua_entry, fr_docs)

    # Update unified agenda metadata
    if ua_entry:
        _update_ua_metadata(conn, item_id, ua_entry)

    return result


def _determine_item_type(ua_entry: Optional[dict], fr_docs: list[dict]) -> str:
    """Determine pipeline item_type from available data."""
    if ua_entry and ua_entry.get("stage"):
        stage = ua_entry["stage"]
        for key, (item_type, _) in UA_STAGE_MAP.items():
            if key.lower() in stage.lower():
                return item_type

    # Check FR docs for type hints
    for doc in sorted(fr_docs, key=lambda d: d.get("publication_date", ""), reverse=True):
        action = _classify_fr_action(doc.get("action", ""))
        if action == "anprm":
            return "ANPRM"
        if action in ("nprm", "extension", "reopening", "supplemental"):
            return "NPRM"
        if action in ("final", "ifr", "dfr"):
            return "final_rule"

    return "NPRM"  # Default


def _determine_status(
    ua_entry: Optional[dict], fr_docs: list[dict],
) -> str:
    """
    Determine the correct status for a pipeline item.

    Returns one of: 'active', 'withdrawn', 'completed'.
    Examines FR documents (newest first) and UA stage to decide.
    """
    sorted_docs = sorted(
        fr_docs, key=lambda d: d.get("publication_date", ""), reverse=True
    )

    # Walk through FR docs newest-first.
    # The first conclusive action we find determines status.
    for doc in sorted_docs:
        action = _classify_fr_action(doc.get("action", ""))
        if action == "withdrawal":
            return "withdrawn"
        if action in ("final", "ifr", "dfr"):
            return "completed"
        # Corrections/delays after a final rule don't change status,
        # but other actions (nprm, extension) mean it's still active
        if action in ("correction", "delay"):
            continue  # keep looking for the underlying final/withdrawal
        if action in ("nprm", "anprm", "extension", "reopening", "supplemental", "rfc"):
            return "active"

    # No FR docs or only non-conclusive ones — check UA
    if ua_entry and ua_entry.get("stage"):
        if "Completed" in ua_entry["stage"]:
            return "completed"

    return "active"


def _determine_stage(
    ua_entry: Optional[dict], fr_docs: list[dict], item_type: str,
) -> Optional[str]:
    """
    Determine the current pipeline stage from available data.

    Returns None for withdrawals — the caller should NOT change the stage;
    the status field handles withdrawn items instead.
    """
    sorted_docs = sorted(
        fr_docs, key=lambda d: d.get("publication_date", ""), reverse=True
    )

    # Walk FR docs newest-first to find the most recent conclusive action
    if sorted_docs:
        for doc in sorted_docs:
            action = _classify_fr_action(doc.get("action", ""))

            # Withdrawal → don't change stage (status field handles this)
            if action == "withdrawal":
                return None

            # Final/IFR/DFR → published
            if action in ("final", "ifr", "dfr"):
                return "published"

            # Corrections/delays are not stage-changing — keep looking
            if action in ("correction", "delay"):
                continue

            # Active proposed rule — check comment period dates
            if action in ("nprm", "anprm", "extension", "reopening",
                          "supplemental", "rfc"):
                close_date = doc.get("comments_close_on")
                if close_date:
                    try:
                        close = datetime.strptime(close_date, "%Y-%m-%d").date()
                        return "comment_period" if close > date.today() else "comment_analysis"
                    except ValueError:
                        pass
                return "comment_period"

    # Fall back to UA stage
    if ua_entry and ua_entry.get("stage"):
        stage = ua_entry["stage"]
        if "Completed" in stage:
            return "published"
        for key, (_, default_stage) in UA_STAGE_MAP.items():
            if key.lower() in stage.lower():
                return default_stage

    # Check item_type for fallback
    if item_type == "final_rule":
        return "final_drafting" if not sorted_docs else "published"

    return "concept"


def _create_new_item(
    conn, rin: str, ua_entry: Optional[dict],
    fr_docs: list[dict], on_ua: bool, on_fr: bool,
) -> int:
    """Create a new pipeline item from sync data."""
    item_type = _determine_item_type(ua_entry, fr_docs)
    stage = _determine_stage(ua_entry, fr_docs, item_type)
    status = _determine_status(ua_entry, fr_docs)

    # If stage is None (withdrawal), default to "concept" for new items
    if stage is None:
        stage = "concept"

    # Get title (prefer UA)
    title = "Unknown Rule"
    if ua_entry:
        title = ua_entry.get("title") or title
    elif fr_docs:
        title = fr_docs[0].get("title") or title

    # Get description/abstract
    description = ""
    if ua_entry:
        description = ua_entry.get("abstract") or ""
    elif fr_docs:
        description = fr_docs[0].get("abstract") or ""

    # Get docket number, FR citation, and URL from FR docs (prefer most recent)
    docket_number = None
    fr_citation = None
    fr_doc_number = None
    sorted_fr = sorted(fr_docs, key=lambda d: d.get("publication_date", ""), reverse=True)
    for doc in sorted_fr:
        dockets = doc.get("docket_ids") or []
        if dockets and not docket_number:
            docket_number = dockets[0] if isinstance(dockets[0], str) else str(dockets[0])
        if doc.get("document_number") and not fr_doc_number:
            fr_doc_number = doc["document_number"]
        if doc.get("citation") and not fr_citation:
            fr_citation = doc["citation"]

    # Determine priority label
    priority_label = "medium"
    if ua_entry and ua_entry.get("priority"):
        p = ua_entry["priority"].lower()
        if "econom" in p or "significant" in p:
            priority_label = "high"
        elif "routine" in p or "info" in p:
            priority_label = "low"

    # Build source notes for description
    source_notes = []
    if on_ua:
        source_notes.append("Source: Unified Agenda")
    else:
        source_notes.append("WARNING: Not on Unified Agenda (potential EO 14192 issue)")
    if on_fr:
        source_notes.append("Source: Federal Register")
    else:
        source_notes.append("Note: Not yet published in Federal Register")

    full_desc = description
    if source_notes:
        full_desc += "\n\n---\n" + "\n".join(source_notes)

    # Validate stage exists in templates, fall back to first stage
    stage_exists = conn.execute(
        "SELECT 1 FROM stage_templates WHERE module = 'rulemaking' AND item_type = ? AND stage_key = ?",
        (item_type, stage),
    ).fetchone()

    if not stage_exists:
        # Fall back to first stage for this item type
        first = conn.execute(
            "SELECT stage_key FROM stage_templates WHERE module = 'rulemaking' AND item_type = ? ORDER BY stage_order ASC LIMIT 1",
            (item_type,),
        ).fetchone()
        if first:
            stage = first["stage_key"]
        else:
            logger.warning(f"No stage templates for item_type={item_type}, using 'concept'")
            stage = "concept"

    cursor = conn.execute(
        """INSERT INTO pipeline_items
           (module, item_type, title, description, docket_number,
            rin, fr_citation, fr_doc_number,
            current_stage, stage_entered_at,
            unified_agenda_rin, unified_agenda_stage,
            priority_label, status, created_by)
           VALUES ('rulemaking', ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'),
                   ?, ?, ?, ?, 'sync_service')""",
        (
            item_type, title, full_desc, docket_number,
            rin, fr_citation, fr_doc_number,
            stage,
            rin if on_ua else None,
            ua_entry.get("stage") if ua_entry else None,
            priority_label,
            status,
        ),
    )
    item_id = cursor.lastrowid

    # Log creation
    conn.execute(
        """INSERT INTO pipeline_decision_log
           (item_id, action_type, description, new_value, decided_by)
           VALUES (?, 'status_change', 'Created by rulemaking sync', ?, 'sync_service')""",
        (item_id, status),
    )

    conn.commit()
    return item_id


def _update_existing_item(
    conn, item_id: int, existing, ua_entry: Optional[dict],
    fr_docs: list[dict], on_ua: bool, on_fr: bool,
):
    """Update an existing pipeline item with fresh sync data."""
    updates = {}
    current_stage = existing["current_stage"]
    item_type = existing["item_type"]

    # Update title from UA if available
    if ua_entry and ua_entry.get("title"):
        updates["title"] = ua_entry["title"]

    # Update description/abstract
    if ua_entry and ua_entry.get("abstract"):
        updates["description"] = ua_entry["abstract"]

    # Update UA fields
    if ua_entry:
        updates["unified_agenda_rin"] = ua_entry["rin"]
        updates["unified_agenda_stage"] = ua_entry.get("stage")

    # Update docket/FR info from latest FR doc
    if fr_docs:
        latest = sorted(fr_docs, key=lambda d: d.get("publication_date", ""), reverse=True)[0]
        dockets = latest.get("docket_ids") or []
        if dockets:
            updates["docket_number"] = dockets[0] if isinstance(dockets[0], str) else str(dockets[0])
        if latest.get("document_number"):
            updates["fr_doc_number"] = latest["document_number"]
        if latest.get("citation"):
            updates["fr_citation"] = latest["citation"]

    # Determine correct status
    new_status = _determine_status(ua_entry, fr_docs)
    if new_status != existing["status"]:
        updates["status"] = new_status
        conn.execute(
            """INSERT INTO pipeline_decision_log
               (item_id, action_type, description, old_value, new_value, decided_by)
               VALUES (?, 'status_change', ?, ?, ?, 'sync_service')""",
            (item_id, f"Status changed to {new_status} by sync",
             existing["status"], new_status),
        )

    # Determine stage (returns None for withdrawals = don't change)
    new_stage = _determine_stage(ua_entry, fr_docs, item_type)
    if new_stage is not None and new_stage != current_stage:
        stage_order_current = _get_stage_order(conn, item_type, current_stage)
        stage_order_new = _get_stage_order(conn, item_type, new_stage)

        # Allow forward movement, or allow jump to "published" from any stage
        if stage_order_new is not None and (
            stage_order_new > (stage_order_current or 0)
            or new_stage == "published"
        ):
            updates["current_stage"] = new_stage
            updates["stage_entered_at"] = datetime.utcnow().isoformat()

            conn.execute(
                """INSERT INTO pipeline_decision_log
                   (item_id, action_type, description, old_value, new_value, decided_by)
                   VALUES (?, 'stage_change', 'Stage advanced by sync', ?, ?, 'sync_service')""",
                (item_id, current_stage, new_stage),
            )

    # Update priority from UA
    if ua_entry and ua_entry.get("priority"):
        p = ua_entry["priority"].lower()
        if "econom" in p or "significant" in p:
            updates["priority_label"] = "high"
        elif "routine" in p or "info" in p:
            updates["priority_label"] = "low"

    # Apply updates
    if updates:
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [item_id]
        conn.execute(
            f"UPDATE pipeline_items SET {set_clause}, updated_at = datetime('now') WHERE id = ?",
            values,
        )
        conn.commit()


def _get_stage_order(conn, item_type: str, stage_key: str) -> Optional[int]:
    """Get the stage_order number for a given stage_key."""
    row = conn.execute(
        "SELECT stage_order FROM stage_templates WHERE module = 'rulemaking' AND item_type = ? AND stage_key = ?",
        (item_type, stage_key),
    ).fetchone()
    return row["stage_order"] if row else None


def _log_fr_events(conn, item_id: int, fr_docs: list[dict]) -> int:
    """Log each FR document as a decision_log entry. Returns count."""
    count = 0
    for doc in fr_docs:
        doc_number = doc.get("document_number", "")

        # Check if already logged (dedup)
        existing = conn.execute(
            """SELECT 1 FROM pipeline_decision_log
               WHERE item_id = ? AND action_type = 'fr_publication'
               AND new_value LIKE ?""",
            (item_id, f"%{doc_number}%"),
        ).fetchone()

        if existing:
            continue

        action = doc.get("action", "Unknown action")
        pub_date = doc.get("publication_date", "Unknown date")
        title = doc.get("title", "")
        html_url = doc.get("html_url", "")

        citation = doc.get("citation", "")
        description = f"FR Publication: {action}"
        if citation:
            description += f" ({citation})"
        detail = json.dumps({
            "document_number": doc_number,
            "publication_date": pub_date,
            "title": title,
            "action": action,
            "html_url": html_url,
            "citation": citation,
            "type": doc.get("type"),
        })

        conn.execute(
            """INSERT INTO pipeline_decision_log
               (item_id, action_type, description, new_value, decided_by, created_at)
               VALUES (?, 'fr_publication', ?, ?, 'sync_service', ?)""",
            (item_id, description, detail, pub_date),
        )
        count += 1

    if count > 0:
        conn.commit()
    return count


def _sync_deadlines(
    conn, item_id: int, ua_entry: Optional[dict], fr_docs: list[dict],
) -> int:
    """Create/update deadline entries. Returns count of new deadlines."""
    count = 0

    # From FR documents: comment_close_on and effective_on
    for doc in fr_docs:
        close_date = doc.get("comments_close_on")
        if close_date:
            count += _upsert_deadline(
                conn, item_id,
                deadline_type="comment_period",
                title=f"Comment period closes — {doc.get('action', 'Rule')}",
                due_date=close_date,
                source="federal_register",
                source_detail=doc.get("document_number", ""),
                is_hard=True,
            )

        effective_date = doc.get("effective_on")
        if effective_date:
            count += _upsert_deadline(
                conn, item_id,
                deadline_type="effective_date",
                title=f"Rule effective date — {doc.get('action', 'Rule')}",
                due_date=effective_date,
                source="federal_register",
                source_detail=doc.get("document_number", ""),
                is_hard=True,
            )

    # From UA timetable: future action dates
    if ua_entry and ua_entry.get("timetable"):
        for tt in ua_entry["timetable"]:
            action = tt.get("action", "")
            dt_str = tt.get("date", "")
            if not dt_str:
                continue

            # Parse date — UA uses various formats
            parsed_date = _parse_ua_date(dt_str)
            if not parsed_date:
                continue

            # Only create deadlines for future dates
            if parsed_date <= date.today():
                continue

            # Determine deadline type from timetable action
            action_lower = action.lower()
            if "nprm" in action_lower or "proposed" in action_lower:
                dl_type = "nprm_target"
            elif "final" in action_lower:
                dl_type = "final_rule_target"
            elif "anprm" in action_lower or "advance" in action_lower:
                dl_type = "anprm_target"
            else:
                dl_type = "ua_target"

            count += _upsert_deadline(
                conn, item_id,
                deadline_type=dl_type,
                title=f"UA Target: {action}",
                due_date=parsed_date.isoformat(),
                source="unified_agenda",
                source_detail=ua_entry.get("rin", ""),
                is_hard=False,
            )

    return count


def _upsert_deadline(
    conn, item_id: int, deadline_type: str, title: str,
    due_date: str, source: str, source_detail: str, is_hard: bool,
) -> int:
    """Insert a deadline if it doesn't already exist. Returns 1 if created, 0 if exists."""
    existing = conn.execute(
        """SELECT id, due_date FROM pipeline_deadlines
           WHERE item_id = ? AND deadline_type = ? AND source_detail = ?""",
        (item_id, deadline_type, source_detail),
    ).fetchone()

    if existing:
        # Update if date changed (extension/delay)
        if existing["due_date"] != due_date:
            conn.execute(
                """UPDATE pipeline_deadlines
                   SET extended_to = ?, extension_reason = 'Updated by sync',
                       updated_at = datetime('now')
                   WHERE id = ?""",
                (due_date, existing["id"]),
            )
            # Also create new deadline with updated date
            conn.execute(
                """INSERT INTO pipeline_deadlines
                   (item_id, deadline_type, title, due_date, source, source_detail,
                    is_hard_deadline, status)
                   VALUES (?, ?, ?, ?, ?, ?, ?, 'pending')""",
                (item_id, deadline_type, title + " (updated)", due_date, source, source_detail, 1 if is_hard else 0),
            )
            conn.commit()
            return 1
        return 0

    # Check if this deadline is past due
    status = "pending"
    try:
        if datetime.strptime(due_date, "%Y-%m-%d").date() < date.today():
            status = "completed"
    except ValueError:
        pass

    conn.execute(
        """INSERT INTO pipeline_deadlines
           (item_id, deadline_type, title, due_date, source, source_detail,
            is_hard_deadline, status)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (item_id, deadline_type, title, due_date, source, source_detail, 1 if is_hard else 0, status),
    )
    conn.commit()
    return 1


def _parse_ua_date(dt_str: str) -> Optional[date]:
    """Parse a date string from the UA timetable (various formats).
    UA uses MM/DD/YYYY where DD=00 means month-only (e.g., '07/00/2025')."""
    s = dt_str.strip()

    # Handle MM/00/YYYY (month-only, set to 1st of month)
    m = re.match(r"(\d{2})/00/(\d{4})", s)
    if m:
        return date(int(m.group(2)), int(m.group(1)), 1)

    for fmt in ("%m/%d/%Y", "%m/%Y", "%Y-%m-%d", "%B %Y", "%b %Y"):
        try:
            d = datetime.strptime(s, fmt)
            return d.date()
        except ValueError:
            continue

    # Try extracting just month/year
    m = re.match(r"(\d{2})/(\d{4})", s)
    if m:
        return date(int(m.group(2)), int(m.group(1)), 1)
    return None


def _update_ua_metadata(conn, item_id: int, ua_entry: dict):
    """Update the pipeline_unified_agenda table with UA metadata."""
    existing = conn.execute(
        "SELECT id FROM pipeline_unified_agenda WHERE item_id = ?", (item_id,)
    ).fetchone()

    timetable_json = json.dumps(ua_entry.get("timetable", []))

    if existing:
        conn.execute(
            """UPDATE pipeline_unified_agenda
               SET rin = ?, agenda_stage = ?, priority_designation = ?,
                   abstract = ?, timetable = ?, legal_authority = ?,
                   last_unified_agenda_update = datetime('now'),
                   updated_at = datetime('now')
               WHERE item_id = ?""",
            (
                ua_entry["rin"], ua_entry.get("stage"), ua_entry.get("priority"),
                ua_entry.get("abstract"), timetable_json, ua_entry.get("legal_authority"),
                item_id,
            ),
        )
    else:
        conn.execute(
            """INSERT INTO pipeline_unified_agenda
               (item_id, rin, agenda_stage, priority_designation,
                abstract, timetable, legal_authority,
                last_unified_agenda_update, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))""",
            (
                item_id, ua_entry["rin"], ua_entry.get("stage"),
                ua_entry.get("priority"), ua_entry.get("abstract"),
                timetable_json, ua_entry.get("legal_authority"),
            ),
        )

    # Parse timetable for next_action
    timetable = ua_entry.get("timetable", [])
    future_actions = []
    for tt in timetable:
        d = _parse_ua_date(tt.get("date", ""))
        if d and d > date.today():
            future_actions.append((d, tt.get("action", "")))

    if future_actions:
        future_actions.sort()
        next_date, next_action = future_actions[0]
        conn.execute(
            """UPDATE pipeline_unified_agenda
               SET next_action = ?, next_action_date = ?
               WHERE item_id = ?""",
            (next_action, next_date.isoformat(), item_id),
        )

    conn.commit()
