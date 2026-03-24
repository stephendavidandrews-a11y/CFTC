"""
Configuration for the CFTC Regulatory Ops Tracker.
"""
from dotenv import load_dotenv
load_dotenv()

import os
import sys
from pathlib import Path

# Base directory
BASE_DIR = Path(__file__).parent.parent

# Database
# In production the TRACKER_DB_PATH env var MUST be set via LaunchAgent/docker-compose.
# The fallback default exists only for local development.
_db_path_raw = os.environ.get("TRACKER_DB_PATH", "")
_db_path_source = "env" if _db_path_raw else "default"
TRACKER_DB_PATH = Path(_db_path_raw) if _db_path_raw else (BASE_DIR / "data" / "tracker.db")
TRACKER_DB_PATH_SOURCE = _db_path_source  # "env" or "default" — exposed for startup logging

# File uploads
UPLOAD_DIR = Path(os.environ.get(
    "TRACKER_UPLOAD_DIR",
    str(BASE_DIR / "uploads")
))
MAX_UPLOAD_SIZE = 100 * 1024 * 1024  # 100 MB

# Server
PORT = int(os.environ.get("TRACKER_PORT", "8004"))
HOST = os.environ.get("TRACKER_HOST", "0.0.0.0")

# Auth — fail closed in production
AUTH_USER = os.environ.get("TRACKER_USER", "")
AUTH_PASS = os.environ.get("TRACKER_PASS", "")

_app_env = os.environ.get("APP_ENV", "development")
if _app_env == "production" and (not AUTH_USER or not AUTH_PASS):
    print("FATAL: TRACKER_USER and TRACKER_PASS env vars are required in production", file=sys.stderr)
    sys.exit(1)

# CORS
CORS_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:5173",
    "https://cftc.stephenandrews.org",
]


def validate_config():
    """Validate required configuration at startup. Raises on missing required values."""
    errors = []
    if not TRACKER_DB_PATH.parent.exists():
        errors.append(f"DB parent directory does not exist: {TRACKER_DB_PATH.parent}")
    if not AUTH_USER:
        errors.append("TRACKER_USER env var is empty or not set")
    if not AUTH_PASS:
        errors.append("TRACKER_PASS env var is empty or not set")
    if errors:
        import sys
        for err in errors:
            print(f"CONFIG ERROR: {err}", file=sys.stderr)
        if os.environ.get("APP_ENV") == "production":
            sys.exit(1)
        else:
            print("WARNING: Running with config errors (non-production mode)", file=sys.stderr)
