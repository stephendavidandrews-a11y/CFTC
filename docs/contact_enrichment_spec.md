# Contact Enrichment (Hunter.io) — Design Spec

Status: **draft for review** — no code written yet.

## Problem

The `people` table is populated by hand and by AI extraction from transcripts. Both
paths produce records with a name and an organization but no email — the field that
makes a contact actionable. Meanwhile the operator has contact lists living in
spreadsheets (conference attendee lists, Hill staff directories, LinkedIn exports)
that never make it into the tracker because typing 300 rows in by hand is not a
plan.

This spec covers: upload a spreadsheet of people, have Hunter.io find their work
email addresses (and optionally LinkedIn/title), review the results, and commit the
accepted ones into `people` with full provenance — plus get the original
spreadsheet back with the columns filled.

## Non-goals

- **Not** a live LinkedIn network sync. See "LinkedIn" below for why, and what
  replaces it.
- **Not** a Hunter Domain Search / "discover everyone at this company" flow. That
  produces N candidate rows per input row and needs a different review UI. Deferred.
- **Not** a bulk re-verification job over the existing `people` table. Natural
  phase 2, and the Hunter client built here is the prerequisite.
- **Not** a general-purpose spreadsheet importer for matters, tasks, or documents.
  People only.

## Decisions

| Decision | Choice | Why |
|---|---|---|
| Service | `services/ai`, new `app/enrichment/` module | Reuses the async-job + review + writeback shape the service already has. Tracker stays system of record behind the existing HTTP boundary. |
| Hunter mode | Email Finder, plus Combined Enrichment behind a per-job toggle | Finder is the core need (name + org to email). Enrichment adds LinkedIn/title for a second credit, so it is opt-in per job. |
| Output | Both — write to `people` **and** offer the filled sheet back | Covers "grow the CRM" and "I needed this list for something else". |
| Review gate | Review queue with confidence-based auto-accept | Matches the five review queues already in the app. A wrong email on a Hill staffer is a real-world embarrassment, so nothing is written unreviewed by default. |
| Table reuse | **New dedicated tables**, mirroring the review-bundle shape rather than reusing it | `review_bundles`, `commit_batches`, and `tracker_writebacks` all declare `communication_id TEXT NOT NULL REFERENCES communications(id)`. An enrichment job has no communication. Making that column nullable would touch five live review queues; a parallel set of tables is the cheaper and safer path. |

---

## Source types

The importer accepts two shapes, selected at upload time.

### 1. Generic spreadsheet
`.csv`, `.xlsx`. Arbitrary headers. The operator maps columns in a confirmation
step before anything is sent to Hunter (see Stage 2).

### 2. LinkedIn connections export (preset)
LinkedIn's own sanctioned data export: Settings → Data Privacy → Get a copy of your
data → Connections. Fixed, known headers:

```
First Name, Last Name, URL, Email Address, Company, Position, Connected On
```

Because the schema is fixed, this preset skips column mapping entirely. Two things
make it the highest-value input:

- `URL` is the person's LinkedIn profile — already present, no Hunter enrichment
  credit needed for these rows.
- `Email Address` is populated only where that connection opted to share it
  (typically a minority of rows). **The blanks are precisely the rows Hunter should
  fill.** LinkedIn establishes who you know and where they currently work; Hunter
  supplies the address LinkedIn withholds.
- `Connected On` seeds provenance and can inform `relationship_category`.

## LinkedIn: why export and not API

Recorded here so the question does not get re-litigated:

- The Connections API was retired in 2015. Sign In with LinkedIn / OIDC returns only
  the authenticated user's own profile.
- Marketing, Talent, and Sales Navigator APIs are partner-gated and expose no
  connections-list endpoint.
- Scraping breaches §8.2 of the LinkedIn User Agreement and risks account
  restriction. The connection list is behind authentication, so the public-data
  reasoning in *hiQ v. LinkedIn* does not apply.
- Third-party resellers of scraped LinkedIn data carry the same ToS exposure plus a
  worse data-egress story than Hunter.

The export is free, sanctioned, and already in the exact format this feature
ingests. Cost: it is a manual re-export rather than a live sync. Acceptable on a
quarterly cadence for a contact list.

---

## Data model

New tables in `ai.db`, appended to `TABLES` in `services/ai/app/schema.py` with
matching entries in `INDEXES`.

```sql
CREATE TABLE IF NOT EXISTS enrichment_jobs (
    id TEXT PRIMARY KEY,
    source_type TEXT NOT NULL,            -- 'spreadsheet' | 'linkedin_export'
    original_filename TEXT NOT NULL,
    stored_path TEXT NOT NULL,            -- under AI_UPLOAD_DIR/enrichment/{job_id}/
    file_sha256 TEXT NOT NULL,            -- re-upload detection
    status TEXT NOT NULL DEFAULT 'uploaded',
    -- uploaded -> mapping -> ready -> running -> paused
    --   -> awaiting_review -> committing -> complete | failed | cancelled
    column_mapping TEXT,                  -- JSON: sheet header -> canonical field
    enrich_profile INTEGER DEFAULT 0,     -- Combined Enrichment toggle (LinkedIn/title)
    row_count INTEGER,
    rows_processed INTEGER DEFAULT 0,
    rows_found INTEGER DEFAULT 0,
    rows_not_found INTEGER DEFAULT 0,
    rows_skipped_cache INTEGER DEFAULT 0,
    credits_estimated INTEGER,
    credits_spent INTEGER DEFAULT 0,
    credit_cap INTEGER,                   -- hard stop; job pauses when reached
    egress_acknowledged_at TEXT,          -- operator confirmed third-party send
    error_message TEXT,
    created_by TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS enrichment_rows (
    id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL REFERENCES enrichment_jobs(id),
    row_number INTEGER NOT NULL,          -- 1-based position in source sheet
    raw_row TEXT NOT NULL,                -- JSON of the original row, verbatim

    -- normalized input
    first_name TEXT,
    last_name TEXT,
    full_name TEXT,
    org_name_raw TEXT,
    domain TEXT,                          -- resolved or supplied
    title_raw TEXT,
    email_raw TEXT,                       -- email already in the sheet, if any

    -- resolution against tracker
    matched_person_id TEXT,               -- existing people.id, if matched
    match_method TEXT,                    -- 'email' | 'name_org' | 'name_fuzzy' | null
    match_confidence REAL,
    resolved_organization_id TEXT,        -- tracker organizations.id
    org_resolution_method TEXT,           -- 'domain' | 'name_exact' | 'name_fuzzy' | 'proposed_new' | null

    -- Hunter results
    hunter_status TEXT,                   -- 'pending' | 'found' | 'not_found' | 'error' | 'skipped'
    hunter_email TEXT,
    hunter_score INTEGER,                 -- Email Finder confidence, 0-100
    hunter_verification TEXT,             -- 'deliverable' | 'risky' | 'undeliverable' | 'unknown'
    hunter_position TEXT,
    hunter_linkedin_url TEXT,
    hunter_twitter TEXT,
    hunter_seniority TEXT,
    hunter_department TEXT,
    hunter_sources_count INTEGER,
    hunter_raw TEXT,                      -- full JSON response, for audit
    from_cache INTEGER DEFAULT 0,
    credits_used INTEGER DEFAULT 0,
    error_detail TEXT,

    -- review
    review_status TEXT NOT NULL DEFAULT 'pending',
    -- pending | auto_accepted | accepted | rejected | edited | committed | skipped
    proposed_data TEXT,                   -- JSON: the exact person payload to write
    edited_data TEXT,                     -- JSON: operator overrides
    write_action TEXT,                    -- 'create' | 'update' | 'none'
    reviewed_by TEXT,
    reviewed_at TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS enrichment_cache (
    id TEXT PRIMARY KEY,
    lookup_key TEXT NOT NULL UNIQUE,      -- sha256('finder:first:last:domain') etc.
    endpoint TEXT NOT NULL,               -- 'email_finder' | 'combined_enrichment'
    response_json TEXT NOT NULL,
    hit_count INTEGER DEFAULT 0,
    fetched_at TEXT DEFAULT (datetime('now')),
    expires_at TEXT                       -- TTL from policy; null = no expiry
);

CREATE TABLE IF NOT EXISTS enrichment_writebacks (
    id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL REFERENCES enrichment_jobs(id),
    row_id TEXT NOT NULL REFERENCES enrichment_rows(id),
    target_table TEXT NOT NULL,           -- 'people' | 'organizations'
    target_record_id TEXT NOT NULL,
    write_type TEXT NOT NULL,             -- 'create' | 'update'
    written_data TEXT NOT NULL,
    previous_data TEXT,                   -- for undo
    auto_committed INTEGER DEFAULT 0,
    reversed INTEGER DEFAULT 0,
    reversed_at TEXT,
    written_at TEXT DEFAULT (datetime('now'))
);
```

Indexes: `enrichment_rows(job_id)`, `enrichment_rows(job_id, review_status)`,
`enrichment_rows(job_id, hunter_status)`, `enrichment_rows(matched_person_id)`,
`enrichment_cache(lookup_key)` unique, `enrichment_cache(expires_at)`,
`enrichment_writebacks(job_id)`, `enrichment_writebacks(target_table, target_record_id)`,
`enrichment_writebacks(reversed)`.

### Tracker-side change

One migration in `services/tracker/app/schema.py`, appended as version 12:

```python
(
    12,
    "people_enrichment_fields",
    [
        "ALTER TABLE people ADD COLUMN linkedin_url TEXT",
        "ALTER TABLE people ADD COLUMN email_verification_status TEXT",
        "ALTER TABLE people ADD COLUMN email_verified_at TEXT",
        "ALTER TABLE people ADD COLUMN email_confidence INTEGER",
        "CREATE INDEX IF NOT EXISTS idx_people_email_verified ON people(email_verification_status)",
    ],
),
```

Rationale for real columns over `external_refs`: the AI writeback layer already
owns `external_refs` for its own provenance keys
(`services/ai/app/writeback/item_converters.py:40`), so overloading it invites key
collisions. These four fields also need to be displayable and filterable —
`PersonDrawer` should render a clickable LinkedIn link, and "show me contacts with
unverified emails" should be a query, not a JSON scan.

`CreatePerson` / `UpdatePerson` / `UpdatePersonProfile` in
`services/tracker/app/validators.py` gain the matching optional fields.

### Organization domains

Email Finder needs a domain. The tracker has organization names, not domains. Add
to the same migration:

```sql
ALTER TABLE organizations ADD COLUMN primary_domain TEXT;
CREATE INDEX IF NOT EXISTS idx_orgs_domain ON organizations(primary_domain);
```

Domain resolution order per row, first hit wins:

1. Explicit domain column in the sheet.
2. Domain parsed from an email already in the sheet.
3. `organizations.primary_domain` where the org name matches.
4. Hunter Domain Search by company name — **costs credits**, so gated behind a
   policy flag, default off.
5. Unresolved: row is marked `skipped`, surfaced in review as "needs a domain".
   The operator can supply one inline and requeue the row.

When a row resolves a domain for an org that had none, the job proposes writing
`primary_domain` back to that organization — so the second import is cheaper than
the first.

---

## Pipeline

Mirrors `pipeline/orchestrator.py` in shape: explicit status transitions on the job
row, SSE progress events, resumable.

**Stage 1 — Upload** (`status: uploaded`)
Store under `AI_UPLOAD_DIR/enrichment/{job_id}/`. Compute `file_sha256`; warn if a
prior job used the same file. Parse with `openpyxl` for `.xlsx` and the stdlib `csv`
module for `.csv`. Note the AI service has no shared upload-size config — it uses a
module-level `MAX_UPLOAD_BYTES` in `routers/communications.py:36`. Define a separate,
much smaller `MAX_ENRICHMENT_UPLOAD_BYTES` (a contact sheet is kilobytes, not the
200MB an audio file gets). Row cap from policy (default 5,000) to stop a runaway job.

**Stage 2 — Column mapping** (`status: mapping`)
For `linkedin_export`, apply the preset and jump to Stage 3. For generic sheets,
propose a mapping from headers to canonical fields (`first_name`, `last_name`,
`full_name`, `org_name`, `domain`, `title`, `email`) by header-name heuristics.
The existing `ANTHROPIC_API_KEY` / `llm/client.py` can propose mappings for
ambiguous headers cheaply via Haiku — a nice fit, but the heuristic path must work
without it. **The operator always confirms the mapping.** Nothing is sent to Hunter
before this step completes.

**Stage 3 — Normalize and resolve** (`status: ready`)
No network calls. Per row: split or join names, normalize the org name, resolve the
domain (order above), and match against the tracker via `/tracker/ai-context` or
`/tracker/people`:

1. Exact email match (case-insensitive) → confidence 1.0.
2. `full_name` + `organization_id` exact → 0.9.
3. Fuzzy name within the same org (normalized Levenshtein above policy threshold)
   → 0.6 to 0.85.
4. No match → this row proposes a new person.

Then present the pre-flight: rows to process, rows already complete (existing
person already has a verified email — skip, cost zero), cache hits, estimated
credits, and current Hunter balance from `/v2/account`. `/v2/email-count` is free
and gives a per-domain sanity check. **Nothing has been spent yet.** The operator
sets `credit_cap` and acknowledges the third-party egress to proceed.

**Stage 4 — Hunter fan-out** (`status: running`)
A bounded worker pool (policy `max_concurrency`, default 5) over pending rows.
Per row: Email Finder, then Combined Enrichment if `enrich_profile` is on and an
email was found. Update the row, increment `credits_spent`, publish an SSE progress
event. Pause the job when `credits_spent` reaches `credit_cap`; the operator can
raise the cap and resume. Crash-safe by construction — progress lives in
`enrichment_rows`, so a restart resumes at the first `hunter_status = 'pending'`
row.

**Stage 5 — Propose** (`status: awaiting_review`)
Build `proposed_data` per row: the exact `people` payload that would be written,
with `source = 'hunter'`, `source_id = {job_id}:{row_number}`, `email_confidence`,
`email_verification_status`, `email_verified_at`, and `linkedin_url`. Set
`write_action` to `create` or `update`. Apply the auto-accept rule (below) to set
`review_status` to `auto_accepted` or `pending`.

**Stage 6 — Review and commit** (`status: committing` → `complete`)
Operator accepts, edits, or rejects. Commit reuses
`services/ai/app/writeback/tracker_client.py`, which already POSTs to
`/tracker/batch` with retry, connection pooling, and idempotency keys — the tracker
side honours them via `app/idempotency.py`. Each write is recorded in
`enrichment_writebacks` with `previous_data` for undo, mirroring how
`writeback/undo.py` works today.

---

## Auto-accept rule

A row is pre-checked for one-click bulk accept only when **all** hold:

- `hunter_score >= auto_accept_score` (policy, default 90)
- `hunter_verification` is not `undeliverable` or `risky`
- `write_action = 'create'`, **or** it is an update that only fills fields that were
  previously empty
- no conflict: the row does not propose overwriting a non-empty email with a
  different one
- `match_confidence` is either 1.0 or below the fuzzy floor — an *ambiguous* match
  always needs a human

Anything else is `pending`. Overwriting an existing non-empty email is **never**
auto-accepted regardless of score. `auto_accept_score` lives in `ai_policy.json`
and is editable from `AISettingsPage.jsx`, matching how `trust_config` thresholds
already work.

---

## Hunter client

New `services/ai/app/enrichment/hunter_client.py`. `httpx.AsyncClient`, matching
the style of `_fetch_tracker_context` in `pipeline/stages/enrichment.py`.

| Endpoint | Purpose | Cost |
|---|---|---|
| `GET /v2/email-finder` | name + domain to email | 1 credit |
| `GET /v2/combined/find` | email to LinkedIn, title, seniority, company | 1 credit |
| `GET /v2/account` | remaining credits, pre-flight guard | free |
| `GET /v2/email-count` | per-domain estimate | free |
| `GET /v2/email-verifier` | grade an existing email | 1 credit (phase 2) |

Requirements:

- **Rate limiting.** Token bucket, policy `requests_per_second` default 8 (Hunter
  allows roughly 15/s on paid plans; leave headroom).
- **Retries.** Exponential backoff on 429 and 5xx, honouring `Retry-After`, max 4
  attempts. A 4xx other than 429 is terminal for that row — record it, move on, do
  not fail the job.
- **Credit guard.** Refuse to start if `/v2/account` reports fewer credits than the
  estimate. Hard-stop at `credit_cap` mid-run.
- **Caching.** Check `enrichment_cache` before every call. A cache hit costs zero
  credits and sets `from_cache = 1`. TTL from policy, default 90 days.
- **Never log the API key.** `HUNTER_API_KEY` is redacted in logs and never returned
  by any endpoint. Add to `.env.example` and to the config-presence check in
  `services/ai/app/config.py`.
- **A 'not found' is a real answer.** Record `hunter_status = 'not_found'`, spend the
  credit, do not retry.

---

## New dependency

`services/ai/requirements.txt` gains `openpyxl>=3.1` for `.xlsx` parsing. It is not
currently a dependency of this service (only `services/intake` pulls in `pandas`,
and pandas is far heavier than this needs). CSV uses the stdlib.

## Config

New `ai_policy.json` section, hot-reloadable through `config_api.py` like the rest:

```json
{
  "enrichment_policy": {
    "enabled": true,
    "auto_accept_score": 90,
    "reject_below_score": 50,
    "allow_risky_emails": false,
    "enrich_profile_default": false,
    "max_concurrency": 5,
    "requests_per_second": 8,
    "max_rows_per_job": 5000,
    "default_credit_cap": 500,
    "cache_ttl_days": 90,
    "fuzzy_name_threshold": 0.85,
    "allow_domain_search_fallback": false,
    "propose_org_domain_writeback": true,
    "require_egress_acknowledgement": true
  }
}
```

`HUNTER_API_KEY` goes in `.env` / `.env.example` only — never in `ai_policy.json`,
which is readable through the config API.

---

## API surface

New `services/ai/app/routers/contact_enrichment.py`, registered in `main.py` under
`api_prefix` with `_ai_auth_dep` like every other router.

```
POST   /ai/enrichment/jobs                  upload file, create job
GET    /ai/enrichment/jobs                  list jobs (paginated)
GET    /ai/enrichment/jobs/{id}             job detail + counts
GET    /ai/enrichment/jobs/{id}/preview     parsed headers + first 10 rows
PUT    /ai/enrichment/jobs/{id}/mapping     confirm column mapping
GET    /ai/enrichment/jobs/{id}/preflight   credits, cache hits, skips, balance
POST   /ai/enrichment/jobs/{id}/start       acknowledge egress, set cap, run
POST   /ai/enrichment/jobs/{id}/pause
POST   /ai/enrichment/jobs/{id}/resume
POST   /ai/enrichment/jobs/{id}/cancel
GET    /ai/enrichment/jobs/{id}/rows        filter by review_status / hunter_status
PATCH  /ai/enrichment/rows/{row_id}         accept | reject | edit | set domain
POST   /ai/enrichment/jobs/{id}/bulk-accept accept all auto_accepted rows
POST   /ai/enrichment/jobs/{id}/commit      write accepted rows to tracker
POST   /ai/enrichment/jobs/{id}/undo        reverse writebacks
GET    /ai/enrichment/jobs/{id}/export      filled sheet (.csv / .xlsx)
GET    /ai/enrichment/account               Hunter credit balance
```

SSE progress reuses the existing bus in `routers/events.py` via `publish_event`,
with event names `enrichment_progress`, `enrichment_complete`, `enrichment_paused`,
`enrichment_error`. `useAIEvents.js` picks these up with no change to the
transport.

---

## Frontend

All inline styles with `styles/theme.js` tokens, shared styles from
`styles/pageStyles.js`, dates through `utils/dateUtils.js`. Literal ASCII in JSX
text, per `CLAUDE.md`.

- `pages/enrichment/ContactEnrichmentPage.jsx` — job list, upload entry point.
- `components/enrichment/UploadContactsModal.jsx` — modeled on
  `UploadAudioModal.jsx`. File picker, source-type selector (generic vs LinkedIn
  export), `enrich_profile` toggle.
- `components/enrichment/ColumnMappingStep.jsx` — proposed mapping with dropdowns
  per canonical field, plus a 10-row preview of the mapped result.
- `components/enrichment/PreflightPanel.jsx` — rows to process, cache hits, skips,
  estimated credits, current balance, credit cap input, egress acknowledgement
  checkbox. The Start button stays disabled until acknowledged.
- `pages/enrichment/EnrichmentReviewPage.jsx` — the review queue. `DataTable` with
  original row on the left, Hunter proposal on the right,
  `ConfidenceIndicator` for the score, inline email edit, accept/reject per row,
  filter tabs for auto-accepted / needs review / not found / needs domain. Reuses
  `PersonOrgResolver` for the org column.
- `api/ai.js` — the client functions.
- `Sidebar.jsx` — add under the Operations separator, near `/people`:
  `{ path: "/enrichment", label: "Contact Enrichment", icon: "⊕" }`.

---

## Export

`GET /ai/enrichment/jobs/{id}/export` returns the **original sheet, column order
preserved**, with appended columns: `hunter_email`, `hunter_score`,
`hunter_verification`, `hunter_linkedin_url`, `hunter_position`, `review_status`,
`tracker_person_id`. Every input row appears, including not-found ones — an export
that silently drops rows is worse than useless for reconciliation. `.csv` by
default, `.xlsx` when the upload was `.xlsx`.

---

## Data egress and compliance

This feature sends personal data about identifiable third parties — including Hill
staff, partner-agency personnel, and outside parties — to a commercial US SaaS.
That is a policy decision, not only an engineering one, so the design makes it
explicit rather than incidental:

- **Opt-in per job.** `require_egress_acknowledgement` defaults true; the job
  cannot start until `egress_acknowledged_at` is set.
- **Minimal payload.** Only first name, last name, and domain go to Hunter. Never
  matter associations, `substantive_areas`, `relationship_category`, meeting
  history, or any tracker identifier.
- **Auditable.** `enrichment_rows.hunter_raw` plus the derived fields record what
  was asked and what came back, per row, permanently. `credits_spent` per job gives
  the spend trail.
- **Sensitivity check.** If a row matches an existing person whose organization or
  relationship_category is flagged sensitive, hold the row for explicit per-row
  confirmation rather than including it in a bulk run. Wiring detail to settle
  against the existing `sensitivity_policy` section.
- **Retention.** Uploaded files stay under `AI_UPLOAD_DIR`; a policy TTL for
  purging raw uploads after commit is worth adding in phase 2.

Worth a human decision before build: whether a Hunter data-processing agreement is
needed, and whether any contacts are EU residents (GDPR legitimate-interest
assessment). Flagging, not resolving — that is the operator's call.

---

## Failure modes

| Failure | Behaviour |
|---|---|
| Hunter 401 / bad key | Job fails fast at pre-flight, before any spend. Clear error. |
| Hunter 429 | Backoff and retry, honour `Retry-After`. Job continues. |
| Credits exhausted mid-run | Job pauses at `paused`, partial results preserved, operator can top up and resume. |
| Service restart mid-run | Resume from first `pending` row. Credits already spent are not re-spent — cache covers repeats. |
| Tracker unreachable at commit | Commit fails atomically per row; `enrichment_writebacks` records only what landed. Re-runnable, idempotency keys prevent duplicate people. |
| Malformed sheet / no name column | Rejected at mapping with the specific reason. No credits spent. |
| Duplicate upload of same file | Warn on `file_sha256` match, let the operator proceed. Cache makes the re-run nearly free. |
| Two rows resolve to the same existing person | Both flagged as conflicts, neither auto-accepted. |
| Wrong email committed | `POST /undo` reverses via `previous_data`. |

---

## Testing

Following the repo's pytest layout under `services/ai/tests/`:

- `test_enrichment_parsing.py` — CSV and XLSX parsing, LinkedIn preset, header
  heuristics, malformed input, row cap.
- `test_enrichment_matching.py` — the four-tier person match, fuzzy threshold
  boundaries, domain resolution order, org proposals.
- `test_hunter_client.py` — mocked `httpx`; retry on 429 and 5xx, terminal 4xx,
  `Retry-After`, rate-limiter pacing, cache hit skips the call, key never logged.
- `test_enrichment_review.py` — auto-accept rule table, including the "never
  auto-overwrite a non-empty email" case and the ambiguous-match case.
- `test_enrichment_commit.py` — writeback payload shape, idempotency, undo,
  partial-failure handling.
- `test_enrichment_api.py` — endpoint contracts, auth, egress gate blocks start,
  credit cap enforced.

No test may make a real Hunter call. All mocked.

---

## Phasing

**Phase 1 — plumbing.** Schema (both services), Hunter client with rate limiting
and cache, upload, parsing, mapping, pre-flight. No review UI. Verifiable via
API plus the export endpoint.

**Phase 2 — review and commit.** Proposal builder, auto-accept rule, review queue
UI, commit, undo, sidebar entry.

**Phase 3 — polish.** LinkedIn export preset end to end, org `primary_domain`
writeback, Combined Enrichment toggle, SSE progress in the UI.

**Phase 4 — deferred.** Email Verifier hygiene sweep over existing `people`
records, scheduled re-verification of stale emails, Domain Search discovery mode.

Phase 1 and 2 are the minimum that delivers the stated goal.

---

## Open questions

1. **Hunter plan and credit budget?** Determines `requests_per_second` and whether
   `enrich_profile` is affordable by default.
2. **`relationship_category` for imported contacts** — leave null for the operator
   to set, default to a value, or infer from the organization?
3. **`is_active` default for created people** — 1 seems right, but a spreadsheet of
   conference attendees is not the same commitment as a hand-entered contact.
4. **Should a not-found row still create the person record** (name + org, no email)?
   Argument for: the tracker learns the person exists. Against: it fills `people`
   with unreachable stubs.
5. **Sensitivity hold** — which exact `organizations` or `relationship_category`
   values should force per-row confirmation?

---

## Implementation note

`CLAUDE.md` requires `gitnexus_impact` before modifying any existing symbol. The
GitNexus MCP tools are not exposed in the session that wrote this spec, so impact
analysis on the touched existing symbols — `CreatePerson`, `UpdatePerson`,
`UpdatePersonProfile`, the `people` router write paths, `load_policy`, and
`Sidebar.jsx` — still needs to be run locally before any code lands, along with
`npx gitnexus analyze` to pick up the new module.
