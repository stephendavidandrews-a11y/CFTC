# Residual Risks — Post-Remediation

Items verified in code but not runtime-tested, and known deferred work.

## Code-Only Verified (not runtime-testable from CLI)

| Item | Location | What It Does | Why Not Runtime-Tested |
|------|----------|-------------|----------------------|
| React ErrorBoundary | `frontend/src/components/shared/ErrorBoundary.jsx` | Catches component render errors, shows fallback UI | Requires browser + forced React component crash |
| Frontend fetch timeout | `frontend/src/api/client.js` (30s AbortController) | Aborts requests after 30s | Requires slow/hanging backend endpoint |
| Frontend fetch retry | `frontend/src/api/client.js` (1 retry on 502/503/504) | Retries on gateway errors | Requires backend returning 5xx |
| SSE exponential backoff | `frontend/src/hooks/useAIEvents.js` (5→10→20→60s) | Reconnects with increasing delay on SSE disconnect | Requires killing SSE stream mid-connection |
| Rate limiting | All 3 `middleware.py` | 120/60 req/min per IP | All traffic arrives from 127.0.0.1 via tunnel (see docs/RATE_LIMITING.md) |

## Deferred Work

| Item | Priority | Notes |
|------|----------|-------|
| DB CHECK constraints | Low | API-layer Literal validation is in place. DB-level enforcement is defense-in-depth only. |
| Frontend test framework | Medium | No Jest/Vitest configured. Zero frontend test coverage. |
| CI/CD pipeline | Medium | Makefile + pre-commit hook exist. No GitHub Actions or automated deployment. |
| Circuit breaker (AI→Tracker) | Low | AI retries 3x on LLM failures. No circuit breaker for tracker HTTP calls. |
| Process supervision | Medium | Services run via `nohup`. No systemd/launchd auto-restart on crash. `scripts/start_services.sh` is the canonical startup method. |
| Intake test coverage | Low | 9 auth tests added. No endpoint-level functional tests. |

## Accepted Risks

| Risk | Mitigation |
|------|-----------|
| Single Mac Mini, no redundancy | Acceptable for dev/staging. Not a production deployment. |
| Manual deployment via SSH | `make start` is the canonical command. No CD pipeline. |
| SQLite (no concurrent writers) | `busy_timeout=30000` + single-writer architecture. Adequate for current load. |
