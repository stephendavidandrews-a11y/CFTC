"""
Configuration for the CFTC AI Layer service.

Loads ai_policy.json for runtime policy, env vars for infrastructure.
"""
import json
import os
import sys
import uuid
import logging
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Infrastructure config (env vars)
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).parent.parent
PROMPT_BASE_DIR = BASE_DIR / "prompts"

AI_DB_PATH = Path(os.environ.get("AI_DB_PATH", str(BASE_DIR / "data" / "ai.db")))
AI_UPLOAD_DIR = Path(os.environ.get("AI_UPLOAD_DIR", str(BASE_DIR / "uploads")))
AI_AUDIO_WATCH_DIR = Path(os.environ.get("AI_AUDIO_WATCH_DIR", str(BASE_DIR / "audio-inbox")))

TRACKER_BASE_URL = os.environ.get("TRACKER_BASE_URL", "http://tracker:8004/tracker")
TRACKER_USER = os.environ.get("TRACKER_USER", "")
TRACKER_PASS = os.environ.get("TRACKER_PASS", "")

# Optional Basic auth for AI service endpoints
AI_AUTH_USER = os.environ.get("AI_AUTH_USER", "")
AI_AUTH_PASS = os.environ.get("AI_AUTH_PASS", "")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

PORT = int(os.environ.get("AI_PORT", "8006"))
HOST = os.environ.get("AI_HOST", "0.0.0.0")

LOCAL_TIMEZONE = os.environ.get("LOCAL_TIMEZONE", "America/New_York")

APP_ENV = os.environ.get("APP_ENV", "development")
if APP_ENV == "production" and not ANTHROPIC_API_KEY:
    print("FATAL: ANTHROPIC_API_KEY env var required in production", file=sys.stderr)
    sys.exit(1)

CORS_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:5173",
    "https://cftc.stephenandrews.org",
]

# ---------------------------------------------------------------------------
# Policy config (ai_policy.json)
# ---------------------------------------------------------------------------

CONFIG_PATH = Path(os.environ.get(
    "AI_CONFIG_PATH",
    str(BASE_DIR / "config" / "ai_policy.json")
))

_policy_cache: dict | None = None


def load_policy() -> dict:
    """Load ai_policy.json from disk. Returns cached copy if already loaded."""
    global _policy_cache
    if _policy_cache is not None:
        return _policy_cache
    if not CONFIG_PATH.exists():
        logger.warning("ai_policy.json not found at %s — using defaults", CONFIG_PATH)
        _policy_cache = _default_policy()
        save_policy(_policy_cache)
        return _policy_cache
    with open(CONFIG_PATH, "r") as f:
        _policy_cache = json.load(f)
    logger.info("Loaded AI policy from %s", CONFIG_PATH)
    return _policy_cache


def save_policy(policy: dict):
    """Persist policy to disk and update cache."""
    global _policy_cache
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_PATH, "w") as f:
        json.dump(policy, f, indent=2)
    _policy_cache = policy
    logger.info("Saved AI policy to %s", CONFIG_PATH)


def reload_policy() -> dict:
    """Force-reload policy from disk (invalidates cache)."""
    global _policy_cache
    _policy_cache = None
    return load_policy()


def update_policy_section(section: str, data: dict, db=None) -> dict:
    """
    Update a single section of the policy. Logs changes to config_audit_log
    if a db connection is provided.
    """
    policy = load_policy()
    if section not in policy:
        raise ValueError(f"Unknown config section: {section}")

    old_data = policy[section]
    old_section = json.dumps(old_data, sort_keys=True)
    policy[section] = data
    save_policy(policy)
    new_section = json.dumps(data, sort_keys=True)

    # Audit log
    if db and old_section != new_section:
        _log_config_change(db, section, old_data, data)

    return policy


def _log_config_change(db, section: str, old_data, new_data):
    """Write field-level changes to config_audit_log."""
    old_flat = _flatten(old_data) if isinstance(old_data, dict) else {}
    new_flat = _flatten(new_data) if isinstance(new_data, dict) else {}
    all_keys = set(old_flat) | set(new_flat)
    for key in all_keys:
        old_val = json.dumps(old_flat.get(key), default=str)
        new_val = json.dumps(new_flat.get(key), default=str)
        if old_val != new_val:
            db.execute("""
                INSERT INTO config_audit_log (id, section, field, old_value, new_value)
                VALUES (?, ?, ?, ?, ?)
            """, (str(uuid.uuid4()), section, key, old_val, new_val))
    db.commit()


def _flatten(d: dict, prefix: str = "") -> dict:
    """Flatten nested dict to dot-notation keys."""
    out = {}
    for k, v in d.items():
        key = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            out.update(_flatten(v, key))
        else:
            out[key] = v
    return out


def _default_policy() -> dict:
    """Return day-one default policy."""
    return {
        "user_config": {
            "tracker_person_id": None,
            "email_addresses": [],
            "name": "",
            "title": ""
        },
        "routing_policy": {
            "new_matter_threshold": "low",
            "match_confidence_minimum": 0.5,
            "multi_matter_enabled": True,
            "max_new_matters_per_communication": 3,
            "standalone_items_enabled": True
        },
        "extraction_policy": {
            "propose_tasks": True,
            "propose_decisions": False,
            "propose_matter_updates": True,
            "propose_meeting_records": True,
            "propose_new_matters": False,
            "propose_stakeholders": True,
            "propose_follow_ups": True,
            "propose_new_people": True,
            "propose_new_organizations": True,
            "propose_status_changes": False,
            "propose_documents": True,
            "capture_stance_data": True,
            "capture_intelligence_notes": True
        },
        "sensitivity_policy": {
            "flag_enforcement_sensitive": True,
            "flag_congressional_sensitive": True,
            "flag_deliberative": True
        },
        "trust_config": {
            action: {"mode": "review_required", "auto_commit_threshold": None}
            for action in [
                "task", "matter_update", "decision", "status_change",
                "meeting_record", "stakeholder_addition", "new_matter",
                "new_person", "new_organization", "follow_up", "document"
            ]
        },
        "model_config": {
            "primary_extraction_model": "claude-sonnet-4-20250514",
            "escalation_model": "claude-opus-4-6",
            "haiku_model": "claude-haiku-4-5-20251001",
            "opus_retry_triggers": {
                "low_confidence": True,
                "over_splitting": True,
                "uncertainty_flags": True,
                "validation_failure": True
            },
            "active_prompt_versions": {
                "extraction": "v1.0.0",
                "haiku_cleanup": "v1.0.0",
                "haiku_enrichment": "v1.0.0"
            },
            "daily_budget_usd": 10.00,
            "budget_warning_threshold": 0.80
        },
        "proactive_config": {
            "daily_digest": {
                "enabled": False,
                "schedule_time": "06:00",
                "email_digest": False
            },
            "weekly_brief": {
                "enabled": False,
                "schedule_day": "sunday",
                "schedule_time": "20:00",
                "auto_boss_brief": False
            },
            "realtime_alerts": {
                "enabled": False,
                "check_interval_minutes": 60
            },
            "deadline_thresholds": {
                "critical_days": 3,
                "warning_days": 7,
                "external_deadline_critical_days": 3,
                "decision_deadline_critical_days": 3,
                "work_deadline_critical_days": 3
            },
            "staleness_thresholds": {
                "critical_this_week_days": 5,
                "important_this_month_days": 10,
                "strategic_slow_burn_days": 21,
                "monitoring_only_days": 30
            },
            "followup_thresholds": {
                "overdue_alert": True,
                "upcoming_days": 3
            },
            "workload_thresholds": {
                "multiplier": 2.0,
                "max_matters_flag": 5
            },
            "snooze_options_days": [3, 7, 14, 30]
        }
    }
