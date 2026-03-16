#!/bin/bash
cd /Users/stephen/Documents/Website/cftc/services/tracker
source .venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8004
