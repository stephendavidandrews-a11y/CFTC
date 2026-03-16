# CFTC Regulatory Operations Platform

Multi-service system for CFTC regulatory pipeline management, comment analysis, vulnerability scoring, and operational tracking.

**Live**: `cftc.stephenandrews.org` (basic auth protected)

## Services

| Route | Service | Source | Database |
|-------|---------|--------|----------|
| `/` | Command Center (React dashboard) | `frontend/` | — |
| `/pipeline/*` | Pipeline Backend (FastAPI) | `services/pipeline/` | pipeline.db |
| `/tracker/*` | Tracker (FastAPI) | `services/tracker/` | tracker.db |
| `/api/v1/*` | Comment Analysis (FastAPI) | `services/comments/` | comments.db |

## Structure

```
frontend/              React Command Center (homepage)
services/
  comments/            Comment analysis backend
  pipeline/            Pipeline manager backend
  tracker/             Tracker service
  work/                Work management module
data/                  Read-only DBs (cftc_regulatory.db, eo_tracker.db)
docker-compose.yml     Production compose (6 containers)
Caddyfile              Caddy reverse proxy + HTTPS
Dockerfile.pipeline    Pipeline backend build
.env                   Production secrets (gitignored)
```

## Deploy

```bash
docker compose up -d --build
docker compose logs -f
```

## Auth

All endpoints require HTTP Basic Auth (`PIPELINE_USER`/`PIPELINE_PASS`).
Caddy adds an additional auth layer at the proxy level.

## Secrets

- `.env` at repo root + `services/comments/.env` — both gitignored
- Required: `ANTHROPIC_API_KEY`, `PIPELINE_USER`, `PIPELINE_PASS`, `DB_PASSWORD`, `SECRET_KEY`
