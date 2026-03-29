"""Capture alert evaluator — background task that monitors capture health.

Checks every 30s:
- prolonged_offline: no heartbeat for >5 minutes
- error_state: Pi reporting error
- high_disk: disk usage >90%
- high_cpu_temp: CPU temperature >75C
- prolonged_silence: silence_seconds > silence_timeout while recording

Opens alerts when conditions are met, auto-resolves when cleared.
"""
import logging
from datetime import datetime, timezone

log = logging.getLogger(__name__)

# Alert type definitions: (alert_type, severity, check_fn_name)
ALERT_DEFS = [
    ("prolonged_offline", "critical", "Capture offline for >5 minutes"),
    ("error_state", "critical", "Capture reporting error"),
    ("high_disk", "warning", "Pi disk usage >90%"),
    ("high_cpu_temp", "warning", "Pi CPU temperature >75\u00b0C"),
    ("prolonged_silence", "warning", "Prolonged silence while recording"),
]

# Thresholds
OFFLINE_ALERT_S = 300  # 5 minutes
DISK_ALERT_PCT = 90
CPU_TEMP_ALERT_C = 75
SILENCE_ALERT_S = 30


def evaluate_alerts(db, last_status, last_heartbeat_received_at):
    """Evaluate all alert conditions. Opens/resolves alerts as needed.

    Returns list of newly opened or resolved alert dicts for broadcasting.
    """
    now = datetime.now(timezone.utc)
    changes = []

    # Get current open alerts
    open_alerts = {}
    rows = db.execute(
        "SELECT id, alert_type FROM capture_alerts WHERE resolved_at IS NULL"
    ).fetchall()
    for row in rows:
        open_alerts[row["alert_type"]] = row["id"]

    # Evaluate each condition
    conditions = _check_conditions(last_status, last_heartbeat_received_at, now)

    for alert_type, severity, default_msg in ALERT_DEFS:
        condition = conditions.get(alert_type)
        is_active = condition is not None
        is_open = alert_type in open_alerts

        if is_active and not is_open:
            # Open new alert
            msg = condition.get("message", default_msg)
            detail = condition.get("detail")
            db.execute(
                """INSERT INTO capture_alerts
                   (alert_type, severity, message, detail, opened_at, last_evaluated_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (alert_type, severity, msg, detail, now.isoformat(), now.isoformat()),
            )
            db.commit()
            log.warning("Alert OPENED: %s — %s", alert_type, msg)
            changes.append({
                "type": "alert_opened",
                "alert_type": alert_type,
                "severity": severity,
                "message": msg,
                "detail": detail,
                "opened_at": now.isoformat(),
            })

        elif not is_active and is_open:
            # Resolve alert
            db.execute(
                """UPDATE capture_alerts
                   SET resolved_at = ?, resolved_reason = ?, last_evaluated_at = ?
                   WHERE id = ?""",
                (now.isoformat(), "condition_cleared", now.isoformat(), open_alerts[alert_type]),
            )
            db.commit()
            log.info("Alert RESOLVED: %s", alert_type)
            changes.append({
                "type": "alert_resolved",
                "alert_type": alert_type,
                "resolved_at": now.isoformat(),
            })

        elif is_active and is_open:
            # Update evaluation timestamp
            db.execute(
                "UPDATE capture_alerts SET last_evaluated_at = ? WHERE id = ?",
                (now.isoformat(), open_alerts[alert_type]),
            )
            db.commit()

    return changes


def _check_conditions(last_status, last_heartbeat_received_at, now):
    """Return dict of active alert conditions. Key = alert_type, value = details."""
    active = {}

    # 1. Prolonged offline
    if last_heartbeat_received_at:
        age_s = (now - last_heartbeat_received_at).total_seconds()
        if age_s > OFFLINE_ALERT_S:
            active["prolonged_offline"] = {
                "message": f"No heartbeat for {int(age_s)}s (>{OFFLINE_ALERT_S}s threshold)",
                "detail": f"last_heartbeat_age_s={int(age_s)}",
            }
    elif last_status is None:
        # Never received a heartbeat — don't alert on startup
        pass

    # 2. Error state
    if last_status and last_status.get("state") == "error":
        active["error_state"] = {
            "message": "Capture in error state",
            "detail": last_status.get("error_detail", ""),
        }

    # 3. High disk
    disk_pct = last_status.get("disk_used_pct") if last_status else None
    if disk_pct is not None and disk_pct > DISK_ALERT_PCT:
        active["high_disk"] = {
            "message": f"Disk usage at {disk_pct:.0f}% (>{DISK_ALERT_PCT}%)",
            "detail": f"disk_used_pct={disk_pct}",
        }

    # 4. High CPU temp
    cpu_temp = last_status.get("cpu_temp_c") if last_status else None
    if cpu_temp is not None and cpu_temp > CPU_TEMP_ALERT_C:
        active["high_cpu_temp"] = {
            "message": f"CPU temp at {cpu_temp:.0f}\u00b0C (>{CPU_TEMP_ALERT_C}\u00b0C)",
            "detail": f"cpu_temp_c={cpu_temp}",
        }

    # 5. Prolonged silence while recording
    if last_status and last_status.get("state") == "recording":
        silence_s = last_status.get("silence_seconds", 0)
        if silence_s is not None and silence_s > SILENCE_ALERT_S:
            active["prolonged_silence"] = {
                "message": f"Silence for {silence_s}s while recording (>{SILENCE_ALERT_S}s)",
                "detail": f"silence_seconds={silence_s}",
            }

    return active


def get_open_alerts(db):
    """Return list of currently open alerts."""
    rows = db.execute(
        """SELECT id, alert_type, severity, message, detail, opened_at, last_evaluated_at
           FROM capture_alerts
           WHERE resolved_at IS NULL
           ORDER BY opened_at DESC"""
    ).fetchall()
    return [dict(row) for row in rows]


def get_alert_history(db, limit=50):
    """Return recently resolved alerts."""
    rows = db.execute(
        """SELECT id, alert_type, severity, message, detail,
                  opened_at, resolved_at, resolved_reason
           FROM capture_alerts
           ORDER BY COALESCE(resolved_at, opened_at) DESC
           LIMIT ?""",
        (limit,),
    ).fetchall()
    return [dict(row) for row in rows]
