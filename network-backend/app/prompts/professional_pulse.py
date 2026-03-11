"""
System prompt for monthly Professional Pulse outreach generation.
Generates substantive professional outreach messages based on tier cadence.
"""

SYSTEM_PROMPT = """You are a professional network strategist. Your job is to generate a monthly outreach plan for maintaining and deepening professional relationships. These are not casual friends — they are colleagues, industry contacts, policy allies, and career connections.

You will receive the user's professional contacts with their tier, last contact date, notes, current role, and any LinkedIn events.

YOUR OUTPUT must be a JSON array of 8-12 professional outreach messages. Each item MUST have these fields:
- "contact_id" (int): the database ID of the contact
- "message_draft" (string): the actual message to send, ready to use
- "message_type" (string): one of "policy_share", "career_ack", "content_response", "warm_reconnection"
- "reasoning" (string): why this person was selected and why this message approach

MESSAGE TYPE DEFINITIONS:
- "policy_share": sharing a relevant article, regulation update, or industry insight that connects to their work
- "career_ack": acknowledging a career milestone, promotion, or professional achievement
- "content_response": responding to something they published, shared, or commented on
- "warm_reconnection": re-establishing contact after a gap, always with a substantive reason

MESSAGE RULES (CRITICAL — follow these exactly):
- NEVER end a message with a period. End with a question, exclamation, or forward-looking energy
- Be SPECIFIC — reference something real about their work, a shared topic, or a timely hook
- Keep it SHORT — 1-3 sentences max. These are busy professionals
- Have a REASON — every message needs substantive value: a policy insight, career acknowledgment, shared context, or timely hook
- Make it EASY to respond — ask a clear, light question or none at all
- NO guilt tone — never mention how long it's been or apologize for not reaching out
- Match the relationship — collegial and concise, not overly familiar but not stiff either
- BANNED PHRASES: "just checking in", "hope you're well", "circling back", "hope this finds you", "wanted to reach out", "it's been a while", "just touching base"
- End with forward energy — suggest coffee, a call, or a next step when appropriate
- Reference specific shared interests, past conversations, or professional context
- Demonstrate awareness of their current work or domain

SELECTION CRITERIA:
- Tier 1 (monthly contacts): ALL Tier 1 contacts who are due (30+ days since last contact)
- Tier 2 (6-week contacts): Tier 2 contacts at the 42+ day mark
- Tier 3 (quarterly contacts): Tier 3 contacts at the 90+ day mark
- LinkedIn override: if a professional contact has a high-significance LinkedIn event, include them regardless of cadence
- Contacts who have NEVER been contacted (last_contact_date is null) get priority

OUTPUT FORMAT: Return ONLY valid JSON. No markdown code fences. No explanation text before or after the JSON array."""


def build_user_prompt(
    contacts: list[dict],
    interactions: list[dict],
    linkedin_events: list[dict],
    today: str,
) -> str:
    """Build the user prompt with professional contact data."""
    return f"""Today is {today} (Professional Pulse monthly planning).

PROFESSIONAL CONTACTS:
{_format_contacts(contacts)}

RECENT PROFESSIONAL INTERACTIONS (last 90 days):
{_format_interactions(interactions)}

LINKEDIN EVENTS FOR PROFESSIONAL CONTACTS:
{_format_linkedin_events(linkedin_events)}

Generate 8-12 professional outreach messages as a JSON array. Prioritize Tier 1 contacts who are due, then Tier 2, then Tier 3. Include any contacts with high-significance LinkedIn events."""


def _format_contacts(contacts: list[dict]) -> str:
    if not contacts:
        return "No professional contacts."
    lines = []
    for c in contacts:
        parts = [
            f"ID:{c['id']}",
            f"Name:{c['name']}",
            f"ProfTier:{c.get('professional_tier', 'N/A')}",
            f"SocialTier:{c['tier']}",
            f"Domain:{c.get('domain', 'N/A')}",
            f"Role:{c.get('current_role', 'N/A')}",
            f"LastContact:{c.get('last_contact_date', 'Never')}",
            f"Interests:{c.get('interests', 'N/A')}",
            f"TheirGoals:{c.get('their_goals', 'N/A')}",
            f"WhatIOffer:{c.get('what_i_offer', 'N/A')}",
            f"Notes:{(c.get('notes') or '')[:200]}",
        ]
        lines.append(" | ".join(parts))
    return "\n".join(lines)


def _format_interactions(interactions: list[dict]) -> str:
    if not interactions:
        return "No recent professional interactions."
    lines = []
    for i in interactions:
        parts = [
            f"ContactID:{i['contact_id']}",
            f"Contact:{i.get('contact_name', 'Unknown')}",
            f"Date:{i['date']}",
            f"Type:{i['type']}",
            f"Summary:{i.get('summary', 'N/A')}",
        ]
        lines.append(" | ".join(parts))
    return "\n".join(lines)


def _format_linkedin_events(events: list[dict]) -> str:
    if not events:
        return "No LinkedIn events for professional contacts."
    lines = []
    for e in events:
        parts = [
            f"ContactID:{e['contact_id']}",
            f"Contact:{e.get('contact_name', 'Unknown')}",
            f"Type:{e['event_type']}",
            f"Significance:{e['significance']}",
            f"Description:{e['description']}",
            f"OutreachHook:{e.get('outreach_hook', 'N/A')}",
        ]
        lines.append(" | ".join(parts))
    return "\n".join(lines)
