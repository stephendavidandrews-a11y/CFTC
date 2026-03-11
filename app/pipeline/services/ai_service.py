"""
AI service: Claude integration for note processing, delegation recommendations,
email parsing, and precedent linking.

Uses Claude Sonnet for cost efficiency (~$3/M input, $15/M output).
"""

import json
import logging
import os
from datetime import datetime

logger = logging.getLogger(__name__)

# We use the anthropic library directly for simplicity
_client = None
_MODEL = os.environ.get("AI_MODEL", "claude-sonnet-4-20250514")


def _get_client():
    """Lazy-init the Anthropic client."""
    global _client
    if _client is None:
        try:
            import anthropic
            _client = anthropic.Anthropic(
                api_key=os.environ.get("ANTHROPIC_API_KEY", "")
            )
        except Exception as e:
            logger.error("Failed to create Anthropic client: %s", e)
            return None
    return _client


def _call_claude(system_prompt: str, user_prompt: str, max_tokens: int = 1024) -> dict:
    """Call Claude and return {text, input_tokens, output_tokens, model}."""
    client = _get_client()
    if not client:
        return {"text": "", "input_tokens": 0, "output_tokens": 0, "model": _MODEL, "error": "No client"}

    try:
        response = client.messages.create(
            model=_MODEL,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        return {
            "text": response.content[0].text,
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
            "model": _MODEL,
        }
    except Exception as e:
        logger.error("Claude API call failed: %s", e)
        return {"text": "", "input_tokens": 0, "output_tokens": 0, "model": _MODEL, "error": str(e)}


def log_ai_call(conn, processing_type: str, source_id: int, source_table: str,
                prompt_summary: str, result_text: str, model: str,
                input_tokens: int, output_tokens: int):
    """Log an AI processing call."""
    # Rough cost estimate (Sonnet pricing)
    cost = (input_tokens / 1_000_000 * 3.0) + (output_tokens / 1_000_000 * 15.0)
    conn.execute(
        """INSERT INTO ai_processing_log
           (processing_type, source_id, source_table, prompt_summary, result_text,
            model_used, input_tokens, output_tokens, cost_estimate)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (processing_type, source_id, source_table, prompt_summary,
         result_text, model, input_tokens, output_tokens, cost),
    )
    conn.commit()


# ---------------------------------------------------------------------------
# Note Processing
# ---------------------------------------------------------------------------

def process_note_insights(conn, note: dict, member: dict | None) -> dict:
    """Process a single note and extract insights for the team member profile.

    Returns: {key_insight, strengths_update, growth_areas_update, ...}
    """
    member_context = ""
    if member:
        member_context = f"""
Current profile for {member.get('name', 'Unknown')}:
- Role: {member.get('role', '')}
- Working style: {member.get('working_style', 'balanced')}
- Strengths: {', '.join(member.get('strengths', []))}
- Growth areas: {', '.join(member.get('growth_areas', []))}
- Personal context: {member.get('personal_context', 'None noted')}
"""

    system_prompt = (
        "You are processing notes about CFTC attorneys for Stephen, "
        "Deputy General Counsel. Extract actionable management insights. "
        "Respond ONLY with valid JSON, no markdown."
    )

    user_prompt = f"""Stephen observed this about a team member:

Context: {note.get('context_type', 'general')}
Date: {note.get('created_at', '')}
Note: {note.get('content', '')}

{member_context}

Extract insights. Return ONLY valid JSON:
{{
  "key_insight": "one sentence — most important management takeaway",
  "new_strengths": ["list of new strengths demonstrated, if any"],
  "new_growth_areas": ["list of new development needs identified, if any"],
  "working_style_signal": "only if note clearly indicates a different style preference, else null",
  "personal_context_update": "only if note mentions personal circumstances, else null",
  "suggested_action": "what Stephen should do next based on this note, if anything"
}}"""

    result = _call_claude(system_prompt, user_prompt, max_tokens=512)

    # Log the call
    log_ai_call(conn, "note_insights", note.get("id", 0), "manager_notes",
                f"Process note for {member.get('name', 'unknown') if member else 'unlinked'}",
                result["text"], result["model"],
                result["input_tokens"], result["output_tokens"])

    # Parse JSON response
    try:
        parsed = json.loads(result["text"])
    except (json.JSONDecodeError, TypeError):
        parsed = {"key_insight": result.get("text", "Failed to parse"), "error": True}

    return parsed


# ---------------------------------------------------------------------------
# Delegation Recommendation
# ---------------------------------------------------------------------------

def recommend_delegation(conn, project: dict, members: list[dict],
                         workloads: list[dict]) -> dict:
    """Recommend how to delegate a project to team members.

    Returns: {recommendation_text, components: [{title, assignee, reasoning}]}
    """
    system_prompt = (
        "You are a strategic advisor helping Stephen delegate work to his "
        "team of CFTC attorneys. Be specific and actionable. "
        "Respond ONLY with valid JSON."
    )

    team_summary = ""
    for m, w in zip(members, workloads):
        team_summary += f"""
{m['name']} ({m['role']}):
  Capacity: {m.get('current_capacity', 'available')} · {w.get('active_items', 0)} active items
  Strengths: {', '.join(m.get('strengths', []))}
  Specializations: {', '.join(m.get('specializations', []))}
  {f"Personal context: {m['personal_context']}" if m.get('personal_context') else ''}
"""

    user_prompt = f"""New project to delegate:

Title: {project.get('title', '')}
Description: {project.get('description', '')}
Due date: {project.get('due_date', 'No deadline')}
Priority: {project.get('priority_label', 'medium')}
Source: {project.get('source', 'Unknown')}

Team:
{team_summary}

Provide delegation strategy as JSON:
{{
  "can_delegate": "yes/partial/no",
  "reasoning": "why this can/cannot be delegated",
  "components": [
    {{
      "title": "component name",
      "description": "what this entails",
      "recommended_assignee": "person name",
      "reasoning": "why this person",
      "suggested_due_date": "YYYY-MM-DD or null"
    }}
  ],
  "what_stephen_keeps": "what Stephen should handle personally, if anything",
  "risk_flags": ["any concerns about this delegation"]
}}"""

    result = _call_claude(system_prompt, user_prompt, max_tokens=2048)

    log_ai_call(conn, "delegation_recommendation", project.get("id", 0), "projects",
                f"Delegation for: {project.get('title', '')}",
                result["text"], result["model"],
                result["input_tokens"], result["output_tokens"])

    try:
        parsed = json.loads(result["text"])
    except (json.JSONDecodeError, TypeError):
        parsed = {"recommendation_text": result.get("text", "Failed to parse"), "error": True}

    return parsed


# ---------------------------------------------------------------------------
# Email Parsing
# ---------------------------------------------------------------------------

def parse_status_email(conn, email_text: str, known_members: list[dict],
                       known_projects: list[dict]) -> dict:
    """Parse a forwarded email to extract status update information.

    Returns: {sender_name, matched_member_id, matched_project_id,
              status_update, action_needed}
    """
    member_names = [m["name"] for m in known_members]
    project_titles = [p["title"] for p in known_projects]

    system_prompt = (
        "You are parsing FORWARDED emails that Stephen sent from his work account. "
        "The actual sender is in the message body, NOT the From field. "
        "Extract structured status update info. Respond ONLY with valid JSON."
    )

    user_prompt = f"""Parse this forwarded email:

{email_text}

Known team members: {', '.join(member_names)}
Known projects: {', '.join(project_titles)}

Return ONLY valid JSON:
{{
  "original_sender_name": "name of person who sent to Stephen",
  "matched_team_member": "exact name from known team members list, or null",
  "assignment_keywords": "key terms about what work this relates to",
  "matched_project": "exact title from known projects list, or null",
  "status_indicator": "in_review | waiting_on_stephen | blocked | complete | in_progress",
  "action_needed": "what Stephen needs to do",
  "urgency": "urgent | normal | low",
  "due_date_mentioned": "YYYY-MM-DD or null",
  "agency_mentioned": "agency name or null"
}}"""

    result = _call_claude(system_prompt, user_prompt, max_tokens=512)

    log_ai_call(conn, "email_parse", 0, "email",
                "Parse forwarded email", result["text"], result["model"],
                result["input_tokens"], result["output_tokens"])

    try:
        parsed = json.loads(result["text"])
    except (json.JSONDecodeError, TypeError):
        parsed = {"error": True, "raw": result.get("text", "")}

    return parsed


# ---------------------------------------------------------------------------
# AI Usage Stats
# ---------------------------------------------------------------------------

def get_ai_usage(conn) -> dict:
    """Get AI usage statistics from the processing log."""
    total = conn.execute(
        "SELECT COUNT(*), COALESCE(SUM(input_tokens), 0), "
        "COALESCE(SUM(output_tokens), 0), COALESCE(SUM(cost_estimate), 0) "
        "FROM ai_processing_log"
    ).fetchone()

    by_type = {}
    rows = conn.execute(
        "SELECT processing_type, COUNT(*) as cnt, "
        "COALESCE(SUM(input_tokens), 0) as inp, "
        "COALESCE(SUM(output_tokens), 0) as outp, "
        "COALESCE(SUM(cost_estimate), 0) as cost "
        "FROM ai_processing_log GROUP BY processing_type"
    ).fetchall()
    for r in rows:
        by_type[r["processing_type"]] = {
            "calls": r["cnt"],
            "input_tokens": r["inp"],
            "output_tokens": r["outp"],
            "cost": round(r["cost"], 4),
        }

    return {
        "total_calls": total[0],
        "total_input_tokens": total[1],
        "total_output_tokens": total[2],
        "total_cost": round(total[3], 4),
        "by_type": by_type,
    }
