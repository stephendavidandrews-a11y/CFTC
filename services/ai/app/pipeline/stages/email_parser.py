"""Email parsing stage — .eml/.msg -> communication_messages + communication_artifacts.

Pipeline position: pending -> **parsing** -> processing_attachments

Parses email files into structured messages and attachment records.
Thread detection via In-Reply-To/References headers and quoted-reply heuristics.
Deduplication via message_hash (SHA-256 of sender+timestamp+body[:200]).
"""
import email
import email.policy
import hashlib
import json
import logging
import re
import shutil
import uuid
from datetime import datetime
from email.utils import parseaddr, parsedate_to_datetime, getaddresses
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Max attachment size for extraction (50MB)
MAX_ATTACHMENT_BYTES = 50 * 1024 * 1024
# Max body text length
MAX_BODY_LENGTH = 500_000

# MIME types safe for text extraction
EXTRACTABLE_MIME_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",  # .docx
    "application/msword",  # .doc
    "text/plain",
    "text/csv",
    "text/html",
}

# Document-proposable types (can become tracker documents)
PROPOSABLE_MIME_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-excel",
}


def compute_message_hash(sender_email: str, timestamp_str: str, body_prefix: str) -> str:
    """SHA-256 hash for dedup: lowercase(sender) | timestamp | first 200 chars of body."""
    raw = f"{(sender_email or '').lower().strip()}|{timestamp_str or ''}|{(body_prefix or '')[:200]}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def _extract_body_text(msg) -> tuple[str, str]:
    """Extract plain text and HTML from email message.
    Returns (plain_text, html_text).
    """
    plain = ""
    html = ""
    if msg.is_multipart():
        for part in msg.walk():
            ct = part.get_content_type()
            if ct == "text/plain" and not plain:
                try:
                    plain = part.get_content()
                except Exception:
                    plain = str(part.get_payload(decode=True) or b"", errors="replace")
            elif ct == "text/html" and not html:
                try:
                    html = part.get_content()
                except Exception:
                    html = str(part.get_payload(decode=True) or b"", errors="replace")
    else:
        ct = msg.get_content_type()
        try:
            content = msg.get_content()
        except Exception:
            content = str(msg.get_payload(decode=True) or b"", errors="replace")
        if ct == "text/plain":
            plain = content
        elif ct == "text/html":
            html = content
    return plain, html


def _html_to_text(html: str) -> str:
    """Convert HTML to plain text. Falls back to regex stripping."""
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
        # Remove script/style elements
        for tag in soup(["script", "style"]):
            tag.decompose()
        return soup.get_text(separator="\n", strip=True)
    except ImportError:
        # Fallback: strip HTML tags
        text = re.sub(r"<[^>]+>", " ", html)
        text = re.sub(r"\s+", " ", text).strip()
        return text


def _detect_thread_messages(body_text: str, subject: str) -> list[dict]:
    """Split email body into thread messages using quoted-reply patterns.

    Returns list of message dicts ordered oldest-first (index 0 = oldest).
    Each dict: {body_text, is_quoted, quote_attribution}
    """
    # Common quoted-reply patterns
    patterns = [
        r"^-{3,}\s*Original Message\s*-{3,}",
        r"^-{3,}\s*Forwarded message\s*-{3,}",
        r"^On .+wrote:$",
        r"^From:.+\nSent:.+\nTo:.+\nSubject:",
    ]

    combined = "|".join(f"({p})" for p in patterns)

    # Try to split on quoted sections
    parts = re.split(f"({combined})", body_text, flags=re.MULTILINE | re.IGNORECASE)

    if len(parts) <= 1:
        # No thread detected -- single message
        return [{"body_text": body_text.strip()[:MAX_BODY_LENGTH], "is_quoted": False, "quote_attribution": None}]

    messages = []
    current_text = ""
    current_attribution = None

    for part in parts:
        if part is None:
            continue
        # Check if this part is a delimiter
        is_delimiter = False
        for p in patterns:
            if re.match(p, part.strip(), re.MULTILINE | re.IGNORECASE):
                is_delimiter = True
                current_attribution = part.strip()
                break

        if is_delimiter:
            if current_text.strip():
                messages.append({
                    "body_text": current_text.strip()[:MAX_BODY_LENGTH],
                    "is_quoted": len(messages) > 0,
                    "quote_attribution": None,
                })
            current_text = ""
        else:
            current_text += part

    if current_text.strip():
        messages.append({
            "body_text": current_text.strip()[:MAX_BODY_LENGTH],
            "is_quoted": len(messages) > 0,
            "quote_attribution": current_attribution,
        })

    # Reverse so oldest is first (index 0)
    messages.reverse()

    return messages if messages else [{"body_text": body_text.strip()[:MAX_BODY_LENGTH], "is_quoted": False, "quote_attribution": None}]


def parse_email_file(file_path: Path) -> dict:
    """Parse a .eml file into structured data.

    Returns dict with:
        subject, from_email, from_name, to_addresses, cc_addresses,
        sent_date, message_id, in_reply_to, references,
        messages: list[dict], attachments: list[dict]
    """
    raw_bytes = file_path.read_bytes()
    msg = email.message_from_bytes(raw_bytes, policy=email.policy.default)

    # Headers
    subject = str(msg.get("Subject", "") or "")
    from_name, from_email_addr = parseaddr(str(msg.get("From", "")))

    to_raw = str(msg.get("To", "") or "")
    cc_raw = str(msg.get("Cc", "") or "")

    to_addresses = [{"name": n, "email": e} for n, e in getaddresses([to_raw]) if e]
    cc_addresses = [{"name": n, "email": e} for n, e in getaddresses([cc_raw]) if e]

    # Date
    sent_date = None
    date_str = msg.get("Date")
    if date_str:
        try:
            sent_date = parsedate_to_datetime(str(date_str))
        except Exception:
            sent_date = None

    message_id = str(msg.get("Message-ID", "") or "").strip("<>")
    in_reply_to = str(msg.get("In-Reply-To", "") or "").strip("<>")
    references_raw = str(msg.get("References", "") or "")
    references = [r.strip("<>") for r in references_raw.split() if r.strip("<>")]

    # Body
    plain_text, html_text = _extract_body_text(msg)
    body_text = plain_text if plain_text else _html_to_text(html_text) if html_text else ""

    # Thread detection
    thread_messages = _detect_thread_messages(body_text, subject)

    # Build message records
    messages = []
    sent_str = sent_date.isoformat() if sent_date else None

    for idx, thread_msg in enumerate(thread_messages):
        msg_hash = compute_message_hash(
            from_email_addr if idx == len(thread_messages) - 1 else "",
            sent_str if idx == len(thread_messages) - 1 else "",
            thread_msg["body_text"],
        )
        messages.append({
            "message_index": idx,
            "sender_email": from_email_addr if idx == len(thread_messages) - 1 else None,
            "sender_name": from_name if idx == len(thread_messages) - 1 else None,
            "recipient_emails": json.dumps([a["email"] for a in to_addresses]) if idx == len(thread_messages) - 1 else None,
            "cc_emails": json.dumps([a["email"] for a in cc_addresses]) if idx == len(thread_messages) - 1 else None,
            "timestamp": sent_str if idx == len(thread_messages) - 1 else None,
            "subject": subject,
            "body_text": thread_msg["body_text"],
            "message_hash": msg_hash,
            "is_new": 0 if thread_msg["is_quoted"] else 1,
        })

    # Attachments
    attachments = []
    if msg.is_multipart():
        for part in msg.walk():
            cd = part.get("Content-Disposition")
            if cd and "attachment" in str(cd).lower():
                filename = part.get_filename() or f"attachment_{len(attachments)}"
                payload = part.get_payload(decode=True)
                if payload:
                    mime_type = part.get_content_type()
                    attachments.append({
                        "original_filename": filename,
                        "mime_type": mime_type,
                        "file_size_bytes": len(payload),
                        "payload": payload,
                        "is_document_proposable": 1 if mime_type in PROPOSABLE_MIME_TYPES else 0,
                    })
            # Also check for inline images / embedded content with filenames
            elif part.get_filename():
                filename = part.get_filename()
                payload = part.get_payload(decode=True)
                if payload and len(payload) > 100:  # Skip tiny inline images
                    mime_type = part.get_content_type()
                    attachments.append({
                        "original_filename": filename,
                        "mime_type": mime_type,
                        "file_size_bytes": len(payload),
                        "payload": payload,
                        "is_document_proposable": 1 if mime_type in PROPOSABLE_MIME_TYPES else 0,
                    })

    return {
        "subject": subject,
        "from_email": from_email_addr,
        "from_name": from_name,
        "to_addresses": to_addresses,
        "cc_addresses": cc_addresses,
        "sent_date": sent_str,
        "message_id": message_id,
        "in_reply_to": in_reply_to,
        "references": references,
        "messages": messages,
        "attachments": attachments,
    }


async def run_email_parsing_stage(db, communication_id: str) -> dict:
    """Execute the email parsing stage.

    Reads the source .eml file, parses it, writes communication_messages
    and communication_artifacts, checks for duplicates.

    Returns dict with parse results.
    """
    from app.config import AI_UPLOAD_DIR, load_policy
    from app.routers.events import publish_event

    comm = db.execute(
        "SELECT source_path, original_filename FROM communications WHERE id = ?",
        (communication_id,),
    ).fetchone()
    if not comm:
        raise RuntimeError(f"Communication {communication_id} not found")

    source_path = Path(comm["source_path"])
    if not source_path.exists():
        raise FileNotFoundError(f"Email file not found: {source_path}")

    await publish_event("stage_progress", {
        "communication_id": communication_id,
        "stage": "parsing",
        "message": f"Parsing {comm['original_filename']}...",
    })

    # Parse the email
    parsed = parse_email_file(source_path)

    # Update communication title from subject
    db.execute("""
        UPDATE communications
        SET title = COALESCE(title, ?),
            source_metadata = ?,
            updated_at = datetime('now')
        WHERE id = ?
    """, (
        parsed["subject"],
        json.dumps({
            "message_id": parsed["message_id"],
            "in_reply_to": parsed["in_reply_to"],
            "references": parsed["references"],
            "from_email": parsed["from_email"],
            "from_name": parsed["from_name"],
            "to_count": len(parsed["to_addresses"]),
            "cc_count": len(parsed["cc_addresses"]),
            "attachment_count": len(parsed["attachments"]),
            "thread_message_count": len(parsed["messages"]),
        }),
        communication_id,
    ))

    # Check user email config for is_from_user
    policy = load_policy()
    user_emails = {e.lower() for e in policy.get("user_config", {}).get("email_addresses", [])}

    # Write messages
    new_message_count = 0
    duplicate_message_count = 0

    for msg_data in parsed["messages"]:
        msg_id = str(uuid.uuid4())

        # Check dedup
        existing = db.execute(
            "SELECT id FROM communication_messages WHERE message_hash = ?",
            (msg_data["message_hash"],),
        ).fetchone()

        is_new = msg_data["is_new"]
        if existing:
            # Message body already seen in another communication
            is_new = 0
            duplicate_message_count += 1
        elif is_new:
            new_message_count += 1

        is_from_user = 1 if (msg_data.get("sender_email") or "").lower() in user_emails else 0

        db.execute("""
            INSERT INTO communication_messages
                (id, communication_id, message_index, sender_email, sender_name,
                 recipient_emails, cc_emails, timestamp, subject, body_text,
                 message_hash, is_new, is_from_user, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
        """, (
            msg_id, communication_id, msg_data["message_index"],
            msg_data["sender_email"], msg_data["sender_name"],
            msg_data["recipient_emails"], msg_data["cc_emails"],
            msg_data["timestamp"], msg_data["subject"],
            msg_data["body_text"], msg_data["message_hash"],
            is_new, is_from_user,
        ))

    # Save attachments to disk and write artifact records
    storage_dir = AI_UPLOAD_DIR / communication_id / "attachments"
    storage_dir.mkdir(parents=True, exist_ok=True)

    for att in parsed["attachments"]:
        att_id = str(uuid.uuid4())
        safe_name = re.sub(r'[^\w\-_\.]', '_', att["original_filename"])
        att_path = storage_dir / f"{att_id}_{safe_name}"

        # Size check
        quarantine_reason = None
        if att["file_size_bytes"] > MAX_ATTACHMENT_BYTES:
            quarantine_reason = f"File too large: {att['file_size_bytes']} bytes (max {MAX_ATTACHMENT_BYTES})"

        # Write file
        att_path.write_bytes(att["payload"])

        db.execute("""
            INSERT INTO communication_artifacts
                (id, communication_id, original_filename, mime_type, file_size_bytes,
                 file_path, artifact_type, text_extraction_status, is_document_proposable,
                 quarantine_reason, created_at)
            VALUES (?, ?, ?, ?, ?, ?, 'attachment', ?, ?, ?, datetime('now'))
        """, (
            att_id, communication_id, att["original_filename"],
            att["mime_type"], att["file_size_bytes"], str(att_path),
            "quarantined" if quarantine_reason else "pending",
            att["is_document_proposable"],
            quarantine_reason,
        ))

    db.commit()

    # Check if ALL messages are duplicates -> mark communication as duplicate
    if new_message_count == 0 and len(parsed["messages"]) > 0:
        logger.info("[%s] All %d messages are duplicates -- marking as duplicate",
                    communication_id[:8], len(parsed["messages"]))
        return {"is_duplicate": True, "messages": len(parsed["messages"]), "attachments": len(parsed["attachments"])}

    await publish_event("stage_progress", {
        "communication_id": communication_id,
        "stage": "parsing",
        "message": f"Parsed: {new_message_count} new messages, {len(parsed['attachments'])} attachments",
    })

    logger.info(
        "[%s] Email parsing complete: %d messages (%d new, %d dup), %d attachments",
        communication_id[:8], len(parsed["messages"]),
        new_message_count, duplicate_message_count, len(parsed["attachments"]),
    )

    return {
        "is_duplicate": False,
        "messages": len(parsed["messages"]),
        "new_messages": new_message_count,
        "duplicate_messages": duplicate_message_count,
        "attachments": len(parsed["attachments"]),
    }
