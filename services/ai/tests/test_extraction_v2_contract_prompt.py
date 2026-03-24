"""Contract-alignment checks for the live v2 extraction prompt."""

import json
from pathlib import Path


AI_ROOT = Path(__file__).resolve().parents[1]
PROMPT_DIR = AI_ROOT / "prompts" / "extraction"
POLICY_PATH = AI_ROOT / "config" / "ai_policy.json"


def test_live_policy_uses_v2_0_1_extraction_prompt():
    policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    assert policy["model_config"]["active_prompt_versions"]["extraction"] == "v2.0.1"


def test_v2_0_1_prompt_is_contract_aligned():
    prompt = (PROMPT_DIR / "v2_0_1.md").read_text(encoding="utf-8")

    assert "services/tracker/app/contracts.py" in prompt
    assert "services/tracker/app/schema.py" in prompt
    assert "engagement_level` (lead | core | consulted | informed | escalation only, people only)" in prompt
    assert "category` (people_insight | process_note | policy_operating_rule | strategic_context | culture_climate | relationship_dynamic)" in prompt
    assert "posture` (factual | attributed_view)" in prompt
    assert "Use `body`, not `content`. Do not include `tags`." in prompt
    assert "All person profile writes must live under `proposed_data.fields`." in prompt
    assert "Use `prior_roles_summary` only for actual prior jobs or career history." in prompt
    assert 'Set `"extraction_version": "2.0.1"` on every response.' in prompt
    assert "institutional_knowledge" not in prompt
    assert "tentative, interpretive, sensitive" not in prompt
