#!/usr/bin/env python3
"""Normalize live tracker rows to the current tracker contract.

Creates a timestamped SQLite backup, applies a small set of enum/source
normalizations, and prints per-step row counts.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = REPO_ROOT / "services" / "tracker" / "data" / "tracker.db"
BACKUP_DIR = REPO_ROOT / "backups"

UPDATES = [
    ("organizations.organization_type", "UPDATE organizations SET organization_type = 'CFTC division' WHERE organization_type = 'internal_division'"),
    ("people.relationship_category", "UPDATE people SET relationship_category = 'Outside party' WHERE relationship_category = 'key contact'"),
    ("documents.document_type.federal_register", "UPDATE documents SET document_type = 'rulemaking_text' WHERE document_type = 'federal_register'"),
    ("documents.document_type.memorandum", "UPDATE documents SET document_type = 'legal_memo' WHERE document_type = 'memorandum'"),
    ("documents.status", "UPDATE documents SET status = 'drafting' WHERE status = 'draft'"),
    ("tasks.task_type", "UPDATE tasks SET task_type = 'research issue' WHERE task_type = 'research'"),
    ("matter_people.matter_role.lead", "UPDATE matter_people SET matter_role = 'lead attorney' WHERE matter_role = 'lead'"),
    ("matter_people.matter_role.point_of_contact", "UPDATE matter_people SET matter_role = 'leadership stakeholder' WHERE matter_role = 'point of contact'"),
    ("matter_organizations.organization_role", "UPDATE matter_organizations SET organization_role = 'partner agency' WHERE organization_role = 'joint_agency'"),
    ("source.human_to_manual", "UPDATE organizations SET source = 'manual' WHERE source IN ('human', 'test')"),
    ("source.human_to_manual", "UPDATE people SET source = 'manual' WHERE source IN ('human', 'test')"),
    ("source.human_to_manual", "UPDATE matters SET source = 'manual' WHERE source IN ('human', 'test')"),
    ("source.human_to_manual", "UPDATE tasks SET source = 'manual' WHERE source IN ('human', 'test')"),
    ("source.human_to_manual", "UPDATE meetings SET source = 'manual' WHERE source IN ('human', 'test')"),
    ("source.human_to_manual", "UPDATE documents SET source = 'manual' WHERE source IN ('human', 'test')"),
    ("source.human_to_manual", "UPDATE decisions SET source = 'manual' WHERE source IN ('human', 'test')"),
    ("source.fr_pipeline_to_federal_register", "UPDATE organizations SET source = 'federal_register' WHERE source = 'fr_pipeline'"),
    ("source.fr_pipeline_to_federal_register", "UPDATE people SET source = 'federal_register' WHERE source = 'fr_pipeline'"),
    ("source.fr_pipeline_to_federal_register", "UPDATE matters SET source = 'federal_register' WHERE source = 'fr_pipeline'"),
    ("source.fr_pipeline_to_federal_register", "UPDATE tasks SET source = 'federal_register' WHERE source = 'fr_pipeline'"),
    ("source.fr_pipeline_to_federal_register", "UPDATE meetings SET source = 'federal_register' WHERE source = 'fr_pipeline'"),
    ("source.fr_pipeline_to_federal_register", "UPDATE documents SET source = 'federal_register' WHERE source = 'fr_pipeline'"),
    ("source.fr_pipeline_to_federal_register", "UPDATE decisions SET source = 'federal_register' WHERE source = 'fr_pipeline'"),
]

VERIFY_QUERIES = {
    'organizations.organization_type': "SELECT DISTINCT organization_type FROM organizations WHERE organization_type = 'internal_division'",
    'people.relationship_category': "SELECT DISTINCT relationship_category FROM people WHERE relationship_category = 'key contact'",
    'documents.document_type': "SELECT DISTINCT document_type FROM documents WHERE document_type IN ('federal_register', 'memorandum')",
    'documents.status': "SELECT DISTINCT status FROM documents WHERE status = 'draft'",
    'tasks.task_type': "SELECT DISTINCT task_type FROM tasks WHERE task_type = 'research'",
    'matter_people.matter_role': "SELECT DISTINCT matter_role FROM matter_people WHERE matter_role IN ('lead', 'point of contact')",
    'matter_organizations.organization_role': "SELECT DISTINCT organization_role FROM matter_organizations WHERE organization_role = 'joint_agency'",
    'common.source': """
        SELECT DISTINCT source FROM (
            SELECT source FROM organizations UNION ALL
            SELECT source FROM people UNION ALL
            SELECT source FROM matters UNION ALL
            SELECT source FROM tasks UNION ALL
            SELECT source FROM meetings UNION ALL
            SELECT source FROM documents UNION ALL
            SELECT source FROM decisions
        ) WHERE source IN ('human', 'test', 'fr_pipeline')
    """,
}


def backup_database(db_path: Path, backup_dir: Path) -> Path:
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
    backup_path = backup_dir / f'tracker-pre-contract-normalization-{stamp}.db'
    source = sqlite3.connect(db_path)
    dest = sqlite3.connect(backup_path)
    source.backup(dest)
    dest.close()
    source.close()
    return backup_path


def main() -> int:
    if not DB_PATH.exists():
        raise SystemExit(f'Tracker DB not found: {DB_PATH}')

    backup_path = backup_database(DB_PATH, BACKUP_DIR)
    print(f'Backup created: {backup_path}')

    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute('BEGIN IMMEDIATE')
        for label, sql in UPDATES:
            before = conn.total_changes
            conn.execute(sql)
            changed = conn.total_changes - before
            print(f'{label}: {changed} row(s) updated')
        conn.commit()

        print('\nVerification:')
        failures = 0
        for label, sql in VERIFY_QUERIES.items():
            remaining = [row[0] for row in conn.execute(sql).fetchall()]
            if remaining:
                failures += 1
                print(f'  FAIL {label}: remaining values = {remaining}')
            else:
                print(f'  OK   {label}')
        return 1 if failures else 0
    finally:
        conn.close()


if __name__ == '__main__':
    raise SystemExit(main())
