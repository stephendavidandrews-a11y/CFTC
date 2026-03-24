#!/bin/bash
set -euo pipefail

APP_DIR="/Users/stephen/Documents/Website/cftc/services/tracker"
cd "$APP_DIR"

# Load env
set -a
source /Users/stephen/Documents/Website/cftc/.env
set +a

# Ensure Homebrew PATH
export PATH="/opt/homebrew/bin:$PATH"

# Set app-specific env
export APP_ENV=production
export TRACKER_DB_PATH="$APP_DIR/data/tracker.db"
export TRACKER_UPLOAD_DIR="$APP_DIR/uploads"
export PYTHONUNBUFFERED=1

exec "$APP_DIR/.venv/bin/uvicorn" app.main:app --host 127.0.0.1 --port 8004
