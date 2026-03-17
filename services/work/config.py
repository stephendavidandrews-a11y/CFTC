"""
Configuration for the Work Management module.
"""

import os
from pathlib import Path

# Work management database (separate SQLite file)
WORK_DB_PATH = Path(__file__).parent / "data" / "work.db"

# Pipeline database (for team_members cross-reference)
PIPELINE_DB_PATH = Path(__file__).parent.parent / "pipeline" / "data" / "pipeline.db"

# Status values
PROJECT_STATUSES = ("active", "paused", "completed", "archived")
WORK_ITEM_STATUSES = ("not_started", "in_progress", "in_review", "waiting_on_stephen", "blocked", "completed")
TASK_STATUSES = ("todo", "in_progress", "done", "deferred")
PRIORITY_LABELS = ("critical", "high", "medium", "low")
ASSIGNMENT_ROLES = ("lead", "assigned", "reviewer", "contributor")
NOTE_TYPES = ("general", "one_on_one", "decision", "followup", "meeting")
NOTE_CONTEXT_TYPES = ("general", "one_on_one", "team_meeting", "hallway", "email", "work_review")
TASK_SOURCES = ("manual", "pipeline", "eo_tracker", "bottleneck_alert")

# Project sources
PROJECT_SOURCES = (
    "Chairman", "General Counsel", "Commissioner", "PWG", "Treasury",
    "SEC", "Fed Reserve", "OCC", "FDIC", "FSOC", "OMB", "DOJ",
    "Congress", "Self-Initiated", "Other",
)

# Team member profile enums
WORKING_STYLES = ("detail_oriented", "big_picture", "balanced", "methodical", "creative")
COMMUNICATION_PREFERENCES = ("email", "slack", "in_person", "phone")
CAPACITY_LEVELS = ("available", "stretched", "at_capacity", "overloaded", "on_leave")

# Interagency
AGENCY_LIST = (
    "SEC", "Treasury", "Fed Reserve", "OCC", "FDIC", "FSOC", "OMB",
    "DOJ", "FTC", "CFPB", "FHFA", "NCUA", "OFR", "State Regulators", "Other",
)
RELATIONSHIP_STATUSES = ("close_ally", "regular_contact", "acquaintance", "new", "dormant")
