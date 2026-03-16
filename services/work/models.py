"""
Pydantic models for Work Management request/response validation.
"""

from typing import Optional, List
from pydantic import BaseModel


# ── Project Types ───────────────────────────────────────────────────

class ProjectTypeResponse(BaseModel):
    id: int
    type_key: str
    label: str
    description: Optional[str] = None
    sort_order: int = 0


class ProjectTypeCreate(BaseModel):
    type_key: str
    label: str
    description: Optional[str] = None


# ── Projects ───────────────────────────────────────────────────────

class ProjectCreate(BaseModel):
    title: str
    short_title: Optional[str] = None
    description: Optional[str] = None
    project_type: str
    status: str = "active"
    priority_label: str = "medium"
    lead_attorney_id: Optional[int] = None
    linked_pipeline_id: Optional[int] = None
    linked_docket: Optional[str] = None
    linked_eo_doc_id: Optional[int] = None
    apply_template: bool = False
    source: Optional[str] = None
    why_me: Optional[str] = None
    due_date: Optional[str] = None


class ProjectUpdate(BaseModel):
    title: Optional[str] = None
    short_title: Optional[str] = None
    description: Optional[str] = None
    project_type: Optional[str] = None
    status: Optional[str] = None
    priority_label: Optional[str] = None
    lead_attorney_id: Optional[int] = None
    linked_pipeline_id: Optional[int] = None
    linked_docket: Optional[str] = None
    linked_eo_doc_id: Optional[int] = None
    source: Optional[str] = None
    why_me: Optional[str] = None
    completion_notes: Optional[str] = None
    due_date: Optional[str] = None


class ProjectResponse(BaseModel):
    id: int
    title: str
    short_title: Optional[str] = None
    description: Optional[str] = None
    project_type: str
    type_label: str = ""
    status: str
    priority_label: str
    lead_attorney_id: Optional[int] = None
    lead_attorney_name: Optional[str] = None
    linked_pipeline_id: Optional[int] = None
    linked_pipeline_title: Optional[str] = None
    linked_pipeline_rin: Optional[str] = None
    linked_pipeline_stage: Optional[str] = None
    linked_docket: Optional[str] = None
    linked_eo_doc_id: Optional[int] = None
    source: Optional[str] = None
    why_me: Optional[str] = None
    completion_notes: Optional[str] = None
    due_date: Optional[str] = None
    delegation_pct: int = 0
    sort_order: int = 0
    progress_completed: int = 0
    progress_total: int = 0
    effective_deadline: Optional[str] = None
    blocked_count: int = 0
    created_at: str
    updated_at: str


class ReorderItem(BaseModel):
    id: int
    sort_order: int


class ReorderRequest(BaseModel):
    items: List[ReorderItem]


# ── Work Items ──────────────────────────────────────────────────────

class WorkItemCreate(BaseModel):
    title: str
    description: Optional[str] = None
    parent_id: Optional[int] = None
    status: str = "not_started"
    priority_label: Optional[str] = None
    due_date: Optional[str] = None
    blocked_reason: Optional[str] = None
    context: Optional[str] = None
    last_update_notes: Optional[str] = None


class WorkItemUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    priority_label: Optional[str] = None
    due_date: Optional[str] = None
    blocked_reason: Optional[str] = None
    context: Optional[str] = None
    last_update_notes: Optional[str] = None
    last_update_date: Optional[str] = None
    completion_notes: Optional[str] = None


class WorkItemMoveRequest(BaseModel):
    parent_id: Optional[int] = None
    project_id: Optional[int] = None


class AssigneeInfo(BaseModel):
    id: int
    team_member_id: int
    name: str = ""
    role: str = "assigned"


class WorkItemResponse(BaseModel):
    id: int
    project_id: int
    parent_id: Optional[int] = None
    title: str
    description: Optional[str] = None
    status: str
    priority_label: Optional[str] = None
    due_date: Optional[str] = None
    blocked_reason: Optional[str] = None
    context: Optional[str] = None
    last_update_notes: Optional[str] = None
    last_update_date: Optional[str] = None
    completion_notes: Optional[str] = None
    days_since_update: Optional[int] = None
    days_until_due: Optional[int] = None
    needs_attention: bool = False
    sort_order: int = 0
    progress_completed: int = 0
    progress_total: int = 0
    effective_deadline: Optional[str] = None
    assignees: List[AssigneeInfo] = []
    children: List["WorkItemResponse"] = []
    tasks: List["TaskResponse"] = []
    depth: int = 0
    created_at: str
    updated_at: str
    completed_at: Optional[str] = None


# ── Assignments ─────────────────────────────────────────────────────

class AssignmentCreate(BaseModel):
    team_member_id: int
    role: str = "assigned"


class AssignmentResponse(BaseModel):
    id: int
    work_item_id: int
    team_member_id: int
    member_name: str = ""
    role: str
    assigned_at: str


# ── Dependencies ────────────────────────────────────────────────────

class DependencyCreate(BaseModel):
    blocking_item_id: int


class DependencyResponse(BaseModel):
    id: int
    blocked_item_id: int
    blocking_item_id: int
    blocking_item_title: str = ""
    description: Optional[str] = None
    resolved: bool = False
    resolved_at: Optional[str] = None


# ── Tasks ───────────────────────────────────────────────────────────

class TaskCreate(BaseModel):
    title: str
    description: Optional[str] = None
    status: str = "todo"
    priority_label: str = "medium"
    due_date: Optional[str] = None
    project_id: Optional[int] = None
    work_item_id: Optional[int] = None
    parent_id: Optional[int] = None
    linked_member_id: Optional[int] = None
    tags: Optional[List[str]] = None
    notes: Optional[str] = None
    source_system: Optional[str] = None
    source_id: Optional[str] = None


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    priority_label: Optional[str] = None
    due_date: Optional[str] = None
    project_id: Optional[int] = None
    work_item_id: Optional[int] = None
    parent_id: Optional[int] = None
    linked_member_id: Optional[int] = None
    tags: Optional[List[str]] = None
    notes: Optional[str] = None


class TaskResponse(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    status: str
    priority_label: str
    due_date: Optional[str] = None
    project_id: Optional[int] = None
    project_title: Optional[str] = None
    work_item_id: Optional[int] = None
    parent_id: Optional[int] = None
    linked_member_id: Optional[int] = None
    member_name: Optional[str] = None
    tags: List[str] = []
    notes: Optional[str] = None
    source_system: Optional[str] = None
    source_id: Optional[str] = None
    children: List["TaskResponse"] = []
    created_at: str
    updated_at: str
    completed_at: Optional[str] = None


# ── Manager Notes ───────────────────────────────────────────────────

class NoteCreate(BaseModel):
    content: str
    project_id: Optional[int] = None
    work_item_id: Optional[int] = None
    linked_member_id: Optional[int] = None
    note_type: str = "general"
    context_type: str = "general"


class NoteUpdate(BaseModel):
    content: Optional[str] = None
    note_type: Optional[str] = None
    context_type: Optional[str] = None
    processed: Optional[bool] = None
    ai_insights: Optional[str] = None


class NoteResponse(BaseModel):
    id: int
    content: str
    project_id: Optional[int] = None
    work_item_id: Optional[int] = None
    linked_member_id: Optional[int] = None
    member_name: Optional[str] = None
    note_type: str
    context_type: str = "general"
    processed: bool = False
    ai_insights: Optional[str] = None
    created_at: str


# ── Dashboard ───────────────────────────────────────────────────────

class DashboardResponse(BaseModel):
    active_projects_by_type: dict = {}
    total_work_items_by_status: dict = {}
    overdue_items: int = 0
    blocked_items: int = 0
    upcoming_deadlines: List[dict] = []
    task_summary: dict = {}


class BottleneckResponse(BaseModel):
    blocked_items: List[dict] = []
    unassigned_items: List[dict] = []
    overdue_items: List[dict] = []
    overloaded_attorneys: List[dict] = []


# Rebuild forward references
WorkItemResponse.model_rebuild()
TaskResponse.model_rebuild()
