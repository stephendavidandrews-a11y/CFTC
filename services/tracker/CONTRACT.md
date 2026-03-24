# Tracker Contract Guide

This is the reference point for future changes to the tracker/AI contract.

There is not one literal "master router" file. Instead, use these two master files:

- `app/contracts.py`
  This is the master for the AI-facing contract.
  Change this first when you change enums, AI-writable tables, batch enum validation, soft-delete rules, upsert rules, or the contract version.
- `app/schema.py`
  This is the master for the physical SQLite schema.
  Change this when you add, remove, or rename actual tables or columns.

## What Each File Owns

- `app/contracts.py`
  Canonical enums, aliases, AI writable tables, batch enum-column map, soft-delete rules, upsert rules, schema contract version.
- `app/schema.py`
  Actual table definitions, columns, indexes, and migrations.
- `app/routers/lookups.py`
  Read-only exposure of canonical enums from `app/contracts.py`.
- `app/routers/schema_version.py`
  Runtime handshake for AI/frontend contract verification.
- `app/routers/batch.py`
  Enforcement of the contract at write time.
- `app/validators.py`
  Pydantic validation aligned to canonical enums.

## Future Change Rules

If you are changing enums or AI write behavior:

1. Edit `app/contracts.py` first.
2. Then update any converter or caller that emits those values.
3. Run contract tests.

If you are changing database tables or columns:

1. Edit `app/schema.py` first.
2. If the AI layer can read or write the new field, update `app/contracts.py`.
3. Run schema and contract tests.

Do not make ontology decisions directly in:

- `app/routers/lookups.py`
- `app/routers/batch.py`
- `app/validators.py`
- `app/routers/schema_version.py`

Those files should follow `app/contracts.py`, not invent their own contract.

## Checklist For Common Changes

### New enum value

1. Update `app/contracts.py`
2. Verify any AI writeback defaults use the canonical value
3. Run:
   - `cd services/tracker && .venv/bin/python -m pytest tests/test_validators.py tests/test_batch.py`
   - `cd services/ai && .venv/bin/python -m pytest tests/test_contract_phase1.py tests/test_v2_extraction_e2e.py`

### New AI-writable table

1. Add or update the table in `app/schema.py`
2. Add the table to `AI_WRITABLE_TABLES` in `app/contracts.py`
3. Add enum validation entries in `AI_WRITABLE_ENUM_COLUMNS` if needed
4. Add tests in `tests/test_batch.py`
5. Update AI writeback tests if the AI layer writes to it

### New upsert rule

1. Add the rule in `BATCH_UPSERT_RULES` in `app/contracts.py`
2. Add batch tests covering first write and repeat write

### New soft-delete rule

1. Add the rule in `BATCH_SOFT_DELETE_TABLES` in `app/contracts.py`
2. Add batch tests covering delete behavior

## Current Phase 1 Test Commands

Tracker:

```bash
cd services/tracker
.venv/bin/python -m pytest tests/test_validators.py tests/test_batch.py tests/test_comment_topics.py tests/test_policy_directives.py
```

AI:

```bash
cd services/ai
.venv/bin/python -m pytest tests/test_contract_phase1.py tests/test_extraction_routing.py tests/test_v2_extraction_e2e.py
```


## Table Categories

### AI-writable tables (batch API + dedicated routers)

These tables can be written by both the AI pipeline (via batch API) and human users (via CRUD routers):

`organizations`, `people`, `matters`, `tasks`, `meetings`, `meeting_participants`, `meeting_matters`, `documents`, `document_files`, `decisions`, `matter_people`, `matter_organizations`, `matter_updates`, `context_notes`, `context_note_links`, `person_profiles`, **`comment_topics`**, **`comment_questions`**

### Manual-only tables (dedicated routers only)

These tables are written only by human users through dedicated CRUD routers. They are NOT in `AI_WRITABLE_TABLES` and cannot be written via the batch API:

- **`policy_directives`** — External mandates (EOs, PWG reports, congressional mandates). CRUD via `app/routers/policy_directives.py`. Enum validation in the router via Pydantic validators, not via batch.
- **`directive_matters`** — Join table linking directives to matters. CRUD via `app/routers/directive_matters.py`. In `BATCH_DELETE_ALLOWED_TABLES` for cleanup only.

### Delete behavior

- **`comment_topics`**: Hard delete via CRUD router. Cascade-deletes all child `comment_questions`. In `BATCH_DELETE_ALLOWED_TABLES`.
- **`comment_questions`**: Hard delete. In `BATCH_DELETE_ALLOWED_TABLES`.
- **`policy_directives`**: Hard delete via CRUD router. Cascade-deletes all `directive_matters` links.
- **`directive_matters`**: Hard delete. In `BATCH_DELETE_ALLOWED_TABLES`.

## New Enum Groups (v1.2.0)

### Comment Topics enums
- `comment_topic_area` — Broad classification of a comment topic
- `comment_topic_position_status` — Position development lifecycle
- `comment_topic_source_document_type` — Type of FR action that originated the topic

### Policy Directive enums
- `directive_source_document_type` — Type of source document
- `directive_priority_tier` — Urgency classification
- `directive_responsible_entity` — Which agency is responsible
- `directive_ogc_role` — OGC's role in implementation
- `directive_implementation_status` — Implementation lifecycle
- `directive_matter_relationship_type` — How a matter relates to a directive

### Expanded existing enums (v1.2.0)
- `regulatory_stage` += `petition_received`, `interpretive_release`
- `matter_dependency_type` += `supersedes`, `joint_action`
- `comment_period_type` += `anprm`, `nprm`, `proposed_order`, `concept_release`, `final_rule_with_comment`, `pra_60_day`, `pra_30_day`
- `source` += `federal_register`

## Router File Map

| Router file | Tables | Pattern |
|---|---|---|
| `comment_topics.py` | `comment_topics`, `comment_questions` | Nested CRUD — topics scoped to matter, questions scoped to topic |
| `policy_directives.py` | `policy_directives` | Standard CRUD with rich filters |
| `directive_matters.py` | `directive_matters` | Join table link/unlink with reverse lookup |

## Practical Summary

If you only remember one thing:

- `app/contracts.py` is the master for the tracker/AI contract.
- `app/schema.py` is the master for the actual database shape.
