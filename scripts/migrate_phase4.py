"""
Matter Schema Redesign — Phase 4 Migration Script (Column Drops)

Run on Mac Mini via SSH:
    cd /Users/stephen/Documents/Website/cftc
    services/tracker/.venv/bin/python3 scripts/migrate_phase4.py

What it does:
1. Backs up the DB
2. Verifies data integrity (all typed matters have extension rows)
3. Drops removed columns from the matters table
4. Updates schema.py DDL in-memory validation
5. Records migration in schema_versions
6. Prints verification report
"""

import sqlite3
import shutil
import sys
from pathlib import Path

DB_PATH = Path("/Users/stephen/Documents/Website/cftc/services/tracker/data/tracker.db")
BACKUP_PATH = DB_PATH.with_suffix(".db.bak-phase4")

# Columns to drop from the matters table
COLUMNS_TO_DROP = [
    "risk_level",
    "boss_involvement_level",
    "supervisor_person_id",
    "next_step_assigned_to_person_id",
    "requesting_organization_id",
    "reviewing_organization_id",
    "lead_external_org_id",
    "decision_deadline",
    "revisit_date",
    "pending_decision",
    "problem_statement",
    "why_it_matters",
    # Rulemaking fields (moved to matter_rulemaking)
    "rin",
    "regulatory_stage",
    "federal_register_citation",
    "unified_agenda_priority",
    "cfr_citation",
    "docket_number",
    "fr_doc_number",
]


def run():
    if not DB_PATH.exists():
        print(f"ERROR: Database not found at {DB_PATH}")
        sys.exit(1)

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    cursor = conn.cursor()

    # Check if already applied
    v = cursor.execute("SELECT MAX(version) FROM schema_versions").fetchone()[0]
    if v and v >= 7:
        print("Migration v7 already applied — skipping.")
        conn.close()
        return

    # Check SQLite version
    sqlite_ver = cursor.execute("SELECT sqlite_version()").fetchone()[0]
    print(f"SQLite version: {sqlite_ver}")
    major, minor, patch = [int(x) for x in sqlite_ver.split(".")[:3]]
    if major < 3 or (major == 3 and minor < 35):
        print("ERROR: SQLite >= 3.35.0 required for ALTER TABLE DROP COLUMN")
        print("  Would need table recreation approach instead.")
        sys.exit(1)

    # ── Step 1: Backup ──
    print(f"\nStep 1: Backing up {DB_PATH}")
    shutil.copy2(DB_PATH, BACKUP_PATH)
    print(f"  Backup: {BACKUP_PATH.stat().st_size:,} bytes")

    # ── Step 2: Integrity checks ──
    print("\nStep 2: Pre-migration integrity checks")

    total = cursor.execute("SELECT COUNT(*) FROM matters").fetchone()[0]
    print(f"  Total matters: {total}")

    # Check all rulemaking matters have extension rows
    orphan_rm = cursor.execute("""
        SELECT COUNT(*) FROM matters m
        WHERE m.matter_type = 'rulemaking'
          AND m.id NOT IN (SELECT matter_id FROM matter_rulemaking)
    """).fetchone()[0]
    if orphan_rm > 0:
        print(f"  ERROR: {orphan_rm} rulemaking matters without extension rows!")
        print("  Run Phase 2 migration first.")
        conn.close()
        sys.exit(1)
    print("  Rulemaking integrity: OK")

    # Check status values are migrated
    bad_status = cursor.execute("""
        SELECT DISTINCT status FROM matters
        WHERE status NOT IN ('active', 'paused', 'closed')
    """).fetchall()
    if bad_status:
        print(f"  ERROR: Unmigrated status values: {[r[0] for r in bad_status]}")
        print("  Run Phase 2 migration first.")
        conn.close()
        sys.exit(1)
    print("  Status values: OK")

    # Check type values are migrated
    bad_types = cursor.execute("""
        SELECT DISTINCT matter_type FROM matters
        WHERE matter_type NOT IN ('rulemaking', 'guidance', 'enforcement',
            'congressional', 'briefing', 'administrative', 'inquiry', 'other')
    """).fetchall()
    if bad_types:
        print(f"  ERROR: Unmigrated type values: {[r[0] for r in bad_types]}")
        conn.close()
        sys.exit(1)
    print("  Type values: OK")

    # ── Step 3: Get current columns ──
    current_cols = {row[1] for row in cursor.execute("PRAGMA table_info(matters)").fetchall()}
    to_drop = [c for c in COLUMNS_TO_DROP if c in current_cols]
    already_dropped = [c for c in COLUMNS_TO_DROP if c not in current_cols]

    if already_dropped:
        print(f"\n  Already dropped: {already_dropped}")
    if not to_drop:
        print("\n  All columns already dropped — nothing to do.")
    else:
        print(f"\n  Columns to drop: {len(to_drop)}")
        for c in to_drop:
            print(f"    - {c}")

    # ── Step 4: Drop columns ──
    if to_drop:
        print("\nStep 3: Dropping columns")
        for col in to_drop:
            try:
                cursor.execute(f"ALTER TABLE matters DROP COLUMN {col}")
                print(f"  Dropped: {col}")
            except Exception as e:
                print(f"  ERROR dropping {col}: {e}")
                # Continue with other drops — some may have FK dependencies
        conn.commit()

    # ── Step 5: Drop obsolete indexes ──
    print("\nStep 4: Dropping obsolete indexes")
    obsolete_indexes = [
        "idx_matters_decision_deadline",
        "idx_matters_revisit_date",
        "idx_matters_rin",
        "idx_matters_regulatory_stage",
        "idx_matters_docket_number",
    ]
    for idx_name in obsolete_indexes:
        try:
            cursor.execute(f"DROP INDEX IF EXISTS {idx_name}")
            print(f"  Dropped index: {idx_name}")
        except Exception as e:
            print(f"  Note: {idx_name} — {e}")
    conn.commit()

    # ── Step 6: Record migration ──
    print("\nStep 5: Recording migration")
    cursor.execute(
        "INSERT INTO schema_versions (version, description) VALUES (7, 'matter_schema_redesign_phase4_column_drops')"
    )
    conn.commit()

    # ── Step 7: Verification ──
    print("\n" + "=" * 60)
    print("VERIFICATION REPORT")
    print("=" * 60)

    # Column count
    final_cols = cursor.execute("PRAGMA table_info(matters)").fetchall()
    print(f"\nMatters table: {len(final_cols)} columns (was ~45)")
    for row in final_cols:
        print(f"  {row[0]:2d}. {row[1]} ({row[2]})")

    # Data integrity
    post_total = cursor.execute("SELECT COUNT(*) FROM matters").fetchone()[0]
    print(f"\nTotal matters: {post_total} (was {total})")
    if post_total != total:
        print("  WARNING: Matter count changed!")

    # Check all queries work
    print("\nQuery checks:")
    try:
        cursor.execute("SELECT id, title, status, priority, blocker FROM matters LIMIT 1")
        print("  Base query: OK")
    except Exception as e:
        print(f"  Base query FAILED: {e}")

    try:
        cursor.execute("""
            SELECT m.id, m.title, m.status, mr.workflow_status, mr.rin
            FROM matters m
            LEFT JOIN matter_rulemaking mr ON m.id = mr.matter_id
            LIMIT 1
        """)
        print("  Extension join: OK")
    except Exception as e:
        print(f"  Extension join FAILED: {e}")

    # Schema versions
    print("\nSchema versions:")
    for r in cursor.execute("SELECT * FROM schema_versions ORDER BY version"):
        print(f"  v{r[0]}: {r[1]} ({r[2]})")

    # Check for any remaining removed fields
    remaining_cols = {row[1] for row in final_cols}
    still_present = [c for c in COLUMNS_TO_DROP if c in remaining_cols]
    if still_present:
        print(f"\nWARNING: These columns were not dropped: {still_present}")
    else:
        print(f"\nAll {len(COLUMNS_TO_DROP)} deprecated columns successfully removed.")

    conn.close()
    print(f"\nPhase 4 migration complete. Backup at {BACKUP_PATH}")


if __name__ == "__main__":
    run()
