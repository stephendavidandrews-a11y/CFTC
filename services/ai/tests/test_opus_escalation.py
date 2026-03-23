"""Original Phase 5 — Opus Escalation verification tests.

Tests the extraction retry/escalation policy, trigger detection,
Opus fallback, budget-aware behavior, and audit trail.

All tests use mock LLM responses — no real API calls.
"""

import asyncio
import json
import sqlite3
import sys
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

# ── Path setup ──
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.llm.client import LLMResponse, LLMUsage
from app.pipeline.stages.escalation import (
    EscalationTrigger,
    ExtractionAttemptResult,
    ExtractionFailureType,
    detect_triggers,
    decide_escalation,
    build_opus_meta_instruction,
)
from app.pipeline.stages.extraction_models import (
    ExtractionOutput,
    ExtractionBundle,
    ExtractionItem,
    SourceTimeRange,
)


# ═══════════════════════════════════════════════════════════════════════════
# Test helpers
# ═══════════════════════════════════════════════════════════════════════════

def _run(coro):
    """Run async coroutine synchronously."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _make_db():
    """Create in-memory DB with minimal schema for tests."""
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = OFF")

    db.execute("""CREATE TABLE communications (
        id TEXT PRIMARY KEY,
        source_type TEXT DEFAULT 'meeting',
        processing_status TEXT DEFAULT 'extracting',
        original_filename TEXT,
        duration_seconds REAL,
        topic_segments_json TEXT,
        sensitivity_flags TEXT,
        source_metadata TEXT,
        error_message TEXT,
        error_stage TEXT,
        processing_lock_token TEXT,
        locked_at TEXT,
        lock_expires_at TEXT,
        created_at TEXT DEFAULT (datetime('now')),
        updated_at TEXT DEFAULT (datetime('now'))
    )""")
    db.execute("""CREATE TABLE transcripts (
        id TEXT PRIMARY KEY,
        communication_id TEXT,
        speaker_label TEXT,
        start_time REAL,
        end_time REAL,
        raw_text TEXT,
        cleaned_text TEXT,
        created_at TEXT DEFAULT (datetime('now'))
    )""")
    db.execute("""CREATE TABLE communication_participants (
        id TEXT PRIMARY KEY,
        communication_id TEXT,
        speaker_label TEXT,
        tracker_person_id TEXT,
        proposed_name TEXT,
        proposed_title TEXT,
        proposed_org TEXT
    )""")
    db.execute("""CREATE TABLE communication_entities (
        id TEXT PRIMARY KEY,
        communication_id TEXT,
        mention_text TEXT,
        entity_type TEXT,
        tracker_person_id TEXT,
        tracker_org_id TEXT,
        proposed_name TEXT,
        confidence REAL,
        confirmed INTEGER DEFAULT 0,
        mention_count INTEGER DEFAULT 1,
        context_snippet TEXT
    )""")
    db.execute("""CREATE TABLE ai_extractions (
        id TEXT PRIMARY KEY,
        communication_id TEXT,
        attempt_number INTEGER DEFAULT 1,
        model_used TEXT,
        prompt_version TEXT,
        system_prompt TEXT,
        user_prompt TEXT,
        raw_output TEXT,
        input_tokens INTEGER,
        output_tokens INTEGER,
        processing_seconds REAL,
        tracker_context_snapshot TEXT,
        escalation_reason TEXT,
        success INTEGER DEFAULT 1,
        extracted_at TEXT DEFAULT (datetime('now'))
    )""")
    db.execute("""CREATE TABLE review_bundles (
        id TEXT PRIMARY KEY,
        communication_id TEXT,
        bundle_type TEXT,
        target_matter_id TEXT,
        target_matter_title TEXT,
        proposed_matter_json TEXT,
        status TEXT DEFAULT 'proposed',
        confidence REAL,
        rationale TEXT,
        intelligence_notes TEXT,
        sort_order INTEGER,
        reviewed_by TEXT,
        reviewed_at TEXT,
        created_at TEXT DEFAULT (datetime('now'))
    )""")
    db.execute("""CREATE TABLE review_bundle_items (
        id TEXT PRIMARY KEY,
        bundle_id TEXT,
        item_type TEXT,
        status TEXT DEFAULT 'proposed',
        proposed_data TEXT,
        original_proposed_data TEXT,
        confidence REAL,
        rationale TEXT,
        source_excerpt TEXT,
        source_transcript_id TEXT,
        source_start_time REAL,
        source_end_time REAL,
        source_locator_json TEXT,
        sort_order INTEGER,
        moved_from_bundle_id TEXT,
        created_at TEXT DEFAULT (datetime('now'))
    )""")
    db.execute("""CREATE TABLE llm_usage (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        communication_id TEXT,
        stage TEXT,
        model TEXT,
        input_tokens INTEGER,
        output_tokens INTEGER,
        cost_usd REAL,
        created_at TEXT DEFAULT (datetime('now'))
    )""")
    db.commit()
    return db


def _seed_communication(db, comm_id, duration=300, num_segments=50):
    """Seed a communication with transcript data."""
    db.execute(
        "INSERT INTO communications (id, duration_seconds) VALUES (?, ?)",
        (comm_id, duration),
    )
    for i in range(num_segments):
        db.execute(
            "INSERT INTO transcripts (id, communication_id, speaker_label, "
            "start_time, end_time, cleaned_text) VALUES (?, ?, ?, ?, ?, ?)",
            (str(uuid.uuid4()), comm_id, f"SPEAKER_{i % 3:02d}",
             i * 6.0, (i + 1) * 6.0, f"Test segment {i}"),
        )
    db.execute(
        "INSERT INTO communication_participants "
        "(id, communication_id, speaker_label, proposed_name) VALUES (?, ?, ?, ?)",
        (str(uuid.uuid4()), comm_id, "SPEAKER_00", "John Smith"),
    )
    db.commit()


def _make_extraction_output(
    comm_id,
    num_bundles=2,
    bundle_type="matter",
    confidence=0.85,
    uncertainty_flags=None,
):
    """Build a mock ExtractionOutput."""
    bundles = []
    for i in range(num_bundles):
        items = [ExtractionItem(
            item_type="task",
            proposed_data={"title": f"Task {i}", "matter_id": f"matter-{i}"},
            confidence=confidence,
            rationale=f"Test rationale {i}",
            source_excerpt=f"Test excerpt {i}",
            source_segments=[str(uuid.uuid4())],
            source_time_range=SourceTimeRange(start=i * 60.0, end=(i + 1) * 60.0),
        )]
        bundles.append(ExtractionBundle(
            bundle_type=bundle_type,
            target_matter_id=f"matter-{i}" if bundle_type == "matter" else None,
            target_matter_title=f"Test Matter {i}",
            confidence=confidence,
            rationale=f"Bundle rationale {i}",
            uncertainty_flags=uncertainty_flags or [],
            items=items,
        ))
    return ExtractionOutput(
        communication_id=comm_id,
        extraction_summary="Test extraction",
        bundles=bundles,
    )


def _make_sonnet_result(
    success=True,
    comm_id="test-comm",
    confidence=0.85,
    num_bundles=2,
    bundle_type="matter",
    uncertainty_flags=None,
    failure_type=None,
    failure_detail=None,
):
    """Build a mock ExtractionAttemptResult for Sonnet."""
    if success:
        extraction = _make_extraction_output(
            comm_id, num_bundles, bundle_type, confidence, uncertainty_flags,
        )
        return ExtractionAttemptResult(
            success=True,
            model="claude-sonnet-4-20250514",
            attempt_number=1,
            raw_output=json.dumps({"bundles": []}),
            parsed_output=extraction,
            processed={"bundles": extraction.bundles, "post_processing_log": {
                "code_suppressed_items": [], "dedup_warnings": [],
                "invalid_references_cleaned": [],
            }},
            usage_data={"input_tokens": 1000, "output_tokens": 500,
                        "processing_seconds": 3.0, "cost_usd": 0.0105,
                        "total_cost_usd": 0.0105},
        )
    else:
        return ExtractionAttemptResult(
            success=False,
            model="claude-sonnet-4-20250514",
            attempt_number=3,
            raw_output="invalid json{{{",
            failure_type=failure_type or ExtractionFailureType.PARSE_FAILURE,
            failure_detail=failure_detail or "JSON parse error",
            usage_data={"total_cost_usd": 0.031},
        )


DEFAULT_POLICY = {
    "model_config": {
        "primary_extraction_model": "claude-sonnet-4-20250514",
        "escalation_model": "claude-opus-4-6",
        "opus_retry_triggers": {
            "low_confidence": True,
            "over_splitting": True,
            "uncertainty_flags": True,
            "validation_failure": True,
        },
        "daily_budget_usd": 10.0,
        "active_prompt_versions": {"extraction": "v1.0.0"},
    },
}


# ═══════════════════════════════════════════════════════════════════════════
# 1. Trigger detection tests
# ═══════════════════════════════════════════════════════════════════════════

class TestTriggerDetection:
    """Verify each escalation trigger fires correctly."""

    def test_no_triggers_on_good_extraction(self):
        """Successful high-confidence extraction triggers nothing."""
        db = _make_db()
        comm_id = str(uuid.uuid4())
        _seed_communication(db, comm_id)
        result = _make_sonnet_result(confidence=0.85, comm_id=comm_id)
        triggers = detect_triggers(result, db, comm_id, DEFAULT_POLICY)
        assert triggers == []

    def test_low_confidence_trigger(self):
        """Bundle with confidence < 0.5 fires low_confidence."""
        db = _make_db()
        comm_id = str(uuid.uuid4())
        _seed_communication(db, comm_id)
        result = _make_sonnet_result(confidence=0.3, comm_id=comm_id)
        triggers = detect_triggers(result, db, comm_id, DEFAULT_POLICY)
        assert EscalationTrigger.LOW_CONFIDENCE in triggers

    def test_over_splitting_trigger(self):
        """4+ new_matter bundles fires over_splitting."""
        db = _make_db()
        comm_id = str(uuid.uuid4())
        _seed_communication(db, comm_id)
        result = _make_sonnet_result(
            num_bundles=5, bundle_type="new_matter", comm_id=comm_id,
        )
        triggers = detect_triggers(result, db, comm_id, DEFAULT_POLICY)
        assert EscalationTrigger.OVER_SPLITTING in triggers

    def test_uncertainty_flags_trigger(self):
        """Sonnet self-reported uncertainty fires uncertainty_flags."""
        db = _make_db()
        comm_id = str(uuid.uuid4())
        _seed_communication(db, comm_id)
        result = _make_sonnet_result(
            uncertainty_flags=["Unsure about matter routing"],
            comm_id=comm_id,
        )
        triggers = detect_triggers(result, db, comm_id, DEFAULT_POLICY)
        assert EscalationTrigger.UNCERTAINTY_FLAGS in triggers

    def test_validation_failure_trigger(self):
        """Failed Sonnet result fires validation_failure."""
        db = _make_db()
        comm_id = str(uuid.uuid4())
        _seed_communication(db, comm_id)
        result = _make_sonnet_result(success=False, comm_id=comm_id)
        triggers = detect_triggers(result, db, comm_id, DEFAULT_POLICY)
        assert EscalationTrigger.VALIDATION_FAILURE in triggers

    def test_empty_extraction_trigger(self):
        """Zero bundles from substantial content fires empty_extraction."""
        db = _make_db()
        comm_id = str(uuid.uuid4())
        _seed_communication(db, comm_id, duration=300, num_segments=50)
        result = _make_sonnet_result(num_bundles=0, comm_id=comm_id)
        # Override to have 0 bundles
        result.parsed_output = ExtractionOutput(
            communication_id=comm_id,
            extraction_summary="Nothing found",
            bundles=[],
        )
        result.processed["bundles"] = []
        triggers = detect_triggers(result, db, comm_id, DEFAULT_POLICY)
        assert EscalationTrigger.EMPTY_EXTRACTION in triggers

    def test_empty_extraction_short_content_no_trigger(self):
        """Zero bundles from very short content does NOT trigger."""
        db = _make_db()
        comm_id = str(uuid.uuid4())
        _seed_communication(db, comm_id, duration=15, num_segments=3)
        result = _make_sonnet_result(num_bundles=0, comm_id=comm_id)
        result.parsed_output = ExtractionOutput(
            communication_id=comm_id,
            extraction_summary="Brief exchange",
            bundles=[],
        )
        result.processed["bundles"] = []
        triggers = detect_triggers(result, db, comm_id, DEFAULT_POLICY)
        assert EscalationTrigger.EMPTY_EXTRACTION not in triggers

    def test_disabled_trigger_not_detected(self):
        """Disabled trigger in config is not detected."""
        db = _make_db()
        comm_id = str(uuid.uuid4())
        _seed_communication(db, comm_id)
        result = _make_sonnet_result(confidence=0.3, comm_id=comm_id)
        policy = {
            "model_config": {
                **DEFAULT_POLICY["model_config"],
                "opus_retry_triggers": {
                    "low_confidence": False,  # disabled
                    "over_splitting": True,
                    "uncertainty_flags": True,
                    "validation_failure": True,
                },
            },
        }
        triggers = detect_triggers(result, db, comm_id, policy)
        # low_confidence disabled → should NOT appear in triggers
        assert EscalationTrigger.LOW_CONFIDENCE not in triggers


# ═══════════════════════════════════════════════════════════════════════════
# 2. Escalation decision tests
# ═══════════════════════════════════════════════════════════════════════════

class TestEscalationDecision:
    """Verify escalation decision logic."""

    def test_no_triggers_no_escalation(self):
        """No triggers → no escalation."""
        db = _make_db()
        decision = decide_escalation([], db, DEFAULT_POLICY)
        assert not decision.should_escalate
        assert decision.triggers == []

    def test_triggers_cause_escalation(self):
        """Enabled triggers → escalation."""
        db = _make_db()
        triggers = [EscalationTrigger.LOW_CONFIDENCE]
        decision = decide_escalation(triggers, db, DEFAULT_POLICY)
        assert decision.should_escalate
        assert EscalationTrigger.LOW_CONFIDENCE in decision.triggers

    def test_budget_blocks_escalation(self):
        """Budget exhausted → escalation blocked."""
        db = _make_db()
        # Spend the budget
        db.execute(
            "INSERT INTO llm_usage (communication_id, stage, model, "
            "input_tokens, output_tokens, cost_usd) VALUES (?, ?, ?, ?, ?, ?)",
            ("x", "test", "claude-sonnet-4-20250514", 100, 100, 15.0),
        )
        db.commit()
        triggers = [EscalationTrigger.LOW_CONFIDENCE]
        decision = decide_escalation(triggers, db, DEFAULT_POLICY)
        assert not decision.should_escalate
        assert decision.blocked_by_budget

    def test_no_escalation_model_blocks(self):
        """Missing escalation_model in config → blocked."""
        db = _make_db()
        policy = {"model_config": {"opus_retry_triggers": {}, "daily_budget_usd": 10.0}}
        triggers = [EscalationTrigger.VALIDATION_FAILURE]
        decision = decide_escalation(triggers, db, policy)
        assert not decision.should_escalate
        assert decision.blocked_by_config

    def test_all_triggers_disabled_blocks(self):
        """All triggered flags disabled → blocked by config."""
        db = _make_db()
        policy = {
            "model_config": {
                "escalation_model": "claude-opus-4-6",
                "opus_retry_triggers": {"low_confidence": False},
                "daily_budget_usd": 10.0,
            },
        }
        triggers = [EscalationTrigger.LOW_CONFIDENCE]
        decision = decide_escalation(triggers, db, policy)
        assert not decision.should_escalate
        assert decision.blocked_by_config


# ═══════════════════════════════════════════════════════════════════════════
# 3. Meta-instruction builder tests
# ═══════════════════════════════════════════════════════════════════════════

class TestMetaInstruction:
    """Verify Opus meta-instruction construction."""

    def test_includes_trigger_descriptions(self):
        """Each trigger type produces relevant instruction text."""
        result = _make_sonnet_result()
        for trigger in [EscalationTrigger.LOW_CONFIDENCE,
                        EscalationTrigger.OVER_SPLITTING,
                        EscalationTrigger.UNCERTAINTY_FLAGS,
                        EscalationTrigger.VALIDATION_FAILURE,
                        EscalationTrigger.EMPTY_EXTRACTION]:
            instruction = build_opus_meta_instruction([trigger], result)
            assert "Escalation Context" in instruction
            assert "Issues Detected" in instruction
            assert len(instruction) > 100

    def test_includes_sonnet_output(self):
        """Meta-instruction includes Sonnet's raw output."""
        result = _make_sonnet_result()
        result.raw_output = '{"bundles": [{"test": true}]}'
        instruction = build_opus_meta_instruction(
            [EscalationTrigger.LOW_CONFIDENCE], result,
        )
        assert "Previous Attempt Output" in instruction
        assert '"test": true' in instruction

    def test_truncates_long_output(self):
        """Very long Sonnet output is truncated."""
        result = _make_sonnet_result()
        result.raw_output = "x" * 20000
        instruction = build_opus_meta_instruction(
            [EscalationTrigger.LOW_CONFIDENCE], result,
        )
        assert "[truncated]" in instruction

    def test_multiple_triggers(self):
        """Multiple triggers all appear in instruction."""
        result = _make_sonnet_result()
        triggers = [
            EscalationTrigger.LOW_CONFIDENCE,
            EscalationTrigger.OVER_SPLITTING,
        ]
        instruction = build_opus_meta_instruction(triggers, result)
        assert "Low confidence" in instruction
        assert "Over-splitting" in instruction


# ═══════════════════════════════════════════════════════════════════════════
# 4. Full extraction flow tests (mocked LLM)
# ═══════════════════════════════════════════════════════════════════════════

def _good_extraction_json(comm_id):
    """Return a valid extraction JSON string."""
    return json.dumps({
        "extraction_version": "1.0.0",
        "communication_id": comm_id,
        "extraction_summary": "Test",
        "bundles": [{
            "bundle_type": "matter",
            "target_matter_id": "m-1",
            "target_matter_title": "Test Matter",
            "confidence": 0.85,
            "rationale": "Strong match",
            "items": [{
                "item_type": "task",
                "proposed_data": {"title": "Draft memo", "matter_id": "m-1"},
                "confidence": 0.9,
                "rationale": "Explicit delegation",
                "source_excerpt": "Can you draft the memo?",
                "source_segments": ["seg-1"],
                "source_time_range": {"start": 10.0, "end": 25.0},
            }],
        }],
    })


def _low_confidence_extraction_json(comm_id):
    """Return extraction with low-confidence bundle."""
    return json.dumps({
        "extraction_version": "1.0.0",
        "communication_id": comm_id,
        "extraction_summary": "Uncertain",
        "bundles": [{
            "bundle_type": "matter",
            "target_matter_id": "m-1",
            "target_matter_title": "Possibly this matter",
            "confidence": 0.3,
            "rationale": "Weak signals",
            "uncertainty_flags": ["Not sure about routing"],
            "items": [{
                "item_type": "matter_update",
                "proposed_data": {"summary": "Something mentioned", "matter_id": "m-1"},
                "confidence": 0.4,
                "rationale": "Low confidence",
                "source_excerpt": "They mentioned something about...",
                "source_segments": ["seg-1"],
                "source_time_range": {"start": 0.0, "end": 30.0},
            }],
        }],
    })


def _make_llm_response(text, model="claude-sonnet-4-20250514", cost=0.01):
    """Build a mock LLMResponse."""
    return LLMResponse(
        text=text,
        usage=LLMUsage(
            model=model,
            input_tokens=5000,
            output_tokens=2000,
            cost_usd=cost,
            processing_seconds=3.0,
        ),
        stop_reason="end_turn",
    )


class TestFullExtractionFlow:
    """Test the complete extraction + escalation pipeline (mocked LLM)."""

    @patch("app.pipeline.stages.extraction._fetch_tracker_context", new_callable=AsyncMock)
    @patch("app.pipeline.stages.extraction.call_llm", new_callable=AsyncMock)
    @patch("app.pipeline.stages.extraction._load_system_prompt")
    @patch("app.config.load_policy")
    @patch("app.routers.events.publish_event", new_callable=AsyncMock)
    def test_normal_sonnet_success_no_escalation(
        self, mock_publish, mock_policy, mock_prompt, mock_llm, mock_ctx,
    ):
        """Path 1: Sonnet succeeds cleanly, no escalation triggers."""
        db = _make_db()
        comm_id = str(uuid.uuid4())
        _seed_communication(db, comm_id)

        mock_policy.return_value = DEFAULT_POLICY
        mock_prompt.return_value = "system prompt"
        mock_ctx.return_value = {"matters": [], "people": [], "organizations": [],
                                 "recent_meetings": [], "standalone_tasks": []}
        mock_llm.return_value = _make_llm_response(
            _good_extraction_json(comm_id),
        )

        from app.pipeline.stages.extraction import run_extraction_stage
        result = _run(run_extraction_stage(db, comm_id))

        assert result["bundles_created"] == 1
        assert result["escalated"] == False
        assert result["escalation_triggers"] == []
        assert result["model_used"] == "claude-sonnet-4-20250514"

        # Check audit trail
        extractions = db.execute(
            "SELECT * FROM ai_extractions WHERE communication_id = ?",
            (comm_id,),
        ).fetchall()
        assert len(extractions) == 1
        assert extractions[0]["model_used"] == "claude-sonnet-4-20250514"
        assert extractions[0]["success"] == 1
        assert extractions[0]["escalation_reason"] is None

    @patch("app.pipeline.stages.extraction._fetch_tracker_context", new_callable=AsyncMock)
    @patch("app.pipeline.stages.extraction.call_llm", new_callable=AsyncMock)
    @patch("app.pipeline.stages.extraction._load_system_prompt")
    @patch("app.config.load_policy")
    @patch("app.routers.events.publish_event", new_callable=AsyncMock)
    def test_sonnet_retry_on_parse_failure(
        self, mock_publish, mock_policy, mock_prompt, mock_llm, mock_ctx,
    ):
        """Path 2: Sonnet parse fails, retries, succeeds on attempt 2."""
        db = _make_db()
        comm_id = str(uuid.uuid4())
        _seed_communication(db, comm_id)

        mock_policy.return_value = DEFAULT_POLICY
        mock_prompt.return_value = "system prompt"
        mock_ctx.return_value = {"matters": [], "people": [], "organizations": [],
                                 "recent_meetings": [], "standalone_tasks": []}

        call_count = [0]
        def side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return _make_llm_response("not valid json {{{")
            return _make_llm_response(_good_extraction_json(comm_id))

        mock_llm.side_effect = side_effect

        from app.pipeline.stages.extraction import run_extraction_stage
        result = _run(run_extraction_stage(db, comm_id))

        assert result["bundles_created"] == 1
        assert result["attempt_number"] == 2  # succeeded on retry
        assert result["escalated"] == False

    @patch("app.pipeline.stages.extraction._fetch_tracker_context", new_callable=AsyncMock)
    @patch("app.pipeline.stages.extraction.call_llm", new_callable=AsyncMock)
    @patch("app.pipeline.stages.extraction._load_system_prompt")
    @patch("app.config.load_policy")
    @patch("app.routers.events.publish_event", new_callable=AsyncMock)
    def test_opus_escalation_on_low_confidence(
        self, mock_publish, mock_policy, mock_prompt, mock_llm, mock_ctx,
    ):
        """Path 3: Sonnet succeeds with low confidence → Opus escalation."""
        db = _make_db()
        comm_id = str(uuid.uuid4())
        _seed_communication(db, comm_id)

        mock_policy.return_value = DEFAULT_POLICY
        mock_prompt.return_value = "system prompt"
        mock_ctx.return_value = {"matters": [], "people": [], "organizations": [],
                                 "recent_meetings": [], "standalone_tasks": []}

        call_count = [0]
        def side_effect(*args, **kwargs):
            call_count[0] += 1
            model = kwargs.get("model", args[4] if len(args) > 4 else "")
            if "opus" in model:
                # Opus returns high-confidence result
                return _make_llm_response(
                    _good_extraction_json(comm_id),
                    model="claude-opus-4-6", cost=2.50,
                )
            # Sonnet returns low-confidence
            return _make_llm_response(
                _low_confidence_extraction_json(comm_id),
            )

        mock_llm.side_effect = side_effect

        from app.pipeline.stages.extraction import run_extraction_stage
        result = _run(run_extraction_stage(db, comm_id))

        assert result["escalated"] == True
        assert "low_confidence" in result["escalation_triggers"]
        assert result["model_used"] == "claude-opus-4-6"

        # Audit trail: should have 2 extraction records
        extractions = db.execute(
            "SELECT * FROM ai_extractions WHERE communication_id = ? "
            "ORDER BY attempt_number",
            (comm_id,),
        ).fetchall()
        assert len(extractions) == 2
        # Sonnet record (not final)
        assert extractions[0]["model_used"] == "claude-sonnet-4-20250514"
        assert extractions[0]["success"] == 0
        # Opus record (final)
        assert extractions[1]["model_used"] == "claude-opus-4-6"
        assert extractions[1]["success"] == 1
        assert extractions[1]["escalation_reason"] is not None
        assert "low_confidence" in extractions[1]["escalation_reason"]

    @patch("app.pipeline.stages.extraction._fetch_tracker_context", new_callable=AsyncMock)
    @patch("app.pipeline.stages.extraction.call_llm", new_callable=AsyncMock)
    @patch("app.pipeline.stages.extraction._load_system_prompt")
    @patch("app.config.load_policy")
    @patch("app.routers.events.publish_event", new_callable=AsyncMock)
    def test_all_attempts_fail_terminal_error(
        self, mock_publish, mock_policy, mock_prompt, mock_llm, mock_ctx,
    ):
        """Path 4: Sonnet fails, Opus fails → terminal RuntimeError."""
        db = _make_db()
        comm_id = str(uuid.uuid4())
        _seed_communication(db, comm_id)

        mock_policy.return_value = DEFAULT_POLICY
        mock_prompt.return_value = "system prompt"
        mock_ctx.return_value = {"matters": [], "people": [], "organizations": [],
                                 "recent_meetings": [], "standalone_tasks": []}

        # All calls return invalid JSON
        mock_llm.return_value = _make_llm_response("not valid json {{{")

        from app.pipeline.stages.extraction import run_extraction_stage
        with pytest.raises(RuntimeError, match="Extraction failed"):
            _run(run_extraction_stage(db, comm_id))

    @patch("app.pipeline.stages.extraction._fetch_tracker_context", new_callable=AsyncMock)
    @patch("app.pipeline.stages.extraction.call_llm", new_callable=AsyncMock)
    @patch("app.pipeline.stages.extraction._load_system_prompt")
    @patch("app.config.load_policy")
    @patch("app.routers.events.publish_event", new_callable=AsyncMock)
    def test_budget_blocks_opus_falls_back_to_sonnet(
        self, mock_publish, mock_policy, mock_prompt, mock_llm, mock_ctx,
    ):
        """Path 5: Sonnet low-confidence, budget blocks Opus → use Sonnet."""
        db = _make_db()
        comm_id = str(uuid.uuid4())
        _seed_communication(db, comm_id)

        # Exhaust budget
        db.execute(
            "INSERT INTO llm_usage (communication_id, stage, model, "
            "input_tokens, output_tokens, cost_usd) VALUES (?, ?, ?, ?, ?, ?)",
            ("x", "test", "claude-sonnet-4-20250514", 100, 100, 15.0),
        )
        db.commit()

        mock_policy.return_value = DEFAULT_POLICY
        mock_prompt.return_value = "system prompt"
        mock_ctx.return_value = {"matters": [], "people": [], "organizations": [],
                                 "recent_meetings": [], "standalone_tasks": []}
        mock_llm.return_value = _make_llm_response(
            _low_confidence_extraction_json(comm_id),
        )

        from app.pipeline.stages.extraction import run_extraction_stage
        result = _run(run_extraction_stage(db, comm_id))

        # Should still succeed with Sonnet result
        assert result["bundles_created"] >= 1
        assert result["escalated"] == False
        assert result["model_used"] == "claude-sonnet-4-20250514"

    @patch("app.pipeline.stages.extraction._fetch_tracker_context", new_callable=AsyncMock)
    @patch("app.pipeline.stages.extraction.call_llm", new_callable=AsyncMock)
    @patch("app.pipeline.stages.extraction._load_system_prompt")
    @patch("app.config.load_policy")
    @patch("app.routers.events.publish_event", new_callable=AsyncMock)
    def test_opus_fails_falls_back_to_sonnet(
        self, mock_publish, mock_policy, mock_prompt, mock_llm, mock_ctx,
    ):
        """Opus fails → fall back to Sonnet result."""
        db = _make_db()
        comm_id = str(uuid.uuid4())
        _seed_communication(db, comm_id)

        mock_policy.return_value = DEFAULT_POLICY
        mock_prompt.return_value = "system prompt"
        mock_ctx.return_value = {"matters": [], "people": [], "organizations": [],
                                 "recent_meetings": [], "standalone_tasks": []}

        call_count = [0]
        def side_effect(*args, **kwargs):
            call_count[0] += 1
            model = kwargs.get("model", "")
            if "opus" in model:
                return _make_llm_response("opus invalid {{{",
                                          model="claude-opus-4-6")
            return _make_llm_response(
                _low_confidence_extraction_json(comm_id),
            )

        mock_llm.side_effect = side_effect

        from app.pipeline.stages.extraction import run_extraction_stage
        result = _run(run_extraction_stage(db, comm_id))

        # Fell back to Sonnet
        assert result["bundles_created"] >= 1
        assert result["escalated"] == False


# ═══════════════════════════════════════════════════════════════════════════
# 5. Audit trail tests
# ═══════════════════════════════════════════════════════════════════════════

class TestAuditTrail:
    """Verify extraction records reflect escalation decisions."""

    @patch("app.pipeline.stages.extraction._fetch_tracker_context", new_callable=AsyncMock)
    @patch("app.pipeline.stages.extraction.call_llm", new_callable=AsyncMock)
    @patch("app.pipeline.stages.extraction._load_system_prompt")
    @patch("app.config.load_policy")
    @patch("app.routers.events.publish_event", new_callable=AsyncMock)
    def test_successful_escalation_records_both(
        self, mock_publish, mock_policy, mock_prompt, mock_llm, mock_ctx,
    ):
        """Successful Opus escalation persists both Sonnet and Opus records."""
        db = _make_db()
        comm_id = str(uuid.uuid4())
        _seed_communication(db, comm_id)

        mock_policy.return_value = DEFAULT_POLICY
        mock_prompt.return_value = "system prompt"
        mock_ctx.return_value = {"matters": [], "people": [], "organizations": [],
                                 "recent_meetings": [], "standalone_tasks": []}

        call_count = [0]
        def side_effect(*args, **kwargs):
            call_count[0] += 1
            model = kwargs.get("model", "")
            if "opus" in model:
                return _make_llm_response(
                    _good_extraction_json(comm_id),
                    model="claude-opus-4-6", cost=2.50,
                )
            return _make_llm_response(
                _low_confidence_extraction_json(comm_id),
            )

        mock_llm.side_effect = side_effect

        from app.pipeline.stages.extraction import run_extraction_stage
        _run(run_extraction_stage(db, comm_id))

        records = db.execute(
            "SELECT model_used, attempt_number, escalation_reason, success "
            "FROM ai_extractions WHERE communication_id = ? "
            "ORDER BY attempt_number",
            (comm_id,),
        ).fetchall()

        assert len(records) == 2
        # Sonnet
        assert records[0]["model_used"] == "claude-sonnet-4-20250514"
        assert records[0]["success"] == 0
        assert records[0]["escalation_reason"] is None
        # Opus
        assert records[1]["model_used"] == "claude-opus-4-6"
        assert records[1]["success"] == 1
        assert "low_confidence" in records[1]["escalation_reason"]

    @patch("app.pipeline.stages.extraction._fetch_tracker_context", new_callable=AsyncMock)
    @patch("app.pipeline.stages.extraction.call_llm", new_callable=AsyncMock)
    @patch("app.pipeline.stages.extraction._load_system_prompt")
    @patch("app.config.load_policy")
    @patch("app.routers.events.publish_event", new_callable=AsyncMock)
    def test_escalation_records_both_models_in_ai_extractions(
        self, mock_publish, mock_policy, mock_prompt, mock_llm, mock_ctx,
    ):
        """Escalation persists both Sonnet and Opus in ai_extractions with correct models."""
        db = _make_db()
        comm_id = str(uuid.uuid4())
        _seed_communication(db, comm_id)

        mock_policy.return_value = DEFAULT_POLICY
        mock_prompt.return_value = "system prompt"
        mock_ctx.return_value = {"matters": [], "people": [], "organizations": [],
                                 "recent_meetings": [], "standalone_tasks": []}

        def side_effect(*args, **kwargs):
            model = kwargs.get("model", "")
            if "opus" in model:
                return _make_llm_response(
                    _good_extraction_json(comm_id),
                    model="claude-opus-4-6", cost=2.50,
                )
            return _make_llm_response(
                _low_confidence_extraction_json(comm_id),
            )

        mock_llm.side_effect = side_effect

        from app.pipeline.stages.extraction import run_extraction_stage
        _run(run_extraction_stage(db, comm_id))

        records = db.execute(
            "SELECT model_used, attempt_number, success, escalation_reason "
            "FROM ai_extractions WHERE communication_id = ? "
            "ORDER BY attempt_number",
            (comm_id,),
        ).fetchall()

        models = [r["model_used"] for r in records]
        assert len(records) == 2
        assert "claude-sonnet-4-20250514" in models
        assert "claude-opus-4-6" in models
        # Sonnet marked as non-authoritative, Opus as authoritative
        assert records[0]["success"] == 0
        assert records[1]["success"] == 1


# ═══════════════════════════════════════════════════════════════════════════
# 6. Regression tests — Phase 4B/4C/writeback unaffected
# ═══════════════════════════════════════════════════════════════════════════

class TestRegression:
    """Verify existing Phase 4B behavior is preserved."""

    def test_extraction_models_unchanged(self):
        """ExtractionOutput model structure unchanged."""
        from app.pipeline.stages.extraction_models import (
            VALID_BUNDLE_TYPES, VALID_ITEM_TYPES,
        )
        assert VALID_BUNDLE_TYPES == {"matter", "new_matter", "standalone"}
        assert "task" in VALID_ITEM_TYPES
        assert "meeting_record" in VALID_ITEM_TYPES

    def test_escalation_module_imports(self):
        """Escalation module imports cleanly."""
        from app.pipeline.stages.escalation import (
            EscalationTrigger,
        )
        assert EscalationTrigger.LOW_CONFIDENCE.value == "low_confidence"

    def test_bundle_review_models_unchanged(self):
        """Bundle review models still work."""
        from app.bundle_review.models import (
            BUNDLE_REVIEW_STATES, BUNDLE_TERMINAL,
        )
        assert "awaiting_bundle_review" in BUNDLE_REVIEW_STATES
        assert "accepted" in BUNDLE_TERMINAL

    def test_writeback_ordering_unchanged(self):
        """Writeback ordering unchanged."""
        from app.writeback.ordering import ITEM_TYPE_ORDER
        assert ITEM_TYPE_ORDER["new_organization"] == 0
        assert ITEM_TYPE_ORDER["new_person"] == 1


# ═══════════════════════════════════════════════════════════════════════════
# Entry point
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
