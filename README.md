# CFTC Regulatory Operations Platform

Multi-service system for CFTC regulatory pipeline management, vulnerability scoring, and operational tracking.

**Live**: `cftc.stephenandrews.org` (basic auth protected)

## Services

| Route | Service | Source | Database |
|-------|---------|--------|----------|
| `/` | Command Center (React dashboard) | `frontend/` | — |
| `/pipeline/*` | Pipeline Backend (FastAPI) | `services/pipeline/` | pipeline.db |
| `/tracker/*` | Tracker (FastAPI) | `services/tracker/` | tracker.db |

## Structure

```
frontend/              React Command Center (homepage)
services/
  pipeline/            Pipeline manager backend
  tracker/             Tracker service
  work/                Work management module (runs inside pipeline-backend)
data/                  Read-only DBs (cftc_regulatory.db, eo_tracker.db)
docker-compose.yml     Production compose (4 containers + Caddy)
Caddyfile              Caddy (personal site only — nginx handles app routing)
Dockerfile.pipeline    Pipeline backend build
.env                   Production secrets (gitignored)
```

## Deploy

```bash
docker compose up -d --build
docker compose logs -f
```

## Auth

All endpoints require HTTP Basic Auth (`PIPELINE_USER`/`PIPELINE_PASS`, `TRACKER_USER`/`TRACKER_PASS`).
nginx (inside command-center container) adds an additional auth layer at the proxy level.

## Secrets

- `.env` at repo root — gitignored
- Required: `ANTHROPIC_API_KEY`, `PIPELINE_USER`, `PIPELINE_PASS`, `TRACKER_USER`, `TRACKER_PASS`, `SECRET_KEY`
