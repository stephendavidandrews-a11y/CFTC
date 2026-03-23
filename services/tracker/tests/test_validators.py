"""Tests for Pydantic validators — field constraints, defaults, auto-timestamps."""
import pytest
from app.validators import (
    CreatePerson, CreateMeeting, CreateTask, UpdateTask,
    CreateMatter, UpdateMatter,
    CreateDecision, UpdateDecision,
    CreateDocument, UpdateDocument,
    CreateContextNote, CreateContextNoteLink,
)
from pydantic import ValidationError


# ── CreatePerson ──────────────────────────────────────────────────────────────


def test_create_person_requires_full_name():
    """CreatePerson raises ValidationError without full_name."""
    with pytest.raises(ValidationError):
        CreatePerson()


def test_create_person_min_length():
    """CreatePerson rejects empty-string full_name."""
    with pytest.raises(ValidationError):
        CreatePerson(full_name="")


def test_create_person_defaults():
    """CreatePerson populates sensible defaults."""
    p = CreatePerson(full_name="Alice")
    assert p.is_active == 1
    assert p.source == "manual"
    assert p.include_in_team_workload == 0


def test_create_person_include_in_team_alias():
    """CreatePerson converts include_in_team bool to include_in_team_workload int."""
    p = CreatePerson(full_name="Bob", include_in_team=True)
    assert p.include_in_team_workload == 1


# ── CreateMeeting ─────────────────────────────────────────────────────────────


def test_create_meeting_requires_title_and_start():
    """CreateMeeting raises ValidationError without required fields."""
    with pytest.raises(ValidationError):
        CreateMeeting()

    with pytest.raises(ValidationError):
        CreateMeeting(title="Meeting only")


def test_create_meeting_defaults():
    """CreateMeeting populates default fields."""
    m = CreateMeeting(title="Standup", date_time_start="2026-04-01T09:00:00")
    assert m.boss_attends == 0
    assert m.external_parties_attend == 0
    assert m.participants == []
    assert m.matter_ids == []
    assert m.source == "manual"


# ── CreateTask ────────────────────────────────────────────────────────────────


def test_create_task_requires_title():
    """CreateTask raises ValidationError without title."""
    with pytest.raises(ValidationError):
        CreateTask()


def test_create_task_mode_literal():
    """CreateTask rejects invalid task_mode values."""
    with pytest.raises(ValidationError):
        CreateTask(title="Bad Mode", task_mode="invalid")


def test_create_task_defaults():
    """CreateTask populates defaults for status, task_mode, priority."""
    t = CreateTask(title="My Task")
    assert t.status == "not started"
    assert t.task_mode == "action"
    assert t.priority == "normal"


# ── UpdateTask auto-timestamps ────────────────────────────────────────────────


def test_update_task_auto_completed_at():
    """UpdateTask auto-fills completed_at when status is 'done'."""
    t = UpdateTask(status="done")
    assert t.completed_at is not None


def test_update_task_auto_started_at():
    """UpdateTask auto-fills started_at when status is 'in progress'."""
    t = UpdateTask(status="in progress")
    assert t.started_at is not None


def test_update_task_no_auto_fill_when_provided():
    """UpdateTask does not overwrite explicitly provided timestamps."""
    t = UpdateTask(status="done", completed_at="2026-01-01T00:00:00")
    assert t.completed_at == "2026-01-01T00:00:00"


# ── CreateMatter ──────────────────────────────────────────────────────────────


def test_create_matter_requires_title_and_type():
    """CreateMatter raises ValidationError without title or matter_type."""
    with pytest.raises(ValidationError):
        CreateMatter(title="Only Title")

    with pytest.raises(ValidationError):
        CreateMatter(matter_type="rulemaking")


def test_create_matter_defaults():
    """CreateMatter populates sensible defaults."""
    m = CreateMatter(title="Test", matter_type="rulemaking")
    assert m.status == "new intake"
    assert m.priority == "important this month"
    assert m.next_step == "Determine next steps"


# ── UpdateMatter auto-timestamps ─────────────────────────────────────────────


def test_update_matter_auto_closed_at():
    """UpdateMatter auto-fills closed_at when status is 'closed'."""
    m = UpdateMatter(status="closed")
    assert m.closed_at is not None


# ── CreateDecision ────────────────────────────────────────────────────────────


def test_create_decision_requires_matter_and_title():
    """CreateDecision raises ValidationError without required fields."""
    with pytest.raises(ValidationError):
        CreateDecision(title="No Matter")

    with pytest.raises(ValidationError):
        CreateDecision(matter_id="some-id")


def test_create_decision_defaults():
    """CreateDecision populates default status."""
    d = CreateDecision(title="Decision", matter_id="some-id")
    assert d.status == "pending"


# ── UpdateDecision auto-timestamps ────────────────────────────────────────────


def test_update_decision_auto_made_at():
    """UpdateDecision auto-fills made_at when status is 'made'."""
    d = UpdateDecision(status="made")
    assert d.made_at is not None


# ── CreateDocument ────────────────────────────────────────────────────────────


def test_create_document_requires_title_and_type():
    """CreateDocument raises ValidationError without required fields."""
    with pytest.raises(ValidationError):
        CreateDocument(title="No Type")

    with pytest.raises(ValidationError):
        CreateDocument(document_type="memo")


def test_create_document_defaults():
    """CreateDocument populates default status."""
    d = CreateDocument(title="Doc", document_type="memo")
    assert d.status == "not started"
    assert d.is_finalized == 0
    assert d.is_sent == 0


# ── UpdateDocument auto-timestamps ────────────────────────────────────────────


def test_update_document_auto_sent_at():
    """UpdateDocument auto-fills sent_at when is_sent is 1."""
    d = UpdateDocument(is_sent=1)
    assert d.sent_at is not None


# ── CreateContextNote ─────────────────────────────────────────────────────────


def test_create_context_note_requires_fields():
    """CreateContextNote raises ValidationError without required fields."""
    with pytest.raises(ValidationError):
        CreateContextNote(title="No body or category")


def test_create_context_note_defaults():
    """CreateContextNote populates defaults."""
    n = CreateContextNote(title="Note", body="Text", category="process_note")
    assert n.posture == "factual"
    assert n.durability == "durable"
    assert n.sensitivity == "low"


# ── CreateContextNoteLink ─────────────────────────────────────────────────────


def test_create_context_note_link_requires_fields():
    """CreateContextNoteLink raises ValidationError without required fields."""
    with pytest.raises(ValidationError):
        CreateContextNoteLink(entity_type="person")


def test_create_context_note_link_rejects_empty_strings():
    """CreateContextNoteLink rejects empty strings."""
    with pytest.raises(ValidationError):
        CreateContextNoteLink(entity_type="", entity_id="x", relationship_role="subject")
