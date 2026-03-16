"""
Configuration for the CFTC Regulatory Ops Tracker.
"""
import os
import sys
from pathlib import Path

# Base directory
BASE_DIR = Path(__file__).parent.parent

# Database
TRACKER_DB_PATH = Path(os.environ.get(
    "TRACKER_DB_PATH",
    str(BASE_DIR / "data" / "tracker.db")
))

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
