"""
Anthropic API client for calling Claude Sonnet.
Uses ANTHROPIC_API_KEY from environment variables.
"""

import os
import json
import re
import anthropic


# Model to use for all AI calls
SONNET_MODEL = "claude-sonnet-4-20250514"


async def call_sonnet(system_prompt: str, user_prompt: str) -> str:
    """
    Call Claude Sonnet with the given system and user prompts.

    Args:
        system_prompt: The system-level instructions for Sonnet's behavior.
        user_prompt: The user-level input data and request.

    Returns:
        The text content of Sonnet's response.

    Raises:
        RuntimeError: If the API key is missing or the API call fails.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY environment variable is not set. "
            "Set it before starting the server: export ANTHROPIC_API_KEY=sk-..."
        )

    try:
        client = anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model=SONNET_MODEL,
            max_tokens=4096,
            system=system_prompt,
            messages=[
                {"role": "user", "content": user_prompt}
            ],
        )
        # Extract the text from the response
        return message.content[0].text

    except anthropic.AuthenticationError:
        raise RuntimeError(
            "Invalid ANTHROPIC_API_KEY. Check that your API key is correct and active."
        )
    except anthropic.RateLimitError:
        raise RuntimeError(
            "Anthropic API rate limit reached. Please wait a moment and try again."
        )
    except anthropic.APIError as e:
        raise RuntimeError(f"Anthropic API error: {str(e)}")
    except Exception as e:
        raise RuntimeError(f"Unexpected error calling Sonnet: {str(e)}")


def parse_json_response(text: str) -> any:
    """
    Parse a JSON response from Sonnet, with fallback regex extraction.
    Sonnet sometimes wraps JSON in markdown code fences despite instructions not to.

    Args:
        text: Raw text response from Sonnet.

    Returns:
        Parsed JSON (dict or list).

    Raises:
        ValueError: If no valid JSON can be extracted.
    """
    # First try: direct parse
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        pass

    # Second try: extract from markdown code fences
    fence_pattern = r"```(?:json)?\s*\n?([\s\S]*?)\n?\s*```"
    match = re.search(fence_pattern, text)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            pass

    # Third try: find the first [ or { and extract to its matching close
    for start_char, end_char in [("[", "]"), ("{", "}")]:
        start_idx = text.find(start_char)
        if start_idx == -1:
            continue
        # Find matching close by counting brackets
        depth = 0
        for i in range(start_idx, len(text)):
            if text[i] == start_char:
                depth += 1
            elif text[i] == end_char:
                depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start_idx : i + 1])
                except json.JSONDecodeError:
                    break

    raise ValueError(
        f"Could not parse JSON from Sonnet response. Raw response:\n{text[:500]}"
    )
