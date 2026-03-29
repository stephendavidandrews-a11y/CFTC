"""Nightly rollup and prune for capture_status table.

Runs at 2:00 AM. Order matters: rollup yesterday FIRST, then prune >24h.
Uses actual reported_at deltas (not fixed 15s buckets), capped at 300s.
"""
import logging
from datetime import datetime, timedelta, timezone

log = logging.getLogger(__name__)

DELTA_CAP_S = 300  # 5-minute cap on any single delta
OFFLINE_THRESHOLD_S = 60


def rollup_and_prune(db) -> dict:
    """Aggregate yesterday's data into capture_status_daily, then prune."""
    yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
    report = {"date": yesterday, "rolled_up": False, "pruned": 0}

    rows = db.execute(
        """SELECT reported_at, recording_state, segment_open,
                  segment_duration_seconds, wifi_rssi, cpu_temp_c,
                  disk_used_pct, last_rsync_at
        FROM capture_status
        WHERE date(reported_at) = ?
        ORDER BY reported_at ASC""",
        (yesterday,),
    ).fetchall()

    if rows:
        recording_s = 0.0
        idle_s = 0.0
        error_s = 0.0
        offline_s = 0.0
        segment_count = 0
        segment_durations = []
        rssi_values = []
        temp_values = []
        disk_values = []
        rsync_count = 0
        seen_rsync = set()

        for i in range(len(rows) - 1):
            prev = rows[i]
            curr = rows[i + 1]
            try:
                prev_dt = datetime.fromisoformat(prev["reported_at"])
                curr_dt = datetime.fromisoformat(curr["reported_at"])
            except (ValueError, TypeError):
                continue
            delta = (curr_dt - prev_dt).total_seconds()

            if delta > DELTA_CAP_S:
                attr_s = OFFLINE_THRESHOLD_S
                overflow = delta - attr_s
            else:
                attr_s = delta
                overflow = 0

            state = prev["recording_state"]
            if state == "recording":
                recording_s += attr_s
            elif state == "idle":
                idle_s += attr_s
            elif state == "error":
                error_s += attr_s
            offline_s += overflow

            if prev["segment_open"] == 1 and curr["segment_open"] == 0:
                segment_count += 1
                if prev["segment_duration_seconds"]:
                    segment_durations.append(prev["segment_duration_seconds"])

            if prev["wifi_rssi"] is not None:
                rssi_values.append(prev["wifi_rssi"])
            if prev["cpu_temp_c"] is not None:
                temp_values.append(prev["cpu_temp_c"])
            if prev["disk_used_pct"] is not None:
                disk_values.append(prev["disk_used_pct"])
            if prev["last_rsync_at"] and prev["last_rsync_at"] not in seen_rsync:
                seen_rsync.add(prev["last_rsync_at"])
                rsync_count += 1

        db.execute(
            """INSERT OR REPLACE INTO capture_status_daily (
                date, recording_minutes, idle_minutes, offline_minutes,
                error_minutes, segment_count, avg_segment_duration_s,
                avg_wifi_rssi, min_wifi_rssi, avg_cpu_temp_c,
                max_cpu_temp_c, max_disk_used_pct, rsync_count
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                yesterday,
                int(recording_s / 60),
                int(idle_s / 60),
                int(offline_s / 60),
                int(error_s / 60),
                segment_count,
                (sum(segment_durations) / len(segment_durations))
                if segment_durations else None,
                (sum(rssi_values) / len(rssi_values)) if rssi_values else None,
                min(rssi_values) if rssi_values else None,
                (sum(temp_values) / len(temp_values)) if temp_values else None,
                max(temp_values) if temp_values else None,
                max(disk_values) if disk_values else None,
                rsync_count,
            ),
        )
        db.commit()
        report["rolled_up"] = True
        log.info("Rolled up %d rows for %s", len(rows), yesterday)

    result = db.execute(
        "DELETE FROM capture_status WHERE received_at < datetime('now', '-24 hours')"
    )
    db.commit()
    report["pruned"] = result.rowcount
    log.info("Pruned %d rows older than 24h", result.rowcount)

    return report
