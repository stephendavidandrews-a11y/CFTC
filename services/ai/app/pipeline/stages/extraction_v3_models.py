"""Pydantic models for Extraction v3.

v3 uses:
1. Pass 1 communication understanding output
2. A deterministic routing and resolution package
3. Pass 2 reviewable proposal output

The pass 2 layer stays aligned to the current extraction/writeback contract by
reusing the existing VALID_ITEM_TYPES and VALID_BUNDLE_TYPES.
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.pipeline.stages.extraction_models import (
    SourceEvidence,
    VALID_BUNDLE_TYPES,
    VALID_ITEM_TYPES,
)


PASS1_SCHEMA_VERSION = "3.0.0-pass1"
ROUTING_SCHEMA_VERSION = "3.0.0-routing"
PASS2_SCHEMA_VERSION = "3.0.0-pass2"

COMMUNICATION_KIND_VALUES = {"audio", "email"}
DIRECTNESS_VALUES = {
    "direct_statement",
    "direct_commitment",
    "direct_request",
    "inferred_from_context",
    "inferred_from_pattern",
}
DURABILITY_VALUES = {"ephemeral", "working", "durable"}
MEMORY_VALUE_VALUES = {"none", "low", "medium", "high"}
ROUTING_CONFIDENCE_VALUES = {
    "high",
    "medium",
    "multi",
    "standalone",
    "new_matter_candidate",
}
ENTITY_TYPE_VALUES = {
    "person",
    "organization",
    "matter",
    "task",
    "decision",
    "document",
    "meeting",
    "concept",
    "legislation",
}
MATCHABLE_RECORD_TYPE_VALUES = {
    "person",
    "organization",
    "matter",
    "task",
    "decision",
    "document",
    "meeting",
}
CONTEXT_NOTE_CATEGORY_VALUES = {
    "policy_operating_rule",
    "process_note",
    "strategic_context",
    "relationship_dynamic",
    "culture_climate",
    "people_insight",
}
CONTEXT_NOTE_POSTURE_VALUES = {"factual", "attributed_view"}
CONTEXT_NOTE_SENSITIVITY_VALUES = {"low", "moderate", "high"}
CONTEXT_NOTE_ALLOWED_FIELDS = {
    "title",
    "body",
    "category",
    "posture",
    "speaker_attribution",
    "durability",
    "sensitivity",
    "linked_entities",
    "matter_id",
    "effective_date",
    "stale_after",
}
PERSON_PROFILE_FIELD_VALUES = {
    "birthday",
    "spouse_name",
    "children_count",
    "children_names",
    "hometown",
    "current_city",
    "prior_roles_summary",
    "education_summary",
    "interests",
    "personal_notes_summary",
    "scheduling_notes",
    "relationship_preferences",
    "leadership_notes",
}
PERSON_DETAIL_PEOPLE_FIELD_VALUES = {
    "relationship_category",
    "email",
    "phone",
    "assistant_name",
    "assistant_contact",
    "substantive_areas",
    "manager_person_id",
}
PERSON_DETAIL_ALLOWED_TOP_LEVEL_FIELDS = {"person_id", "person_name", "fields"}
PERSON_DETAIL_ALLOWED_FIELDS = (
    PERSON_PROFILE_FIELD_VALUES | PERSON_DETAIL_PEOPLE_FIELD_VALUES
)

OBSERVATION_SUBTYPE_MAP = {
    "task_signal": {
        "commitment",
        "request",
        "follow_up_need",
        "deadline_change",
        "state_change",
        "blocker",
    },
    "decision_signal": {
        "decision_made",
        "recommendation",
        "decision_request",
        "open_question",
    },
    "matter_signal": {
        "status_change",
        "state_change",
        "priority_change",
        "risk_or_sensitivity_change",
        "scope_change",
        "dependency_change",
    },
    "meeting_signal": {
        "meeting_occurred",
        "meeting_planned",
        "meeting_recap",
    },
    "stakeholder_signal": {
        "involvement",
        "role",
        "stance",
    },
    "document_signal": {
        "document_created",
        "document_requested",
        "document_revised",
        "document_referenced",
    },
    "person_memory_signal": {
        "biography",
        "preference",
        "working_style",
        "management_guidance",
        "relationship_dynamic",
    },
    "institutional_memory_signal": {
        "operating_rule",
        "process_norm",
        "leadership_preference",
        "strategic_context",
        "organization_fact",
        "stakeholder_posture",
    },
}

OBSERVATION_TYPE_VALUES = set(OBSERVATION_SUBTYPE_MAP)
MEMORY_OBSERVATION_TYPES = {"person_memory_signal", "institutional_memory_signal"}


class V3BaseModel(BaseModel):
    """Base model for v3 structures."""

    model_config = ConfigDict(extra="forbid")


class Pass1Participant(V3BaseModel):
    speaker_label: Optional[str] = None
    display_name: str = Field(..., min_length=1)
    tracker_person_id: Optional[str] = None
    organization_name: Optional[str] = None
    tracker_org_id: Optional[str] = None
    confidence: float = Field(..., ge=0.0, le=1.0)


class ObservationSpeakerRef(V3BaseModel):
    name: str = Field(..., min_length=1)
    tracker_person_id: Optional[str] = None


class ObservationEntityRef(V3BaseModel):
    entity_type: str
    name: str = Field(..., min_length=1)
    tracker_id: Optional[str] = None

    @model_validator(mode="after")
    def validate_entity_type(self):
        if self.entity_type not in ENTITY_TYPE_VALUES:
            raise ValueError(
                f"Invalid entity_type: {self.entity_type!r}. Allowed values: {sorted(ENTITY_TYPE_VALUES)}"
            )
        return self


class CandidateMatterRef(V3BaseModel):
    matter_id: str = Field(..., min_length=1)
    matter_title: str = Field(..., min_length=1)
    score: float = Field(..., ge=0.0, le=1.0)
    reason: str = Field(..., min_length=1)


class CandidateRecordRef(V3BaseModel):
    record_type: str
    record_id: str = Field(..., min_length=1)
    score: float = Field(..., ge=0.0, le=1.0)
    reason: str = Field(..., min_length=1)

    @model_validator(mode="after")
    def validate_record_type(self):
        if self.record_type not in MATCHABLE_RECORD_TYPE_VALUES:
            raise ValueError(
                f"Invalid record_type: {self.record_type!r}. Allowed values: {sorted(MATCHABLE_RECORD_TYPE_VALUES)}"
            )
        return self


class Pass1Observation(V3BaseModel):
    id: str = Field(..., min_length=1)
    observation_type: str
    observation_subtype: str
    summary: str = Field(..., min_length=1)
    directness: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    durability: str
    memory_value: str = "none"
    speaker_refs: list[ObservationSpeakerRef] = Field(default_factory=list)
    entity_refs: list[ObservationEntityRef] = Field(default_factory=list)
    candidate_matter_refs: list[CandidateMatterRef] = Field(default_factory=list)
    candidate_record_refs: list[CandidateRecordRef] = Field(default_factory=list)
    field_hints: dict[str, Any] = Field(default_factory=dict)
    evidence: list[SourceEvidence] = Field(..., min_length=1)

    @model_validator(mode="after")
    def validate_vocab(self):
        if self.observation_type not in OBSERVATION_TYPE_VALUES:
            raise ValueError(
                f"Invalid observation_type: {self.observation_type!r}. "
                f"Allowed values: {sorted(OBSERVATION_TYPE_VALUES)}"
            )

        allowed_subtypes = OBSERVATION_SUBTYPE_MAP[self.observation_type]
        if self.observation_subtype not in allowed_subtypes:
            raise ValueError(
                f"Invalid observation_subtype {self.observation_subtype!r} for {self.observation_type!r}. "
                f"Allowed values: {sorted(allowed_subtypes)}"
            )

        if self.directness not in DIRECTNESS_VALUES:
            raise ValueError(
                f"Invalid directness: {self.directness!r}. Allowed values: {sorted(DIRECTNESS_VALUES)}"
            )

        if self.durability not in DURABILITY_VALUES:
            raise ValueError(
                f"Invalid durability: {self.durability!r}. Allowed values: {sorted(DURABILITY_VALUES)}"
            )

        if self.memory_value not in MEMORY_VALUE_VALUES:
            raise ValueError(
                f"Invalid memory_value: {self.memory_value!r}. Allowed values: {sorted(MEMORY_VALUE_VALUES)}"
            )

        if (
            self.observation_type in MEMORY_OBSERVATION_TYPES
            and self.memory_value == "none"
        ):
            raise ValueError(
                "Memory observations must use memory_value 'low', 'medium', or 'high'"
            )

        return self


class CommunicationUnderstandingOutput(V3BaseModel):
    """Pass 1 high-recall output."""

    schema_version: str = PASS1_SCHEMA_VERSION
    communication_id: str = Field(..., min_length=1)
    communication_kind: str
    communication_summary: str = Field(..., min_length=1)
    participants: list[Pass1Participant] = Field(default_factory=list)
    observations: list[Pass1Observation] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_kind(self):
        if self.communication_kind not in COMMUNICATION_KIND_VALUES:
            raise ValueError(
                f"Invalid communication_kind: {self.communication_kind!r}. "
                f"Allowed values: {sorted(COMMUNICATION_KIND_VALUES)}"
            )
        return self


class ResolvedPerson(V3BaseModel):
    name: str = Field(..., min_length=1)
    tracker_person_id: str = Field(..., min_length=1)
    resolution_confidence: float = Field(..., ge=0.0, le=1.0)
    source: str = Field(..., min_length=1)


class ResolvedOrganization(V3BaseModel):
    name: str = Field(..., min_length=1)
    tracker_org_id: str = Field(..., min_length=1)
    resolution_confidence: float = Field(..., ge=0.0, le=1.0)
    source: str = Field(..., min_length=1)


class MatterRoutingAssessment(V3BaseModel):
    primary_matter_id: Optional[str] = None
    secondary_matter_ids: list[str] = Field(default_factory=list)
    routing_confidence: str
    routing_basis: list[str] = Field(default_factory=list)
    standalone_reason: Optional[str] = None
    new_matter_candidate: bool = False

    @model_validator(mode="after")
    def validate_routing(self):
        if self.routing_confidence not in ROUTING_CONFIDENCE_VALUES:
            raise ValueError(
                f"Invalid routing_confidence: {self.routing_confidence!r}. "
                f"Allowed values: {sorted(ROUTING_CONFIDENCE_VALUES)}"
            )

        if self.routing_confidence == "standalone":
            if self.primary_matter_id is not None:
                raise ValueError(
                    "standalone routing_confidence cannot include primary_matter_id"
                )
            if not self.standalone_reason:
                raise ValueError(
                    "standalone routing_confidence requires standalone_reason"
                )

        if self.routing_confidence != "standalone" and self.standalone_reason:
            raise ValueError(
                "standalone_reason is only allowed when routing_confidence='standalone'"
            )

        return self


class RecordMatch(V3BaseModel):
    observation_id: str = Field(..., min_length=1)
    record_id: str = Field(..., min_length=1)
    match_score: float = Field(..., ge=0.0, le=1.0)
    match_reason: str = Field(..., min_length=1)


class RecordMatches(V3BaseModel):
    tasks: list[RecordMatch] = Field(default_factory=list)
    decisions: list[RecordMatch] = Field(default_factory=list)
    people: list[RecordMatch] = Field(default_factory=list)
    organizations: list[RecordMatch] = Field(default_factory=list)
    documents: list[RecordMatch] = Field(default_factory=list)
    matters: list[RecordMatch] = Field(default_factory=list)
    meetings: list[RecordMatch] = Field(default_factory=list)


class RoutingResolutionPackage(V3BaseModel):
    """Deterministic middle artifact between pass 1 and pass 2."""

    schema_version: str = ROUTING_SCHEMA_VERSION
    communication_id: str = Field(..., min_length=1)
    resolved_people: list[ResolvedPerson] = Field(default_factory=list)
    resolved_organizations: list[ResolvedOrganization] = Field(default_factory=list)
    matter_routing: MatterRoutingAssessment
    record_matches: RecordMatches = Field(default_factory=RecordMatches)
    relevant_tracker_context: dict[str, Any] = Field(default_factory=dict)


class ProposedMatterData(V3BaseModel):
    """Bundle-level new matter proposal."""

    title: str = Field(..., min_length=1)
    matter_type: str = Field(..., min_length=1)
    description: Optional[str] = None
    problem_statement: Optional[str] = None
    why_it_matters: Optional[str] = None
    status: str = "new intake"
    priority: Optional[str] = None
    sensitivity: Optional[str] = None
    boss_involvement_level: Optional[str] = None
    next_step: Optional[str] = None


class V3ProposalItem(V3BaseModel):
    """Pass 2 commit-ready proposal item."""

    item_type: str
    proposed_data: dict[str, Any] = Field(default_factory=dict)
    confidence: float = Field(..., ge=0.0, le=1.0)
    rationale: str = Field(..., min_length=1)
    why_new_vs_update: str = Field(..., min_length=1)
    why_this_matter: str = Field(..., min_length=1)
    source_observation_ids: list[str] = Field(..., min_length=1)
    source_evidence: list[SourceEvidence] = Field(..., min_length=1)
    client_id: Optional[str] = None

    @model_validator(mode="after")
    def validate_item_type(self):
        if self.item_type not in VALID_ITEM_TYPES:
            raise ValueError(
                f"Invalid item_type: {self.item_type!r}. Allowed values: {sorted(VALID_ITEM_TYPES)}"
            )

        if self.item_type == "context_note":
            self._validate_context_note()
        elif self.item_type == "person_detail_update":
            self._validate_person_detail_update()
        return self

    def _validate_context_note(self):
        data = self.proposed_data
        unknown_fields = set(data) - CONTEXT_NOTE_ALLOWED_FIELDS
        if unknown_fields:
            raise ValueError(
                "context_note proposed_data contains unsupported fields: "
                f"{sorted(unknown_fields)}"
            )

        for required in ("title", "body", "category"):
            if not data.get(required):
                raise ValueError(f"context_note proposed_data requires {required!r}")

        posture = data.get("posture")
        if not posture:
            raise ValueError("context_note proposed_data requires 'posture'")
        if posture not in CONTEXT_NOTE_POSTURE_VALUES:
            raise ValueError(
                f"Invalid context_note posture: {posture!r}. "
                f"Allowed values: {sorted(CONTEXT_NOTE_POSTURE_VALUES)}"
            )

        category = data.get("category")
        if category not in CONTEXT_NOTE_CATEGORY_VALUES:
            raise ValueError(
                f"Invalid context_note category: {category!r}. "
                f"Allowed values: {sorted(CONTEXT_NOTE_CATEGORY_VALUES)}"
            )

        sensitivity = data.get("sensitivity")
        if (
            sensitivity is not None
            and sensitivity not in CONTEXT_NOTE_SENSITIVITY_VALUES
        ):
            raise ValueError(
                f"Invalid context_note sensitivity: {sensitivity!r}. "
                f"Allowed values: {sorted(CONTEXT_NOTE_SENSITIVITY_VALUES)}"
            )

        if posture == "attributed_view" and not data.get("speaker_attribution"):
            raise ValueError(
                "context_note with posture='attributed_view' requires speaker_attribution"
            )

        linked_entities = data.get("linked_entities")
        if linked_entities is not None and not isinstance(linked_entities, list):
            raise ValueError(
                "context_note linked_entities must be a list when provided"
            )

    def _validate_person_detail_update(self):
        data = self.proposed_data
        unknown_fields = set(data) - PERSON_DETAIL_ALLOWED_TOP_LEVEL_FIELDS
        if unknown_fields:
            raise ValueError(
                "person_detail_update proposed_data contains unsupported top-level fields: "
                f"{sorted(unknown_fields)}"
            )

        if not data.get("person_id"):
            raise ValueError("person_detail_update proposed_data requires 'person_id'")

        fields = data.get("fields")
        if not isinstance(fields, dict) or not fields:
            raise ValueError(
                "person_detail_update proposed_data requires non-empty 'fields'"
            )

        unknown_profile_fields = set(fields) - PERSON_DETAIL_ALLOWED_FIELDS
        if unknown_profile_fields:
            raise ValueError(
                "person_detail_update fields contain unsupported keys: "
                f"{sorted(unknown_profile_fields)}"
            )


class V3Bundle(V3BaseModel):
    """Pass 2 bundle for reviewable proposals."""

    bundle_type: str
    target_matter_id: Optional[str] = None
    target_matter_title: Optional[str] = None
    proposed_matter: Optional[ProposedMatterData] = None
    confidence: float = Field(..., ge=0.0, le=1.0)
    rationale: str = Field(..., min_length=1)
    intelligence_notes: Optional[str] = None
    uncertainty_flags: list[str] = Field(default_factory=list)
    items: list[V3ProposalItem] = Field(..., min_length=1)

    @model_validator(mode="after")
    def validate_bundle(self):
        if self.bundle_type not in VALID_BUNDLE_TYPES:
            raise ValueError(
                f"Invalid bundle_type: {self.bundle_type!r}. Allowed values: {sorted(VALID_BUNDLE_TYPES)}"
            )

        if self.bundle_type == "matter" and not self.target_matter_id:
            raise ValueError("matter bundles require target_matter_id")

        if self.bundle_type == "standalone" and self.target_matter_id is not None:
            raise ValueError("standalone bundles cannot include target_matter_id")

        if self.bundle_type == "new_matter":
            if self.target_matter_id is not None:
                raise ValueError("new_matter bundles cannot include target_matter_id")
            if self.proposed_matter is None:
                raise ValueError("new_matter bundles require proposed_matter")
        elif self.proposed_matter is not None:
            raise ValueError("Only new_matter bundles may include proposed_matter")

        return self


class V3SuppressedObservation(V3BaseModel):
    observation_id: str = Field(..., min_length=1)
    observation_type: str
    observation_subtype: str
    description: str = Field(..., min_length=1)
    reason_noted: str = Field(..., min_length=1)
    candidate_item_type: Optional[str] = None
    candidate_fields: dict[str, Any] = Field(default_factory=dict)
    confidence_if_enabled: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    source_excerpt: Optional[str] = None
    source_segments: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_suppressed_types(self):
        if self.observation_type not in OBSERVATION_TYPE_VALUES:
            raise ValueError(
                f"Invalid observation_type: {self.observation_type!r}. "
                f"Allowed values: {sorted(OBSERVATION_TYPE_VALUES)}"
            )

        allowed_subtypes = OBSERVATION_SUBTYPE_MAP[self.observation_type]
        if self.observation_subtype not in allowed_subtypes:
            raise ValueError(
                f"Invalid observation_subtype {self.observation_subtype!r} for {self.observation_type!r}. "
                f"Allowed values: {sorted(allowed_subtypes)}"
            )

        if (
            self.candidate_item_type is not None
            and self.candidate_item_type not in VALID_ITEM_TYPES
        ):
            raise ValueError(
                f"Invalid candidate_item_type: {self.candidate_item_type!r}. "
                f"Allowed values: {sorted(VALID_ITEM_TYPES)}"
            )

        return self


class V3ExtractionOutput(V3BaseModel):
    """Pass 2 conservative reviewable output."""

    schema_version: str = PASS2_SCHEMA_VERSION
    communication_id: str = Field(..., min_length=1)
    extraction_summary: str = Field(..., min_length=1)
    routing_assessment: MatterRoutingAssessment
    bundles: list[V3Bundle] = Field(default_factory=list)
    suppressed_observations: list[V3SuppressedObservation] = Field(default_factory=list)
