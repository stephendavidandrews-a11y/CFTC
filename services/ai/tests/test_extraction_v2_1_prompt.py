"""Smoke tests for the v2.1 extraction prompt."""

from pathlib import Path


PROMPT_DIR = Path(__file__).resolve().parents[1] / "prompts" / "extraction"


def test_v2_1_prompt_contains_key_v2_1_invariants():
    prompt = (PROMPT_DIR / "v2_1_0.md").read_text(encoding="utf-8")

    assert "2.1.0" in prompt
    assert "services/tracker/app/contracts.py" in prompt
    assert "services/tracker/app/schema.py" in prompt
    assert (
        'If Tyler says "I need to ask Rusty," that is Tyler\'s action task.' in prompt
    )
    assert (
        'If Tyler says "You should ask Rusty," that is a request for Stephen' in prompt
    )
    assert "Do not rewrite a third-party commitment into a Stephen-owned task" in prompt
    assert "Operational commitments outrank memory capture" in prompt
    assert "Use `body`, not `content`." in prompt
    assert "Do not include `tags`." in prompt
    assert "All person profile writes must live under `proposed_data.fields`." in prompt
    assert "Use `prior_roles_summary` only for actual prior jobs" in prompt
    assert 'Set `"extraction_version": "2.1.0"` on every response.' in prompt
