"""
Pydantic schemas for Pipeline Manager request/response validation.

Follows the pattern from app/schemas/schemas.py.
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


# ---------------------------------------------------------------------------
# Pipeline Items
# ---------------------------------------------------------------------------

class PipelineItemCreate(BaseModel):
    module: str = Field(..., pattern="^(rulemaking|regulatory_action)$")
    item_type: str
    title: str
    short_title: Optional[str] = None
    description: Optional[str] = None
    docket_number: Optional[str] = None
    rin: Optional[str] = None
    fr_citation: Optional[str] = None
    fr_doc_number: Optional[str] = None
    lead_attorney_id: Optional[int] = None
    backup_attorney_id: Optional[int] = None
    chairman_priority: bool = False
    # Regulatory action specifics
    action_subtype: Optional[str] = None
    requesting_party: Optional[str] = None
    related_rulemaking_id: Optional[int] = None
    # Integration keys
    stage1_fr_citation: Optional[str] = None
    stage1_doc_id: Optional[str] = None
    eo_action_item_id: Optional[int] = None
    comment_docket: Optional[str] = None


class PipelineItemUpdate(BaseModel):
    title: Optional[str] = None
    short_title: Optional[str] = None
    description: Optional[str] = None
    docket_number: Optional[str] = None
    rin: Optional[str] = None
    fr_citation: Optional[str] = None
    current_stage: Optional[str] = None
    priority_override: Optional[float] = None
    priority_label: Optional[str] = None
    chairman_priority: Optional[bool] = None
    lead_attorney_id: Optional[int] = None
    backup_attorney_id: Optional[int] = None
    status: Optional[str] = None
    action_subtype: Optional[str] = None
    requesting_party: Optional[str] = None
    related_rulemaking_id: Optional[int] = None
    unified_agenda_rin: Optional[str] = None
    stage1_fr_citation: Optional[str] = None
    stage1_doc_id: Optional[str] = None
    eo_action_item_id: Optional[int] = None
    comment_docket: Optional[str] = None


class PipelineItemResponse(BaseModel):
    id: int
    module: str
    item_type: str
    title: str
    short_title: Optional[str] = None
    docket_number: Optional[str] = None
    rin: Optional[str] = None
    fr_citation: Optional[str] = None
    current_stage: str
    stage_label: str = ""
    stage_color: str = ""
    priority_composite: float
    priority_label: str
    chairman_priority: bool = False
    lead_attorney_id: Optional[int] = None
    lead_attorney_name: Optional[str] = None
    status: str
    days_in_stage: int = 0
    next_deadline_date: Optional[str] = None
    next_deadline_title: Optional[str] = None
    deadline_severity: Optional[str] = None
    created_at: str
    updated_at: str


class PipelineItemDetailResponse(PipelineItemResponse):
    description: Optional[str] = None
    fr_doc_number: Optional[str] = None
    backup_attorney_id: Optional[int] = None
    backup_attorney_name: Optional[str] = None
    action_subtype: Optional[str] = None
    requesting_party: Optional[str] = None
    related_rulemaking_id: Optional[int] = None
    unified_agenda_rin: Optional[str] = None
    stage1_fr_citation: Optional[str] = None
    stage1_doc_id: Optional[str] = None
    eo_action_item_id: Optional[int] = None
    comment_docket: Optional[str] = None
    enforcement_referral: bool = False
    foia_request_count: int = 0
    archived_at: Optional[str] = None
    archived_reason: Optional[str] = None
    created_by: Optional[str] = None
    assignments: List[dict] = []
    deadlines: List[dict] = []
    recent_decisions: List[dict] = []
    stages: List[dict] = []


class PipelineItemListResponse(BaseModel):
    items: List[PipelineItemResponse]
    total: int


class StageAdvanceRequest(BaseModel):
    rationale: Optional[str] = None
    decided_by: Optional[str] = None


# ---------------------------------------------------------------------------
# Kanban
# ---------------------------------------------------------------------------

class KanbanColumn(BaseModel):
    stage_key: str
    stage_label: str
    stage_color: str
    stage_order: int
    items: List[PipelineItemResponse]
    count: int


class KanbanResponse(BaseModel):
    module: str
    item_type: Optional[str] = None
    columns: List[KanbanColumn]
    total_items: int


# ---------------------------------------------------------------------------
# Deadlines
# ---------------------------------------------------------------------------

class DeadlineCreate(BaseModel):
    item_id: int
    deadline_type: str
    title: str
    due_date: str
    source: Optional[str] = None
    source_detail: Optional[str] = None
    is_hard_deadline: bool = True
    days_warning: int = 14
    days_critical: int = 3
    owner_id: Optional[int] = None


class DeadlineUpdate(BaseModel):
    title: Optional[str] = None
    due_date: Optional[str] = None
    deadline_type: Optional[str] = None
    status: Optional[str] = None
    owner_id: Optional[int] = None
    is_hard_deadline: Optional[bool] = None
    days_warning: Optional[int] = None
    days_critical: Optional[int] = None


class DeadlineResponse(BaseModel):
    id: int
    item_id: int
    item_title: Optional[str] = None
    deadline_type: str
    title: str
    due_date: str
    source: Optional[str] = None
    is_hard_deadline: bool
    status: str
    days_remaining: Optional[int] = None
    severity: str = "ok"
    owner_id: Optional[int] = None
    owner_name: Optional[str] = None
    extended_to: Optional[str] = None
    extension_reason: Optional[str] = None
    created_at: str


class DeadlineListResponse(BaseModel):
    deadlines: List[DeadlineResponse]
    total: int


class ExtendDeadlineRequest(BaseModel):
    new_due_date: str
    reason: str


class BackwardCalcRequest(BaseModel):
    item_id: int
    final_deadline_date: str
    item_type: str


# ---------------------------------------------------------------------------
# Team
# ---------------------------------------------------------------------------

class TeamMemberCreate(BaseModel):
    name: str
    email: Optional[str] = None
    role: str
    gs_level: Optional[str] = None
    division: str = "Regulation"
    specializations: List[str] = []
    max_concurrent: int = 5


class TeamMemberUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    role: Optional[str] = None
    gs_level: Optional[str] = None
    division: Optional[str] = None
    specializations: Optional[List[str]] = None
    max_concurrent: Optional[int] = None
    is_active: Optional[bool] = None


class TeamMemberResponse(BaseModel):
    id: int
    name: str
    email: Optional[str] = None
    role: str
    gs_level: Optional[str] = None
    division: str
    specializations: List[str] = []
    max_concurrent: int
    is_active: bool
    created_at: str


class WorkloadResponse(BaseModel):
    member: TeamMemberResponse
    active_items: int
    lead_items: int
    overdue_deadlines: int
    upcoming_deadlines: List[dict] = []
    capacity_remaining: int
    items: List[dict] = []


class TeamDashboardResponse(BaseModel):
    members: List[dict]
    total_active_items: int
    total_overdue: int


# ---------------------------------------------------------------------------
# Decision Log
# ---------------------------------------------------------------------------

class DecisionLogCreate(BaseModel):
    action_type: str
    description: str
    decided_by: Optional[str] = None
    rationale: Optional[str] = None


class DecisionLogResponse(BaseModel):
    id: int
    item_id: int
    action_type: str
    description: str
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    decided_by: Optional[str] = None
    rationale: Optional[str] = None
    created_at: str


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

class ExecutiveSummaryResponse(BaseModel):
    active_rulemakings: int
    active_reg_actions: int
    total_overdue_deadlines: int
    total_stalled_items: int
    upcoming_deadlines: List[dict]
    team_workload: List[dict]
    pipeline_distribution: dict
    reg_action_distribution: dict
    recent_activity: List[dict]
    unread_notifications: int


class NotificationResponse(BaseModel):
    id: int
    recipient_id: Optional[int] = None
    item_id: Optional[int] = None
    item_title: Optional[str] = None
    notification_type: str
    title: str
    message: Optional[str] = None
    severity: str
    is_read: bool
    created_at: str


# ---------------------------------------------------------------------------
# Stakeholders & Meetings
# ---------------------------------------------------------------------------

class StakeholderCreate(BaseModel):
    name: str
    organization: Optional[str] = None
    stakeholder_type: str
    title: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    notes: Optional[str] = None


class StakeholderResponse(BaseModel):
    id: int
    name: str
    organization: Optional[str] = None
    stakeholder_type: str
    title: Optional[str] = None
    email: Optional[str] = None
    notes: Optional[str] = None
    created_at: str


class MeetingCreate(BaseModel):
    item_id: Optional[int] = None
    meeting_type: str
    title: str
    date: str
    attendees: List[str] = []
    summary: Optional[str] = None
    is_ex_parte: bool = False


class MeetingResponse(BaseModel):
    id: int
    item_id: Optional[int] = None
    item_title: Optional[str] = None
    meeting_type: str
    title: str
    date: str
    attendees: List[str] = []
    summary: Optional[str] = None
    is_ex_parte: bool
    ex_parte_filed: bool
    created_at: str
