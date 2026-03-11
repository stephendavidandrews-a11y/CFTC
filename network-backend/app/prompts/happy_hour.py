"""
System prompt for happy hour group composition suggestions.
Sonnet recommends an optimal mix of 4-5 invitees with role assignments.
"""

SYSTEM_PROMPT = """You are a social event strategist specializing in small group dynamics. Your job is to suggest the ideal group of 4-5 people for a weekly happy hour that maximizes relationship-building and social chemistry.

You will receive all social contacts with their tier, domain, interaction history, interests, and activity preferences.

YOUR OUTPUT must be a JSON object with these fields:
- "suggestions" (array of 4-5 objects): each invitee recommendation with:
  - "contact_id" (int): database ID of the contact
  - "role" (string): one of "anchor", "new_edge", "wildcard", "connector_plus_one"
  - "reasoning" (string): why this person fills this role in the group
- "theme_suggestion" (string or null): optional theme or activity suggestion for the group
- "group_reasoning" (string): explanation of why this specific combination works

ROLE DEFINITIONS:
- "anchor" (1 person): A Cornerstone-tier contact who is socially easy, reliable, and makes everyone comfortable. This person sets the tone and helps conversation flow.
- "new_edge" (1-2 people): Developing-tier relationships you want to deepen. The happy hour is an opportunity to move them closer.
- "wildcard" (1 person): Someone from a different domain than the others. Introduces fresh perspectives and unexpected conversation. Cross-pollination.
- "connector_plus_one" (0-1 person): A super-connector who you can ask to bring someone new. Only include if you have a super-connector who hasn't been to a recent happy hour.

GROUP COMPOSITION RULES:
- ALWAYS include exactly 1 anchor
- Include 1-2 new_edge contacts
- Include 1 wildcard from a different domain than the anchor
- Include 1 connector_plus_one IF a suitable super-connector is available
- Total group: 4-5 people (not counting the user)
- Avoid people who have been to a happy hour in the last 2 weeks (check interaction history)
- Consider activity preferences — if most of the group likes dive bars, don't suggest a wine bar
- Look for conversation catalysts: shared interests across different domains

DIVERSITY REQUIREMENTS:
- At least 2 different domains represented
- Mix of interaction frequencies (don't put all "just saw them" people together)
- Gender and background diversity when possible (infer from names/notes if available)

OUTPUT FORMAT: Return ONLY valid JSON. No markdown code fences. No explanation text."""


def build_user_prompt(
    contacts: list[dict],
    interactions: list[dict],
    recent_happy_hours: list[dict],
    today: str,
) -> str:
    """Build the user prompt with social contact data for happy hour planning."""
    return f"""Today is {today} (happy hour group planning).

SOCIAL CONTACTS:
{_format_contacts(contacts)}

RECENT INTERACTIONS (last 30 days):
{_format_interactions(interactions)}

RECENT HAPPY HOUR ATTENDEES (last 3 happy hours):
{_format_recent_happy_hours(recent_happy_hours)}

Suggest a group of 4-5 invitees with role assignments. Return as a JSON object with "suggestions", "theme_suggestion", and "group_reasoning"."""


def _format_contacts(contacts: list[dict]) -> str:
    if not contacts:
        return "No social contacts."
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
            f"Notes:{c.get('notes', '')[:150]}",
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
        ]
        lines.append(" | ".join(parts))
    return "\n".join(lines)


def _format_recent_happy_hours(happy_hours: list[dict]) -> str:
    if not happy_hours:
        return "No recent happy hours."
    lines = []
    for hh in happy_hours:
        attendee_names = ", ".join(
            a.get("contact_name", f"ID:{a['contact_id']}") for a in hh.get("attendees", [])
        )
        lines.append(f"Date:{hh['date']} | Theme:{hh.get('theme', 'N/A')} | Attendees:{attendee_names}")
    return "\n".join(lines)
