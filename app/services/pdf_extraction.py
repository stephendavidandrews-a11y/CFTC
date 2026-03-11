"""PDF text extraction service.

Extracts text from PDF files using:
1. pdfplumber (for text-based PDFs) — fast and accurate
2. Tesseract OCR (for image-based/scanned PDFs) — slower, best-effort

Flags low-confidence extractions for manual review.
"""

import io
import logging
import tempfile
from pathlib import Path
from dataclasses import dataclass
from typing import Optional

import pdfplumber

logger = logging.getLogger(__name__)


@dataclass
class ExtractionResult:
    """Result of a PDF text extraction."""
    text: str
    page_count: int
    method: str  # "text", "ocr", "mixed", "failed"
    confidence: float  # 0.0 - 1.0
    error: Optional[str] = None


def extract_text_from_pdf(pdf_bytes: bytes) -> ExtractionResult:
    """Extract text from a PDF file (provided as bytes).

    Strategy:
    1. Try pdfplumber first (handles text-based PDFs)
    2. If that yields very little text, fall back to OCR
    3. Report confidence score based on extraction quality
    """
    if not pdf_bytes:
        return ExtractionResult(
            text="", page_count=0, method="failed", confidence=0.0,
            error="Empty PDF bytes"
        )

    # Step 1: Try text extraction with pdfplumber
    try:
        text, page_count = _extract_with_pdfplumber(pdf_bytes)
    except Exception as e:
        logger.warning(f"pdfplumber extraction failed: {e}")
        text, page_count = "", 0

    if text and _text_quality_score(text, page_count) > 0.5:
        confidence = _text_quality_score(text, page_count)
        return ExtractionResult(
            text=text.strip(),
            page_count=page_count,
            method="text",
            confidence=min(confidence, 1.0),
        )

    # Step 2: Fall back to OCR
    logger.info("Low text quality from pdfplumber, attempting OCR...")
    try:
        ocr_text, ocr_pages = _extract_with_ocr(pdf_bytes)
        if ocr_text:
            confidence = _text_quality_score(ocr_text, ocr_pages) * 0.8  # OCR penalty
            return ExtractionResult(
                text=ocr_text.strip(),
                page_count=ocr_pages or page_count,
                method="ocr",
                confidence=min(confidence, 1.0),
            )
    except Exception as e:
        logger.warning(f"OCR extraction failed: {e}")

    # Step 3: Return whatever we have, even if low quality
    if text:
        return ExtractionResult(
            text=text.strip(),
            page_count=page_count,
            method="text",
            confidence=_text_quality_score(text, page_count),
        )

    return ExtractionResult(
        text="", page_count=page_count, method="failed", confidence=0.0,
        error="Could not extract text via pdfplumber or OCR"
    )


def _extract_with_pdfplumber(pdf_bytes: bytes) -> tuple[str, int]:
    """Extract text using pdfplumber (works on text-based PDFs)."""
    pages_text = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        page_count = len(pdf.pages)
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                pages_text.append(text)
    return "\n\n".join(pages_text), page_count


def _extract_with_ocr(pdf_bytes: bytes) -> tuple[str, int]:
    """Extract text using Tesseract OCR (for scanned/image PDFs).

    Requires: tesseract, pdf2image (poppler-utils)
    """
    try:
        from pdf2image import convert_from_bytes
        import pytesseract
    except ImportError:
        logger.error("OCR dependencies not installed (pdf2image, pytesseract)")
        return "", 0

    # Convert PDF pages to images
    with tempfile.TemporaryDirectory() as tmpdir:
        images = convert_from_bytes(pdf_bytes, dpi=300, output_folder=tmpdir)
        page_count = len(images)

        pages_text = []
        for img in images:
            text = pytesseract.image_to_string(img)
            if text.strip():
                pages_text.append(text)

    return "\n\n".join(pages_text), page_count


def _text_quality_score(text: str, page_count: int) -> float:
    """Heuristic score for text extraction quality (0.0 - 1.0).

    A good extraction should have a reasonable amount of text per page,
    mostly ASCII characters, and recognizable word patterns.
    """
    if not text or page_count == 0:
        return 0.0

    # Characters per page (a normal page of text has ~2000-3000 chars)
    chars_per_page = len(text) / max(page_count, 1)
    if chars_per_page < 100:
        return 0.1  # Almost certainly a bad extraction
    if chars_per_page < 500:
        return 0.3

    # Ratio of printable ASCII characters
    printable = sum(1 for c in text if c.isprintable() or c in '\n\t')
    ascii_ratio = printable / len(text)

    # Word-like tokens (at least 3 chars with letters)
    tokens = text.split()
    word_like = sum(1 for t in tokens if len(t) >= 3 and any(c.isalpha() for c in t))
    word_ratio = word_like / max(len(tokens), 1)

    # Composite score
    score = 0.4 * min(chars_per_page / 2000, 1.0) + 0.3 * ascii_ratio + 0.3 * word_ratio
    return round(score, 2)


def count_pdf_pages(pdf_bytes: bytes) -> int:
    """Quick page count without full text extraction."""
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            return len(pdf.pages)
    except Exception:
        return 0
