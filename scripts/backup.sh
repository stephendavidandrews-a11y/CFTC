#!/bin/bash
# CFTC Database Backup Script
# Run daily via crontab: 0 3 * * * /path/to/backup.sh >> /var/log/cftc-backup.log 2>&1

set -euo pipefail

CFTC_DIR="$HOME/Documents/Website/cftc"
BACKUP_DIR="$HOME/Documents/Website/backups/cftc"
RETAIN_DAYS=7
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_PATH="$BACKUP_DIR/$DATE"

echo "[$DATE] Starting CFTC database backup..."

# Create backup directory
mkdir -p "$BACKUP_PATH"

# SQLite databases to back up
DATABASES=(
    "$CFTC_DIR/data/cftc_regulatory.db"
    "$CFTC_DIR/data/eo_tracker.db"
    "$CFTC_DIR/services/pipeline/data/pipeline.db"
    "$CFTC_DIR/services/tracker/data/tracker.db"
    "$CFTC_DIR/services/work/data/work.db"
)

# Back up each database using sqlite3 .backup (safe even if DB is in use)
for db in "${DATABASES[@]}"; do
    if [ -f "$db" ]; then
        name=$(basename "$db")
        echo "  Backing up $name..."
        sqlite3 "$db" ".backup '$BACKUP_PATH/$name'" 2>/dev/null || {
            # Fallback to copy if sqlite3 backup fails
            echo "  sqlite3 backup failed for $name, using cp..."
            cp "$db" "$BACKUP_PATH/$name"
        }
        echo "  Done: $(du -h "$BACKUP_PATH/$name" | cut -f1)"
    else
        echo "  SKIP: $db (not found)"
    fi
done

# Verify backups
echo ""
echo "Backup verification:"
for f in "$BACKUP_PATH"/*.db; do
    if [ -f "$f" ]; then
        name=$(basename "$f")
        tables=$(sqlite3 "$f" ".tables" 2>/dev/null | wc -w || echo "0")
        echo "  $name: $tables tables, $(du -h "$f" | cut -f1)"
    fi
done

# Rotate old backups (keep last N days)
echo ""
echo "Rotating backups older than $RETAIN_DAYS days..."
find "$BACKUP_DIR" -maxdepth 1 -type d -mtime +$RETAIN_DAYS -exec rm -rf {} \; 2>/dev/null || true
remaining=$(ls -d "$BACKUP_DIR"/*/ 2>/dev/null | wc -l)
echo "  $remaining backup(s) retained"

echo ""
echo "[$DATE] Backup complete: $BACKUP_PATH"
