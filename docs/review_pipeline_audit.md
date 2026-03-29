# Review Pipeline End-to-End Audit Report

**Date**: 2026-03-30
**Scope**: Bundle review, entity review, speaker review, participant review, writeback, undo, commit queue, frontend
**Test baseline**: 100/102 passing (2 pre-existing fixture failures in test_writeback.py)

---

## Summary

| Classification | Count | Critical | High | Medium | Low |
|----------------|-------|----------|------|--------|-----|
| Bug            | 7     | 1        | 3    | 3      | 0   |
| Risk           | 9     | 0        | 3    | 5      | 1   |
| Gap            | 4     | 0        | 0    | 4      | 0   |
| Cleanup        | 6     | 0        | 0    | 2      | 4   |
| **Total**      | **26**| **1**    | **6**| **14** | **5**|

---

## 1. BUNDLE REVIEW BACKEND

### BUG-1: Undo status mismatch (Critical)

**File**: `app/writeback/undo.py` line 545, `app/routers/communications.py` line 665
**Finding**: After successful undo, the DB is set to `processing_status = "reviewed"` but the API response body claims `"new_status": "bundle_review_in_progress"`. The response lies to the frontend. The `reviewed` state means the pipeline will auto-advance to `committing` on next resume, re-committing everything. But the review UI requires `awaiting_bundle_review` or `bundle_review_in_progress` state, so the user cannot re-review items through the UI. Post-undo is a dead end.
**Fix**: Undo should set status to `bundle_review_in_progress` (allows re-review) and the response should match.

### BUG-2: Items can be added/moved into rejected bundles (High)

**File**: `app/bundle_review/item_actions.py`, `app/bundle_review/restructure.py`
**Finding**: `add_item`, `move_item`, and `merge_bundles` do not check if the target bundle is rejected. Creates orphaned items inside rejected bundles that are invisible to `compute_blockers` and the completion flow.
**Fix**: Add guard: if target bundle status is rejected, raise 400.

### BUG-3: edit_bundle has no CAS guard (High)

**File**: `app/bundle_review/bundle_actions.py`
**Finding**: Unlike `accept_bundle` and `reject_bundle` which use compare-and-set, `edit_bundle` uses just `WHERE id = ?`. Two concurrent edits silently last-write-wins.
**Fix**: Add CAS guard using `updated_at` from the read.

### BUG-4: accept_item on edited item downgrades status (Medium)

**File**: `app/bundle_review/item_actions.py`
**Finding**: Accepting an already-edited item changes status from `edited` to `accepted`, losing the semantic marker. `original_proposed_data` is preserved but status is misleading.
**Fix**: No-op if already edited (item is already implicitly accepted).

### BUG-5: validate_proposed_data missing for 6 item types (Medium)

**File**: `app/bundle_review/validation.py`
**Finding**: `task_update`, `decision_update`, `context_note`, `person_detail_update`, `org_detail_update`, `directive_update` have zero required-field validation.
**Fix**: Add required field checks per type.

### BUG-6: test_writeback.py 2 failures from fixture startup (Medium)

**File**: `services/ai/tests/test_writeback.py` tests 10_01, 10_03
**Finding**: Test app fixture reports `"starting"` status instead of `"ok"`, causing health check and queue tests to fail.
**Fix**: Set `_ready` flag in test fixture before running integration tests.

### BUG-7: CommitQueuePage SSE listener recreated every render (High)

**File**: `frontend/src/pages/review/CommitQueuePage.jsx`
**Finding**: `refetchAll` useCallback depends on `[ready, committed, failed]` which are new objects every render. SSE useEffect unsubscribes and resubscribes on every render cycle.
**Fix**: Extract refetch functions into refs or memoize useApi return values.

---

## 2. WRITEBACK AND UNDO

### RISK-1: Post-undo dead end (High)

After undo, status is `reviewed`. The bundle review UI requires `awaiting_bundle_review` or `bundle_review_in_progress`. The pipeline maps `reviewed` -> `committing`. No path back to review-editable states without manual DB manipulation. Same fix as BUG-1.

### RISK-2: No retry mechanism for undo HTTP calls (Medium)

Commit has 3 attempts with backoff. Undo has zero retries per individual GET/DELETE/PUT. A single timeout creates partial failure.

### RISK-3: Concurrent commit + undo not guarded (Medium)

No locking mechanism prevents pipeline retry from starting commit while undo is in progress.

### RISK-4: Skipped update reversals marked as reversed (Medium)

If an update writeback has null `previous_data`, undo marks it `reversed=1` and skips it. Tracker record keeps AI-written values permanently.

---

## 3. ENTITY / SPEAKER / PARTICIPANT REVIEW

### RISK-5: Transcript editing bypasses review state check (High)

PATCH transcript, find-similar, and apply-corrections endpoints do NOT call `_check_review_state`. Transcripts can be edited after review is complete, after commit, or during commit.

### RISK-6: No tracker_person_id existence validation (Medium)

All three review routers accept any string as `tracker_person_id`. No check that it exists in the tracker.

### RISK-7: Entity merge DELETE may leave orphans (Medium)

DELETE from `communication_entities` does not cascade to related tables.

### GAP-1: No unlink/reject for participant review (Medium)

Once confirmed, cannot undo. Cannot skip unknowns. Every participant MUST be assigned a `tracker_person_id`. User stuck if they make a mistake.

### GAP-2: Entity/participant queues show archived communications (Medium)

Speaker review queue filters `archived_at IS NULL`. Entity and participant queues do not.

---

## 4. FRONTEND

### GAP-3: rejectVoiceprintMatch imported but no UI (Medium)

Users cannot reject a voiceprint suggestion. Incorrect matches accumulate without correction.

### GAP-4: addMatterAssociation / addDirectiveAssociation no UI (Medium)

Users can only confirm/reject AI-proposed associations, not manually add new ones during entity review.

### RISK-8: Inconsistent SSE patterns across queue pages (Medium)

Speaker/Entity/Participant queues use `lastEvent` effect pattern (causes unnecessary re-renders). BundleReview uses `on()` callback pattern (correct).

### RISK-9: ParticipantReviewDetailPage weakest review page (Medium)

No SSE integration, no toast feedback on actions, raw `<select>` dropdown for person picker (unusable for large orgs). Should use `PersonOrgResolver` component like SpeakerReview.

### CLEANUP-1: Dead imports across review pages (Low)

5 functions imported but never called: `rejectVoiceprintMatch`, `editBundle`, `addMatterAssociation`, `rejectDirectiveAssociation`, `addDirectiveAssociation`.

### CLEANUP-2: Date timezone handling inconsistent (Low)

Some queue pages append "Z" to UTC timestamps, others do not. Can cause timezone-dependent display bugs.

### CLEANUP-3: window.prompt in SpeakerReviewDetailPage (Low)

Blocking browser dialog for poor voice quality reason. Breaks dark theme. Replace with Radix Dialog modal.

### CLEANUP-4: Speaker response shape inconsistency (Low)

`unlink-speaker` and `merge-speakers` return `{ok: true}`. All other endpoints return `{status: "ok"}`.

---

## 5. DATA INTEGRITY

### Duplicate blocker computation (Low Risk)

`validation.compute_blockers` (Python) vs `completion.complete_review` (SQL). Two independent implementations of the same logic that must stay in sync.

### Fragile reviewer-created detection (Medium Risk)

Detects via `rationale.startswith("Reviewer-created")` and `confidence is None`. Heuristic-based, not explicit. A future `source` column on both tables would be more reliable.

---

## 6. TEST COVERAGE (100/102 passing)

### Missing Test Scenarios

| Area | Missing Coverage |
|------|-----------------|
| Bundle review | Concurrent edits, add/move to rejected bundle, accept-edited downgrade |
| Writeback | Network failure during tracker HTTP, partial commit then undo |
| Undo | Timeout during reversal, compound partial conflicts |
| Entity review | Merge orphan cleanup, confirm-all + association interaction |
| Speaker review | Transcript edit outside review state, merge + voice sample cleanup |
| Participant review | Complete with no participants, skip/unlink (when implemented) |
| Frontend | No automated frontend tests exist |

---

## Recommended Fix Priority

### P0 (Fix immediately)
1. **BUG-1 + RISK-1**: Undo should transition to `bundle_review_in_progress`, not `reviewed`
2. **BUG-2**: Guard add/move/merge against rejected target bundles
3. **BUG-7**: Fix CommitQueuePage SSE listener churn

### P1 (Fix this sprint)
4. **RISK-5**: Add review state check to transcript editing endpoints
5. **BUG-3**: Add CAS guard to edit_bundle
6. **BUG-5**: Add validation for missing item types
7. **BUG-6**: Fix test_writeback.py fixture startup issue
8. **GAP-2**: Filter archived comms from entity/participant queues

### P2 (Fix when touching these files)
9. **BUG-4**: Guard accept_item on edited items
10. **RISK-2**: Add retry to undo HTTP calls
11. **GAP-1**: Add skip/unlink for participant review
12. **GAP-3/4**: Build UI for reject voiceprint and add associations
13. All CLEANUP items

### P3 (Backlog)
14. **RISK-3**: Concurrent commit/undo locking
15. **RISK-6**: Validate tracker_person_id existence
16. Fragile reviewer-created detection (add explicit `source` column)
