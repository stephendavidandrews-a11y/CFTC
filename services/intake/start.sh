#!/bin/bash
export PATH="/opt/homebrew/bin:$PATH"
cd /Users/stephen/Documents/Website/cftc/services/intake
exec .venv/bin/python3.11 -m uvicorn main:app --host 0.0.0.0 --port 8005
