"""Smoke tests for v3 extraction prompts."""

from pathlib import Path


PROMPT_DIR = Path(__file__).resolve().parents[1] / "prompts" / "extraction"


def test_v3_pass1_prompt_exists_and_mentions_observation_vocab():
    prompt = (PROMPT_DIR / "v3_0_0_pass1.md").read_text(encoding="utf-8")
    assert "3.0.0-pass1" in prompt
    assert "services/tracker/app/contracts.py" in prompt
    assert "services/tracker/app/schema.py" in prompt
    assert "person_memory_signal" in prompt
    assert "institutional_memory_signal" in prompt
    assert "management_guidance" in prompt
    assert "context_note_posture" in prompt
    assert "task_signal.follow_up_need" in prompt
    assert "paired_follow_up_for_stephen" in prompt
    assert "Operational commitments outrank memory capture" in prompt
    assert "I need to ask Rusty at SEC about that." in prompt
    assert 'If Tyler says, "I\'ll ask Rusty at SEC," that is Tyler\'s `task_signal.commitment`.' in prompt
    assert "Do not silently rewrite a third-party commitment into a Stephen-owned task." in prompt
    assert "Use `prior_roles_summary` only for actual prior jobs" in prompt
    assert "You are not producing final tracker proposals in this pass." in prompt


def test_v3_pass2_prompt_exists_and_mentions_contract_alignment():
    prompt = (PROMPT_DIR / "v3_0_0_pass2.md").read_text(encoding="utf-8")
    assert "3.0.0-pass2" in prompt
    assert "services/tracker/app/contracts.py" in prompt
    assert "services/tracker/app/schema.py" in prompt
    assert "`new_matter` is not an item type in Pass 2." in prompt
    assert "stay strictly inside the existing tracker contract" in prompt
    assert "primary topic" in prompt
    assert "secondary topic" in prompt
    assert "Stephen's paired `follow_up` task" in prompt
    assert "same bundle" in prompt
    assert "person_detail_update" in prompt
    assert "context_note" in prompt
    assert '"body"' in prompt
    assert '"fields"' in prompt
    assert "policy_operating_rule" in prompt
    assert "process_note" in prompt
    assert "attributed_view" in prompt
    assert "Do not invent posture values like `neutral`." in prompt
    assert "Do not reassign a third-party action to Stephen just because Stephen benefits from it." in prompt
