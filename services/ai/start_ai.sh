#!/bin/bash
set -euo pipefail

APP_DIR="/Users/stephen/Documents/Website/cftc/services/ai"
cd "$APP_DIR"

# Load env
set -a
source /Users/stephen/Documents/Website/cftc/.env
set +a

# Ensure Homebrew PATH
export PATH="/opt/homebrew/bin:$PATH"

# Set app-specific env
export APP_ENV=production
export AI_DB_PATH="/Users/stephen/Documents/Website/cftc/volumes/ai/data/ai.db"
export AI_UPLOAD_DIR="/Users/stephen/Documents/Website/cftc/volumes/ai/uploads"
export AI_AUDIO_WATCH_DIR="/Users/stephen/Documents/Website/cftc/volumes/ai/audio-inbox"
export TRACKER_BASE_URL="http://127.0.0.1:8004/tracker"
export PYTHONUNBUFFERED=1

exec "$APP_DIR/.venv/bin/uvicorn" app.main:app --host 127.0.0.1 --port 8006
