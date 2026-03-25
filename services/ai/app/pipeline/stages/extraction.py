"""Sonnet extraction stage — matter-centered intelligence extraction.

Pipeline position: associations_confirmed → **extracting** → awaiting_bundle_review

Takes confirmed speakers, cleaned transcript, enrichment data, and reviewed
entities. Fetches tracker context, builds a tiered prompt, calls Sonnet 4.6,
then runs a 7-step code post-processing pass before persisting review bundles.

Design contract: Phase 4A.1 revision memo (sections A-H).

This module is the coordinator. Implementation is split across:
- extraction_context.py    — tracker context fetching and tiering
- extraction_prompts.py    — prompt assembly
- extraction_postprocess.py — response parsing, validation, post-processing
- extraction_persist.py    — database persistence
- extraction_models.py     — Pydantic models and constants
"""

import json
import logging

from pydantic import ValidationError

from app.config import load_policy
from app.llm.client import call_llm, BudgetExceededError, LLMError

from app.pipeline.stages.extraction_models import (
    ExtractionOutput,
)

# ── Re-exports for backward compatibility ────────────────────────────────
# Tests and other modules import these by name from this file.
# All implementations now live in focused submodules.
from app.pipeline.stages.extraction_context import (  # noqa: F401
    _fetch_tracker_context,
    build_extraction_context,
)
from app.pipeline.stages.extraction_prompts import (  # noqa: F401
    _load_system_prompt,
    _build_user_prompt,
    PROMPT_DIR,
)
from app.pipeline.stages.extraction_postprocess import (  # noqa: F401
    _parse_extraction_response,
    _resolve_name_to_id,
    _resolve_entity_names,
    _validate_tracks_task_refs,
    _validate_update_items,
    _convert_legacy_follow_ups,
    _post_process,
    _fuzzy_title_match,
    _normalize_context_note_item,
    _normalize_person_detail_update_item,
    _first_source_speaker,
    _choose_context_note_category,
    _choose_context_note_posture,
    _looks_like_current_role_note,
    CONTEXT_NOTE_CATEGORIES,
    CONTEXT_NOTE_CATEGORY_ALIASES,
    CONTEXT_NOTE_POSTURES,
    PERSON_PROFILE_FIELDS,
    PERSON_PEOPLE_FIELDS,
    PERSON_DETAIL_FIELDS,
    CURRENT_ROLE_MARKERS,
    PRIOR_ROLE_MARKERS,
)
from app.pipeline.stages.extraction_persist import (  # noqa: F401
    _build_source_locator,
    _persist_extraction,
    _clear_bundles_for_communication,
    _persist_failed_extraction,
)

logger = logging.getLogger(__name__)

MAX_SONNET_ATTEMPTS = 3

# ═══════════════════════════════════════════════════════════════════════════
# 8. Sonnet extraction with retry (internal helper)
# ═══════════════════════════════════════════════════════════════════════════

MAX_SONNET_ATTEMPTS = 3   # Sonnet self-correction retries (parse/validation)

async def _run_sonnet_extraction(
    db,
    communication_id: str,
    sonnet_model: str,
    system_prompt: str,
    user_prompt: str,
    full_context: dict,
    full_context_json: str,
    policy: dict,
    prompt_version: str,
) -> "ExtractionAttemptResult":
    """Run Sonnet extraction with up to MAX_SONNET_ATTEMPTS retries on
    parse/validation failures.

    Returns ExtractionAttemptResult (success or final failure).
    Raises BudgetExceededError (let orchestrator handle).
    """
    from app.pipeline.stages.escalation import (
        ExtractionAttemptResult, ExtractionFailureType,
    )

    last_error = None
    last_raw_output = None
    total_cost = 0.0

    for attempt in range(1, MAX_SONNET_ATTEMPTS + 1):
        try:
            prompt_for_attempt = user_prompt if attempt == 1 else (
                user_prompt + f"\n\n## Retry Note\n"
                f"Previous attempt failed to produce valid JSON. "
                f"Error: {last_error}\nReturn ONLY the JSON object."
            )

            response = await call_llm(
                db=db,
                communication_id=communication_id,
                stage="extracting",
                model=sonnet_model,
                system_prompt=system_prompt,
                user_prompt=prompt_for_attempt,
                max_tokens=8192,
                temperature=0.0,
            )
            total_cost += response.usage.cost_usd
            last_raw_output = response.text

            # Parse response
            raw_dict = _parse_extraction_response(response.text)
            extraction = ExtractionOutput(**raw_dict)

            # Post-process
            processed = _post_process(
                extraction, full_context, policy, db, communication_id,
            )

            logger.info(
                "[%s] Sonnet attempt %d succeeded: %d bundles, $%.4f",
                communication_id[:8], attempt,
                len(processed["bundles"]), response.usage.cost_usd,
            )

            return ExtractionAttemptResult(
                success=True,
                model=sonnet_model,
                attempt_number=attempt,
                raw_output=response.text,
                parsed_output=extraction,
                processed=processed,
                usage_data={
                    "input_tokens": response.usage.input_tokens,
                    "output_tokens": response.usage.output_tokens,
                    "processing_seconds": response.usage.processing_seconds,
                    "cost_usd": response.usage.cost_usd,
                    "total_cost_usd": total_cost,
                },
            )

        except json.JSONDecodeError as e:
            last_error = f"JSON parse error: {e}"
            logger.warning(
                "[%s] Sonnet attempt %d parse failed: %s",
                communication_id[:8], attempt, e,
            )
        except ValidationError as e:
            last_error = f"Validation error: {e.error_count()} errors"
            logger.warning(
                "[%s] Sonnet attempt %d validation failed: %s",
                communication_id[:8], attempt, e,
            )
        except BudgetExceededError:
            raise
        except LLMError as e:
            if not e.recoverable:
                raise
            last_error = str(e)
            logger.warning(
                "[%s] Sonnet attempt %d LLM error: %s",
                communication_id[:8], attempt, e,
            )

    # All Sonnet attempts failed
    failure_type = ExtractionFailureType.PARSE_FAILURE
    if last_error and "Validation" in last_error:
        failure_type = ExtractionFailureType.VALIDATION_FAILURE
    elif last_error and ("API" in last_error or "LLM" in last_error):
        failure_type = ExtractionFailureType.MODEL_API_FAILURE

    return ExtractionAttemptResult(
        success=False,
        model=sonnet_model,
        attempt_number=MAX_SONNET_ATTEMPTS,
        raw_output=last_raw_output,
        failure_type=failure_type,
        failure_detail=last_error,
        usage_data={"total_cost_usd": total_cost},
    )


# ═══════════════════════════════════════════════════════════════════════════
# 9. Opus escalation attempt (Original Phase 5)
# ═══════════════════════════════════════════════════════════════════════════

async def _run_opus_escalation(
    db,
    communication_id: str,
    opus_model: str,
    system_prompt: str,
    user_prompt: str,
    full_context: dict,
    full_context_json: str,
    policy: dict,
    prompt_version: str,
    sonnet_result: "ExtractionAttemptResult",
    triggers: list,
) -> "ExtractionAttemptResult":
    """Run Opus escalation extraction.

    Per 03_AI_BEHAVIOR.md §7C: Opus receives the same input as Sonnet
    plus Sonnet's complete output plus a meta-instruction.

    Returns ExtractionAttemptResult.
    Raises BudgetExceededError (let orchestrator handle).
    """
    from app.pipeline.stages.escalation import (
        ExtractionAttemptResult, ExtractionFailureType,
        build_opus_meta_instruction,
    )

    meta_instruction = build_opus_meta_instruction(triggers, sonnet_result)
    opus_prompt = user_prompt + "\n\n" + meta_instruction

    escalation_reason = ", ".join(t.value for t in triggers)

    try:
        response = await call_llm(
            db=db,
            communication_id=communication_id,
            stage="extracting_opus",
            model=opus_model,
            system_prompt=system_prompt,
            user_prompt=opus_prompt,
            max_tokens=8192,
            temperature=0.0,
        )

        # Parse
        raw_dict = _parse_extraction_response(response.text)
        extraction = ExtractionOutput(**raw_dict)

        # Post-process (same rules as Sonnet)
        processed = _post_process(
            extraction, full_context, policy, db, communication_id,
        )

        logger.info(
            "[%s] Opus escalation succeeded: %d bundles, $%.4f",
            communication_id[:8],
            len(processed["bundles"]), response.usage.cost_usd,
        )

        return ExtractionAttemptResult(
            success=True,
            model=opus_model,
            attempt_number=1,
            raw_output=response.text,
            parsed_output=extraction,
            processed=processed,
            triggers_detected=triggers,
            escalation_reason=escalation_reason,
            usage_data={
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
                "processing_seconds": response.usage.processing_seconds,
                "cost_usd": response.usage.cost_usd,
            },
        )

    except json.JSONDecodeError as e:
        logger.warning(
            "[%s] Opus escalation parse failed: %s",
            communication_id[:8], e,
        )
        return ExtractionAttemptResult(
            success=False,
            model=opus_model,
            attempt_number=1,
            failure_type=ExtractionFailureType.PARSE_FAILURE,
            failure_detail=f"Opus JSON parse error: {e}",
            triggers_detected=triggers,
            escalation_reason=escalation_reason,
        )
    except ValidationError as e:
        logger.warning(
            "[%s] Opus escalation validation failed: %s",
            communication_id[:8], e,
        )
        return ExtractionAttemptResult(
            success=False,
            model=opus_model,
            attempt_number=1,
            failure_type=ExtractionFailureType.VALIDATION_FAILURE,
            failure_detail=f"Opus validation error: {e.error_count()} errors",
            triggers_detected=triggers,
            escalation_reason=escalation_reason,
        )
    except BudgetExceededError:
        raise
    except LLMError as e:
        logger.warning(
            "[%s] Opus escalation LLM error: %s", communication_id[:8], e,
        )
        return ExtractionAttemptResult(
            success=False,
            model=opus_model,
            attempt_number=1,
            failure_type=ExtractionFailureType.MODEL_API_FAILURE,
            failure_detail=str(e),
            triggers_detected=triggers,
            escalation_reason=escalation_reason,
        )


# ═══════════════════════════════════════════════════════════════════════════
# 10. Main entry point — extraction with escalation (Phase 4B + Phase 5)
# ═══════════════════════════════════════════════════════════════════════════

async def run_extraction_stage(db, communication_id: str) -> dict:
    """Run extraction: Sonnet first, then Opus escalation if triggered.

    Flow (per 03_AI_BEHAVIOR.md §7 and 05_CONFIG_AND_BUILD_ORDER.md Phase 5):
      1. Run Sonnet extraction (up to MAX_SONNET_ATTEMPTS with self-correction)
      2. If Sonnet succeeds: check escalation triggers
         a. No triggers → persist Sonnet result → done
         b. Triggers fired + escalation enabled → run Opus → persist winner
      3. If Sonnet fails entirely: check if Opus escalation can salvage
         a. Escalation enabled → run Opus
         b. Escalation disabled or Opus also fails → terminal error

    Returns summary dict with bundle counts, cost, and escalation metadata.
    Raises BudgetExceededError if budget is exhausted.
    Raises RuntimeError for unrecoverable failures.
    """
    from app.pipeline.stages.escalation import (
        detect_triggers,
        decide_escalation,
    )
    from app.routers.events import publish_event

    policy = load_policy()
    model_config = policy.get("model_config", {})
    sonnet_model = model_config.get(
        "primary_extraction_model", "claude-sonnet-4-20250514"
    )
    opus_model = model_config.get("escalation_model", "claude-opus-4-6")
    prompt_version = model_config.get("active_prompt_versions", {}).get(
        "extraction", "v1.0.0"
    )

    # Load system prompt
    system_prompt = _load_system_prompt(prompt_version)

    # Build extraction context using confirmed enrichment associations
    tiered = await build_extraction_context(db, communication_id)

    # Extract full context for snapshot storage
    full_context = tiered.pop("_full_context", {})
    full_context_json = json.dumps(full_context, ensure_ascii=False, default=str)

    logger.info(
        "[%s] Context built: %d T1 matters, %d T2 matters, %d T1 directives, "
        "%d T1 people, %d T1 meetings, %d intents, %d intel flags",
        communication_id[:8],
        tiered["tier_stats"]["tier_1_matter_count"],
        tiered["tier_stats"]["tier_2_matter_count"],
        tiered["tier_stats"].get("tier_1_directive_count", 0),
        tiered["tier_stats"].get("tier_1_people_count", 0),
        tiered["tier_stats"]["tier_1_meeting_count"],
        len(tiered.get("segment_intents", [])),
        len(tiered.get("intelligence_flags", [])),
    )

    # Build user prompt
    user_prompt = _build_user_prompt(db, communication_id, tiered, policy)

    # ── Step 1: Sonnet extraction ──
    sonnet_result = await _run_sonnet_extraction(
        db, communication_id, sonnet_model, system_prompt, user_prompt,
        full_context, full_context_json, policy, prompt_version,
    )

    # ── Step 2: Check escalation triggers (Original Phase 5) ──
    triggers = detect_triggers(sonnet_result, db, communication_id, policy)
    escalation_decision = decide_escalation(triggers, db, policy)

    # Log the decision
    if triggers:
        logger.info(
            "[%s] Escalation triggers: [%s] — decision: %s",
            communication_id[:8],
            ", ".join(t.value for t in triggers),
            escalation_decision.reason,
        )

    # ── Step 3: Persist Sonnet result (always, for audit trail) ──
    sonnet_extraction_id = None
    if sonnet_result.success:
        sonnet_extraction_id = _persist_extraction(
            db=db,
            communication_id=communication_id,
            extraction=sonnet_result.parsed_output,
            processed=sonnet_result.processed,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            full_context_json=full_context_json,
            raw_output=sonnet_result.raw_output,
            attempt_number=sonnet_result.attempt_number,
            model_used=sonnet_model,
            prompt_version=prompt_version,
            usage_data=sonnet_result.usage_data or {},
            escalation_reason=None,
            success=not escalation_decision.should_escalate,
        )

    # ── Step 4: Opus escalation if warranted ──
    opus_result = None
    final_extraction_id = sonnet_extraction_id

    if escalation_decision.should_escalate:
        await publish_event("stage_progress", {
            "communication_id": communication_id,
            "stage": "extracting",
            "message": f"Escalating to Opus ({escalation_decision.reason})...",
        })

        opus_result = await _run_opus_escalation(
            db, communication_id, opus_model, system_prompt, user_prompt,
            full_context, full_context_json, policy, prompt_version,
            sonnet_result, triggers,
        )

        if opus_result.success:
            # Clear Sonnet bundles — Opus output supersedes
            if sonnet_result.success:
                _clear_bundles_for_communication(db, communication_id)

            # Persist Opus result as the authoritative extraction
            opus_attempt = (sonnet_result.attempt_number + 1) if sonnet_result.success else (MAX_SONNET_ATTEMPTS + 1)
            final_extraction_id = _persist_extraction(
                db=db,
                communication_id=communication_id,
                extraction=opus_result.parsed_output,
                processed=opus_result.processed,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                full_context_json=full_context_json,
                raw_output=opus_result.raw_output,
                attempt_number=opus_attempt,
                model_used=opus_model,
                prompt_version=prompt_version,
                usage_data=opus_result.usage_data or {},
                escalation_reason=opus_result.escalation_reason,
                success=True,
            )
            logger.info(
                "[%s] Opus escalation succeeded — using Opus bundles",
                communication_id[:8],
            )
        else:
            # Opus failed — fall back to Sonnet if available
            if sonnet_result.success:
                # Mark Sonnet extraction as the final success
                db.execute("""
                    UPDATE ai_extractions SET success = 1
                    WHERE id = ? AND communication_id = ?
                """, (sonnet_extraction_id, communication_id))
                db.commit()
                logger.warning(
                    "[%s] Opus escalation failed — falling back to Sonnet result",
                    communication_id[:8],
                )
            else:
                # Both failed — persist Opus failure for audit, then error
                _persist_failed_extraction(
                    db, communication_id, opus_model, opus_result,
                    prompt_version, full_context_json,
                )
                raise RuntimeError(
                    f"Extraction failed: Sonnet ({sonnet_result.failure_detail}) "
                    f"and Opus escalation ({opus_result.failure_detail})"
                )

    elif escalation_decision.blocked_by_budget:
        # Escalation warranted but budget blocked
        if not sonnet_result.success:
            raise BudgetExceededError(0, 0)  # Let orchestrator handle
        logger.warning(
            "[%s] Escalation blocked by budget — using Sonnet result",
            communication_id[:8],
        )

    elif not sonnet_result.success:
        # No escalation available, Sonnet failed
        _persist_failed_extraction(
            db, communication_id, sonnet_model, sonnet_result,
            prompt_version, full_context_json,
        )
        raise RuntimeError(
            f"Extraction failed after {MAX_SONNET_ATTEMPTS} Sonnet attempts "
            f"(escalation {'disabled' if escalation_decision.blocked_by_config else 'not triggered'}): "
            f"{sonnet_result.failure_detail}"
        )

    # ── Step 5: Build return summary ──
    winner = opus_result if (opus_result and opus_result.success) else sonnet_result
    bundles = winner.processed["bundles"]
    total_items = sum(len(b.items) for b in bundles)
    pp_log = winner.processed["post_processing_log"]

    sonnet_cost = (sonnet_result.usage_data or {}).get("total_cost_usd", 0)
    opus_cost = (opus_result.usage_data or {}).get("cost_usd", 0) if opus_result else 0

    logger.info(
        "[%s] Extraction stage complete: %d bundles, %d items, "
        "model=%s, escalated=%s, cost=$%.4f",
        communication_id[:8], len(bundles), total_items,
        winner.model.split("-")[1],
        bool(opus_result and opus_result.success),
        sonnet_cost + opus_cost,
    )

    return {
        "extraction_id": final_extraction_id,
        "bundles_created": len(bundles),
        "items_created": total_items,
        "items_suppressed": len(pp_log["code_suppressed_items"]),
        "dedup_warnings": len(pp_log["dedup_warnings"]),
        "invalid_refs_cleaned": len(pp_log["invalid_references_cleaned"]),
        "input_tokens": (winner.usage_data or {}).get("input_tokens", 0),
        "output_tokens": (winner.usage_data or {}).get("output_tokens", 0),
        "total_cost_usd": round(sonnet_cost + opus_cost, 6),
        "attempt_number": winner.attempt_number,
        "tier_stats": tiered["tier_stats"],
        "escalated": bool(opus_result and opus_result.success),
        "escalation_triggers": [t.value for t in triggers] if triggers else [],
        "escalation_decision": escalation_decision.reason if triggers else None,
        "model_used": winner.model,
    }
