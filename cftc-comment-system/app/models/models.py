"""SQLAlchemy ORM models for the CFTC Comment Analysis System."""

import enum
from datetime import datetime, date
from sqlalchemy import (
    Column, Integer, String, Text, Date, DateTime, Boolean, Enum, JSON,
    ForeignKey, Index, UniqueConstraint, Float,
)
from sqlalchemy.orm import relationship
from app.core.database import Base


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class PriorityLevel(str, enum.Enum):
    HIGH = "HIGH"
    STANDARD = "STANDARD"


class RuleStatus(str, enum.Enum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"


class CommentTier(int, enum.Enum):
    TIER_1 = 1
    TIER_2 = 2
    TIER_3 = 3


class Sentiment(str, enum.Enum):
    SUPPORT = "SUPPORT"
    OPPOSE = "OPPOSE"
    MIXED = "MIXED"
    NEUTRAL = "NEUTRAL"


class TagType(str, enum.Enum):
    TOPIC = "TOPIC"
    LEGAL_CITATION = "LEGAL_CITATION"
    THEME = "THEME"


class OrgCategory(str, enum.Enum):
    LAW_FIRM = "LAW_FIRM"
    INDUSTRY_ASSOCIATION = "INDUSTRY_ASSOCIATION"
    EXCHANGE = "EXCHANGE"
    GOVERNMENT = "GOVERNMENT"
    ACADEMIA = "ACADEMIA"


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class ProposedRule(Base):
    """A CFTC proposed rule tracked by the system."""
    __tablename__ = "proposed_rules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    docket_number = Column(String(50), unique=True, nullable=False, index=True)
    rin = Column(String(20), nullable=True)
    title = Column(Text, nullable=False)
    publication_date = Column(Date, nullable=True)
    comment_period_start = Column(Date, nullable=True)
    comment_period_end = Column(Date, nullable=True)
    federal_register_citation = Column(String(100), nullable=True)
    federal_register_doc_number = Column(String(50), nullable=True)
    priority_level = Column(Enum(PriorityLevel), default=PriorityLevel.STANDARD, nullable=False)
    status = Column(Enum(RuleStatus), default=RuleStatus.OPEN, nullable=False)
    full_text_url = Column(Text, nullable=True)
    summary = Column(Text, nullable=True)
    regulations_gov_url = Column(Text, nullable=True)
    page_count = Column(Integer, nullable=True)

    # Tracking metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    last_comment_pull = Column(DateTime, nullable=True)
    total_comments = Column(Integer, default=0)

    # Relationships
    comments = relationship("Comment", back_populates="proposed_rule", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_proposed_rules_priority_status", "priority_level", "status"),
        Index("ix_proposed_rules_comment_period_end", "comment_period_end"),
    )


class Comment(Base):
    """A public comment submitted on a proposed rule."""
    __tablename__ = "comments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    docket_number = Column(String(50), ForeignKey("proposed_rules.docket_number"), nullable=False, index=True)
    document_id = Column(String(100), unique=True, nullable=False, index=True)

    # Commenter info
    commenter_name = Column(String(500), nullable=True)
    commenter_organization = Column(String(500), nullable=True)

    # Content
    submission_date = Column(Date, nullable=True)
    comment_text = Column(Text, nullable=True)
    original_pdf_url = Column(Text, nullable=True)  # S3 path
    page_count = Column(Integer, nullable=True)
    has_attachments = Column(Boolean, default=False)
    attachment_count = Column(Integer, default=0)

    # Classification
    tier = Column(Integer, nullable=True)  # 1, 2, or 3
    sentiment = Column(Enum(Sentiment), nullable=True)
    is_form_letter = Column(Boolean, default=False)
    form_letter_group_id = Column(Integer, nullable=True)

    # AI-generated fields (populated in Phase 2)
    ai_summary = Column(Text, nullable=True)
    ai_summary_structured = Column(JSON, nullable=True)  # Tier 1 detailed structure

    # PDF extraction
    pdf_extraction_confidence = Column(Float, nullable=True)
    pdf_extraction_method = Column(String(20), nullable=True)  # "text", "ocr", "failed"

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    regulations_gov_url = Column(Text, nullable=True)

    # Relationships
    proposed_rule = relationship("ProposedRule", back_populates="comments")
    tags = relationship("CommentTag", back_populates="comment", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_comments_tier", "tier"),
        Index("ix_comments_submission_date", "submission_date"),
        Index("ix_comments_org", "commenter_organization"),
    )


class CommentTag(Base):
    """Tags extracted from comments (topics, legal citations, themes)."""
    __tablename__ = "comment_tags"

    id = Column(Integer, primary_key=True, autoincrement=True)
    comment_id = Column(Integer, ForeignKey("comments.id", ondelete="CASCADE"), nullable=False, index=True)
    tag_type = Column(Enum(TagType), nullable=False)
    tag_value = Column(String(500), nullable=False)

    comment = relationship("Comment", back_populates="tags")

    __table_args__ = (
        Index("ix_comment_tags_type_value", "tag_type", "tag_value"),
    )


class Tier1Organization(Base):
    """Known Tier 1 organizations for automatic comment classification."""
    __tablename__ = "tier1_organizations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(500), nullable=False, unique=True)
    category = Column(Enum(OrgCategory), nullable=False)
    name_variations = Column(JSON, default=list)  # e.g., ["FIA", "Futures Industry Association"]
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class WeeklyReport(Base):
    """Auto-generated weekly executive summaries."""
    __tablename__ = "weekly_reports"

    id = Column(Integer, primary_key=True, autoincrement=True)
    week_ending_date = Column(Date, nullable=False)
    generated_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    pdf_file_url = Column(Text, nullable=True)
    html_content = Column(Text, nullable=True)
