# Full Platform Audit — CFTC Regulatory Operations Platform

Static audit of the current repository state across the React frontend, tracker service, AI service, scripts, and deployment/config files. This report documents findings only; it does not apply fixes.

## Summary Table

| Category | Critical | High | Medium | Low |
|---|---:|---:|---:|---:|
| 1. Functional Completeness | 0 | 2 | 3 | 0 |
| 2. Data Integrity | 0 | 2 | 1 | 0 |
| 3. Cross-Service Consistency | 0 | 3 | 0 | 0 |
| 4. Error Handling | 0 | 1 | 1 | 1 |
| 5. Security | 0 | 2 | 1 | 0 |
| 6. Configuration and Deployment | 0 | 2 | 2 | 0 |
| 7. Code Quality | 0 | 0 | 3 | 1 |
| 8. UI/UX Consistency | 0 | 0 | 2 | 0 |
| 9. Performance Concerns | 0 | 2 | 2 | 0 |
| 10. Schema vs. Code Drift | 0 | 1 | 3 | 0 |

## Category 1: Functional Completeness

### [high] Bundle review queue does not refresh after undo events
**Location:** `frontend/src/pages/review/BundleReviewQueuePage.jsx:140-147`; `services/ai/app/routers/communications.py:584-598`  
**Issue:** The page subscribes to `communication_undo` in `useAIEvents(...)`, but the effect only registers refresh handlers for `review_ready` and `bundle_review_complete`. The backend publishes `communication_undo` and moves the communication back to `bundle_review_in_progress`, so the queue stays stale after an undo until the user refreshes manually.  
**Recommendation:** Register a `communication_undo` handler that calls `refetch()`, and consider centralizing the subscribed-event list and handler list so they cannot drift apart.

### [high] Meetings page archive action calls an update shape the backend cannot accept
**Location:** `frontend/src/pages/tracker/MeetingsPage.jsx:82-84`; `services/tracker/app/validators.py:132-147`; `services/tracker/app/schema.py:146-170`  
**Issue:** The UI calls `updateMeeting(id, { status: "archived" })`, but `UpdateMeeting` has no `status` field and the `meetings` table has no `status` column. The button is therefore wired to an unsupported contract.  
**Recommendation:** Either add a real archive mechanism for meetings end-to-end, or remove/replace the archive action so the UI only exposes operations the tracker actually supports.

### [medium] Meetings date filters are UI-only because the tracker list route ignores them
**Location:** `frontend/src/pages/tracker/MeetingsPage.jsx:188-203`; `frontend/src/api/tracker.js:172-173`; `services/tracker/app/routers/meetings.py:17-27`  
**Issue:** The frontend renders `date_from` and `date_to` inputs and sends those query params, but the tracker list route does not accept or apply either filter. Users can change the controls without affecting results.  
**Recommendation:** Add `date_from` and `date_to` support to `GET /tracker/meetings`, or remove the filters from the page until backend support exists.

### [medium] Organizations page exposes sort options that never take effect
**Location:** `frontend/src/pages/tracker/OrganizationsPage.jsx:63-65`; `frontend/src/pages/tracker/OrganizationsPage.jsx:124-190`; `services/tracker/app/routers/organizations.py:41-58`  
**Issue:** The frontend offers sorting by `active_matters` and `people_count`, but the router validates `sort_by` against `{"name", "organization_type", "created_at"}` before adding those computed fields back into the sort set. Any request for the computed sorts gets reset to `name`.  
**Recommendation:** Validate against the full set of supported sort keys before coercing, and add a regression test for computed-field sorting.

### [medium] Matters page “Needs My Attention” view never matches real owner names
**Location:** `frontend/src/pages/tracker/MattersPage.jsx:73-78`; `services/tracker/app/routers/matters.py:88-95`  
**Issue:** The saved view filters for `owner_name === "You"` or `next_step_owner_name === "You"`, but the tracker returns actual `full_name` values from the database. Unless a person is literally named “You,” the view remains empty.  
**Recommendation:** Replace the `"You"` sentinel with a real current-user identity mapping, or remove the saved view until user identity is modeled consistently.

## Category 2: Data Integrity

Static schema review did not reveal broken foreign-key references in the current tracker table definitions. The concrete integrity issues are enum and status-drift problems:

### [high] Matter validators still enforce retired enum vocabularies
**Location:** `services/tracker/app/validators.py:223-306`; `services/tracker/app/routers/lookups.py:6-37`  
**Issue:** `CreateMatter` and `UpdateMatter` still accept older matter types, statuses, sensitivities, and boss-involvement values that no longer match the canonical lookup enums exposed to the frontend. This creates a split contract between form options and backend validation.  
**Recommendation:** Generate matter validators from the shared enum source, or import the canonical enum definitions into the validator layer so only one source of truth exists.

### [high] Batch writes only enforce enum validity for `tasks.task_mode`
**Location:** `services/tracker/app/routers/batch.py:52-69`; `services/tracker/app/routers/batch.py:182-195`  
**Issue:** The batch endpoint validates column existence for every allowed table, but enum enforcement is limited to `tasks.task_mode`. Reviewed AI writes can therefore persist invalid matter, meeting, decision, and other enum values as long as the column names exist.  
**Recommendation:** Extend batch-time enum validation to every enum-backed column that the tracker validators and lookup endpoints treat as constrained.

### [medium] People open-task counts still use retired terminal status values
**Location:** `services/tracker/app/routers/people.py:66-75`; `services/tracker/app/routers/lookups.py:38-39`  
**Issue:** The `open_tasks` count excludes `('completed', 'deferred')`, but the canonical task status enum now uses `done` rather than `completed`. Completed tasks can therefore remain counted as “open” on people records and pages that consume `open_tasks`.  
**Recommendation:** Update the query to use the current status vocabulary and add a test that verifies open-task counts against the canonical task status enum.

## Category 3: Cross-Service Consistency

### [high] Frontend development proxy is still wired for removed routes and omits `/ai`
**Location:** `frontend/src/setupProxy.js:1-37`; `frontend/src/api/ai.js:1-58`  
**Issue:** The React dev proxy still routes `/pipeline` and `/intake`, but the frontend AI client calls `/ai/api/*` and no `/ai` proxy is defined. In local `react-scripts start` mode, AI API calls will miss the backend entirely.  
**Recommendation:** Update `setupProxy.js` to proxy `/ai` to the AI service and remove stale proxy entries that no longer reflect the active frontend/backend contract.

### [high] Daily brief job expects tracker response fields that the tracker no longer returns
**Location:** `services/ai/app/jobs/daily_brief.py:103-141`; `services/tracker/app/routers/ai_context.py:75-85`; `services/tracker/app/routers/ai_context.py:127-136`  
**Issue:** The daily brief formats pending decisions with `owner_name` and `due_date`, and overdue tasks with `assignee_name` and `days_overdue`. The tracker intelligence endpoint now returns `decision_owner_name`, `decision_due_date`, and `owner_name` for overdue tasks, with no `days_overdue` field. This makes the generated brief incomplete or misleading.  
**Recommendation:** Align the brief generator with the current tracker response schema and add a contract test that exercises the live `/tracker/ai-context/intel` payload shape.

### [high] Weekly brief and dev report still depend on removed people fields
**Location:** `services/ai/app/jobs/weekly_brief.py:319-345`; `services/ai/app/jobs/dev_report.py:77-90`; `services/tracker/app/schema.py:717-760`  
**Issue:** The weekly brief still reads `relationship_lane`, and the dev report’s `PEOPLE_FIELDS` list still includes `relationship_lane` and `working_style_notes`, even though those legacy columns are dropped by the current tracker schema migration path. The reports are auditing and summarizing fields the live app no longer stores.  
**Recommendation:** Remove retired fields from report-generation code and define these report inputs from the live schema or lookup metadata rather than hand-maintained field lists.

## Category 4: Error Handling

### [high] Frontend API client drops the backend’s structured `error.message` envelope
**Location:** `frontend/src/api/client.js:15-26`; `frontend/src/api/client.js:63-71`  
**Issue:** `fetchJSON` unwraps `parsed.detail ?? parsed`, and `ApiError` only surfaces `detail.message` when `detail` itself is the error object. Tracker and AI routes often return `{ error: { code, message, details } }`, so the user-facing message frequently falls back to the generic HTTP status text instead of the server’s actual explanation.  
**Recommendation:** Normalize both `detail` and `error` envelopes in `fetchJSON` so the frontend always preserves the backend’s human-readable message.

### [medium] Team workload page has no error state
**Location:** `frontend/src/pages/tracker/TeamWorkloadPage.jsx:139-148`; `frontend/src/pages/tracker/TeamWorkloadPage.jsx:290-302`  
**Issue:** The page reads only `loading` from its `useApi` hooks and never renders an error branch. If either people or task loading fails, the page can end up empty or misleading without telling the user why.  
**Recommendation:** Surface `error` from both API hooks, merge the failure state, and render a consistent retry/error UI.

### [low] Meetings page still uses `alert()` and console logging instead of the app’s notification pattern
**Location:** `frontend/src/pages/tracker/MeetingsPage.jsx:89-92`  
**Issue:** Meeting action failures are surfaced via `console.error(...)` and `alert(...)`, while the rest of the app uses shared toast/notification patterns. This produces an inconsistent failure experience and makes error handling harder to standardize.  
**Recommendation:** Route meeting action failures through the shared notification/toast system and reserve `alert()` for truly blocking flows only if needed.

## Category 5: Security

Targeted config review showed `.env*` is gitignored in `.gitignore:1-5`, and CORS is explicitly whitelisted in both service config files rather than set to `*`. The concrete security findings are:

### [high] AI service authentication is optional and fails open when env vars are missing
**Location:** `services/ai/app/main.py:329-356`; `services/ai/app/main.py:366-376`  
**Issue:** AI endpoint protection is only enabled if both `AI_AUTH_USER` and `AI_AUTH_PASS` are set. Otherwise the app logs a warning and mounts its routers without authentication. That is materially weaker than the tracker’s fail-closed behavior in production.  
**Recommendation:** Make AI auth mandatory in production, mirroring the tracker’s startup guard, and fail startup when credentials are absent in production mode.

### [high] Rate limiting is bypassed in the deployed Cloudflare tunnel topology
**Location:** `services/tracker/app/middleware.py:124-126`; `services/ai/app/middleware.py:124-126`; `docs/RATE_LIMITING.md:22-31`; `docs/RATE_LIMITING.md:59-60`  
**Issue:** Both services exempt `127.0.0.1` from rate limiting, and the documented tunnel architecture makes all external traffic appear as `127.0.0.1`. In practice, the limiter never throttles real external clients.  
**Recommendation:** Read the real client IP from `CF-Connecting-IP` or `X-Forwarded-For`, remove localhost from the exempt list for external traffic, and add an integration test for proxied requests.

### [medium] Health and metrics endpoints are exposed without authentication
**Location:** `services/tracker/app/main.py:226-233`; `services/ai/app/routers/health.py:14-49`; `services/ai/app/main.py:358-366`  
**Issue:** Tracker `/tracker/health` and `/tracker/metrics`, plus AI `/ai/api/health` and `/ai/api/metrics`, are mounted outside the normal router auth dependencies. These endpoints expose service status, queue counts, versioning, and spend information without credentials.  
**Recommendation:** Gate operational endpoints behind auth or restrict them to internal-only listeners/proxy rules if public exposure is not intended.

## Category 6: Configuration and Deployment

### [high] Service and backup scripts hardcode Mac-specific absolute paths
**Location:** `scripts/backup_dbs.sh:3-19`; `services/ai/start_ai.sh:4-23`; `services/tracker/start_tracker.sh:4-21`  
**Issue:** Multiple scripts are pinned to `/Users/stephen/Documents/Website/...` and assume a single local filesystem layout. That makes the repo harder to relocate, harder to bootstrap on a fresh machine, and harder to document as a reusable deployment.  
**Recommendation:** Parameterize repo roots and data paths through environment variables or a shared config loader, with sensible defaults only for local development.

### [high] `services/ai/start.sh` uses a divergent port and startup contract from the rest of the repo
**Location:** `services/ai/start.sh:8-22`; `services/ai/start_ai.sh:17-23`; `services/ai/app/config.py:38-39`  
**Issue:** `start.sh` hardcodes the AI DB path and tracker URL and launches uvicorn on port `8007`, while the rest of the repo and service config consistently treat the AI app as port `8006`. There are now two conflicting startup paths for the same service.  
**Recommendation:** Remove or update the stale startup script so there is exactly one documented, tested way to launch the AI service.

### [medium] Transcription stage hardcodes the native worker host outside development mode
**Location:** `services/ai/app/pipeline/stages/transcription.py:42-52`  
**Issue:** `NATIVE_WORKER_BASE` defaults to `http://localhost:8005` and only becomes configurable via `NATIVE_WORKER_URL` in development mode. Production and other non-dev environments cannot redirect the worker base without editing code.  
**Recommendation:** Read the native worker base URL from environment/config in all environments, with `localhost` only as a fallback default.

### [medium] Canonical startup relies on `nohup`, port killing, and no process supervision
**Location:** `scripts/start_services.sh:35-46`; `scripts/start_services.sh:50-71`; `docs/RESIDUAL_RISKS.md:20-23`  
**Issue:** The repo’s startup script forcibly kills ports with `kill -9`, starts services via `nohup`, and has no restart supervision. The repo’s own residual-risks document calls out the lack of process supervision.  
**Recommendation:** Move service startup to a proper supervisor (`launchd`, `systemd`, or container orchestration) and reserve `start_services.sh` for local/dev convenience rather than canonical production control.

## Category 7: Code Quality

### [medium] Several core files have grown large enough to be maintenance hotspots
**Location:** `services/ai/app/pipeline/stages/extraction.py` (1894 lines); `frontend/src/pages/review/BundleReviewDetailPage.jsx` (1777 lines); `frontend/src/pages/settings/AISettingsPage.jsx` (1762 lines); `frontend/src/pages/tracker/MeetingDetailPage.jsx` (1431 lines); `frontend/src/pages/tracker/TasksPage.jsx` (1305 lines)  
**Issue:** Core page and pipeline files are carrying too many concerns in single modules, which raises review cost, makes regressions harder to isolate, and discourages focused tests.  
**Recommendation:** Split these files by concern: page layout vs. data hooks vs. row/detail subcomponents on the frontend, and prompt assembly vs. matching vs. post-processing in the AI extraction stage.

### [medium] Tracker drawer components duplicate shell styling and interaction scaffolding
**Location:** `MatterDrawer`, `MeetingDrawer`, `TaskDrawer`, `PersonDrawer`, `OrganizationDrawer`, `DocumentDrawer`, `DecisionDrawer` components under `frontend/src/components/tracker/`  
**Issue:** Drawer components repeat border, spacing, header, label, and action-button styles even though `DrawerShell.jsx` already exists. This makes UI fixes and pattern changes expensive because each drawer must be touched separately.  
**Recommendation:** Push the repeated chrome and footer behavior into shared drawer primitives and leave drawer-specific files responsible only for their form fields and entity-specific logic.

### [medium] Tracker startup duplicates logging/config initialization calls
**Location:** `services/tracker/app/main.py:58-61`  
**Issue:** `setup_logging("tracker")` and `validate_config()` are each called twice at startup. This is harmless most of the time, but it is a code-smell and makes startup side effects harder to reason about.  
**Recommendation:** Collapse tracker startup initialization to a single call path and add a smoke test for startup side effects if needed.

### [low] Frontend test script exists, but the frontend has no test files
**Location:** `frontend/package.json:14-17`; `frontend/src` (no `*.test.*` or `*.spec.*` files found)  
**Issue:** The frontend advertises `react-scripts test`, but there is no meaningful frontend test suite in the repo. That leaves complex UI pages and interaction-heavy review flows unprotected by automated checks.  
**Recommendation:** Add targeted tests for the highest-risk frontend flows first: API client error handling, drawer submit/cancel behavior, queue refresh behavior, and table filtering/sorting logic.

## Category 8: UI/UX Consistency

### [medium] Shared UI components still hardcode status colors instead of consuming theme tokens
**Location:** `frontend/src/components/shared/ConfidenceIndicator.jsx:7-15`; `frontend/src/components/shared/Toast.jsx:4-9`; `frontend/src/pages/tracker/OrganizationsPage.jsx:143-149`  
**Issue:** Several shared components embed raw hex values for semantic colors instead of sourcing them from `theme.js`. This makes it harder to evolve the visual system consistently and causes semantic styles to drift page by page.  
**Recommendation:** Move semantic status colors into theme tokens and have shared components consume only the theme layer.

### [medium] Table pages and drawers do not follow one consistent interaction pattern
**Location:** `frontend/src/pages/tracker/MeetingsPage.jsx`; `frontend/src/pages/tracker/TeamWorkloadPage.jsx`; tracker drawer components under `frontend/src/components/tracker/`  
**Issue:** Some pages use server-side filtering, some use client-side saved views, some show no error state, and failure feedback varies between alerts and in-app notifications. Drawer shells also repeat custom open/close/save scaffolding rather than leaning fully on one shared pattern.  
**Recommendation:** Standardize list-page conventions and drawer interaction patterns in a small UI contract document, then refactor pages/components to conform to the shared behavior.

## Category 9: Performance Concerns

### [high] `/tracker/ai-context` returns a very large nested snapshot by default
**Location:** `services/tracker/app/routers/ai_context.py:16-38`; `services/tracker/app/routers/ai_context.py:166-250`  
**Issue:** The default AI context endpoint returns matters, people, organizations, recent meetings, and standalone tasks, and each matter carries nested tags, stakeholders, organizations, updates, tasks, and decisions. This is a large payload to compute and ship on every extraction run.  
**Recommendation:** Add leaner snapshot modes, incremental fetch options, or selective field projection so the AI service can ask only for the context it actually needs.

### [high] Brief/report jobs call paginated tracker endpoints without explicit limits or paging loops
**Location:** `services/ai/app/jobs/daily_brief.py:196-201`; `services/ai/app/jobs/weekly_brief.py:319-320`; `services/ai/app/jobs/weekly_brief.py:372-416`; `services/tracker/app/routers/people.py:27`; `services/tracker/app/routers/matters.py:41`; `services/tracker/app/routers/documents.py:29`  
**Issue:** Report jobs fetch `/people`, `/matters`, and `/documents` without explicit pagination parameters even though those endpoints default to `limit=100`. Once the data set grows past 100 rows, the reports silently truncate.  
**Recommendation:** Either request explicit large limits with paging loops, or add dedicated unpaginated/internal summary endpoints designed for report generation.

### [medium] Context note list endpoints do N+1 link lookups
**Location:** `services/tracker/app/routers/context_notes.py:130-149`; `services/tracker/app/routers/context_notes.py:190-198`  
**Issue:** After fetching the note list, the router performs a separate query for links for each note returned. The entity-specific variant repeats the same pattern. This scales poorly as note counts grow.  
**Recommendation:** Batch-fetch links for all returned note IDs in one query and attach them in memory.

### [medium] Team workload page pulls large datasets and aggregates everything client-side
**Location:** `frontend/src/pages/tracker/TeamWorkloadPage.jsx:139-166`; `frontend/src/pages/tracker/TeamWorkloadPage.jsx:150-288`  
**Issue:** The page fetches 500 people and 2000 tasks up front, then computes workload groupings, overdue counts, and manager breakdowns entirely in the browser. That increases page load cost and makes correctness depend on arbitrary frontend limits.  
**Recommendation:** Move workload aggregation to a tracker endpoint or dashboard summary route and let the frontend render pre-aggregated workload data.

## Category 10: Schema vs. Code Drift

### [high] Follow-up policy toggles are still seeded and persisted even though follow-ups are no longer a standalone item type
**Location:** `services/ai/config/ai_policy.json:30`; `services/ai/app/config.py:165-190`; `services/ai/app/pipeline/stages/extraction_models.py:166-180`; `services/ai/app/pipeline/stages/extraction.py:496-505`; `services/ai/app/pipeline/stages/extraction.py:925-929`  
**Issue:** The default AI policy and persisted policy still carry `propose_follow_ups`, and `trust_config` still includes `"follow_up"`, but `POLICY_TOGGLE_MAP` no longer maps follow-ups because they are modeled as tasks with `task_mode: "follow_up"`. The configuration surface and runtime toggle wiring have drifted apart.  
**Recommendation:** Remove retired follow-up toggles from policy/config, migrate existing persisted policy files, and make the UI expose only still-wired extraction controls.

### [medium] Schema/version handshake under-reports what the AI layer can actually write
**Location:** `services/tracker/app/routers/schema_version.py:13-20`; `services/tracker/app/routers/schema_version.py:53-64`; `services/tracker/app/routers/batch.py:25-31`  
**Issue:** The schema handshake advertises `TRACKER_SCHEMA_VERSION = "1.0.0"` and an `AI_WRITABLE_TABLES` list that omits `context_notes`, `context_note_links`, and `person_profiles`, even though the live batch endpoint now allows writes to those tables. Downstream services cannot rely on the handshake to detect real write capabilities.  
**Recommendation:** Update the schema version and the advertised writable-table list whenever batch-write capabilities change, and add a contract test that compares the handshake output to `ALLOWED_TABLES`.

### [medium] Meeting writeback only persists a subset of the meeting schema’s supported fields
**Location:** `services/ai/app/writeback/item_converters.py:366-419`; `services/tracker/app/schema.py:306-322`  
**Issue:** Meeting writeback drops fields like `external_parties_attend` at the meeting level and ignores richer participant fields such as `attendance_status`, `organization_id`, `stance_confidence`, `position_strength`, `movement_summary`, and `follow_up_expected` even though the tracker schema supports them. Reviewed meeting intelligence cannot round-trip all of the schema’s modeled detail.  
**Recommendation:** Either narrow the tracker schema to the subset the AI layer is meant to own, or extend writeback converters to persist the full supported meeting/participant contract.

### [medium] Extraction tiering still contains placeholder branches for stakeholder and organization matching
**Location:** `services/ai/app/pipeline/stages/extraction.py:189-211`  
**Issue:** The tiering logic still uses literal `pass` statements for stakeholder-based and organization-list-based matter escalation checks. This means the extraction stage is not fully using the relationship data already present in the tracker snapshot to determine tier relevance.  
**Recommendation:** Implement the remaining tier checks and add tests for stakeholder-linked and organization-linked transcript/entity cases so the matching logic covers the full schema design.
