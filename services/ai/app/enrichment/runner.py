"""Enrichment job orchestration.

Status flow:
    uploaded -> mapping -> ready -> running -> awaiting_review -> committing
                                       |
                                    paused (credit cap reached)

Crash-safe by construction: every row's progress lives in enrichment_rows, so a
restart resumes at the first row still marked pending. Credits already spent are
never re-spent, because the cache covers a repeat lookup.
"""

import asyncio
import json
import logging
import uuid
from datetime import datetime

import httpx

from app.config import (
    TRACKER_BASE_URL,
    TRACKER_PASS,
    TRACKER_USER,
    load_policy,
)
from app.enrichment import parsing
from app.enrichment.hunter_client import HunterAuthError, HunterClient
from app.enrichment.matching import (
    match_person,
    needs_lookup,
    resolve_domain,
    resolve_organization,
)
from app.enrichment.proposals import build_proposal, decide_review_status

logger = logging.getLogger(__name__)

STATUS_UPLOADED = "uploaded"
STATUS_MAPPING = "mapping"
STATUS_READY = "ready"
STATUS_RUNNING = "running"
STATUS_PAUSED = "paused"
STATUS_AWAITING_REVIEW = "awaiting_review"
STATUS_COMMITTING = "committing"
STATUS_COMPLETE = "complete"
STATUS_FAILED = "failed"
STATUS_CANCELLED = "cancelled"

HUNTER_PENDING = "pending"
HUNTER_FOUND = "found"
HUNTER_NOT_FOUND = "not_found"
HUNTER_ERROR = "error"
HUNTER_SKIPPED = "skipped"

# Jobs currently running in this process, so pause/cancel can signal them.
_cancel_flags: dict[str, bool] = {}


def request_stop(job_id: str):
    """Ask a running job to stop at the next row boundary."""
    _cancel_flags[job_id] = True


def clear_stop(job_id: str):
    _cancel_flags.pop(job_id, None)


def _stop_requested(job_id: str) -> bool:
    return _cancel_flags.get(job_id, False)


def _now() -> str:
    return datetime.now().isoformat()


# ---------------------------------------------------------------------------
# Tracker context
# ---------------------------------------------------------------------------


async def fetch_tracker_context() -> dict:
    """People and organizations, for matching. Returns {} when unreachable."""
    url = f"{TRACKER_BASE_URL}/ai-context"
    params = {
        "include_matters": "false",
        "include_people": "true",
        "include_organizations": "true",
        "include_recent_meetings": "false",
        "include_standalone_tasks": "false",
        "include_directives": "false",
        "people_limit": "2000",
        "organizations_limit": "1000",
    }
    auth = (TRACKER_USER, TRACKER_PASS) if TRACKER_USER else None
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(url, params=params, auth=auth)
            resp.raise_for_status()
            return resp.json()
    except (httpx.HTTPStatusError, httpx.ConnectError, httpx.TimeoutException) as e:
        logger.warning("Tracker context fetch failed for enrichment: %s", e)
        return {}


# ---------------------------------------------------------------------------
# Stage 1-2: create job and rows
# ---------------------------------------------------------------------------


def create_job(
    db,
    *,
    filename: str,
    stored_path: str,
    file_sha256: str,
    source_type: str,
    enrich_profile: bool,
    created_by: str | None = None,
) -> str:
    job_id = str(uuid.uuid4())
    db.execute(
        """INSERT INTO enrichment_jobs
           (id, source_type, original_filename, stored_path, file_sha256, status,
            enrich_profile, created_by)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            job_id,
            source_type,
            filename,
            stored_path,
            file_sha256,
            STATUS_UPLOADED,
            1 if enrich_profile else 0,
            created_by,
        ),
    )
    db.commit()
    return job_id


def store_rows(db, job_id: str, rows: list[dict]) -> int:
    """Persist raw rows verbatim. Mapping is applied later, so a re-map is cheap."""
    db.execute("DELETE FROM enrichment_rows WHERE job_id = ?", (job_id,))
    for i, row in enumerate(rows, start=1):
        db.execute(
            """INSERT INTO enrichment_rows (id, job_id, row_number, raw_row)
               VALUES (?, ?, ?, ?)""",
            (str(uuid.uuid4()), job_id, i, json.dumps(row)),
        )
    db.execute(
        "UPDATE enrichment_jobs SET row_count = ?, status = ?, updated_at = ? WHERE id = ?",
        (len(rows), STATUS_MAPPING, _now(), job_id),
    )
    db.commit()
    return len(rows)


def set_mapping(db, job_id: str, mapping: dict):
    db.execute(
        "UPDATE enrichment_jobs SET column_mapping = ?, status = ?, updated_at = ? WHERE id = ?",
        (json.dumps(mapping), STATUS_READY, _now(), job_id),
    )
    db.commit()


# ---------------------------------------------------------------------------
# Stage 3: normalize and resolve (no network calls to Hunter)
# ---------------------------------------------------------------------------


async def resolve_rows(db, job_id: str, policy: dict | None = None) -> dict:
    """Apply the mapping, match against the tracker, and decide what needs a lookup.

    Returns a summary suitable for the pre-flight panel. Spends nothing.
    """
    pol = policy or load_policy()
    enrich = pol.get("enrichment_policy", {})
    fuzzy = enrich.get("fuzzy_name_threshold", 0.85)

    job = get_job(db, job_id)
    if not job:
        raise ValueError(f"Unknown job {job_id}")
    mapping = json.loads(job["column_mapping"] or "{}")
    if not mapping:
        raise ValueError("Job has no confirmed column mapping")

    context = await fetch_tracker_context()
    people = context.get("people", []) or []
    organizations = context.get("organizations", []) or []

    rows = db.execute(
        "SELECT * FROM enrichment_rows WHERE job_id = ? ORDER BY row_number",
        (job_id,),
    ).fetchall()

    people_by_id = {p["id"]: p for p in people}
    summary = {
        "total": len(rows),
        "to_lookup": 0,
        "skipped": 0,
        "matched_existing": 0,
        "new_contacts": 0,
        "needs_domain": 0,
        "skip_reasons": {},
    }

    for row in rows:
        raw = json.loads(row["raw_row"])
        mapped = parsing.apply_mapping(raw, mapping)

        org_id, org_method = resolve_organization(mapped, organizations, fuzzy)
        domain, _domain_method = resolve_domain(mapped, organizations, org_id)
        mapped["domain"] = domain
        mapped["resolved_organization_id"] = org_id

        person_id, match_method, match_conf, ambiguous = match_person(
            mapped, people, fuzzy
        )
        person = people_by_id.get(person_id) if person_id else None

        do_lookup, reason = needs_lookup(mapped, person)
        hunter_status = HUNTER_PENDING if do_lookup else HUNTER_SKIPPED

        if do_lookup:
            summary["to_lookup"] += 1
        else:
            summary["skipped"] += 1
            summary["skip_reasons"][reason] = summary["skip_reasons"].get(reason, 0) + 1
            if reason == "no_domain":
                summary["needs_domain"] += 1
        if person_id:
            summary["matched_existing"] += 1
        else:
            summary["new_contacts"] += 1

        db.execute(
            """UPDATE enrichment_rows SET
                 first_name = ?, last_name = ?, full_name = ?, org_name_raw = ?,
                 domain = ?, title_raw = ?, email_raw = ?,
                 matched_person_id = ?, match_method = ?, match_confidence = ?,
                 match_ambiguous = ?,
                 resolved_organization_id = ?, org_resolution_method = ?,
                 hunter_status = ?, error_detail = ?, updated_at = ?
               WHERE id = ?""",
            (
                mapped["first_name"],
                mapped["last_name"],
                mapped["full_name"],
                mapped["org_name"],
                domain,
                mapped["title"],
                mapped["email"],
                person_id,
                match_method,
                match_conf,
                1 if ambiguous else 0,
                org_id,
                org_method,
                hunter_status,
                None if do_lookup else f"skipped: {reason}",
                _now(),
                row["id"],
            ),
        )
    # Each Email Finder call is one credit; profile enrichment adds a second.
    per_row = 2 if job["enrich_profile"] else 1
    summary["credits_estimated"] = summary["to_lookup"] * per_row

    db.execute(
        "UPDATE enrichment_jobs SET credits_estimated = ?, updated_at = ? WHERE id = ?",
        (summary["credits_estimated"], _now(), job_id),
    )
    db.commit()
    return summary


# ---------------------------------------------------------------------------
# Stage 4: Hunter fan-out
# ---------------------------------------------------------------------------


async def run_job(
    db,
    job_id: str,
    policy: dict | None = None,
    client: HunterClient | None = None,
    publish=None,
) -> dict:
    """Look up every pending row, bounded by concurrency and the credit cap.

    `publish` is an optional async callable(event_name, payload) for SSE.
    """
    pol = policy or load_policy()
    enrich = pol.get("enrichment_policy", {})
    concurrency = max(1, int(enrich.get("max_concurrency", 5)))

    job = get_job(db, job_id)
    if not job:
        raise ValueError(f"Unknown job {job_id}")
    if not job["egress_acknowledged_at"] and enrich.get(
        "require_egress_acknowledgement", True
    ):
        raise PermissionError("Third-party egress has not been acknowledged")

    clear_stop(job_id)
    _set_status(db, job_id, STATUS_RUNNING)

    pending = db.execute(
        """SELECT * FROM enrichment_rows
           WHERE job_id = ? AND hunter_status = ?
           ORDER BY row_number""",
        (job_id, HUNTER_PENDING),
    ).fetchall()

    credit_cap = job["credit_cap"]
    spent = job["credits_spent"] or 0
    enrich_profile = bool(job["enrich_profile"])

    owns_client = client is None
    hunter = client or HunterClient(policy=pol)
    semaphore = asyncio.Semaphore(concurrency)
    lock = asyncio.Lock()
    # `reserved` is the cap accounting. It must be claimed BEFORE the call, not
    # after: checking spent-so-far lets every concurrent worker pass the check
    # while spent is still stale, overrunning the cap by up to the concurrency.
    # Credits burned by earlier runs of this job count against the same budget.
    state = {
        "spent": spent,
        "reserved": spent,
        "stopped": False,
        "auth_error": None,
    }

    async def process(row):
        if state["stopped"]:
            return
        async with semaphore:
            if state["stopped"] or _stop_requested(job_id):
                state["stopped"] = True
                return

            cost = 2 if enrich_profile else 1
            async with lock:
                if credit_cap is not None and state["reserved"] + cost > credit_cap:
                    state["stopped"] = True
                    return
                state["reserved"] += cost

            actual = 0
            try:
                try:
                    result = await hunter.find_email(
                        db, row["first_name"], row["last_name"], row["domain"]
                    )
                except HunterAuthError as e:
                    state["auth_error"] = str(e)
                    state["stopped"] = True
                    return
                actual = result.credits_used

                profile = None
                if enrich_profile and result.status == HUNTER_FOUND and result.email:
                    try:
                        profile = await hunter.enrich_person(db, result.email)
                    except HunterAuthError as e:
                        state["auth_error"] = str(e)
                        state["stopped"] = True
                        return
                    actual += profile.credits_used
            finally:
                # Give back whatever the reservation over-claimed, so a cache hit
                # (which costs nothing) does not consume budget.
                async with lock:
                    state["reserved"] -= cost - actual

            async with lock:
                state["spent"] += actual
                _write_result(db, row, result, profile)
                db.execute(
                    """UPDATE enrichment_jobs SET
                         rows_processed = rows_processed + 1,
                         rows_found = rows_found + ?,
                         rows_not_found = rows_not_found + ?,
                         rows_skipped_cache = rows_skipped_cache + ?,
                         credits_spent = ?, updated_at = ?
                       WHERE id = ?""",
                    (
                        1 if result.status == HUNTER_FOUND else 0,
                        1 if result.status == HUNTER_NOT_FOUND else 0,
                        1 if result.from_cache else 0,
                        state["spent"],
                        _now(),
                        job_id,
                    ),
                )
                db.commit()

            if publish:
                await publish(
                    "enrichment_progress",
                    {
                        "job_id": job_id,
                        "row_number": row["row_number"],
                        "status": result.status,
                        "credits_spent": state["spent"],
                    },
                )

    try:
        if owns_client:
            async with hunter:
                await asyncio.gather(*(process(r) for r in pending))
        else:
            await asyncio.gather(*(process(r) for r in pending))
    finally:
        clear_stop(job_id)

    if state["auth_error"]:
        _set_status(db, job_id, STATUS_FAILED, error=state["auth_error"])
        if publish:
            await publish(
                "enrichment_error", {"job_id": job_id, "error": state["auth_error"]}
            )
        return {"status": STATUS_FAILED, "error": state["auth_error"]}

    remaining = db.execute(
        "SELECT COUNT(*) c FROM enrichment_rows WHERE job_id = ? AND hunter_status = ?",
        (job_id, HUNTER_PENDING),
    ).fetchone()["c"]

    if remaining and state["stopped"]:
        _set_status(db, job_id, STATUS_PAUSED)
        if publish:
            await publish(
                "enrichment_paused",
                {"job_id": job_id, "remaining": remaining,
                 "credits_spent": state["spent"]},
            )
        return {"status": STATUS_PAUSED, "remaining": remaining,
                "credits_spent": state["spent"]}

    await build_proposals(db, job_id, pol)
    _set_status(db, job_id, STATUS_AWAITING_REVIEW)
    if publish:
        await publish(
            "enrichment_complete",
            {"job_id": job_id, "credits_spent": state["spent"]},
        )
    return {"status": STATUS_AWAITING_REVIEW, "credits_spent": state["spent"]}


def _write_result(db, row, result, profile=None):
    """Persist one Hunter outcome onto its row."""
    linkedin = result.linkedin_url
    position = result.position
    seniority = result.seniority
    department = result.department
    twitter = result.twitter
    raw = {"finder": result.raw}

    if profile is not None:
        linkedin = profile.linkedin_url or linkedin
        position = profile.position or position
        seniority = profile.seniority or seniority
        department = profile.department or department
        twitter = profile.twitter or twitter
        raw["combined"] = profile.raw

    db.execute(
        """UPDATE enrichment_rows SET
             hunter_status = ?, hunter_email = ?, hunter_score = ?,
             hunter_verification = ?, hunter_position = ?, hunter_linkedin_url = ?,
             hunter_twitter = ?, hunter_seniority = ?, hunter_department = ?,
             hunter_sources_count = ?, hunter_raw = ?, from_cache = ?,
             credits_used = ?, error_detail = ?, updated_at = ?
           WHERE id = ?""",
        (
            result.status,
            result.email,
            result.score,
            result.verification,
            position,
            linkedin,
            twitter,
            seniority,
            department,
            result.sources_count,
            json.dumps(raw),
            1 if result.from_cache else 0,
            result.credits_used + (profile.credits_used if profile else 0),
            result.error_detail,
            _now(),
            row["id"],
        ),
    )


# ---------------------------------------------------------------------------
# Stage 5: proposals
# ---------------------------------------------------------------------------


async def build_proposals(db, job_id: str, policy: dict | None = None) -> dict:
    """Turn every row into a reviewable proposal and apply the auto-accept rule."""
    pol = policy or load_policy()
    job = get_job(db, job_id)
    context = await fetch_tracker_context()
    people_by_id = {p["id"]: p for p in (context.get("people") or [])}

    rows = db.execute(
        "SELECT * FROM enrichment_rows WHERE job_id = ? ORDER BY row_number",
        (job_id,),
    ).fetchall()

    counts = {"auto_accepted": 0, "pending": 0, "skipped": 0}
    now = _now()
    for row in rows:
        data = dict(row)
        data["match_ambiguous"] = bool(data.get("match_ambiguous"))
        person = people_by_id.get(data.get("matched_person_id"))

        proposed, action = build_proposal(data, person, dict(job), now)
        status, reason = decide_review_status(data, proposed, action, person, pol)
        counts[status] = counts.get(status, 0) + 1

        db.execute(
            """UPDATE enrichment_rows SET
                 proposed_data = ?, write_action = ?, review_status = ?,
                 error_detail = COALESCE(error_detail, ?), updated_at = ?
               WHERE id = ?""",
            (
                json.dumps(proposed) if proposed else None,
                action,
                status,
                None if status == "auto_accepted" else reason,
                now,
                data["id"],
            ),
        )
    db.commit()
    return counts


# ---------------------------------------------------------------------------
# Job helpers
# ---------------------------------------------------------------------------


def get_job(db, job_id: str):
    return db.execute(
        "SELECT * FROM enrichment_jobs WHERE id = ?", (job_id,)
    ).fetchone()


def _set_status(db, job_id: str, status: str, error: str | None = None):
    db.execute(
        "UPDATE enrichment_jobs SET status = ?, error_message = ?, updated_at = ? WHERE id = ?",
        (status, error, _now(), job_id),
    )
    db.commit()


def acknowledge_egress(db, job_id: str, credit_cap: int | None):
    db.execute(
        """UPDATE enrichment_jobs
           SET egress_acknowledged_at = ?, credit_cap = ?, updated_at = ?
           WHERE id = ?""",
        (_now(), credit_cap, _now(), job_id),
    )
    db.commit()


def org_domains_learned(db, job_id: str) -> dict:
    """Domains this job discovered for orgs that had none.

    Writing these back makes the next import cheaper, because the domain no
    longer has to be re-derived from an email.
    """
    rows = db.execute(
        """SELECT DISTINCT resolved_organization_id AS org_id, domain
           FROM enrichment_rows
           WHERE job_id = ? AND resolved_organization_id IS NOT NULL
             AND domain IS NOT NULL AND domain != ''
             AND org_resolution_method != 'domain'""",
        (job_id,),
    ).fetchall()
    out: dict[str, str] = {}
    for row in rows:
        out.setdefault(row["org_id"], row["domain"])
    return out
