#!/bin/bash
# Local dev convenience script — start tracker service
cd "$(dirname "$0")"
if [ -d .venv ]; then
    source .venv/bin/activate
fi
uvicorn app.main:app --host 127.0.0.1 --port 8004
