"""Contact enrichment API — upload a sheet, fill in emails via Hunter.io, review, commit.

Endpoint order mirrors the operator's path through the feature: upload, confirm
the column mapping, look at the pre-flight cost, acknowledge the third-party
egress, run, review, commit.

Nothing reaches Hunter before the mapping is confirmed and the egress gate is
acknowledged, so a malformed sheet or a change of mind costs nothing.
"""

import hashlib
import json
import logging
from pathlib import Path

from fastapi import APIRouter, Body, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import Response

from app.config import (
    ENRICHMENT_UPLOAD_DIR,
    HUNTER_API_KEY,
    MAX_ENRICHMENT_UPLOAD_BYTES,
    load_policy,
)
from app.db import get_db
from app.enrichment import committer, export, parsing, runner
from app.enrichment.hunter_client import HunterAuthError, HunterClient, HunterError
from app.enrichment.proposals import (
    REVIEW_ACCEPTED,
    REVIEW_AUTO_ACCEPTED,
    REVIEW_EDITED,
    REVIEW_PENDING,
    REVIEW_REJECTED,
    UPDATABLE_PERSON_FIELDS,
)
from app.routers.events import publish_event

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/enrichment", tags=["contact-enrichment"])


def _policy() -> dict:
    return load_policy()


def _enrich_policy() -> dict:
    return _policy().get("enrichment_policy", {})


def _require_enabled():
    pol = _enrich_policy()
    if not pol.get("enabled", True):
        raise HTTPException(503, detail="Contact enrichment is disabled by policy")
    if not HUNTER_API_KEY:
        raise HTTPException(
            503,
            detail="HUNTER_API_KEY is not configured — set it in .env to use "
            "contact enrichment",
        )


def _job_or_404(db, job_id: str):
    job = runner.get_job(db, job_id)
    if not job:
        raise HTTPException(404, detail="Enrichment job not found")
    return job


# ---------------------------------------------------------------------------
# Availability
# ---------------------------------------------------------------------------


@router.get("/status")
async def enrichment_status():
    """Whether the feature is usable, and the thresholds in force.

    Deliberately does not require the key: the UI needs to explain why the
    feature is unavailable.
    """
    pol = _enrich_policy()
    return {
        "enabled": bool(pol.get("enabled", True)),
        "api_key_configured": bool(HUNTER_API_KEY),
        "auto_accept_score": pol.get("auto_accept_score", 90),
        "max_rows_per_job": pol.get("max_rows_per_job", 5000),
        "default_credit_cap": pol.get("default_credit_cap", 500),
        "enrich_profile_default": bool(pol.get("enrich_profile_default", False)),
        "require_egress_acknowledgement": bool(
            pol.get("require_egress_acknowledgement", True)
        ),
    }


@router.get("/account")
async def hunter_account():
    """Remaining Hunter credits. Free — spends nothing."""
    _require_enabled()
    try:
        async with HunterClient(policy=_policy()) as client:
            return await client.account()
    except HunterAuthError as e:
        raise HTTPException(502, detail=f"Hunter rejected the API key: {e.message}")
    except HunterError as e:
        raise HTTPException(502, detail=f"Hunter unreachable: {e.message}")


# ---------------------------------------------------------------------------
# Jobs
# ---------------------------------------------------------------------------


@router.get("/jobs")
async def list_jobs(
    db=Depends(get_db),
    status: str = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0),
):
    conditions, params = [], []
    if status:
        conditions.append("status = ?")
        params.append(status)
    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    total = db.execute(
        f"SELECT COUNT(*) c FROM enrichment_jobs {where}", params
    ).fetchone()["c"]
    rows = db.execute(
        f"""SELECT * FROM enrichment_jobs {where}
            ORDER BY created_at DESC LIMIT ? OFFSET ?""",
        params + [limit, offset],
    ).fetchall()
    return {
        "items": [dict(r) for r in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.post("/jobs")
async def create_job(
    file: UploadFile = File(...),
    source_type: str = Query(
        parsing.SOURCE_SPREADSHEET,
        description="'spreadsheet' or 'linkedin_export'",
    ),
    enrich_profile: bool = Query(
        None, description="Also fetch LinkedIn URL and title (one extra credit per row)"
    ),
    db=Depends(get_db),
):
    """Upload a contact sheet. Parses and stores rows; spends nothing."""
    _require_enabled()

    if source_type not in (parsing.SOURCE_SPREADSHEET, parsing.SOURCE_LINKEDIN):
        raise HTTPException(400, detail=f"Unknown source_type '{source_type}'")

    content = await file.read()
    if not content:
        raise HTTPException(400, detail="File is empty")
    if len(content) > MAX_ENRICHMENT_UPLOAD_BYTES:
        raise HTTPException(
            413,
            detail=f"File too large: {len(content)} bytes "
            f"(max {MAX_ENRICHMENT_UPLOAD_BYTES})",
        )

    try:
        headers, rows = parsing.parse_file(content, file.filename or "upload.csv")
    except parsing.ParseError as e:
        raise HTTPException(422, detail=str(e))

    if not rows:
        raise HTTPException(422, detail="No data rows found in the file")

    max_rows = _enrich_policy().get("max_rows_per_job", 5000)
    if len(rows) > max_rows:
        raise HTTPException(
            422,
            detail=f"{len(rows)} rows exceeds the per-job limit of {max_rows}. "
            "Split the file or raise max_rows_per_job.",
        )

    # A sheet whose headers look like LinkedIn's export gets the preset even if
    # the caller did not say so — the mapping is confirmed either way.
    if source_type == parsing.SOURCE_SPREADSHEET and parsing.is_linkedin_export(headers):
        source_type = parsing.SOURCE_LINKEDIN

    sha = hashlib.sha256(content).hexdigest()
    duplicate = db.execute(
        "SELECT id, created_at FROM enrichment_jobs WHERE file_sha256 = ? "
        "ORDER BY created_at DESC LIMIT 1",
        (sha,),
    ).fetchone()

    if enrich_profile is None:
        enrich_profile = bool(_enrich_policy().get("enrich_profile_default", False))

    safe_name = Path(file.filename or "upload.csv").name.replace("..", "_")
    job_id = runner.create_job(
        db,
        filename=safe_name,
        stored_path="",  # set below, once we know the job id
        file_sha256=sha,
        source_type=source_type,
        enrich_profile=enrich_profile,
    )

    job_dir = ENRICHMENT_UPLOAD_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    stored = job_dir / safe_name
    stored.write_bytes(content)
    db.execute(
        "UPDATE enrichment_jobs SET stored_path = ? WHERE id = ?",
        (str(stored), job_id),
    )
    db.commit()

    runner.store_rows(db, job_id, rows)
    proposed = parsing.propose_mapping(headers, source_type)

    return {
        "job_id": job_id,
        "source_type": source_type,
        "row_count": len(rows),
        "headers": headers,
        "proposed_mapping": proposed,
        "mapping_problems": parsing.validate_mapping(proposed),
        "enrich_profile": enrich_profile,
        "duplicate_of": dict(duplicate) if duplicate else None,
        "preview": rows[:10],
    }


@router.get("/jobs/{job_id}")
async def get_job(job_id: str, db=Depends(get_db)):
    job = dict(_job_or_404(db, job_id))
    counts = {
        r["review_status"]: r["c"]
        for r in db.execute(
            "SELECT review_status, COUNT(*) c FROM enrichment_rows "
            "WHERE job_id = ? GROUP BY review_status",
            (job_id,),
        )
    }
    hunter_counts = {
        r["hunter_status"]: r["c"]
        for r in db.execute(
            "SELECT hunter_status, COUNT(*) c FROM enrichment_rows "
            "WHERE job_id = ? GROUP BY hunter_status",
            (job_id,),
        )
    }
    job["review_counts"] = counts
    job["hunter_counts"] = hunter_counts
    if job.get("column_mapping"):
        try:
            job["column_mapping"] = json.loads(job["column_mapping"])
        except json.JSONDecodeError:
            pass
    return job


@router.get("/jobs/{job_id}/preview")
async def preview_job(job_id: str, db=Depends(get_db), limit: int = Query(10, le=50)):
    """Parsed headers and the first rows, for the mapping step."""
    _job_or_404(db, job_id)
    rows = db.execute(
        "SELECT raw_row FROM enrichment_rows WHERE job_id = ? ORDER BY row_number LIMIT ?",
        (job_id, limit),
    ).fetchall()
    parsed = []
    headers: list[str] = []
    for r in rows:
        try:
            raw = json.loads(r["raw_row"])
        except json.JSONDecodeError:
            continue
        parsed.append(raw)
        for k in raw:
            if k not in headers:
                headers.append(k)
    return {"headers": headers, "rows": parsed}


@router.put("/jobs/{job_id}/mapping")
async def confirm_mapping(
    job_id: str,
    payload: dict = Body(...),
    db=Depends(get_db),
):
    """Confirm the column mapping. Required before anything is looked up."""
    _job_or_404(db, job_id)
    mapping = payload.get("mapping")
    if not isinstance(mapping, dict) or not mapping:
        raise HTTPException(400, detail="'mapping' must be a non-empty object")

    problems = parsing.validate_mapping(mapping)
    if problems:
        raise HTTPException(422, detail={"mapping_problems": problems})

    runner.set_mapping(db, job_id, mapping)
    summary = await runner.resolve_rows(db, job_id, _policy())
    return {"job_id": job_id, "mapping": mapping, "resolution": summary}


@router.get("/jobs/{job_id}/preflight")
async def preflight(job_id: str, db=Depends(get_db)):
    """What this job will cost, and whether the account can cover it.

    Uses only free Hunter endpoints. Spends nothing.
    """
    _require_enabled()
    job = _job_or_404(db, job_id)
    if not job["column_mapping"]:
        raise HTTPException(409, detail="Confirm the column mapping first")

    counts = {
        r["hunter_status"]: r["c"]
        for r in db.execute(
            "SELECT hunter_status, COUNT(*) c FROM enrichment_rows "
            "WHERE job_id = ? GROUP BY hunter_status",
            (job_id,),
        )
    }
    skip_reasons = {
        r["error_detail"]: r["c"]
        for r in db.execute(
            "SELECT error_detail, COUNT(*) c FROM enrichment_rows "
            "WHERE job_id = ? AND hunter_status = 'skipped' GROUP BY error_detail",
            (job_id,),
        )
        if r["error_detail"]
    }

    balance = None
    balance_error = None
    try:
        async with HunterClient(policy=_policy()) as client:
            account = await client.account()
        balance = (
            account.get("requests", {}).get("searches", {}).get("available")
            if isinstance(account.get("requests"), dict)
            else None
        )
    except (HunterAuthError, HunterError) as e:
        balance_error = e.message

    estimated = job["credits_estimated"] or 0
    return {
        "job_id": job_id,
        "row_count": job["row_count"],
        "to_lookup": counts.get("pending", 0),
        "skipped": counts.get("skipped", 0),
        "skip_reasons": skip_reasons,
        "credits_estimated": estimated,
        "credits_spent": job["credits_spent"] or 0,
        "credit_balance": balance,
        "balance_error": balance_error,
        "sufficient_credits": (balance is None or balance >= estimated),
        "default_credit_cap": _enrich_policy().get("default_credit_cap", 500),
        "egress_acknowledged": bool(job["egress_acknowledged_at"]),
        "require_egress_acknowledgement": bool(
            _enrich_policy().get("require_egress_acknowledgement", True)
        ),
    }


@router.post("/jobs/{job_id}/start")
async def start_job(
    job_id: str,
    payload: dict = Body(default={}),
    db=Depends(get_db),
):
    """Acknowledge the third-party egress, set the credit cap, and run.

    The egress acknowledgement is explicit because this sends names of
    identifiable third parties to a commercial API.
    """
    _require_enabled()
    job = _job_or_404(db, job_id)
    if not job["column_mapping"]:
        raise HTTPException(409, detail="Confirm the column mapping first")
    if job["status"] == runner.STATUS_RUNNING:
        raise HTTPException(409, detail="Job is already running")

    require_ack = _enrich_policy().get("require_egress_acknowledgement", True)
    acknowledged = bool(payload.get("acknowledge_egress"))
    if require_ack and not acknowledged and not job["egress_acknowledged_at"]:
        raise HTTPException(
            422,
            detail="acknowledge_egress must be true: this sends contact names to "
            "Hunter.io, a third-party service",
        )

    cap = payload.get("credit_cap", _enrich_policy().get("default_credit_cap", 500))
    if cap is not None:
        try:
            cap = int(cap)
        except (TypeError, ValueError):
            raise HTTPException(400, detail="credit_cap must be an integer or null")
        if cap <= 0:
            raise HTTPException(400, detail="credit_cap must be positive")

    runner.acknowledge_egress(db, job_id, cap)

    try:
        result = await runner.run_job(
            db, job_id, _policy(), publish=publish_event
        )
    except PermissionError as e:
        raise HTTPException(422, detail=str(e))
    return result


@router.post("/jobs/{job_id}/resume")
async def resume_job(
    job_id: str,
    payload: dict = Body(default={}),
    db=Depends(get_db),
):
    """Resume a paused job, optionally with a higher credit cap."""
    _require_enabled()
    job = _job_or_404(db, job_id)
    if job["status"] not in (runner.STATUS_PAUSED, runner.STATUS_READY):
        raise HTTPException(
            409, detail=f"Job is '{job['status']}', not paused"
        )
    if "credit_cap" in payload:
        cap = payload["credit_cap"]
        if cap is not None:
            try:
                cap = int(cap)
            except (TypeError, ValueError):
                raise HTTPException(400, detail="credit_cap must be an integer or null")
        runner.acknowledge_egress(db, job_id, cap)

    try:
        return await runner.run_job(db, job_id, _policy(), publish=publish_event)
    except PermissionError as e:
        raise HTTPException(422, detail=str(e))


@router.post("/jobs/{job_id}/pause")
async def pause_job(job_id: str, db=Depends(get_db)):
    """Ask a running job to stop at the next row boundary."""
    job = _job_or_404(db, job_id)
    if job["status"] != runner.STATUS_RUNNING:
        raise HTTPException(409, detail=f"Job is '{job['status']}', not running")
    runner.request_stop(job_id)
    return {"job_id": job_id, "pausing": True}


@router.post("/jobs/{job_id}/cancel")
async def cancel_job(job_id: str, db=Depends(get_db)):
    job = _job_or_404(db, job_id)
    if job["status"] in (runner.STATUS_COMPLETE, runner.STATUS_CANCELLED):
        raise HTTPException(409, detail=f"Job is already '{job['status']}'")
    runner.request_stop(job_id)
    runner._set_status(db, job_id, runner.STATUS_CANCELLED)
    return {"job_id": job_id, "status": runner.STATUS_CANCELLED}


# ---------------------------------------------------------------------------
# Review
# ---------------------------------------------------------------------------


@router.get("/jobs/{job_id}/rows")
async def list_rows(
    job_id: str,
    db=Depends(get_db),
    review_status: str = Query(None),
    hunter_status: str = Query(None),
    limit: int = Query(100, le=500),
    offset: int = Query(0),
):
    _job_or_404(db, job_id)
    conditions, params = ["job_id = ?"], [job_id]
    if review_status:
        conditions.append("review_status = ?")
        params.append(review_status)
    if hunter_status:
        conditions.append("hunter_status = ?")
        params.append(hunter_status)
    where = " AND ".join(conditions)

    total = db.execute(
        f"SELECT COUNT(*) c FROM enrichment_rows WHERE {where}", params
    ).fetchone()["c"]
    rows = db.execute(
        f"""SELECT * FROM enrichment_rows WHERE {where}
            ORDER BY row_number LIMIT ? OFFSET ?""",
        params + [limit, offset],
    ).fetchall()

    items = []
    for r in rows:
        item = dict(r)
        for key in ("raw_row", "proposed_data", "edited_data"):
            if item.get(key):
                try:
                    item[key] = json.loads(item[key])
                except (TypeError, json.JSONDecodeError):
                    pass
        # hunter_raw is large and only useful for audit; omit from the list view.
        item.pop("hunter_raw", None)
        items.append(item)

    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.patch("/rows/{row_id}")
async def update_row(
    row_id: str,
    payload: dict = Body(...),
    db=Depends(get_db),
):
    """Accept, reject, edit, or supply a missing domain for one row."""
    row = db.execute("SELECT * FROM enrichment_rows WHERE id = ?", (row_id,)).fetchone()
    if not row:
        raise HTTPException(404, detail="Row not found")

    action = payload.get("action")
    now = runner._now()

    if action == "accept":
        db.execute(
            """UPDATE enrichment_rows SET review_status = ?, reviewed_by = ?,
                 reviewed_at = ?, updated_at = ? WHERE id = ?""",
            (REVIEW_ACCEPTED, payload.get("actor"), now, now, row_id),
        )
    elif action == "reject":
        db.execute(
            """UPDATE enrichment_rows SET review_status = ?, reviewed_by = ?,
                 reviewed_at = ?, updated_at = ? WHERE id = ?""",
            (REVIEW_REJECTED, payload.get("actor"), now, now, row_id),
        )
    elif action == "edit":
        edits = payload.get("data")
        if not isinstance(edits, dict) or not edits:
            raise HTTPException(400, detail="'data' must be a non-empty object")
        unknown = sorted(set(edits) - set(UPDATABLE_PERSON_FIELDS) - {
            "full_name", "first_name", "last_name", "source", "source_id",
        })
        if unknown:
            raise HTTPException(
                422, detail=f"Fields not writable by enrichment: {unknown}"
            )
        base = {}
        if row["proposed_data"]:
            try:
                base = json.loads(row["proposed_data"])
            except json.JSONDecodeError:
                base = {}
        base.update(edits)
        db.execute(
            """UPDATE enrichment_rows SET edited_data = ?, review_status = ?,
                 reviewed_by = ?, reviewed_at = ?, updated_at = ? WHERE id = ?""",
            (json.dumps(base), REVIEW_EDITED, payload.get("actor"), now, now, row_id),
        )
    elif action == "set_domain":
        domain = parsing.normalize_domain(payload.get("domain") or "")
        if not domain:
            raise HTTPException(400, detail="'domain' is not a valid domain")
        db.execute(
            """UPDATE enrichment_rows SET domain = ?, hunter_status = ?,
                 review_status = ?, error_detail = NULL, updated_at = ?
               WHERE id = ?""",
            (domain, runner.HUNTER_PENDING, REVIEW_PENDING, now, row_id),
        )
    else:
        raise HTTPException(
            400,
            detail="action must be one of: accept, reject, edit, set_domain",
        )

    db.commit()
    updated = db.execute(
        "SELECT * FROM enrichment_rows WHERE id = ?", (row_id,)
    ).fetchone()
    return {"id": row_id, "review_status": updated["review_status"]}


@router.post("/jobs/{job_id}/bulk-accept")
async def bulk_accept(job_id: str, payload: dict = Body(default={}), db=Depends(get_db)):
    """Accept every row the auto-accept rule pre-approved."""
    _job_or_404(db, job_id)
    now = runner._now()
    cursor = db.execute(
        """UPDATE enrichment_rows SET review_status = ?, reviewed_by = ?,
             reviewed_at = ?, updated_at = ?
           WHERE job_id = ? AND review_status = ?""",
        (
            REVIEW_ACCEPTED,
            payload.get("actor"),
            now,
            now,
            job_id,
            REVIEW_AUTO_ACCEPTED,
        ),
    )
    db.commit()
    return {"job_id": job_id, "accepted": cursor.rowcount}


@router.post("/jobs/{job_id}/commit")
async def commit(job_id: str, db=Depends(get_db)):
    """Write accepted rows into the tracker."""
    _job_or_404(db, job_id)
    try:
        return await committer.commit_job(db, job_id, _policy())
    except Exception as e:
        logger.exception("Enrichment commit failed for job %s", job_id)
        raise HTTPException(502, detail=f"Commit failed: {e}")


@router.post("/jobs/{job_id}/undo")
async def undo(job_id: str, db=Depends(get_db)):
    """Reverse this job's writes to the tracker."""
    _job_or_404(db, job_id)
    try:
        return await committer.undo_job(db, job_id)
    except Exception as e:
        logger.exception("Enrichment undo failed for job %s", job_id)
        raise HTTPException(502, detail=f"Undo failed: {e}")


@router.get("/jobs/{job_id}/export")
async def export_filled_sheet(
    job_id: str,
    db=Depends(get_db),
    fmt: str = Query(None, description="'csv' or 'xlsx'; defaults to the upload format"),
):
    """The original sheet with the enrichment columns filled in.

    Every input row appears, including not-found ones.
    """
    _job_or_404(db, job_id)
    try:
        content, filename, media_type = export.export_job(db, job_id, fmt)
    except ValueError as e:
        raise HTTPException(404, detail=str(e))
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
