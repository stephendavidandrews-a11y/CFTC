# 2026-03-24 GPT Audit Report

Audit scope: remote Mac mini repository at `/Users/stephen/Documents/Website/cftc`

Verification notes:
- Frontend production build completed successfully on the Mac mini.
- Tracker test suite passed: `275 passed in 2.75s`.
- AI test suite failed: `47 failed, 106 passed, 17 errors in 4.33s`.
- Live endpoint probes were run against `127.0.0.1:8004` and `127.0.0.1:8006` on the Mac mini to verify selected auth and error-handling behavior.

## Summary Table

| Category | Critical | High | Medium | Low |
| --- | ---: | ---: | ---: | ---: |
| Functional Completeness | 0 | 1 | 2 | 0 |
| Data Integrity | 0 | 0 | 0 | 0 |
| Cross-Service Consistency | 0 | 0 | 1 | 1 |
| Error Handling | 0 | 1 | 1 | 1 |
| Security | 1 | 0 | 0 | 0 |
| Configuration and Deployment | 0 | 1 | 1 | 0 |
| Code Quality | 0 | 0 | 1 | 1 |
| UI/UX Consistency | 0 | 0 | 0 | 1 |
| Performance Concerns | 0 | 0 | 2 | 0 |
| Schema vs. Code Drift | 0 | 0 | 0 | 0 |

## Category 1: Functional Completeness

[high] Intelligence brief detail endpoints do not return correct not-found responses  
Location: `services/ai/app/routers/intelligence.py:38-47,60-70`  
Issue: `GET /ai/api/intelligence/briefs/{brief_id}` returns `({"error": "Brief not found"}, 404)` instead of raising an HTTP exception, which FastAPI serializes as a `200 OK` response body containing `[{"error":"Brief not found"},404]`. `GET /ai/api/intelligence/briefs/by-date/{brief_type}/{brief_date}` also returns an error payload with HTTP 200 when no brief exists. A live probe against the running AI service confirmed the bad `200 OK` behavior for a missing brief ID. This breaks the expected request/response contract for consumers.  
Recommendation: Raise `HTTPException(status_code=404, detail=...)` for missing briefs in both handlers and keep the response shape consistent for success vs. not-found cases.

[medium] Development proxy configuration is broken and still points at retired service paths  
Location: `frontend/src/setupProxy.js:1-25`  
Issue: The proxy file is syntactically incomplete, calls `createProxyMiddleware` without importing it, and only proxies `/tracker` and `/intake`. It does not proxy `/ai`, which the current frontend uses heavily, and it still references the retired `/intake` backend surface. This makes local page/API behavior diverge from production and can cause frontend pages to fail in development even though the production build succeeds.  
Recommendation: Replace the file with a valid proxy configuration that imports `createProxyMiddleware`, proxies the current backend paths in use, and removes stale `/intake` assumptions if that service is no longer part of this app’s active frontend flow.

[medium] Team Workload page has no explicit API error state and no true empty-state path  
Location: `frontend/src/pages/tracker/TeamWorkloadPage.jsx:139-148,290-440`  
Issue: The page reads only `data` and `loading` from `useApi`, ignores the hook error state entirely, and renders either a loading screen or the workload layout. If either people or task fetch fails, the page falls through to empty summary cards with no visible explanation. If no team members qualify for `include_in_team_workload`, the page also renders a blank grouped layout rather than an explicit empty state.  
Recommendation: Consume and render the API error state, add a no-team-members empty state, and keep the page consistent with the other tracker pages that use visible error and empty-state components.

## Category 2: Data Integrity

No findings confirmed during this remote audit. Current tracker and AI schema foreign keys, enum usage, seed data, and batch-table validation appear aligned in the Mac mini repository state that was audited.

## Category 3: Cross-Service Consistency

[medium] Frontend AI client still exposes a nonexistent `digests` endpoint  
Location: `frontend/src/api/ai.js:327-335`; `services/ai/app/routers/intelligence.py:17-82`  
Issue: `getDigests()` calls `/ai/api/intelligence/digests`, but the AI service only mounts `/intelligence/briefs`, `/intelligence/briefs/{brief_id}`, `/intelligence/briefs/by-date/...`, and `/intelligence/generate`. Search across `frontend/src` found no current callers of `getDigests()`, so this is stale client surface area that no longer matches the server contract.  
Recommendation: Remove `getDigests()` if the feature is retired, or add the corresponding backend route and document its response shape if the feature is still intended.

[low] Developer page documents routes and infrastructure that do not match the running platform  
Location: `frontend/src/pages/developer/DeveloperPage.jsx:88-109,122-165,600,638,675,679-688`; `services/ai/app/routers/meeting_intelligence.py:11-78`; repository root deployment files  
Issue: The developer page still lists many `/intake/api/...` endpoints, references nonexistent AI endpoints such as `/ai/api/communications/:id/complete`, `/bundle-review/:id/confirm-all`, `/bundle-review/:id/undo`, `/entity-review/:id/new-person`, and outdated meeting-intelligence paths. It also still presents the architecture as Docker Compose based even though this repo has no `docker-compose.yml`, `compose.yml`, or Dockerfiles and the Mac mini deployment is running as native launchd services.  
Recommendation: Regenerate the endpoint catalog from mounted routers or maintain it from a single source of truth, and update the architecture text to reflect the actual Mac mini deployment model.

## Category 4: Error Handling

[high] AI startup path is not safe for in-memory test databases and causes cascading startup failures  
Location: `services/ai/tests/new/conftest.py:22-27`; `services/ai/app/db.py:15-24`; `services/ai/app/main.py:387-435`  
Issue: The new AI tests set `AI_DB_PATH=":memory:"`, but service startup initializes schema on one SQLite connection and then opens a second connection for crash recovery. Because SQLite `:memory:` databases are per-connection, the second connection does not contain the initialized tables and startup fails with `sqlite3.OperationalError: no such table: communications`. This directly explains the 17 startup errors and many of the downstream AI test failures on the Mac mini.  
Recommendation: Use a shared in-memory SQLite URI for tests, or refactor startup so schema init and crash recovery share the same connection/session abstraction.

[medium] Readiness middleware hides startup failures behind a generic 503  
Location: `services/ai/app/main.py:542-550`  
Issue: While `_ready` is false, every non-health request is converted to a generic `503 {"detail":"Service starting up","ready":false}` response. When startup actually fails, callers see the same 503 regardless of the underlying cause, which masked the real SQLite startup problem across multiple AI tests.  
Recommendation: Preserve a startup-failure state and surface it through a more descriptive readiness response or structured error payload so operators and tests can distinguish “still booting” from “boot failed.”

[low] Tracker pre-commit health check is built with brittle string replacement  
Location: `services/ai/app/pipeline/orchestrator.py:746-758`  
Issue: The writeback preflight derives the tracker health URL by calling `TRACKER_BASE_URL.replace("/tracker", "") + "/tracker/health"`. This is fragile if the configured base URL changes shape, contains `/tracker` more than once, or already includes a trailing path variant.  
Recommendation: Parse the configured URL and join paths explicitly, or store a dedicated tracker service origin/base separately from the API prefix.

## Category 5: Security

[critical] Multiple AI operational endpoints are mounted without authentication, including mutating administrative actions  
Location: `services/ai/app/main.py:601-605`; `services/ai/app/routers/health.py:15-179`; `services/ai/app/routers/events.py:32-62`  
Issue: The AI app mounts `health.router` and `events.router` without the `_ai_auth_dep` dependency, while most business routers are protected. That leaves the following endpoints unauthenticated on the live Mac mini service: `GET /ai/api/health`, `GET /ai/api/errors`, `GET /ai/api/errors/history`, `GET /ai/api/costs`, `GET /ai/api/notifications/status`, `POST /ai/api/notifications/flush`, `POST /ai/api/notifications/test`, `POST /ai/api/stuck-recovery/trigger`, and `GET /ai/api/events/stream`. Live probes confirmed these routes return HTTP 200 without credentials, while protected business endpoints such as `/ai/api/communications` return HTTP 401. The mutating endpoints can trigger operational side effects without authentication.  
Recommendation: Apply the AI auth dependency to the operational routers or split public liveness checks from privileged operational/admin routes and protect the latter explicitly.

## Category 6: Configuration and Deployment

[high] Startup scripts and backup scripts are hardcoded to a stale filesystem layout that does not match the live Mac mini deployment  
Location: `services/tracker/start_tracker.sh:4,9,17-18`; `services/ai/start.sh:8-20`; `services/ai/start_ai.sh:4,9,17-20`; `scripts/backup_dbs.sh:3-4,19`; `services/scripts/backup_databases.py:32-40`  
Issue: Several scripts hardcode `/Users/stephen/Documents/Website/cftc/...` absolute paths and, for tracker/AI startup, point database and upload paths at `volumes/...`. The current repository defaults and live Mac mini services use `services/.../data` and `services/.../uploads` instead. This makes the fresh-start/deployment path inconsistent and increases the chance that operators start the wrong database or a nonexistent path.  
Recommendation: Centralize runtime paths in env/config, remove the stale `volumes/...` assumptions, and ensure the checked-in startup scripts match the actual launchd deployment layout.

[medium] Environment variable documentation is incomplete for the current runtime contract  
Location: `.env.example:14-42`; `services/ai/app/config.py:25-31`; `services/ai/app/main.py:309-313`; `services/ai/app/pipeline/stages/transcription.py:42-52`  
Issue: `.env.example` documents the basic tracker and AI credentials/paths, but it does not document `TRACKER_BASE_URL`, `TRACKER_URL`, or `NATIVE_WORKER_URL`, all of which are consumed by the current AI service code paths. That makes clean setup and environment parity harder, especially because the code uses both `TRACKER_URL` and `TRACKER_BASE_URL` in different places.  
Recommendation: Document every env var actually read by the current services, consolidate duplicate tracker-base settings where possible, and add one authoritative setup section for Mac mini deployment.

## Category 7: Code Quality

[medium] `NotificationPanel` is dead code and still imports a removed API module  
Location: `frontend/src/components/shared/NotificationPanel.jsx:1-90`  
Issue: `NotificationPanel` imports `getNotifications` and `markNotificationRead` from `../../api/pipeline`, but there is no active `api/pipeline` client in the current frontend surface. Search across `frontend/src` found no imports of `NotificationPanel`, so the component is both stale and unused. Keeping it in tree increases confusion and makes future refactors harder because it implies a still-supported notification path that no longer exists.  
Recommendation: Remove the component if the feature is retired, or reconnect it to the current API layer and mount it in the active UI if notifications are still intended.

[low] Several files are now large enough that review and maintenance costs are high  
Location: `services/ai/app/pipeline/stages/extraction.py` (2125 lines); `frontend/src/pages/review/BundleReviewDetailPage.jsx` (1777 lines); `frontend/src/pages/settings/AISettingsPage.jsx` (1760 lines); `frontend/src/pages/tracker/MeetingDetailPage.jsx` (1431 lines); `frontend/src/pages/tracker/TasksPage.jsx` (1307 lines)  
Issue: Core pipeline and UI flows are concentrated in very large files, making the code harder to reason about, harder to test in isolation, and more brittle when multiple edits are needed. This is especially visible in the AI extraction stage and the largest review/detail pages.  
Recommendation: Split these files by responsibility into smaller components/modules with isolated helpers, view sections, and service logic.

## Category 8: UI/UX Consistency

[low] Several live pages bypass shared theme tokens and define their own badge color systems  
Location: `frontend/src/pages/intelligence/DailyBriefPage.jsx:6-12`; `frontend/src/pages/tracker/ContextNotesPage.jsx:5-20,178-182`; `frontend/src/pages/review/CommitQueuePage.jsx:40-45`  
Issue: These pages define raw hex-based color maps for tags, note categories, posture badges, and commit states instead of deriving badge/status styling from shared theme tokens or shared badge components. That increases visual drift risk across the app and makes future theme changes harder to apply consistently.  
Recommendation: Move status/category badge palettes into shared theme or badge helpers and have the pages consume those tokens rather than maintaining page-local color maps.

## Category 9: Performance Concerns

[medium] Tracker AI-context endpoints assemble large unpaginated snapshots and derived datasets  
Location: `services/tracker/app/routers/ai_context.py:16-40,43-159,166-260`  
Issue: `GET /tracker/ai-context` and `GET /tracker/ai-context/intelligence-data` return whole-context payloads that include open matters, active people, active organizations, recent meetings, standalone tasks, and multiple intelligence lists without pagination or response-size controls. This increases payload size and query cost as production data grows.  
Recommendation: Add scope controls, row caps, or incremental/since-token options for large consumers, and log payload/query sizes so growth becomes visible before the endpoint turns into a bottleneck.

[medium] Multiple frontend pages fetch 500-2000 records and do client-side filtering/aggregation  
Location: `frontend/src/pages/tracker/TeamWorkloadPage.jsx:139-145`; `frontend/src/pages/tracker/TasksPage.jsx:349-364`; `frontend/src/pages/tracker/PeoplePage.jsx:117-125`; `frontend/src/pages/tracker/MattersPage.jsx:119-121`  
Issue: Several pages request very large lists up front (`limit: 500` and, for team workload, `limit: 2000`) and then compute views in the browser. This works at current data size but scales poorly, increases page load cost, and duplicates aggregation work that could live in targeted backend endpoints.  
Recommendation: Introduce paginated/default-limited list APIs for browse pages and add dedicated summary endpoints for views such as team workload that currently require loading the full task set into the browser.

## Category 10: Schema vs. Code Drift

No findings confirmed during this remote audit. In the Mac mini repository state that was audited, the current tracker schema, AI schema, enum manifest, seed data, batch validation, `VALID_ITEM_TYPES`, and item converter surface appear aligned. The main drift still present is API/client and deployment-documentation drift already captured in Categories 3 and 6.
