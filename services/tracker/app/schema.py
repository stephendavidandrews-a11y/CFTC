"""
CFTC Regulatory Ops Tracker — Database Schema

Creates all 28 tables + indexes. Idempotent (CREATE TABLE/INDEX IF NOT EXISTS).
Returns list of newly created table names on each run.
"""

import sqlite3
import logging

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Table definitions
# ---------------------------------------------------------------------------

TABLES = [
    # ---- Core tables ----
    (
        "organizations",
        """CREATE TABLE IF NOT EXISTS organizations (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        short_name TEXT,
        organization_type TEXT,
        parent_organization_id TEXT REFERENCES organizations(id),
        jurisdiction TEXT,
        notes TEXT,
        is_active INTEGER DEFAULT 1,
        source TEXT DEFAULT 'manual',
        source_id TEXT,
        external_refs TEXT,
        created_at TEXT DEFAULT (datetime('now')),
        updated_at TEXT DEFAULT (datetime('now'))
    )""",
    ),
    (
        "people",
        """CREATE TABLE IF NOT EXISTS people (
        id TEXT PRIMARY KEY,
        full_name TEXT NOT NULL,
        first_name TEXT,
        last_name TEXT,
        title TEXT,
        organization_id TEXT REFERENCES organizations(id),
        email TEXT,
        phone TEXT,
        assistant_name TEXT,
        assistant_contact TEXT,
        substantive_areas TEXT,
        relationship_category TEXT,
        last_interaction_date TEXT,
        next_interaction_needed_date TEXT,
        next_interaction_type TEXT,
        next_interaction_purpose TEXT,
        manager_person_id TEXT REFERENCES people(id),
        include_in_team_workload INTEGER DEFAULT 0,
        relationship_assigned_to_person_id TEXT REFERENCES people(id),
        is_active INTEGER DEFAULT 1,
        source TEXT DEFAULT 'manual',
        source_id TEXT,
        external_refs TEXT,
        created_at TEXT DEFAULT (datetime('now')),
        updated_at TEXT DEFAULT (datetime('now'))
    )""",
    ),
    (
        "matters",
        """CREATE TABLE IF NOT EXISTS matters (
        id TEXT PRIMARY KEY,
        matter_number TEXT UNIQUE,
        title TEXT NOT NULL,
        matter_type TEXT NOT NULL,
        description TEXT,        status TEXT NOT NULL,
        priority TEXT NOT NULL,
        sensitivity TEXT NOT NULL,        assigned_to_person_id TEXT REFERENCES people(id),        client_organization_id TEXT REFERENCES organizations(id),        opened_date TEXT,
        work_deadline TEXT,        external_deadline TEXT,        next_step TEXT NOT NULL,        outcome_summary TEXT,
        last_material_update_at TEXT,
        closed_at TEXT,
        is_stale_override INTEGER DEFAULT 0,
        created_by_person_id TEXT REFERENCES people(id),        source TEXT DEFAULT 'manual',
        source_id TEXT,
        ai_confidence REAL,
        automation_hold INTEGER DEFAULT 0,
        external_refs TEXT,
        created_at TEXT DEFAULT (datetime('now')),
        updated_at TEXT DEFAULT (datetime('now'))
    )""",
    ),
    (
        "tasks",
        """CREATE TABLE IF NOT EXISTS tasks (
        id TEXT PRIMARY KEY,
        matter_id TEXT REFERENCES matters(id),
        title TEXT NOT NULL,
        description TEXT,
        task_type TEXT,
        status TEXT NOT NULL,
        task_mode TEXT NOT NULL,
        priority TEXT,
        assigned_to_person_id TEXT REFERENCES people(id),
        created_by_person_id TEXT REFERENCES people(id),
        delegated_by_person_id TEXT REFERENCES people(id),
        supervising_person_id TEXT REFERENCES people(id),
        waiting_on_person_id TEXT REFERENCES people(id),
        waiting_on_org_id TEXT REFERENCES organizations(id),
        waiting_on_description TEXT,
        tracks_task_id TEXT REFERENCES tasks(id),
        trigger_description TEXT,
        expected_output TEXT,
        due_date TEXT,
        deadline_type TEXT,
        started_at TEXT,
        completed_at TEXT,
        next_follow_up_date TEXT,
        completion_notes TEXT,
        sort_order INTEGER,
        source TEXT DEFAULT 'manual',
        source_id TEXT,
        ai_confidence REAL,
        automation_hold INTEGER DEFAULT 0,
        external_refs TEXT,
        created_at TEXT DEFAULT (datetime('now')),
        updated_at TEXT DEFAULT (datetime('now'))
    )""",
    ),
    (
        "meetings",
        """CREATE TABLE IF NOT EXISTS meetings (
        id TEXT PRIMARY KEY,
        title TEXT NOT NULL,
        meeting_type TEXT,
        date_time_start TEXT NOT NULL,
        date_time_end TEXT,
        location_or_link TEXT,
        purpose TEXT,
        prep_needed TEXT,
        notes TEXT,
        decisions_made TEXT,
        readout_summary TEXT,
        boss_attends INTEGER DEFAULT 0,
        external_parties_attend INTEGER DEFAULT 0,
        created_followups INTEGER DEFAULT 0,
        assigned_to_person_id TEXT REFERENCES people(id),
        transcript_id TEXT,
        recording_id TEXT,
        created_by_person_id TEXT REFERENCES people(id),
        source TEXT DEFAULT 'manual',
        source_id TEXT,
        external_refs TEXT,
        created_at TEXT DEFAULT (datetime('now')),
        updated_at TEXT DEFAULT (datetime('now'))
    )""",
    ),
    (
        "documents",
        """CREATE TABLE IF NOT EXISTS documents (
        id TEXT PRIMARY KEY,
        matter_id TEXT REFERENCES matters(id),
        title TEXT NOT NULL,
        document_type TEXT NOT NULL,
        status TEXT NOT NULL,
        assigned_to_person_id TEXT REFERENCES people(id),
        version_label TEXT,
        due_date TEXT,
        final_location TEXT,
        current_file_id TEXT,
        is_finalized INTEGER DEFAULT 0,
        is_sent INTEGER DEFAULT 0,
        sent_at TEXT,
        summary TEXT,
        notes TEXT,
        source TEXT DEFAULT 'manual',
        source_id TEXT,
        external_refs TEXT,
        created_at TEXT DEFAULT (datetime('now')),
        updated_at TEXT DEFAULT (datetime('now'))
    )""",
    ),
    (
        "decisions",
        """CREATE TABLE IF NOT EXISTS decisions (
        id TEXT PRIMARY KEY,
        matter_id TEXT REFERENCES matters(id),
        title TEXT NOT NULL,
        decision_type TEXT,
        status TEXT,
        decision_assigned_to_person_id TEXT REFERENCES people(id),
        decision_due_date TEXT,
        options_summary TEXT,
        recommended_option TEXT,
        decision_result TEXT,
        made_at TEXT,
        notes TEXT,
        source TEXT DEFAULT 'manual',
        source_id TEXT,
        ai_confidence REAL,
        automation_hold INTEGER DEFAULT 0,
        external_refs TEXT,
        created_at TEXT DEFAULT (datetime('now')),
        updated_at TEXT DEFAULT (datetime('now'))
    )""",
    ),
    # ---- Context Layer tables ----
    (
        "context_notes",
        """CREATE TABLE IF NOT EXISTS context_notes (
        id TEXT PRIMARY KEY,
        title TEXT NOT NULL,
        body TEXT NOT NULL,
        category TEXT NOT NULL,
        posture TEXT NOT NULL DEFAULT 'factual',
        durability TEXT NOT NULL DEFAULT 'durable',
        sensitivity TEXT NOT NULL DEFAULT 'low',
        status TEXT NOT NULL DEFAULT 'active',
        confidence REAL,
        source_type TEXT,
        source_id TEXT,
        source_excerpt TEXT,
        source_timestamp_start REAL,
        source_timestamp_end REAL,
        speaker_attribution TEXT,
        created_by_type TEXT DEFAULT 'ai',
        created_by_person_id TEXT REFERENCES people(id),
        effective_date TEXT,
        stale_after TEXT,
        archived_at TEXT,
        notes_visibility TEXT DEFAULT 'normal',
        last_reviewed_at TEXT,
        matter_id TEXT REFERENCES matters(id),
        source_communication_id TEXT,
        is_active INTEGER DEFAULT 1,
        source TEXT DEFAULT 'manual',
        ai_confidence REAL,
        automation_hold INTEGER DEFAULT 0,
        external_refs TEXT,
        created_at TEXT DEFAULT (datetime('now')),
        updated_at TEXT DEFAULT (datetime('now'))
    )""",
    ),
    (
        "context_note_links",
        """CREATE TABLE IF NOT EXISTS context_note_links (
        id TEXT PRIMARY KEY,
        context_note_id TEXT NOT NULL REFERENCES context_notes(id),
        entity_type TEXT NOT NULL,
        entity_id TEXT NOT NULL,
        relationship_role TEXT NOT NULL,
        created_at TEXT DEFAULT (datetime('now'))
    )""",
    ),
    (
        "person_profiles",
        """CREATE TABLE IF NOT EXISTS person_profiles (
        id TEXT PRIMARY KEY,
        person_id TEXT NOT NULL UNIQUE REFERENCES people(id),
        birthday TEXT,
        spouse_name TEXT,
        children_count INTEGER,
        children_names TEXT,
        hometown TEXT,
        current_city TEXT,
        prior_roles_summary TEXT,
        education_summary TEXT,
        interests TEXT,
        personal_notes_summary TEXT,
        scheduling_notes TEXT,
        relationship_preferences TEXT,
        leadership_notes TEXT,
        created_at TEXT DEFAULT (datetime('now')),
        updated_at TEXT DEFAULT (datetime('now'))
    )""",
    ),
    # ---- Junction tables ----
    (
        "matter_people",
        """CREATE TABLE IF NOT EXISTS matter_people (
        id TEXT PRIMARY KEY,
        matter_id TEXT NOT NULL REFERENCES matters(id),
        person_id TEXT NOT NULL REFERENCES people(id),
        matter_role TEXT NOT NULL,
        engagement_level TEXT,
        notes TEXT,
        last_contact_at TEXT,
        next_contact_needed_at TEXT,
        created_at TEXT DEFAULT (datetime('now')),
        updated_at TEXT DEFAULT (datetime('now'))
    )""",
    ),
    (
        "matter_organizations",
        """CREATE TABLE IF NOT EXISTS matter_organizations (
        id TEXT PRIMARY KEY,
        matter_id TEXT NOT NULL REFERENCES matters(id),
        organization_id TEXT NOT NULL REFERENCES organizations(id),
        organization_role TEXT NOT NULL,
        notes TEXT,
        created_at TEXT DEFAULT (datetime('now')),
        updated_at TEXT DEFAULT (datetime('now'))
    )""",
    ),
    (
        "meeting_participants",
        """CREATE TABLE IF NOT EXISTS meeting_participants (
        id TEXT PRIMARY KEY,
        meeting_id TEXT NOT NULL REFERENCES meetings(id),
        person_id TEXT NOT NULL REFERENCES people(id),
        organization_id TEXT REFERENCES organizations(id),
        meeting_role TEXT,
        attendance_status TEXT,
        attended INTEGER,
        stance_summary TEXT,
        stance_confidence REAL,
        position_strength TEXT,
        moved_position INTEGER,
        movement_summary TEXT,
        key_contribution_summary TEXT,
        follow_up_expected INTEGER,
        notes TEXT
    )""",
    ),
    (
        "meeting_matters",
        """CREATE TABLE IF NOT EXISTS meeting_matters (
        id TEXT PRIMARY KEY,
        meeting_id TEXT NOT NULL REFERENCES meetings(id),
        matter_id TEXT NOT NULL REFERENCES matters(id),
        relationship_type TEXT,
        status_before TEXT,
        status_after TEXT,
        decision_made INTEGER,
        decision_summary TEXT,
        follow_up_required INTEGER,
        notes TEXT,
        created_at TEXT DEFAULT (datetime('now')),
        updated_at TEXT DEFAULT (datetime('now'))
    )""",
    ),
    (
        "document_reviewers",
        """CREATE TABLE IF NOT EXISTS document_reviewers (
        id TEXT PRIMARY KEY,
        document_id TEXT NOT NULL REFERENCES documents(id),
        person_id TEXT NOT NULL REFERENCES people(id),
        review_role TEXT,
        review_status TEXT,
        requested_at TEXT,
        responded_at TEXT,
        notes TEXT
    )""",
    ),
    (
        "task_dependencies",
        """CREATE TABLE IF NOT EXISTS task_dependencies (
        id TEXT PRIMARY KEY,
        task_id TEXT NOT NULL REFERENCES tasks(id),
        depends_on_task_id TEXT NOT NULL REFERENCES tasks(id),
        dependency_type TEXT,
        notes TEXT
    )""",
    ),
    (
        "matter_dependencies",
        """CREATE TABLE IF NOT EXISTS matter_dependencies (
        id TEXT PRIMARY KEY,
        matter_id TEXT NOT NULL REFERENCES matters(id),
        depends_on_matter_id TEXT NOT NULL REFERENCES matters(id),
        dependency_type TEXT,
        notes TEXT
    )""",
    ),
    (
        "tags",
        """CREATE TABLE IF NOT EXISTS tags (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        tag_type TEXT
    )""",
    ),
    (
        "matter_tags",
        """CREATE TABLE IF NOT EXISTS matter_tags (
        matter_id TEXT NOT NULL REFERENCES matters(id),
        tag_id TEXT NOT NULL REFERENCES tags(id),
        PRIMARY KEY (matter_id, tag_id)
    )""",
    ),
    # ---- Support tables ----
    (
        "matter_updates",
        """CREATE TABLE IF NOT EXISTS matter_updates (
        id TEXT PRIMARY KEY,
        matter_id TEXT NOT NULL REFERENCES matters(id),
        update_type TEXT,
        summary TEXT NOT NULL,
        created_by_person_id TEXT REFERENCES people(id),
        created_at TEXT DEFAULT (datetime('now'))
    )""",
    ),
    (
        "task_updates",
        """CREATE TABLE IF NOT EXISTS task_updates (
        id TEXT PRIMARY KEY,
        task_id TEXT NOT NULL REFERENCES tasks(id),
        update_type TEXT,
        summary TEXT NOT NULL,
        old_status TEXT,
        new_status TEXT,
        old_assigned_to_person_id TEXT,
        new_assigned_to_person_id TEXT,
        created_by_person_id TEXT,
        created_at TEXT DEFAULT (datetime('now'))
    )""",
    ),
    (
        "document_files",
        """CREATE TABLE IF NOT EXISTS document_files (
        id TEXT PRIMARY KEY,
        document_id TEXT NOT NULL REFERENCES documents(id),
        storage_provider TEXT,
        storage_path TEXT,
        original_filename TEXT NOT NULL,
        mime_type TEXT,
        file_size_bytes INTEGER,
        version_label TEXT,
        uploaded_at TEXT,
        uploaded_by_person_id TEXT,
        is_current INTEGER DEFAULT 1,
        notes TEXT,
        created_at TEXT DEFAULT (datetime('now')),
        updated_at TEXT DEFAULT (datetime('now'))
    )""",
    ),
    # ---- Rulemaking extension tables ----
    (
        "rulemaking_publication_status",
        """CREATE TABLE IF NOT EXISTS rulemaking_publication_status (
        id TEXT PRIMARY KEY,
        matter_id TEXT NOT NULL UNIQUE REFERENCES matters(id),
        ofr_submitted TEXT,
        ofr_accepted TEXT,
        ofr_publication_date TEXT,
        ofr_doc_number TEXT,
        pra_required INTEGER DEFAULT 0,
        pra_icr_number TEXT,
        pra_submitted_oira TEXT,
        pra_approved TEXT,
        pra_burden_hours INTEGER,
        oira_submitted TEXT,
        oira_review_type TEXT,
        oira_completed TEXT,
        oira_changes TEXT,
        cra_submitted TEXT,
        cra_review_period_end TEXT,
        cra_is_major INTEGER DEFAULT 0,
        cra_resolution_introduced INTEGER DEFAULT 0,
        fr_volume TEXT,
        fr_start_page TEXT,
        fr_end_page TEXT,
        effective_date TEXT,
        notes TEXT,
        updated_at TEXT DEFAULT (datetime('now'))
    )""",
    ),
    (
        "rulemaking_comment_periods",
        """CREATE TABLE IF NOT EXISTS rulemaking_comment_periods (
        id TEXT PRIMARY KEY,
        matter_id TEXT NOT NULL REFERENCES matters(id),
        comment_period_type TEXT,
        opens_at TEXT,
        closes_at TEXT,
        fr_doc_number TEXT,
        comment_count INTEGER,
        comment_docket TEXT,
        notes TEXT,
        created_at TEXT DEFAULT (datetime('now')),
        updated_at TEXT DEFAULT (datetime('now'))
    )""",
    ),
    (
        "rulemaking_cba_tracking",
        """CREATE TABLE IF NOT EXISTS rulemaking_cba_tracking (
        id TEXT PRIMARY KEY,
        matter_id TEXT NOT NULL UNIQUE REFERENCES matters(id),
        cba_status TEXT,
        analyst_assigned_person_id TEXT REFERENCES people(id),
        estimated_costs REAL,
        estimated_benefits REAL,
        net_benefit REAL,
        methodology TEXT,
        small_entity_impact TEXT,
        rfa_required INTEGER DEFAULT 0,
        irfa_completed INTEGER DEFAULT 0,
        frfa_completed INTEGER DEFAULT 0,
        notes TEXT,
        updated_at TEXT DEFAULT (datetime('now'))
    )""",
    ),
    # ---- Comment & Directive tables ----
    (
        "comment_topics",
        """CREATE TABLE IF NOT EXISTS comment_topics (
        id TEXT PRIMARY KEY,
        matter_id TEXT NOT NULL REFERENCES matters(id),
        topic_label TEXT NOT NULL,
        topic_area TEXT,
        assigned_to_person_id TEXT REFERENCES people(id),
        secondary_assignee_person_id TEXT REFERENCES people(id),
        position_status TEXT NOT NULL DEFAULT 'open',
        position_summary TEXT,
        priority TEXT,
        due_date TEXT,
        deadline_type TEXT,
        source_fr_doc_number TEXT,
        source_document_type TEXT,
        response_fr_doc_number TEXT,
        notes TEXT,
        sort_order INTEGER,
        source TEXT DEFAULT 'manual',
        source_id TEXT,
        ai_confidence REAL,
        automation_hold INTEGER DEFAULT 0,
        external_refs TEXT,
        created_at TEXT DEFAULT (datetime('now')),
        updated_at TEXT DEFAULT (datetime('now'))
    )""",
    ),
    (
        "comment_questions",
        """CREATE TABLE IF NOT EXISTS comment_questions (
        id TEXT PRIMARY KEY,
        comment_topic_id TEXT NOT NULL REFERENCES comment_topics(id),
        question_number TEXT NOT NULL,
        question_text TEXT NOT NULL,
        sort_order INTEGER,
        source TEXT DEFAULT 'manual',
        source_id TEXT,
        ai_confidence REAL,
        created_at TEXT DEFAULT (datetime('now'))
    )""",
    ),
    (
        "policy_directives",
        """CREATE TABLE IF NOT EXISTS policy_directives (
        id TEXT PRIMARY KEY,
        source_document TEXT NOT NULL,
        source_document_type TEXT NOT NULL,
        source_document_url TEXT,
        source_date TEXT,
        directive_label TEXT NOT NULL,
        directive_text TEXT,
        section_reference TEXT,
        chapter TEXT,
        priority_tier TEXT,
        responsible_entity TEXT,
        ogc_role TEXT,
        assigned_to_person_id TEXT REFERENCES people(id),
        implementation_status TEXT NOT NULL DEFAULT 'not_started',
        implementation_notes TEXT,
        target_date TEXT,
        completed_date TEXT,
        notes TEXT,
        sort_order INTEGER,
        source TEXT DEFAULT 'manual',
        source_id TEXT,
        external_refs TEXT,
        created_at TEXT DEFAULT (datetime('now')),
        updated_at TEXT DEFAULT (datetime('now'))
    )""",
    ),
    (
        "directive_research_notes",
        """CREATE TABLE IF NOT EXISTS directive_research_notes (
        id TEXT PRIMARY KEY,
        directive_id TEXT NOT NULL REFERENCES policy_directives(id),
        fr_citation TEXT,
        rule_title TEXT,
        cfr_parts TEXT,
        statutory_authority TEXT,
        action_category TEXT,
        composite_score REAL,
        relationship_basis TEXT,
        analysis_summary TEXT,
        regulation_text_excerpt TEXT,
        needs_reg_reading INTEGER DEFAULT 0,
        reg_reading_done INTEGER DEFAULT 0,
        reg_reading_notes TEXT,
        promote_to_matter INTEGER DEFAULT 0,
        matter_id TEXT REFERENCES matters(id),
        created_at TEXT DEFAULT (datetime('now')),
        updated_at TEXT DEFAULT (datetime('now'))
    )""",
    ),
    (
        "directive_matters",
        """CREATE TABLE IF NOT EXISTS directive_matters (
        id TEXT PRIMARY KEY,
        directive_id TEXT NOT NULL REFERENCES policy_directives(id),
        matter_id TEXT NOT NULL REFERENCES matters(id),
        relationship_type TEXT NOT NULL DEFAULT 'implements',
        notes TEXT,
        created_at TEXT DEFAULT (datetime('now')),
        UNIQUE(directive_id, matter_id)
    )""",
    ),
    # ---- Comment & Directive tables ----
    # ---- Automation tables ----
    (
        "system_events",
        """CREATE TABLE IF NOT EXISTS system_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        table_name TEXT NOT NULL,
        record_id TEXT NOT NULL,
        action TEXT NOT NULL,
        source TEXT NOT NULL,
        changed_fields TEXT,
        old_values TEXT,
        new_values TEXT,
        actor_person_id TEXT,
        created_at TEXT DEFAULT (datetime('now'))
    )""",
    ),
    (
        "idempotency_keys",
        """CREATE TABLE IF NOT EXISTS idempotency_keys (
        key TEXT PRIMARY KEY,
        method TEXT NOT NULL,
        path TEXT NOT NULL,
        request_hash TEXT NOT NULL,
        status_code INTEGER,
        response_body TEXT,
        created_at TEXT DEFAULT (datetime('now'))
    )""",
    ),
    (
        "schema_versions",
        """CREATE TABLE IF NOT EXISTS schema_versions (
        version INTEGER PRIMARY KEY,
        description TEXT NOT NULL,
        applied_at TEXT DEFAULT (datetime('now'))
    )""",
    ),
    (
        "sync_state",
        """CREATE TABLE IF NOT EXISTS sync_state (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sync_type TEXT NOT NULL UNIQUE,
        last_run_at TEXT,
        last_status TEXT,
        last_error TEXT,
        items_created INTEGER DEFAULT 0,
        items_updated INTEGER DEFAULT 0,
        next_run_at TEXT,
        config_json TEXT
    )""",
    ),
    # ---- System Config (key-value store) ----
    (
        "system_config",
        """CREATE TABLE IF NOT EXISTS system_config (
        key TEXT PRIMARY KEY,
        value TEXT,
        updated_at TEXT DEFAULT (datetime('now'))
    )""",
    ),
]

# ---------------------------------------------------------------------------
# Index definitions
# ---------------------------------------------------------------------------

INDEXES = [
    # -- matters --
    "CREATE INDEX IF NOT EXISTS idx_matters_status ON matters(status);",
    "CREATE INDEX IF NOT EXISTS idx_matters_priority ON matters(priority);",
    "CREATE INDEX IF NOT EXISTS idx_matters_sensitivity ON matters(sensitivity);",
    "CREATE INDEX IF NOT EXISTS idx_matters_assigned_to ON matters(assigned_to_person_id);",
    "CREATE INDEX IF NOT EXISTS idx_matters_client_org ON matters(client_organization_id);",
    "CREATE INDEX IF NOT EXISTS idx_matters_work_deadline ON matters(work_deadline);",
    "CREATE INDEX IF NOT EXISTS idx_matters_external_deadline ON matters(external_deadline);",
    "CREATE INDEX IF NOT EXISTS idx_matters_last_material_update ON matters(last_material_update_at);",
    "CREATE INDEX IF NOT EXISTS idx_matters_source ON matters(source);",
    "CREATE INDEX IF NOT EXISTS idx_matters_automation_hold ON matters(automation_hold);",
    "CREATE INDEX IF NOT EXISTS idx_matters_matter_type ON matters(matter_type);",
    # -- tasks --
    "CREATE INDEX IF NOT EXISTS idx_tasks_matter ON tasks(matter_id);",
    "CREATE INDEX IF NOT EXISTS idx_tasks_assigned_to ON tasks(assigned_to_person_id);",
    "CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);",
    "CREATE INDEX IF NOT EXISTS idx_tasks_due_date ON tasks(due_date);",
    "CREATE INDEX IF NOT EXISTS idx_tasks_waiting_on_person ON tasks(waiting_on_person_id);",
    "CREATE INDEX IF NOT EXISTS idx_tasks_waiting_on_org ON tasks(waiting_on_org_id);",
    "CREATE INDEX IF NOT EXISTS idx_tasks_task_type ON tasks(task_type);",
    "CREATE INDEX IF NOT EXISTS idx_tasks_deadline_type ON tasks(deadline_type);",
    "CREATE INDEX IF NOT EXISTS idx_tasks_tracks_task_id ON tasks(tracks_task_id);",
    # -- documents --
    "CREATE INDEX IF NOT EXISTS idx_documents_matter ON documents(matter_id);",
    "CREATE INDEX IF NOT EXISTS idx_documents_status ON documents(status);",
    "CREATE INDEX IF NOT EXISTS idx_documents_due_date ON documents(due_date);",
    # -- meetings --
    "CREATE INDEX IF NOT EXISTS idx_meetings_start ON meetings(date_time_start);",
    # -- people --
    "CREATE INDEX IF NOT EXISTS idx_people_organization ON people(organization_id);",
    "CREATE INDEX IF NOT EXISTS idx_people_next_interaction ON people(next_interaction_needed_date);",
    "CREATE INDEX IF NOT EXISTS idx_people_team_workload ON people(include_in_team_workload);",
    "CREATE INDEX IF NOT EXISTS idx_people_manager ON people(manager_person_id);",
    # -- organizations --
    "CREATE INDEX IF NOT EXISTS idx_orgs_type ON organizations(organization_type);",
    "CREATE INDEX IF NOT EXISTS idx_orgs_parent ON organizations(parent_organization_id);",
    "CREATE INDEX IF NOT EXISTS idx_orgs_active ON organizations(is_active);",
    # -- document_files --
    "CREATE INDEX IF NOT EXISTS idx_doc_files_document ON document_files(document_id);",
    "CREATE INDEX IF NOT EXISTS idx_doc_files_current ON document_files(is_current);",
    "CREATE INDEX IF NOT EXISTS idx_doc_files_uploaded ON document_files(uploaded_at);",
    # -- task_updates --
    "CREATE INDEX IF NOT EXISTS idx_task_updates_task ON task_updates(task_id);",
    "CREATE INDEX IF NOT EXISTS idx_task_updates_created ON task_updates(created_at);",
    # -- matter_updates --
    "CREATE INDEX IF NOT EXISTS idx_matter_updates_matter ON matter_updates(matter_id);",
    "CREATE INDEX IF NOT EXISTS idx_matter_updates_created ON matter_updates(created_at);",
    # -- junction table composites --
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_matter_people_unique ON matter_people(matter_id, person_id, matter_role);",
    "CREATE INDEX IF NOT EXISTS idx_matter_people_person ON matter_people(person_id);",
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_matter_orgs_unique ON matter_organizations(matter_id, organization_id, organization_role);",
    "CREATE INDEX IF NOT EXISTS idx_matter_orgs_org ON matter_organizations(organization_id);",
    "CREATE INDEX IF NOT EXISTS idx_matter_orgs_role ON matter_organizations(organization_role);",
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_meeting_participants_unique ON meeting_participants(meeting_id, person_id);",
    "CREATE INDEX IF NOT EXISTS idx_meeting_participants_person ON meeting_participants(person_id);",
    "CREATE INDEX IF NOT EXISTS idx_meeting_participants_org ON meeting_participants(organization_id);",
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_meeting_matters_unique ON meeting_matters(meeting_id, matter_id);",
    "CREATE INDEX IF NOT EXISTS idx_meeting_matters_matter ON meeting_matters(matter_id);",
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_doc_reviewers_unique ON document_reviewers(document_id, person_id);",
    "CREATE INDEX IF NOT EXISTS idx_doc_reviewers_person ON document_reviewers(person_id);",
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_task_deps_unique ON task_dependencies(task_id, depends_on_task_id);",
    "CREATE INDEX IF NOT EXISTS idx_task_deps_depends_on ON task_dependencies(depends_on_task_id);",
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_matter_deps_unique ON matter_dependencies(matter_id, depends_on_matter_id);",
    "CREATE INDEX IF NOT EXISTS idx_matter_deps_depends_on ON matter_dependencies(depends_on_matter_id);",
    # -- system_events --
    "CREATE INDEX IF NOT EXISTS idx_sysevents_table_created ON system_events(table_name, created_at);",
    "CREATE INDEX IF NOT EXISTS idx_sysevents_source_created ON system_events(source, created_at);",
    "CREATE INDEX IF NOT EXISTS idx_idempotency_created ON idempotency_keys(created_at);",
    "CREATE INDEX IF NOT EXISTS idx_sysevents_record ON system_events(record_id);",
    # -- sync_state --
    "CREATE INDEX IF NOT EXISTS idx_sync_state_type ON sync_state(sync_type);",
    # -- rulemaking tables --
    "CREATE INDEX IF NOT EXISTS idx_rulemaking_pub_matter ON rulemaking_publication_status(matter_id);",
    "CREATE INDEX IF NOT EXISTS idx_rulemaking_comments_matter ON rulemaking_comment_periods(matter_id);",
    "CREATE INDEX IF NOT EXISTS idx_rulemaking_comments_closes ON rulemaking_comment_periods(closes_at);",
    "CREATE INDEX IF NOT EXISTS idx_rulemaking_cba_matter ON rulemaking_cba_tracking(matter_id);",
    # -- context_notes --
    "CREATE INDEX IF NOT EXISTS idx_ctx_notes_category ON context_notes(category);",
    "CREATE INDEX IF NOT EXISTS idx_ctx_notes_matter ON context_notes(matter_id);",
    "CREATE INDEX IF NOT EXISTS idx_ctx_notes_active ON context_notes(is_active);",
    "CREATE INDEX IF NOT EXISTS idx_ctx_notes_posture ON context_notes(posture);",
    "CREATE INDEX IF NOT EXISTS idx_ctx_notes_sensitivity ON context_notes(sensitivity);",
    "CREATE INDEX IF NOT EXISTS idx_ctx_notes_created ON context_notes(created_at);",
    "CREATE INDEX IF NOT EXISTS idx_ctx_notes_stale ON context_notes(stale_after);",
    "CREATE INDEX IF NOT EXISTS idx_ctx_notes_source_comm ON context_notes(source_communication_id);",
    # -- context_note_links --
    "CREATE INDEX IF NOT EXISTS idx_ctx_note_links_note ON context_note_links(context_note_id);",
    "CREATE INDEX IF NOT EXISTS idx_ctx_note_links_entity ON context_note_links(entity_type, entity_id);",
    # -- person_profiles --
    "CREATE INDEX IF NOT EXISTS idx_person_profiles_person ON person_profiles(person_id);",
    # -- decisions --
    "CREATE INDEX IF NOT EXISTS idx_decisions_matter ON decisions(matter_id);",
    "CREATE INDEX IF NOT EXISTS idx_decisions_status ON decisions(status);",
    # -- comment_topics --
    "CREATE INDEX IF NOT EXISTS idx_comment_topics_matter ON comment_topics(matter_id);",
    "CREATE INDEX IF NOT EXISTS idx_comment_topics_status ON comment_topics(position_status);",
    "CREATE INDEX IF NOT EXISTS idx_comment_topics_assigned ON comment_topics(assigned_to_person_id);",
    "CREATE INDEX IF NOT EXISTS idx_comment_topics_due ON comment_topics(due_date);",
    "CREATE INDEX IF NOT EXISTS idx_comment_topics_source_doc ON comment_topics(source_fr_doc_number);",
    "CREATE INDEX IF NOT EXISTS idx_comment_topics_area ON comment_topics(topic_area);",
    # -- comment_questions --
    "CREATE INDEX IF NOT EXISTS idx_comment_questions_topic ON comment_questions(comment_topic_id);",
    # -- policy_directives --
    "CREATE INDEX IF NOT EXISTS idx_directives_status ON policy_directives(implementation_status);",
    "CREATE INDEX IF NOT EXISTS idx_directives_responsible ON policy_directives(responsible_entity);",
    "CREATE INDEX IF NOT EXISTS idx_directives_assigned ON policy_directives(assigned_to_person_id);",
    "CREATE INDEX IF NOT EXISTS idx_directives_source_type ON policy_directives(source_document_type);",
    "CREATE INDEX IF NOT EXISTS idx_directives_source_date ON policy_directives(source_date);",
    "CREATE INDEX IF NOT EXISTS idx_directives_ogc_role ON policy_directives(ogc_role);",
    "CREATE INDEX IF NOT EXISTS idx_directives_target_date ON policy_directives(target_date);",
    # -- directive_matters --
    "CREATE INDEX IF NOT EXISTS idx_dir_matters_directive ON directive_matters(directive_id);",
    "CREATE INDEX IF NOT EXISTS idx_dir_matters_matter ON directive_matters(matter_id);",
    # -- comment_topics --
    # -- comment_questions --
    # -- policy_directives --
    # -- directive_matters --
]


# ---------------------------------------------------------------------------
# Schema initializer
# ---------------------------------------------------------------------------


def init_schema(conn: sqlite3.Connection) -> list[str]:
    """Create all tables and indexes. Idempotent.

    Returns the names of tables that were newly created during this call.
    """
    cursor = conn.cursor()
    existing = {
        row[0]
        for row in cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }

    created: list[str] = []
    for name, sql in TABLES:
        if name not in existing:
            created.append(name)
        cursor.execute(sql)

    for idx in INDEXES:
        cursor.execute(idx)

    conn.commit()

    if created:
        logger.info("Created %d new tables: %s", len(created), ", ".join(created))
    else:
        logger.debug("Schema up to date — no new tables created.")

    return created


# ---------------------------------------------------------------------------
# Versioned migrations
# ---------------------------------------------------------------------------

# Each migration: (version, description, sql_statements_list)
# Existing ad-hoc migrations are version 1 (the baseline).
MIGRATIONS = [
    # Version 1: baseline (all prior ad-hoc migrations consolidated)
    # No SQL — represents the state before versioned migrations.
    # Version 2: add missing indexes
    (
        2,
        "add_missing_indexes",
        [
            "CREATE INDEX IF NOT EXISTS idx_tasks_task_mode ON tasks(task_mode)",
            "CREATE INDEX IF NOT EXISTS idx_meetings_meeting_type ON meetings(meeting_type)",
            "CREATE INDEX IF NOT EXISTS idx_documents_document_type ON documents(document_type)",
        ],
    ),
    # Version 3: comment topics, policy directives tables and indexes
    (
        3,
        "comment_topics_policy_directives",
        [
            # Tables
            """CREATE TABLE IF NOT EXISTS comment_topics (
            id TEXT PRIMARY KEY,
            matter_id TEXT NOT NULL REFERENCES matters(id),
            topic_label TEXT NOT NULL,
            topic_area TEXT,
            assigned_to_person_id TEXT REFERENCES people(id),
            secondary_assignee_person_id TEXT REFERENCES people(id),
            position_status TEXT NOT NULL DEFAULT 'open',
            position_summary TEXT,
            priority TEXT,
            due_date TEXT,
            deadline_type TEXT,
            source_fr_doc_number TEXT,
            source_document_type TEXT,
            response_fr_doc_number TEXT,
            notes TEXT,
            sort_order INTEGER,
            source TEXT DEFAULT 'manual',
            source_id TEXT,
            ai_confidence REAL,
            automation_hold INTEGER DEFAULT 0,
            external_refs TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        )""",
            """CREATE TABLE IF NOT EXISTS comment_questions (
            id TEXT PRIMARY KEY,
            comment_topic_id TEXT NOT NULL REFERENCES comment_topics(id),
            question_number TEXT NOT NULL,
            question_text TEXT NOT NULL,
            sort_order INTEGER,
            source TEXT DEFAULT 'manual',
            source_id TEXT,
            ai_confidence REAL,
            created_at TEXT DEFAULT (datetime('now'))
        )""",
            """CREATE TABLE IF NOT EXISTS policy_directives (
            id TEXT PRIMARY KEY,
            source_document TEXT NOT NULL,
            source_document_type TEXT NOT NULL,
            source_document_url TEXT,
            source_date TEXT,
            directive_label TEXT NOT NULL,
            directive_text TEXT,
            section_reference TEXT,
            chapter TEXT,
            priority_tier TEXT,
            responsible_entity TEXT,
            ogc_role TEXT,
            assigned_to_person_id TEXT REFERENCES people(id),
            implementation_status TEXT NOT NULL DEFAULT 'not_started',
            implementation_notes TEXT,
            target_date TEXT,
            completed_date TEXT,
            notes TEXT,
            sort_order INTEGER,
            source TEXT DEFAULT 'manual',
            source_id TEXT,
            external_refs TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        )""",
            """CREATE TABLE IF NOT EXISTS directive_matters (
            id TEXT PRIMARY KEY,
            directive_id TEXT NOT NULL REFERENCES policy_directives(id),
            matter_id TEXT NOT NULL REFERENCES matters(id),
            relationship_type TEXT NOT NULL DEFAULT 'implements',
            notes TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            UNIQUE(directive_id, matter_id)
        )""",
            # Indexes
            "CREATE INDEX IF NOT EXISTS idx_comment_topics_matter ON comment_topics(matter_id)",
            "CREATE INDEX IF NOT EXISTS idx_comment_topics_status ON comment_topics(position_status)",
            "CREATE INDEX IF NOT EXISTS idx_comment_topics_assigned ON comment_topics(assigned_to_person_id)",
            "CREATE INDEX IF NOT EXISTS idx_comment_topics_due ON comment_topics(due_date)",
            "CREATE INDEX IF NOT EXISTS idx_comment_topics_source_doc ON comment_topics(source_fr_doc_number)",
            "CREATE INDEX IF NOT EXISTS idx_comment_topics_area ON comment_topics(topic_area)",
            "CREATE INDEX IF NOT EXISTS idx_comment_questions_topic ON comment_questions(comment_topic_id)",
            "CREATE INDEX IF NOT EXISTS idx_directives_status ON policy_directives(implementation_status)",
            "CREATE INDEX IF NOT EXISTS idx_directives_responsible ON policy_directives(responsible_entity)",
            "CREATE INDEX IF NOT EXISTS idx_directives_assigned ON policy_directives(assigned_to_person_id)",
            "CREATE INDEX IF NOT EXISTS idx_directives_source_type ON policy_directives(source_document_type)",
            "CREATE INDEX IF NOT EXISTS idx_directives_source_date ON policy_directives(source_date)",
            "CREATE INDEX IF NOT EXISTS idx_directives_ogc_role ON policy_directives(ogc_role)",
            "CREATE INDEX IF NOT EXISTS idx_directives_target_date ON policy_directives(target_date)",
            "CREATE INDEX IF NOT EXISTS idx_dir_matters_directive ON directive_matters(directive_id)",
            "CREATE INDEX IF NOT EXISTS idx_dir_matters_matter ON directive_matters(matter_id)",
        ],
    ),
    # Version 4: directive_documents join table (links directives to documents)
    (
        4,
        "directive_documents",
        [
            """CREATE TABLE IF NOT EXISTS directive_documents (
            id TEXT PRIMARY KEY,
            directive_id TEXT NOT NULL REFERENCES policy_directives(id),
            document_id TEXT NOT NULL REFERENCES documents(id),
            relationship_type TEXT NOT NULL DEFAULT 'references',
            notes TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            UNIQUE(directive_id, document_id)
        )""",
            "CREATE INDEX IF NOT EXISTS idx_directive_documents_directive ON directive_documents(directive_id)",
            "CREATE INDEX IF NOT EXISTS idx_directive_documents_document ON directive_documents(document_id)",
        ],
    ),
    # Version 5: Matter schema redesign Phase 1 — extension tables + blocker + staleness + seq
    (
        5,
        "matter_schema_redesign_phase1",
        [
            # -- matter_rulemaking (1:1 extension) --
            """CREATE TABLE IF NOT EXISTS matter_rulemaking (
            matter_id TEXT PRIMARY KEY REFERENCES matters(id) ON DELETE CASCADE,
            rin TEXT,
            regulatory_stage TEXT,
            workflow_status TEXT,
            current_comment_period_closes TEXT,
            federal_register_citation TEXT,
            unified_agenda_priority TEXT,
            cfr_citation TEXT,
            docket_number TEXT,
            fr_doc_number TEXT,
            interagency_role TEXT,
            is_petition INTEGER DEFAULT 0,
            petition_disposition TEXT,
            review_trigger TEXT,
            updated_at TEXT DEFAULT (datetime('now'))
        )""",

            # -- matter_guidance (1:1 extension) --
            """CREATE TABLE IF NOT EXISTS matter_guidance (
            matter_id TEXT PRIMARY KEY REFERENCES matters(id) ON DELETE CASCADE,
            instrument_type TEXT,
            published_in_fr INTEGER DEFAULT 0,
            cftc_letter_number TEXT,
            request_date TEXT,
            requestor_name TEXT,
            requestor_organization_id TEXT REFERENCES organizations(id),
            requestor_counsel TEXT,
            issuing_office_id TEXT REFERENCES organizations(id),
            signatory_person_id TEXT REFERENCES people(id),
            staff_contact_person_id TEXT REFERENCES people(id),
            cea_provisions TEXT,
            cfr_provisions TEXT,
            legal_question TEXT,
            conditions_summary TEXT,
            amends_matter_id TEXT REFERENCES matters(id),
            prior_letter_number TEXT,
            workflow_status TEXT,
            issuance_date TEXT,
            expiration_date TEXT,
            updated_at TEXT DEFAULT (datetime('now'))
        )""",

            # -- matter_enforcement (1:1 extension) --
            """CREATE TABLE IF NOT EXISTS matter_enforcement (
            matter_id TEXT PRIMARY KEY REFERENCES matters(id) ON DELETE CASCADE,
            requesting_division_id TEXT REFERENCES organizations(id),
            enforcement_reference TEXT,
            legal_issue_type TEXT,
            support_type TEXT,
            litigation_stage TEXT,
            court_or_forum TEXT,
            deadline_source TEXT,
            workflow_status TEXT,
            privilege_flags TEXT,
            is_confidential INTEGER DEFAULT 1,
            updated_at TEXT DEFAULT (datetime('now'))
        )""",

            # -- matter_regulatory_ids (Stage 1 bridge) --
            """CREATE TABLE IF NOT EXISTS matter_regulatory_ids (
            id TEXT PRIMARY KEY,
            matter_id TEXT NOT NULL REFERENCES matters(id) ON DELETE CASCADE,
            id_type TEXT NOT NULL,
            id_value TEXT NOT NULL,
            relationship TEXT NOT NULL DEFAULT 'primary',
            notes TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )""",

            # -- matter_number_seq (atomic sequence) --
            """CREATE TABLE IF NOT EXISTS matter_number_seq (
            prefix TEXT NOT NULL DEFAULT 'MAT',
            year INTEGER NOT NULL,
            next_val INTEGER NOT NULL DEFAULT 1,
            PRIMARY KEY (prefix, year)
        )""",

            # -- staleness_config (type-aware thresholds) --
            """CREATE TABLE IF NOT EXISTS staleness_config (
            id TEXT PRIMARY KEY,
            matter_type TEXT NOT NULL,
            workflow_status TEXT,
            stale_days INTEGER NOT NULL,
            critical_stale_days INTEGER NOT NULL,
            description TEXT
        )""",

            # -- blocker column on base matters table --
            "ALTER TABLE matters ADD COLUMN blocker TEXT",

            # -- Indexes --
            "CREATE INDEX IF NOT EXISTS idx_mr_rin ON matter_rulemaking(rin) WHERE rin IS NOT NULL",
            "CREATE INDEX IF NOT EXISTS idx_mr_stage ON matter_rulemaking(regulatory_stage)",
            "CREATE INDEX IF NOT EXISTS idx_mr_workflow ON matter_rulemaking(workflow_status)",
            "CREATE INDEX IF NOT EXISTS idx_mr_comment_closes ON matter_rulemaking(current_comment_period_closes) WHERE current_comment_period_closes IS NOT NULL",
            "CREATE INDEX IF NOT EXISTS idx_mr_docket ON matter_rulemaking(docket_number) WHERE docket_number IS NOT NULL",
            "CREATE INDEX IF NOT EXISTS idx_mg_instrument ON matter_guidance(instrument_type)",
            "CREATE INDEX IF NOT EXISTS idx_mg_workflow ON matter_guidance(workflow_status)",
            "CREATE INDEX IF NOT EXISTS idx_mg_issuing ON matter_guidance(issuing_office_id)",
            "CREATE INDEX IF NOT EXISTS idx_mg_letter ON matter_guidance(cftc_letter_number) WHERE cftc_letter_number IS NOT NULL",
            "CREATE INDEX IF NOT EXISTS idx_me_litigation ON matter_enforcement(litigation_stage)",
            "CREATE INDEX IF NOT EXISTS idx_me_workflow ON matter_enforcement(workflow_status)",
            "CREATE INDEX IF NOT EXISTS idx_me_division ON matter_enforcement(requesting_division_id)",
            "CREATE INDEX IF NOT EXISTS idx_mri_matter ON matter_regulatory_ids(matter_id)",
            "CREATE INDEX IF NOT EXISTS idx_mri_type_value ON matter_regulatory_ids(id_type, id_value)",
            "CREATE INDEX IF NOT EXISTS idx_mri_value ON matter_regulatory_ids(id_value)",
            "CREATE INDEX IF NOT EXISTS idx_matters_blocker ON matters(blocker) WHERE blocker IS NOT NULL",

            # -- Triggers for updated_at on extension tables --
            """CREATE TRIGGER IF NOT EXISTS trg_matter_rulemaking_updated
            AFTER UPDATE ON matter_rulemaking
            BEGIN
                UPDATE matter_rulemaking SET updated_at = datetime('now')
                WHERE matter_id = NEW.matter_id;
            END""",
            """CREATE TRIGGER IF NOT EXISTS trg_matter_guidance_updated
            AFTER UPDATE ON matter_guidance
            BEGIN
                UPDATE matter_guidance SET updated_at = datetime('now')
                WHERE matter_id = NEW.matter_id;
            END""",
            """CREATE TRIGGER IF NOT EXISTS trg_matter_enforcement_updated
            AFTER UPDATE ON matter_enforcement
            BEGIN
                UPDATE matter_enforcement SET updated_at = datetime('now')
                WHERE matter_id = NEW.matter_id;
            END""",
        ],
    ),
]


def _get_current_version(conn: sqlite3.Connection) -> int:
    """Get the latest applied migration version, or 0 if none."""
    try:
        row = conn.execute("SELECT MAX(version) as v FROM schema_versions").fetchone()
        return row["v"] if row and row["v"] is not None else 0
    except Exception:
        return 0


def migrate_schema(conn: sqlite3.Connection):
    """Run forward-only versioned migrations. Idempotent."""
    cursor = conn.cursor()

    # ── Legacy migrations (pre-versioned, still idempotent) ──
    cols = {row[1] for row in cursor.execute("PRAGMA table_info(people)")}
    for col in ("relationship_lane", "working_style_notes", "personality"):
        if col in cols:
            cursor.execute(f"ALTER TABLE people DROP COLUMN {col}")
            logger.info("Legacy migration: dropped people.%s", col)
            conn.commit()

    task_cols = {row[1] for row in cursor.execute("PRAGMA table_info(tasks)")}
    if "tracks_task_id" not in task_cols:
        cursor.execute(
            "ALTER TABLE tasks ADD COLUMN tracks_task_id TEXT REFERENCES tasks(id)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_tasks_tracks_task_id ON tasks(tracks_task_id)"
        )
        logger.info("Legacy migration: added tasks.tracks_task_id")
        conn.commit()

    if "trigger_description" not in task_cols:
        cursor.execute("ALTER TABLE tasks ADD COLUMN trigger_description TEXT")
        logger.info("Legacy migration: added tasks.trigger_description")
        conn.commit()

    # Normalize task_mode values (idempotent — only touches non-standard values)
    cursor.execute(
        "UPDATE tasks SET task_mode = 'action' WHERE task_mode LIKE 'delegated%'"
    )
    cursor.execute(
        "UPDATE tasks SET task_mode = 'follow_up' WHERE task_mode LIKE 'waiting%'"
    )
    cursor.execute(
        "UPDATE tasks SET task_mode = 'follow_up' WHERE task_mode = 'decision'"
    )
    cursor.execute(
        "UPDATE tasks SET task_mode = 'action' WHERE task_mode NOT IN ('action', 'follow_up', 'monitoring')"
    )
    conn.commit()

    # Seed version 1 if schema_versions is empty (represents baseline)
    current = _get_current_version(conn)
    if current == 0:
        cursor.execute(
            "INSERT OR IGNORE INTO schema_versions (version, description) VALUES (1, 'baseline')"
        )
        conn.commit()
        current = 1

    # ── Versioned migrations ──
    for version, description, statements in MIGRATIONS:
        if version <= current:
            continue
        logger.info("Applying migration v%d: %s", version, description)
        for sql in statements:
            cursor.execute(sql)
        cursor.execute(
            "INSERT INTO schema_versions (version, description) VALUES (?, ?)",
            (version, description),
        )
        conn.commit()
        logger.info("Migration v%d applied successfully", version)
