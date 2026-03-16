#!/bin/bash
cd "$(dirname "$0")/.."
python3 scripts/generate-schema-manifest.py
echo "Schema manifest generated at frontend/src/data/schema-manifest.json"
