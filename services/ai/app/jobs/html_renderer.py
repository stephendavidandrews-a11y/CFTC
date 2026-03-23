"""HTML email renderer for intelligence briefs.

Generates responsive HTML emails with inline CSS and dark theme
matching the CFTC Command Center (#0a0f1a bg, #111827 cards).
"""
import logging
from datetime import date

logger = logging.getLogger(__name__)

# Color Palette
BG = "#0a0f1a"
CARD_BG = "#111827"
CARD_BORDER = "#1e293b"
TEXT = "#e2e8f0"
TEXT_MUTED = "#94a3b8"
TEXT_FAINT = "#64748b"
ACCENT = "#3b82f6"
RED = "#ef4444"
ORANGE = "#f97316"
GREEN = "#22c55e"

TAG_COLORS = {
    "BOSS": ("#fef2f2", "#dc2626"),
    "DEADLINE": ("#fff7ed", "#ea580c"),
    "BLOCKED": ("#fef2f2", "#991b1b"),
    "OVERDUE": ("#fff7ed", "#c2410c"),
    "REVIEW": ("#f0f9ff", "#2563eb"),
}


def _wrap(title, body):
    return (
        '<!DOCTYPE html><html><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<title>{title}</title></head>'
        f'<body style="margin:0;padding:0;background:{BG};font-family:Arial,Helvetica,sans-serif;'
        f'color:{TEXT};-webkit-text-size-adjust:100%;">'
        f'<div style="max-width:680px;margin:0 auto;padding:20px 16px;">'
        f'{body}</div></body></html>'
    )


def _section(title, content, icon=""):
    icon_html = f'<span style="margin-right:8px;">{icon}</span>' if icon else ""
    return (
        f'<div style="background:{CARD_BG};border:1px solid {CARD_BORDER};'
        f'border-radius:8px;margin-bottom:16px;overflow:hidden;">'
        f'<div style="padding:12px 16px;border-bottom:1px solid {CARD_BORDER};">'
        f'<h2 style="margin:0;font-size:15px;font-weight:600;color:{TEXT};">{icon_html}{title}</h2>'
        f'</div><div style="padding:16px;">{content}</div></div>'
    )


def _tag(label):
    bg, fg = TAG_COLORS.get(label, ("#f1f5f9", "#475569"))
    return (
        f'<span style="display:inline-block;padding:2px 8px;border-radius:4px;'
        f'font-size:11px;font-weight:600;background:{bg};color:{fg};margin-right:6px;">'
        f'{label}</span>'
    )


def _empty(message):
    return f'<p style="color:{TEXT_FAINT};font-size:13px;font-style:italic;margin:8px 0;">{message}</p>'


def _render_change_item(c):
    ts = (c.get("timestamp") or "")[:16]
    etype = c.get("entity_type", "")
    summary = c.get("summary", "")
    return (
        f'<div style="padding:6px 0;border-bottom:1px solid {CARD_BORDER};font-size:13px;">'
        f'<span style="color:{TEXT_MUTED};font-size:11px;">{etype}</span> {summary}'
        f'<span style="color:{TEXT_FAINT};font-size:11px;margin-left:8px;">{ts}</span></div>'
    )


def _render_action_item(a):
    tag_html = _tag(a.get("tag", ""))
    title = a.get("title", "")
    matter = a.get("matter", "")
    detail = a.get("detail", "")
    matter_html = ""
    if matter:
        matter_html = f'<span style="font-size:12px;color:{TEXT_MUTED};margin-left:8px;">{matter}</span>'
    return (
        f'<div style="padding:8px 0;border-bottom:1px solid {CARD_BORDER};">'
        f'{tag_html}<span style="font-size:14px;font-weight:500;">{title}</span>{matter_html}'
        f'<div style="font-size:12px;color:{TEXT_MUTED};margin-top:4px;">{detail}</div></div>'
    )


def _render_meeting_item(m):
    participants = m.get("participants", [])
    participant_names = ", ".join(p.get("full_name", p.get("name", "")) for p in participants[:6])
    matters = m.get("linked_matters", [])
    matter_names = ", ".join(mat.get("title", "") for mat in matters[:3])

    flags = ""
    if m.get("has_external"):
        flags += ('<span style="background:#fef3c7;color:#92400e;padding:1px 6px;'
                  'border-radius:3px;font-size:10px;margin-left:6px;">EXTERNAL</span>')
    if m.get("prep_needed"):
        flags += ('<span style="background:#dbeafe;color:#1e40af;padding:1px 6px;'
                  'border-radius:3px;font-size:10px;margin-left:6px;">PREP</span>')

    title = m.get("title", "")
    start = m.get("start_time", "")[:5] if m.get("start_time") else ""
    mtype = m.get("meeting_type", "")
    location = m.get("location", "")

    detail_parts = [p for p in [start, mtype, location] if p]
    detail_line = " \u2022 ".join(detail_parts)

    parts = [
        f'<div style="padding:10px 0;border-bottom:1px solid {CARD_BORDER};">',
        f'<div style="font-size:14px;font-weight:500;">{title}{flags}</div>',
    ]
    if detail_line:
        parts.append(f'<div style="font-size:12px;color:{TEXT_MUTED};margin-top:2px;">{detail_line}</div>')
    if participant_names:
        parts.append(f'<div style="font-size:12px;color:{TEXT_MUTED};margin-top:2px;">{participant_names}</div>')
    if matter_names:
        parts.append(f'<div style="font-size:11px;color:{TEXT_FAINT};margin-top:2px;">Matters: {matter_names}</div>')

    prep = m.get("prep_narrative")
    if prep:
        parts.append(
            f'<div style="font-size:13px;color:{TEXT};margin-top:8px;padding:8px 12px;'
            f'background:rgba(59,130,246,0.05);border-radius:4px;border-left:3px solid {ACCENT};">'
            f'{prep}</div>'
        )
    parts.append('</div>')
    return "".join(parts)


def _render_followup_item(f_item):
    today_str = date.today().isoformat()
    next_date = f_item.get("next_date", "")
    urgency_color = RED if next_date <= today_str else ORANGE
    name = f_item.get("name", "")
    org = f_item.get("organization", "")
    itype = f_item.get("interaction_type", "")
    purpose = f_item.get("purpose", "")

    org_html = ""
    if org:
        org_html = f'<span style="color:{TEXT_MUTED};font-size:12px;margin-left:6px;">{org}</span>'

    detail_parts = [p for p in [itype, purpose] if p]
    detail = " \u2022 ".join(detail_parts)
    detail_str = f' \u2022 {detail}' if detail else ""

    return (
        f'<div style="padding:6px 0;border-bottom:1px solid {CARD_BORDER};font-size:13px;">'
        f'<span style="font-weight:500;">{name}</span>{org_html}'
        f'<div style="font-size:12px;color:{TEXT_MUTED};margin-top:2px;">'
        f'<span style="color:{urgency_color};">{next_date}</span>{detail_str}</div></div>'
    )


def render_daily_html(data):
    """Render complete daily brief as HTML email."""
    d = data.get("date_display", date.today().strftime("%A, %B %d, %Y"))

    header = (
        f'<div style="text-align:center;padding:24px 0 16px;">'
        f'<div style="font-size:11px;text-transform:uppercase;letter-spacing:2px;'
        f'color:{TEXT_FAINT};margin-bottom:4px;">CFTC Daily Brief</div>'
        f'<div style="font-size:20px;font-weight:600;color:{TEXT};">{d}</div></div>'
    )

    sections = [header]

    # Section 1: What Changed
    changes = data.get("what_changed", [])
    if changes:
        items = [_render_change_item(c) for c in changes[:20]]
        sections.append(_section(f"What Changed ({len(changes)})", "\n".join(items), "\U0001F504"))
    else:
        sections.append(_section("What Changed", _empty("No changes since last brief."), "\U0001F504"))

    # Section 2: Action List
    actions = data.get("action_list", [])
    if actions:
        items = [_render_action_item(a) for a in actions[:15]]
        sections.append(_section(f"Action List ({len(actions)})", "\n".join(items), "\U0001F4CB"))
    else:
        sections.append(_section("Action List", _empty("No action items today."), "\U0001F4CB"))

    # Section 3: Meetings
    meetings = data.get("meetings", [])
    if meetings:
        items = [_render_meeting_item(m) for m in meetings]
        sections.append(_section(f"Today\u2019s Meetings ({len(meetings)})", "\n".join(items), "\U0001F4C5"))
    else:
        sections.append(_section("Today\u2019s Meetings", _empty("No meetings today."), "\U0001F4C5"))

    # Section 4: Follow-Ups
    followups = data.get("followups", [])
    if followups:
        items = [_render_followup_item(f_item) for f_item in followups[:10]]
        sections.append(_section(f"Follow-Ups Due ({len(followups)})", "\n".join(items), "\U0001F4DE"))
    else:
        sections.append(_section("Follow-Ups Due", _empty("No follow-ups due in the next 3 days."), "\U0001F4DE"))

    # Section 5: Team Pulse
    pulse = data.get("team_pulse", {})
    overdue_count = pulse.get("overdue_count", 0)
    by_assignee = pulse.get("overdue_by_assignee", {})
    overloaded = pulse.get("overloaded_people", [])

    pulse_lines = []
    if overdue_count:
        assignee_summary = ", ".join(f"{name} ({count})" for name, count in by_assignee.items())
        pulse_lines.append(
            f'<div style="font-size:13px;padding:4px 0;">'
            f'<span style="color:{RED};">{overdue_count} overdue tasks</span>: {assignee_summary}</div>'
        )
    if overloaded:
        names = ", ".join(f"{p['name']} ({p['task_count']})" for p in overloaded)
        pulse_lines.append(
            f'<div style="font-size:13px;padding:4px 0;">'
            f'<span style="color:{ORANGE};">Overloaded</span>: {names}</div>'
        )
    if not pulse_lines:
        pulse_lines.append(f'<div style="font-size:13px;color:{GREEN};">No team execution risks today.</div>')

    sections.append(_section("Team Pulse", "\n".join(pulse_lines), "\U0001F465"))

    # Footer
    footer = (
        f'<div style="text-align:center;padding:16px 0;font-size:11px;color:{TEXT_FAINT};">'
        f'Generated by CFTC AI Layer \u2022 '
        f'<a href="https://cftc.stephenandrews.org" style="color:{ACCENT};text-decoration:none;">Open Dashboard</a>'
        f'</div>'
    )
    sections.append(footer)

    return _wrap(f"CFTC Daily Brief \u2014 {d}", "\n".join(sections))
