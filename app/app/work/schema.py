"""
Database schema for the Work Management module.
All tables in work.db. Idempotent (IF NOT EXISTS).
"""

import sqlite3
import logging

logger = logging.getLogger(__name__)

WORK_TABLES = [
    ("project_types", """
    CREATE TABLE IF NOT EXISTS project_types (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        type_key    TEXT UNIQUE NOT NULL,
        label       TEXT NOT NULL,
        description TEXT,
        sort_order  INTEGER DEFAULT 0
    )
    """),

    ("projects", """
    CREATE TABLE IF NOT EXISTS projects (
        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
        title               TEXT NOT NULL,
        short_title         TEXT,
        description         TEXT,
        project_type        TEXT NOT NULL,
        status              TEXT NOT NULL DEFAULT 'active',
        priority_label      TEXT NOT NULL DEFAULT 'medium',
        lead_attorney_id    INTEGER,
        linked_pipeline_id  INTEGER,
        linked_docket       TEXT,
        linked_eo_doc_id    INTEGER,
        sort_order          INTEGER DEFAULT 0,
        created_at          TEXT DEFAULT (datetime('now')),
        updated_at          TEXT DEFAULT (datetime('now'))
    )
    """),

    ("projects_indexes", """
    CREATE INDEX IF NOT EXISTS idx_proj_status ON projects(status);
    CREATE INDEX IF NOT EXISTS idx_proj_type ON projects(project_type);
    CREATE INDEX IF NOT EXISTS idx_proj_lead ON projects(lead_attorney_id);
    CREATE INDEX IF NOT EXISTS idx_proj_priority ON projects(priority_label);
    """),

    ("work_items", """
    CREATE TABLE IF NOT EXISTS work_items (
        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
        project_id          INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
        parent_id           INTEGER REFERENCES work_items(id) ON DELETE CASCADE,
        title               TEXT NOT NULL,
        description         TEXT,
        status              TEXT NOT NULL DEFAULT 'not_started',
        priority_label      TEXT,
        due_date            TEXT,
        blocked_reason      TEXT,
        sort_order          INTEGER DEFAULT 0,
        created_at          TEXT DEFAULT (datetime('now')),
        updated_at          TEXT DEFAULT (datetime('now')),
        completed_at        TEXT
    )
    """),

    ("work_items_indexes", """
    CREATE INDEX IF NOT EXISTS idx_wi_project ON work_items(project_id);
    CREATE INDEX IF NOT EXISTS idx_wi_parent ON work_items(parent_id);
    CREATE INDEX IF NOT EXISTS idx_wi_status ON work_items(status);
    CREATE INDEX IF NOT EXISTS idx_wi_due ON work_items(due_date);
    """),

    ("work_item_assignments", """
    CREATE TABLE IF NOT EXISTS work_item_assignments (
        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
        work_item_id        INTEGER NOT NULL REFERENCES work_items(id) ON DELETE CASCADE,
        team_member_id      INTEGER NOT NULL,
        role                TEXT NOT NULL DEFAULT 'assigned',
        assigned_at         TEXT DEFAULT (datetime('now')),
        UNIQUE(work_item_id, team_member_id, role)
    )
    """),

    ("work_item_assignments_indexes", """
    CREATE INDEX IF NOT EXISTS idx_wia_item ON work_item_assignments(work_item_id);
    CREATE INDEX IF NOT EXISTS idx_wia_member ON work_item_assignments(team_member_id);
    """),

    ("work_item_dependencies", """
    CREATE TABLE IF NOT EXISTS work_item_dependencies (
        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
        blocked_item_id     INTEGER NOT NULL REFERENCES work_items(id) ON DELETE CASCADE,
        blocking_item_id    INTEGER NOT NULL REFERENCES work_items(id) ON DELETE CASCADE,
        description         TEXT,
        resolved            INTEGER DEFAULT 0,
        resolved_at         TEXT,
        UNIQUE(blocked_item_id, blocking_item_id)
    )
    """),

    ("work_item_dependencies_indexes", """
    CREATE INDEX IF NOT EXISTS idx_wid_blocked ON work_item_dependencies(blocked_item_id);
    CREATE INDEX IF NOT EXISTS idx_wid_blocking ON work_item_dependencies(blocking_item_id);
    """),

    ("tasks", """
    CREATE TABLE IF NOT EXISTS tasks (
        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
        title               TEXT NOT NULL,
        description         TEXT,
        status              TEXT NOT NULL DEFAULT 'todo',
        priority_label      TEXT DEFAULT 'medium',
        due_date            TEXT,
        project_id          INTEGER REFERENCES projects(id) ON DELETE SET NULL,
        work_item_id        INTEGER REFERENCES work_items(id) ON DELETE SET NULL,
        linked_member_id    INTEGER,
        tags                TEXT DEFAULT '[]',
        notes               TEXT,
        source_system       TEXT,
        source_id           TEXT,
        created_at          TEXT DEFAULT (datetime('now')),
        updated_at          TEXT DEFAULT (datetime('now')),
        completed_at        TEXT
    )
    """),

    ("tasks_indexes", """
    CREATE INDEX IF NOT EXISTS idx_task_status ON tasks(status);
    CREATE INDEX IF NOT EXISTS idx_task_due ON tasks(due_date);
    CREATE INDEX IF NOT EXISTS idx_task_project ON tasks(project_id);
    CREATE INDEX IF NOT EXISTS idx_task_member ON tasks(linked_member_id);
    """),

    ("manager_notes", """
    CREATE TABLE IF NOT EXISTS manager_notes (
        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
        content             TEXT NOT NULL,
        project_id          INTEGER REFERENCES projects(id) ON DELETE SET NULL,
        work_item_id        INTEGER REFERENCES work_items(id) ON DELETE SET NULL,
        linked_member_id    INTEGER,
        note_type           TEXT DEFAULT 'general',
        created_at          TEXT DEFAULT (datetime('now'))
    )
    """),

    ("manager_notes_indexes", """
    CREATE INDEX IF NOT EXISTS idx_mn_project ON manager_notes(project_id);
    CREATE INDEX IF NOT EXISTS idx_mn_item ON manager_notes(work_item_id);
    CREATE INDEX IF NOT EXISTS idx_mn_member ON manager_notes(linked_member_id);
    """),

    ("project_type_templates", """
    CREATE TABLE IF NOT EXISTS project_type_templates (
        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
        project_type        TEXT NOT NULL,
        item_title          TEXT NOT NULL,
        item_description    TEXT,
        item_sort_order     INTEGER DEFAULT 0,
        parent_ref          TEXT
    )
    """),

    ("project_type_templates_index", """
    CREATE INDEX IF NOT EXISTS idx_ptt_type ON project_type_templates(project_type);
    """),
]


def init_work_schema(conn: sqlite3.Connection) -> list[str]:
    """Create all work management tables. Returns list of newly created table names."""
    created = []
    for name, sql in WORK_TABLES:
        if name.endswith("_indexes") or name.endswith("_index"):
            # Execute multi-statement index blocks
            for stmt in sql.strip().split(";"):
                stmt = stmt.strip()
                if stmt:
                    conn.execute(stmt)
        else:
            # Check if table already exists
            existing = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                (name,)
            ).fetchone()
            conn.execute(sql)
            if not existing:
                created.append(name)
    conn.commit()
    if created:
        logger.info(f"Work schema: created tables: {created}")
    return created
