"""Tests for Pydantic validators - field constraints, defaults, and canonical enums."""

import pytest
from pydantic import ValidationError

from app.contracts import ENUMS
from app.validators import (
    CreateContextNote,
    CreateContextNoteLink,
    CreateDecision,
    CreateDocument,
    CreateMatter,
    CreateMeeting,
    CreatePerson,
    CreateTask,
    UpdateDecision,
    UpdateDocument,
    UpdateMatter,
    UpdateTask,
)


def test_create_person_requires_full_name():
    with pytest.raises(ValidationError):
        CreatePerson()


def test_create_person_min_length():
    with pytest.raises(ValidationError):
        CreatePerson(full_name="")


def test_create_person_defaults():
    person = CreatePerson(full_name="Alice")
    assert person.is_active == 1
    assert person.source == "manual"
    assert person.include_in_team_workload == 0


def test_create_person_include_in_team_alias():
    person = CreatePerson(full_name="Bob", include_in_team=True)
    assert person.include_in_team_workload == 1


def test_create_meeting_requires_title_and_start():
    with pytest.raises(ValidationError):
        CreateMeeting()

    with pytest.raises(ValidationError):
        CreateMeeting(title="Meeting only")


def test_create_meeting_defaults():
    meeting = CreateMeeting(title="Standup", date_time_start="2026-04-01T09:00:00")
    assert meeting.boss_attends == 0
    assert meeting.external_parties_attend == 0
    assert meeting.participants == []
    assert meeting.matter_ids == []
    assert meeting.source == "manual"


def test_create_meeting_rejects_noncanonical_type():
    with pytest.raises(ValidationError):
        CreateMeeting(
            title="Standup",
            date_time_start="2026-04-01T09:00:00",
            meeting_type="internal",
        )


def test_create_task_requires_title():
    with pytest.raises(ValidationError):
        CreateTask()


def test_create_task_rejects_invalid_mode():
    with pytest.raises(ValidationError):
        CreateTask(title="Bad Mode", task_mode="invalid")


def test_create_task_defaults():
    task = CreateTask(title="My Task")
    assert task.status == "not started"
    assert task.task_mode == "action"
    assert task.priority == "normal"


def test_update_task_auto_completed_at():
    task = UpdateTask(status="done")
    assert task.completed_at is not None


def test_update_task_auto_started_at():
    task = UpdateTask(status="in progress")
    assert task.started_at is not None


def test_update_task_no_auto_fill_when_provided():
    task = UpdateTask(status="done", completed_at="2026-01-01T00:00:00")
    assert task.completed_at == "2026-01-01T00:00:00"


def test_create_matter_requires_title_and_type():
    with pytest.raises(ValidationError):
        CreateMatter(title="Only Title")

    with pytest.raises(ValidationError):
        CreateMatter(matter_type="rulemaking")


def test_create_matter_defaults():
    matter = CreateMatter(title="Test", matter_type="rulemaking")
    assert matter.status == "new intake"
    assert matter.priority == "important this month"
    assert matter.next_step == "Determine next steps"


def test_update_matter_auto_closed_at():
    matter = UpdateMatter(status="closed")
    assert matter.closed_at is not None


def test_create_decision_requires_matter_and_title():
    with pytest.raises(ValidationError):
        CreateDecision(title="No Matter")

    with pytest.raises(ValidationError):
        CreateDecision(matter_id="some-id")


def test_create_decision_defaults():
    decision = CreateDecision(title="Decision", matter_id="some-id")
    assert decision.status == "pending"


def test_update_decision_auto_made_at():
    decision = UpdateDecision(status="made")
    assert decision.made_at is not None


def test_create_document_requires_title_and_type():
    with pytest.raises(ValidationError):
        CreateDocument(title="No Type")

    with pytest.raises(ValidationError):
        CreateDocument(document_type="invalid-type")


def test_create_document_defaults():
    document = CreateDocument(title="Doc", document_type="legal_memo")
    assert document.status == "not started"
    assert document.is_finalized == 0
    assert document.is_sent == 0


def test_update_document_auto_sent_at():
    document = UpdateDocument(is_sent=1)
    assert document.sent_at is not None


def test_create_context_note_requires_fields():
    with pytest.raises(ValidationError):
        CreateContextNote(title="No body or category")


def test_create_context_note_defaults():
    note = CreateContextNote(title="Note", body="Text", category="process_note")
    assert note.posture == "factual"
    assert note.durability == "durable"
    assert note.sensitivity == "low"


def test_create_context_note_link_requires_fields():
    with pytest.raises(ValidationError):
        CreateContextNoteLink(entity_type="person")


def test_create_context_note_link_rejects_empty_strings():
    with pytest.raises(ValidationError):
        CreateContextNoteLink(entity_type="", entity_id="x", relationship_role="subject")


@pytest.mark.parametrize("matter_type", ENUMS["matter_type"])
def test_create_matter_accepts_all_canonical_matter_types(matter_type):
    matter = CreateMatter(title="Matter", matter_type=matter_type)
    assert matter.matter_type == matter_type


@pytest.mark.parametrize("status", ENUMS["matter_status"])
def test_update_matter_accepts_all_canonical_statuses(status):
    matter = UpdateMatter(status=status)
    assert matter.status == status


@pytest.mark.parametrize("priority", ENUMS["matter_priority"])
def test_update_matter_accepts_all_canonical_priorities(priority):
    matter = UpdateMatter(priority=priority)
    assert matter.priority == priority


@pytest.mark.parametrize("sensitivity", ENUMS["matter_sensitivity"])
def test_update_matter_accepts_all_canonical_sensitivities(sensitivity):
    matter = UpdateMatter(sensitivity=sensitivity)
    assert matter.sensitivity == sensitivity


@pytest.mark.parametrize("boss_involvement_level", ENUMS["boss_involvement_level"])
def test_update_matter_accepts_all_canonical_boss_levels(boss_involvement_level):
    matter = UpdateMatter(boss_involvement_level=boss_involvement_level)
    assert matter.boss_involvement_level == boss_involvement_level


@pytest.mark.parametrize("task_mode", ENUMS["task_mode"])
def test_create_task_accepts_all_canonical_task_modes(task_mode):
    task = CreateTask(title="Task", task_mode=task_mode)
    assert task.task_mode == task_mode
