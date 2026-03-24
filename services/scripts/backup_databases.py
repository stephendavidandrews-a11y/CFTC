#!/usr/bin/env python3
"""
CFTC Platform — Database Backup Script

Backs up all SQLite databases with:
  1. WAL checkpoint (flush pending writes)
  2. Integrity quick_check (skip corrupt databases)
  3. shutil.copy2 (preserves metadata)
  4. Size verification (backup matches original)

Retention: 7 daily + 4 weekly (Sunday backups kept 4 weeks).
Schedule: cron/launchd at 02:00 daily.

Usage: python3 backup_databases.py [--backup-dir /path/to/backups]
"""

import argparse
import logging
import os
import shutil
import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [backup] %(levelname)s: %(message)s",
)
logger = logging.getLogger("backup")

# Databases to back up: (label, path)
DATABASES = [
    ("tracker", Path("/Users/stephen/Documents/Website/cftc/services/tracker/data/tracker.db")),
    ("ai", Path("/Users/stephen/Documents/Website/cftc/services/ai/data/ai.db")),
    ("intake", Path("/Users/stephen/Documents/Website/cftc/services/intake/data/cftc_voice.db")),
]

DEFAULT_BACKUP_DIR = Path("/Users/stephen/backups/cftc")
DAILY_RETENTION = 7
WEEKLY_RETENTION = 4  # Sundays kept for 4 weeks


def checkpoint_and_verify(db_path: Path, label: str) -> bool:
    """Checkpoint WAL and run quick_check. Returns True if database is healthy."""
    try:
        conn = sqlite3.connect(str(db_path))
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        result = conn.execute("PRAGMA quick_check").fetchone()[0]
        conn.close()
        if result == "ok":
            logger.info("[%s] Checkpoint + integrity check PASSED", label)
            return True
        else:
            logger.critical("[%s] Integrity check FAILED: %s — SKIPPING BACKUP", label, result)
            return False
    except Exception as e:
        logger.critical("[%s] Checkpoint/integrity error: %s — SKIPPING BACKUP", label, e)
        return False


def backup_database(db_path: Path, label: str, backup_dir: Path) -> Path | None:
    """Copy database file to backup directory with timestamp. Returns backup path or None."""
    now = datetime.now()
    timestamp = now.strftime("%Y-%m-%d_%H%M%S")
    backup_name = "%s_%s.db" % (label, timestamp)
    backup_path = backup_dir / backup_name

    try:
        shutil.copy2(str(db_path), str(backup_path))

        # Verify size matches
        original_size = db_path.stat().st_size
        backup_size = backup_path.stat().st_size
        if original_size != backup_size:
            logger.error("[%s] Size mismatch: original=%d, backup=%d", label, original_size, backup_size)
            backup_path.unlink()
            return None

        logger.info("[%s] Backed up: %s (%d bytes)", label, backup_name, backup_size)
        return backup_path
    except Exception as e:
        logger.error("[%s] Backup failed: %s", label, e)
        return None


def verify_backup(backup_path: Path, label: str) -> bool:
    """Run integrity check on the backup copy itself."""
    try:
        conn = sqlite3.connect(str(backup_path))
        result = conn.execute("PRAGMA quick_check").fetchone()[0]
        row_count = conn.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table'"
        ).fetchone()[0]
        conn.close()
        if result == "ok" and row_count > 0:
            logger.info("[%s] Backup verification PASSED: %d tables, integrity=ok", label, row_count)
            return True
        else:
            logger.error("[%s] Backup verification FAILED: tables=%d, integrity=%s", label, row_count, result)
            return False
    except Exception as e:
        logger.error("[%s] Backup verification error: %s", label, e)
        return False


def apply_retention(backup_dir: Path, label: str):
    """Delete old backups beyond retention policy."""
    now = datetime.now()
    daily_cutoff = now - timedelta(days=DAILY_RETENTION)
    weekly_cutoff = now - timedelta(weeks=WEEKLY_RETENTION)

    pattern = "%s_*.db" % label
    backups = sorted(backup_dir.glob(pattern), reverse=True)

    kept = 0
    deleted = 0
    for bp in backups:
        # Parse timestamp from filename: label_YYYY-MM-DD_HHMMSS.db
        try:
            ts_str = bp.stem.replace(label + "_", "")
            ts = datetime.strptime(ts_str, "%Y-%m-%d_%H%M%S")
        except ValueError:
            continue

        is_sunday = ts.weekday() == 6

        if ts >= daily_cutoff:
            kept += 1  # Within daily retention
        elif is_sunday and ts >= weekly_cutoff:
            kept += 1  # Sunday within weekly retention
        else:
            bp.unlink()
            deleted += 1

    if deleted:
        logger.info("[%s] Retention: kept %d, deleted %d", label, kept, deleted)


def main():
    parser = argparse.ArgumentParser(description="CFTC Database Backup")
    parser.add_argument("--backup-dir", type=Path, default=DEFAULT_BACKUP_DIR)
    args = parser.parse_args()

    backup_dir = args.backup_dir
    backup_dir.mkdir(parents=True, exist_ok=True)
    logger.info("Backup directory: %s", backup_dir)

    total = 0
    passed = 0
    failed = 0

    for label, db_path in DATABASES:
        total += 1
        if not db_path.exists():
            logger.warning("[%s] Database not found: %s — SKIPPING", label, db_path)
            failed += 1
            continue

        if not checkpoint_and_verify(db_path, label):
            failed += 1
            continue

        backup_path = backup_database(db_path, label, backup_dir)
        if not backup_path:
            failed += 1
            continue

        if not verify_backup(backup_path, label):
            failed += 1
            continue

        apply_retention(backup_dir, label)
        passed += 1

    logger.info("Backup complete: %d/%d succeeded, %d failed", passed, total, failed)

    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
