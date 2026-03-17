#!/bin/bash
# CFTC Database Backup Script
# Backs up LIVE databases from Docker volumes via python3 (no sqlite3 CLI in containers).
# Run daily via crontab: 0 3 * * * /path/to/backup.sh >> /tmp/cftc-backup.log 2>&1

set -euo pipefail

export PATH=/opt/homebrew/bin:$PATH

BACKUP_DIR="$HOME/Documents/Website/backups/cftc"
RETAIN_DAYS=7
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_PATH="$BACKUP_DIR/$DATE"

echo "[$DATE] Starting CFTC database backup..."
mkdir -p "$BACKUP_PATH"

backup_from_container() {
    local container=$1 db_path=$2 name=$3
    echo "  Backing up $name from $container..."
    docker exec "$container" python3 -c "
import sqlite3, shutil
src = sqlite3.connect('"$db_path"')
dst = sqlite3.connect('/tmp/backup.db')
src.backup(dst)
src.close()
dst.close()
" && docker cp "$container:/tmp/backup.db" "$BACKUP_PATH/$name" \
   && docker exec "$container" rm -f /tmp/backup.db \
   && echo "  Done: $(du -h "$BACKUP_PATH/$name" | cut -f1)" \
   || echo "  FAILED: $name"
}

# Tracker database (only remaining service)
backup_from_container cftc-tracker /app/data/tracker.db tracker.db

# Verify
echo ""
echo "Backup verification:"
for f in "$BACKUP_PATH"/*.db; do
    [ -f "$f" ] || continue
    name=$(basename "$f")
    size=$(du -h "$f" | cut -f1)
    tables=$(python3 -c "
import sqlite3
c = sqlite3.connect('"$f"')
print(len(c.execute('SELECT name FROM sqlite_master WHERE type=\"table\"').fetchall()))
c.close()
" 2>/dev/null || echo "?")
    echo "  $name: $tables tables, $size"
done

# Rotate
echo ""
echo "Rotating backups older than $RETAIN_DAYS days..."
find "$BACKUP_DIR" -maxdepth 1 -type d -mtime +$RETAIN_DAYS -exec rm -rf {} \; 2>/dev/null || true
remaining=$(ls -d "$BACKUP_DIR"/*/ 2>/dev/null | wc -l)
echo "  $remaining backup(s) retained"

echo ""
echo "[$DATE] Backup complete: $BACKUP_PATH"
