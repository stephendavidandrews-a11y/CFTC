# CFTC Regulatory Operations Platform

Multi-service system for CFTC regulatory operational tracking, AI-powered extraction, and intelligence.

**Live**: `cftc.stephenandrews.org` (Cloudflare tunnel)

## Services

| Route | Service | Port | Source | Database |
|-------|---------|------|--------|----------|
| `/` | Command Center (React) | via nginx | `frontend/` | — |
| `/tracker/*` | Tracker (FastAPI) | 8004 | `services/tracker/` | tracker.db |
| `/ai/*` | AI Layer (FastAPI) | 8006 | `services/ai/` | ai.db |
| `/intake/*` | Intake (FastAPI) | 8005 | `services/intake/` | intake.db |

## Quick Start

```bash
# Start all services (sources .env automatically)
make start

# Stop all services
make stop

# Restart
make restart

# Or directly:
./scripts/start_services.sh all
./scripts/start_services.sh tracker   # single service
./scripts/start_services.sh stop
```

Logs are written to `logs/{tracker,ai,intake}.log` (append mode).

## Testing

```bash
make test          # all services (354 tests)
make test-tracker  # tracker only (203 tests)
make test-ai       # AI only (143 tests)
make test-intake   # intake only (8 tests)
make lint          # ruff check on all services
make check         # lint + test
```

## Structure

```
frontend/              React Command Center (nginx serves SPA + proxies)
services/
  tracker/             Tracker service (matters, tasks, people, orgs)
  ai/                  AI extraction, review, intelligence, writeback
  intake/              Intake ingest service (audio processing)
scripts/
  start_services.sh    Canonical startup (sources .env, manages all services)
  backup.sh            Database backup
docs/                  Implementation notes and residual risks
logs/                  Service log files (gitignored)
.env                   Secrets (gitignored)
```

## Auth

| Service | Mechanism | Env Vars |
|---------|-----------|----------|
| Tracker | HTTP Basic (required) | `TRACKER_USER`, `TRACKER_PASS` |
| AI | HTTP Basic (optional) | `AI_AUTH_USER`, `AI_AUTH_PASS` |
| Intake | HTTP Basic (required) | `PIPELINE_USER`, `PIPELINE_PASS` |

Health and metrics endpoints are unauthenticated on all services.

## Environment

All services use `python-dotenv` to load `.env` from the repo root.

Required variables:
- `ANTHROPIC_API_KEY` — LLM API access
- `TRACKER_USER`, `TRACKER_PASS` — Tracker auth
- `PIPELINE_USER`, `PIPELINE_PASS` — Intake auth
- `SECRET_KEY` — Session signing

Optional:
- `AI_AUTH_USER`, `AI_AUTH_PASS` — Enable AI service auth
- `TRACKER_DB_PATH` — Override default DB location
- `LOG_LEVEL` — Logging verbosity (default: INFO)
- `ENVIRONMENT` — `development` (console logs) or `production` (JSON logs)
