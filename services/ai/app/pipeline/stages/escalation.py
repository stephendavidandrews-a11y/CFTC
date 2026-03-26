"""Original Phase 5 — Opus Escalation policy and trigger detection.

Implements the extraction retry/escalation policy from 03_AI_BEHAVIOR.md §7.
Sonnet runs first.  Opus is invoked ONLY when Sonnet's output indicates
problems, as determined by configurable trigger conditions.

Trigger sources (all configurable via model_config.opus_retry_triggers):
    1. low_confidence   — any bundle confidence < 0.5
    2. over_splitting   — 4+ new_matter bundles from one communication
    3. uncertainty_flags — Sonnet self-reported uncertainty_flags on any bundle
    4. validation_failure — Sonnet output failed JSON parse or Pydantic validation
                           after all Sonnet retry attempts

Conservative first implementation:
    - "empty_extraction" is an additional safety trigger (not configurable):
      extraction produced zero bundles from a communication with substantial
      transcript content (>= 60 seconds or >= 30 segments).
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════
# Typed escalation triggers
# ═══════════════════════════════════════════════════════════════════════════


class EscalationTrigger(str, Enum):
    """Trigger conditions from 03_AI_BEHAVIOR.md §7B."""

    LOW_CONFIDENCE = "low_confidence"
    OVER_SPLITTING = "over_splitting"
    UNCERTAINTY_FLAGS = "uncertainty_flags"
    VALIDATION_FAILURE = "validation_failure"
    EMPTY_EXTRACTION = "empty_extraction"  # conservative safety net


# ═══════════════════════════════════════════════════════════════════════════
# Typed extraction failures
# ═══════════════════════════════════════════════════════════════════════════


class ExtractionFailureType(str, Enum):
    """Typed failure categories for extraction attempts."""

    PARSE_FAILURE = "parse_failure"
    VALIDATION_FAILURE = "validation_failure"
    MODEL_API_FAILURE = "model_api_failure"
    BUDGET_BLOCK = "budget_block"
    ESCALATION_EXHAUSTED = "escalation_exhausted"


@dataclass
class ExtractionAttemptResult:
    """Result of a single extraction attempt (Sonnet or Opus)."""

    success: bool
    model: str
    attempt_number: int
    raw_output: Optional[str] = None
    parsed_output: Optional[object] = None  # ExtractionOutput when success
    processed: Optional[dict] = None  # post-processing result
    failure_type: Optional[ExtractionFailureType] = None
    failure_detail: Optional[str] = None
    usage_data: Optional[dict] = None
    triggers_detected: list[EscalationTrigger] = field(default_factory=list)
    escalation_reason: Optional[str] = None


@dataclass
class EscalationDecision:
    """Decision about whether to escalate to Opus."""

    should_escalate: bool
    triggers: list[EscalationTrigger]
    reason: str
    blocked_by_budget: bool = False
    blocked_by_config: bool = False


# ═══════════════════════════════════════════════════════════════════════════
# Trigger detection — analyze Sonnet output for escalation conditions
# ═══════════════════════════════════════════════════════════════════════════

LOW_CONFIDENCE_THRESHOLD = 0.5
OVER_SPLITTING_THRESHOLD = 4


def detect_triggers(
    sonnet_result: ExtractionAttemptResult,
    db,
    communication_id: str,
    policy: dict,
) -> list[EscalationTrigger]:
    """Analyze Sonnet extraction result for escalation trigger conditions.

    Checks all 4 spec triggers + the conservative empty_extraction safety net.
    Returns list of triggered conditions (may be empty).
    """
    triggers = []
    trigger_config = policy.get("model_config", {}).get("opus_retry_triggers", {})

    # ── Trigger 1: validation_failure ──
    # Sonnet failed to produce valid output after all retries
    if not sonnet_result.success:
        if trigger_config.get("validation_failure", True):
            triggers.append(EscalationTrigger.VALIDATION_FAILURE)
        return triggers  # No output to check other triggers against

    # From here, Sonnet succeeded — check quality triggers on the output
    extraction = sonnet_result.parsed_output
    if extraction is None:
        return triggers

    bundles = extraction.bundles

    # ── Trigger 2: low_confidence ──
    # Any bundle has confidence < 0.5
    if trigger_config.get("low_confidence", True):
        low_conf_bundles = [
            b for b in bundles if b.confidence < LOW_CONFIDENCE_THRESHOLD
        ]
        if low_conf_bundles:
            triggers.append(EscalationTrigger.LOW_CONFIDENCE)
            logger.info(
                "[%s] Escalation trigger: low_confidence — %d bundles below %.1f",
                communication_id[:8],
                len(low_conf_bundles),
                LOW_CONFIDENCE_THRESHOLD,
            )

    # ── Trigger 3: over_splitting ──
    # 4+ new_matter bundles from a single communication
    if trigger_config.get("over_splitting", True):
        new_matter_count = sum(1 for b in bundles if b.bundle_type == "new_matter")
        if new_matter_count >= OVER_SPLITTING_THRESHOLD:
            triggers.append(EscalationTrigger.OVER_SPLITTING)
            logger.info(
                "[%s] Escalation trigger: over_splitting — %d new matters (>= %d)",
                communication_id[:8],
                new_matter_count,
                OVER_SPLITTING_THRESHOLD,
            )

    # ── Trigger 4: uncertainty_flags ──
    # Sonnet self-reported uncertainty on any bundle
    if trigger_config.get("uncertainty_flags", True):
        flagged_bundles = [b for b in bundles if b.uncertainty_flags]
        if flagged_bundles:
            triggers.append(EscalationTrigger.UNCERTAINTY_FLAGS)
            total_flags = sum(len(b.uncertainty_flags) for b in flagged_bundles)
            logger.info(
                "[%s] Escalation trigger: uncertainty_flags — %d flags across %d bundles",
                communication_id[:8],
                total_flags,
                len(flagged_bundles),
            )

    # ── Safety net: empty_extraction ──
    # Zero bundles from substantial content (always checked, not configurable)
    if not bundles:
        comm_row = db.execute(
            "SELECT duration_seconds FROM communications WHERE id = ?",
            (communication_id,),
        ).fetchone()
        duration = (comm_row["duration_seconds"] or 0) if comm_row else 0

        seg_count = db.execute(
            "SELECT COUNT(*) as cnt FROM transcripts WHERE communication_id = ?",
            (communication_id,),
        ).fetchone()["cnt"]

        if duration >= 60 or seg_count >= 30:
            triggers.append(EscalationTrigger.EMPTY_EXTRACTION)
            logger.info(
                "[%s] Escalation trigger: empty_extraction — "
                "0 bundles from %ds / %d segments",
                communication_id[:8],
                duration,
                seg_count,
            )

    return triggers


# ═══════════════════════════════════════════════════════════════════════════
# Escalation decision — combine triggers with config and budget
# ═══════════════════════════════════════════════════════════════════════════


def decide_escalation(
    triggers: list[EscalationTrigger],
    db,
    policy: dict,
) -> EscalationDecision:
    """Decide whether to escalate to Opus based on triggers, config, and budget.

    Returns EscalationDecision with reason and any blocking conditions.
    """
    if not triggers:
        return EscalationDecision(
            should_escalate=False,
            triggers=[],
            reason="No escalation triggers detected",
        )

    # Check if escalation model is configured
    model_config = policy.get("model_config", {})
    escalation_model = model_config.get("escalation_model")
    if not escalation_model:
        return EscalationDecision(
            should_escalate=False,
            triggers=triggers,
            reason="No escalation model configured",
            blocked_by_config=True,
        )

    # Check all trigger flags — if ALL triggered flags are disabled, don't escalate
    trigger_config = model_config.get("opus_retry_triggers", {})
    enabled_triggers = [
        t
        for t in triggers
        if t == EscalationTrigger.EMPTY_EXTRACTION  # always enabled
        or trigger_config.get(t.value, True)
    ]

    if not enabled_triggers:
        return EscalationDecision(
            should_escalate=False,
            triggers=triggers,
            reason=f"Triggers detected ({', '.join(t.value for t in triggers)}) "
            f"but all disabled in config",
            blocked_by_config=True,
        )

    # Check budget
    from app.llm.client import check_budget

    today_spend, daily_budget, is_over = check_budget(db)
    if is_over:
        return EscalationDecision(
            should_escalate=False,
            triggers=enabled_triggers,
            reason=f"Budget exhausted (${today_spend:.2f} / ${daily_budget:.2f})",
            blocked_by_budget=True,
        )

    reason = "Escalation triggered: " + ", ".join(t.value for t in enabled_triggers)
    return EscalationDecision(
        should_escalate=True,
        triggers=enabled_triggers,
        reason=reason,
    )


# ═══════════════════════════════════════════════════════════════════════════
# Opus meta-instruction — tell Opus what went wrong with Sonnet
# ═══════════════════════════════════════════════════════════════════════════


def build_opus_meta_instruction(
    triggers: list[EscalationTrigger],
    sonnet_result: ExtractionAttemptResult,
) -> str:
    """Build the meta-instruction appended to the Opus prompt.

    Per 03_AI_BEHAVIOR.md §7C: Opus receives the same input as Sonnet
    plus Sonnet's complete output plus a meta-instruction explaining
    which triggers fired.
    """
    sections = [
        "## Escalation Context",
        "",
        "The previous extraction attempt (Claude Sonnet) completed but was "
        "flagged for quality review. You are being asked to re-extract with "
        "particular attention to the issues identified below.",
        "",
        "### Issues Detected",
    ]

    for trigger in triggers:
        if trigger == EscalationTrigger.LOW_CONFIDENCE:
            sections.append(
                "- **Low confidence routing**: One or more bundles had "
                "confidence below 0.5. Re-evaluate matter routing with "
                "careful attention to the matter context provided."
            )
        elif trigger == EscalationTrigger.OVER_SPLITTING:
            sections.append(
                "- **Over-splitting**: 4+ new matters were proposed from a "
                "single communication. This is unusual. Re-evaluate whether "
                "some topics actually belong to existing matters or should "
                "be consolidated."
            )
        elif trigger == EscalationTrigger.UNCERTAINTY_FLAGS:
            sections.append(
                "- **Self-flagged uncertainty**: The previous attempt flagged "
                "areas of uncertainty. Address these directly and provide "
                "clearer routing/classification."
            )
        elif trigger == EscalationTrigger.VALIDATION_FAILURE:
            sections.append(
                "- **Validation failure**: The previous attempt produced "
                "output that could not be parsed or validated. Ensure your "
                "output is strictly valid JSON matching the required schema."
            )
        elif trigger == EscalationTrigger.EMPTY_EXTRACTION:
            sections.append(
                "- **Empty extraction**: The previous attempt produced zero "
                "bundles from substantial conversation content. This is "
                "likely incorrect. Re-analyze the transcript carefully for "
                "actionable intelligence."
            )

    # Include Sonnet's output if available
    if sonnet_result.raw_output:
        # Truncate to avoid prompt explosion (Opus has same context window)
        sonnet_text = sonnet_result.raw_output
        if len(sonnet_text) > 12000:
            sonnet_text = sonnet_text[:12000] + "\n... [truncated]"
        sections.extend(
            [
                "",
                "### Previous Attempt Output (Sonnet)",
                "```json",
                sonnet_text,
                "```",
            ]
        )

    sections.extend(
        [
            "",
            "### Instructions",
            "Re-extract from the same source material. Your output must use the "
            "exact same JSON schema. Focus on correcting the specific issues "
            "above. Prefer fewer, higher-quality proposals with well-justified "
            "routing decisions.",
        ]
    )

    return "\n".join(sections)
