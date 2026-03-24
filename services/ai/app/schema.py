"""
CFTC AI Layer — Database Schema for ai.db

18 spec tables + 2 hardening tables (commit_batches, review_action_log).
Processing lock/lease is on communications table (lock_token, locked_at, lock_expires_at).
Provenance locator is on review_bundle_items (source_locator_json).

Idempotent: CREATE TABLE/INDEX IF NOT EXISTS.
"""
import sqlite3
import logging

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Table definitions — spec tables 1-18 + hardening tables
# ---------------------------------------------------------------------------

TABLES = [
    # ---- Table 1: communications ----
    ("communications", """CREATE TABLE IF NOT EXISTS communications (
        id TEXT PRIMARY KEY,
        source_type TEXT NOT NULL,
        source_path TEXT,
        original_filename TEXT,
        title TEXT,
        processing_status TEXT NOT NULL DEFAULT 'pending',
        error_message TEXT,
        error_stage TEXT,
        duration_seconds REAL,
        topic_segments_json TEXT,
        source_metadata TEXT,
        sensitivity_flags TEXT,
        processing_lock_token TEXT,
        locked_at TEXT,
        lock_expires_at TEXT,
        archived_at TEXT,
        created_at TEXT DEFAULT (datetime('now')),
        updated_at TEXT DEFAULT (datetime('now'))
    )"""),

    # ---- Table 2: audio_files ----
    ("audio_files", """CREATE TABLE IF NOT EXISTS audio_files (
        id TEXT PRIMARY KEY,
        communication_id TEXT NOT NULL REFERENCES communications(id),
        file_path TEXT NOT NULL,
        original_filename TEXT,
        format TEXT,
        duration_seconds REAL,
        file_size_bytes INTEGER,
        captured_at TEXT,
        created_at TEXT DEFAULT (datetime('now'))
    )"""),

    # ---- Table 3: communication_participants ----
    ("communication_participants", """CREATE TABLE IF NOT EXISTS communication_participants (
        id TEXT PRIMARY KEY,
        communication_id TEXT NOT NULL REFERENCES communications(id),
        speaker_label TEXT,
        tracker_person_id TEXT,
        proposed_name TEXT,
        proposed_title TEXT,
        proposed_org TEXT,
        proposed_org_id TEXT,
        participant_role TEXT,
        participant_email TEXT,
        header_role TEXT,
        match_source TEXT,
        confirmed INTEGER DEFAULT 0,
        voiceprint_confidence REAL,
        voiceprint_method TEXT,
        created_at TEXT DEFAULT (datetime('now')),
        updated_at TEXT DEFAULT (datetime('now'))
    )"""),

    # ---- Table 4: transcripts ----
    ("transcripts", """CREATE TABLE IF NOT EXISTS transcripts (
        id TEXT PRIMARY KEY,
        communication_id TEXT NOT NULL REFERENCES communications(id),
        speaker_label TEXT,
        start_time REAL,
        end_time REAL,
        raw_text TEXT,
        cleaned_text TEXT,
        enriched_text TEXT,
        word_timestamps TEXT,
        confidence REAL,
        created_at TEXT DEFAULT (datetime('now'))
    )"""),

    # ---- Table 5: communication_entities ----
    ("communication_entities", """CREATE TABLE IF NOT EXISTS communication_entities (
        id TEXT PRIMARY KEY,
        communication_id TEXT NOT NULL REFERENCES communications(id),
        mention_text TEXT NOT NULL,
        entity_type TEXT NOT NULL,
        tracker_person_id TEXT,
        tracker_org_id TEXT,
        proposed_name TEXT,
        proposed_title TEXT,
        proposed_org TEXT,
        confidence REAL,
        confirmed INTEGER DEFAULT 0,
        mention_count INTEGER DEFAULT 1,
        first_mention_transcript_id TEXT REFERENCES transcripts(id),
        context_snippet TEXT,
        created_at TEXT DEFAULT (datetime('now')),
        updated_at TEXT DEFAULT (datetime('now'))
    )"""),

    # ---- Table 6: communication_messages (email) ----
    ("communication_messages", """CREATE TABLE IF NOT EXISTS communication_messages (
        id TEXT PRIMARY KEY,
        communication_id TEXT NOT NULL REFERENCES communications(id),
        message_index INTEGER NOT NULL,
        sender_email TEXT,
        sender_name TEXT,
        recipient_emails TEXT,
        cc_emails TEXT,
        timestamp TEXT,
        subject TEXT,
        body_text TEXT,
        enriched_text TEXT,
        message_hash TEXT NOT NULL,
        is_new INTEGER DEFAULT 1,
        is_from_user INTEGER DEFAULT 0,
        created_at TEXT DEFAULT (datetime('now'))
    )"""),

    # ---- Table 7: communication_artifacts (email attachments) ----
    ("communication_artifacts", """CREATE TABLE IF NOT EXISTS communication_artifacts (
        id TEXT PRIMARY KEY,
        communication_id TEXT NOT NULL REFERENCES communications(id),
        message_id TEXT REFERENCES communication_messages(id),
        original_filename TEXT NOT NULL,
        mime_type TEXT,
        file_size_bytes INTEGER,
        file_path TEXT NOT NULL,
        artifact_type TEXT NOT NULL DEFAULT 'attachment',
        extracted_text TEXT,
        text_extraction_status TEXT DEFAULT 'pending',
        is_document_proposable INTEGER DEFAULT 0,
        tracker_document_id TEXT,
        tracker_document_file_id TEXT,
        quarantine_reason TEXT,
        created_at TEXT DEFAULT (datetime('now'))
    )"""),

    # ---- Table 8: voice_samples ----
    ("voice_samples", """CREATE TABLE IF NOT EXISTS voice_samples (
        id TEXT PRIMARY KEY,
        communication_id TEXT REFERENCES communications(id),
        speaker_label TEXT,
        embedding BLOB,
        created_at TEXT DEFAULT (datetime('now'))
    )"""),

    # ---- Table 9: speaker_voice_profiles ----
    ("speaker_voice_profiles", """CREATE TABLE IF NOT EXISTS speaker_voice_profiles (
        id TEXT PRIMARY KEY,
        tracker_person_id TEXT NOT NULL,
        embedding BLOB NOT NULL,
        embedding_dimension INTEGER DEFAULT 192,
        quality_score REAL DEFAULT 0.0,
        sample_count INTEGER DEFAULT 1,
        total_speech_seconds REAL DEFAULT 0.0,
        status TEXT DEFAULT 'active',
        source_communication_id TEXT REFERENCES communications(id),
        created_from TEXT DEFAULT 'manual',
        created_at TEXT DEFAULT (datetime('now')),
        updated_at TEXT DEFAULT (datetime('now'))
    )"""),

    # ---- Table 9b: voiceprint_match_log ----
    ("voiceprint_match_log", """CREATE TABLE IF NOT EXISTS voiceprint_match_log (
        id TEXT PRIMARY KEY,
        communication_id TEXT NOT NULL REFERENCES communications(id),
        speaker_label TEXT NOT NULL,
        sample_embedding_id TEXT REFERENCES voice_samples(id),
        profiles_compared INTEGER DEFAULT 0,
        top_candidate_person_id TEXT,
        top_candidate_score REAL,
        candidate_list TEXT,
        threshold_used REAL,
        outcome TEXT NOT NULL,
        reviewer_action TEXT,
        confirmed_person_id TEXT,
        created_at TEXT DEFAULT (datetime('now')),
        reviewed_at TEXT
    )"""),

    # ---- Table 10: ai_extractions ----
    ("ai_extractions", """CREATE TABLE IF NOT EXISTS ai_extractions (
        id TEXT PRIMARY KEY,
        communication_id TEXT NOT NULL REFERENCES communications(id),
        attempt_number INTEGER DEFAULT 1,
        model_used TEXT NOT NULL,
        prompt_version TEXT NOT NULL,
        system_prompt TEXT,
        user_prompt TEXT,
        raw_output TEXT NOT NULL,
        input_tokens INTEGER,
        output_tokens INTEGER,
        processing_seconds REAL,
        tracker_context_snapshot TEXT,
        escalation_reason TEXT,
        success INTEGER DEFAULT 1,
        extracted_at TEXT DEFAULT (datetime('now'))
    )"""),

    # ---- Table 11: review_bundles ----
    ("review_bundles", """CREATE TABLE IF NOT EXISTS review_bundles (
        id TEXT PRIMARY KEY,
        communication_id TEXT NOT NULL REFERENCES communications(id),
        bundle_type TEXT NOT NULL,
        target_matter_id TEXT,
        target_matter_title TEXT,
        proposed_matter_json TEXT,
        status TEXT NOT NULL DEFAULT 'proposed',
        confidence REAL,
        rationale TEXT,
        intelligence_notes TEXT,
        sort_order INTEGER,
        reviewed_by TEXT,
        reviewed_at TEXT,
        created_at TEXT DEFAULT (datetime('now')),
        updated_at TEXT DEFAULT (datetime('now'))
    )"""),

    # ---- Table 12: review_bundle_items ----
    ("review_bundle_items", """CREATE TABLE IF NOT EXISTS review_bundle_items (
        id TEXT PRIMARY KEY,
        bundle_id TEXT NOT NULL REFERENCES review_bundles(id),
        item_type TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'proposed',
        proposed_data TEXT NOT NULL,
        original_proposed_data TEXT,
        confidence REAL,
        rationale TEXT,
        source_excerpt TEXT,
        source_transcript_id TEXT REFERENCES transcripts(id),
        source_start_time REAL,
        source_end_time REAL,
        source_locator_json TEXT,
        sort_order INTEGER,
        moved_from_bundle_id TEXT REFERENCES review_bundles(id),
        reviewed_at TEXT,
        created_at TEXT DEFAULT (datetime('now')),
        updated_at TEXT DEFAULT (datetime('now'))
    )"""),

    # ---- Table 13: tracker_writebacks ----
    ("tracker_writebacks", """CREATE TABLE IF NOT EXISTS tracker_writebacks (
        id TEXT PRIMARY KEY,
        communication_id TEXT NOT NULL REFERENCES communications(id),
        bundle_id TEXT NOT NULL REFERENCES review_bundles(id),
        bundle_item_id TEXT REFERENCES review_bundle_items(id),
        target_table TEXT NOT NULL,
        target_record_id TEXT NOT NULL,
        write_type TEXT NOT NULL,
        written_data TEXT NOT NULL,
        previous_data TEXT,
        auto_committed INTEGER DEFAULT 0,
        reversed INTEGER DEFAULT 0,
        reversed_at TEXT,
        written_at TEXT DEFAULT (datetime('now'))
    )"""),

    # ---- Table 14: config_audit_log ----
    ("config_audit_log", """CREATE TABLE IF NOT EXISTS config_audit_log (
        id TEXT PRIMARY KEY,
        section TEXT NOT NULL,
        field TEXT NOT NULL,
        old_value TEXT,
        new_value TEXT NOT NULL,
        created_at TEXT DEFAULT (datetime('now'))
    )"""),

    # ---- Table 15: digests ----
    ("digests", """CREATE TABLE IF NOT EXISTS digests (
        id TEXT PRIMARY KEY,
        digest_date TEXT NOT NULL,
        alert_data TEXT NOT NULL,
        narrative TEXT,
        communication_context TEXT,
        model_used TEXT,
        prompt_version TEXT,
        emailed INTEGER DEFAULT 0,
        emailed_at TEXT,
        created_at TEXT DEFAULT (datetime('now'))
    )"""),

    # ---- Table 16: intelligence_briefs ----
    ("intelligence_briefs", """CREATE TABLE IF NOT EXISTS intelligence_briefs (
        id TEXT PRIMARY KEY,
        brief_type TEXT NOT NULL,
        brief_date TEXT NOT NULL,
        content TEXT NOT NULL,
        input_context TEXT,
        model_used TEXT,
        prompt_version TEXT,
        is_auto_generated INTEGER DEFAULT 1,
        docx_file_path TEXT,
        created_at TEXT DEFAULT (datetime('now'))
    )"""),

    # ---- Table 17: alert_actions ----
    ("alert_actions", """CREATE TABLE IF NOT EXISTS alert_actions (
        id TEXT PRIMARY KEY,
        alert_fingerprint TEXT NOT NULL,
        action TEXT NOT NULL,
        snooze_until TEXT,
        created_at TEXT DEFAULT (datetime('now'))
    )"""),

    # ---- Table 18: llm_usage ----
    ("llm_usage", """CREATE TABLE IF NOT EXISTS llm_usage (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        communication_id TEXT REFERENCES communications(id),
        stage TEXT NOT NULL,
        model TEXT NOT NULL,
        input_tokens INTEGER NOT NULL,
        output_tokens INTEGER NOT NULL,
        cost_usd REAL NOT NULL,
        created_at TEXT DEFAULT (datetime('now'))
    )"""),

    # ---- Hardening: commit_batches (receipt tracking) ----
    ("commit_batches", """CREATE TABLE IF NOT EXISTS commit_batches (
        id TEXT PRIMARY KEY,
        communication_id TEXT NOT NULL REFERENCES communications(id),
        idempotency_key TEXT,
        request_hash TEXT,
        response_hash TEXT,
        status TEXT NOT NULL DEFAULT 'pending',
        operation_count INTEGER,
        started_at TEXT DEFAULT (datetime('now')),
        completed_at TEXT,
        error_message TEXT,
        tracker_response TEXT
    )"""),

    # ---- Hardening: review_action_log (audit trail) ----
    ("review_action_log", """CREATE TABLE IF NOT EXISTS review_action_log (
        id TEXT PRIMARY KEY,
        actor TEXT,
        communication_id TEXT REFERENCES communications(id),
        bundle_id TEXT REFERENCES review_bundles(id),
        item_id TEXT REFERENCES review_bundle_items(id),
        action_type TEXT NOT NULL,
        old_state TEXT,
        new_state TEXT,
        details TEXT,
        created_at TEXT DEFAULT (datetime('now'))
    )"""),

    # ---- Hardening: communication_error_log (error history) ----
    ("communication_error_log", """CREATE TABLE IF NOT EXISTS communication_error_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        communication_id TEXT NOT NULL REFERENCES communications(id),
        error_stage TEXT,
        error_message TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    )"""),
    # ---- Federal Register staging ----
    ("fr_documents", """CREATE TABLE IF NOT EXISTS fr_documents (
        id TEXT PRIMARY KEY,
        document_number TEXT NOT NULL UNIQUE,
        title TEXT NOT NULL,
        fr_type TEXT,
        action TEXT,
        abstract TEXT,
        publication_date TEXT,
        agencies_json TEXT,
        comments_close_on TEXT,
        docket_ids_json TEXT,
        regulation_id_numbers_json TEXT,
        cfr_references_json TEXT,
        html_url TEXT,
        pdf_url TEXT,
        body_html_url TEXT,
        raw_text_url TEXT,
        full_text TEXT,
        routing_tier INTEGER NOT NULL,
        processing_status TEXT NOT NULL DEFAULT 'pending',
        communication_id TEXT,
        matter_id TEXT,
        notes TEXT,
        created_at TEXT DEFAULT (datetime('now')),
        updated_at TEXT DEFAULT (datetime('now'))
    )"""),


    # ---- Table: meeting_intelligence ----
    ("meeting_intelligence", """CREATE TABLE IF NOT EXISTS meeting_intelligence (
        id TEXT PRIMARY KEY,
        communication_id TEXT NOT NULL REFERENCES communications(id),
        tracker_meeting_id TEXT,
        summary TEXT,
        key_decisions TEXT,
        action_items TEXT,
        relationship_dynamics TEXT,
        strategic_context TEXT,
        model_used TEXT,
        prompt_version TEXT,
        created_at TEXT DEFAULT (datetime('now')),
        updated_at TEXT DEFAULT (datetime('now'))
    )"""),

    # ---- Table: page_visits (telemetry) ----
    ("page_visits", """CREATE TABLE IF NOT EXISTS page_visits (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        page_path TEXT NOT NULL,
        entity_type TEXT,
        entity_id TEXT,
        visited_at TEXT DEFAULT (datetime('now'))
    )"""),

]

# ---------------------------------------------------------------------------
# Indexes
# ---------------------------------------------------------------------------

INDEXES = [
    # -- communications --
    "CREATE INDEX IF NOT EXISTS idx_comm_status ON communications(processing_status);",
    "CREATE INDEX IF NOT EXISTS idx_comm_source_type ON communications(source_type);",
    "CREATE INDEX IF NOT EXISTS idx_comm_created ON communications(created_at);",
    "CREATE INDEX IF NOT EXISTS idx_comm_lock ON communications(processing_lock_token);",

    # -- audio_files --
    "CREATE INDEX IF NOT EXISTS idx_audio_comm ON audio_files(communication_id);",

    # -- communication_participants --
    "CREATE INDEX IF NOT EXISTS idx_comm_part_comm ON communication_participants(communication_id);",
    "CREATE INDEX IF NOT EXISTS idx_comm_part_person ON communication_participants(tracker_person_id);",
    "CREATE INDEX IF NOT EXISTS idx_comm_part_label ON communication_participants(communication_id, speaker_label);",

    # -- transcripts --
    "CREATE INDEX IF NOT EXISTS idx_transcripts_comm ON transcripts(communication_id);",
    "CREATE INDEX IF NOT EXISTS idx_transcripts_speaker ON transcripts(communication_id, speaker_label);",
    "CREATE INDEX IF NOT EXISTS idx_transcripts_time ON transcripts(communication_id, start_time);",

    # -- communication_entities --
    "CREATE INDEX IF NOT EXISTS idx_entity_comm ON communication_entities(communication_id);",
    "CREATE INDEX IF NOT EXISTS idx_entity_person ON communication_entities(tracker_person_id);",
    "CREATE INDEX IF NOT EXISTS idx_entity_org ON communication_entities(tracker_org_id);",
    "CREATE INDEX IF NOT EXISTS idx_entity_type ON communication_entities(entity_type);",
    "CREATE INDEX IF NOT EXISTS idx_entity_confirmed ON communication_entities(communication_id, confirmed);",

    # -- communication_messages --
    "CREATE INDEX IF NOT EXISTS idx_msg_comm ON communication_messages(communication_id);",
    "CREATE INDEX IF NOT EXISTS idx_msg_hash ON communication_messages(message_hash);",
    "CREATE INDEX IF NOT EXISTS idx_msg_new ON communication_messages(communication_id, is_new);",
    "CREATE INDEX IF NOT EXISTS idx_msg_sender ON communication_messages(sender_email);",

    # -- communication_artifacts --
    "CREATE INDEX IF NOT EXISTS idx_artifact_comm ON communication_artifacts(communication_id);",
    "CREATE INDEX IF NOT EXISTS idx_artifact_msg ON communication_artifacts(message_id);",
    "CREATE INDEX IF NOT EXISTS idx_artifact_proposable ON communication_artifacts(is_document_proposable);",
    "CREATE INDEX IF NOT EXISTS idx_artifact_tracker_doc ON communication_artifacts(tracker_document_id);",

    # -- voice_samples --
    "CREATE INDEX IF NOT EXISTS idx_voice_comm ON voice_samples(communication_id);",
    "CREATE INDEX IF NOT EXISTS idx_voice_label ON voice_samples(communication_id, speaker_label);",

    # -- speaker_voice_profiles --
    "CREATE INDEX IF NOT EXISTS idx_voice_profile_person ON speaker_voice_profiles(tracker_person_id);",
    "CREATE INDEX IF NOT EXISTS idx_voice_profile_status ON speaker_voice_profiles(status);",

    # -- voiceprint_match_log --
    "CREATE INDEX IF NOT EXISTS idx_vp_match_comm ON voiceprint_match_log(communication_id);",
    "CREATE INDEX IF NOT EXISTS idx_vp_match_outcome ON voiceprint_match_log(outcome);",

    # -- ai_extractions --
    "CREATE INDEX IF NOT EXISTS idx_extraction_comm ON ai_extractions(communication_id);",

    # -- review_bundles --
    "CREATE INDEX IF NOT EXISTS idx_bundle_comm ON review_bundles(communication_id);",
    "CREATE INDEX IF NOT EXISTS idx_bundle_status ON review_bundles(status);",
    "CREATE INDEX IF NOT EXISTS idx_bundle_matter ON review_bundles(target_matter_id);",
    "CREATE INDEX IF NOT EXISTS idx_bundle_type ON review_bundles(bundle_type);",

    # -- review_bundle_items --
    "CREATE INDEX IF NOT EXISTS idx_item_bundle ON review_bundle_items(bundle_id);",
    "CREATE INDEX IF NOT EXISTS idx_item_type ON review_bundle_items(item_type);",
    "CREATE INDEX IF NOT EXISTS idx_item_status ON review_bundle_items(status);",
    "CREATE INDEX IF NOT EXISTS idx_item_source_transcript ON review_bundle_items(source_transcript_id);",

    # -- tracker_writebacks --
    "CREATE INDEX IF NOT EXISTS idx_wb_comm ON tracker_writebacks(communication_id);",
    "CREATE INDEX IF NOT EXISTS idx_wb_bundle ON tracker_writebacks(bundle_id);",
    "CREATE INDEX IF NOT EXISTS idx_wb_item ON tracker_writebacks(bundle_item_id);",
    "CREATE INDEX IF NOT EXISTS idx_wb_target ON tracker_writebacks(target_table, target_record_id);",
    "CREATE INDEX IF NOT EXISTS idx_wb_reversed ON tracker_writebacks(reversed);",

    # -- config_audit_log --
    "CREATE INDEX IF NOT EXISTS idx_config_audit_created ON config_audit_log(created_at);",
    "CREATE INDEX IF NOT EXISTS idx_config_audit_section ON config_audit_log(section);",

    # -- digests --
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_digest_date ON digests(digest_date);",

    # -- intelligence_briefs --
    "CREATE INDEX IF NOT EXISTS idx_brief_type_date ON intelligence_briefs(brief_type, brief_date);",

    # -- alert_actions --
    "CREATE INDEX IF NOT EXISTS idx_alert_fp ON alert_actions(alert_fingerprint);",
    "CREATE INDEX IF NOT EXISTS idx_alert_snooze ON alert_actions(snooze_until);",

    # -- llm_usage --
    "CREATE INDEX IF NOT EXISTS idx_llm_usage_comm ON llm_usage(communication_id);",
    "CREATE INDEX IF NOT EXISTS idx_llm_usage_date ON llm_usage(created_at);",

    # -- commit_batches --
    "CREATE INDEX IF NOT EXISTS idx_commit_batch_comm ON commit_batches(communication_id);",
    "CREATE INDEX IF NOT EXISTS idx_commit_batch_idemp ON commit_batches(idempotency_key);",

    # -- review_action_log --
    "CREATE INDEX IF NOT EXISTS idx_review_action_comm ON review_action_log(communication_id);",
    "CREATE INDEX IF NOT EXISTS idx_review_action_type ON review_action_log(action_type);",
    "CREATE INDEX IF NOT EXISTS idx_review_action_created ON review_action_log(created_at);",

    # -- communication_error_log --
    "CREATE INDEX IF NOT EXISTS idx_error_log_comm ON communication_error_log(communication_id);",
    "CREATE INDEX IF NOT EXISTS idx_error_log_created ON communication_error_log(created_at);",

    # -- fr_documents --
    "CREATE INDEX IF NOT EXISTS idx_fr_docs_docnum ON fr_documents(document_number);",
    "CREATE INDEX IF NOT EXISTS idx_fr_docs_status ON fr_documents(processing_status);",
    "CREATE INDEX IF NOT EXISTS idx_fr_docs_tier ON fr_documents(routing_tier);",
    "CREATE INDEX IF NOT EXISTS idx_fr_docs_pub_date ON fr_documents(publication_date);",

]


# ---------------------------------------------------------------------------
# Schema initializer
# ---------------------------------------------------------------------------

def init_schema(conn: sqlite3.Connection) -> list[str]:
    """Create all tables and indexes. Idempotent.
    Returns names of newly created tables.
    """
    cursor = conn.cursor()
    existing = {
        row[0]
        for row in cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
    }

    created: list[str] = []
    for name, sql in TABLES:
        if name not in existing:
            created.append(name)
        cursor.execute(sql)

    for idx in INDEXES:
        cursor.execute(idx)

    # ── Migrations for existing databases ──
    _run_migrations(cursor)

    conn.commit()

    if created:
        logger.info("Created %d new tables: %s", len(created), ", ".join(created))
    else:
        logger.debug("ai.db schema up to date — no new tables created.")

    return created


def _run_migrations(cursor):
    """Idempotent column additions for schema evolution.

    Each migration checks PRAGMA table_info before ALTER TABLE.
    """
    # Phase 5: add 'success' column to ai_extractions (2026-03-18)
    cols = {row[1] for row in cursor.execute("PRAGMA table_info(ai_extractions)")}
    if "success" not in cols:
        cursor.execute(
            "ALTER TABLE ai_extractions ADD COLUMN success INTEGER DEFAULT 1"
        )
        logger.info("Migration: added ai_extractions.success column")

    # Voiceprint: extend voice_samples with promotion tracking + speech duration
    vs_cols = {row[1] for row in cursor.execute("PRAGMA table_info(voice_samples)")}
    if "promoted_to_profile" not in vs_cols:
        cursor.execute(
            "ALTER TABLE voice_samples ADD COLUMN promoted_to_profile INTEGER DEFAULT 0"
        )
        logger.info("Migration: added voice_samples.promoted_to_profile column")
    if "speech_duration_seconds" not in vs_cols:
        cursor.execute(
            "ALTER TABLE voice_samples ADD COLUMN speech_duration_seconds REAL"
        )
        logger.info("Migration: added voice_samples.speech_duration_seconds column")

    # Archive support: add archived_at to communications (2026-03-19)
    comm_cols = {row[1] for row in cursor.execute("PRAGMA table_info(communications)")}
    if "archived_at" not in comm_cols:
        cursor.execute(
            "ALTER TABLE communications ADD COLUMN archived_at TEXT"
        )
        logger.info("Migration: added communications.archived_at column")

    # Phase 7: content_hash for dedup on audio_files
    af_cols = {row[1] for row in cursor.execute("PRAGMA table_info(audio_files)")}
    if "content_hash" not in af_cols:
        cursor.execute(
            "ALTER TABLE audio_files ADD COLUMN content_hash TEXT"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_af_content_hash ON audio_files(content_hash)"
        )
        logger.info("Migration: added audio_files.content_hash column + index")
