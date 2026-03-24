"""Tracker context fetching and tiering for extraction.

Fetches the full tracker context snapshot via HTTP, gathers tiering signals
from the AI database, and applies tiering rules to build the extraction context.
"""
import logging
import re

import httpx

from app.config import TRACKER_BASE_URL, TRACKER_USER, TRACKER_PASS

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════

async def _fetch_tracker_context() -> dict:
    """Fetch full tracker context snapshot from GET /tracker/ai-context.

    Returns the full untiered response. Raises on failure.
    """
    url = f"{TRACKER_BASE_URL}/ai-context"
    try:
        auth = (TRACKER_USER, TRACKER_PASS) if TRACKER_USER else None
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(url, auth=auth)
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPStatusError as e:
        raise RuntimeError(
            f"Tracker context fetch failed: HTTP {e.response.status_code}"
        ) from e
    except (httpx.ConnectError, httpx.TimeoutException) as e:
        raise RuntimeError(
            f"Tracker context fetch failed: {type(e).__name__}: {e}"
        ) from e


# ═══════════════════════════════════════════════════════════════════════════
# 3. Context tiering (H.1 rules)
# ═══════════════════════════════════════════════════════════════════════════

def _gather_tiering_signals(db, communication_id: str) -> dict:
    """Gather speaker/entity/identifier signals for tiering.

    Returns dict with speaker_person_ids, entity_person_ids,
    entity_org_ids, identifier_hits.
    """
    # Confirmed speaker tracker_person_ids
    speaker_rows = db.execute("""
        SELECT tracker_person_id FROM communication_participants
        WHERE communication_id = ? AND tracker_person_id IS NOT NULL
    """, (communication_id,)).fetchall()
    speaker_person_ids = {r["tracker_person_id"] for r in speaker_rows}

    # Confirmed entity tracker IDs (confirmed=1 or confirmed=0, not -1)
    entity_rows = db.execute("""
        SELECT tracker_person_id, tracker_org_id
        FROM communication_entities
        WHERE communication_id = ? AND confirmed != -1
    """, (communication_id,)).fetchall()
    entity_person_ids = {
        r["tracker_person_id"] for r in entity_rows
        if r["tracker_person_id"]
    }
    entity_org_ids = {
        r["tracker_org_id"] for r in entity_rows
        if r["tracker_org_id"]
    }

    # Identifier hits from enrichment topics and entities
    # (RIN, docket numbers, CFR citations mentioned in conversation)
    identifier_hits = {"rin": set(), "docket": set(), "cfr": set()}
    topic_row = db.execute(
        "SELECT topic_segments_json FROM communications WHERE id = ?",
        (communication_id,),
    ).fetchone()
    if topic_row and topic_row["topic_segments_json"]:
        try:
            topic_data = json.loads(topic_row["topic_segments_json"])
            # Scan topic descriptions and entity mentions for identifiers
            _scan_for_identifiers(
                json.dumps(topic_data, default=str), identifier_hits
            )
        except (json.JSONDecodeError, TypeError):
            pass

    # Also scan entity mention_text and context_snippet
    mention_rows = db.execute("""
        SELECT mention_text, context_snippet FROM communication_entities
        WHERE communication_id = ? AND confirmed != -1
    """, (communication_id,)).fetchall()
    for mr in mention_rows:
        text = (mr["mention_text"] or "") + " " + (mr["context_snippet"] or "")
        _scan_for_identifiers(text, identifier_hits)

    return {
        "speaker_person_ids": speaker_person_ids,
        "entity_person_ids": entity_person_ids,
        "entity_org_ids": entity_org_ids,
        "identifier_hits": identifier_hits,
    }


def _scan_for_identifiers(text: str, hits: dict):
    """Scan text for RIN (XXXX-XXXX), docket numbers, and CFR citations."""
    # RIN pattern: 4 digits, dash, 2-4 alphanum
    for m in re.finditer(r'\b(\d{4}-[A-Z0-9]{2,4})\b', text):
        hits["rin"].add(m.group(1))
    # Docket pattern
    for m in re.finditer(r'(?i)\bdocket\s*(?:no\.?\s*)?([A-Z0-9-]+)', text):
        hits["docket"].add(m.group(1))
    # CFR pattern: number CFR number
    for m in re.finditer(r'\b(\d+\s*CFR\s*(?:Part\s*)?\d+(?:\.\d+)?)\b', text, re.IGNORECASE):
        hits["cfr"].add(m.group(1))


def _tier_context(full_context: dict, signals: dict) -> dict:
    """Build tiered context from full tracker snapshot and tiering signals.

    Returns a dict with tier_1_matters, tier_2_matters, tier_1_meetings,
    people, organizations, standalone_tasks, and tier_stats.
    """
    sp_ids = signals["speaker_person_ids"]
    ep_ids = signals["entity_person_ids"]
    eo_ids = signals["entity_org_ids"]
    id_hits = signals["identifier_hits"]

    all_person_ids = sp_ids | ep_ids

    matters = full_context.get("matters", [])
    tier_1_matters = []
    tier_1_matter_ids = set()
    tier_2_matters = []

    for m in matters:
        is_tier_1 = False
        mid = m.get("id", "")

        # Speaker/entity is matter owner, supervisor, or next_step owner
        for field in ("assigned_to_person_id", "supervisor_person_id",
                      "next_step_assigned_to_person_id"):
            if m.get(field) in all_person_ids and m.get(field):
                is_tier_1 = True
                break

        # Speaker/entity is matter stakeholder
        if not is_tier_1:
            for stk in m.get("stakeholders", []):
                # stakeholder data from ai-context uses full_name, we need
                # to check by person_id in the matter_people join
                if stk.get("person_id") in all_person_ids and stk.get("person_id"):
                    is_tier_1 = True
                    break

        # Linked entity org is one of the matter's org roles
        if not is_tier_1 and eo_ids:
            for org_field in ("requesting_organization_id",
                              "client_organization_id",
                              "reviewing_organization_id",
                              "lead_external_org_id"):
                if m.get(org_field) in eo_ids:
                    is_tier_1 = True
                    break

        # Linked entity org in matter's organizations list
        if not is_tier_1 and eo_ids:
            for org in m.get("organizations", []):
                # org data from ai-context doesn't include organization_id
                # directly — it has 'name' and 'organization_role'
                if org.get("organization_id") in eo_ids and org.get("organization_id"):
                    is_tier_1 = True
                    break

        # RIN match
        if not is_tier_1 and id_hits["rin"]:
            if m.get("rin") and m["rin"] in id_hits["rin"]:
                is_tier_1 = True

        # Docket match
        if not is_tier_1 and id_hits["docket"]:
            if m.get("docket_number") and m["docket_number"] in id_hits["docket"]:
                is_tier_1 = True

        # CFR match (partial — check if matter's cfr_citation contains any hit)
        if not is_tier_1 and id_hits["cfr"]:
            m_cfr = (m.get("cfr_citation") or "").lower()
            for cfr_hit in id_hits["cfr"]:
                if cfr_hit.lower() in m_cfr or m_cfr in cfr_hit.lower():
                    is_tier_1 = True
                    break

        if is_tier_1:
            tier_1_matters.append(m)
            tier_1_matter_ids.add(mid)
        else:
            # Build compact Tier 2 summary
            deadlines = [
                m.get(d) for d in
                ("work_deadline", "decision_deadline", "external_deadline")
                if m.get(d)
            ]
            nearest = min(deadlines) if deadlines else None
            tier_2_matters.append({
                "id": mid,
                "title": m.get("title", ""),
                "matter_type": m.get("matter_type", ""),
                "status": m.get("status", ""),
                "priority": m.get("priority", ""),
                "owner_name": m.get("owner_name", ""),
                "rin": m.get("rin"),
                "docket_number": m.get("docket_number"),
                "nearest_deadline": nearest,
                "tags": m.get("tags", []),
            })

    # Tier 1 meetings: involving speakers or linked to Tier 1 matters
    meetings = full_context.get("recent_meetings", [])
    tier_1_meetings = []
    for mtg in meetings:
        participants = mtg.get("participants", [])
        # We can't directly match person_ids from the meeting data since
        # ai-context returns full_name and meeting_role, not person_id
        # But meeting_matters gives us matter links
        matter_links = mtg.get("matter_links", [])
        if any(ml.get("matter_id") in tier_1_matter_ids for ml in matter_links):
            tier_1_meetings.append(mtg)
        # If we have speaker names, do a name match as best-effort
        # (person_ids aren't in the meeting participant data from ai-context)

    # People and orgs: always Tier 3 (full registry, already compact)
    people = full_context.get("people", [])
    orgs = full_context.get("organizations", [])
    standalone_tasks = full_context.get("standalone_tasks", [])

    tier_stats = {
        "tier_1_matter_count": len(tier_1_matters),
        "tier_2_matter_count": len(tier_2_matters),
        "tier_1_meeting_count": len(tier_1_meetings),
        "people_count": len(people),
        "org_count": len(orgs),
    }

    if len(tier_1_matters) > 30:
        logger.warning(
            "Tier 1 has %d matters (>30) — keeping all, conversation "
            "involves many connected workstreams",
            len(tier_1_matters),
        )

    return {
        "tier_1_matters": tier_1_matters,
        "tier_2_matters": tier_2_matters,
        "tier_1_meetings": tier_1_meetings,
        "people": people,
        "organizations": orgs,
        "standalone_tasks": standalone_tasks,
        "tier_stats": tier_stats,
    }
