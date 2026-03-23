"""SMTP email sender for intelligence briefs.

Sends HTML email with optional .docx attachment.
Uses same SMTP config pattern as Sauron morning email.
"""
import logging
import os
import smtplib
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

logger = logging.getLogger(__name__)

SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASS = os.environ.get("SMTP_PASS", os.environ.get("SMTP_PASSWORD", ""))
SMTP_FROM = os.environ.get("SMTP_FROM", f"CFTC AI <{SMTP_USER}>")
BRIEF_RECIPIENT = os.environ.get("BRIEF_RECIPIENT", "email@stephenandrews.org")


def send_email(
    subject: str,
    html_body: str,
    docx_path: str | Path | None = None,
    recipient: str | None = None,
    plain_text: str | None = None,
) -> bool:
    """Send an HTML email with optional .docx attachment.

    Args:
        subject: Email subject line.
        html_body: HTML content of the email.
        docx_path: Optional path to .docx file to attach.
        recipient: Override recipient (defaults to BRIEF_RECIPIENT).
        plain_text: Optional plain-text fallback.

    Returns:
        True on success, False on failure.
    """
    to_addr = recipient or BRIEF_RECIPIENT
    if not SMTP_USER or not SMTP_PASS:
        logger.error("SMTP credentials not configured. Set SMTP_USER and SMTP_PASS.")
        return False

    msg = MIMEMultipart("mixed")
    msg["Subject"] = subject
    msg["From"] = SMTP_FROM
    msg["To"] = to_addr

    # HTML body (with plain-text fallback)
    alt = MIMEMultipart("alternative")
    if plain_text:
        alt.attach(MIMEText(plain_text, "plain", "utf-8"))
    alt.attach(MIMEText(html_body, "html", "utf-8"))
    msg.attach(alt)

    # Optional .docx attachment
    if docx_path:
        docx_path = Path(docx_path)
        if docx_path.exists():
            with open(docx_path, "rb") as f:
                att = MIMEApplication(f.read(), _subtype="vnd.openxmlformats-officedocument.wordprocessingml.document")
                att.add_header("Content-Disposition", "attachment", filename=docx_path.name)
                msg.attach(att)
            logger.info("Attached %s (%d bytes)", docx_path.name, docx_path.stat().st_size)
        else:
            logger.warning("DOCX not found: %s", docx_path)

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(SMTP_USER, [to_addr], msg.as_string())
        logger.info("Email sent: '%s' -> %s", subject, to_addr)
        return True
    except Exception as e:
        logger.error("Email send failed: %s", e)
        return False
