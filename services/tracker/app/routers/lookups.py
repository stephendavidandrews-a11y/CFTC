"""Lookup/enum endpoints for the tracker."""
from fastapi import APIRouter

router = APIRouter(prefix="/lookups", tags=["lookups"])

ENUMS = {
    "matter_type": [
        "rulemaking", "interpretive guidance", "no-action letter", "exemptive letter",
        "staff advisory", "other letter", "interagency coordination", "enforcement support",
        "congressional response", "speech / testimony / briefing prep", "litigation-sensitive issue",
        "personnel / management", "administrative / ethics / process", "industry inquiry",
        "international matter", "regulatory review", "prospective policy", "other",
    ],
    "matter_status": [
        "new intake", "framing issue", "research in progress", "draft in progress", "internal review",
        "client review", "leadership review", "external coordination", "awaiting decision",
        "awaiting comments", "parked / monitoring", "closed",
    ],
    "matter_priority": [
        "critical this week", "important this month", "strategic / slow burn", "monitoring only",
    ],
    "matter_sensitivity": [
        "routine", "internal only", "leadership-sensitive", "deliberative / predecisional",
        "enforcement-sensitive", "congressional-sensitive",
    ],
    "risk_level": ["low", "medium", "high", "critical"],
    "boss_involvement_level": [
        "no boss involvement needed", "keep boss informed", "boss review required",
        "boss decision required", "boss will present / speak",
    ],
    "regulatory_stage": [
        "concept", "drafting", "proposed", "comment_period", "final_review",
        "published", "effective", "withdrawn", "long_term",
    ],
    "unified_agenda_priority": [
        "economically_significant", "significant", "substantive_nonsignificant", "routine", "info_only",
    ],
    "task_status": ["not started", "in progress", "waiting on others", "needs review", "done", "deferred"],
    "task_mode": ["action", "waiting", "decision", "follow-up", "reading", "delegated"],
    "task_type": [
        "research issue", "draft memo", "review markup", "prepare talking points",
        "schedule meeting", "get clearance", "follow up with client", "redline document",
        "produce options memo", "send readout", "coordinate with agency partner", "other",
    ],
    "task_priority": ["critical", "high", "normal", "low"],
    "deadline_type": ["hard", "soft"],
    "meeting_type": [
        "internal working meeting", "leadership meeting", "client meeting", "interagency meeting",
        "industry meeting", "Hill meeting", "briefing", "check-in", "commissioner office", "other",
    ],
    "meeting_role": [
        "chair", "presenter", "attendee", "decision-maker", "note-taker", "guest",
    ],
    "attendance_status": ["invited", "attended", "declined", "tentative"],
    "position_strength": ["tentative", "qualified", "firm"],
    "meeting_matter_relationship_type": [
        "primary topic", "secondary topic", "status update", "decision point", "coordination",
    ],
    "document_type": [
        "memo", "briefing paper", "talking points", "redline", "regulatory text",
        "comment summary", "clearance memo", "email draft", "hearing prep", "FAQ / Q&A",
        "interagency paper", "other",
    ],
    "document_status": [
        "not started", "drafting", "under review", "awaiting comments",
        "finalized", "sent", "superseded", "archived",
    ],
    "review_role": [
        "drafter", "primary reviewer", "legal reviewer", "client reviewer",
        "leadership reviewer", "clearance reviewer", "final approver",
    ],
    "review_status": [
        "not set", "pending", "in review", "comments returned", "approved", "declined",
    ],
    "decision_type": [
        "boss decision", "leadership decision", "client decision",
        "interagency decision", "legal interpretation", "process decision",
    ],
    "decision_status": ["pending", "under consideration", "made", "deferred", "no longer needed"],
    "organization_type": [
        "CFTC office", "CFTC division", "Commissioner office", "Federal agency",
        "White House / OMB", "Congressional office", "Regulated entity", "Exchange",
        "Clearinghouse", "Trade association", "Outside counsel",
        "Inspector General / auditor", "Other",
    ],
    "relationship_category": [
        "Boss", "Leadership", "Direct report", "OGC peer", "Internal client",
        "Commissioner office", "Partner agency", "Hill", "Outside party",
    ],
    "relationship_lane": [
        "Decision-maker", "Recommender", "Drafter", "Blocker", "Influencer", "FYI only",
    ],
    "next_interaction_type": [
        "briefing", "follow-up", "check-in", "escalation", "decision request",
        "relationship maintenance", "outreach", "coordination", "other",
    ],
    "matter_role": [
        "lead attorney", "supervisor", "requesting stakeholder", "substantive client",
        "reviewing stakeholder", "leadership stakeholder", "external partner",
        "Hill stakeholder", "outside party", "subject matter contributor", "FYI only",
    ],
    "engagement_level": ["lead", "core", "consulted", "informed", "escalation only"],
    "organization_role": [
        "requesting office", "client office", "reviewing office", "lead office",
        "partner agency", "counterparty", "Hill office", "affected office", "outside party", "FYI",
    ],
    "update_type": [
        "status update", "meeting readout", "document milestone", "decision made",
        "blocker identified", "deadline changed", "escalation", "closure note",
    ],
    "task_dependency_type": [
        "cannot start until complete", "should follow", "needs input from", "parallel but linked",
    ],
    "matter_dependency_type": [
        "legal dependency", "policy dependency", "sequencing dependency",
        "approval dependency", "external dependency", "shared deadline", "related risk",
    ],
    "comment_period_type": ["original", "extension", "reopening", "supplemental"],
    "cba_status": ["not_started", "in_progress", "under_review", "completed"],
    "task_update_type": [
        "status update", "reassigned", "waiting state changed", "due date changed",
        "note added", "completion note", "escalation", "blocker identified",
    ],
    "source": ["manual", "sync", "sauron", "api", "import"],
}

# Aliases for backward compatibility — frontend uses short names for some enums
ENUM_ALIASES = {
    "priority": "matter_priority",
    "sensitivity": "matter_sensitivity",
    "boss_involvement": "boss_involvement_level",
}

@router.get("/enums")
async def get_all_enums():
    """Return all enum values. Used by Sauron and other integrations for validation."""
    return ENUMS

@router.get("/enums/{enum_name}")
async def get_enum(enum_name: str):
    """Return values for a specific enum."""
    # Check direct match first, then aliases
    resolved = ENUM_ALIASES.get(enum_name, enum_name)
    if resolved not in ENUMS:
        return {"error": f"Unknown enum: {enum_name}"}
    return {enum_name: ENUMS[resolved]}
