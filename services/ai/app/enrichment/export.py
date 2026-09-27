"""Hand the spreadsheet back, filled in.

The original column order is preserved and every input row appears, including
not-found ones. An export that silently drops rows is worse than useless for
reconciliation: the operator cannot tell a missing row from a failed one.
"""

import csv
import io
import json
import logging

logger = logging.getLogger(__name__)

# Appended to the right of the operator's own columns.
APPENDED_COLUMNS = (
    "hunter_email",
    "hunter_score",
    "hunter_verification",
    "hunter_linkedin_url",
    "hunter_position",
    "review_status",
    "tracker_person_id",
)


def _row_values(row: dict) -> dict:
    """The appended cells for one enrichment row."""
    return {
        "hunter_email": row.get("hunter_email") or "",
        "hunter_score": "" if row.get("hunter_score") is None else row["hunter_score"],
        "hunter_verification": row.get("hunter_verification") or "",
        "hunter_linkedin_url": row.get("hunter_linkedin_url") or "",
        "hunter_position": row.get("hunter_position") or "",
        "review_status": row.get("review_status") or "",
        "tracker_person_id": row.get("matched_person_id") or "",
    }


def _original_headers(rows: list[dict]) -> list[str]:
    """Header order as it appeared in the upload, union across all rows."""
    headers: list[str] = []
    for row in rows:
        try:
            raw = json.loads(row["raw_row"])
        except (TypeError, json.JSONDecodeError):
            continue
        for key in raw:
            if key not in headers:
                headers.append(key)
    return headers


def build_csv(rows: list[dict]) -> bytes:
    """Original sheet plus the appended columns, as UTF-8 CSV with a BOM.

    The BOM is deliberate: without it Excel mangles non-ASCII names.
    """
    original = _original_headers(rows)
    fieldnames = original + [c for c in APPENDED_COLUMNS if c not in original]

    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        try:
            raw = json.loads(row["raw_row"])
        except (TypeError, json.JSONDecodeError):
            raw = {}
        record = {h: raw.get(h, "") for h in original}
        record.update(_row_values(row))
        writer.writerow(record)
    return buf.getvalue().encode("utf-8-sig")


def build_xlsx(rows: list[dict]) -> bytes:
    """Same content as build_csv, as a workbook."""
    import openpyxl

    original = _original_headers(rows)
    fieldnames = original + [c for c in APPENDED_COLUMNS if c not in original]

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Contacts"
    ws.append(fieldnames)
    for row in rows:
        try:
            raw = json.loads(row["raw_row"])
        except (TypeError, json.JSONDecodeError):
            raw = {}
        record = {h: raw.get(h, "") for h in original}
        record.update(_row_values(row))
        ws.append([record.get(h, "") for h in fieldnames])

    buf = io.BytesIO()
    wb.save(buf)
    wb.close()
    return buf.getvalue()


def export_job(db, job_id: str, fmt: str | None = None) -> tuple[bytes, str, str]:
    """Build the filled sheet for a job.

    Returns (content, filename, media_type). Format defaults to whatever the
    upload was.
    """
    job = db.execute(
        "SELECT * FROM enrichment_jobs WHERE id = ?", (job_id,)
    ).fetchone()
    if not job:
        raise ValueError(f"Unknown job {job_id}")

    rows = [
        dict(r)
        for r in db.execute(
            "SELECT * FROM enrichment_rows WHERE job_id = ? ORDER BY row_number",
            (job_id,),
        ).fetchall()
    ]

    original_name = job["original_filename"] or "contacts"
    stem = original_name.rsplit(".", 1)[0] if "." in original_name else original_name

    chosen = (fmt or "").lower().lstrip(".")
    if not chosen:
        chosen = "xlsx" if original_name.lower().endswith((".xlsx", ".xlsm")) else "csv"

    if chosen == "xlsx":
        return (
            build_xlsx(rows),
            f"{stem}_enriched.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    return build_csv(rows), f"{stem}_enriched.csv", "text/csv; charset=utf-8"
