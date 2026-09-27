"""Commit accepted rows to the tracker, and undo a commit.

Writes go through app/writeback/tracker_client.post_batch, which already handles
retry, connection pooling, and idempotency keys against POST /tracker/batch.
Every write is recorded in enrichment_writebacks with previous_data, so a wrong
email can be reversed.
"""

import json
import logging
import uuid
from datetime import datetime

from app.config import load_policy
from app.enrichment import runner
from app.enrichment.proposals import (
    REVIEW_ACCEPTED,
    REVIEW_AUTO_ACCEPTED,
    REVIEW_COMMITTED,
    REVIEW_EDITED,
    to_batch_operations,
)
from app.writeback.tracker_client import TrackerBatchError, post_batch

logger = logging.getLogger(__name__)

# Statuses eligible to be written.
COMMITTABLE = (REVIEW_ACCEPTED, REVIEW_AUTO_ACCEPTED, REVIEW_EDITED)


def _now() -> str:
    return datetime.now().isoformat()


async def commit_job(db, job_id: str, policy: dict | None = None) -> dict:
    """Write every accepted row for this job to the tracker.

    Idempotent per job: the idempotency key is derived from the job id and the
    set of rows being written, so a retry after a network failure does not create
    duplicate people.
    """
    pol = policy or load_policy()
    enrich = pol.get("enrichment_policy", {})

    job = runner.get_job(db, job_id)
    if not job:
        raise ValueError(f"Unknown job {job_id}")

    placeholders = ",".join("?" * len(COMMITTABLE))
    rows = [
        dict(r)
        for r in db.execute(
            f"""SELECT * FROM enrichment_rows
                WHERE job_id = ? AND review_status IN ({placeholders})
                ORDER BY row_number""",
            (job_id, *COMMITTABLE),
        ).fetchall()
    ]

    if not rows:
        return {"committed": 0, "operations": 0, "message": "nothing accepted to commit"}

    org_updates = (
        runner.org_domains_learned(db, job_id)
        if enrich.get("propose_org_domain_writeback", True)
        else {}
    )

    operations, plan = to_batch_operations(
        rows,
        {},
        dict(job),
        propose_org_domains=bool(org_updates),
        org_domain_updates=org_updates,
    )

    if not operations:
        return {"committed": 0, "operations": 0, "message": "no writable changes"}

    runner._set_status(db, job_id, runner.STATUS_COMMITTING)

    idempotency_key = _idempotency_key(job_id, rows)

    try:
        response = await post_batch(
            operations,
            source="hunter",
            source_metadata={"enrichment_job_id": job_id},
            idempotency_key=idempotency_key,
        )
    except TrackerBatchError as e:
        runner._set_status(db, job_id, runner.STATUS_AWAITING_REVIEW, error=str(e))
        logger.error("Enrichment commit failed for job %s: %s", job_id, e)
        raise

    results = response.get("results") or []
    committed = _record_writebacks(db, job_id, plan, results)

    runner._set_status(db, job_id, runner.STATUS_COMPLETE)
    return {
        "committed": committed,
        "operations": len(operations),
        "org_domains_written": len(org_updates),
    }


def _idempotency_key(job_id: str, rows: list[dict]) -> str:
    """Stable per (job, accepted row set), so a retry is safe but a second
    genuine commit after more rows are accepted is not blocked."""
    row_ids = ",".join(sorted(r["id"] for r in rows))
    digest = uuid.uuid5(uuid.NAMESPACE_URL, f"enrichment:{job_id}:{row_ids}")
    return f"enrich-{digest}"


def _record_writebacks(db, job_id: str, plan: list[dict], results: list[dict]) -> int:
    """Pair each batch result with its plan entry and record it for undo."""
    committed = 0
    now = _now()
    for i, entry in enumerate(plan):
        result = results[i] if i < len(results) else {}
        record_id = result.get("record_id")
        if not record_id:
            continue

        written_data = {}
        if entry.get("row_id"):
            row = db.execute(
                "SELECT proposed_data, edited_data FROM enrichment_rows WHERE id = ?",
                (entry["row_id"],),
            ).fetchone()
            if row:
                raw = row["edited_data"] or row["proposed_data"] or "{}"
                try:
                    written_data = json.loads(raw)
                except (TypeError, json.JSONDecodeError):
                    written_data = {}

        db.execute(
            """INSERT INTO enrichment_writebacks
               (id, job_id, row_id, target_table, target_record_id, write_type,
                written_data, previous_data, auto_committed, written_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                str(uuid.uuid4()),
                job_id,
                entry.get("row_id") or "",
                entry["table"],
                record_id,
                entry["write_type"],
                json.dumps(written_data),
                json.dumps(result.get("previous_data")) if result.get("previous_data") else None,
                0,
                now,
            ),
        )

        if entry.get("row_id"):
            db.execute(
                """UPDATE enrichment_rows
                   SET review_status = ?, matched_person_id = COALESCE(matched_person_id, ?),
                       reviewed_at = COALESCE(reviewed_at, ?), updated_at = ?
                   WHERE id = ?""",
                (REVIEW_COMMITTED, record_id, now, now, entry["row_id"]),
            )
            committed += 1

    db.commit()
    return committed


async def undo_job(db, job_id: str) -> dict:
    """Reverse this job's writebacks.

    Updates are restored from previous_data. Creates are soft-deleted, because
    the tracker treats a person delete as is_active = 0 and hard-deleting a
    record other things may now reference would be worse than leaving it inactive.
    """
    writebacks = [
        dict(r)
        for r in db.execute(
            """SELECT * FROM enrichment_writebacks
               WHERE job_id = ? AND reversed = 0
               ORDER BY written_at DESC""",
            (job_id,),
        ).fetchall()
    ]
    if not writebacks:
        return {"reversed": 0, "message": "nothing to undo"}

    operations = []
    reversible = []
    for wb in writebacks:
        if wb["write_type"] == "update":
            if not wb["previous_data"]:
                continue
            try:
                previous = json.loads(wb["previous_data"])
            except (TypeError, json.JSONDecodeError):
                continue
            written = {}
            try:
                written = json.loads(wb["written_data"] or "{}")
            except (TypeError, json.JSONDecodeError):
                pass
            # Restore only the fields this job actually wrote.
            restore = {
                k: previous.get(k) for k in written if k in previous
            }
            if not restore:
                continue
            operations.append(
                {
                    "table": wb["target_table"],
                    "op": "update",
                    "record_id": wb["target_record_id"],
                    "data": restore,
                }
            )
            reversible.append(wb)
        elif wb["write_type"] == "create":
            operations.append(
                {
                    "table": wb["target_table"],
                    "op": "delete",
                    "record_id": wb["target_record_id"],
                }
            )
            reversible.append(wb)

    if not operations:
        return {"reversed": 0, "message": "no reversible writes"}

    await post_batch(
        operations,
        source="hunter",
        source_metadata={"enrichment_job_id": job_id, "undo": True},
        idempotency_key=f"enrich-undo-{job_id}-{len(reversible)}",
    )

    now = _now()
    for wb in reversible:
        db.execute(
            "UPDATE enrichment_writebacks SET reversed = 1, reversed_at = ? WHERE id = ?",
            (now, wb["id"]),
        )
        if wb["row_id"]:
            db.execute(
                "UPDATE enrichment_rows SET review_status = ?, updated_at = ? WHERE id = ?",
                (REVIEW_ACCEPTED, now, wb["row_id"]),
            )
    db.commit()
    return {"reversed": len(reversible)}
