# CFTC Comment Letter Analysis System

## Phase 1: Core Infrastructure

Automated system to monitor, analyze, and report on public comment letters submitted to the CFTC during notice-and-comment rulemaking.

---

## Quick Start

```bash
# 1. Start infrastructure (Postgres, Redis, MinIO)
docker compose up -d

# 2. Copy and configure environment
cp .env.example .env
# Edit .env → add your Regulations.gov API key

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run the server (auto-creates tables + seeds data)
uvicorn app.main:app --reload --port 8000

# 5. Seed Tier 1 organizations
python -m scripts.seed_tier1_orgs
```

Or use the all-in-one script: `bash start.sh`

**API docs**: http://localhost:8000/docs

---

## Phase 1 Capabilities

| Feature | Status |
|---------|--------|
| PostgreSQL schema (rules, comments, tags, orgs) | ✅ |
| Federal Register API integration (rule detection) | ✅ |
| Regulations.gov API integration (comment fetching) | ✅ |
| PDF download + text extraction (pdfplumber + OCR) | ✅ |
| S3 storage for PDF files | ✅ |
| Initial tier classification (org matching + heuristics) | ✅ |
| REST API with search/filter/pagination | ✅ |
| Priority classification (crypto, event contracts, etc.) | ✅ |
| Tier 1 organization seed data (80+ orgs) | ✅ |

---

## API Endpoints

### Rules
| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/rules` | List tracked rules (sorted by priority) |
| `GET` | `/api/v1/rules/{docket}` | Get rule details |
| `POST` | `/api/v1/rules/detect-new` | Scan Federal Register for new CFTC rules |
| `POST` | `/api/v1/rules/add-docket` | Manually add a docket to track |

### Comments
| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/comments` | Search/filter comments (tier, sentiment, org, date, full-text) |
| `GET` | `/api/v1/comments/{doc_id}` | Full comment detail with text + tags |
| `POST` | `/api/v1/comments/fetch` | Pull comments from Regulations.gov for a docket |
| `GET` | `/api/v1/comments/stats/{docket}` | Docket statistics (tier breakdown, sentiment, etc.) |

### Organizations
| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/tier1-orgs` | List all Tier 1 organizations |
| `POST` | `/api/v1/tier1-orgs` | Add a Tier 1 organization |
| `DELETE` | `/api/v1/tier1-orgs/{id}` | Remove a Tier 1 organization |

---

## Project Structure

```
cftc-comment-system/
├── app/
│   ├── main.py                  # FastAPI app entry point
│   ├── api/
│   │   └── routes.py            # All REST endpoints
│   ├── core/
│   │   ├── config.py            # Settings from .env
│   │   └── database.py          # SQLAlchemy engine + session
│   ├── models/
│   │   └── models.py            # ORM models (5 tables)
│   ├── schemas/
│   │   └── schemas.py           # Pydantic request/response models
│   └── services/
│       ├── federal_register.py  # Federal Register API client
│       ├── regulations_gov.py   # Regulations.gov API client
│       ├── pdf_extraction.py    # PDF text extraction (pdfplumber + OCR)
│       ├── storage.py           # S3 file storage
│       └── ingestion.py         # Orchestration pipeline
├── scripts/
│   └── seed_tier1_orgs.py       # Seed 80+ Tier 1 organizations
├── alembic/                     # Database migrations
├── docker-compose.yml           # Postgres + Redis + MinIO
├── requirements.txt
├── .env.example
└── start.sh                     # One-command setup
```

---

## Typical Workflow

```bash
# 1. Detect new CFTC proposed rules
curl -X POST http://localhost:8000/api/v1/rules/detect-new

# 2. Or manually add a known docket
curl -X POST http://localhost:8000/api/v1/rules/add-docket \
  -H "Content-Type: application/json" \
  -d '{"docket_number": "CFTC-2024-0007"}'

# 3. Fetch all comments for that docket
curl -X POST http://localhost:8000/api/v1/comments/fetch \
  -H "Content-Type: application/json" \
  -d '{"docket_number": "CFTC-2024-0007"}'

# 4. Browse comments with filters
curl "http://localhost:8000/api/v1/comments?docket_number=CFTC-2024-0007&tier=1"

# 5. Get docket statistics
curl http://localhost:8000/api/v1/comments/stats/CFTC-2024-0007
```

---

## Next: Phase 2 (AI Processing Pipeline)

- Claude API integration for comment summarization
- Full tier classification with text analysis
- Form letter detection (text similarity matching)
- Sentiment analysis
- Legal citation extraction and tagging
