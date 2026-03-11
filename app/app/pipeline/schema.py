"""
Database schema for the CFTC Regulatory Pipeline Manager.

Creates all 19 pipeline tables in pipeline.db. All CREATE statements
are idempotent (IF NOT EXISTS). Follows the same pattern as
stage1/db/schema.py.

Tables:
  1.  team_members                — Attorneys and staff
  2.  stage_templates             — Default stage sequences per item type
  3.  pipeline_items              — Core table: both modules write here
  4.  pipeline_stages             — Per-item custom stage overrides
  5.  pipeline_item_assignments   — Junction: items <-> team members
  6.  pipeline_deadlines          — Multiple deadlines per item
  7.  pipeline_documents          — Version-controlled attachments
  8.  pipeline_decision_log       — Audit trail of changes and decisions
  9.  pipeline_stakeholders       — External contacts
  10. pipeline_stakeholder_links  — Junction: items <-> stakeholders
  11. pipeline_meetings           — Ex parte, interagency, Hill briefings
  12. pipeline_dependencies       — Item-to-item links
  13. pipeline_notifications      — Alerts for team members
  14. pipeline_cba_tracking       — Cost-benefit analysis status
  15. pipeline_publication_status — OFR, PRA, OIRA, CRA, FR tracking
  16. pipeline_unified_agenda     — Unified Agenda mapping
  17. pipeline_foia               — FOIA request tracking
  18. pipeline_enforcement_referrals — Enforcement referral tracking
  19. pipeline_priority_signals   — Individual signals for composite priority
"""

import sqlite3
import logging

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Table definitions — each is a (name, CREATE TABLE sql) tuple
# ---------------------------------------------------------------------------

PIPELINE_TABLES = [

    # -----------------------------------------------------------------------
    # 1. team_members
    # -----------------------------------------------------------------------
    ("team_members", """
    CREATE TABLE IF NOT EXISTS team_members (
        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
        name                TEXT NOT NULL,
        email               TEXT UNIQUE,
        role                TEXT NOT NULL,
        gs_level            TEXT,
        division            TEXT DEFAULT 'Regulation',
        specializations     TEXT DEFAULT '[]',
        max_concurrent      INTEGER DEFAULT 5,
        is_active           INTEGER DEFAULT 1,
        created_at          TEXT DEFAULT (datetime('now')),
        updated_at          TEXT DEFAULT (datetime('now'))
    )
    """),

    # -----------------------------------------------------------------------
    # 2. stage_templates
    # Default stage sequences per item_type.
    # -----------------------------------------------------------------------
    ("stage_templates", """
    CREATE TABLE IF NOT EXISTS stage_templates (
        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
        module              TEXT NOT NULL,
        item_type           TEXT NOT NULL,
        stage_order         INTEGER NOT NULL,
        stage_key           TEXT NOT NULL,
        stage_label         TEXT NOT NULL,
        stage_color         TEXT,
        is_terminal         INTEGER DEFAULT 0,
        sla_days            INTEGER,
        UNIQUE(module, item_type, stage_order)
    )
    """),

    # -----------------------------------------------------------------------
    # 3. pipeline_items — CORE TABLE
    # Both rulemaking and regulatory_action modules write here.
    # -----------------------------------------------------------------------
    ("pipeline_items", """
    CREATE TABLE IF NOT EXISTS pipeline_items (
        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
        module              TEXT NOT NULL,
        item_type           TEXT NOT NULL,
        title               TEXT NOT NULL,
        short_title         TEXT,
        description         TEXT,
        docket_number       TEXT,
        rin                 TEXT,
        fr_citation         TEXT,
        fr_doc_number       TEXT,

        -- Stage management
        current_stage       TEXT NOT NULL,
        stage_entered_at    TEXT DEFAULT (datetime('now')),

        -- Priority
        priority_composite  REAL DEFAULT 0.0,
        priority_override   REAL,
        priority_label      TEXT DEFAULT 'medium',
        chairman_priority   INTEGER DEFAULT 0,

        -- Assignment
        lead_attorney_id    INTEGER REFERENCES team_members(id),
        backup_attorney_id  INTEGER REFERENCES team_members(id),

        -- Regulatory action specifics
        action_subtype      TEXT,
        requesting_party    TEXT,
        related_rulemaking_id INTEGER REFERENCES pipeline_items(id),

        -- Enforcement/FOIA linkage
        enforcement_referral INTEGER DEFAULT 0,
        foia_request_count   INTEGER DEFAULT 0,

        -- Unified Agenda
        unified_agenda_rin  TEXT,
        unified_agenda_stage TEXT,

        -- Integration keys (cross-DB)
        stage1_fr_citation  TEXT,
        stage1_doc_id       TEXT,
        eo_action_item_id   INTEGER,
        comment_docket      TEXT,

        -- Status
        status              TEXT DEFAULT 'active',
        archived_at         TEXT,
        archived_reason     TEXT,

        -- Metadata
        created_at          TEXT DEFAULT (datetime('now')),
        updated_at          TEXT DEFAULT (datetime('now')),
        created_by          TEXT
    )
    """),

    # -----------------------------------------------------------------------
    # 4. pipeline_stages — per-item custom stage overrides
    # -----------------------------------------------------------------------
    ("pipeline_stages", """
    CREATE TABLE IF NOT EXISTS pipeline_stages (
        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
        item_id             INTEGER NOT NULL REFERENCES pipeline_items(id) ON DELETE CASCADE,
        stage_order         INTEGER NOT NULL,
        stage_key           TEXT NOT NULL,
        stage_label         TEXT NOT NULL,
        stage_color         TEXT,
        is_terminal         INTEGER DEFAULT 0,
        sla_days            INTEGER,
        entered_at          TEXT,
        completed_at        TEXT,
        UNIQUE(item_id, stage_order)
    )
    """),

    # -----------------------------------------------------------------------
    # 5. pipeline_item_assignments
    # -----------------------------------------------------------------------
    ("pipeline_item_assignments", """
    CREATE TABLE IF NOT EXISTS pipeline_item_assignments (
        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
        item_id             INTEGER NOT NULL REFERENCES pipeline_items(id) ON DELETE CASCADE,
        team_member_id      INTEGER NOT NULL REFERENCES team_members(id) ON DELETE CASCADE,
        role                TEXT NOT NULL DEFAULT 'contributor',
        assigned_at         TEXT DEFAULT (datetime('now')),
        UNIQUE(item_id, team_member_id, role)
    )
    """),

    # -----------------------------------------------------------------------
    # 6. pipeline_deadlines
    # -----------------------------------------------------------------------
    ("pipeline_deadlines", """
    CREATE TABLE IF NOT EXISTS pipeline_deadlines (
        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
        item_id             INTEGER NOT NULL REFERENCES pipeline_items(id) ON DELETE CASCADE,
        deadline_type       TEXT NOT NULL,
        title               TEXT NOT NULL,
        due_date            TEXT NOT NULL,
        source              TEXT,
        source_detail       TEXT,
        is_hard_deadline    INTEGER DEFAULT 1,
        days_warning        INTEGER DEFAULT 14,
        days_critical       INTEGER DEFAULT 3,

        -- Backward calculation
        predecessor_id      INTEGER REFERENCES pipeline_deadlines(id),
        offset_days         INTEGER,

        -- Status
        status              TEXT DEFAULT 'pending',
        completed_at        TEXT,
        extended_to         TEXT,
        extension_reason    TEXT,

        -- Assignment
        owner_id            INTEGER REFERENCES team_members(id),

        created_at          TEXT DEFAULT (datetime('now')),
        updated_at          TEXT DEFAULT (datetime('now'))
    )
    """),

    # -----------------------------------------------------------------------
    # 7. pipeline_documents
    # -----------------------------------------------------------------------
    ("pipeline_documents", """
    CREATE TABLE IF NOT EXISTS pipeline_documents (
        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
        item_id             INTEGER NOT NULL REFERENCES pipeline_items(id) ON DELETE CASCADE,
        document_type       TEXT NOT NULL,
        title               TEXT NOT NULL,
        version             INTEGER DEFAULT 1,
        file_path           TEXT,
        file_size           INTEGER,
        file_hash           TEXT,
        mime_type           TEXT,
        uploaded_by         TEXT,
        change_summary      TEXT,
        is_current          INTEGER DEFAULT 1,
        parent_version_id   INTEGER REFERENCES pipeline_documents(id),
        created_at          TEXT DEFAULT (datetime('now'))
    )
    """),

    # -----------------------------------------------------------------------
    # 8. pipeline_decision_log
    # -----------------------------------------------------------------------
    ("pipeline_decision_log", """
    CREATE TABLE IF NOT EXISTS pipeline_decision_log (
        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
        item_id             INTEGER NOT NULL REFERENCES pipeline_items(id) ON DELETE CASCADE,
        action_type         TEXT NOT NULL,
        description         TEXT NOT NULL,
        old_value           TEXT,
        new_value           TEXT,
        decided_by          TEXT,
        rationale           TEXT,
        created_at          TEXT DEFAULT (datetime('now'))
    )
    """),

    # -----------------------------------------------------------------------
    # 9. pipeline_stakeholders
    # -----------------------------------------------------------------------
    ("pipeline_stakeholders", """
    CREATE TABLE IF NOT EXISTS pipeline_stakeholders (
        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
        name                TEXT NOT NULL,
        organization        TEXT,
        stakeholder_type    TEXT NOT NULL,
        title               TEXT,
        email               TEXT,
        phone               TEXT,
        notes               TEXT,
        created_at          TEXT DEFAULT (datetime('now'))
    )
    """),

    # -----------------------------------------------------------------------
    # 10. pipeline_stakeholder_links
    # -----------------------------------------------------------------------
    ("pipeline_stakeholder_links", """
    CREATE TABLE IF NOT EXISTS pipeline_stakeholder_links (
        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
        item_id             INTEGER NOT NULL REFERENCES pipeline_items(id) ON DELETE CASCADE,
        stakeholder_id      INTEGER NOT NULL REFERENCES pipeline_stakeholders(id) ON DELETE CASCADE,
        interest_level      TEXT DEFAULT 'medium',
        position            TEXT,
        notes               TEXT,
        UNIQUE(item_id, stakeholder_id)
    )
    """),

    # -----------------------------------------------------------------------
    # 11. pipeline_meetings
    # -----------------------------------------------------------------------
    ("pipeline_meetings", """
    CREATE TABLE IF NOT EXISTS pipeline_meetings (
        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
        item_id             INTEGER REFERENCES pipeline_items(id) ON DELETE SET NULL,
        meeting_type        TEXT NOT NULL,
        title               TEXT NOT NULL,
        date                TEXT NOT NULL,
        attendees           TEXT,
        summary             TEXT,
        follow_up_items     TEXT,
        is_ex_parte         INTEGER DEFAULT 0,
        ex_parte_filed      INTEGER DEFAULT 0,
        created_at          TEXT DEFAULT (datetime('now'))
    )
    """),

    # -----------------------------------------------------------------------
    # 12. pipeline_dependencies
    # -----------------------------------------------------------------------
    ("pipeline_dependencies", """
    CREATE TABLE IF NOT EXISTS pipeline_dependencies (
        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
        source_item_id      INTEGER NOT NULL REFERENCES pipeline_items(id) ON DELETE CASCADE,
        target_item_id      INTEGER NOT NULL REFERENCES pipeline_items(id) ON DELETE CASCADE,
        dependency_type     TEXT NOT NULL,
        description         TEXT,
        UNIQUE(source_item_id, target_item_id, dependency_type)
    )
    """),

    # -----------------------------------------------------------------------
    # 13. pipeline_notifications
    # -----------------------------------------------------------------------
    ("pipeline_notifications", """
    CREATE TABLE IF NOT EXISTS pipeline_notifications (
        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
        recipient_id        INTEGER REFERENCES team_members(id),
        item_id             INTEGER REFERENCES pipeline_items(id) ON DELETE CASCADE,
        notification_type   TEXT NOT NULL,
        title               TEXT NOT NULL,
        message             TEXT,
        severity            TEXT DEFAULT 'info',
        is_read             INTEGER DEFAULT 0,
        is_dismissed        INTEGER DEFAULT 0,
        created_at          TEXT DEFAULT (datetime('now'))
    )
    """),

    # -----------------------------------------------------------------------
    # 14. pipeline_cba_tracking
    # -----------------------------------------------------------------------
    ("pipeline_cba_tracking", """
    CREATE TABLE IF NOT EXISTS pipeline_cba_tracking (
        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
        item_id             INTEGER NOT NULL REFERENCES pipeline_items(id) ON DELETE CASCADE,
        cba_status          TEXT DEFAULT 'not_started',
        analyst_assigned    TEXT,
        estimated_costs     REAL,
        estimated_benefits  REAL,
        net_benefit         REAL,
        methodology         TEXT,
        oira_review_required INTEGER DEFAULT 0,
        oira_submitted      TEXT,
        oira_completed      TEXT,
        small_entity_impact TEXT,
        rfa_required        INTEGER DEFAULT 0,
        irfa_completed      INTEGER DEFAULT 0,
        frfa_completed      INTEGER DEFAULT 0,
        notes               TEXT,
        updated_at          TEXT DEFAULT (datetime('now'))
    )
    """),

    # -----------------------------------------------------------------------
    # 15. pipeline_publication_status
    # -----------------------------------------------------------------------
    ("pipeline_publication_status", """
    CREATE TABLE IF NOT EXISTS pipeline_publication_status (
        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
        item_id             INTEGER NOT NULL REFERENCES pipeline_items(id) ON DELETE CASCADE,
        -- OFR
        ofr_submitted       TEXT,
        ofr_accepted        TEXT,
        ofr_publication_date TEXT,
        ofr_doc_number      TEXT,
        -- PRA
        pra_required        INTEGER DEFAULT 0,
        pra_icr_number      TEXT,
        pra_submitted_oira  TEXT,
        pra_approved        TEXT,
        pra_burden_hours    INTEGER,
        -- OIRA
        oira_submitted      TEXT,
        oira_review_type    TEXT,
        oira_completed      TEXT,
        oira_changes        TEXT,
        -- CRA
        cra_submitted       TEXT,
        cra_review_period_end TEXT,
        cra_is_major        INTEGER DEFAULT 0,
        cra_resolution_introduced INTEGER DEFAULT 0,
        -- FR publication
        fr_volume           TEXT,
        fr_start_page       TEXT,
        fr_end_page         TEXT,
        effective_date      TEXT,
        -- Notes
        notes               TEXT,
        updated_at          TEXT DEFAULT (datetime('now'))
    )
    """),

    # -----------------------------------------------------------------------
    # 16. pipeline_unified_agenda
    # -----------------------------------------------------------------------
    ("pipeline_unified_agenda", """
    CREATE TABLE IF NOT EXISTS pipeline_unified_agenda (
        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
        item_id             INTEGER NOT NULL REFERENCES pipeline_items(id) ON DELETE CASCADE,
        rin                 TEXT,
        agenda_stage        TEXT,
        priority_designation TEXT,
        abstract            TEXT,
        timetable           TEXT,
        legal_authority     TEXT,
        last_unified_agenda_update TEXT,
        next_action         TEXT,
        next_action_date    TEXT,
        notes               TEXT,
        updated_at          TEXT DEFAULT (datetime('now'))
    )
    """),

    # -----------------------------------------------------------------------
    # 17. pipeline_foia
    # -----------------------------------------------------------------------
    ("pipeline_foia", """
    CREATE TABLE IF NOT EXISTS pipeline_foia (
        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
        item_id             INTEGER REFERENCES pipeline_items(id) ON DELETE SET NULL,
        foia_number         TEXT,
        requester           TEXT,
        request_date        TEXT,
        due_date            TEXT,
        status              TEXT DEFAULT 'pending',
        assigned_to         INTEGER REFERENCES team_members(id),
        notes               TEXT,
        created_at          TEXT DEFAULT (datetime('now'))
    )
    """),

    # -----------------------------------------------------------------------
    # 18. pipeline_enforcement_referrals
    # -----------------------------------------------------------------------
    ("pipeline_enforcement_referrals", """
    CREATE TABLE IF NOT EXISTS pipeline_enforcement_referrals (
        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
        item_id             INTEGER REFERENCES pipeline_items(id) ON DELETE SET NULL,
        referral_date       TEXT,
        referring_division  TEXT,
        subject             TEXT NOT NULL,
        status              TEXT DEFAULT 'pending',
        enforcement_case_id TEXT,
        notes               TEXT,
        created_at          TEXT DEFAULT (datetime('now'))
    )
    """),

    # -----------------------------------------------------------------------
    # 19. pipeline_priority_signals
    # -----------------------------------------------------------------------
    ("pipeline_priority_signals", """
    CREATE TABLE IF NOT EXISTS pipeline_priority_signals (
        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
        item_id             INTEGER NOT NULL REFERENCES pipeline_items(id) ON DELETE CASCADE,
        signal_type         TEXT NOT NULL,
        signal_value        REAL NOT NULL,
        signal_source       TEXT,
        signal_detail       TEXT,
        computed_at         TEXT DEFAULT (datetime('now')),
        UNIQUE(item_id, signal_type)
    )
    """),
]


# ---------------------------------------------------------------------------
# Index definitions for query performance
# ---------------------------------------------------------------------------

PIPELINE_INDEXES = [
    # pipeline_items
    "CREATE INDEX IF NOT EXISTS idx_pi_module ON pipeline_items(module)",
    "CREATE INDEX IF NOT EXISTS idx_pi_type ON pipeline_items(item_type)",
    "CREATE INDEX IF NOT EXISTS idx_pi_stage ON pipeline_items(current_stage)",
    "CREATE INDEX IF NOT EXISTS idx_pi_status ON pipeline_items(status)",
    "CREATE INDEX IF NOT EXISTS idx_pi_priority ON pipeline_items(priority_composite)",
    "CREATE INDEX IF NOT EXISTS idx_pi_lead ON pipeline_items(lead_attorney_id)",
    "CREATE INDEX IF NOT EXISTS idx_pi_docket ON pipeline_items(docket_number)",
    "CREATE INDEX IF NOT EXISTS idx_pi_fr ON pipeline_items(fr_citation)",
    "CREATE INDEX IF NOT EXISTS idx_pi_module_stage ON pipeline_items(module, current_stage)",
    "CREATE INDEX IF NOT EXISTS idx_pi_module_status ON pipeline_items(module, status)",

    # pipeline_deadlines
    "CREATE INDEX IF NOT EXISTS idx_pd_item ON pipeline_deadlines(item_id)",
    "CREATE INDEX IF NOT EXISTS idx_pd_due ON pipeline_deadlines(due_date)",
    "CREATE INDEX IF NOT EXISTS idx_pd_type ON pipeline_deadlines(deadline_type)",
    "CREATE INDEX IF NOT EXISTS idx_pd_status ON pipeline_deadlines(status)",

    # pipeline_documents
    "CREATE INDEX IF NOT EXISTS idx_pdoc_item ON pipeline_documents(item_id)",
    "CREATE INDEX IF NOT EXISTS idx_pdoc_current ON pipeline_documents(is_current)",

    # pipeline_decision_log
    "CREATE INDEX IF NOT EXISTS idx_pdl_item ON pipeline_decision_log(item_id)",
    "CREATE INDEX IF NOT EXISTS idx_pdl_type ON pipeline_decision_log(action_type)",

    # pipeline_notifications
    "CREATE INDEX IF NOT EXISTS idx_pn_recipient ON pipeline_notifications(recipient_id)",
    "CREATE INDEX IF NOT EXISTS idx_pn_read ON pipeline_notifications(is_read)",

    # pipeline_item_assignments
    "CREATE INDEX IF NOT EXISTS idx_pia_item ON pipeline_item_assignments(item_id)",
    "CREATE INDEX IF NOT EXISTS idx_pia_member ON pipeline_item_assignments(team_member_id)",

    # pipeline_dependencies
    "CREATE INDEX IF NOT EXISTS idx_dep_source ON pipeline_dependencies(source_item_id)",
    "CREATE INDEX IF NOT EXISTS idx_dep_target ON pipeline_dependencies(target_item_id)",

    # pipeline_stakeholder_links
    "CREATE INDEX IF NOT EXISTS idx_psl_item ON pipeline_stakeholder_links(item_id)",
    "CREATE INDEX IF NOT EXISTS idx_psl_stakeholder ON pipeline_stakeholder_links(stakeholder_id)",

    # pipeline_meetings
    "CREATE INDEX IF NOT EXISTS idx_pm_item ON pipeline_meetings(item_id)",
    "CREATE INDEX IF NOT EXISTS idx_pm_date ON pipeline_meetings(date)",

    # pipeline_priority_signals
    "CREATE INDEX IF NOT EXISTS idx_pps_item ON pipeline_priority_signals(item_id)",

    # pipeline_stages
    "CREATE INDEX IF NOT EXISTS idx_ps_item ON pipeline_stages(item_id)",

    # pipeline_foia
    "CREATE INDEX IF NOT EXISTS idx_foia_item ON pipeline_foia(item_id)",

    # pipeline_enforcement_referrals
    "CREATE INDEX IF NOT EXISTS idx_er_item ON pipeline_enforcement_referrals(item_id)",

    # team_members
    "CREATE INDEX IF NOT EXISTS idx_tm_active ON team_members(is_active)",
]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def init_pipeline_schema(conn: sqlite3.Connection) -> list[str]:
    """
    Create all pipeline tables and indexes in the database.

    Idempotent -- safe to call repeatedly.

    Returns:
        List of table names that were newly created.
    """
    cursor = conn.cursor()

    existing = set()
    for row in cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ):
        existing.add(row[0])

    created = []
    for table_name, create_sql in PIPELINE_TABLES:
        if table_name not in existing:
            created.append(table_name)
        cursor.execute(create_sql)
        logger.info(
            f"Table {table_name}: "
            f"{'CREATED' if table_name not in existing else 'exists'}"
        )

    for idx_sql in PIPELINE_INDEXES:
        cursor.execute(idx_sql)

    conn.commit()
    logger.info(
        f"Pipeline schema init complete: {len(created)} new tables, "
        f"{len(PIPELINE_TABLES) - len(created)} existing"
    )
    return created


def get_pipeline_table_counts(conn: sqlite3.Connection) -> dict[str, int]:
    """Get row counts for all pipeline tables."""
    cursor = conn.cursor()
    counts = {}
    for table_name, _ in PIPELINE_TABLES:
        try:
            count = cursor.execute(
                f"SELECT COUNT(*) FROM {table_name}"
            ).fetchone()[0]
            counts[table_name] = count
        except Exception:
            counts[table_name] = -1
    return counts
