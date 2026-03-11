"""
Configuration for the Pipeline Manager module.

Database paths, constants, and controlled vocabularies.
"""

import os
from pathlib import Path

# ── Database Paths ────────────────────────────────────────────────────────

# Pipeline's own database (new, created by this module)
PIPELINE_DB_PATH = Path(__file__).parent / "data" / "pipeline.db"

# Read-only references to existing databases
CFTC_REGULATORY_DB_PATH = Path(
    os.environ.get(
        "CFTC_REGULATORY_DB_PATH",
        r"C:\Users\steph\OneDrive\Documents\CFTC\Authorities Scrapper\cftc_regulatory\cftc_regulatory.db",
    )
)

EO_TRACKER_DB_PATH = Path(
    os.environ.get(
        "EO_TRACKER_DB_PATH",
        r"C:\Users\steph\OneDrive\Documents\CFTC\Executive Order Tracker\eo_tracker\data\eo_tracker.db",
    )
)

# ── Document Storage ──────────────────────────────────────────────────────

PIPELINE_DOC_STORAGE = Path(__file__).parent / "data" / "documents"

# ── Modules ───────────────────────────────────────────────────────────────

MODULES = ("rulemaking", "regulatory_action")

# ── Rulemaking Item Types ─────────────────────────────────────────────────

RULEMAKING_ITEM_TYPES = (
    "NPRM",           # Notice of Proposed Rulemaking
    "IFR",            # Interim Final Rule
    "ANPRM",          # Advance Notice of Proposed Rulemaking
    "DFR",            # Direct Final Rule
    "final_rule",     # Final Rule (standalone, not from NPRM)
)

# ── Regulatory Action Item Types ──────────────────────────────────────────

REGULATORY_ACTION_ITEM_TYPES = (
    "no_action_letter",
    "exemptive_order",
    "interpretive_guidance",
    "advisory_opinion",
    "petition",
    "staff_letter",
)

ALL_ITEM_TYPES = RULEMAKING_ITEM_TYPES + REGULATORY_ACTION_ITEM_TYPES

# ── Deadline Types ────────────────────────────────────────────────────────

DEADLINE_TYPES = (
    "statutory",
    "eo",
    "pwg",
    "internal",
    "cra",
    "pra",
    "ofr",
    "comment_period",
    "oira_review",
    "chairman_imposed",
)

# ── Status Values ─────────────────────────────────────────────────────────

ITEM_STATUSES = ("active", "paused", "completed", "withdrawn", "archived")
DEADLINE_STATUSES = ("pending", "met", "missed", "waived", "extended")

# ── Priority ──────────────────────────────────────────────────────────────

PRIORITY_LABELS = ("critical", "high", "medium", "low")

PRIORITY_WEIGHTS = {
    "eo_alignment": 0.20,
    "chairman_priority": 0.25,
    "pwg_deadline": 0.15,
    "stage1_score": 0.15,
    "deadline_proximity": 0.15,
    "congressional_interest": 0.05,
    "comment_volume": 0.05,
}

# ── Assignment Roles ──────────────────────────────────────────────────────

ASSIGNMENT_ROLES = ("lead", "backup", "contributor", "reviewer")

# ── Decision Log Action Types ─────────────────────────────────────────────

DECISION_LOG_TYPES = (
    "stage_change",
    "priority_change",
    "assignment_change",
    "deadline_change",
    "status_change",
    "decision",
    "note",
    "chairman_direction",
    "commission_vote",
)
