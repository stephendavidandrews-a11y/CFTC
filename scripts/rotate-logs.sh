#!/bin/bash
# Rotate CFTC service logs — runs via cron at 3:05 AM daily
# Keeps 3 compressed archives, rotates when file exceeds threshold

rotate_log() {
    local f="$1"
    local max_bytes=${2:-10485760}
    if [ ! -f "$f" ]; then return; fi
    local size=$(stat -f%z "$f" 2>/dev/null || echo 0)
    if [ "$size" -gt "$max_bytes" ]; then
        [ -f "${f}.2.bz2" ] && rm -f "${f}.2.bz2"
        [ -f "${f}.1.bz2" ] && mv "${f}.1.bz2" "${f}.2.bz2"
        [ -f "${f}.0" ] && bzip2 -f "${f}.0"
        mv "$f" "${f}.0"
        touch "$f"
        echo "$(date): Rotated $f ($size bytes)"
    fi
}

rotate_log /tmp/cftc-caddy.log 10485760
rotate_log /tmp/cftc-ai.log 10485760
rotate_log /tmp/cftc-tracker.log 5242880
rotate_log /tmp/cftctools-backend.log 5242880
rotate_log /tmp/sauron.log 5242880
