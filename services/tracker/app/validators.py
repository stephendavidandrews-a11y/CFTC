"""
CFTC Tracker — Pydantic request models for all write endpoints.

FastAPI auto-returns 422 with structured errors when validation fails.
All Optional fields default to None. Required fields raise 422 if missing.
"""
from typing import Optional, List
from datetime import datetime as dt
from pydantic import BaseModel, Field, model_validator


# ── People ───────────────────────────────────────────────────────────────────

class CreatePerson(BaseModel):
    full_name: str = Field(..., min_length=1, description="Required display name")
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    title: Optional[str] = None
    organization_id: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    assistant_name: Optional[str] = None
    assistant_contact: Optional[str] = None
    working_style_notes: Optional[str] = None
    substantive_areas: Optional[str] = None
    relationship_category: Optional[str] = None
    relationship_lane: Optional[str] = None
    personality: Optional[str] = None
    last_interaction_date: Optional[str] = None
    next_interaction_needed_date: Optional[str] = None
    next_interaction_type: Optional[str] = None
    next_interaction_purpose: Optional[str] = None
    manager_person_id: Optional[str] = None
    include_in_team_workload: int = 0
    include_in_team: Optional[bool] = None  # alias accepted from frontend
    relationship_assigned_to_person_id: Optional[str] = None
    is_active: int = 1
    source: str = "manual"
    source_id: Optional[str] = None
    external_refs: Optional[str] = None

    def model_post_init(self, __context):
        if self.include_in_team is not None:
            self.include_in_team_workload = 1 if self.include_in_team else 0


class UpdatePerson(BaseModel):
    full_name: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    title: Optional[str] = None
    organization_id: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    assistant_name: Optional[str] = None
    assistant_contact: Optional[str] = None
    working_style_notes: Optional[str] = None
    substantive_areas: Optional[str] = None
    relationship_category: Optional[str] = None
    relationship_lane: Optional[str] = None
    personality: Optional[str] = None
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


# ── Organizations ────────────────────────────────────────────────────────────

class CreateOrganization(BaseModel):
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


class UpdateOrganization(BaseModel):
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


# ── Meetings ─────────────────────────────────────────────────────────────────

class MeetingParticipant(BaseModel):
    person_id: str = Field(..., description="Required person ID")
    organization_id: Optional[str] = None
    meeting_role: str = "attendee"
    attendance_status: str = "invited"
    attended: Optional[int] = None
    follow_up_expected: Optional[int] = None
    notes: Optional[str] = None


class CreateMeeting(BaseModel):
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


class UpdateMeeting(BaseModel):
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


# ── Tasks ────────────────────────────────────────────────────────────────────

class CreateTask(BaseModel):
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


class UpdateTask(BaseModel):
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

    @model_validator(mode="before")
    @classmethod
    def auto_fill_timestamps(cls, values):
        if isinstance(values, dict):
            if values.get("status") == "done" and not values.get("completed_at"):
                values["completed_at"] = dt.now().isoformat()
            if values.get("status") == "in progress" and not values.get("started_at"):
                values["started_at"] = dt.now().isoformat()
        return values


# ── Matters ──────────────────────────────────────────────────────────────────

class CreateMatter(BaseModel):
    title: str = Field(..., min_length=1, description="Required matter title")
    matter_type: str = Field(..., min_length=1, description="Required matter type")
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


class UpdateMatter(BaseModel):
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


# ── Matter sub-resources ─────────────────────────────────────────────────────

class AddMatterPerson(BaseModel):
    person_id: str = Field(..., description="Required person ID")
    matter_role: str = "FYI only"
    engagement_level: Optional[str] = None
    notes: Optional[str] = None


class AddMatterOrg(BaseModel):
    organization_id: str = Field(..., description="Required org ID")
    organization_role: str = "FYI"
    notes: Optional[str] = None


class AddMatterUpdate(BaseModel):
    summary: str = Field(..., min_length=1, description="Required update text")
    update_type: str = "status update"
    created_by_person_id: Optional[str] = None


# ── Decisions ────────────────────────────────────────────────────────────────

class CreateDecision(BaseModel):
    matter_id: str = Field(..., description="Required matter ID")
    title: str = Field(..., min_length=1, description="Required decision title")
    decision_type: Optional[str] = None
    status: str = "pending"
    decision_assigned_to_person_id: Optional[str] = None
    decision_due_date: Optional[str] = None
    options_summary: Optional[str] = None
    recommended_option: Optional[str] = None
    notes: Optional[str] = None
    source: str = "manual"
    source_id: Optional[str] = None
    ai_confidence: Optional[float] = None
    automation_hold: int = 0
    external_refs: Optional[str] = None


class UpdateDecision(BaseModel):
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


# ── Documents ────────────────────────────────────────────────────────────────

class CreateDocument(BaseModel):
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


class UpdateDocument(BaseModel):
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
