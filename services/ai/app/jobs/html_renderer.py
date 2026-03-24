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

    # Section 6: Comment Deadlines
    comment_dls = data.get("comment_deadlines", [])
    if comment_dls:
        cd_items = []
        for cd in comment_dls:
            days = cd.get("days_remaining", 0)
            urgency = RED if days <= 7 else ORANGE if days <= 14 else ACCENT
            status_counts = cd.get("status_counts", {})
            taken = status_counts.get("position_taken", 0)
            total = cd.get("total_topics", 0)
            pct = round(taken / total * 100) if total else 0

            # Progress bar
            bar_color = GREEN if pct >= 75 else ORANGE if pct >= 25 else RED
            progress_bar = (
                f'<div style="display:inline-block;width:80px;height:6px;background:{CARD_BORDER};'
                f'border-radius:3px;overflow:hidden;vertical-align:middle;margin-left:8px;">'
                f'<div style="width:{pct}%;height:100%;background:{bar_color};border-radius:3px;"></div></div>'
                f'<span style="font-size:11px;color:{TEXT_MUTED};margin-left:4px;">{taken}/{total}</span>'
            )

            cd_items.append(
                f'<div style="padding:8px 0;border-bottom:1px solid {CARD_BORDER};">'
                f'<div style="display:flex;justify-content:space-between;align-items:center;">'
                f'<span style="font-size:14px;font-weight:500;">{cd.get("matter_title", "")[:60]}</span>'
                f'<span style="color:{urgency};font-size:12px;font-weight:600;">{days}d</span></div>'
                f'<div style="font-size:12px;color:{TEXT_MUTED};margin-top:4px;">'
                f'Deadline: {cd.get("comment_deadline", "")} \u2022 '
                f'{cd.get("total_questions", 0)} questions \u2022 '
                f'Progress: {progress_bar}</div></div>'
            )
        sections.append(_section(f"Comment Deadlines ({len(comment_dls)})", "\n".join(cd_items), "\U0001F4AC"))
    else:
        sections.append(_section("Comment Deadlines", _empty("No comment periods closing in the next 30 days."), "\U0001F4AC"))

    # Section 7: Directives Watch
    dir_watch = data.get("directives_watch", [])
    if dir_watch:
        dw_items = []
        for dw in dir_watch:
            days = dw.get("days_remaining")
            if days is not None:
                urgency = RED if days <= 3 else ORANGE if days <= 7 else ACCENT
                deadline_str = f'<span style="color:{urgency};font-weight:600;">{days}d to deadline</span>'
            else:
                deadline_str = '<span style="color:{};font-size:11px;">NEW</span>'.format(GREEN)
            dw_items.append(
                f'<div style="padding:6px 0;border-bottom:1px solid {CARD_BORDER};font-size:13px;">'
                f'<div style="font-weight:500;">{dw.get("title", "")}</div>'
                f'<div style="font-size:12px;color:{TEXT_MUTED};margin-top:2px;">'
                f'{dw.get("source_type", "")} \u2022 {dw.get("issued_by", "")} \u2022 '
                f'{dw.get("implementation_status", "")} \u2022 {deadline_str}</div></div>'
            )
        sections.append(_section(f"Directives Watch ({len(dir_watch)})", "\n".join(dw_items), "\U0001F3AF"))
    else:
        sections.append(_section("Directives Watch", _empty("No directives requiring attention."), "\U0001F3AF"))

    # Footer
    footer = (
        f'<div style="text-align:center;padding:16px 0;font-size:11px;color:{TEXT_FAINT};">'
        f'Generated by CFTC AI Layer \u2022 '
        f'<a href="https://cftc.stephenandrews.org" style="color:{ACCENT};text-decoration:none;">Open Dashboard</a>'
        f'</div>'
    )
    sections.append(footer)

    return _wrap(f"CFTC Daily Brief \u2014 {d}", "\n".join(sections))


# ── Weekly Brief ─────────────────────────────────────────────────────────

def render_weekly_html(data):
    """Render complete weekly brief as HTML email."""
    d = data.get("date_display", "Weekly Brief")

    header = (
        f'<div style="text-align:center;padding:24px 0 16px;">'
        f'<div style="font-size:11px;text-transform:uppercase;letter-spacing:2px;'
        f'color:{TEXT_FAINT};margin-bottom:4px;">CFTC Weekly Brief</div>'
        f'<div style="font-size:20px;font-weight:600;color:{TEXT};">{d}</div></div>'
    )

    sections = [header]

    # Section 0: Calibration
    cal = data.get("calibration", {})
    if cal.get("has_data"):
        score = cal.get("score", 0)
        score_color = GREEN if score >= 70 else ORANGE if score >= 50 else RED
        cal_html = (
            f'<div style="text-align:center;margin-bottom:16px;">'
            f'<div style="font-size:36px;font-weight:700;color:{score_color};">{score}%</div>'
            f'<div style="font-size:12px;color:{TEXT_MUTED};">Signal Quality</div></div>'
            f'<div style="display:flex;justify-content:center;gap:24px;font-size:13px;">'
            f'<div><span style="color:{RED};font-weight:600;">{cal.get("materialized", 0)}</span> materialized</div>'
            f'<div><span style="color:{GREEN};font-weight:600;">{cal.get("resolved", 0)}</span> resolved</div>'
            f'<div><span style="color:{TEXT_MUTED};font-weight:600;">{cal.get("still_open", 0)}</span> still open</div>'
            f'<div><span style="color:{ORANGE};font-weight:600;">{cal.get("wrong", 0)}</span> wrong</div>'
            f'</div>'
        )
        sections.append(_section("What I Got Wrong", cal_html, "\U0001F3AF"))
    else:
        msg = cal.get("message", "No calibration data available.")
        sections.append(_section("What I Got Wrong", _empty(msg), "\U0001F3AF"))

    # Section 1: Executive Summary
    summary = data.get("executive_summary")
    if summary:
        sections.append(_section("Executive Summary", f'<div style="font-size:14px;line-height:1.6;color:{TEXT};">{summary}</div>', "\U0001F4DD"))
    else:
        sections.append(_section("Executive Summary", _empty("Executive summary not generated."), "\U0001F4DD"))

    # Section 2: Portfolio Health
    portfolio = data.get("portfolio", {})
    portfolio_html = []
    for posture, label, color in [
        ("critical", "Critical This Week", RED),
        ("important", "Important This Month", ORANGE),
        ("strategic", "Strategic / Slow Burn", ACCENT),
        ("monitoring", "Monitoring", TEXT_FAINT),
    ]:
        items = portfolio.get(posture, [])
        if not items:
            continue
        portfolio_html.append(
            f'<div style="margin-bottom:12px;">'
            f'<div style="font-size:12px;font-weight:600;color:{color};text-transform:uppercase;'
            f'letter-spacing:0.05em;margin-bottom:6px;">{label} ({len(items)})</div>'
        )
        for m in items:
            dl = m.get("nearest_deadline") or "no deadline"
            owner = m.get("next_step_owner") or "no owner"
            portfolio_html.append(
                f'<div style="padding:6px 0;border-bottom:1px solid {CARD_BORDER};font-size:13px;">'
                f'<span style="font-weight:500;">{m.get("title", "")}</span>'
                f'<div style="font-size:11px;color:{TEXT_MUTED};margin-top:2px;">'
                f'{m.get("status", "")} \u2022 {dl} \u2022 {owner}</div></div>'
            )
        portfolio_html.append('</div>')
    sections.append(_section(f'Portfolio Health ({portfolio.get("total_active", 0)})', "\n".join(portfolio_html) or _empty("No active matters."), "\U0001F4CA"))

    # Section 3: Decision Docket
    decisions = data.get("decisions", [])
    if decisions:
        dec_items = []
        for dec in decisions:
            due = dec.get("due_date") or "no date"
            owner = dec.get("decision_owner") or "unassigned"
            dec_items.append(
                f'<div style="padding:6px 0;border-bottom:1px solid {CARD_BORDER};font-size:13px;">'
                f'<span style="font-weight:500;">{dec.get("title", "")}</span>'
                f'<div style="font-size:11px;color:{TEXT_MUTED};margin-top:2px;">'
                f'{dec.get("matter_title", "")} \u2022 {owner} \u2022 Due: {due} \u2022 {dec.get("status", "")}</div></div>'
            )
        sections.append(_section(f"Decision Docket ({len(decisions)})", "\n".join(dec_items), "\u2696\uFE0F"))
    else:
        sections.append(_section("Decision Docket", _empty("No open decisions."), "\u2696\uFE0F"))

    # Section 4: Team View
    team = data.get("team", {})
    team_html = []
    workload = team.get("workload", [])
    if workload:
        team_html.append('<div style="margin-bottom:12px;">')
        for w in sorted(workload, key=lambda x: -x.get("overdue", 0)):
            overdue_badge = ""
            if w.get("overdue", 0) > 0:
                overdue_badge = f' <span style="color:{RED};font-size:11px;">({w["overdue"]} overdue)</span>'
            team_html.append(
                f'<div style="padding:4px 0;font-size:13px;">'
                f'<span style="font-weight:500;">{w.get("name", "")}</span>'
                f' \u2014 {w.get("open_tasks", 0)} tasks, {w.get("open_matters", 0)} matters'
                + (f', {w.get("open_topics", 0)} topics' if w.get("open_topics") else '')
                + f'{overdue_badge}</div>'
            )
        team_html.append('</div>')
    drifting = team.get("drifting_matters", [])
    if drifting:
        team_html.append(f'<div style="font-size:12px;font-weight:600;color:{ORANGE};margin:8px 0 4px;">Drifting Matters</div>')
        for dm in drifting:
            team_html.append(
                f'<div style="padding:3px 0;font-size:12px;color:{TEXT_MUTED};">'
                f'{dm.get("title", "")} \u2014 {dm.get("days_stale", 0)}d stale \u2014 {dm.get("owner", "")}</div>'
            )
    sections.append(_section("Team View", "\n".join(team_html) or _empty("No team data."), "\U0001F465"))

    # Section 5: Stakeholders
    stak = data.get("stakeholders", {})
    stak_html = []
    touchpoints = stak.get("touchpoints_due", [])
    if touchpoints:
        stak_html.append(f'<div style="font-size:12px;font-weight:600;color:{ACCENT};margin-bottom:6px;">Touchpoints Due This Week</div>')
        for tp in touchpoints:
            stak_html.append(
                f'<div style="padding:4px 0;font-size:13px;border-bottom:1px solid {CARD_BORDER};">'
                f'<span style="font-weight:500;">{tp.get("name", "")}</span>'
                f' <span style="color:{TEXT_MUTED};font-size:12px;">{tp.get("organization", "")}</span>'
                f'<div style="font-size:11px;color:{TEXT_MUTED};">{tp.get("next_date", "")} \u2022 {tp.get("purpose", "")}</div></div>'
            )
    neglected = stak.get("neglected", [])
    if neglected:
        stak_html.append(f'<div style="font-size:12px;font-weight:600;color:{ORANGE};margin:12px 0 6px;">Neglected Relationships</div>')
        for n in neglected:
            stak_html.append(
                f'<div style="padding:3px 0;font-size:12px;color:{TEXT_MUTED};">'
                f'{n.get("name", "")} ({n.get("category", "")}) \u2014 {n.get("days_since", 0)} days since last contact</div>'
            )
    sections.append(_section("Stakeholders", "\n".join(stak_html) or _empty("No stakeholder actions needed."), "\U0001F91D"))

    # Section 6: Deadlines
    dl_data = data.get("deadlines", {})
    dl_html = []
    for period, label in [("two_weeks", "Next 2 Weeks"), ("thirty_days", "Next 30 Days"), ("ninety_days", "Next 90 Days")]:
        items = dl_data.get(period, [])
        if items:
            dl_html.append(f'<div style="font-size:12px;font-weight:600;color:{ACCENT};margin:8px 0 4px;">{label} ({len(items)})</div>')
            for item in items:
                dl_html.append(
                    f'<div style="padding:3px 0;font-size:12px;color:{TEXT_MUTED};">'
                    f'{item.get("date", "")} \u2022 {item.get("deadline_type", "")} \u2022 {item.get("matter_title", "")} \u2022 {item.get("owner", "")}</div>'
                )
    sections.append(_section("Deadlines & Horizon", "\n".join(dl_html) or _empty("No upcoming deadlines."), "\U0001F4C6"))

    # Section 7: Documents
    docs = data.get("documents", {})
    if docs:
        doc_html = []
        for status, items in docs.items():
            doc_html.append(f'<div style="font-size:12px;font-weight:600;color:{TEXT_MUTED};margin:6px 0 3px;">{status} ({len(items)})</div>')
            for doc in items:
                doc_html.append(f'<div style="padding:2px 0;font-size:12px;color:{TEXT_MUTED};">{doc.get("title", "")}</div>')
        sections.append(_section("Documents Pipeline", "\n".join(doc_html), "\U0001F4C4"))
    else:
        sections.append(_section("Documents Pipeline", _empty("No documents tracked."), "\U0001F4C4"))

    # Section 8: Risks
    risks = data.get("risks", {})
    high = risks.get("high_sensitivity", [])
    if high:
        risk_html = []
        for r in high:
            risk_html.append(
                f'<div style="padding:4px 0;font-size:13px;border-bottom:1px solid {CARD_BORDER};">'
                f'<span style="font-weight:500;">{r.get("title", "")}</span>'
                f'<div style="font-size:11px;color:{TEXT_MUTED};">{r.get("sensitivity", "")} \u2022 {r.get("status", "")} \u2022 Boss: {r.get("boss_involvement", "none")}</div></div>'
            )
        sections.append(_section(f"Risk Register ({len(high)})", "\n".join(risk_html), "\u26A0\uFE0F"))
    else:
        sections.append(_section("Risk Register", _empty("No high-sensitivity items."), "\u26A0\uFE0F"))

    # Section 9: Data Hygiene
    hygiene = data.get("hygiene", {})
    score = hygiene.get("score", 0)
    score_color = GREEN if score >= 80 else ORANGE if score >= 60 else RED
    checks = hygiene.get("checks", [])
    hyg_html = (
        f'<div style="text-align:center;margin-bottom:16px;">'
        f'<div style="font-size:48px;font-weight:700;color:{score_color};">{score}%</div>'
        f'<div style="font-size:12px;color:{TEXT_MUTED};">Tracker Health</div></div>'
    )
    if checks:
        hyg_html += '<div style="font-size:12px;">'
        for c in sorted(checks, key=lambda x: x.get("pct", 0)):
            bar_color = GREEN if c["pct"] >= 80 else ORANGE if c["pct"] >= 50 else RED
            field = c.get("field", "").replace(".", " \u2192 ")
            hyg_html += (
                f'<div style="display:flex;align-items:center;gap:8px;padding:3px 0;">'
                f'<span style="width:180px;color:{TEXT_MUTED};">{field}</span>'
                f'<div style="flex:1;height:6px;background:{CARD_BORDER};border-radius:3px;overflow:hidden;">'
                f'<div style="width:{c["pct"]}%;height:100%;background:{bar_color};border-radius:3px;"></div></div>'
                f'<span style="width:60px;text-align:right;color:{TEXT_MUTED};">{c["count"]}/{c["total"]}</span>'
                f'</div>'
            )
        hyg_html += '</div>'
    sections.append(_section("Data Hygiene", hyg_html, "\U0001F9F9"))

    # Section 10: Rulemaking Comment Progress
    cp = data.get("comment_progress", {})
    cp_matters = cp.get("matters", [])
    cp_totals = cp.get("totals", {})
    if cp_matters:
        cp_html = []
        # Summary header
        sb = cp_totals.get("status_breakdown", {})
        cp_html.append(
            f'<div style="display:flex;justify-content:center;gap:16px;margin-bottom:16px;font-size:13px;">'
            f'<div><span style="font-weight:600;color:{GREEN};">{sb.get("position_taken", 0)}</span> positions taken</div>'
            f'<div><span style="font-weight:600;color:{ACCENT};">{sb.get("drafting", 0) + sb.get("final_review", 0)}</span> in progress</div>'
            f'<div><span style="font-weight:600;color:{ORANGE};">{sb.get("open", 0) + sb.get("not_started", 0)}</span> not started</div>'
            f'</div>'
        )
        for cm in cp_matters:
            pct = cm.get("completion_pct", 0)
            bar_color = GREEN if pct >= 75 else ORANGE if pct >= 25 else RED
            dr = cm.get("days_remaining")
            deadline_str = f'{dr}d remaining' if dr is not None else "no deadline"
            deadline_color = RED if dr is not None and dr <= 14 else TEXT_MUTED

            cp_html.append(
                f'<div style="padding:10px 0;border-bottom:1px solid {CARD_BORDER};">'
                f'<div style="display:flex;justify-content:space-between;align-items:center;">'
                f'<span style="font-size:14px;font-weight:500;">{cm.get("matter_title", "")[:55]}</span>'
                f'<span style="color:{deadline_color};font-size:12px;">{deadline_str}</span></div>'
                f'<div style="display:flex;align-items:center;gap:8px;margin-top:6px;">'
                f'<span style="font-size:12px;color:{TEXT_MUTED};">{cm["total_topics"]} topics, {cm["total_questions"]} questions</span>'
                f'<div style="flex:1;height:8px;background:{CARD_BORDER};border-radius:4px;overflow:hidden;">'
                f'<div style="width:{pct}%;height:100%;background:{bar_color};border-radius:4px;"></div></div>'
                f'<span style="font-size:12px;font-weight:600;color:{bar_color};">{pct}%</span>'
                f'</div></div>'
            )
        sections.append(_section(
            f"Rulemaking Comment Progress ({cp_totals.get('total_topics', 0)} topics)",
            "\n".join(cp_html), "\U0001F4AC"
        ))
    else:
        sections.append(_section("Rulemaking Comment Progress", _empty("No comment topics tracked."), "\U0001F4AC"))

    # Section 11: Policy Directives Status
    dir_status = data.get("directives_status", {})
    if dir_status.get("has_data"):
        ds_html = []
        by_st = dir_status.get("by_status", {})
        ds_html.append(
            '<div style="display:flex;justify-content:center;gap:16px;margin-bottom:12px;font-size:13px;">'
        )
        for st, count in by_st.items():
            label = st.replace("_", " ").title()
            ds_html.append(f'<div><span style="font-weight:600;">{count}</span> {label}</div>')
        ds_html.append('</div>')

        overdue_dir = dir_status.get("overdue", [])
        if overdue_dir:
            ds_html.append(f'<div style="font-size:12px;font-weight:600;color:{RED};margin:8px 0 4px;">Overdue ({len(overdue_dir)})</div>')
            for od in overdue_dir:
                ds_html.append(
                    f'<div style="padding:4px 0;font-size:12px;color:{TEXT_MUTED};">'
                    f'{od.get("title", "")} \u2022 {od.get("deadline", "")} \u2022 {abs(od.get("days_remaining", 0))}d overdue</div>'
                )
        upcoming_dir = dir_status.get("upcoming", [])
        if upcoming_dir:
            ds_html.append(f'<div style="font-size:12px;font-weight:600;color:{ORANGE};margin:8px 0 4px;">Approaching ({len(upcoming_dir)})</div>')
            for ud in upcoming_dir:
                ds_html.append(
                    f'<div style="padding:4px 0;font-size:12px;color:{TEXT_MUTED};">'
                    f'{ud.get("title", "")} \u2022 {ud.get("deadline", "")} \u2022 {ud.get("days_remaining", 0)}d</div>'
                )
        if not overdue_dir and not upcoming_dir:
            ds_html.append(f'<div style="font-size:13px;color:{GREEN};">All directives on track.</div>')
        sections.append(_section(f"Policy Directives ({dir_status.get('total', 0)})", "\n".join(ds_html), "\U0001F4DC"))
    else:
        sections.append(_section("Policy Directives", _empty("No policy directives tracked."), "\U0001F4DC"))

    # Footer
    footer = (
        f'<div style="text-align:center;padding:16px 0;font-size:11px;color:{TEXT_FAINT};">'
        f'Generated by CFTC AI Layer \u2022 '
        f'<a href="https://cftc.stephenandrews.org" style="color:{ACCENT};text-decoration:none;">Open Dashboard</a>'
        f'</div>'
    )
    sections.append(footer)

    return _wrap(f"CFTC Weekly Brief \u2014 {d}", "\n".join(sections))
