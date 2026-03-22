"""CFTC Intake Service -- database schema.

Speaker identity is owned by the Tracker service (people table).
This service only stores audio-domain data (voiceprints, mappings)
keyed by tracker_person_id.
"""

import logging
import sqlite3
from pathlib import Path

from config import DB_PATH

logger = logging.getLogger(__name__)

SCHEMA_SQL = """
-- Core pipeline tables

CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    file_path TEXT,
    processing_status TEXT DEFAULT 'pending',
    duration_seconds REAL,
    title TEXT,
    speakers_confirmed BOOLEAN DEFAULT 0,
    created_at DATETIME DEFAULT (datetime('now')),
    updated_at DATETIME DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS audio_files (
    id TEXT PRIMARY KEY,
    conversation_id TEXT REFERENCES conversations(id),
    file_path TEXT NOT NULL,
    original_filename TEXT,
    source TEXT,
    format TEXT,
    duration_seconds REAL,
    file_size_bytes INTEGER,
    captured_at DATETIME,
    created_at DATETIME DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS transcripts (
    id TEXT PRIMARY KEY,
    conversation_id TEXT REFERENCES conversations(id),
    speaker_label TEXT,
    speaker_id TEXT,
    start_time REAL,
    end_time REAL,
    text TEXT,
    word_timestamps TEXT,
    original_text TEXT,
    user_corrected BOOLEAN DEFAULT 0,
    confidence REAL,
    created_at DATETIME DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS voice_samples (
    id TEXT PRIMARY KEY,
    source_conversation_id TEXT REFERENCES conversations(id),
    speaker_label TEXT,
    embedding BLOB,
    created_at DATETIME DEFAULT (datetime('now'))
);

-- Speaker identity tables (keyed to Tracker people, not local known_speakers)

CREATE TABLE IF NOT EXISTS speaker_voice_profiles (
    id TEXT PRIMARY KEY,
    tracker_person_id TEXT NOT NULL,
    embedding BLOB NOT NULL,
    source_conversation_id TEXT REFERENCES conversations(id),
    quality_score REAL DEFAULT 0.0,
    created_at DATETIME DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS speaker_mappings (
    id TEXT PRIMARY KEY,
    conversation_id TEXT REFERENCES conversations(id),
    speaker_label TEXT NOT NULL,
    tracker_person_id TEXT NOT NULL,
    confidence REAL,
    method TEXT DEFAULT 'manual',
    confirmed BOOLEAN DEFAULT 0,
    created_at DATETIME DEFAULT (datetime('now')),
    updated_at DATETIME DEFAULT (datetime('now'))
);

-- Vocal analysis tables

CREATE TABLE IF NOT EXISTS vocal_features (
    id TEXT PRIMARY KEY,
    conversation_id TEXT REFERENCES conversations(id),
    speaker_label TEXT,
    pitch_mean REAL,
    pitch_std REAL,
    pitch_min REAL,
    pitch_max REAL,
    jitter REAL,
    shimmer REAL,
    hnr REAL,
    intensity_mean REAL,
    f1_mean REAL,
    f2_mean REAL,
    f3_mean REAL,
    mfcc_means TEXT,
    rms_mean REAL,
    spectral_centroid REAL,
    zcr_mean REAL,
    spectral_rolloff REAL,
    speaking_rate_wpm REAL,
    created_at DATETIME DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS vocal_baselines (
    id TEXT PRIMARY KEY,
    tracker_person_id TEXT NOT NULL UNIQUE,
    pitch_mean REAL,
    pitch_std REAL,
    jitter REAL,
    shimmer REAL,
    hnr REAL,
    speaking_rate_wpm REAL,
    spectral_centroid REAL,
    rms_mean REAL,
    f1_mean REAL,
    f2_mean REAL,
    f3_mean REAL,
    sample_count INTEGER DEFAULT 0,
    last_updated DATETIME DEFAULT (datetime('now'))
);

-- Auto-advance audit

CREATE TABLE IF NOT EXISTS auto_advance_log (
    id TEXT PRIMARY KEY,
    conversation_id TEXT REFERENCES conversations(id),
    speaker_label TEXT,
    tracker_person_id TEXT,
    confidence REAL,
    method TEXT,
    created_at DATETIME DEFAULT (datetime('now'))
);

-- Voiceprint quality gate candidates

CREATE TABLE IF NOT EXISTS voiceprint_candidates (
    id TEXT PRIMARY KEY,
    conversation_id TEXT REFERENCES conversations(id),
    speaker_label TEXT NOT NULL,
    embedding BLOB,
    quality_score REAL DEFAULT 0.0,
    total_duration REAL,
    segment_count INTEGER,
    segment_ranges TEXT,
    metrics_summary TEXT,
    status TEXT DEFAULT 'pending',
    rejection_reason TEXT,
    created_at DATETIME DEFAULT (datetime('now')),
    reviewed_at DATETIME
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_transcripts_conversation ON transcripts(conversation_id);
CREATE INDEX IF NOT EXISTS idx_transcripts_speaker ON transcripts(conversation_id, speaker_label);
CREATE INDEX IF NOT EXISTS idx_audio_conversation ON audio_files(conversation_id);
CREATE INDEX IF NOT EXISTS idx_voice_samples_conversation ON voice_samples(source_conversation_id);
CREATE INDEX IF NOT EXISTS idx_speaker_profiles_person ON speaker_voice_profiles(tracker_person_id);
CREATE INDEX IF NOT EXISTS idx_speaker_mappings_conversation ON speaker_mappings(conversation_id);
CREATE INDEX IF NOT EXISTS idx_vocal_features_conversation ON vocal_features(conversation_id);
CREATE INDEX IF NOT EXISTS idx_vocal_baselines_person ON vocal_baselines(tracker_person_id);
CREATE INDEX IF NOT EXISTS idx_auto_advance_conversation ON auto_advance_log(conversation_id);
CREATE INDEX IF NOT EXISTS idx_voiceprint_candidates_conversation ON voiceprint_candidates(conversation_id);
CREATE INDEX IF NOT EXISTS idx_voiceprint_candidates_status ON voiceprint_candidates(status);
"""


def init_db(db_path: Path = DB_PATH):
    """Initialize the database schema."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.executescript(SCHEMA_SQL)
    conn.commit()
    conn.close()
    logger.info(f"Database initialized at {db_path}")
