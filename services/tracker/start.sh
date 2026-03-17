#!/bin/bash
# Local dev convenience script — start tracker service
cd "$(dirname "$0")"
if [ -d .venv ]; then
    source .venv/bin/activate
fi
uvicorn app.main:app --host 0.0.0.0 --port 8004
