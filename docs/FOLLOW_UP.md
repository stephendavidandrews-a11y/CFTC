# Follow-Up Work Items

Post-remediation tracked items. None are merge blockers.

## 1. Frontend Test Framework
- **Priority**: Medium
- **Why it matters**: ErrorBoundary, fetch timeout/retry, SSE backoff are code-only verified. No automated regression protection for the React frontend.
- **Next action**: Install Vitest + React Testing Library. Write component tests for ErrorBoundary (forced crash renders fallback), fetchJSON (timeout triggers AbortError, retry on 503), useAIEvents (reconnect with backoff on disconnect).

## 2. DB CHECK Constraints
- **Priority**: Low
- **Why it matters**: API-layer Literal validation catches invalid values at the HTTP boundary. DB-level CHECK constraints would be defense-in-depth against direct DB writes or bugs in new endpoints.
- **Next action**: Add CHECK constraints via schema migration v3 for matter_type, status, priority, sensitivity, boss_involvement_level, task_mode. Use the existing `schema_versions` migration system.

## 3. CI/CD Pipeline
- **Priority**: Medium
- **Why it matters**: Tests and lint only run locally (Makefile + pre-commit hook). No automated test-on-push or deployment pipeline. Regressions can ship if developer forgets to run `make check`.
- **Next action**: Add GitHub Actions workflow: `make lint && make test` on push/PR to main. Optionally add SSH deploy step via Cloudflare tunnel for staging.

## 4. Process Supervision
- **Priority**: Medium
- **Why it matters**: Services run via `nohup`. If a service crashes, it stays down until manually restarted. No auto-restart, no crash alerting.
- **Next action**: Create launchd plist files for each service (macOS equivalent of systemd). Place in `~/Library/LaunchAgents/`. Set `KeepAlive: true` for auto-restart. The plist should source `.env` and write logs to `logs/`.

## 5. Rate Limiting Runtime Verification
- **Priority**: Low
- **Why it matters**: Rate limiter code is present but untestable from localhost (127.0.0.1 excluded by design). Cannot confirm it works for real external traffic.
- **Next action**: Update middleware to read `CF-Connecting-IP` header (see `docs/RATE_LIMITING.md` for exact code). Then test by sending 130+ requests through `https://cftc.stephenandrews.org` and confirming 429.

## 6. Circuit Breaker / Upstream Resilience
- **Priority**: Low
- **Why it matters**: AI service calls tracker via HTTP. If tracker is down, AI retries the LLM call (not the tracker call) and eventually fails. No circuit breaker prevents cascading failures.
- **Next action**: Add a simple circuit breaker to `services/ai/app/writeback/tracker_client.py`: track consecutive failures, open circuit after 5 failures, half-open after 30s. Use the existing `httpx.AsyncClient` timeout as the health probe.
