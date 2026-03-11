"""Pydantic schemas for request/response validation."""

from pydantic import BaseModel, Field
from datetime import date, datetime
from typing import Optional, List
from app.models.models import PriorityLevel, RuleStatus, Sentiment, TagType, OrgCategory


# ---------------------------------------------------------------------------
# Proposed Rules
# ---------------------------------------------------------------------------

class ProposedRuleBase(BaseModel):
    docket_number: str
    title: str
    rin: Optional[str] = None
    publication_date: Optional[date] = None
    comment_period_start: Optional[date] = None
    comment_period_end: Optional[date] = None
    federal_register_citation: Optional[str] = None
    priority_level: PriorityLevel = PriorityLevel.STANDARD
    status: RuleStatus = RuleStatus.OPEN
    summary: Optional[str] = None
    regulations_gov_url: Optional[str] = None


class ProposedRuleCreate(ProposedRuleBase):
    pass


class ProposedRuleResponse(ProposedRuleBase):
    id: int
    total_comments: int = 0
    last_comment_pull: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ProposedRuleListResponse(BaseModel):
    rules: List[ProposedRuleResponse]
    total: int


# ---------------------------------------------------------------------------
# Comments
# ---------------------------------------------------------------------------

class CommentBase(BaseModel):
    document_id: str
    docket_number: str
    commenter_name: Optional[str] = None
    commenter_organization: Optional[str] = None
    submission_date: Optional[date] = None
    page_count: Optional[int] = None


class CommentResponse(CommentBase):
    id: int
    tier: Optional[int] = None
    sentiment: Optional[Sentiment] = None
    is_form_letter: bool = False
    ai_summary: Optional[str] = None
    has_attachments: bool = False
    pdf_extraction_confidence: Optional[float] = None
    created_at: datetime

    class Config:
        from_attributes = True


class CommentDetailResponse(CommentResponse):
    comment_text: Optional[str] = None
    ai_summary_structured: Optional[dict] = None
    original_pdf_url: Optional[str] = None
    regulations_gov_url: Optional[str] = None
    tags: List["CommentTagResponse"] = []

    class Config:
        from_attributes = True


class CommentListResponse(BaseModel):
    comments: List[CommentResponse]
    total: int


# ---------------------------------------------------------------------------
# Comment Tags
# ---------------------------------------------------------------------------

class CommentTagResponse(BaseModel):
    tag_type: TagType
    tag_value: str

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Tier 1 Organizations
# ---------------------------------------------------------------------------

class Tier1OrgCreate(BaseModel):
    name: str
    category: OrgCategory
    name_variations: List[str] = []


class Tier1OrgResponse(Tier1OrgCreate):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Actions
# ---------------------------------------------------------------------------

class FetchCommentsRequest(BaseModel):
    """Request to fetch comments for a specific docket."""
    docket_number: str


class AddDocketRequest(BaseModel):
    """Request to manually add a docket for tracking."""
    docket_number: str


class DocketStatsResponse(BaseModel):
    """Statistics for a docket's comments."""
    docket_number: str
    total_comments: int
    tier_1_count: int
    tier_2_count: int
    tier_3_count: int
    support_count: int
    oppose_count: int
    mixed_count: int
    neutral_count: int
    unclassified_count: int
    form_letter_count: int
    avg_page_count: Optional[float] = None
    tier1_summarized: bool = False
