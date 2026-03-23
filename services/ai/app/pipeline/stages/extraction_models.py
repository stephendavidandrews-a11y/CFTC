"""Pydantic models for validating extraction output (v1 + v2).

These models validate the raw JSON output from the extraction model before
post-processing. They enforce structural correctness but allow
flexible proposed_data (validated at commit time against tracker schema).

v2 changes:
- source_evidence replaces source_excerpt/source_segments/source_time_range
- client_id for forward references between items ($ref: syntax)
- Name fallback fields for entity resolution when UUID is uncertain
"""

from typing import Optional
from pydantic import BaseModel, Field, model_validator


# ── Source provenance ──

class SourceTimeRange(BaseModel):
    start: float
    end: float


class SourceEvidence(BaseModel):
    """A single piece of source evidence (v2 format)."""
    excerpt: str = Field(..., min_length=1)
    segments: list[str] = Field(default_factory=list)
    time_range: Optional[SourceTimeRange] = None
    speaker: Optional[str] = None


# ── Bundle items ──

class ExtractionItem(BaseModel):
    """A single proposed tracker write."""
    item_type: str = Field(
        ...,
        description="One of: task, task_update, decision, decision_update, "
                    "matter_update, meeting_record, stakeholder_addition, "
                    "status_change, document, context_note, "
                    "person_detail_update, new_person, new_organization, "
                    "org_detail_update",
    )
    proposed_data: dict = Field(..., description="Item-type-specific fields")
    confidence: float = Field(..., ge=0.0, le=1.0)
    rationale: str = Field(..., min_length=1)

    # v2 source evidence (array of evidence objects)
    source_evidence: Optional[list[SourceEvidence]] = None

    # v1 source fields (kept for backward compatibility)
    source_excerpt: Optional[str] = None
    source_segments: Optional[list[str]] = None
    source_time_range: Optional[SourceTimeRange] = None

    # v2 forward reference ID for paired records ($ref: syntax)
    client_id: Optional[str] = Field(
        default=None,
        description="Temporary reference ID for forward references between items",
    )

    # Entity reference name fallbacks (v2 — used when model can't resolve to UUID)
    assigned_to_name: Optional[str] = None
    waiting_on_name: Optional[str] = None
    decision_assigned_to_name: Optional[str] = None
    organization_name_ref: Optional[str] = None

    @model_validator(mode="after")
    def normalize_source_fields(self):
        """Ensure both v1 and v2 source formats are normalized.

        If v2 source_evidence is present, populate v1 fields from the first
        entry for backward compatibility with post-processing and persistence.
        If only v1 fields are present, build a single-entry source_evidence.
        """
        if self.source_evidence and len(self.source_evidence) > 0:
            first = self.source_evidence[0]
            if not self.source_excerpt:
                self.source_excerpt = first.excerpt
            if not self.source_segments:
                self.source_segments = first.segments or []
            if not self.source_time_range and first.time_range:
                self.source_time_range = first.time_range
        elif self.source_excerpt:
            # v1 only — build source_evidence for uniformity
            self.source_evidence = [SourceEvidence(
                excerpt=self.source_excerpt,
                segments=self.source_segments or [],
                time_range=self.source_time_range,
            )]

        # Ensure v1 fields have defaults for post-processing
        if not self.source_excerpt:
            self.source_excerpt = ""
        if not self.source_segments:
            self.source_segments = []
        if not self.source_time_range:
            self.source_time_range = SourceTimeRange(start=0.0, end=0.0)

        return self


# ── Bundles ──

class ExtractionBundle(BaseModel):
    """A cluster of proposals grouped by target matter."""
    bundle_type: str = Field(
        ...,
        description="matter | new_matter | standalone",
    )
    target_matter_id: Optional[str] = None
    target_matter_title: Optional[str] = None
    proposed_matter: Optional[dict] = None
    confidence: float = Field(..., ge=0.0, le=1.0)
    rationale: str = Field(..., min_length=1)
    intelligence_notes: Optional[str] = None
    uncertainty_flags: list[str] = Field(default_factory=list)
    items: list[ExtractionItem] = Field(..., min_length=1)


# ── Matter associations ──

class MatterAssociation(BaseModel):
    matter_id: str
    matter_title: str
    match_reason: str
    match_confidence: float = Field(..., ge=0.0, le=1.0)


# ── Suppressed observations ──

class SuppressedObservation(BaseModel):
    item_type: str
    description: str
    reason_noted: str
    source_excerpt: Optional[str] = None
    source_segments: list[str] = Field(default_factory=list)
    confidence_if_enabled: Optional[float] = None


# ── Top-level extraction response ──

class ExtractionOutput(BaseModel):
    """Full validated extraction response from Sonnet."""
    extraction_version: str = "2.0.0"
    communication_id: str
    extraction_summary: str
    matter_associations: list[MatterAssociation] = Field(default_factory=list)
    bundles: list[ExtractionBundle] = Field(default_factory=list)
    suppressed_observations: list[SuppressedObservation] = Field(default_factory=list)
    unmatched_intelligence: Optional[str] = None


# ── Valid vocabularies for post-processing checks ──

VALID_BUNDLE_TYPES = {"matter", "new_matter", "standalone"}

VALID_ITEM_TYPES = {
    "task", "task_update", "decision", "decision_update",
    "matter_update", "meeting_record", "stakeholder_addition",
    "status_change", "document", "context_note",
    "person_detail_update", "new_person", "new_organization",
    "org_detail_update",
}

# Maps extraction_policy toggle names to item_type values.
# follow_ups are now tasks with task_mode: "follow_up", controlled by "propose_tasks".
POLICY_TOGGLE_MAP = {
    "propose_tasks": "task",
    "propose_decisions": "decision",
    "propose_matter_updates": "matter_update",
    "propose_meeting_records": "meeting_record",
    "propose_stakeholders": "stakeholder_addition",
    "propose_status_changes": "status_change",
    "propose_documents": "document",
    "propose_new_people": "new_person",
    "propose_new_organizations": "new_organization",
    "propose_context_notes": "context_note",
    "propose_person_details": "person_detail_update",
}
# Note: task_update, decision_update, org_detail_update are always-on by design.
# Disabling them would cause the model to create duplicate records instead of updates.

# Allowed fields for task_update changes
TASK_UPDATE_ALLOWED_FIELDS = {
    "status", "priority", "due_date", "deadline_type",
    "assigned_to_person_id", "waiting_on_person_id",
    "waiting_on_org_id", "waiting_on_description",
    "next_follow_up_date", "description", "expected_output",
}

# Allowed fields for decision_update changes
DECISION_UPDATE_ALLOWED_FIELDS = {
    "status", "decision_assigned_to_person_id", "decision_due_date",
    "options_summary", "recommended_option", "decision_result",
    "made_at", "notes",
}
