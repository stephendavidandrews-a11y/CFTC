"""
Pydantic models for request/response schemas across all Network entities.
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from datetime import date, datetime
from enum import Enum


# ── Enums ──────────────────────────────────────────────────────────────

class TierEnum(str, Enum):
    cornerstone = "Cornerstone"
    developing = "Developing"
    new = "New"
    dormant = "Dormant"


class ContactType(str, Enum):
    social = "social"
    professional = "professional"


class ProfessionalTier(str, Enum):
    tier_1 = "Tier 1"
    tier_2 = "Tier 2"
    tier_3 = "Tier 3"


class PlanType(str, Enum):
    social_thursday = "social_thursday"
    professional_pulse = "professional_pulse"
    happy_hour_invite = "happy_hour_invite"
    happy_hour_reminder = "happy_hour_reminder"
    ad_hoc_due = "ad_hoc_due"


class DomainEnum(str, Enum):
    senate_hill = "Senate/Hill"
    friend = "Friend"
    industry_policy = "Industry/Policy"
    social = "Social"
    military = "Military"
    faith = "Faith"
    government_executive = "Government/Executive"
    policy_issue = "Policy/Issue-Specific"
    media_press = "Media/Press"
    law_enforcement = "Law Enforcement"


class InteractionType(str, Enum):
    happy_hour = "Happy Hour"
    one_on_one = "1-on-1"
    dinner = "Dinner"
    coffee = "Coffee"
    text_call = "Text/Call"
    group_activity = "Group Activity"
    intro_made = "Intro Made"
    event = "Event"


class WhoInitiated(str, Enum):
    me = "Me"
    them = "Them"
    mutual = "Mutual"


class OutreachMessageType(str, Enum):
    weekend_checkin = "weekend_checkin"
    happy_hour_invite = "happy_hour_invite"
    connector_invite = "connector_invite"
    life_event = "life_event"
    follow_up = "follow_up"
    intro = "intro"
    linkedin_congrats = "linkedin_congrats"
    linkedin_content = "linkedin_content"
    linkedin_milestone = "linkedin_milestone"
    open_loop = "open_loop"
    policy_share = "policy_share"
    career_ack = "career_ack"
    content_response = "content_response"
    warm_reconnection = "warm_reconnection"


class OutreachStatus(str, Enum):
    pending = "pending"
    approved = "approved"
    sent = "sent"
    skipped = "skipped"


class RSVPStatus(str, Enum):
    invited = "invited"
    confirmed = "confirmed"
    declined = "declined"
    no_response = "no_response"
    attended = "attended"


class AttendeeRole(str, Enum):
    anchor = "anchor"
    new_edge = "new_edge"
    wildcard = "wildcard"
    connector_plus_one = "connector_plus_one"


class LinkedInEventType(str, Enum):
    job_change = "job_change"
    promotion = "promotion"
    post = "post"
    article = "article"
    work_anniversary = "work_anniversary"
    life_event = "life_event"
    event_mention = "event_mention"
    general_activity = "general_activity"


class SignificanceLevel(str, Enum):
    high = "high"
    medium = "medium"
    low = "low"


# ── Contact Schemas ────────────────────────────────────────────────────

class ContactCreate(BaseModel):
    name: str
    phone: Optional[str] = None
    email: Optional[str] = None
    how_we_met: Optional[str] = None
    current_role: Optional[str] = None
    domain: Optional[DomainEnum] = None
    tier: TierEnum = TierEnum.new
    is_super_connector: Optional[bool] = False
    relationship_status: Optional[str] = None
    interests: Optional[str] = None
    their_goals: Optional[str] = None
    what_i_offer: Optional[str] = None
    activity_prefs: Optional[str] = None
    next_action: Optional[str] = None
    notes: Optional[str] = None
    linkedin_url: Optional[str] = None
    linkedin_headline: Optional[str] = None
    contact_type: Optional[ContactType] = ContactType.social
    professional_tier: Optional[ProfessionalTier] = None

    @field_validator("professional_tier", mode="before")
    @classmethod
    def empty_str_to_none_pt(cls, v):
        if v == "":
            return None
        return v

    @field_validator("domain", mode="before")
    @classmethod
    def empty_str_to_none_domain(cls, v):
        if v == "":
            return None
        return v


class ContactUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    how_we_met: Optional[str] = None
    current_role: Optional[str] = None
    domain: Optional[DomainEnum] = None
    tier: Optional[TierEnum] = None
    is_super_connector: Optional[bool] = None
    relationship_status: Optional[str] = None
    interests: Optional[str] = None
    their_goals: Optional[str] = None
    what_i_offer: Optional[str] = None
    activity_prefs: Optional[str] = None
    next_action: Optional[str] = None
    notes: Optional[str] = None
    linkedin_url: Optional[str] = None
    linkedin_headline: Optional[str] = None
    contact_type: Optional[ContactType] = None
    professional_tier: Optional[ProfessionalTier] = None

    @field_validator("professional_tier", mode="before")
    @classmethod
    def empty_str_to_none_pt(cls, v):
        if v == "":
            return None
        return v

    @field_validator("domain", mode="before")
    @classmethod
    def empty_str_to_none_domain(cls, v):
        if v == "":
            return None
        return v


class ContactResponse(BaseModel):
    id: int
    name: str
    phone: Optional[str] = None
    email: Optional[str] = None
    how_we_met: Optional[str] = None
    current_role: Optional[str] = None
    domain: Optional[str] = None
    tier: str
    is_super_connector: bool = False
    relationship_status: Optional[str] = None
    interests: Optional[str] = None
    their_goals: Optional[str] = None
    what_i_offer: Optional[str] = None
    activity_prefs: Optional[str] = None
    last_contact_date: Optional[str] = None
    next_action: Optional[str] = None
    notes: Optional[str] = None
    linkedin_url: Optional[str] = None
    linkedin_headline: Optional[str] = None
    linkedin_last_checked: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    contact_type: Optional[str] = "social"
    professional_tier: Optional[str] = None


class ContactDetailResponse(ContactResponse):
    interactions: List["InteractionResponse"] = []


# ── Interaction Schemas ────────────────────────────────────────────────

class InteractionCreate(BaseModel):
    contact_id: int
    date: date
    type: InteractionType
    who_initiated: Optional[WhoInitiated] = None
    summary: Optional[str] = None
    open_loops: Optional[str] = None
    follow_up_date: Optional[date] = None


class InteractionResponse(BaseModel):
    id: int
    contact_id: int
    date: str
    type: str
    who_initiated: Optional[str] = None
    summary: Optional[str] = None
    open_loops: Optional[str] = None
    follow_up_date: Optional[str] = None
    contact_name: Optional[str] = None


# ── Outreach Plan Schemas ──────────────────────────────────────────────

class OutreachPlanCreate(BaseModel):
    week_of: date
    contact_id: int
    message_draft: str
    reasoning: Optional[str] = None
    message_type: Optional[OutreachMessageType] = None
    status: OutreachStatus = OutreachStatus.pending
    plan_type: Optional[PlanType] = PlanType.social_thursday


class OutreachPlanUpdate(BaseModel):
    message_draft: Optional[str] = None
    reasoning: Optional[str] = None
    message_type: Optional[OutreachMessageType] = None
    status: Optional[OutreachStatus] = None


class OutreachPlanResponse(BaseModel):
    id: int
    week_of: str
    contact_id: int
    message_draft: str
    reasoning: Optional[str] = None
    message_type: Optional[str] = None
    status: str
    sent_at: Optional[str] = None
    contact_name: Optional[str] = None
    contact_phone: Optional[str] = None
    plan_type: Optional[str] = "social_thursday"


# ── Happy Hour Schemas ─────────────────────────────────────────────────

class AttendeeCreate(BaseModel):
    contact_id: int
    role: Optional[AttendeeRole] = None
    rsvp_status: RSVPStatus = RSVPStatus.invited


class AttendeeUpdate(BaseModel):
    role: Optional[AttendeeRole] = None
    rsvp_status: Optional[RSVPStatus] = None
    brought_guest: Optional[bool] = None


class AttendeeResponse(BaseModel):
    id: int
    happy_hour_id: int
    contact_id: int
    role: Optional[str] = None
    rsvp_status: str
    brought_guest: bool = False
    contact_name: Optional[str] = None


class HappyHourCreate(BaseModel):
    date: date
    venue_id: Optional[int] = None
    theme: Optional[str] = None
    sonnet_reasoning: Optional[str] = None
    attendees: Optional[List[AttendeeCreate]] = []


class HappyHourUpdate(BaseModel):
    date: Optional[str] = None
    venue_id: Optional[int] = None
    theme: Optional[str] = None
    sonnet_reasoning: Optional[str] = None


class HappyHourResponse(BaseModel):
    id: int
    date: str
    venue_id: Optional[int] = None
    theme: Optional[str] = None
    sonnet_reasoning: Optional[str] = None
    venue_name: Optional[str] = None


class HappyHourDetailResponse(HappyHourResponse):
    attendees: List[AttendeeResponse] = []


# ── Venue Schemas ──────────────────────────────────────────────────────

class VenueCreate(BaseModel):
    name: str
    type: Optional[str] = None
    neighborhood: Optional[str] = None
    vibe: Optional[str] = None
    best_for: Optional[str] = None
    price_range: Optional[str] = None
    notes: Optional[str] = None


class VenueUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None
    neighborhood: Optional[str] = None
    vibe: Optional[str] = None
    best_for: Optional[str] = None
    price_range: Optional[str] = None
    notes: Optional[str] = None


class VenueResponse(BaseModel):
    id: int
    name: str
    type: Optional[str] = None
    neighborhood: Optional[str] = None
    vibe: Optional[str] = None
    best_for: Optional[str] = None
    price_range: Optional[str] = None
    notes: Optional[str] = None


# ── Intro Schemas ──────────────────────────────────────────────────────

class IntroCreate(BaseModel):
    person_a_id: int
    person_b_id: int
    date: date
    context: Optional[str] = None
    outcome: Optional[str] = None


class IntroUpdate(BaseModel):
    outcome: Optional[str] = None


class IntroResponse(BaseModel):
    id: int
    person_a_id: int
    person_b_id: int
    date: str
    context: Optional[str] = None
    outcome: Optional[str] = None
    person_a_name: Optional[str] = None
    person_b_name: Optional[str] = None


# ── LinkedIn Event Schemas ─────────────────────────────────────────────

class LinkedInEventCreate(BaseModel):
    contact_id: int
    detected_date: date
    event_type: LinkedInEventType
    significance: SignificanceLevel = SignificanceLevel.medium
    description: str
    outreach_hook: Optional[str] = None
    opportunity_flag: Optional[str] = None


class LinkedInEventResponse(BaseModel):
    id: int
    contact_id: int
    detected_date: str
    event_type: str
    significance: str
    description: str
    outreach_hook: Optional[str] = None
    opportunity_flag: Optional[str] = None
    used_in_outreach: bool = False
    dismissed: bool = False
    contact_name: Optional[str] = None


# ── AI Intelligence Response Schemas ──────────────────────────────────

class OutreachGenerateResponse(BaseModel):
    """Response from Thursday outreach or Professional Pulse generation."""
    plans: List[OutreachPlanResponse]
    reasoning: Optional[str] = None


class HappyHourSuggestion(BaseModel):
    """A single happy hour invitee suggestion from Sonnet."""
    contact_id: int
    contact_name: str
    role: str  # anchor, new_edge, wildcard, connector_plus_one
    reasoning: str


class HappyHourSuggestResponse(BaseModel):
    """Response from happy hour group suggestion."""
    suggestions: List[HappyHourSuggestion]
    theme_suggestion: Optional[str] = None
    group_reasoning: str


class FollowUpAnalysis(BaseModel):
    """Response from post-interaction follow-up analysis."""
    open_loops: List[str]
    new_interests: List[str]
    intro_suggestions: List[dict]
    suggested_follow_up_date: Optional[str] = None


class LinkedInScanResult(BaseModel):
    """Response from LinkedIn scan operation."""
    contacts_scanned: int
    events_detected: int
    high_significance: int
    events: List[LinkedInEventResponse]


class IntroSuggestion(BaseModel):
    """A single intro recommendation from Sonnet."""
    person_a_id: int
    person_a_name: str
    person_b_id: int
    person_b_name: str
    reasoning: str
    shared_context: Optional[str] = None


class IntroSuggestResponse(BaseModel):
    """Response from intro suggestion endpoint."""
    suggestions: List[IntroSuggestion]


# ── Scheduler / Notification Schemas ──────────────────────────────────

class NotificationLogResponse(BaseModel):
    """A logged notification that was sent."""
    id: int
    job_name: str
    sent_at: str
    title: str
    message: Optional[str] = None
    plans_generated: int = 0


class SchedulerJobStatus(BaseModel):
    """Status of a single scheduler job."""
    job_name: str
    enabled: bool = True
    cron: str
    last_run: Optional[str] = None
    next_run: Optional[str] = None


class SchedulerStatusResponse(BaseModel):
    """Overall scheduler status."""
    running: bool
    jobs: List[SchedulerJobStatus]


# Rebuild models for forward references
ContactDetailResponse.model_rebuild()
