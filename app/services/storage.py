"""Local filesystem storage for PDF files and attachments.

Stores PDFs in a local directory. Can be swapped for S3 later.
"""

import logging
import os
from pathlib import Path
from typing import Optional

from app.core.config import settings

logger = logging.getLogger(__name__)

# Default to a 'pdf_storage' directory next to the app
DEFAULT_STORAGE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "pdf_storage")


class StorageService:
    """Handles uploading and retrieving PDFs from local filesystem."""

    def __init__(self):
        self._base_dir = Path(getattr(settings, "PDF_STORAGE_DIR", DEFAULT_STORAGE_DIR))
        self._base_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"PDF storage directory: {self._base_dir}")

    def upload_pdf(self, key: str, pdf_bytes: bytes, content_type: str = "application/pdf") -> str:
        """Save a PDF to local filesystem."""
        file_path = self._base_dir / key
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_bytes(pdf_bytes)
        logger.debug(f"Saved {len(pdf_bytes)} bytes to {file_path}")
        return key

    def download_pdf(self, key: str) -> Optional[bytes]:
        """Read a PDF from local filesystem."""
        file_path = self._base_dir / key
        if not file_path.exists():
            logger.error(f"PDF not found: {file_path}")
            return None
        return file_path.read_bytes()

    def pdf_exists(self, key: str) -> bool:
        """Check if a PDF exists in storage."""
        return (self._base_dir / key).exists()

    def build_comment_pdf_key(self, docket_number: str, document_id: str, filename: str = "comment.pdf") -> str:
        """Build a standardized storage key for a comment PDF."""
        safe_docket = docket_number.replace("/", "-")
        safe_doc_id = document_id.replace("/", "-")
        return f"comments/{safe_docket}/{safe_doc_id}/{filename}"

    def get_storage_stats(self) -> dict:
        """Get storage usage stats."""
        total_files = 0
        total_bytes = 0
        for f in self._base_dir.rglob("*.pdf"):
            total_files += 1
            total_bytes += f.stat().st_size
        return {
            "directory": str(self._base_dir),
            "total_pdfs": total_files,
            "total_size_mb": round(total_bytes / (1024 * 1024), 1),
        }


# Module-level convenience instance
storage_service = StorageService()
