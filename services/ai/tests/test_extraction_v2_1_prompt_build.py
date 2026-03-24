"""Prompt-construction tests for v2.1 extraction inputs."""

import sqlite3

from app.pipeline.stages.extraction import _build_user_prompt


def _make_db() -> sqlite3.Connection:
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row

    db.execute("""
        CREATE TABLE communications (
            id TEXT PRIMARY KEY,
            source_type TEXT,
            original_filename TEXT,
            duration_seconds REAL,
            topic_segments_json TEXT,
            sensitivity_flags TEXT,
            created_at TEXT
        )
    """)
    db.execute("""
        CREATE TABLE communication_participants (
            communication_id TEXT,
            speaker_label TEXT,
            tracker_person_id TEXT,
            proposed_name TEXT,
            proposed_title TEXT,
            proposed_org TEXT,
            participant_email TEXT,
            header_role TEXT,
            participant_role TEXT
        )
    """)
    db.execute("""
        CREATE TABLE communication_entities (
            communication_id TEXT,
            mention_text TEXT,
            entity_type TEXT,
            tracker_person_id TEXT,
            tracker_org_id TEXT,
            proposed_name TEXT,
            confidence REAL,
            confirmed INTEGER,
            mention_count INTEGER,
            context_snippet TEXT
        )
    """)
    db.execute("""
        CREATE TABLE transcripts (
            id TEXT PRIMARY KEY,
            communication_id TEXT,
            speaker_label TEXT,
            start_time REAL,
            end_time REAL,
            raw_text TEXT,
            cleaned_text TEXT,
            enriched_text TEXT,
            word_timestamps TEXT,
            confidence REAL,
            created_at TEXT,
            reviewed_text TEXT
        )
    """)
    return db


def _tiered_context() -> dict:
    return {
        "tier_1_matters": [],
        "tier_2_matters": [],
        "tier_1_meetings": [],
        "people": [],
        "organizations": [],
        "standalone_tasks": [],
    }


def _policy() -> dict:
    return {
        "model_config": {"primary_extraction_model": "claude-sonnet-4-20250514"},
        "extraction_policy": {},
    }


def test_build_user_prompt_prefers_reviewed_text_for_audio_transcripts():
    db = _make_db()
    db.execute("""
        INSERT INTO communications
            (id, source_type, original_filename, duration_seconds, topic_segments_json, sensitivity_flags, created_at)
        VALUES
            ('comm-1', 'audio_upload', 'sample.m4a', 120, NULL, NULL, '2026-03-24 10:00:00')
    """)
    db.execute("""
        INSERT INTO communication_participants
            (communication_id, speaker_label, tracker_person_id, proposed_name, proposed_title, proposed_org,
             participant_email, header_role, participant_role)
        VALUES
            ('comm-1', 'SPEAKER_00', 'person-1', 'Tyler Badgley', 'Counsel', 'CFTC', NULL, NULL, NULL)
    """)
    db.execute("""
        INSERT INTO transcripts
            (id, communication_id, speaker_label, start_time, end_time, raw_text, cleaned_text, enriched_text,
             word_timestamps, confidence, created_at, reviewed_text)
        VALUES
            ('seg-1', 'comm-1', 'SPEAKER_00', 0, 10, 'raw transcript text', 'cleaned transcript text',
             'topic label text that should not be used', NULL, 0.98, '2026-03-24 10:00:00', 'reviewed transcript text')
    """)

    prompt = _build_user_prompt(db, "comm-1", _tiered_context(), _policy())

    assert "reviewed transcript text" in prompt
    assert "topic label text that should not be used" not in prompt
    assert "cleaned transcript text" not in prompt
    assert "raw transcript text" not in prompt


def test_build_user_prompt_falls_back_to_cleaned_text_when_reviewed_missing():
    db = _make_db()
    db.execute("""
        INSERT INTO communications
            (id, source_type, original_filename, duration_seconds, topic_segments_json, sensitivity_flags, created_at)
        VALUES
            ('comm-2', 'audio_upload', 'sample-2.m4a', 90, NULL, NULL, '2026-03-24 11:00:00')
    """)
    db.execute("""
        INSERT INTO communication_participants
            (communication_id, speaker_label, tracker_person_id, proposed_name, proposed_title, proposed_org,
             participant_email, header_role, participant_role)
        VALUES
            ('comm-2', 'SPEAKER_01', 'person-2', 'Stephen Andrews', 'Chairman', 'CFTC', NULL, NULL, NULL)
    """)
    db.execute("""
        INSERT INTO transcripts
            (id, communication_id, speaker_label, start_time, end_time, raw_text, cleaned_text, enriched_text,
             word_timestamps, confidence, created_at, reviewed_text)
        VALUES
            ('seg-2', 'comm-2', 'SPEAKER_01', 0, 8, 'raw transcript fallback', 'cleaned transcript fallback',
             'topic label fallback', NULL, 0.99, '2026-03-24 11:00:00', NULL)
    """)

    prompt = _build_user_prompt(db, "comm-2", _tiered_context(), _policy())

    assert "cleaned transcript fallback" in prompt
    assert "topic label fallback" not in prompt
    assert "raw transcript fallback" not in prompt
