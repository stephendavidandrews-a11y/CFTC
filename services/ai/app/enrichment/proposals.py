"""Turn Hunter results into reviewable proposals, and decide what may auto-accept.

The auto-accept rule is the safety-critical part of this feature. A wrong email
on a Hill staffer is a real-world embarrassment, so the bar is deliberately high
and one case is absolute: an existing non-empty email is NEVER overwritten
automatically, whatever the confidence score.
"""

import json
import logging

logger = logging.getLogger(__name__)

REVIEW_PENDING = "pending"
REVIEW_AUTO_ACCEPTED = "auto_accepted"
REVIEW_ACCEPTED = "accepted"
REVIEW_REJECTED = "rejected"
REVIEW_EDITED = "edited"
REVIEW_COMMITTED = "committed"
REVIEW_SKIPPED = "skipped"

WRITE_CREATE = "create"
WRITE_UPDATE = "update"
WRITE_NONE = "none"

# Verification verdicts we refuse to auto-accept.
BAD_VERIFICATION = {"undeliverable", "risky", "unknown"}

# Fields the enrichment feature is allowed to write on an existing person. It
# deliberately cannot touch relationship data, matter links, or notes.
UPDATABLE_PERSON_FIELDS = (
    "email",
    "title",
    "linkedin_url",
    "email_verification_status",
    "email_verified_at",
    "email_confidence",
    "organization_id",
)


def build_proposal(
    row: dict,
    person: dict | None,
    job: dict,
    now_iso: str,
) -> tuple[dict, str]:
    """Build the person payload this row would write, plus the write action.

    `row` is an enrichment_rows record (already enriched). `person` is the matched
    tracker person, or None for a new contact.

    Returns (proposed_data, write_action). proposed_data for an update contains
    only the fields that would actually change.
    """
    email = row.get("hunter_email") or row.get("email_raw") or ""
    score = row.get("hunter_score")
    verification = row.get("hunter_verification")
    title = row.get("hunter_position") or row.get("title_raw") or ""
    linkedin = row.get("hunter_linkedin_url") or row.get("linkedin_url_raw") or ""

    if person is None:
        payload = {
            "full_name": row.get("full_name") or "",
            "first_name": row.get("first_name") or "",
            "last_name": row.get("last_name") or "",
            "source": "hunter",
            "source_id": f"{job['id']}:{row['row_number']}",
        }
        if email:
            payload["email"] = email
            payload["email_confidence"] = score
            payload["email_verification_status"] = verification
            payload["email_verified_at"] = now_iso
        if title:
            payload["title"] = title
        if linkedin:
            payload["linkedin_url"] = linkedin
        if row.get("resolved_organization_id"):
            payload["organization_id"] = row["resolved_organization_id"]
        return payload, WRITE_CREATE

    # Update: only fields that would actually change, and only empty ones for
    # anything the operator may have curated by hand.
    changes: dict = {}
    existing_email = (person.get("email") or "").strip()
    if email and email.lower() != existing_email.lower():
        changes["email"] = email
        changes["email_confidence"] = score
        changes["email_verification_status"] = verification
        changes["email_verified_at"] = now_iso
    elif email and email.lower() == existing_email.lower():
        # Same address, but now we have a verification verdict worth recording.
        if verification and verification != person.get("email_verification_status"):
            changes["email_verification_status"] = verification
            changes["email_verified_at"] = now_iso
            changes["email_confidence"] = score

    if title and not (person.get("title") or "").strip():
        changes["title"] = title
    if linkedin and not (person.get("linkedin_url") or "").strip():
        changes["linkedin_url"] = linkedin
    if row.get("resolved_organization_id") and not person.get("organization_id"):
        changes["organization_id"] = row["resolved_organization_id"]

    return changes, (WRITE_UPDATE if changes else WRITE_NONE)


def is_email_overwrite(proposed: dict, person: dict | None) -> bool:
    """True when this proposal would replace an existing, different email."""
    if not person:
        return False
    if "email" not in proposed:
        return False
    existing = (person.get("email") or "").strip()
    if not existing:
        return False
    return existing.lower() != (proposed.get("email") or "").strip().lower()


def only_fills_empty_fields(proposed: dict, person: dict | None) -> bool:
    """True when every proposed field is currently empty on the person."""
    if not person:
        return True
    for key in proposed:
        if key in ("email_confidence", "email_verification_status", "email_verified_at"):
            # Metadata about the email, not user-authored content.
            continue
        if (person.get(key) or "") not in ("", None):
            return False
    return True


def decide_review_status(
    row: dict,
    proposed: dict,
    write_action: str,
    person: dict | None,
    policy: dict,
) -> tuple[str, str]:
    """Apply the auto-accept rule.

    Returns (review_status, reason). Only REVIEW_AUTO_ACCEPTED rows are eligible
    for the one-click bulk accept; everything else waits for a human.

    A row auto-accepts only when ALL of these hold:
      - Hunter's score is at or above auto_accept_score
      - the verification verdict is not undeliverable, risky, or unknown
      - it is a create, or an update that only fills previously-empty fields
      - it would not overwrite an existing non-empty email
      - the person match is unambiguous
    """
    enrich = policy.get("enrichment_policy", {})
    threshold = enrich.get("auto_accept_score", 90)
    reject_below = enrich.get("reject_below_score", 50)
    allow_risky = enrich.get("allow_risky_emails", False)

    if write_action == WRITE_NONE:
        return REVIEW_SKIPPED, "nothing_to_write"

    hunter_status = row.get("hunter_status")
    if hunter_status == "not_found":
        return REVIEW_PENDING, "not_found"
    if hunter_status == "error":
        return REVIEW_PENDING, "lookup_error"
    if hunter_status == "skipped":
        return REVIEW_PENDING, "skipped_lookup"

    score = row.get("hunter_score")
    verification = (row.get("hunter_verification") or "").lower()

    # An overwrite of a curated email is never automatic, at any score.
    if is_email_overwrite(proposed, person):
        return REVIEW_PENDING, "would_overwrite_existing_email"

    if row.get("match_ambiguous"):
        return REVIEW_PENDING, "ambiguous_person_match"

    if verification == "undeliverable":
        return REVIEW_PENDING, "undeliverable"
    if verification in BAD_VERIFICATION and not allow_risky:
        return REVIEW_PENDING, f"verification_{verification or 'missing'}"

    if score is None:
        return REVIEW_PENDING, "no_score"
    if score < reject_below:
        return REVIEW_PENDING, "below_reject_threshold"
    if score < threshold:
        return REVIEW_PENDING, "below_auto_accept_threshold"

    if write_action == WRITE_UPDATE and not only_fills_empty_fields(proposed, person):
        return REVIEW_PENDING, "would_change_existing_values"

    return REVIEW_AUTO_ACCEPTED, "meets_auto_accept_criteria"


def to_batch_operations(
    rows: list[dict],
    people_by_id: dict,
    job: dict,
    propose_org_domains: bool = False,
    org_domain_updates: dict | None = None,
) -> tuple[list[dict], list[dict]]:
    """Build tracker /batch operations for accepted rows.

    Returns (operations, row_plan) where row_plan[i] describes which row produced
    operation i, so writebacks can be recorded against the right row.
    """
    operations: list[dict] = []
    plan: list[dict] = []

    for row in rows:
        payload = _effective_payload(row)
        if not payload:
            continue
        action = row.get("write_action")

        if action == WRITE_CREATE:
            operations.append(
                {
                    "table": "people",
                    "op": "insert",
                    "data": payload,
                    "client_id": f"row_{row['row_number']}",
                }
            )
            plan.append({"row_id": row["id"], "table": "people", "write_type": "create"})
        elif action == WRITE_UPDATE and row.get("matched_person_id"):
            operations.append(
                {
                    "table": "people",
                    "op": "update",
                    "record_id": row["matched_person_id"],
                    "data": payload,
                }
            )
            plan.append(
                {
                    "row_id": row["id"],
                    "table": "people",
                    "write_type": "update",
                    "record_id": row["matched_person_id"],
                }
            )

    # Teach organizations their domain, so the next import is cheaper.
    if propose_org_domains and org_domain_updates:
        for org_id, domain in sorted(org_domain_updates.items()):
            operations.append(
                {
                    "table": "organizations",
                    "op": "update",
                    "record_id": org_id,
                    "data": {"primary_domain": domain},
                }
            )
            plan.append(
                {
                    "row_id": None,
                    "table": "organizations",
                    "write_type": "update",
                    "record_id": org_id,
                }
            )

    return operations, plan


def _effective_payload(row: dict) -> dict:
    """The payload to write: operator edits override the generated proposal."""
    for key in ("edited_data", "proposed_data"):
        raw = row.get(key)
        if raw:
            try:
                data = json.loads(raw) if isinstance(raw, str) else raw
            except (TypeError, json.JSONDecodeError):
                continue
            if data:
                return data
    return {}
