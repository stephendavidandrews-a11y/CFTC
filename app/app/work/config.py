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
WORK_ITEM_STATUSES = ("not_started", "in_progress", "in_review", "blocked", "completed")
TASK_STATUSES = ("todo", "in_progress", "done", "deferred")
PRIORITY_LABELS = ("critical", "high", "medium", "low")
ASSIGNMENT_ROLES = ("lead", "assigned", "reviewer", "contributor")
NOTE_TYPES = ("general", "one_on_one", "decision", "followup", "meeting")
TASK_SOURCES = ("manual", "pipeline", "eo_tracker", "comments", "bottleneck_alert")
