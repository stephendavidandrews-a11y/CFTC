"""
Seed data for the Pipeline Manager.

Inserts test team members and default stage templates for all item types.
Idempotent -- checks for existing data before inserting.
"""

import sqlite3
import json
import logging

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Test team members
# ---------------------------------------------------------------------------

SEED_TEAM_MEMBERS = [
    {
        "name": "Sarah Chen",
        "role": "Assistant General Counsel",
        "gs_level": "GS-15",
        "specializations": json.dumps(["digital_assets", "event_contracts", "derivatives"]),
        "max_concurrent": 5,
    },
    {
        "name": "Marcus Williams",
        "role": "Senior Counsel",
        "gs_level": "GS-15",
        "specializations": json.dumps(["swaps", "clearing", "cross_border"]),
        "max_concurrent": 5,
    },
    {
        "name": "Jennifer Park",
        "role": "Senior Counsel",
        "gs_level": "GS-15",
        "specializations": json.dumps(["market_structure", "position_limits", "speculation"]),
        "max_concurrent": 5,
    },
    {
        "name": "David Thompson",
        "role": "Counsel",
        "gs_level": "GS-14",
        "specializations": json.dumps(["technology", "cybersecurity", "operational_resilience"]),
        "max_concurrent": 5,
    },
    {
        "name": "Rachel Foster",
        "role": "Senior Counsel",
        "gs_level": "GS-15",
        "specializations": json.dumps(["clearing", "margin", "systemic_risk"]),
        "max_concurrent": 4,
    },
    {
        "name": "James Liu",
        "role": "Counsel",
        "gs_level": "GS-14",
        "specializations": json.dumps(["registration", "compliance", "sro_oversight"]),
        "max_concurrent": 5,
    },
    {
        "name": "Ana Martinez",
        "role": "Senior Counsel",
        "gs_level": "GS-15",
        "specializations": json.dumps(["enforcement", "market_manipulation", "anti_fraud"]),
        "max_concurrent": 4,
    },
    {
        "name": "Robert Kim",
        "role": "Counsel",
        "gs_level": "GS-14",
        "specializations": json.dumps(["data_reporting", "real_time_reporting", "trade_execution"]),
        "max_concurrent": 5,
    },
    {
        "name": "Lisa Patel",
        "role": "Counsel",
        "gs_level": "GS-14",
        "specializations": json.dumps(["consumer_protection", "retail_forex", "commodity_pools"]),
        "max_concurrent": 5,
    },
    {
        "name": "Michael Brown",
        "role": "Attorney Advisor",
        "gs_level": "GS-13",
        "specializations": json.dumps(["administrative_law", "rulemaking_process", "apa_compliance"]),
        "max_concurrent": 6,
    },
]


# ---------------------------------------------------------------------------
# Stage templates
# (module, item_type, stage_order, stage_key, stage_label, stage_color,
#  is_terminal, sla_days)
# ---------------------------------------------------------------------------

STAGE_TEMPLATES = [
    # ── RULEMAKING: NPRM (Notice of Proposed Rulemaking) ──
    ("rulemaking", "NPRM", 1, "concept", "Concept Development", "#6b7280", 0, 30),
    ("rulemaking", "NPRM", 2, "drafting", "Drafting", "#6b7280", 0, 45),
    ("rulemaking", "NPRM", 3, "cba_development", "CBA Development", "#8b5cf6", 0, 30),
    ("rulemaking", "NPRM", 4, "chairman_review", "Chairman Review", "#f59e0b", 0, 14),
    ("rulemaking", "NPRM", 5, "commission_review", "Commission Review/Vote", "#f59e0b", 0, 21),
    ("rulemaking", "NPRM", 6, "ofr_submission", "OFR Submission", "#3b82f6", 0, 7),
    ("rulemaking", "NPRM", 7, "comment_period", "Comment Period", "#f59e0b", 0, 60),
    ("rulemaking", "NPRM", 8, "comment_analysis", "Comment Analysis", "#8b5cf6", 0, 30),
    ("rulemaking", "NPRM", 9, "final_drafting", "Final Rule Drafting", "#3b82f6", 0, 45),
    ("rulemaking", "NPRM", 10, "final_commission", "Final Commission Vote", "#f59e0b", 0, 21),
    ("rulemaking", "NPRM", 11, "published", "Published", "#22c55e", 1, None),

    # ── RULEMAKING: IFR (Interim Final Rule) ──
    ("rulemaking", "IFR", 1, "concept", "Concept Development", "#6b7280", 0, 14),
    ("rulemaking", "IFR", 2, "drafting", "Drafting", "#6b7280", 0, 21),
    ("rulemaking", "IFR", 3, "good_cause", "Good Cause Determination", "#ef4444", 0, 7),
    ("rulemaking", "IFR", 4, "chairman_review", "Chairman Review", "#f59e0b", 0, 7),
    ("rulemaking", "IFR", 5, "commission_review", "Commission Review/Vote", "#f59e0b", 0, 14),
    ("rulemaking", "IFR", 6, "published", "Published", "#22c55e", 1, None),

    # ── RULEMAKING: ANPRM (Advance Notice of Proposed Rulemaking) ──
    ("rulemaking", "ANPRM", 1, "concept", "Concept Development", "#6b7280", 0, 21),
    ("rulemaking", "ANPRM", 2, "drafting", "Drafting", "#6b7280", 0, 30),
    ("rulemaking", "ANPRM", 3, "chairman_review", "Chairman Review", "#f59e0b", 0, 14),
    ("rulemaking", "ANPRM", 4, "commission_review", "Commission Review/Vote", "#f59e0b", 0, 14),
    ("rulemaking", "ANPRM", 5, "published", "Published", "#22c55e", 1, None),

    # ── RULEMAKING: DFR (Direct Final Rule) ──
    ("rulemaking", "DFR", 1, "concept", "Concept Development", "#6b7280", 0, 14),
    ("rulemaking", "DFR", 2, "drafting", "Drafting", "#6b7280", 0, 21),
    ("rulemaking", "DFR", 3, "chairman_review", "Chairman Review", "#f59e0b", 0, 7),
    ("rulemaking", "DFR", 4, "commission_review", "Commission Review/Vote", "#f59e0b", 0, 14),
    ("rulemaking", "DFR", 5, "ofr_submission", "OFR Submission", "#3b82f6", 0, 7),
    ("rulemaking", "DFR", 6, "comment_period", "Comment Period", "#f59e0b", 0, 30),
    ("rulemaking", "DFR", 7, "effective", "Effective", "#22c55e", 1, None),

    # ── RULEMAKING: final_rule (standalone) ──
    ("rulemaking", "final_rule", 1, "drafting", "Drafting", "#6b7280", 0, 30),
    ("rulemaking", "final_rule", 2, "cba_development", "CBA Development", "#8b5cf6", 0, 21),
    ("rulemaking", "final_rule", 3, "chairman_review", "Chairman Review", "#f59e0b", 0, 14),
    ("rulemaking", "final_rule", 4, "commission_review", "Commission Review/Vote", "#f59e0b", 0, 21),
    ("rulemaking", "final_rule", 5, "ofr_submission", "OFR Submission", "#3b82f6", 0, 7),
    ("rulemaking", "final_rule", 6, "published", "Published", "#22c55e", 1, None),

    # ── REGULATORY ACTION: no_action_letter ──
    ("regulatory_action", "no_action_letter", 1, "request_received", "Request Received", "#6b7280", 0, 7),
    ("regulatory_action", "no_action_letter", 2, "staff_review", "Staff Review", "#3b82f6", 0, 21),
    ("regulatory_action", "no_action_letter", 3, "legal_analysis", "Legal Analysis", "#8b5cf6", 0, 14),
    ("regulatory_action", "no_action_letter", 4, "senior_review", "Senior Counsel Review", "#f59e0b", 0, 7),
    ("regulatory_action", "no_action_letter", 5, "agc_review", "AGC Review", "#f59e0b", 0, 7),
    ("regulatory_action", "no_action_letter", 6, "issued", "Issued", "#22c55e", 1, None),

    # ── REGULATORY ACTION: exemptive_order ──
    ("regulatory_action", "exemptive_order", 1, "request_received", "Request Received", "#6b7280", 0, 7),
    ("regulatory_action", "exemptive_order", 2, "staff_review", "Staff Review", "#3b82f6", 0, 21),
    ("regulatory_action", "exemptive_order", 3, "legal_analysis", "Legal Analysis", "#8b5cf6", 0, 21),
    ("regulatory_action", "exemptive_order", 4, "chairman_review", "Chairman Review", "#f59e0b", 0, 14),
    ("regulatory_action", "exemptive_order", 5, "commission_review", "Commission Review/Vote", "#f59e0b", 0, 14),
    ("regulatory_action", "exemptive_order", 6, "ofr_submission", "OFR Submission", "#3b82f6", 0, 7),
    ("regulatory_action", "exemptive_order", 7, "issued", "Issued", "#22c55e", 1, None),

    # ── REGULATORY ACTION: interpretive_guidance ──
    ("regulatory_action", "interpretive_guidance", 1, "concept", "Concept Development", "#6b7280", 0, 14),
    ("regulatory_action", "interpretive_guidance", 2, "drafting", "Drafting", "#3b82f6", 0, 21),
    ("regulatory_action", "interpretive_guidance", 3, "senior_review", "Senior Review", "#f59e0b", 0, 14),
    ("regulatory_action", "interpretive_guidance", 4, "commission_review", "Commission Review", "#f59e0b", 0, 14),
    ("regulatory_action", "interpretive_guidance", 5, "published", "Published", "#22c55e", 1, None),

    # ── REGULATORY ACTION: advisory_opinion ──
    ("regulatory_action", "advisory_opinion", 1, "request_received", "Request Received", "#6b7280", 0, 7),
    ("regulatory_action", "advisory_opinion", 2, "staff_analysis", "Staff Analysis", "#3b82f6", 0, 30),
    ("regulatory_action", "advisory_opinion", 3, "legal_review", "Legal Review", "#8b5cf6", 0, 14),
    ("regulatory_action", "advisory_opinion", 4, "general_counsel", "General Counsel Review", "#f59e0b", 0, 14),
    ("regulatory_action", "advisory_opinion", 5, "commission_review", "Commission Review", "#f59e0b", 0, 14),
    ("regulatory_action", "advisory_opinion", 6, "issued", "Issued", "#22c55e", 1, None),

    # ── REGULATORY ACTION: petition ──
    ("regulatory_action", "petition", 1, "received", "Received", "#6b7280", 0, 7),
    ("regulatory_action", "petition", 2, "staff_review", "Staff Review", "#3b82f6", 0, 30),
    ("regulatory_action", "petition", 3, "recommendation", "Recommendation", "#f59e0b", 0, 14),
    ("regulatory_action", "petition", 4, "commission_action", "Commission Action", "#f59e0b", 0, 21),
    ("regulatory_action", "petition", 5, "resolved", "Resolved", "#22c55e", 1, None),

    # ── REGULATORY ACTION: staff_letter ──
    ("regulatory_action", "staff_letter", 1, "request_received", "Request Received", "#6b7280", 0, 7),
    ("regulatory_action", "staff_letter", 2, "staff_review", "Staff Review", "#3b82f6", 0, 14),
    ("regulatory_action", "staff_letter", 3, "drafting", "Drafting Response", "#3b82f6", 0, 14),
    ("regulatory_action", "staff_letter", 4, "senior_review", "Senior Review", "#f59e0b", 0, 7),
    ("regulatory_action", "staff_letter", 5, "issued", "Issued", "#22c55e", 1, None),
]


def seed_team_members(conn: sqlite3.Connection) -> int:
    """Insert team members that don't already exist (by name)."""
    existing_names = set()
    for row in conn.execute("SELECT name FROM team_members"):
        existing_names.add(row[0])

    inserted = 0
    for member in SEED_TEAM_MEMBERS:
        if member["name"] in existing_names:
            continue
        conn.execute(
            """INSERT INTO team_members (name, role, gs_level, specializations, max_concurrent)
               VALUES (?, ?, ?, ?, ?)""",
            (
                member["name"],
                member["role"],
                member["gs_level"],
                member["specializations"],
                member["max_concurrent"],
            ),
        )
        inserted += 1

    if inserted > 0:
        conn.commit()
    logger.info(f"Team members: {inserted} new, {len(existing_names)} existing")
    return inserted


def seed_stage_templates(conn: sqlite3.Connection) -> int:
    """Insert default stage templates if none exist."""
    count = conn.execute("SELECT COUNT(*) FROM stage_templates").fetchone()[0]
    if count > 0:
        logger.info(f"Stage templates already seeded ({count} exist), skipping")
        return 0

    inserted = 0
    for row in STAGE_TEMPLATES:
        conn.execute(
            """INSERT INTO stage_templates
               (module, item_type, stage_order, stage_key, stage_label,
                stage_color, is_terminal, sla_days)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            row,
        )
        inserted += 1

    conn.commit()
    logger.info(f"Seeded {inserted} stage templates")
    return inserted


def seed_all(conn: sqlite3.Connection) -> dict:
    """Run all seed operations. Returns counts."""
    return {
        "team_members": seed_team_members(conn),
        "stage_templates": seed_stage_templates(conn),
    }
