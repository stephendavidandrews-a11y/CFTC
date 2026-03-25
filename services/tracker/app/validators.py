"""
CFTC Tracker - Pydantic request models for all write endpoints.

FastAPI auto-returns 422 with structured errors when validation fails.
All Optional fields default to None. Required fields raise 422 if missing.
"""

from datetime import datetime as dt
from typing import ClassVar, List, Optional

from pydantic import BaseModel, Field, model_validator

from app.contracts import get_enum_values


class EnumValidatedModel(BaseModel):
    """Base model that validates selected fields against canonical tracker enums."""

    __enum_fields__: ClassVar[dict[str, str]] = {}

    @model_validator(mode="after")
    def validate_enum_fields(self):
        for field_name, enum_name in self.__enum_fields__.items():
            value = getattr(self, field_name, None)
            if value is None:
                continue
            allowed_values = get_enum_values(enum_name)
            if value not in allowed_values:
                raise ValueError(
                    f"Invalid value for {field_name}: {value!r}. Allowed values: {allowed_values}"
                )
        return self


# People

class CreatePerson(EnumValidatedModel):
    __enum_fields__ = {
        "relationship_category": "relationship_category",
        "next_interaction_type": "next_interaction_type",
        "source": "source",
    }

    full_name: str = Field(..., min_length=1, description="Required display name")
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    title: Optional[str] = None
    organization_id: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    assistant_name: Optional[str] = None
    assistant_contact: Optional[str] = None
    substantive_areas: Optional[str] = None
    relationship_category: Optional[str] = None
    last_interaction_date: Optional[str] = None
    next_interaction_needed_date: Optional[str] = None
    next_interaction_type: Optional[str] = None
    next_interaction_purpose: Optional[str] = None
    manager_person_id: Optional[str] = None
    include_in_team_workload: int = 0
    include_in_team: Optional[bool] = None
    relationship_assigned_to_person_id: Optional[str] = None
    is_active: int = 1
    source: str = "manual"
    source_id: Optional[str] = None
    external_refs: Optional[str] = None

    def model_post_init(self, __context):
        if self.include_in_team is not None:
            self.include_in_team_workload = 1 if self.include_in_team else 0


class UpdatePerson(EnumValidatedModel):
    __enum_fields__ = {
        "relationship_category": "relationship_category",
        "next_interaction_type": "next_interaction_type",
        "source": "source",
    }

    full_name: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    title: Optional[str] = None
    organization_id: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    assistant_name: Optional[str] = None
    assistant_contact: Optional[str] = None
    substantive_areas: Optional[str] = None
    relationship_category: Optional[str] = None
    last_interaction_date: Optional[str] = None
    next_interaction_needed_date: Optional[str] = None
    next_interaction_type: Optional[str] = None
    next_interaction_purpose: Optional[str] = None
    manager_person_id: Optional[str] = None
    include_in_team_workload: Optional[int] = None
    relationship_assigned_to_person_id: Optional[str] = None
    is_active: Optional[int] = None
    source: Optional[str] = None
    source_id: Optional[str] = None
    external_refs: Optional[str] = None


# Organizations

class CreateOrganization(EnumValidatedModel):
    __enum_fields__ = {
        "organization_type": "organization_type",
        "source": "source",
    }

    name: str = Field(..., min_length=1, description="Required org name")
    short_name: Optional[str] = None
    organization_type: Optional[str] = None
    parent_organization_id: Optional[str] = None
    jurisdiction: Optional[str] = None
    notes: Optional[str] = None
    is_active: int = 1
    source: str = "manual"
    source_id: Optional[str] = None
    external_refs: Optional[str] = None


class UpdateOrganization(EnumValidatedModel):
    __enum_fields__ = {
        "organization_type": "organization_type",
        "source": "source",
    }

    name: Optional[str] = None
    short_name: Optional[str] = None
    organization_type: Optional[str] = None
    parent_organization_id: Optional[str] = None
    jurisdiction: Optional[str] = None
    notes: Optional[str] = None
    is_active: Optional[int] = None
    source: Optional[str] = None
    source_id: Optional[str] = None
    external_refs: Optional[str] = None


# Meetings

class MeetingParticipant(EnumValidatedModel):
    __enum_fields__ = {
        "meeting_role": "meeting_role",
        "attendance_status": "attendance_status",
    }

    person_id: str = Field(..., description="Required person ID")
    organization_id: Optional[str] = None
    meeting_role: str = "attendee"
    attendance_status: str = "invited"
    attended: Optional[int] = None
    follow_up_expected: Optional[int] = None
    notes: Optional[str] = None


class CreateMeeting(EnumValidatedModel):
    __enum_fields__ = {
        "meeting_type": "meeting_type",
        "source": "source",
    }

    title: str = Field(..., min_length=1, description="Required meeting title")
    meeting_type: Optional[str] = None
    date_time_start: str = Field(..., description="Required start time (ISO 8601)")
    date_time_end: Optional[str] = None
    location_or_link: Optional[str] = None
    purpose: Optional[str] = None
    prep_needed: Optional[str] = None
    notes: Optional[str] = None
    decisions_made: Optional[str] = None
    readout_summary: Optional[str] = None
    created_followups: int = 0
    boss_attends: int = 0
    external_parties_attend: int = 0
    assigned_to_person_id: Optional[str] = None
    created_by_person_id: Optional[str] = None
    participants: List[MeetingParticipant] = []
    matter_ids: List[str] = []
    source: str = "manual"
    source_id: Optional[str] = None
    external_refs: Optional[str] = None


class UpdateMeeting(EnumValidatedModel):
    __enum_fields__ = {
        "meeting_type": "meeting_type",
    }

    title: Optional[str] = None
    meeting_type: Optional[str] = None
    date_time_start: Optional[str] = None
    date_time_end: Optional[str] = None
    location_or_link: Optional[str] = None
    purpose: Optional[str] = None
    prep_needed: Optional[str] = None
    notes: Optional[str] = None
    decisions_made: Optional[str] = None
    readout_summary: Optional[str] = None
    boss_attends: Optional[int] = None
    external_parties_attend: Optional[int] = None
    created_followups: Optional[int] = None
    assigned_to_person_id: Optional[str] = None


# Tasks

class CreateTask(EnumValidatedModel):
    __enum_fields__ = {
        "task_type": "task_type",
        "status": "task_status",
        "task_mode": "task_mode",
        "priority": "task_priority",
        "deadline_type": "deadline_type",
        "source": "source",
    }

    title: str = Field(..., min_length=1, description="Required task title")
    matter_id: Optional[str] = None
    description: Optional[str] = None
    task_type: Optional[str] = None
    status: str = "not started"
    task_mode: str = "action"
    priority: str = "normal"
    assigned_to_person_id: Optional[str] = None
    created_by_person_id: Optional[str] = None
    delegated_by_person_id: Optional[str] = None
    supervising_person_id: Optional[str] = None
    waiting_on_person_id: Optional[str] = None
    waiting_on_org_id: Optional[str] = None
    waiting_on_description: Optional[str] = None
    expected_output: Optional[str] = None
    due_date: Optional[str] = None
    deadline_type: Optional[str] = None
    sort_order: Optional[int] = None
    next_follow_up_date: Optional[str] = None
    completion_notes: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    source: str = "manual"
    source_id: Optional[str] = None
    ai_confidence: Optional[float] = None
    automation_hold: int = 0
    external_refs: Optional[str] = None
    tracks_task_id: Optional[str] = None
    trigger_description: Optional[str] = None


class UpdateTask(EnumValidatedModel):
    __enum_fields__ = {
        "task_type": "task_type",
        "status": "task_status",
        "task_mode": "task_mode",
        "priority": "task_priority",
        "deadline_type": "deadline_type",
    }

    matter_id: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    task_type: Optional[str] = None
    status: Optional[str] = None
    task_mode: Optional[str] = None
    priority: Optional[str] = None
    assigned_to_person_id: Optional[str] = None
    delegated_by_person_id: Optional[str] = None
    supervising_person_id: Optional[str] = None
    waiting_on_person_id: Optional[str] = None
    waiting_on_org_id: Optional[str] = None
    waiting_on_description: Optional[str] = None
    expected_output: Optional[str] = None
    due_date: Optional[str] = None
    deadline_type: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    next_follow_up_date: Optional[str] = None
    completion_notes: Optional[str] = None
    sort_order: Optional[int] = None
    tracks_task_id: Optional[str] = None
    trigger_description: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def auto_fill_timestamps(cls, values):
        if isinstance(values, dict):
            if values.get("status") == "done" and not values.get("completed_at"):
                values["completed_at"] = dt.now().isoformat()
            if values.get("status") == "in progress" and not values.get("started_at"):
                values["started_at"] = dt.now().isoformat()
        return values


# Matters

class CreateMatter(EnumValidatedModel):
    __enum_fields__ = {
        "matter_type": "matter_type",
        "status": "matter_status",
        "priority": "matter_priority",
        "sensitivity": "matter_sensitivity",
        "risk_level": "risk_level",
        "boss_involvement_level": "boss_involvement_level",
        "regulatory_stage": "regulatory_stage",
        "unified_agenda_priority": "unified_agenda_priority",
        "source": "source",
    }

    title: str = Field(..., min_length=1, description="Required matter title")
    matter_type: str = Field(..., description="Required matter type")
    description: Optional[str] = None
    problem_statement: Optional[str] = None
    why_it_matters: Optional[str] = None
    status: str = "new intake"
    priority: str = "important this month"
    sensitivity: str = "routine"
    risk_level: Optional[str] = None
    boss_involvement_level: str = "keep boss informed"
    assigned_to_person_id: Optional[str] = None
    supervisor_person_id: Optional[str] = None
    requesting_organization_id: Optional[str] = None
    client_organization_id: Optional[str] = None
    reviewing_organization_id: Optional[str] = None
    lead_external_org_id: Optional[str] = None
    opened_date: Optional[str] = None
    work_deadline: Optional[str] = None
    decision_deadline: Optional[str] = None
    external_deadline: Optional[str] = None
    revisit_date: Optional[str] = None
    next_step: str = "Determine next steps"
    next_step_assigned_to_person_id: Optional[str] = None
    pending_decision: Optional[str] = None
    rin: Optional[str] = None
    regulatory_stage: Optional[str] = None
    federal_register_citation: Optional[str] = None
    unified_agenda_priority: Optional[str] = None
    cfr_citation: Optional[str] = None
    docket_number: Optional[str] = None
    fr_doc_number: Optional[str] = None
    source: str = "manual"
    source_id: Optional[str] = None
    ai_confidence: Optional[float] = None
    automation_hold: int = 0
    external_refs: Optional[str] = None
    created_by_person_id: Optional[str] = None


class UpdateMatter(EnumValidatedModel):
    __enum_fields__ = {
        "matter_type": "matter_type",
        "status": "matter_status",
        "priority": "matter_priority",
        "sensitivity": "matter_sensitivity",
        "risk_level": "risk_level",
        "boss_involvement_level": "boss_involvement_level",
        "regulatory_stage": "regulatory_stage",
        "unified_agenda_priority": "unified_agenda_priority",
        "source": "source",
    }

    title: Optional[str] = None
    matter_type: Optional[str] = None
    description: Optional[str] = None
    problem_statement: Optional[str] = None
    why_it_matters: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    sensitivity: Optional[str] = None
    risk_level: Optional[str] = None
    boss_involvement_level: Optional[str] = None
    assigned_to_person_id: Optional[str] = None
    supervisor_person_id: Optional[str] = None
    requesting_organization_id: Optional[str] = None
    client_organization_id: Optional[str] = None
    reviewing_organization_id: Optional[str] = None
    lead_external_org_id: Optional[str] = None
    opened_date: Optional[str] = None
    work_deadline: Optional[str] = None
    decision_deadline: Optional[str] = None
    external_deadline: Optional[str] = None
    revisit_date: Optional[str] = None
    next_step: Optional[str] = None
    next_step_assigned_to_person_id: Optional[str] = None
    pending_decision: Optional[str] = None
    outcome_summary: Optional[str] = None
    closed_at: Optional[str] = None
    is_stale_override: Optional[int] = None
    rin: Optional[str] = None
    regulatory_stage: Optional[str] = None
    federal_register_citation: Optional[str] = None
    unified_agenda_priority: Optional[str] = None
    cfr_citation: Optional[str] = None
    docket_number: Optional[str] = None
    fr_doc_number: Optional[str] = None
    source: Optional[str] = None
    source_id: Optional[str] = None
    ai_confidence: Optional[float] = None
    automation_hold: Optional[int] = None
    external_refs: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def auto_fill_closed(cls, values):
        if isinstance(values, dict):
            if values.get("status") == "closed" and not values.get("closed_at"):
                values["closed_at"] = dt.now().isoformat()
        return values


# Matter sub-resources

class AddMatterPerson(EnumValidatedModel):
    __enum_fields__ = {
        "matter_role": "matter_role",
        "engagement_level": "engagement_level",
    }

    person_id: str = Field(..., description="Required person ID")
    matter_role: str = "FYI only"
    engagement_level: Optional[str] = None
    notes: Optional[str] = None


class AddMatterOrg(EnumValidatedModel):
    __enum_fields__ = {
        "organization_role": "organization_role",
    }

    organization_id: str = Field(..., description="Required org ID")
    organization_role: str = "FYI"
    notes: Optional[str] = None


class AddMatterUpdate(EnumValidatedModel):
    __enum_fields__ = {
        "update_type": "update_type",
    }

    summary: str = Field(..., min_length=1, description="Required update text")
    update_type: str = "status update"
    created_by_person_id: Optional[str] = None


# Decisions

class CreateDecision(EnumValidatedModel):
    __enum_fields__ = {
        "decision_type": "decision_type",
        "status": "decision_status",
        "source": "source",
    }

    matter_id: str = Field(..., description="Required matter ID")
    title: str = Field(..., min_length=1, description="Required decision title")
    decision_type: Optional[str] = None
    status: str = "pending"
    decision_assigned_to_person_id: Optional[str] = None
    decision_due_date: Optional[str] = None
    options_summary: Optional[str] = None
    recommended_option: Optional[str] = None
    decision_result: Optional[str] = None
    made_at: Optional[str] = None
    notes: Optional[str] = None
    source: str = "manual"
    source_id: Optional[str] = None
    ai_confidence: Optional[float] = None
    automation_hold: int = 0
    external_refs: Optional[str] = None


class UpdateDecision(EnumValidatedModel):
    __enum_fields__ = {
        "decision_type": "decision_type",
        "status": "decision_status",
    }

    title: Optional[str] = None
    decision_type: Optional[str] = None
    status: Optional[str] = None
    decision_assigned_to_person_id: Optional[str] = None
    decision_due_date: Optional[str] = None
    options_summary: Optional[str] = None
    recommended_option: Optional[str] = None
    decision_result: Optional[str] = None
    made_at: Optional[str] = None
    notes: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def auto_fill_made(cls, values):
        if isinstance(values, dict):
            if values.get("status") == "made" and not values.get("made_at"):
                values["made_at"] = dt.now().isoformat()
        return values


# Documents

class CreateDocument(EnumValidatedModel):
    __enum_fields__ = {
        "document_type": "document_type",
        "status": "document_status",
        "source": "source",
    }

    title: str = Field(..., min_length=1, description="Required document title")
    document_type: str = Field(..., min_length=1, description="Required document type")
    matter_id: Optional[str] = None
    status: str = "not started"
    assigned_to_person_id: Optional[str] = None
    version_label: Optional[str] = None
    due_date: Optional[str] = None
    summary: Optional[str] = None
    notes: Optional[str] = None
    final_location: Optional[str] = None
    is_finalized: int = 0
    is_sent: int = 0
    sent_at: Optional[str] = None
    source: str = "manual"
    source_id: Optional[str] = None
    external_refs: Optional[str] = None


class UpdateDocument(EnumValidatedModel):
    __enum_fields__ = {
        "document_type": "document_type",
        "status": "document_status",
    }

    title: Optional[str] = None
    document_type: Optional[str] = None
    matter_id: Optional[str] = None
    status: Optional[str] = None
    assigned_to_person_id: Optional[str] = None
    version_label: Optional[str] = None
    due_date: Optional[str] = None
    summary: Optional[str] = None
    notes: Optional[str] = None
    final_location: Optional[str] = None
    is_finalized: Optional[int] = None
    is_sent: Optional[int] = None
    sent_at: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def auto_fill_sent(cls, values):
        if isinstance(values, dict):
            if values.get("is_sent") in (1, True) and not values.get("sent_at"):
                values["sent_at"] = dt.now().isoformat()
        return values


# Context Notes

class CreateContextNote(EnumValidatedModel):
    __enum_fields__ = {
        "source": "source",
    }

    title: str = Field(..., min_length=1, description="Required note title")
    body: str = Field(..., min_length=1, description="Required note body")
    category: str = Field(..., min_length=1, description="Required category")
    posture: str = "factual"
    durability: str = "durable"
    sensitivity: str = "low"
    status: str = "active"
    confidence: Optional[float] = None
    source_type: Optional[str] = None
    source_id: Optional[str] = None
    source_excerpt: Optional[str] = None
    source_timestamp_start: Optional[float] = None
    source_timestamp_end: Optional[float] = None
    speaker_attribution: Optional[str] = None
    created_by_type: str = "ai"
    created_by_person_id: Optional[str] = None
    effective_date: Optional[str] = None
    stale_after: Optional[str] = None
    notes_visibility: str = "normal"
    matter_id: Optional[str] = None
    source_communication_id: Optional[str] = None
    source: str = "manual"
    ai_confidence: Optional[float] = None
    automation_hold: int = 0
    external_refs: Optional[str] = None


class UpdateContextNote(BaseModel):
    title: Optional[str] = None
    body: Optional[str] = None
    category: Optional[str] = None
    posture: Optional[str] = None
    durability: Optional[str] = None
    sensitivity: Optional[str] = None
    status: Optional[str] = None
    confidence: Optional[float] = None
    source_excerpt: Optional[str] = None
    speaker_attribution: Optional[str] = None
    effective_date: Optional[str] = None
    stale_after: Optional[str] = None
    notes_visibility: Optional[str] = None
    matter_id: Optional[str] = None
    last_reviewed_at: Optional[str] = None
    ai_confidence: Optional[float] = None
    automation_hold: Optional[int] = None
    external_refs: Optional[str] = None


class CreateContextNoteLink(BaseModel):
    entity_type: str = Field(..., min_length=1, description="Required entity type")
    entity_id: str = Field(..., min_length=1, description="Required entity ID")
    relationship_role: str = Field(..., min_length=1, description="Required relationship role")


# Person Profiles

class UpdatePersonProfile(BaseModel):
    birthday: Optional[str] = None
    spouse_name: Optional[str] = None
    children_count: Optional[int] = None
    children_names: Optional[str] = None
    hometown: Optional[str] = None
    current_city: Optional[str] = None
    prior_roles_summary: Optional[str] = None
    education_summary: Optional[str] = None
    interests: Optional[str] = None
    personal_notes_summary: Optional[str] = None
    scheduling_notes: Optional[str] = None
    relationship_preferences: Optional[str] = None
    leadership_notes: Optional[str] = None


# Comment Topics

class CreateCommentTopic(EnumValidatedModel):
    __enum_fields__ = {
        "topic_area": "comment_topic_area",
        "position_status": "comment_topic_position_status",
        "source_document_type": "comment_topic_source_document_type",
        "priority": "task_priority",
        "deadline_type": "deadline_type",
        "source": "source",
    }

    matter_id: str = Field(..., description="Required matter ID")
    topic_label: str = Field(..., min_length=1, description="Required topic label")
    topic_area: Optional[str] = None
    assigned_to_person_id: Optional[str] = None
    secondary_assignee_person_id: Optional[str] = None
    position_status: str = "open"
    position_summary: Optional[str] = None
    priority: Optional[str] = None
    due_date: Optional[str] = None
    deadline_type: Optional[str] = None
    source_fr_doc_number: Optional[str] = None
    source_document_type: Optional[str] = None
    response_fr_doc_number: Optional[str] = None
    notes: Optional[str] = None
    sort_order: Optional[int] = None
    source: str = "manual"
    source_id: Optional[str] = None
    ai_confidence: Optional[float] = None
    automation_hold: int = 0
    external_refs: Optional[str] = None


class UpdateCommentTopic(EnumValidatedModel):
    __enum_fields__ = {
        "topic_area": "comment_topic_area",
        "position_status": "comment_topic_position_status",
        "source_document_type": "comment_topic_source_document_type",
        "priority": "task_priority",
        "deadline_type": "deadline_type",
    }

    topic_label: Optional[str] = None
    topic_area: Optional[str] = None
    assigned_to_person_id: Optional[str] = None
    secondary_assignee_person_id: Optional[str] = None
    position_status: Optional[str] = None
    position_summary: Optional[str] = None
    priority: Optional[str] = None
    due_date: Optional[str] = None
    deadline_type: Optional[str] = None
    source_fr_doc_number: Optional[str] = None
    source_document_type: Optional[str] = None
    response_fr_doc_number: Optional[str] = None
    notes: Optional[str] = None
    sort_order: Optional[int] = None


# Comment Questions

class CreateCommentQuestion(BaseModel):
    question_number: str = Field(..., min_length=1, description="Required question number")
    question_text: str = Field(..., min_length=1, description="Required question text")
    sort_order: Optional[int] = None
    source: str = "manual"
    source_id: Optional[str] = None
    ai_confidence: Optional[float] = None


class UpdateCommentQuestion(BaseModel):
    question_number: Optional[str] = None
    question_text: Optional[str] = None
    sort_order: Optional[int] = None


class MoveCommentQuestion(BaseModel):
    target_topic_id: str = Field(..., min_length=1, description="Target topic ID")


# Policy Directives

class CreatePolicyDirective(EnumValidatedModel):
    __enum_fields__ = {
        "source_document_type": "directive_source_document_type",
        "priority_tier": "directive_priority_tier",
        "responsible_entity": "directive_responsible_entity",
        "ogc_role": "directive_ogc_role",
        "implementation_status": "directive_implementation_status",
        "source": "source",
    }

    source_document: str = Field(..., min_length=1, description="Required source document citation")
    source_document_type: str = Field(..., min_length=1, description="Required document type")
    source_document_url: Optional[str] = None
    source_date: Optional[str] = None
    directive_label: str = Field(..., min_length=1, description="Required directive label")
    directive_text: Optional[str] = None
    section_reference: Optional[str] = None
    chapter: Optional[str] = None
    priority_tier: Optional[str] = None
    responsible_entity: Optional[str] = None
    ogc_role: Optional[str] = None
    assigned_to_person_id: Optional[str] = None
    implementation_status: str = "not_started"
    implementation_notes: Optional[str] = None
    target_date: Optional[str] = None
    completed_date: Optional[str] = None
    notes: Optional[str] = None
    sort_order: Optional[int] = None
    source: str = "manual"
    source_id: Optional[str] = None
    external_refs: Optional[str] = None


class UpdatePolicyDirective(EnumValidatedModel):
    __enum_fields__ = {
        "source_document_type": "directive_source_document_type",
        "priority_tier": "directive_priority_tier",
        "responsible_entity": "directive_responsible_entity",
        "ogc_role": "directive_ogc_role",
        "implementation_status": "directive_implementation_status",
    }

    source_document: Optional[str] = None
    source_document_type: Optional[str] = None
    source_document_url: Optional[str] = None
    source_date: Optional[str] = None
    directive_label: Optional[str] = None
    directive_text: Optional[str] = None
    section_reference: Optional[str] = None
    chapter: Optional[str] = None
    priority_tier: Optional[str] = None
    responsible_entity: Optional[str] = None
    ogc_role: Optional[str] = None
    assigned_to_person_id: Optional[str] = None
    implementation_status: Optional[str] = None
    implementation_notes: Optional[str] = None
    target_date: Optional[str] = None
    completed_date: Optional[str] = None
    notes: Optional[str] = None
    sort_order: Optional[int] = None

    @model_validator(mode="before")
    @classmethod
    def auto_fill_completed(cls, values):
        if isinstance(values, dict):
            if values.get("implementation_status") == "implemented" and not values.get("completed_date"):
                from datetime import datetime as dt
                values["completed_date"] = dt.now().isoformat()
        return values


# Directive-Matter Links

class CreateDirectiveMatter(EnumValidatedModel):
    __enum_fields__ = {
        "relationship_type": "directive_matter_relationship_type",
    }

    directive_id: str = Field(..., description="Required directive ID")
    matter_id: str = Field(..., description="Required matter ID")
    relationship_type: str = "implements"
    notes: Optional[str] = None


# ── Directive Research Notes ─────────────────────────────────────────────────

class CreateDirectiveDocument(EnumValidatedModel):
    __enum_fields__ = {
        "relationship_type": "directive_document_relationship_type",
    }

    directive_id: str = Field(..., description="Required directive ID")
    document_id: str = Field(..., description="Required document ID")
    relationship_type: str = "references"
    notes: Optional[str] = None



class CreateDirectiveResearchNote(BaseModel):
    directive_id: str = Field(..., description="Required directive ID")
    fr_citation: Optional[str] = None
    rule_title: Optional[str] = None
    cfr_parts: Optional[str] = None
    statutory_authority: Optional[str] = None
    action_category: Optional[str] = None
    composite_score: Optional[float] = None
    relationship_basis: Optional[str] = None
    analysis_summary: Optional[str] = None
    regulation_text_excerpt: Optional[str] = None
    needs_reg_reading: int = 0
    reg_reading_done: int = 0
    reg_reading_notes: Optional[str] = None
    promote_to_matter: int = 0
    matter_id: Optional[str] = None


class UpdateDirectiveResearchNote(BaseModel):
    fr_citation: Optional[str] = None
    rule_title: Optional[str] = None
    cfr_parts: Optional[str] = None
    statutory_authority: Optional[str] = None
    action_category: Optional[str] = None
    composite_score: Optional[float] = None
    relationship_basis: Optional[str] = None
    analysis_summary: Optional[str] = None
    regulation_text_excerpt: Optional[str] = None
    needs_reg_reading: Optional[int] = None
    reg_reading_done: Optional[int] = None
    reg_reading_notes: Optional[str] = None
    promote_to_matter: Optional[int] = None
    matter_id: Optional[str] = None
