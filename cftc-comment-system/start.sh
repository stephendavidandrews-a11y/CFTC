#!/usr/bin/env bash
# =============================================================================
# CFTC Comment System - Phase 1 Quick Start
# =============================================================================
set -euo pipefail

echo "========================================"
echo "  CFTC Comment Analysis System - Setup"
echo "========================================"

# 1. Check prerequisites
echo ""
echo "Checking prerequisites..."
command -v docker >/dev/null 2>&1 || { echo "❌ Docker is required. Install: https://docs.docker.com/get-docker/"; exit 1; }
command -v python3 >/dev/null 2>&1 || { echo "❌ Python 3.11+ is required."; exit 1; }
echo "✅ Prerequisites found"

# 2. Start infrastructure
echo ""
echo "Starting PostgreSQL, Redis, and MinIO..."
docker compose up -d
echo "Waiting for services to be healthy..."
sleep 5

# 3. Create .env if it doesn't exist
if [ ! -f .env ]; then
    echo ""
    echo "Creating .env from template..."
    cp .env.example .env
    echo "⚠️  Edit .env to add your Regulations.gov API key!"
    echo "   Get one at: https://open.gsa.gov/api/regulationsgov/"
fi

# 4. Install Python dependencies
echo ""
echo "Installing Python dependencies..."
pip install -r requirements.txt --quiet

# 5. Create MinIO bucket
echo ""
echo "Configuring MinIO bucket..."
python3 -c "
from app.services.storage import storage_service
try:
    storage_service.ensure_bucket_exists()
    print('✅ S3 bucket ready')
except Exception as e:
    print(f'⚠️  MinIO bucket setup skipped (will retry on first upload): {e}')
"

# 6. Seed Tier 1 organizations
echo ""
echo "Seeding Tier 1 organizations..."
python3 -m scripts.seed_tier1_orgs

# 7. Start the API server
echo ""
echo "========================================"
echo "  🚀 Starting API server on port 8000"
echo "========================================"
echo ""
echo "  API docs:  http://localhost:8000/docs"
echo "  Health:    http://localhost:8000/health"
echo ""
echo "  Key endpoints:"
echo "    POST /api/v1/rules/detect-new     — Check for new CFTC rules"
echo "    POST /api/v1/rules/add-docket     — Add a docket manually"
echo "    POST /api/v1/comments/fetch       — Fetch comments for a docket"
echo "    GET  /api/v1/rules                — List tracked rules"
echo "    GET  /api/v1/comments             — Search/filter comments"
echo "    GET  /api/v1/comments/stats/{id}  — Docket statistics"
echo ""

uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
