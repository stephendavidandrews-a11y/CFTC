"""
Seed data for the Work Management module.
Inserts project types and templates. Idempotent.
"""

import sqlite3
import logging

logger = logging.getLogger(__name__)

SEED_PROJECT_TYPES = [
    ("rulemaking", "Rulemaking", "NPRMs, ANPRMs, final rules, IFRs, DFRs", 1),
    ("guidance", "Guidance & Interpretive Letters", "Staff advisories, no-action letters, interpretive letters", 2),
    ("exemptive_relief", "Exemptive Relief", "Petitions for exemption under CEA Section 4(c), etc.", 3),
    ("interagency", "Interagency Work", "Project Crypto deliverables, PWG items, bilateral coordination", 4),
    ("congressional", "Congressional/Legislative", "Hill inquiries, testimony support, legislation analysis", 5),
    ("legal_opinion", "Internal Legal Opinion", "Legal analysis requested by other CFTC divisions", 6),
    ("enforcement", "Enforcement Support", "Referrals from/to Division of Enforcement", 7),
    ("foia", "FOIA Response", "FOIA requests requiring attorney time", 8),
    ("policy_research", "Policy Research & Memo", "Loper Bright analysis, CEA authority mapping, policy development", 9),
]

SEED_TEMPLATES = [
    # rulemaking
    ("rulemaking", "Draft rule text", None, 1),
    ("rulemaking", "Economic / cost-benefit analysis", None, 2),
    ("rulemaking", "Chairman briefing memo", None, 3),
    ("rulemaking", "Commission review package", None, 4),
    ("rulemaking", "OFR submission preparation", None, 5),
    ("rulemaking", "Comment analysis (if applicable)", None, 6),
    # guidance
    ("guidance", "Research & legal analysis", None, 1),
    ("guidance", "Draft letter/advisory", None, 2),
    ("guidance", "Internal review", None, 3),
    ("guidance", "Division head sign-off", None, 4),
    ("guidance", "Issuance/publication", None, 5),
    # exemptive_relief
    ("exemptive_relief", "Petition review & analysis", None, 1),
    ("exemptive_relief", "Staff recommendation memo", None, 2),
    ("exemptive_relief", "Draft exemptive order", None, 3),
    ("exemptive_relief", "Commission consideration", None, 4),
    # interagency
    ("interagency", "CFTC position paper", None, 1),
    ("interagency", "Internal clearance", None, 2),
    ("interagency", "Interagency coordination", None, 3),
    ("interagency", "Final deliverable", None, 4),
    # policy_research
    ("policy_research", "Scope & methodology", None, 1),
    ("policy_research", "Research & drafting", None, 2),
    ("policy_research", "Internal review", None, 3),
    ("policy_research", "Final memo", None, 4),
]


def seed_all(conn: sqlite3.Connection):
    """Seed project types and templates. Idempotent."""
    # Project types
    existing = conn.execute("SELECT COUNT(*) FROM project_types").fetchone()[0]
    if existing == 0:
        conn.executemany(
            "INSERT INTO project_types (type_key, label, description, sort_order) VALUES (?, ?, ?, ?)",
            SEED_PROJECT_TYPES,
        )
        logger.info(f"Seeded {len(SEED_PROJECT_TYPES)} project types")

    # Templates
    existing = conn.execute("SELECT COUNT(*) FROM project_type_templates").fetchone()[0]
    if existing == 0:
        conn.executemany(
            "INSERT INTO project_type_templates (project_type, item_title, parent_ref, item_sort_order) VALUES (?, ?, ?, ?)",
            SEED_TEMPLATES,
        )
        logger.info(f"Seeded {len(SEED_TEMPLATES)} template items")

    conn.commit()
