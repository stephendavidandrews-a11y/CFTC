# CFTC Regulatory Operations Platform

Multi-service system for CFTC regulatory operational tracking, AI-powered extraction, and intelligence.

**Live**: `cftc.stephenandrews.org` (Cloudflare tunnel)

## Services

| Route | Service | Source | Database |
|-------|---------|--------|----------|
| `/` | Command Center (React dashboard) | `frontend/` | — |
| `/tracker/*` | Tracker (FastAPI) | `services/tracker/` | tracker.db |
| `/ai/*` | AI Layer (FastAPI) | `services/ai/` | ai.db |

## Structure

```
frontend/              React Command Center (nginx serves SPA + proxies)
services/
  tracker/             Tracker service (matters, tasks, people, orgs)
  ai/                  AI extraction, review, intelligence, writeback
  intake/              Intake ingest service (GPU-bound, runs natively on port 8005)
docker-compose.yml     Production compose (tracker, ai, command-center, caddy)
Caddyfile              Caddy (personal site only — nginx handles app routing)
.env                   Production secrets (gitignored)
```

## Deploy

```bash
docker compose up -d --build
docker compose logs -f
```

## Auth

- **Tracker**: HTTP Basic Auth (`TRACKER_USER`/`TRACKER_PASS`) on all endpoints
- **AI Layer**: Optional HTTP Basic Auth (`AI_AUTH_USER`/`AI_AUTH_PASS`) — disabled by default, enable via env vars
- **Edge**: Cloudflare tunnel restricts external access

## Secrets

- `.env` at repo root — gitignored
- Required: `ANTHROPIC_API_KEY`, `TRACKER_USER`, `TRACKER_PASS`, `SECRET_KEY`
- Optional: `AI_AUTH_USER`, `AI_AUTH_PASS` (enables AI service auth)
