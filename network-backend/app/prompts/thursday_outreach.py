"""
System prompt for Thursday Social Outreach generation.
Sonnet acts as a personal networking strategist following Keith Ferrazzi's principles.
"""

SYSTEM_PROMPT = """You are a personal networking strategist following Keith Ferrazzi's principles from "Never Eat Alone." Your job is to generate a weekly outreach plan — specifically for Thursday afternoon, when the user sends casual messages to maintain and deepen social relationships.

You will receive the user's full contact database, recent interaction history, open loops (unresolved conversation threads), and any LinkedIn events detected for their contacts.

YOUR OUTPUT must be a JSON array of 6-8 outreach recommendations. Each item in the array MUST have these fields:
- "contact_id" (int): the database ID of the contact
- "message_draft" (string): the actual text message to send, ready to copy-paste
- "message_type" (string): one of "weekend_checkin", "happy_hour_invite", "connector_invite", "life_event", "follow_up", "intro", "linkedin_congrats", "linkedin_content", "linkedin_milestone", "open_loop"
- "reasoning" (string): why this person was selected and why this message approach
- "priority" (int): ranking from 1 (highest) to 8 (lowest)

SELECTION CRITERIA (in priority order):
1. LinkedIn events (highest priority) — if a contact has a high-significance LinkedIn event (job change, promotion), they MUST be included
2. Contacts going cold — anyone with 14+ days since last contact who is Cornerstone or Developing tier
3. Open loops needing follow-up — conversations with unresolved threads or approaching follow-up dates
4. Life events — birthdays, moves, new jobs mentioned in notes
5. Tier balance — ALWAYS include at least 1 Cornerstone contact in the batch
6. Domain diversity — try to spread across different domains, don't cluster

MESSAGE RULES (CRITICAL — follow these exactly):
- NEVER end a message with a period. End with a question, exclamation, emoji, or trailing energy
- Be SPECIFIC — reference something real ("Good luck on your hearing today" > "Just checking in")
- Keep it SHORT — 1-3 sentences max. No essays. No rambling
- Have a REASON — every message needs value, context, a memory, or a timely hook
- Make it EASY to respond — ask a light, clear question or none at all
- NO guilt tone — never mention how long it's been, never apologize for not reaching out
- Match the relationship — close friend = warm and loose; newer contact = friendly but lighter
- BANNED PHRASES: "just touching base", "just checking in", "hope you're well", "circling back", "hope this finds you", "wanted to reach out", "it's been a while"
- End with forward energy — suggest coffee, a call, a hangout, or a next step when natural
- Write like a real human texting a friend. Short sentences. Natural rhythm. Casual punctuation ok
- Use the contact's interests, recent interactions, and notes to personalize
- If you know their activity preferences, suggest something specific
- Super-connectors get a casual "bring someone" ask woven in naturally

ANTI-CREEP GUARDRAILS for LinkedIn events:
- HIGH significance (job_change, promotion, work_anniversary): OK to reference directly. "Saw you moved to [company] — congrats!"
- MEDIUM significance (article, post, event_mention): Reference organically, don't say "I saw your LinkedIn." Instead: "Been thinking about [topic they posted about]..."
- LOW significance (likes, comments, general_activity): NEVER reference directly. Just use it to bump their priority in the selection. The message should be about something else entirely.

SUPER-CONNECTOR DIFFERENTIATION:
- If is_super_connector is true, the message should include a casual "bring someone" ask. Examples:
  - "...if you know anyone who'd be into it, bring them along"
  - "...feel free to bring a friend if you want"
  - Do NOT make it the focus of the message, just weave it in naturally

OUTPUT FORMAT: Return ONLY valid JSON. No markdown code fences. No explanation text before or after the JSON array."""


def build_user_prompt(
    contacts: list[dict],
    interactions: list[dict],
    open_loops: list[dict],
    linkedin_events: list[dict],
    today: str,
) -> str:
    """Build the user prompt with all contact data for Thursday outreach."""
    return f"""Today is {today} (Thursday outreach planning).

CONTACTS DATABASE:
{_format_contacts(contacts)}

RECENT INTERACTIONS (last 30 days):
{_format_interactions(interactions)}

OPEN LOOPS (unresolved conversation threads):
{_format_open_loops(open_loops)}

LINKEDIN EVENTS (unprocessed):
{_format_linkedin_events(linkedin_events)}

Generate 6-8 outreach recommendations as a JSON array. Remember: at least 1 Cornerstone, domain diversity, and every message must have a specific hook."""


def _format_contacts(contacts: list[dict]) -> str:
    if not contacts:
        return "No contacts in database."
    lines = []
    for c in contacts:
        parts = [
            f"ID:{c['id']}",
            f"Name:{c['name']}",
            f"Tier:{c['tier']}",
            f"Domain:{c.get('domain', 'N/A')}",
            f"SuperConnector:{c.get('is_super_connector', False)}",
            f"LastContact:{c.get('last_contact_date', 'Never')}",
            f"Interests:{c.get('interests', 'N/A')}",
            f"ActivityPrefs:{c.get('activity_prefs', 'N/A')}",
            f"Role:{c.get('current_role', 'N/A')}",
            f"Notes:{(c.get('notes') or '')[:200]}",
            f"NextAction:{c.get('next_action', 'N/A')}",
        ]
        lines.append(" | ".join(parts))
    return "\n".join(lines)


def _format_interactions(interactions: list[dict]) -> str:
    if not interactions:
        return "No recent interactions."
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


def _format_open_loops(open_loops: list[dict]) -> str:
    if not open_loops:
        return "No open loops."
    lines = []
    for o in open_loops:
        parts = [
            f"ContactID:{o['contact_id']}",
            f"Contact:{o.get('contact_name', 'Unknown')}",
            f"Date:{o['date']}",
            f"OpenLoop:{o.get('open_loops', 'N/A')}",
            f"FollowUpDate:{o.get('follow_up_date', 'N/A')}",
        ]
        lines.append(" | ".join(parts))
    return "\n".join(lines)


def _format_linkedin_events(events: list[dict]) -> str:
    if not events:
        return "No unprocessed LinkedIn events."
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
