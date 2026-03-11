"""
Email notification service: SMTP sending, template building, and logging.

Sends automated status updates, bottleneck alerts, note digests,
and contact reminders to the manager.
"""

import os
import json
import smtplib
import logging
from datetime import date, datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

logger = logging.getLogger(__name__)

# Configuration from environment
SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASS = os.environ.get("SMTP_PASS", "")
FROM_EMAIL = os.environ.get("FROM_EMAIL", "") or SMTP_USER
MANAGER_EMAIL = os.environ.get("MANAGER_EMAIL", "")

# Common styling
_STYLE = """
<style>
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
         background: #0a0f1a; color: #e2e8f0; margin: 0; padding: 20px; }
  .container { max-width: 700px; margin: 0 auto; }
  h1 { color: #60a5fa; font-size: 20px; border-bottom: 1px solid #1e3a5f; padding-bottom: 8px; }
  h2 { color: #93c5fd; font-size: 16px; margin-top: 24px; }
  .card { background: #111827; border-radius: 8px; padding: 12px 16px; margin: 8px 0;
          border-left: 3px solid #3b82f6; }
  .card.alert { border-left-color: #ef4444; }
  .card.warning { border-left-color: #f59e0b; }
  .card.success { border-left-color: #10b981; }
  .badge { display: inline-block; padding: 2px 8px; border-radius: 4px;
           font-size: 12px; font-weight: 600; }
  .badge-red { background: #7f1d1d; color: #fca5a5; }
  .badge-yellow { background: #78350f; color: #fcd34d; }
  .badge-green { background: #064e3b; color: #6ee7b7; }
  .badge-blue { background: #1e3a5f; color: #93c5fd; }
  .meta { color: #9ca3af; font-size: 13px; }
  ul { padding-left: 20px; }
  li { margin: 4px 0; }
  .footer { color: #6b7280; font-size: 12px; margin-top: 32px;
            border-top: 1px solid #1e3a5f; padding-top: 12px; }
</style>
"""


def send_email(to: list[str], subject: str, html_body: str, text_body: str = "") -> dict:
    """Send an email via SMTP. Returns status dict."""
    if not SMTP_USER or not SMTP_PASS:
        logger.warning("SMTP not configured — email not sent: %s", subject)
        return {"status": "skipped", "reason": "SMTP not configured"}

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = FROM_EMAIL
    msg["To"] = ", ".join(to)

    if text_body:
        msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.send_message(msg)
        logger.info("Email sent: %s → %s", subject, to)
        return {"status": "sent"}
    except Exception as e:
        logger.error("Email send failed: %s — %s", subject, e)
        return {"status": "failed", "error": str(e)}


def log_email(conn, email_type: str, recipients: list[str], subject: str,
              body_html: str, status: str, error: str = None):
    """Log an email send attempt to email_log table."""
    conn.execute(
        """INSERT INTO email_log (email_type, recipients, subject, body_html, status, error_message)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (email_type, json.dumps(recipients), subject, body_html, status, error),
    )
    conn.commit()


# ---------------------------------------------------------------------------
# Status Email (Mon/Wed/Fri 6 AM)
# ---------------------------------------------------------------------------

def build_status_email(pipeline_conn, work_conn) -> dict:
    """Build the tri-weekly status email. Returns {subject, html, text}."""
    today = date.today()
    today_str = today.strftime("%A, %B %d, %Y")

    # Gather data
    from app.pipeline.services.team import list_members, get_workload
    from app.pipeline.services.interagency import list_rulemakings

    members = list_members(pipeline_conn, active_only=True)
    rulemakings = list_rulemakings(pipeline_conn, status="active")

    # Get work projects and items
    projects = work_conn.execute(
        "SELECT * FROM projects WHERE status != 'completed' ORDER BY priority_label, title"
    ).fetchall()

    # Items needing attention
    attention_items = work_conn.execute(
        """SELECT wi.*, p.title as project_title FROM work_items wi
           JOIN projects p ON wi.project_id = p.id
           WHERE wi.status IN ('waiting_on_stephen', 'in_review')
             AND wi.status != 'completed'
           ORDER BY wi.due_date ASC"""
    ).fetchall()

    # Overdue items
    overdue_items = work_conn.execute(
        """SELECT wi.*, p.title as project_title FROM work_items wi
           JOIN projects p ON wi.project_id = p.id
           WHERE wi.due_date < ? AND wi.status NOT IN ('completed')
           ORDER BY wi.due_date ASC""",
        (today.isoformat(),)
    ).fetchall()

    # Build HTML
    html_parts = [f"""<html><head>{_STYLE}</head><body><div class="container">
        <h1>Status Update — {today_str}</h1>"""]

    # Needs your action section
    if attention_items:
        html_parts.append("<h2>Needs Your Action</h2>")
        for item in attention_items:
            d = dict(item)
            cls = "alert" if d["status"] == "waiting_on_stephen" else "warning"
            badge = "Waiting on You" if d["status"] == "waiting_on_stephen" else "In Review"
            html_parts.append(f"""<div class="card {cls}">
                <strong>{d['title']}</strong>
                <span class="badge badge-red">{badge}</span>
                <div class="meta">{d.get('project_title', '')} · Due: {d.get('due_date', 'N/A')}</div>
                {f'<div class="meta">{d["last_update_notes"]}</div>' if d.get("last_update_notes") else ''}
            </div>""")

    # Overdue section
    if overdue_items:
        html_parts.append("<h2>Overdue</h2>")
        for item in overdue_items:
            d = dict(item)
            days = (today - date.fromisoformat(d["due_date"])).days
            html_parts.append(f"""<div class="card alert">
                <strong>{d['title']}</strong>
                <span class="badge badge-red">{days}d overdue</span>
                <div class="meta">{d.get('project_title', '')}</div>
            </div>""")

    # Active projects
    if projects:
        html_parts.append("<h2>Your Projects</h2>")
        for proj in projects:
            p = dict(proj)
            # Count items
            total = work_conn.execute(
                "SELECT COUNT(*) FROM work_items WHERE project_id = ?", (p["id"],)
            ).fetchone()[0]
            completed = work_conn.execute(
                "SELECT COUNT(*) FROM work_items WHERE project_id = ? AND status = 'completed'",
                (p["id"],)
            ).fetchone()[0]
            pct = round(completed / total * 100) if total > 0 else 0
            source_badge = f'<span class="badge badge-blue">{p["source"]}</span>' if p.get("source") else ""
            html_parts.append(f"""<div class="card">
                <strong>{p['title']}</strong> {source_badge}
                <div class="meta">Progress: {completed}/{total} ({pct}%) · Priority: {p.get('priority_label', 'medium')}
                {f" · Due: {p['due_date']}" if p.get('due_date') else ''}</div>
            </div>""")

    # Team workload summary
    html_parts.append("<h2>Team Workload</h2>")
    for m in members:
        workload = get_workload(pipeline_conn, m["id"])
        if workload:
            cap = m.get("current_capacity", "available")
            cap_class = {"overloaded": "badge-red", "at_capacity": "badge-yellow",
                         "stretched": "badge-yellow"}.get(cap, "badge-green")
            html_parts.append(f"""<div class="card">
                <strong>{m['name']}</strong>
                <span class="badge {cap_class}">{cap.replace('_', ' ').title()}</span>
                <div class="meta">{workload['active_items']} active · {workload['overdue_deadlines']} overdue
                · {workload['capacity_remaining']} capacity remaining</div>
            </div>""")

    # Interagency rulemakings
    if rulemakings:
        html_parts.append("<h2>Interagency Activity</h2>")
        for rm in rulemakings[:5]:
            html_parts.append(f"""<div class="card">
                <strong>{rm['title']}</strong>
                <span class="badge badge-blue">{rm['agency']}</span>
                <div class="meta">Status: {rm['status']}
                {f" · Position: {rm['cftc_position']}" if rm.get('cftc_position') else ''}</div>
            </div>""")

    html_parts.append(f"""<div class="footer">
        Generated by CFTC Pipeline Manager · {datetime.now().strftime('%I:%M %p ET')}
    </div></div></body></html>""")

    html = "\n".join(html_parts)
    subject = f"CFTC Status Update — {today.strftime('%A, %m/%d')}"

    return {"subject": subject, "html": html, "text": ""}


# ---------------------------------------------------------------------------
# Bottleneck Alert (Daily 7 AM)
# ---------------------------------------------------------------------------

def build_bottleneck_alert(work_conn) -> dict | None:
    """Build bottleneck alert. Returns None if no bottlenecks."""
    today = date.today()

    blocked = work_conn.execute(
        """SELECT wi.*, p.title as project_title FROM work_items wi
           JOIN projects p ON wi.project_id = p.id
           WHERE wi.status IN ('waiting_on_stephen', 'in_review')
             AND wi.status != 'completed'
           ORDER BY wi.due_date ASC"""
    ).fetchall()

    if not blocked:
        return None

    today_str = today.strftime("%A, %B %d")
    count = len(blocked)
    html_parts = [f"""<html><head>{_STYLE}</head><body><div class="container">
        <h1>Bottleneck Alert — {today_str}</h1>
        <p>You are blocking <strong>{count}</strong> item{'s' if count != 1 else ''}.</p>"""]

    # In review items
    in_review = [dict(b) for b in blocked if b["status"] == "in_review"]
    if in_review:
        html_parts.append("<h2>Needs Your Review</h2>")
        for item in in_review:
            days_waiting = ""
            if item.get("last_update_date"):
                try:
                    d = (today - date.fromisoformat(item["last_update_date"])).days
                    days_waiting = f" · Waiting {d}d"
                except (ValueError, TypeError):
                    pass
            html_parts.append(f"""<div class="card warning">
                <strong>{item['title']}</strong>
                <div class="meta">{item.get('project_title', '')}{days_waiting}
                {f" · Due: {item['due_date']}" if item.get('due_date') else ''}</div>
                {f'<div class="meta">Notes: {item["last_update_notes"]}</div>' if item.get("last_update_notes") else ''}
            </div>""")

    # Waiting on Stephen items
    waiting = [dict(b) for b in blocked if b["status"] == "waiting_on_stephen"]
    if waiting:
        html_parts.append("<h2>Waiting on Your Input</h2>")
        for item in waiting:
            days_waiting = ""
            if item.get("last_update_date"):
                try:
                    d = (today - date.fromisoformat(item["last_update_date"])).days
                    days_waiting = f" · Waiting {d}d"
                except (ValueError, TypeError):
                    pass
            html_parts.append(f"""<div class="card alert">
                <strong>{item['title']}</strong>
                <div class="meta">{item.get('project_title', '')}{days_waiting}
                {f" · Due: {item['due_date']}" if item.get('due_date') else ''}</div>
                {f'<div class="meta">Needs: {item["last_update_notes"]}</div>' if item.get("last_update_notes") else ''}
            </div>""")

    html_parts.append(f"""<div class="footer">
        Generated by CFTC Pipeline Manager · {datetime.now().strftime('%I:%M %p ET')}
    </div></div></body></html>""")

    html = "\n".join(html_parts)
    subject = f"Bottleneck Alert — You're blocking {count} item{'s' if count != 1 else ''}"

    return {"subject": subject, "html": html, "text": ""}


# ---------------------------------------------------------------------------
# Note Digest (Sunday 8 PM)
# ---------------------------------------------------------------------------

def build_note_digest(work_conn, insights: list[dict]) -> dict | None:
    """Build weekly note processing digest. Returns None if no insights."""
    if not insights:
        return None

    today_str = date.today().strftime("%B %d, %Y")
    html_parts = [f"""<html><head>{_STYLE}</head><body><div class="container">
        <h1>Weekly Insights — {today_str}</h1>
        <p>Processed <strong>{len(insights)}</strong> note{'s' if len(insights) != 1 else ''} this week.</p>"""]

    for insight in insights:
        html_parts.append(f"""<div class="card success">
            <strong>{insight.get('member_name', 'Unknown')}</strong>
            <div class="meta">{insight.get('context_type', 'general')} · {insight.get('created_at', '')}</div>
            <div>{insight.get('ai_insights', '')}</div>
        </div>""")

    html_parts.append(f"""<div class="footer">
        All insights added to team member profiles.
    </div></div></body></html>""")

    html = "\n".join(html_parts)
    subject = f"Weekly Insights — {len(insights)} notes processed"

    return {"subject": subject, "html": html, "text": ""}


# ---------------------------------------------------------------------------
# Contact Reminder (Sunday 8 PM)
# ---------------------------------------------------------------------------

def build_contact_reminder(dormant_contacts: list[dict]) -> dict | None:
    """Build relationship check-in reminder. Returns None if no dormant contacts."""
    if not dormant_contacts:
        return None

    count = len(dormant_contacts)
    html_parts = [f"""<html><head>{_STYLE}</head><body><div class="container">
        <h1>Interagency Relationship Check-in</h1>
        <p><strong>{count}</strong> key contact{'s' if count != 1 else ''} you haven't reached out to recently.</p>"""]

    for contact in dormant_contacts[:5]:
        days = contact.get("days_since_contact")
        days_str = f"{days}d ago" if days else "Never contacted"
        html_parts.append(f"""<div class="card warning">
            <strong>{contact['name']}</strong>
            <span class="badge badge-blue">{contact['agency']}</span>
            <div class="meta">{contact.get('title', '')} · Last contact: {days_str}</div>
            <div class="meta">Focus: {', '.join(contact.get('areas_of_focus', []))}</div>
            {f'<div class="meta">{contact["notes"]}</div>' if contact.get("notes") else ''}
        </div>""")

    html_parts.append(f"""<div class="footer">
        Relationship maintenance builds coordination channels for when you need them.
    </div></div></body></html>""")

    html = "\n".join(html_parts)
    subject = f"Interagency Check-in — {count} contact{'s' if count != 1 else ''} to reach"

    return {"subject": subject, "html": html, "text": ""}


# ---------------------------------------------------------------------------
# Orchestration functions (called by schedulers)
# ---------------------------------------------------------------------------

def send_status_email(pipeline_conn, work_conn) -> dict:
    """Build and send the status email."""
    email_data = build_status_email(pipeline_conn, work_conn)
    recipients = [MANAGER_EMAIL] if MANAGER_EMAIL else []
    if not recipients:
        return {"status": "skipped", "reason": "No MANAGER_EMAIL configured"}

    result = send_email(recipients, email_data["subject"], email_data["html"])
    log_email(pipeline_conn, "status_update", recipients, email_data["subject"],
              email_data["html"], result["status"], result.get("error"))
    return result


def send_bottleneck_alert(pipeline_conn, work_conn) -> dict:
    """Build and send bottleneck alert if needed."""
    email_data = build_bottleneck_alert(work_conn)
    if not email_data:
        return {"status": "skipped", "reason": "No bottlenecks"}

    recipients = [MANAGER_EMAIL] if MANAGER_EMAIL else []
    if not recipients:
        return {"status": "skipped", "reason": "No MANAGER_EMAIL configured"}

    result = send_email(recipients, email_data["subject"], email_data["html"])
    log_email(pipeline_conn, "bottleneck_alert", recipients, email_data["subject"],
              email_data["html"], result["status"], result.get("error"))
    return result


def send_note_digest(pipeline_conn, insights: list[dict]) -> dict:
    """Build and send note processing digest."""
    email_data = build_note_digest(None, insights)
    if not email_data:
        return {"status": "skipped", "reason": "No insights to report"}

    recipients = [MANAGER_EMAIL] if MANAGER_EMAIL else []
    if not recipients:
        return {"status": "skipped", "reason": "No MANAGER_EMAIL configured"}

    result = send_email(recipients, email_data["subject"], email_data["html"])
    log_email(pipeline_conn, "note_digest", recipients, email_data["subject"],
              email_data["html"], result["status"], result.get("error"))
    return result


def send_contact_reminder(pipeline_conn, dormant: list[dict]) -> dict:
    """Build and send contact relationship reminder."""
    email_data = build_contact_reminder(dormant)
    if not email_data:
        return {"status": "skipped", "reason": "No dormant contacts"}

    recipients = [MANAGER_EMAIL] if MANAGER_EMAIL else []
    if not recipients:
        return {"status": "skipped", "reason": "No MANAGER_EMAIL configured"}

    result = send_email(recipients, email_data["subject"], email_data["html"])
    log_email(pipeline_conn, "contact_reminder", recipients, email_data["subject"],
              email_data["html"], result["status"], result.get("error"))
    return result
