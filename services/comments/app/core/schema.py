"""Database schema for the CFTC Comment Analysis System (SQLite)."""

import sqlite3
import logging

logger = logging.getLogger(__name__)

TABLES = [
    ("proposed_rules", """
    CREATE TABLE IF NOT EXISTS proposed_rules (
        id                          INTEGER PRIMARY KEY AUTOINCREMENT,
        docket_number               TEXT UNIQUE NOT NULL,
        rin                         TEXT,
        title                       TEXT NOT NULL,
        publication_date            TEXT,
        comment_period_start        TEXT,
        comment_period_end          TEXT,
        federal_register_citation   TEXT,
        federal_register_doc_number TEXT,
        priority_level              TEXT DEFAULT 'STANDARD',
        status                      TEXT DEFAULT 'OPEN',
        full_text_url               TEXT,
        summary                     TEXT,
        regulations_gov_url         TEXT,
        page_count                  INTEGER,
        created_at                  TEXT DEFAULT (datetime('now')),
        updated_at                  TEXT DEFAULT (datetime('now')),
        last_comment_pull           TEXT,
        total_comments              INTEGER DEFAULT 0
    )
    """),

    ("comments", """
    CREATE TABLE IF NOT EXISTS comments (
        id                          INTEGER PRIMARY KEY AUTOINCREMENT,
        docket_number               TEXT NOT NULL REFERENCES proposed_rules(docket_number),
        document_id                 TEXT UNIQUE NOT NULL,
        commenter_name              TEXT,
        commenter_organization      TEXT,
        submission_date             TEXT,
        comment_text                TEXT,
        original_pdf_url            TEXT,
        page_count                  INTEGER,
        has_attachments             INTEGER DEFAULT 0,
        attachment_count            INTEGER DEFAULT 0,
        tier                        INTEGER,
        sentiment                   TEXT,
        is_form_letter              INTEGER DEFAULT 0,
        form_letter_group_id        INTEGER,
        ai_summary                  TEXT,
        ai_summary_structured       TEXT,
        pdf_extraction_confidence   REAL,
        pdf_extraction_method       TEXT,
        created_at                  TEXT DEFAULT (datetime('now')),
        updated_at                  TEXT DEFAULT (datetime('now')),
        regulations_gov_url         TEXT
    )
    """),

    ("comment_tags", """
    CREATE TABLE IF NOT EXISTS comment_tags (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        comment_id      INTEGER NOT NULL REFERENCES comments(id) ON DELETE CASCADE,
        tag_type        TEXT NOT NULL,
        tag_value       TEXT NOT NULL
    )
    """),

    ("tier1_organizations", """
    CREATE TABLE IF NOT EXISTS tier1_organizations (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        name            TEXT UNIQUE NOT NULL,
        category        TEXT NOT NULL,
        name_variations TEXT DEFAULT '[]',
        created_at      TEXT DEFAULT (datetime('now'))
    )
    """),

    ("weekly_reports", """
    CREATE TABLE IF NOT EXISTS weekly_reports (
        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
        week_ending_date    TEXT NOT NULL,
        generated_at        TEXT DEFAULT (datetime('now')),
        pdf_file_url        TEXT,
        html_content        TEXT
    )
    """),
]

INDEXES = [
    "CREATE INDEX IF NOT EXISTS ix_comments_docket ON comments(docket_number)",
    "CREATE INDEX IF NOT EXISTS ix_comments_document_id ON comments(document_id)",
    "CREATE INDEX IF NOT EXISTS ix_comments_tier ON comments(tier)",
    "CREATE INDEX IF NOT EXISTS ix_comments_submission_date ON comments(submission_date)",
    "CREATE INDEX IF NOT EXISTS ix_comments_org ON comments(commenter_organization)",
    "CREATE INDEX IF NOT EXISTS ix_comment_tags_type_value ON comment_tags(tag_type, tag_value)",
    "CREATE INDEX IF NOT EXISTS ix_comment_tags_comment_id ON comment_tags(comment_id)",
    "CREATE INDEX IF NOT EXISTS ix_proposed_rules_docket ON proposed_rules(docket_number)",
    "CREATE INDEX IF NOT EXISTS ix_proposed_rules_priority_status ON proposed_rules(priority_level, status)",
]


def init_schema(conn: sqlite3.Connection) -> list:
    """Create all tables and indexes. Returns list of newly created table names."""
    created = []
    cursor = conn.cursor()
    for name, sql in TABLES:
        existing = cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (name,)
        ).fetchone()
        cursor.execute(sql)
        if not existing:
            created.append(name)
            logger.info(f"Created table: {name}")

    for idx_sql in INDEXES:
        cursor.execute(idx_sql)

    conn.commit()
    return created
