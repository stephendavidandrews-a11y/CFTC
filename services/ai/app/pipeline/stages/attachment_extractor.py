"""Attachment text extraction stage — extract readable text from email attachments.

Pipeline position: parsing -> **processing_attachments** -> awaiting_participant_review

Extracts text from PDF, DOCX, and plain text attachments.
Skips unsupported types and quarantined files.
"""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Max extracted text length per attachment
MAX_TEXT_LENGTH = 100_000
# Timeout per file extraction (seconds)
EXTRACTION_TIMEOUT = 30


def _extract_pdf_text(file_path: Path) -> str:
    """Extract text from PDF file."""
    try:
        import PyPDF2

        text_parts = []
        with open(file_path, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            for page in reader.pages[:100]:  # Cap at 100 pages
                page_text = page.extract_text() or ""
                text_parts.append(page_text)
                if sum(len(t) for t in text_parts) > MAX_TEXT_LENGTH:
                    break
        return "\n\n".join(text_parts)[:MAX_TEXT_LENGTH]
    except Exception as e:
        raise RuntimeError(f"PDF extraction failed: {e}") from e


def _extract_docx_text(file_path: Path) -> str:
    """Extract text from DOCX file."""
    try:
        import docx

        doc = docx.Document(str(file_path))
        text_parts = []
        for para in doc.paragraphs:
            text_parts.append(para.text)
            if sum(len(t) for t in text_parts) > MAX_TEXT_LENGTH:
                break
        return "\n".join(text_parts)[:MAX_TEXT_LENGTH]
    except Exception as e:
        raise RuntimeError(f"DOCX extraction failed: {e}") from e


def _extract_text_file(file_path: Path) -> str:
    """Extract text from plain text files."""
    try:
        return file_path.read_text(encoding="utf-8", errors="replace")[:MAX_TEXT_LENGTH]
    except Exception as e:
        raise RuntimeError(f"Text file extraction failed: {e}") from e


EXTRACTORS = {
    "application/pdf": _extract_pdf_text,
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": _extract_docx_text,
    "application/msword": None,  # .doc not directly supported
    "text/plain": _extract_text_file,
    "text/csv": _extract_text_file,
    "text/html": _extract_text_file,
}


async def run_attachment_extraction_stage(db, communication_id: str) -> dict:
    """Extract text from all pending attachments for a communication.

    Returns dict with extraction results.
    """
    from app.routers.events import publish_event

    artifacts = db.execute(
        """
        SELECT id, file_path, mime_type, original_filename, text_extraction_status
        FROM communication_artifacts
        WHERE communication_id = ? AND text_extraction_status = 'pending'
    """,
        (communication_id,),
    ).fetchall()

    if not artifacts:
        logger.info("[%s] No pending attachments to extract", communication_id[:8])
        return {"extracted": 0, "failed": 0, "skipped": 0}

    await publish_event(
        "stage_progress",
        {
            "communication_id": communication_id,
            "stage": "processing_attachments",
            "message": f"Extracting text from {len(artifacts)} attachments...",
        },
    )

    extracted = 0
    failed = 0
    skipped = 0

    for art in artifacts:
        file_path = Path(art["file_path"])
        mime_type = art["mime_type"] or ""

        extractor = EXTRACTORS.get(mime_type)

        if extractor is None and mime_type in EXTRACTORS:
            # Explicitly unsupported (like .doc)
            db.execute(
                """
                UPDATE communication_artifacts
                SET text_extraction_status = 'not_supported',
                    quarantine_reason = ?
                WHERE id = ?
            """,
                (f"No extractor for {mime_type}", art["id"]),
            )
            skipped += 1
            continue

        if extractor is None:
            # Unknown type -- not applicable
            db.execute(
                """
                UPDATE communication_artifacts
                SET text_extraction_status = 'not_applicable'
                WHERE id = ?
            """,
                (art["id"],),
            )
            skipped += 1
            continue

        if not file_path.exists():
            db.execute(
                """
                UPDATE communication_artifacts
                SET text_extraction_status = 'failed',
                    quarantine_reason = 'File not found on disk'
                WHERE id = ?
            """,
                (art["id"],),
            )
            failed += 1
            continue

        try:
            text = extractor(file_path)
            db.execute(
                """
                UPDATE communication_artifacts
                SET extracted_text = ?,
                    text_extraction_status = 'complete'
                WHERE id = ?
            """,
                (text, art["id"]),
            )
            extracted += 1
            logger.info(
                "[%s] Extracted %d chars from %s",
                communication_id[:8],
                len(text),
                art["original_filename"],
            )
        except Exception as e:
            logger.warning(
                "[%s] Extraction failed for %s: %s",
                communication_id[:8],
                art["original_filename"],
                e,
            )
            db.execute(
                """
                UPDATE communication_artifacts
                SET text_extraction_status = 'failed',
                    quarantine_reason = ?
                WHERE id = ?
            """,
                (str(e)[:500], art["id"]),
            )
            failed += 1

    db.commit()

    await publish_event(
        "stage_progress",
        {
            "communication_id": communication_id,
            "stage": "processing_attachments",
            "message": f"Attachment extraction: {extracted} extracted, {failed} failed, {skipped} skipped",
        },
    )

    logger.info(
        "[%s] Attachment extraction: %d extracted, %d failed, %d skipped",
        communication_id[:8],
        extracted,
        failed,
        skipped,
    )

    return {"extracted": extracted, "failed": failed, "skipped": skipped}
