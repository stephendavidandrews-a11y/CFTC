#!/bin/bash
# Daily backup of CFTC tracker and AI databases
BACKUP_DIR="/Users/stephen/Documents/Website/backups/cftc/$(date +%Y%m%d_%H%M%S)"
SRC_DIR="/Users/stephen/Documents/Website/cftc/services"

mkdir -p "$BACKUP_DIR"

# Copy tracker DB
cp "$SRC_DIR/tracker/data/tracker.db" "$BACKUP_DIR/tracker.db" 2>/dev/null
cp "$SRC_DIR/tracker/data/tracker.db-wal" "$BACKUP_DIR/tracker.db-wal" 2>/dev/null
cp "$SRC_DIR/tracker/data/tracker.db-shm" "$BACKUP_DIR/tracker.db-shm" 2>/dev/null

# Copy AI DB
cp "$SRC_DIR/ai/data/ai.db" "$BACKUP_DIR/ai.db" 2>/dev/null
cp "$SRC_DIR/ai/data/ai.db-wal" "$BACKUP_DIR/ai.db-wal" 2>/dev/null
cp "$SRC_DIR/ai/data/ai.db-shm" "$BACKUP_DIR/ai.db-shm" 2>/dev/null

# Keep only last 14 days of backups
find /Users/stephen/Documents/Website/backups/cftc/ -maxdepth 1 -type d -mtime +14 -exec rm -rf {} \;

echo "Backup complete: $BACKUP_DIR"
ls -la "$BACKUP_DIR"
