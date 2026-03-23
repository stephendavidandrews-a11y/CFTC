#!/bin/bash
# CFTC Database Backup Script
# Backs up databases from bind-mounted volumes (no Docker dependency).
# Run daily via crontab: 0 3 * * * /path/to/backup.sh >> /tmp/cftc-backup.log 2>&1

set -euo pipefail

export PATH=/usr/local/bin:/opt/homebrew/bin:$PATH

BACKUP_DIR="$HOME/Documents/Website/backups/cftc"
SRC_DIR="$HOME/Documents/Website/cftc/volumes"
EXT_RETAIN_DAYS=14
LOCAL_RETAIN_DAYS=3
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_PATH="$BACKUP_DIR/$DATE"

echo "[$DATE] Starting CFTC database backup..."
mkdir -p "$BACKUP_PATH"

# Use sqlite3 .backup for safe copy (handles WAL mode)
INTAKE_DB="$HOME/Documents/Website/cftc/services/intake/data/cftc_voice.db"
for db_file in "$SRC_DIR"/tracker/data/tracker.db "$SRC_DIR"/ai/data/ai.db "$INTAKE_DB"; do
    if [ -f "$db_file" ]; then
        name=$(basename "$db_file")
        echo "  Backing up $name..."
        python3 -c "
import sqlite3
src = sqlite3.connect('$db_file')
dst = sqlite3.connect('$BACKUP_PATH/$name')
src.backup(dst)
src.close()
dst.close()
" && echo "  Done: $(du -h "$BACKUP_PATH/$name" | cut -f1)"    || echo "  FAILED: $name"
    fi
done

# Verify
echo ""
echo "Backup verification:"
for f in "$BACKUP_PATH"/*.db; do
    [ -f "$f" ] || continue
    name=$(basename "$f")
    size=$(du -h "$f" | cut -f1)
    tables=$(python3 -c "
import sqlite3
c = sqlite3.connect('$f')
print(len(c.execute('SELECT name FROM sqlite_master WHERE type=\"table\"').fetchall()))
c.close()
" 2>/dev/null || echo "?")
    echo "  $name: $tables tables, $size"
done

# Copy to external storage
EXT_BACKUP_DIR="/Volumes/ZX20/Backups/cftc"
if mountpoint -q /Volumes/ZX20 2>/dev/null || [ -d /Volumes/ZX20 ]; then
    echo ""
    echo "Copying to external storage ($EXT_BACKUP_DIR)..."
    mkdir -p "$EXT_BACKUP_DIR"
    rsync -a "$BACKUP_PATH/" "$EXT_BACKUP_DIR/$DATE/" && EXT_COPY_OK=true || EXT_COPY_OK=false
    if $EXT_COPY_OK; then
        echo "  External copy complete"
        # Rotate external backups (14 days)
        find "$EXT_BACKUP_DIR" -maxdepth 1 -type d -mtime +$EXT_RETAIN_DAYS -exec rm -rf {} \; 2>/dev/null || true
    else
        echo "  WARNING: External copy failed"
    fi
else
    EXT_COPY_OK=false
    echo ""
    echo "WARNING: External drive ZX20 not mounted — skipping external backup"
fi

# Rotate local backups
# Keep 3 days locally if external has a copy, otherwise keep 14 days as fallback
echo ""
if $EXT_COPY_OK; then
    echo "Rotating local backups older than $LOCAL_RETAIN_DAYS days (external has full history)..."
    find "$BACKUP_DIR" -maxdepth 1 -type d -mtime +$LOCAL_RETAIN_DAYS -exec rm -rf {} \; 2>/dev/null || true
else
    echo "Rotating local backups older than $EXT_RETAIN_DAYS days (external unavailable — keeping full history locally)..."
    find "$BACKUP_DIR" -maxdepth 1 -type d -mtime +$EXT_RETAIN_DAYS -exec rm -rf {} \; 2>/dev/null || true
fi
remaining=$(ls -d "$BACKUP_DIR"/*/ 2>/dev/null | wc -l)
echo "  $remaining backup(s) retained"

echo ""
echo "[$DATE] Backup complete: $BACKUP_PATH"
