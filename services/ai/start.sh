#!/bin/bash
# CFTC AI Service startup script
# Usage: ./start.sh

cd "$(dirname "$0")"

# Load env vars
export AI_DB_PATH=/Users/stephen/Documents/Website/cftc/volumes/ai/data/ai.db
export TRACKER_BASE_URL=http://localhost:8004/tracker

# Source .env for secrets (TRACKER_USER, TRACKER_PASS, OPENAI_API_KEY, SMTP_*, etc)
while IFS== read -r key value; do
    [[ -z "$key" || "$key" == \#* ]] && continue
    export "$key=$value"
done < .env

echo "Starting CFTC AI Service..."
echo "  DB: $AI_DB_PATH"
echo "  Tracker: $TRACKER_BASE_URL"
echo "  Model: $(grep primary_extraction_model config/ai_policy.json 2>/dev/null | head -1)"

exec .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8006
