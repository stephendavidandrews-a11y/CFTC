"""
Matter Schema Redesign — Phase 2 Migration Script

Run on Mac Mini via SSH:
    cd /Users/stephen/Documents/Website/cftc
    .venv/bin/python3 scripts/migrate_phase2.py

What it does:
1. Backs up the DB
2. Backfills matter_rulemaking from base table rulemaking fields
3. Backfills matter_regulatory_ids from base table identifiers
4. Migrates matter_type (18 → 8)
5. Migrates matter_status (12 → 3) + populates extension workflow_status
6. Records migration in schema_versions
7. Prints verification report
"""

import sqlite3
import uuid
import shutil
import sys
from pathlib import Path
from datetime import datetime

DB_PATH = Path("/Users/stephen/Documents/Website/cftc/services/tracker/data/tracker.db")
BACKUP_PATH = DB_PATH.with_suffix(".db.bak-phase2")


def uid():
    return str(uuid.uuid4())


def run():
    if not DB_PATH.exists():
        print(f"ERROR: Database not found at {DB_PATH}")
        sys.exit(1)

    # ── Step 1: Backup ──
    print(f"Step 1: Backing up {DB_PATH} → {BACKUP_PATH}")
    shutil.copy2(DB_PATH, BACKUP_PATH)
    print(f"  Backup: {BACKUP_PATH.stat().st_size:,} bytes")

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    cursor = conn.cursor()

    # Check schema_versions — skip if already applied
    v = cursor.execute("SELECT MAX(version) FROM schema_versions").fetchone()[0]
    if v and v >= 6:
        print("Migration v6 already applied — skipping.")
        conn.close()
        return

    # Verify Phase 1 tables exist
    tables = {r[0] for r in cursor.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    required = {"matter_rulemaking", "matter_guidance", "matter_enforcement", "matter_regulatory_ids"}
    missing = required - tables
    if missing:
        print(f"ERROR: Phase 1 tables missing: {missing}")
        sys.exit(1)

    print(f"  Pre-migration: {cursor.execute('SELECT COUNT(*) FROM matters').fetchone()[0]} matters")

    # ── Step 2: Backfill matter_rulemaking ──
    print("\nStep 2: Backfill matter_rulemaking")
    rulemaking_matters = cursor.execute("""
        SELECT id, rin, regulatory_stage, federal_register_citation,
               unified_agenda_priority, cfr_citation, docket_number, fr_doc_number
        FROM matters
        WHERE matter_type = 'rulemaking'
          AND id NOT IN (SELECT matter_id FROM matter_rulemaking)
    """).fetchall()

    rm_count = 0
    for m in rulemaking_matters:
        # Map old regulatory_stage to workflow_status
        stage = m["regulatory_stage"]
        wf_map = {
            "concept": "concept",
            "drafting": "drafting",
            "proposed": "drafting",
            "comment_period": "comment_analysis",
            "final_review": "final_drafting",
            "published": "published",
            "effective": "effective",
            "withdrawn": "concept",  # withdrawn rules — mark as concept for review
            "long_term": "concept",
            "petition_received": "concept",
            "interpretive_release": "published",
        }
        workflow_status = wf_map.get(stage, "concept") if stage else "concept"

        cursor.execute("""
            INSERT OR IGNORE INTO matter_rulemaking
            (matter_id, rin, regulatory_stage, workflow_status,
             federal_register_citation, unified_agenda_priority,
             cfr_citation, docket_number, fr_doc_number)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            m["id"], m["rin"], stage, workflow_status,
            m["federal_register_citation"], m["unified_agenda_priority"],
            m["cfr_citation"], m["docket_number"], m["fr_doc_number"],
        ))
        rm_count += 1

    conn.commit()
    print(f"  Created {rm_count} matter_rulemaking rows")

    # ── Step 3: Backfill matter_regulatory_ids ──
    print("\nStep 3: Backfill matter_regulatory_ids")
    id_count = 0

    # RINs
    rows = cursor.execute(
        "SELECT id, rin FROM matters WHERE rin IS NOT NULL AND rin != ''"
    ).fetchall()
    for r in rows:
        cursor.execute(
            "INSERT OR IGNORE INTO matter_regulatory_ids (id, matter_id, id_type, id_value, relationship) VALUES (?, ?, 'rin', ?, 'primary')",
            (uid(), r["id"], r["rin"]),
        )
        id_count += 1

    # Docket numbers
    rows = cursor.execute(
        "SELECT id, docket_number FROM matters WHERE docket_number IS NOT NULL AND docket_number != ''"
    ).fetchall()
    for r in rows:
        cursor.execute(
            "INSERT OR IGNORE INTO matter_regulatory_ids (id, matter_id, id_type, id_value, relationship) VALUES (?, ?, 'docket_number', ?, 'primary')",
            (uid(), r["id"], r["docket_number"]),
        )
        id_count += 1

    # FR citations
    rows = cursor.execute(
        "SELECT id, federal_register_citation FROM matters WHERE federal_register_citation IS NOT NULL AND federal_register_citation != ''"
    ).fetchall()
    for r in rows:
        cursor.execute(
            "INSERT OR IGNORE INTO matter_regulatory_ids (id, matter_id, id_type, id_value, relationship) VALUES (?, ?, 'fr_citation', ?, 'primary')",
            (uid(), r["id"], r["federal_register_citation"]),
        )
        id_count += 1

    # CFR citations (may contain multiple parts like "17 CFR Part 23; 17 CFR Part 37")
    rows = cursor.execute(
        "SELECT id, cfr_citation FROM matters WHERE cfr_citation IS NOT NULL AND cfr_citation != ''"
    ).fetchall()
    for r in rows:
        # Store the full citation as one entry
        cursor.execute(
            "INSERT OR IGNORE INTO matter_regulatory_ids (id, matter_id, id_type, id_value, relationship) VALUES (?, ?, 'cfr_part', ?, 'primary')",
            (uid(), r["id"], r["cfr_citation"]),
        )
        id_count += 1

    conn.commit()
    print(f"  Created {id_count} matter_regulatory_ids rows")

    # ── Step 4: Migrate matter_type (18 → 8) ──
    print("\nStep 4: Migrate matter_type")

    type_mappings = [
        # (new_type, [old_types])
        ("guidance", [
            "interpretive guidance", "no-action letter", "exemptive letter",
            "staff advisory", "other letter",
        ]),
        ("enforcement", ["enforcement support", "litigation-sensitive issue"]),
        ("congressional", ["congressional response"]),
        ("briefing", ["speech / testimony / briefing prep"]),
        ("administrative", ["personnel / management", "administrative / ethics / process"]),
        ("inquiry", ["industry inquiry", "international matter"]),
        # rulemaking stays as-is
        # "regulatory review" and "prospective policy" → rulemaking (with review_trigger)
        ("rulemaking", ["regulatory review", "prospective policy"]),
        # "policy development" (test data) → "other"
        ("other", ["policy development"]),
        # "invalid_type" (test data) → "other"
        ("other", ["invalid_type"]),
        # "interagency coordination" → "rulemaking" (it's a dimension, not a type)
        ("rulemaking", ["interagency coordination"]),
    ]

    for new_type, old_types in type_mappings:
        placeholders = ",".join(["?"] * len(old_types))
        result = cursor.execute(
            f"UPDATE matters SET matter_type = ? WHERE matter_type IN ({placeholders})",
            [new_type] + old_types,
        )
        if result.rowcount > 0:
            print(f"  {old_types} → '{new_type}': {result.rowcount} rows")

    conn.commit()

    # ── Step 5: Migrate matter_status (12 → 3) ──
    print("\nStep 5: Migrate matter_status")

    # First, map the old workflow-specific status to the appropriate extension workflow_status
    # For rulemaking matters that have extension rows
    status_to_rm_workflow = {
        "new intake": "concept",
        "framing issue": "concept",
        "research in progress": "drafting",
        "draft in progress": "drafting",
        "internal review": "internal_review",
        "client review": "client_review",
        "leadership review": "chairman_review",
        "external coordination": "commission_review",
        "awaiting decision": "commission_review",
        "awaiting comments": "comment_analysis",
    }

    for old_status, wf_status in status_to_rm_workflow.items():
        # Update extension workflow_status for rulemaking matters with this old base status
        cursor.execute("""
            UPDATE matter_rulemaking SET workflow_status = ?
            WHERE matter_id IN (
                SELECT id FROM matters WHERE status = ? AND matter_type = 'rulemaking'
            )
            AND workflow_status = 'concept'
        """, (wf_status, old_status))

    conn.commit()

    # Now simplify base status
    active_statuses = [
        "new intake", "framing issue", "research in progress", "draft in progress",
        "internal review", "client review", "leadership review",
        "external coordination", "awaiting decision", "awaiting comments",
    ]
    placeholders = ",".join(["?"] * len(active_statuses))
    result = cursor.execute(
        f"UPDATE matters SET status = 'active' WHERE status IN ({placeholders})",
        active_statuses,
    )
    print(f"  Active: {result.rowcount} rows (from {len(active_statuses)} old statuses)")

    result = cursor.execute(
        "UPDATE matters SET status = 'paused' WHERE status = 'parked / monitoring'"
    )
    print(f"  Paused: {result.rowcount} rows")

    # 'closed' stays 'closed'
    closed_count = cursor.execute("SELECT COUNT(*) FROM matters WHERE status = 'closed'").fetchone()[0]
    print(f"  Closed: {closed_count} rows (unchanged)")

    conn.commit()

    # ── Step 6: Record migration ──
    print("\nStep 6: Record migration")
    cursor.execute(
        "INSERT INTO schema_versions (version, description) VALUES (6, 'matter_schema_redesign_phase2_data_migration')"
    )
    conn.commit()
    print("  Recorded schema version 6")

    # ── Step 7: Verification report ──
    print("\n" + "=" * 60)
    print("VERIFICATION REPORT")
    print("=" * 60)

    total = cursor.execute("SELECT COUNT(*) FROM matters").fetchone()[0]
    print(f"\nTotal matters: {total}")

    print("\nMatter types:")
    for r in cursor.execute("SELECT matter_type, COUNT(*) as c FROM matters GROUP BY matter_type ORDER BY c DESC"):
        print(f"  {r['matter_type']}: {r['c']}")

    print("\nMatter statuses:")
    for r in cursor.execute("SELECT status, COUNT(*) as c FROM matters GROUP BY status ORDER BY c DESC"):
        print(f"  {r['status']}: {r['c']}")

    print("\nExtension tables:")
    for tbl in ["matter_rulemaking", "matter_guidance", "matter_enforcement"]:
        c = cursor.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
        print(f"  {tbl}: {c} rows")

    print(f"\nmatter_regulatory_ids: {cursor.execute('SELECT COUNT(*) FROM matter_regulatory_ids').fetchone()[0]} rows")

    # Integrity check: every rulemaking matter should have an extension row
    orphans = cursor.execute("""
        SELECT m.id, m.title FROM matters m
        WHERE m.matter_type = 'rulemaking'
          AND m.id NOT IN (SELECT matter_id FROM matter_rulemaking)
    """).fetchall()
    if orphans:
        print(f"\nWARNING: {len(orphans)} rulemaking matters without extension rows:")
        for o in orphans:
            print(f"  {o['id'][:8]}... {o['title'][:60]}")
    else:
        print("\nIntegrity: All rulemaking matters have extension rows ✓")

    # Check no unexpected matter_type values
    unexpected = cursor.execute("""
        SELECT DISTINCT matter_type FROM matters
        WHERE matter_type NOT IN ('rulemaking', 'guidance', 'enforcement', 'congressional', 'briefing', 'administrative', 'inquiry', 'other')
    """).fetchall()
    if unexpected:
        print(f"\nWARNING: Unexpected matter_type values: {[r[0] for r in unexpected]}")
    else:
        print("Integrity: All matter_type values are in the 8-type set ✓")

    # Check no unexpected status values
    unexpected_status = cursor.execute("""
        SELECT DISTINCT status FROM matters
        WHERE status NOT IN ('active', 'paused', 'closed')
    """).fetchall()
    if unexpected_status:
        print(f"\nWARNING: Unexpected status values: {[r[0] for r in unexpected_status]}")
    else:
        print("Integrity: All status values are in {active, paused, closed} ✓")

    print("\nSchema versions:")
    for r in cursor.execute("SELECT * FROM schema_versions ORDER BY version"):
        print(f"  v{r['version']}: {r['description']} ({r['applied_at']})")

    conn.close()
    print(f"\nPhase 2 migration complete. Backup at {BACKUP_PATH}")


if __name__ == "__main__":
    run()
