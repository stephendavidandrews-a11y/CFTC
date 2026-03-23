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
    detail_line = " • ".join(detail_parts)

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
    detail = " • ".join(detail_parts)
    detail_str = f' • {detail}' if detail else ""

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
        sections.append(_section(f"What Changed ({len(changes)})", "\n".join(items), ""))
    else:
        sections.append(_section("What Changed", _empty("No changes since last brief."), ""))

    # Section 2: Action List
    actions = data.get("action_list", [])
    if actions:
        items = [_render_action_item(a) for a in actions[:15]]
        sections.append(_section(f"Action List ({len(actions)})", "\n".join(items), ""))
    else:
        sections.append(_section("Action List", _empty("No action items today."), ""))

    # Section 3: Meetings
    meetings = data.get("meetings", [])
    if meetings:
        items = [_render_meeting_item(m) for m in meetings]
        sections.append(_section(f"Today\u2019s Meetings ({len(meetings)})", "\n".join(items), ""))
    else:
        sections.append(_section("Today\u2019s Meetings", _empty("No meetings today."), ""))

    # Section 4: Follow-Ups
    followups = data.get("followups", [])
    if followups:
        items = [_render_followup_item(f_item) for f_item in followups[:10]]
        sections.append(_section(f"Follow-Ups Due ({len(followups)})", "\n".join(items), ""))
    else:
        sections.append(_section("Follow-Ups Due", _empty("No follow-ups due in the next 3 days."), ""))

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

    sections.append(_section("Team Pulse", "\n".join(pulse_lines), ""))

    # Footer
    footer = (
        f'<div style="text-align:center;padding:16px 0;font-size:11px;color:{TEXT_FAINT};">'
        f'Generated by CFTC AI Layer • '
        f'<a href="https://cftc.stephenandrews.org" style="color:{ACCENT};text-decoration:none;">Open Dashboard</a>'
        f'</div>'
    )
    sections.append(footer)

    return _wrap(f"CFTC Daily Brief — {d}", "\n".join(sections))



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
        sections.append(_section("What I Got Wrong", cal_html, ""))
    else:
        msg = cal.get("message", "No calibration data available.")
        sections.append(_section("What I Got Wrong", _empty(msg), ""))

    # Section 1: Executive Summary
    summary = data.get("executive_summary")
    if summary:
        sections.append(_section("Executive Summary", f'<div style="font-size:14px;line-height:1.6;color:{TEXT};">{summary}</div>', ""))
    else:
        sections.append(_section("Executive Summary", _empty("Executive summary not generated."), ""))

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
                f'{m.get("status", "")} • {dl} • {owner}</div></div>'
            )
        portfolio_html.append('</div>')
    sections.append(_section(f'Portfolio Health ({portfolio.get("total_active", 0)})', "\n".join(portfolio_html) or _empty("No active matters."), ""))

    # Section 3: Decision Docket
    decisions = data.get("decisions", [])
    if decisions:
        dec_items = []
        for d in decisions:
            due = d.get("due_date") or "no date"
            owner = d.get("decision_owner") or "unassigned"
            dec_items.append(
                f'<div style="padding:6px 0;border-bottom:1px solid {CARD_BORDER};font-size:13px;">'
                f'<span style="font-weight:500;">{d.get("title", "")}</span>'
                f'<div style="font-size:11px;color:{TEXT_MUTED};margin-top:2px;">'
                f'{d.get("matter_title", "")} • {owner} • Due: {due} • {d.get("status", "")}</div></div>'
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
                f' — {w.get("open_tasks", 0)} tasks, {w.get("open_matters", 0)} matters{overdue_badge}</div>'
            )
        team_html.append('</div>')
    drifting = team.get("drifting_matters", [])
    if drifting:
        team_html.append(f'<div style="font-size:12px;font-weight:600;color:{ORANGE};margin:8px 0 4px;">Drifting Matters</div>')
        for dm in drifting:
            team_html.append(
                f'<div style="padding:3px 0;font-size:12px;color:{TEXT_MUTED};">'
                f'{dm.get("title", "")} — {dm.get("days_stale", 0)}d stale — {dm.get("owner", "")}</div>'
            )
    sections.append(_section("Team View", "\n".join(team_html) or _empty("No team data."), ""))

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
                f'<div style="font-size:11px;color:{TEXT_MUTED};">{tp.get("next_date", "")} • {tp.get("purpose", "")}</div></div>'
            )
    neglected = stak.get("neglected", [])
    if neglected:
        stak_html.append(f'<div style="font-size:12px;font-weight:600;color:{ORANGE};margin:12px 0 6px;">Neglected Relationships</div>')
        for n in neglected:
            stak_html.append(
                f'<div style="padding:3px 0;font-size:12px;color:{TEXT_MUTED};">'
                f'{n.get("name", "")} ({n.get("category", "")}) — {n.get("days_since", 0)} days since last contact</div>'
            )
    sections.append(_section("Stakeholders", "\n".join(stak_html) or _empty("No stakeholder actions needed."), ""))

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
                    f'{item.get("date", "")} • {item.get("deadline_type", "")} • {item.get("matter_title", "")} • {item.get("owner", "")}</div>'
                )
    sections.append(_section("Deadlines & Horizon", "\n".join(dl_html) or _empty("No upcoming deadlines."), ""))

    # Section 7: Documents
    docs = data.get("documents", {})
    if docs:
        doc_html = []
        for status, items in docs.items():
            doc_html.append(f'<div style="font-size:12px;font-weight:600;color:{TEXT_MUTED};margin:6px 0 3px;">{status} ({len(items)})</div>')
            for d in items:
                doc_html.append(f'<div style="padding:2px 0;font-size:12px;color:{TEXT_MUTED};">{d.get("title", "")}</div>')
        sections.append(_section("Documents Pipeline", "\n".join(doc_html), ""))
    else:
        sections.append(_section("Documents Pipeline", _empty("No documents tracked."), ""))

    # Section 8: Risks
    risks = data.get("risks", {})
    high = risks.get("high_sensitivity", [])
    if high:
        risk_html = []
        for r in high:
            risk_html.append(
                f'<div style="padding:4px 0;font-size:13px;border-bottom:1px solid {CARD_BORDER};">'
                f'<span style="font-weight:500;">{r.get("title", "")}</span>'
                f'<div style="font-size:11px;color:{TEXT_MUTED};">{r.get("sensitivity", "")} • {r.get("status", "")} • Boss: {r.get("boss_involvement", "none")}</div></div>'
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
            field = c.get("field", "").replace(".", " → ")
            hyg_html += (
                f'<div style="display:flex;align-items:center;gap:8px;padding:3px 0;">'
                f'<span style="width:180px;color:{TEXT_MUTED};">{field}</span>'
                f'<div style="flex:1;height:6px;background:{CARD_BORDER};border-radius:3px;overflow:hidden;">'
                f'<div style="width:{c["pct"]}%;height:100%;background:{bar_color};border-radius:3px;"></div></div>'
                f'<span style="width:60px;text-align:right;color:{TEXT_MUTED};">{c["count"]}/{c["total"]}</span>'
                f'</div>'
            )
        hyg_html += '</div>'
    sections.append(_section("Data Hygiene", hyg_html, ""))

    # Footer
    footer = (
        f'<div style="text-align:center;padding:16px 0;font-size:11px;color:{TEXT_FAINT};">'
        f'Generated by CFTC AI Layer • '
        f'<a href="https://cftc.stephenandrews.org" style="color:{ACCENT};text-decoration:none;">Open Dashboard</a>'
        f'</div>'
    )
    sections.append(footer)

    return _wrap(f"CFTC Weekly Brief — {d}", "\n".join(sections))



# ── Dev Report ───────────────────────────────────────────────────────────

def render_dev_report_html(data):
    """Render weekly dev report as HTML email."""
    d = data.get("date_display", "Dev Report")
    overall = data.get("overall_score", 0)
    overall_color = GREEN if overall >= 80 else ORANGE if overall >= 60 else RED

    header = (
        f'<div style="text-align:center;padding:24px 0 16px;">'
        f'<div style="font-size:11px;text-transform:uppercase;letter-spacing:2px;'
        f'color:{TEXT_FAINT};margin-bottom:4px;">CFTC App Health</div>'
        f'<div style="font-size:20px;font-weight:600;color:{TEXT};">{d}</div>'
        f'<div style="font-size:48px;font-weight:700;color:{overall_color};margin-top:12px;">{overall}%</div>'
        f'<div style="font-size:12px;color:{TEXT_MUTED};">Overall Data Completeness</div></div>'
    )

    sections = [header]

    # Entity analyses (verbose format)
    for entity_key in ["matters", "tasks", "people", "meetings", "decisions"]:
        analysis = data.get("entity_analyses", {}).get(entity_key, {})
        entity_name = analysis.get("entity", entity_key).title()
        total = analysis.get("total", 0)
        fields = analysis.get("fields", [])

        if not fields:
            sections.append(_section(f"{entity_name} ({total})", _empty(f"No {entity_key} to analyze."), ""))
            continue

        field_html = []
        for f in fields:
            pct = f.get("pct", 0)
            bar_color = GREEN if pct >= 80 else ORANGE if pct >= 50 else RED
            source_badge = ""
            if f.get("source") == "ai":
                source_badge = f' <span style="background:#1e3a5f;color:#60a5fa;padding:1px 5px;border-radius:3px;font-size:9px;">AI</span>'
            elif f.get("source") == "manual":
                source_badge = f' <span style="background:#1f2937;color:#9ca3af;padding:1px 5px;border-radius:3px;font-size:9px;">MANUAL</span>'

            field_html.append(
                f'<div style="padding:8px 0;border-bottom:1px solid {CARD_BORDER};">'
                f'<div style="display:flex;align-items:center;justify-content:space-between;">'
                f'<div><span style="font-weight:500;font-size:13px;">{f.get("field", "")}</span>{source_badge}</div>'
                f'<span style="font-size:12px;color:{TEXT_MUTED};">{f.get("populated", 0)}/{f.get("total", 0)} ({pct}%)</span></div>'
                f'<div style="height:4px;background:{CARD_BORDER};border-radius:2px;margin:6px 0;overflow:hidden;">'
                f'<div style="width:{pct}%;height:100%;background:{bar_color};border-radius:2px;"></div></div>'
                f'<div style="font-size:11px;color:{TEXT_FAINT};font-style:italic;">'
                f'Purpose: {f.get("purpose", "")}. If empty: {f.get("impact", "")}</div>'
            )

            # Enum distribution
            dist = f.get("distribution")
            if dist:
                dist_parts = []
                for val, count in dist.items():
                    is_empty = val == "NOT SET"
                    style = f"color:{RED};font-weight:600;" if is_empty else f"color:{TEXT_MUTED};"
                    dist_parts.append(f'<span style="{style}">{val}: {count}</span>')
                field_html.append(
                    f'<div style="font-size:11px;margin-top:4px;">{" • ".join(dist_parts)}</div>'
                )

            field_html.append('</div>')

        sections.append(_section(f"{entity_name} ({total} records)", "\n".join(field_html), ""))

    # Context Notes
    cn = data.get("context_notes", {})
    if cn.get("total", 0) > 0:
        cn_html = f'<div style="font-size:13px;">Total: {cn["total"]}</div>'
        if cn.get("by_source"):
            cn_html += f'<div style="font-size:12px;color:{TEXT_MUTED};margin-top:4px;">Sources: {", ".join(f"{k}: {v}" for k, v in cn["by_source"].items())}</div>'
        if cn.get("by_category"):
            cn_html += f'<div style="font-size:12px;color:{TEXT_MUTED};margin-top:4px;">Categories: {", ".join(f"{k}: {v}" for k, v in cn["by_category"].items())}</div>'
        cn_html += f'<div style="font-size:12px;color:{TEXT_MUTED};margin-top:4px;">Avg entity links per note: {cn.get("avg_links", 0)}</div>'
        sections.append(_section("Context Notes", cn_html, ""))
    else:
        sections.append(_section("Context Notes", _empty("No context notes exist yet."), ""))

    # Pipeline Quality
    pipe = data.get("pipeline", {})
    pipe_html = (
        f'<div style="display:flex;gap:24px;justify-content:center;margin-bottom:12px;font-size:13px;">'
        f'<div style="text-align:center;"><div style="font-size:24px;font-weight:700;color:{GREEN};">{pipe.get("accept_rate", 0)}%</div>Accept</div>'
        f'<div style="text-align:center;"><div style="font-size:24px;font-weight:700;color:{ORANGE};">{pipe.get("edit_rate", 0)}%</div>Edit</div>'
        f'<div style="text-align:center;"><div style="font-size:24px;font-weight:700;color:{RED};">{pipe.get("reject_rate", 0)}%</div>Reject</div>'
        f'</div>'
        f'<div style="font-size:12px;color:{TEXT_MUTED};text-align:center;">'
        f'{pipe.get("communications_processed", 0)} communications • '
        f'{pipe.get("total_review_actions", 0)} review actions • '
        f'${pipe.get("total_spend", 0):.2f} LLM spend</div>'
    )
    sections.append(_section("Pipeline Quality", pipe_html, ""))

    # Page Visits
    visits = data.get("page_visits", [])
    if visits:
        visit_html = []
        for pv in visits[:15]:
            visit_html.append(
                f'<div style="display:flex;justify-content:space-between;padding:3px 0;font-size:12px;">'
                f'<span style="color:{TEXT_MUTED};">{pv.get("page", "")}</span>'
                f'<span style="font-weight:500;">{pv.get("visits", 0)}x</span></div>'
            )
        sections.append(_section("Page Visits This Week", "\n".join(visit_html), ""))
    else:
        sections.append(_section("Page Visits", _empty("No page visits recorded yet."), ""))

    # Suggestions
    suggestions = data.get("suggestions", [])
    if suggestions:
        sug_html = []
        for s in suggestions:
            sug_html.append(f'<div style="padding:4px 0;font-size:13px;color:{TEXT};">• {s}</div>')
        sections.append(_section("Suggestions", "\n".join(sug_html), ""))

    footer = (
        f'<div style="text-align:center;padding:16px 0;font-size:11px;color:{TEXT_FAINT};">'
        f'Generated by CFTC AI Layer • Zero LLM cost</div>'
    )
    sections.append(footer)

    return _wrap(f"CFTC App Health — {d}", "\n".join(sections))
