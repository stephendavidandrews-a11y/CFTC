# Fix Plan

## Scope
Implement the highest-priority fixes from the 2026-03-29 audit in the live Mac mini repo. Do not spend time on portability-only deployment cleanup or low-traffic performance tuning unless those items become blockers for correctness.

## Phase 1 - Broken Review Flows
Goal: restore reviewer ability to add and edit review items without contract mismatches.

Tasks:
- Align bundle review validation with the frontend's current payload keys for `task_update`, `decision_update`, `context_note`, and `org_detail_update`.
- Remove stale `follow_up` item validation and ensure reviewer-created tasks continue to use `task_mode="follow_up"` instead.
- Align review-form enum options with current tracker contract values for new matters and documents.
- Verify bundle review create/edit endpoints succeed for the current item types.

Acceptance criteria:
- Reviewer-created `task_update`, `decision_update`, `context_note`, and `org_detail_update` payloads validate successfully.
- Bundle review add/edit flows no longer reject valid frontend payloads due to stale backend field names.
- Matter/document selects in the review UI only present values accepted by tracker contracts.

## Phase 2 - Schema and Contract Drift
Goal: make tracker, AI, and frontend agree on the current contract.

Tasks:
- Update extraction item vocabularies and ordering to remove legacy `follow_up` item handling.
- Align AI writeback converters with the canonical tracker matter/document contract.
- Refresh stale frontend schema/theme references that still encode pre-redesign tracker matter statuses.
- Check batch and cross-service assumptions touched by these fixes.

Acceptance criteria:
- AI extraction, review, and writeback code share the same supported item-type set.
- No active code path still depends on standalone `follow_up` items.
- Frontend contract artifacts used by the app reflect the current tracker enums.

## Phase 3 - Error Handling and Security Hardening
Goal: improve visible failure behavior and close the most meaningful low-effort security gaps.

Tasks:
- Make `useApi` preserve promise failures so callers can surface errors consistently.
- Add visible error handling for the audited silent-failure secondary loads.
- Review public health endpoints and spoofable write-source handling; tighten where low-risk and low-disruption.
- Validate AI/tracker behavior for the touched paths after hardening.

Acceptance criteria:
- Frontend callers can reliably catch `useApi` failures.
- The previously silent audited pages surface secondary-load failures.
- Public/internal endpoint exposure and write-source behavior match deliberate policy, not accidental defaults.

## Deferred Unless Requested
- Mac-specific script path parameterization.
- Bespoke deployment artifact standardization.
- Meeting-detail N+1 fetch cleanup.
- Review picker prefetch reduction.
- Frontend lazy-loading and bundle-size tuning.
