"""The auto-accept rule and proposal building.

This is the safety-critical table. The absolute rule under test: an existing
non-empty email is never auto-overwritten, at any confidence score.
"""

import json

import pytest
from app.enrichment.proposals import (
    REVIEW_AUTO_ACCEPTED,
    REVIEW_PENDING,
    REVIEW_SKIPPED,
    WRITE_CREATE,
    WRITE_NONE,
    WRITE_UPDATE,
    build_proposal,
    decide_review_status,
    is_email_overwrite,
    only_fills_empty_fields,
    to_batch_operations,
)

NOW = "2026-09-27T12:00:00"
JOB = {"id": "job1"}

POLICY = {
    "enrichment_policy": {
        "auto_accept_score": 90,
        "reject_below_score": 50,
        "allow_risky_emails": False,
    }
}


def _row(**kw):
    base = {
        "id": "r1",
        "row_number": 1,
        "full_name": "Jane Doe",
        "first_name": "Jane",
        "last_name": "Doe",
        "hunter_status": "found",
        "hunter_email": "jane.doe@cftc.gov",
        "hunter_score": 95,
        "hunter_verification": "deliverable",
        "hunter_position": None,
        "hunter_linkedin_url": None,
        "resolved_organization_id": None,
        "match_ambiguous": False,
    }
    base.update(kw)
    return base


# ---------------------------------------------------------------------------
# Proposal building
# ---------------------------------------------------------------------------


def test_new_contact_proposal_is_a_create():
    payload, action = build_proposal(_row(), None, JOB, NOW)
    assert action == WRITE_CREATE
    assert payload["full_name"] == "Jane Doe"
    assert payload["email"] == "jane.doe@cftc.gov"
    assert payload["email_confidence"] == 95
    assert payload["email_verification_status"] == "deliverable"
    assert payload["email_verified_at"] == NOW
    assert payload["source"] == "hunter"
    assert payload["source_id"] == "job1:1"


def test_create_includes_linkedin_and_title_when_present():
    row = _row(hunter_position="Senior Counsel",
               hunter_linkedin_url="https://www.linkedin.com/in/janedoe")
    payload, _ = build_proposal(row, None, JOB, NOW)
    assert payload["title"] == "Senior Counsel"
    assert payload["linkedin_url"] == "https://www.linkedin.com/in/janedoe"


def test_update_only_contains_changed_fields():
    person = {"id": "p1", "email": "", "title": "Counsel", "linkedin_url": ""}
    row = _row(hunter_position="Senior Counsel")
    payload, action = build_proposal(row, person, JOB, NOW)
    assert action == WRITE_UPDATE
    assert payload["email"] == "jane.doe@cftc.gov"
    # title is already set on the person, so it is left alone
    assert "title" not in payload


def test_identical_email_records_verification_only():
    person = {
        "id": "p1",
        "email": "jane.doe@cftc.gov",
        "email_verification_status": None,
    }
    payload, action = build_proposal(_row(), person, JOB, NOW)
    assert action == WRITE_UPDATE
    assert "email" not in payload, "same address must not be rewritten"
    assert payload["email_verification_status"] == "deliverable"


def test_nothing_to_change_is_write_none():
    person = {
        "id": "p1",
        "email": "jane.doe@cftc.gov",
        "email_verification_status": "deliverable",
        "title": "Counsel",
        "linkedin_url": "x",
        "organization_id": "o1",
    }
    payload, action = build_proposal(_row(), person, JOB, NOW)
    assert action == WRITE_NONE
    assert payload == {}


def test_org_is_only_filled_when_person_has_none():
    person = {"id": "p1", "email": "", "organization_id": "existing-org"}
    row = _row(resolved_organization_id="new-org")
    payload, _ = build_proposal(row, person, JOB, NOW)
    assert "organization_id" not in payload


# ---------------------------------------------------------------------------
# The absolute rule
# ---------------------------------------------------------------------------


def test_email_overwrite_is_detected():
    person = {"email": "old.address@cftc.gov"}
    assert is_email_overwrite({"email": "new@cftc.gov"}, person) is True


def test_same_email_is_not_an_overwrite():
    person = {"email": "Jane.Doe@CFTC.gov"}
    assert is_email_overwrite({"email": "jane.doe@cftc.gov"}, person) is False


def test_filling_an_empty_email_is_not_an_overwrite():
    assert is_email_overwrite({"email": "new@cftc.gov"}, {"email": ""}) is False


@pytest.mark.parametrize("score", [90, 95, 99, 100])
def test_overwriting_an_existing_email_never_auto_accepts(score):
    """No score is high enough to silently replace a curated address."""
    person = {"id": "p1", "email": "curated@cftc.gov"}
    row = _row(hunter_score=score, hunter_email="different@cftc.gov")
    proposed, action = build_proposal(row, person, JOB, NOW)
    status, reason = decide_review_status(row, proposed, action, person, POLICY)
    assert status == REVIEW_PENDING
    assert reason == "would_overwrite_existing_email"


# ---------------------------------------------------------------------------
# Auto-accept rule table
# ---------------------------------------------------------------------------


def test_high_score_new_contact_auto_accepts():
    row = _row(hunter_score=95, hunter_verification="deliverable")
    proposed, action = build_proposal(row, None, JOB, NOW)
    status, reason = decide_review_status(row, proposed, action, None, POLICY)
    assert status == REVIEW_AUTO_ACCEPTED
    assert reason == "meets_auto_accept_criteria"


def test_score_exactly_at_threshold_auto_accepts():
    row = _row(hunter_score=90)
    proposed, action = build_proposal(row, None, JOB, NOW)
    assert decide_review_status(row, proposed, action, None, POLICY)[0] == (
        REVIEW_AUTO_ACCEPTED
    )


def test_score_one_below_threshold_needs_review():
    row = _row(hunter_score=89)
    proposed, action = build_proposal(row, None, JOB, NOW)
    status, reason = decide_review_status(row, proposed, action, None, POLICY)
    assert status == REVIEW_PENDING
    assert reason == "below_auto_accept_threshold"


def test_very_low_score_is_flagged_below_reject_threshold():
    row = _row(hunter_score=20)
    proposed, action = build_proposal(row, None, JOB, NOW)
    assert decide_review_status(row, proposed, action, None, POLICY)[1] == (
        "below_reject_threshold"
    )


def test_missing_score_needs_review():
    row = _row(hunter_score=None)
    proposed, action = build_proposal(row, None, JOB, NOW)
    assert decide_review_status(row, proposed, action, None, POLICY)[1] == "no_score"


@pytest.mark.parametrize("verdict", ["undeliverable", "risky", "unknown"])
def test_bad_verification_never_auto_accepts(verdict):
    row = _row(hunter_score=99, hunter_verification=verdict)
    proposed, action = build_proposal(row, None, JOB, NOW)
    assert decide_review_status(row, proposed, action, None, POLICY)[0] == REVIEW_PENDING


def test_risky_can_be_allowed_by_policy():
    policy = {
        "enrichment_policy": {
            "auto_accept_score": 90,
            "reject_below_score": 50,
            "allow_risky_emails": True,
        }
    }
    row = _row(hunter_score=95, hunter_verification="risky")
    proposed, action = build_proposal(row, None, JOB, NOW)
    assert decide_review_status(row, proposed, action, None, policy)[0] == (
        REVIEW_AUTO_ACCEPTED
    )


def test_undeliverable_is_never_allowed_even_with_risky_enabled():
    """allow_risky_emails must not open the door to known-bad addresses."""
    policy = {
        "enrichment_policy": {
            "auto_accept_score": 90,
            "reject_below_score": 50,
            "allow_risky_emails": True,
        }
    }
    row = _row(hunter_score=99, hunter_verification="undeliverable")
    proposed, action = build_proposal(row, None, JOB, NOW)
    status, reason = decide_review_status(row, proposed, action, None, policy)
    assert status == REVIEW_PENDING
    assert reason == "undeliverable"


def test_ambiguous_person_match_never_auto_accepts():
    row = _row(hunter_score=99, match_ambiguous=True)
    proposed, action = build_proposal(row, None, JOB, NOW)
    status, reason = decide_review_status(row, proposed, action, None, POLICY)
    assert status == REVIEW_PENDING
    assert reason == "ambiguous_person_match"


def test_not_found_row_goes_to_review_not_auto_accept():
    row = _row(hunter_status="not_found", hunter_email=None, hunter_score=None)
    proposed, action = build_proposal(row, None, JOB, NOW)
    status, reason = decide_review_status(row, proposed, action, None, POLICY)
    assert status == REVIEW_PENDING
    assert reason == "not_found"


def test_error_row_goes_to_review():
    row = _row(hunter_status="error", hunter_email=None, hunter_score=None)
    proposed, action = build_proposal(row, None, JOB, NOW)
    assert decide_review_status(row, proposed, action, None, POLICY)[1] == "lookup_error"


def test_nothing_to_write_is_skipped():
    row = _row()
    status, reason = decide_review_status(row, {}, WRITE_NONE, None, POLICY)
    assert status == REVIEW_SKIPPED
    assert reason == "nothing_to_write"


def test_update_that_changes_an_existing_value_needs_review():
    """Only empty-field fills may auto-accept on an existing person."""
    person = {"id": "p1", "email": "", "title": "Old Title"}
    row = _row(hunter_score=99, hunter_position="New Title")
    # Force a payload that would change the existing title.
    proposed = {"email": "jane.doe@cftc.gov", "title": "New Title"}
    status, reason = decide_review_status(row, proposed, WRITE_UPDATE, person, POLICY)
    assert status == REVIEW_PENDING
    assert reason == "would_change_existing_values"


def test_update_filling_only_empty_fields_auto_accepts():
    person = {"id": "p1", "email": "", "title": "", "linkedin_url": ""}
    row = _row(hunter_score=95)
    proposed, action = build_proposal(row, person, JOB, NOW)
    assert action == WRITE_UPDATE
    assert decide_review_status(row, proposed, action, person, POLICY)[0] == (
        REVIEW_AUTO_ACCEPTED
    )


def test_only_fills_empty_ignores_email_metadata():
    person = {"email": "", "email_verification_status": "risky"}
    proposed = {"email": "a@b.gov", "email_verification_status": "deliverable"}
    assert only_fills_empty_fields(proposed, person) is True


def test_only_fills_empty_false_for_populated_field():
    assert only_fills_empty_fields({"title": "X"}, {"title": "Y"}) is False


def test_new_person_always_counts_as_filling_empty():
    assert only_fills_empty_fields({"email": "a@b.gov"}, None) is True


# ---------------------------------------------------------------------------
# Batch operations
# ---------------------------------------------------------------------------


def test_create_row_produces_insert_operation():
    rows = [
        {
            "id": "r1",
            "row_number": 1,
            "write_action": WRITE_CREATE,
            "proposed_data": json.dumps({"full_name": "Jane Doe", "email": "j@x.gov"}),
        }
    ]
    ops, plan = to_batch_operations(rows, {}, JOB)
    assert len(ops) == 1
    assert ops[0]["table"] == "people"
    assert ops[0]["op"] == "insert"
    assert ops[0]["data"]["email"] == "j@x.gov"
    assert plan[0]["row_id"] == "r1"
    assert plan[0]["write_type"] == "create"


def test_update_row_produces_update_operation_with_record_id():
    rows = [
        {
            "id": "r2",
            "row_number": 2,
            "write_action": WRITE_UPDATE,
            "matched_person_id": "p1",
            "proposed_data": json.dumps({"email": "j@x.gov"}),
        }
    ]
    ops, plan = to_batch_operations(rows, {}, JOB)
    assert ops[0]["op"] == "update"
    assert ops[0]["record_id"] == "p1"
    assert plan[0]["record_id"] == "p1"


def test_operator_edits_override_the_generated_proposal():
    rows = [
        {
            "id": "r3",
            "row_number": 3,
            "write_action": WRITE_CREATE,
            "proposed_data": json.dumps({"email": "generated@x.gov"}),
            "edited_data": json.dumps({"email": "corrected@x.gov"}),
        }
    ]
    ops, _ = to_batch_operations(rows, {}, JOB)
    assert ops[0]["data"]["email"] == "corrected@x.gov"


def test_rows_with_empty_payload_produce_no_operation():
    rows = [{"id": "r4", "row_number": 4, "write_action": WRITE_CREATE,
             "proposed_data": None}]
    ops, plan = to_batch_operations(rows, {}, JOB)
    assert ops == []
    assert plan == []


def test_update_without_matched_person_is_skipped():
    rows = [{"id": "r5", "row_number": 5, "write_action": WRITE_UPDATE,
             "matched_person_id": None,
             "proposed_data": json.dumps({"email": "x@y.gov"})}]
    ops, _ = to_batch_operations(rows, {}, JOB)
    assert ops == []


def test_org_domain_writeback_is_appended_when_enabled():
    rows = [{"id": "r6", "row_number": 6, "write_action": WRITE_CREATE,
             "proposed_data": json.dumps({"full_name": "A B"})}]
    ops, plan = to_batch_operations(
        rows, {}, JOB, propose_org_domains=True,
        org_domain_updates={"o1": "cftc.gov"},
    )
    assert len(ops) == 2
    org_op = ops[-1]
    assert org_op["table"] == "organizations"
    assert org_op["data"]["primary_domain"] == "cftc.gov"
    assert plan[-1]["row_id"] is None


def test_org_domain_writeback_suppressed_when_disabled():
    rows = []
    ops, _ = to_batch_operations(
        rows, {}, JOB, propose_org_domains=False,
        org_domain_updates={"o1": "cftc.gov"},
    )
    assert ops == []


def test_corrupt_proposed_data_does_not_raise():
    rows = [{"id": "r7", "row_number": 7, "write_action": WRITE_CREATE,
             "proposed_data": "{not json"}]
    ops, _ = to_batch_operations(rows, {}, JOB)
    assert ops == []
