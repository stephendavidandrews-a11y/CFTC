"""Pydantic models for validating Sonnet extraction output.

These models validate the raw JSON output from Sonnet before
post-processing. They enforce structural correctness but allow
flexible proposed_data (validated at commit time against tracker schema).
"""

from typing import Optional
from pydantic import BaseModel, Field


# ── Source provenance ──

class SourceTimeRange(BaseModel):
    start: float
    end: float


class SourceEvidence(BaseModel):
    """A single piece of supporting evidence from the source material."""
    excerpt: str = Field(..., min_length=1, description="Exact or close quote")
    segments: list[str] = Field(default_factory=list, description="Transcript segment IDs")
    time_range: Optional[SourceTimeRange] = None
    speaker: Optional[str] = None


# ── Bundle items ──

class ExtractionItem(BaseModel):
    """A single proposed tracker write."""
    item_type: str = Field(
        ...,
        description="One of: task, follow_up, decision, matter_update, "
                    "meeting_record, stakeholder_addition, status_change, "
                    "document, new_person, new_organization",
    )
    proposed_data: dict = Field(..., description="Item-type-specific fields")
    confidence: float = Field(..., ge=0.0, le=1.0)
    rationale: str = Field(..., min_length=1)

    # New multi-evidence format (preferred)
    source_evidence: Optional[list[SourceEvidence]] = None

    # Legacy single-evidence fields (still accepted for backward compat)
    source_excerpt: Optional[str] = None
    source_segments: list[str] = Field(default_factory=list)
    source_time_range: Optional[SourceTimeRange] = None

    def get_evidence_list(self) -> list[dict]:
        """Return normalized evidence list regardless of format used."""
        if self.source_evidence:
            return [
                {
                    "excerpt": e.excerpt,
                    "segments": e.segments,
                    "time_range": {"start": e.time_range.start, "end": e.time_range.end} if e.time_range else None,
                    "speaker": e.speaker,
                }
                for e in self.source_evidence
            ]
        # Fall back to legacy single evidence
        if self.source_excerpt:
            return [{
                "excerpt": self.source_excerpt,
                "segments": self.source_segments,
                "time_range": {"start": self.source_time_range.start, "end": self.source_time_range.end} if self.source_time_range else None,
                "speaker": None,
            }]
        return []

    @property
    def primary_excerpt(self) -> str:
        """Return the first evidence excerpt (for backward compat DB column)."""
        evidence = self.get_evidence_list()
        return evidence[0]["excerpt"] if evidence else ""

    @property
    def primary_segments(self) -> list[str]:
        """Return all unique segment IDs across all evidence."""
        evidence = self.get_evidence_list()
        seen = set()
        result = []
        for e in evidence:
            for s in e.get("segments", []):
                if s not in seen:
                    seen.add(s)
                    result.append(s)
        return result

    @property
    def primary_time_range(self):
        """Return the widest time range spanning all evidence."""
        evidence = self.get_evidence_list()
        starts = [e["time_range"]["start"] for e in evidence if e.get("time_range")]
        ends = [e["time_range"]["end"] for e in evidence if e.get("time_range")]
        if starts and ends:
            return SourceTimeRange(start=min(starts), end=max(ends))
        return self.source_time_range


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
    extraction_version: str = "1.0.0"
    communication_id: str
    extraction_summary: str
    matter_associations: list[MatterAssociation] = Field(default_factory=list)
    bundles: list[ExtractionBundle] = Field(default_factory=list)
    suppressed_observations: list[SuppressedObservation] = Field(default_factory=list)
    unmatched_intelligence: Optional[str] = None


# ── Valid vocabularies for post-processing checks ──

VALID_BUNDLE_TYPES = {"matter", "new_matter", "standalone"}

VALID_ITEM_TYPES = {
    "task", "follow_up", "decision", "matter_update",
    "meeting_record", "stakeholder_addition", "status_change",
    "document", "new_person", "new_organization",
}

# Maps extraction_policy toggle names to item_type values
POLICY_TOGGLE_MAP = {
    "propose_tasks": "task",
    "propose_follow_ups": "follow_up",
    "propose_decisions": "decision",
    "propose_matter_updates": "matter_update",
    "propose_meeting_records": "meeting_record",
    "propose_stakeholders": "stakeholder_addition",
    "propose_status_changes": "status_change",
    "propose_documents": "document",
    "propose_new_people": "new_person",
    "propose_new_organizations": "new_organization",
}
