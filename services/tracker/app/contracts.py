"""Canonical tracker contract for enums, writable tables, and batch behavior.

See ../CONTRACT.md for the human-facing change guide.
"""

from __future__ import annotations


TRACKER_SCHEMA_VERSION = "1.2.0"


ENUMS = {
    "matter_type": [
        "rulemaking", "guidance", "enforcement", "congressional",
        "briefing", "administrative", "inquiry", "other",
    ],
    "matter_status": [
        "active", "paused", "closed",
    ],
    "matter_priority": [
        "critical this week",
        "important this month",
        "strategic / slow burn",
        "monitoring only",
    ],
    "matter_sensitivity": [
        "routine",
        "internal only",
        "leadership-sensitive",
        "deliberative / predecisional",
        "enforcement-sensitive",
        "congressional-sensitive",
    ],


    "regulatory_stage": [
        "concept",
        "drafting",
        "proposed",
        "comment_period",
        "final_review",
        "published",
        "effective",
        "withdrawn",
        "long_term",
        "petition_received",
        "interpretive_release",
    ],
    "unified_agenda_priority": [
        "economically_significant",
        "significant",
        "substantive_nonsignificant",
        "routine",
        "info_only",
    ],
    "task_status": [
        "not started",
        "in progress",
        "waiting on others",
        "needs review",
        "done",
        "deferred",
    ],
    "task_mode": ["action", "follow_up", "monitoring"],
    "task_type": [
        "research issue",
        "draft memo",
        "review markup",
        "prepare talking points",
        "schedule meeting",
        "get clearance",
        "follow up with client",
        "redline document",
        "produce options memo",
        "send readout",
        "coordinate with agency partner",
        "other",
    ],
    "task_priority": ["critical", "high", "normal", "low"],
    "deadline_type": ["hard", "soft", "internal"],
    "meeting_type": [
        "internal working meeting",
        "leadership meeting",
        "client meeting",
        "interagency meeting",
        "industry meeting",
        "Hill meeting",
        "briefing",
        "check-in",
        "commissioner office",
        "other",
    ],
    "meeting_role": [
        "chair",
        "presenter",
        "attendee",
        "decision-maker",
        "note-taker",
        "guest",
    ],
    "attendance_status": ["invited", "attended", "declined", "tentative"],
    "position_strength": ["tentative", "qualified", "firm"],
    "meeting_matter_relationship_type": [
        "primary topic",
        "secondary topic",
        "status update",
        "decision point",
        "coordination",
    ],
    "document_type": [
        "rulemaking_text",
        "legal_memo",
        "options_memo",
        "comment_letter",
        "testimony",
        "talking_points",
        "briefing_paper",
        "correspondence",
        "report",
        "no_action_letter",
        "other",
    ],
    "document_status": [
        "not started",
        "drafting",
        "internal_review",
        "client_review",
        "leadership_review",
        "clearance",
        "final",
        "sent",
        "archived",
    ],
    "review_role": [
        "drafter",
        "primary reviewer",
        "legal reviewer",
        "client reviewer",
        "leadership reviewer",
        "clearance reviewer",
        "final approver",
    ],
    "review_status": [
        "not set",
        "pending",
        "in review",
        "comments returned",
        "approved",
        "declined",
    ],
    "decision_type": [
        "policy",
        "legal",
        "resource",
        "timing",
        "personnel",
        "procedural",
    ],
    "decision_status": [
        "pending",
        "under consideration",
        "made",
        "deferred",
        "no longer needed",
    ],
    "organization_type": [
        "CFTC office",
        "CFTC division",
        "Commissioner office",
        "Federal agency",
        "White House / OMB",
        "Congressional office",
        "Regulated entity",
        "Exchange",
        "Clearinghouse",
        "Trade association",
        "Outside counsel",
        "Inspector General / auditor",
        "Other",
    ],
    "relationship_category": [
        "Boss",
        "Leadership",
        "Direct report",
        "Indirect report",
        "OGC peer",
        "Internal client",
        "Commissioner office",
        "Partner agency",
        "Hill",
        "Outside party",
    ],
    "next_interaction_type": [
        "briefing",
        "follow-up",
        "check-in",
        "escalation",
        "decision request",
        "relationship maintenance",
        "outreach",
        "coordination",
        "other",
    ],
    "matter_role": [
        "lead attorney",
        "supervisor",
        "requesting stakeholder",
        "substantive client",
        "reviewing stakeholder",
        "leadership stakeholder",
        "external partner",
        "Hill stakeholder",
        "outside party",
        "subject matter contributor",
        "FYI only",
    ],
    "engagement_level": ["lead", "core", "consulted", "informed", "escalation only"],
    "organization_role": [
        "requesting office",
        "client office",
        "reviewing office",
        "lead office",
        "partner agency",
        "counterparty",
        "Hill office",
        "affected office",
        "outside party",
        "FYI",
    ],
    "update_type": [
        "status update",
        "meeting readout",
        "document milestone",
        "decision made",
        "blocker identified",
        "deadline changed",
        "escalation",
        "closure note",
    ],
    "task_dependency_type": [
        "cannot start until complete",
        "should follow",
        "needs input from",
        "parallel but linked",
    ],
    "matter_dependency_type": [
        "legal dependency",
        "policy dependency",
        "sequencing dependency",
        "approval dependency",
        "external dependency",
        "shared deadline",
        "related risk",
        "supersedes",
        "joint_action",
    ],
    "comment_period_type": [
        "original",
        "extension",
        "reopening",
        "supplemental",
        "anprm",
        "nprm",
        "proposed_order",
        "concept_release",
        "final_rule_with_comment",
        "pra_60_day",
        "pra_30_day",
    ],
    "cba_status": ["not_started", "in_progress", "under_review", "completed"],
    "task_update_type": [
        "status update",
        "reassigned",
        "waiting state changed",
        "due date changed",
        "note added",
        "completion note",
        "escalation",
        "blocker identified",
    ],
    "source": ["manual", "sync", "sauron", "api", "import", "ai", "federal_register"],
    # ---- comment_topics enums ----
    "comment_topic_area": [
        "core_principles",
        "public_interest",
        "market_structure",
        "disclosure",
        "documentation",
        "registration",
        "special_entity",
        "clearing",
        "margin",
        "reporting",
        "surveillance",
        "position_limits",
        "cost_benefit",
        "definitional",
        "jurisdictional",
        "technology",
        "consumer_protection",
        "political_contributions",
        "procedural",
        "other",
    ],
    "comment_topic_position_status": [
        "open",
        "research",
        "draft_position",
        "under_review",
        "final",
        "deferred",
        "not_applicable",
    ],
    "comment_topic_source_document_type": [
        "anprm",
        "nprm",
        "final_rule_with_comment",
        "proposed_order",
        "concept_release",
        "interpretive_release",
        "guidance",
        "external_rulemaking",
    ],
    # ---- policy_directives enums ----
    "directive_source_document_type": [
        "executive_order",
        "pwg_report",
        "congressional_mandate",
        "statutory_requirement",
        "gao_recommendation",
        "ig_finding",
        "fsoc_recommendation",
        "interagency_agreement",
        "chairman_directive",
        "testimony_commitment",
        "chairman_speech",
        "other",
    ],
    "directive_priority_tier": [
        "immediate_action",
        "priority_guidance",
        "possible_regulation",
        "possible_legislation",
        "longer_term",
        "other",
    ],
    "directive_responsible_entity": [
        "cftc",
        "sec",
        "cftc_and_sec",
        "treasury",
        "occ",
        "fdic",
        "ncua",
        "fincen",
        "congress",
        "multiple_agencies",
        "other",
    ],
    "directive_ogc_role": [
        "drafter",
        "reviewer",
        "advisor",
        "commenter",
        "monitoring",
        "not_involved",
    ],
    "directive_implementation_status": [
        "not_started",
        "scoping",
        "in_progress",
        "partially_implemented",
        "implemented",
        "deferred",
        "not_applicable",
    ],
    "directive_matter_relationship_type": [
        "implements",
        "partially_addresses",
        "related_to",
        "supersedes",
    ],
    "directive_document_relationship_type": [
        "references",
        "implements",
        "supersedes",
        "withdraws",
        "amends",
    ],

    # ---- matter schema v2 enums ----
    "rulemaking_workflow_status": [
        "concept", "drafting", "cba_development", "internal_review",
        "client_review", "chairman_review", "commission_review",
        "ofr_submission", "comment_analysis", "final_drafting",
        "published", "effective",
    ],
    "guidance_workflow_status": [
        "request_received", "framing", "drafting", "internal_review",
        "division_review", "front_office_review", "issued",
        "amended", "withdrawn",
    ],
    "enforcement_workflow_status": [
        "intake", "analysis", "drafting", "review",
        "delivered", "ongoing_support",
    ],
    "instrument_type": [
        "no_action", "interpretive", "exemptive_letter",
        "exemptive_order", "staff_advisory", "other_letter",
    ],
    "enforcement_legal_issue_type": [
        "statutory_interpretation", "regulatory_interpretation",
        "jurisdictional", "penalty_authority", "settlement_terms",
        "litigation_support", "amicus", "other",
    ],
    "enforcement_support_type": [
        "legal_analysis", "draft_review", "expert_consultation",
        "testimony_support", "brief_drafting", "other",
    ],
    "enforcement_litigation_stage": [
        "investigation", "pre_complaint", "litigation",
        "settlement", "post_judgment", "appeal",
    ],
    "interagency_role": [
        "lead", "co_lead", "commenter", "observer", "parallel_rule",
    ],
    "petition_disposition": [
        "granted", "denied", "deferred", "pending",
    ],
    "review_trigger": [
        "executive_order", "court_decision", "internal_initiative",
        "congressional_request", "sunset_provision",
    ],
    "regulatory_id_type": [
        "fr_citation", "rin", "cfr_part", "docket_number",
        "stage1_doc_id", "letter_number",
    ],
    "regulatory_id_relationship": [
        "primary", "related", "under_review", "amends", "supersedes",
    ],
}


ENUM_ALIASES = {
    "priority": "matter_priority",
    "sensitivity": "matter_sensitivity",
}


AI_WRITABLE_TABLES = (
    "organizations",
    "people",
    "matters",
    "tasks",
    "meetings",
    "meeting_participants",
    "meeting_matters",
    "documents",
    "document_files",
    "decisions",
    "matter_people",
    "matter_organizations",
    "matter_updates",
    "context_notes",
    "context_note_links",
    "person_profiles",
    "comment_topics",
    "comment_questions",
    "rulemaking_comment_periods",
    "rulemaking_publication_status",
    "directive_research_notes",
    "policy_directives",
    "directive_matters",
    # Matter schema v2 extension tables
    "matter_rulemaking",
    "matter_guidance",
    "matter_enforcement",
    "matter_regulatory_ids",
)


BATCH_DELETE_ALLOWED_TABLES = (
    "matter_people",
    "matter_organizations",
    "meeting_participants",
    "meeting_matters",
    "matter_updates",
    "context_note_links",
    "comment_topics",
    "comment_questions",
    "directive_matters",
    "directive_documents",
    "directive_research_notes",
    "policy_directives",
    "directive_matters",
)


BATCH_SOFT_DELETE_TABLES = {
    "organizations": ("is_active", 0),
    "people": ("is_active", 0),
    "matters": ("status", "closed"),
    "tasks": ("status", "deferred"),
    "meetings": None,
    "documents": ("status", "archived"),
    "decisions": ("status", "no longer needed"),
    "context_notes": ("is_active", 0),
}


BATCH_UPSERT_RULES = {
    "person_profiles": ("person_id",),
    "rulemaking_publication_status": ("matter_id",),
    "matter_rulemaking": ("matter_id",),
    "matter_guidance": ("matter_id",),
    "matter_enforcement": ("matter_id",),
}


AI_WRITABLE_ENUM_COLUMNS = {
    "organizations": {
        "organization_type": "organization_type",
        "source": "source",
    },
    "people": {
        "relationship_category": "relationship_category",
        "next_interaction_type": "next_interaction_type",
        "source": "source",
    },
    "matters": {
        "matter_type": "matter_type",
        "status": "matter_status",
        "priority": "matter_priority",
        "sensitivity": "matter_sensitivity",
        "source": "source",
    },
    "tasks": {
        "task_type": "task_type",
        "status": "task_status",
        "task_mode": "task_mode",
        "priority": "task_priority",
        "deadline_type": "deadline_type",
        "source": "source",
    },
    "meetings": {
        "meeting_type": "meeting_type",
        "source": "source",
    },
    "meeting_participants": {
        "meeting_role": "meeting_role",
        "attendance_status": "attendance_status",
        "position_strength": "position_strength",
    },
    "meeting_matters": {
        "relationship_type": "meeting_matter_relationship_type",
    },
    "documents": {
        "document_type": "document_type",
        "status": "document_status",
        "source": "source",
    },
    "decisions": {
        "decision_type": "decision_type",
        "status": "decision_status",
        "source": "source",
    },
    "matter_people": {
        "matter_role": "matter_role",
        "engagement_level": "engagement_level",
    },
    "matter_organizations": {
        "organization_role": "organization_role",
    },
    "matter_updates": {
        "update_type": "update_type",
    },
    "context_notes": {
        "source": "source",
    },
    "comment_topics": {
        "topic_area": "comment_topic_area",
        "position_status": "comment_topic_position_status",
        "source_document_type": "comment_topic_source_document_type",
        "priority": "task_priority",
        "deadline_type": "deadline_type",
        "source": "source",
    },
    "rulemaking_comment_periods": {
        "comment_period_type": "comment_period_type",
    },
    "comment_questions": {
        "source": "source",
    },
    "policy_directives": {
        "implementation_status": "directive_implementation_status",
        "source_document_type": "directive_source_document_type",
        "responsible_entity": "directive_responsible_entity",
        "priority_tier": "directive_priority_tier",
        "ogc_role": "directive_ogc_role",
        "source": "source",
    },
    "directive_matters": {
        "relationship_type": "directive_matter_relationship_type",
    },

    "matter_rulemaking": {
        "workflow_status": "rulemaking_workflow_status",
        "interagency_role": "interagency_role",
        "petition_disposition": "petition_disposition",
        "review_trigger": "review_trigger",
    },
    "matter_guidance": {
        "instrument_type": "instrument_type",
        "workflow_status": "guidance_workflow_status",
    },
    "matter_enforcement": {
        "legal_issue_type": "enforcement_legal_issue_type",
        "support_type": "enforcement_support_type",
        "litigation_stage": "enforcement_litigation_stage",
        "workflow_status": "enforcement_workflow_status",
    },
    "matter_regulatory_ids": {
        "id_type": "regulatory_id_type",
        "relationship": "regulatory_id_relationship",
    },
}


def get_enum_values(enum_name: str) -> list[str]:
    """Return canonical values for an enum or alias name."""
    resolved = ENUM_ALIASES.get(enum_name, enum_name)
    return ENUMS[resolved]


def is_valid_enum_value(enum_name: str, value: str) -> bool:
    """Return True when the value belongs to the canonical enum set."""
    return value in get_enum_values(enum_name)
