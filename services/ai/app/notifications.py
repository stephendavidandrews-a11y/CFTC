"""Pipeline error notification — email alerts on communication failures.

Debounces multiple errors within a window into a single email.
Gracefully skips if SMTP is not configured.
"""

import os
import logging
import smtplib
import threading
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

logger = logging.getLogger(__name__)

# SMTP configuration (from environment, same vars as tracker)
SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASS = os.environ.get("SMTP_PASS", "")
FROM_EMAIL = os.environ.get("FROM_EMAIL", "") or SMTP_USER
MANAGER_EMAIL = os.environ.get("MANAGER_EMAIL", "")

# Debounce: batch errors within this window
DEBOUNCE_SECONDS = 900  # 15 minutes

# In-memory error buffer for debouncing
_error_buffer: list[dict] = []
_last_sent: datetime | None = None
_lock = threading.Lock()


def notify_pipeline_error(
    communication_id: str,
    title: str | None,
    error_stage: str,
    error_message: str,
    target_state: str = "error",
):
    """Queue an error notification. Sends immediately or batches within debounce window.

    Args:
        communication_id: The failed communication
        title: Communication title (for human reference)
        error_stage: Pipeline stage where failure occurred
        error_message: Error description
        target_state: The state transitioned to (error, waiting_for_api, awaiting_tracker)
    """
    global _last_sent

    entry = {
        "communication_id": communication_id,
        "title": title or "(untitled)",
        "error_stage": error_stage,
        "error_message": (error_message or "")[:500],
        "target_state": target_state,
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }

    with _lock:
        _error_buffer.append(entry)

        # If last email was within debounce window, let the buffer accumulate
        if (
            _last_sent
            and (datetime.utcnow() - _last_sent).total_seconds() < DEBOUNCE_SECONDS
        ):
            logger.debug(
                "Error notification buffered (debounce): %s at %s",
                communication_id[:8],
                error_stage,
            )
            return

        # Otherwise, flush the buffer
        errors_to_send = list(_error_buffer)
        _error_buffer.clear()
        _last_sent = datetime.utcnow()

    _send_error_email(errors_to_send)


def flush_error_buffer():
    """Force-flush any buffered errors. Returns count of errors sent."""
    with _lock:
        if not _error_buffer:
            return 0
        errors = list(_error_buffer)
        _error_buffer.clear()
    _send_error_email(errors)
    return len(errors)


def get_buffer_status() -> dict:
    """Return current buffer state for health/debug endpoints."""
    with _lock:
        return {
            "buffered_errors": len(_error_buffer),
            "last_sent": _last_sent.isoformat() + "Z" if _last_sent else None,
            "smtp_configured": bool(SMTP_USER and SMTP_PASS and MANAGER_EMAIL),
        }


def _send_error_email(errors: list[dict]):
    """Send an error notification email. Gracefully skips if SMTP not configured."""
    if not errors:
        return

    if not SMTP_USER or not SMTP_PASS:
        logger.info(
            "Pipeline error notification (SMTP not configured — logged only): %d errors",
            len(errors),
        )
        for e in errors:
            logger.warning(
                "  [%s] %s at %s → %s: %s",
                e["communication_id"][:8],
                e["title"][:30],
                e["error_stage"],
                e["target_state"],
                e["error_message"][:80],
            )
        return

    if not MANAGER_EMAIL:
        logger.warning("Pipeline error notification: MANAGER_EMAIL not set — skipping")
        return

    # Build email
    subject = "CFTC AI: %d pipeline error%s" % (
        len(errors),
        "s" if len(errors) > 1 else "",
    )

    rows = ""
    for e in errors:
        rows += (
            "<tr>"
            "<td style='padding:6px;border-bottom:1px solid #333'>%s</td>"
            "<td style='padding:6px;border-bottom:1px solid #333'>%s</td>"
            "<td style='padding:6px;border-bottom:1px solid #333'>%s</td>"
            "<td style='padding:6px;border-bottom:1px solid #333'>%s</td>"
            "<td style='padding:6px;border-bottom:1px solid #333;font-size:12px'>%s</td>"
            "</tr>"
        ) % (
            e["communication_id"][:12],
            e["title"][:40],
            e["error_stage"],
            e["target_state"],
            e["error_message"][:120],
        )

    html = """
    <div style="font-family:system-ui;background:#0a0f1a;color:#e5e7eb;padding:20px">
      <h2 style="color:#f87171">Pipeline Error Alert</h2>
      <p>%d communication%s encountered errors:</p>
      <table style="width:100%%;border-collapse:collapse;font-size:13px">
        <tr style="color:#9ca3af">
          <th style="text-align:left;padding:6px">Communication</th>
          <th style="text-align:left;padding:6px">Title</th>
          <th style="text-align:left;padding:6px">Stage</th>
          <th style="text-align:left;padding:6px">State</th>
          <th style="text-align:left;padding:6px">Error</th>
        </tr>
        %s
      </table>
      <p style="color:#6b7280;font-size:12px;margin-top:16px">
        Generated at %s by CFTC AI Layer
      </p>
    </div>
    """ % (
        len(errors),
        "s" if len(errors) > 1 else "",
        rows,
        datetime.utcnow().isoformat() + "Z",
    )

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = FROM_EMAIL
    msg["To"] = MANAGER_EMAIL
    msg.attach(MIMEText(html, "html"))

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.send_message(msg)
        logger.info(
            "Pipeline error email sent: %d errors → %s", len(errors), MANAGER_EMAIL
        )
    except Exception as e:
        logger.error("Pipeline error email FAILED: %s", e)
        # Log errors to stdout so they're not lost
        for err in errors:
            logger.warning(
                "  [UNSENT] %s at %s: %s",
                err["communication_id"][:8],
                err["error_stage"],
                err["error_message"][:80],
            )
