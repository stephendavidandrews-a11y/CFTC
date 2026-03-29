"""Capture monitoring: WebSocket ingest, dashboard broadcast, state normalizer, timeline API."""
import asyncio
import hashlib
import json
import logging
from datetime import datetime, timedelta, timezone

import secrets as _secrets

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from app.config import (
    AUTH_USER,
    AUTH_PASS,
    CAPTURE_INGEST_TOKEN,
    HEARTBEAT_INTERVAL_S,
    OFFLINE_THRESHOLD_S,
    SILENCE_THRESHOLD_DB,
    SILENCE_TIMEOUT_S,
    STALE_WARNING_S,
)
from app.db import get_connection, get_db

import asyncio as _asyncio_mod
import subprocess
import time as _time_mod
from app.config import PI_SSH_HOST, PI_SSH_USER
from app.jobs.capture_alerts import evaluate_alerts, get_open_alerts, get_alert_history

log = logging.getLogger(__name__)
_security = HTTPBasic()


def _verify_capture_auth(credentials: HTTPBasicCredentials = Depends(_security)):
    correct_user = _secrets.compare_digest(credentials.username.encode(), AUTH_USER.encode())
    correct_pass = _secrets.compare_digest(credentials.password.encode(), AUTH_PASS.encode())
    if not (correct_user and correct_pass):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username
router = APIRouter(tags=["capture"])

# --- In-memory state ---
_dashboard_clients: set[WebSocket] = set()
_last_status: dict | None = None
_last_heartbeat_received_at: datetime | None = None
_last_session_id: str | None = None
_last_seq: int = 0
_last_reported_at: str | None = None


# --- State normalizer ---

def normalize_status(heartbeat: dict) -> str:
    """Return canonical state: 'recording', 'idle', or 'error'.

    'offline' is never returned here — set by the staleness timer.
    Precedence: error > recording > idle.
    """
    if heartbeat.get("error_detail"):
        return "error"
    if heartbeat.get("capture_service") != "active":
        return "error"
    if heartbeat.get("segment_open"):
        return "recording"
    return "idle"


def _build_broadcast(
    heartbeat: dict,
    state: str,
    received_at: datetime,
    prev_reported_at: str | None,
) -> dict:
    """Build normalized status_update for dashboard clients."""
    reported_at = heartbeat.get("reported_at", "")
    reported_dt = None
    try:
        reported_dt = datetime.fromisoformat(reported_at)
        transport_delay_ms = int(
            (received_at - reported_dt).total_seconds() * 1000
        )
    except (ValueError, TypeError):
        transport_delay_ms = 0

    heartbeat_gap_s = 0.0
    if reported_dt and prev_reported_at:
        try:
            prev_reported = datetime.fromisoformat(prev_reported_at)
            heartbeat_gap_s = round(
                (reported_dt - prev_reported).total_seconds(), 1
            )
        except (ValueError, TypeError):
            pass

    buffered_replay = transport_delay_ms > HEARTBEAT_INTERVAL_S * 2 * 1000

    return {
        "type": "status_update",
        "state": state,
        "session_id": heartbeat.get("session_id"),
        "seq": heartbeat.get("seq"),
        "reported_at": reported_at,
        "received_at": received_at.isoformat(),
        "segment_open": heartbeat.get("segment_open"),
        "silence_seconds": heartbeat.get("silence_seconds"),
        "last_speech_at": heartbeat.get("last_speech_at"),
        "segment_started_at": heartbeat.get("segment_started_at"),
        "segment_duration_seconds": heartbeat.get("segment_duration_seconds"),
        "last_segment_close_reason": heartbeat.get("last_segment_close_reason"),
        "audio_level_db": heartbeat.get("audio_level_db"),
        "audio_level_peak_db": heartbeat.get("audio_level_peak_db"),
        "wifi_rssi": heartbeat.get("wifi_rssi"),
        "wifi_ssid": heartbeat.get("wifi_ssid"),
        "cpu_temp_c": heartbeat.get("cpu_temp_c"),
        "disk_used_pct": heartbeat.get("disk_used_pct"),
        "memory_used_pct": heartbeat.get("memory_used_pct"),
        "uptime_seconds": heartbeat.get("uptime_seconds"),
        "capture_service": heartbeat.get("capture_service"),
        "last_rsync_at": heartbeat.get("last_rsync_at"),
        "transport_delay_ms": transport_delay_ms,
        "heartbeat_gap_s": heartbeat_gap_s,
        "buffered_replay": buffered_replay,
    }


async def _broadcast(message: dict) -> None:
    """Send a message to all connected dashboard clients."""
    payload = json.dumps(message)
    dead: list[WebSocket] = []
    for ws in _dashboard_clients:
        try:
            await asyncio.wait_for(ws.send_text(payload), timeout=5.0)
        except (WebSocketDisconnect, asyncio.TimeoutError, RuntimeError):
            dead.append(ws)
    for ws in dead:
        _dashboard_clients.discard(ws)


def _store_heartbeat(db, heartbeat: dict, state: str, received_at: datetime):
    """Insert heartbeat into capture_status. Duplicates ignored by UNIQUE."""
    try:
        db.execute(
            """INSERT OR IGNORE INTO capture_status (
                session_id, seq, reported_at, received_at, recording_state,
                segment_open, silence_seconds, segment_started_at,
                segment_duration_seconds, last_speech_at,
                last_segment_close_reason, error_detail,
                audio_level_db, audio_level_peak_db,
                wifi_rssi, wifi_ssid, cpu_temp_c, disk_used_pct,
                memory_used_pct, uptime_seconds, capture_service,
                last_rsync_at, raw_payload
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                heartbeat.get("session_id"),
                heartbeat.get("seq"),
                heartbeat.get("reported_at"),
                received_at.isoformat(),
                state,
                int(heartbeat.get("segment_open", False)),
                heartbeat.get("silence_seconds", 0),
                heartbeat.get("segment_started_at"),
                heartbeat.get("segment_duration_seconds"),
                heartbeat.get("last_speech_at"),
                heartbeat.get("last_segment_close_reason"),
                heartbeat.get("error_detail"),
                heartbeat.get("audio_level_db"),
                heartbeat.get("audio_level_peak_db"),
                heartbeat.get("wifi_rssi"),
                heartbeat.get("wifi_ssid"),
                heartbeat.get("cpu_temp_c"),
                heartbeat.get("disk_used_pct"),
                heartbeat.get("memory_used_pct"),
                heartbeat.get("uptime_seconds"),
                heartbeat.get("capture_service"),
                heartbeat.get("last_rsync_at"),
                json.dumps(heartbeat),
            ),
        )
        db.commit()
    except Exception:
        log.exception("Failed to store heartbeat")


# --- WebSocket: Pi ingest (Bearer token auth) ---

@router.websocket("/ws/capture-ingest")
async def capture_ingest(ws: WebSocket):
    """Accept heartbeats from the Pi's respeaker-heartbeat daemon."""
    await ws.accept()

    auth = ws.headers.get("authorization", "")
    if auth != f"Bearer {CAPTURE_INGEST_TOKEN}" or not CAPTURE_INGEST_TOKEN:
        await ws.close(code=1008, reason="Unauthorized")
        return
    log.info("Pi heartbeat connected from %s", ws.client.host if ws.client else "unknown")

    global _last_status, _last_heartbeat_received_at, _last_session_id, _last_seq, _last_reported_at
    db = get_connection()

    try:
        while True:
            raw = await ws.receive_text()
            data = json.loads(raw)
            msg_type = data.get("type")
            received_at = datetime.now(timezone.utc)

            if msg_type == "heartbeat":
                session_id = data.get("session_id", "")
                seq = data.get("seq", 0)

                if _last_session_id and session_id != _last_session_id:
                    log.info(
                        "Daemon restarted: session %s -> %s",
                        _last_session_id, session_id,
                    )

                if session_id == _last_session_id and seq == _last_seq:
                    log.debug("Duplicate (session=%s, seq=%d), dropping", session_id, seq)
                    continue

                if (
                    session_id == _last_session_id
                    and _last_seq > 0
                    and seq > _last_seq + 1
                ):
                    log.warning(
                        "Gap: expected seq=%d, got seq=%d (missed %d)",
                        _last_seq + 1, seq, seq - _last_seq - 1,
                    )

                if (
                    session_id == _last_session_id
                    and _last_seq > 0
                    and seq < _last_seq
                ):
                    log.warning("Out-of-order: seq=%d after seq=%d", seq, _last_seq)

                _last_session_id = session_id
                _last_seq = seq

                state = normalize_status(data)
                _store_heartbeat(db, data, state, received_at)
                prev_reported_at = _last_reported_at
                _last_reported_at = data.get("reported_at")
                broadcast = _build_broadcast(data, state, received_at, prev_reported_at)
                _last_status = broadcast
                _last_heartbeat_received_at = received_at
                await _broadcast(broadcast)

            elif msg_type == "reconnected":
                log.info(
                    "Pi reconnected: gap=%ds, buffered=%d, session=%s",
                    data.get("gap_seconds", 0),
                    data.get("buffered_count", 0),
                    data.get("session_id", ""),
                )

    except (WebSocketDisconnect, RuntimeError):
        log.info("Pi heartbeat disconnected")
    finally:
        db.close()


# --- WebSocket: Dashboard (read-only, hash-based auth) ---

@router.websocket("/ws/capture-status")
async def capture_status_stream(ws: WebSocket):
    """Stream normalized capture status to dashboard clients."""
    await ws.accept()

    token = ws.query_params.get("token", "")
    expected_token = hashlib.sha256(f"{AUTH_USER}:{AUTH_PASS}".encode()).hexdigest()
    if not token or token != expected_token:
        await ws.close(code=1008, reason="Unauthorized")
        return

    _dashboard_clients.add(ws)
    log.info("Dashboard client connected (total=%d)", len(_dashboard_clients))

    try:
        welcome = {
            "type": "welcome",
            "thresholds": {
                "HEARTBEAT_INTERVAL_S": HEARTBEAT_INTERVAL_S,
                "STALE_WARNING_S": STALE_WARNING_S,
                "OFFLINE_THRESHOLD_S": OFFLINE_THRESHOLD_S,
                "SILENCE_TIMEOUT_S": SILENCE_TIMEOUT_S,
                "SILENCE_THRESHOLD_DB": SILENCE_THRESHOLD_DB,
            },
            "last_status": _last_status,
        }
        await ws.send_text(json.dumps(welcome))

        while True:
            try:
                await ws.receive_text()
            except WebSocketDisconnect:
                break
    finally:
        _dashboard_clients.discard(ws)
        log.info("Dashboard client disconnected (total=%d)", len(_dashboard_clients))


# --- Staleness timer ---

async def staleness_checker():
    """Background task: broadcast offline state when no heartbeat received."""
    global _last_status
    while True:
        await asyncio.sleep(5)
        if _last_heartbeat_received_at:
            age = (datetime.now(timezone.utc) - _last_heartbeat_received_at).total_seconds()
            if age > OFFLINE_THRESHOLD_S:
                current_state = _last_status.get("state") if _last_status else None
                if current_state != "offline":
                    offline_msg = {
                        **(_last_status or {}),
                        "type": "status_update",
                        "state": "offline",
                        "reported_at": None,
                        "received_at": datetime.now(timezone.utc).isoformat(),
                    }
                    _last_status = offline_msg
                    await _broadcast(offline_msg)
                    log.warning("No heartbeat in %ds — broadcasting offline", int(age))


# --- Timeline API ---

@router.get("/api/capture/ws-token")
async def capture_ws_token(_user=Depends(_verify_capture_auth)):
    """Return the WebSocket auth token for the dashboard capture-status stream.

    Protected by HTTP Basic auth (same as all tracker endpoints).
    The frontend calls this once, then uses the token for the WS connection.
    """
    token = hashlib.sha256(f"{AUTH_USER}:{AUTH_PASS}".encode()).hexdigest()
    return {"token": token}


@router.get("/api/capture/timeline")
async def capture_timeline(hours: int = 24, db=Depends(get_db), _user=Depends(_verify_capture_auth)):
    """Return time-bucketed capture status intervals for the timeline."""
    rows = db.execute(
        """SELECT reported_at, recording_state, segment_open
        FROM capture_status
        WHERE reported_at > datetime('now', ? || ' hours')
        ORDER BY reported_at ASC""",
        (f"-{hours}",),
    ).fetchall()

    if not rows:
        return {"intervals": [], "hours": hours}

    intervals = []
    prev = None

    for row in rows:
        reported_at = row["reported_at"]
        state = row["recording_state"]

        if prev:
            try:
                prev_dt = datetime.fromisoformat(prev["reported_at"])
                curr_dt = datetime.fromisoformat(reported_at)
                gap_s = (curr_dt - prev_dt).total_seconds()
            except (ValueError, TypeError):
                gap_s = 0

            if gap_s > OFFLINE_THRESHOLD_S:
                intervals.append({
                    "from": prev["reported_at"],
                    "to": (prev_dt + timedelta(seconds=OFFLINE_THRESHOLD_S)).isoformat(),
                    "state": prev["state"],
                })
                intervals.append({
                    "from": (prev_dt + timedelta(seconds=OFFLINE_THRESHOLD_S)).isoformat(),
                    "to": reported_at,
                    "state": "offline",
                })
            else:
                intervals.append({
                    "from": prev["reported_at"],
                    "to": reported_at,
                    "state": prev["state"],
                })

        prev = {"reported_at": reported_at, "state": state}

    if prev:
        intervals.append({
            "from": prev["reported_at"],
            "to": datetime.now(timezone.utc).isoformat(),
            "state": prev["state"],
        })

    return {"intervals": intervals, "hours": hours}


# --- Remote Management Actions ---

# Per-action cooldown tracker: action_name -> last_completed_timestamp
_action_cooldowns: dict[str, float] = {}
_ACTION_COOLDOWN_S = 60  # minimum seconds between same action
_SSH_TIMEOUT_S = 10

# Allowed actions and their commands (whitelist — no arbitrary execution)
_ALLOWED_ACTIONS = {
    "restart-heartbeat": {
        "cmd": "sudo systemctl restart respeaker-heartbeat",
        "description": "Restart the heartbeat daemon",
        "verify_cmd": "systemctl is-active respeaker-heartbeat",
    },
    "restart-capture": {
        "cmd": "sudo systemctl restart sauron-capture",
        "description": "Restart the audio capture daemon",
        "verify_cmd": "systemctl is-active sauron-capture",
    },
    "diagnose": {
        "cmd": (
            "echo '=== Services ===' && "
            "systemctl is-active sauron-capture respeaker-heartbeat && "
            "echo '=== Disk ===' && "
            "df -h /home/stephen && "
            "echo '=== Memory ===' && "
            "free -h | head -2 && "
            "echo '=== Uptime ===' && "
            "uptime && "
            "echo '=== Network ===' && "
            "ip route get 100.87.51.75 2>/dev/null | head -1 && "
            "echo '=== Tailscale ===' && "
            "tailscale status --peers=false 2>/dev/null || echo 'tailscale not available' && "
            "echo '=== Recent capture logs ===' && "
            "journalctl -u sauron-capture --no-pager -n 5 2>/dev/null || echo 'no journal' && "
            "echo '=== Recent heartbeat logs ===' && "
            "journalctl -u respeaker-heartbeat --no-pager -n 5 2>/dev/null || echo 'no journal'"
        ),
        "description": "Gather diagnostic information from the Pi",
        "verify_cmd": None,
    },
}


def _check_cooldown(action: str) -> tuple[bool, int]:
    """Check if action is within cooldown. Returns (allowed, seconds_remaining)."""
    last = _action_cooldowns.get(action, 0)
    elapsed = _time_mod.time() - last
    if elapsed < _ACTION_COOLDOWN_S:
        return False, int(_ACTION_COOLDOWN_S - elapsed)
    return True, 0


def _run_ssh_command(cmd: str) -> dict:
    """Execute a command on the Pi via SSH. Returns structured result."""
    ssh_cmd = [
        "ssh",
        "-o", "ConnectTimeout=5",
        "-o", "StrictHostKeyChecking=no",
        "-o", "BatchMode=yes",
        f"{PI_SSH_USER}@{PI_SSH_HOST}",
        cmd,
    ]
    start = _time_mod.time()
    try:
        result = subprocess.run(
            ssh_cmd,
            capture_output=True,
            text=True,
            timeout=_SSH_TIMEOUT_S,
        )
        duration_ms = int((_time_mod.time() - start) * 1000)
        return {
            "success": result.returncode == 0,
            "exit_code": result.returncode,
            "stdout": result.stdout[-2000:] if result.stdout else "",
            "stderr": result.stderr[-500:] if result.stderr else "",
            "duration_ms": duration_ms,
        }
    except subprocess.TimeoutExpired:
        duration_ms = int((_time_mod.time() - start) * 1000)
        return {
            "success": False,
            "exit_code": -1,
            "stdout": "",
            "stderr": f"SSH command timed out after {_SSH_TIMEOUT_S}s",
            "duration_ms": duration_ms,
        }
    except Exception as e:
        duration_ms = int((_time_mod.time() - start) * 1000)
        return {
            "success": False,
            "exit_code": -1,
            "stdout": "",
            "stderr": str(e)[:500],
            "duration_ms": duration_ms,
        }


def _log_action(db, action: str, user: str, status: str, result: dict, duration_ms: int):
    """Record a management action in the audit log."""
    now = datetime.now(timezone.utc).isoformat()
    try:
        db.execute(
            """INSERT INTO capture_actions
               (action, requested_by, requested_at, completed_at, status, result_summary, result_detail, pi_host, duration_ms)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                action,
                user,
                now,
                now,
                status,
                result.get("stderr", "")[:200] if not result.get("success") else "OK",
                json.dumps(result)[:4000],
                PI_SSH_HOST,
                duration_ms,
            ),
        )
        db.commit()
    except Exception:
        log.exception("Failed to log action %s", action)


@router.post("/api/capture/actions/{action_name}")
async def execute_capture_action(
    action_name: str,
    force: bool = False,
    db=Depends(get_db),
    user=Depends(_verify_capture_auth),
):
    """Execute a safe, scoped management action on the Pi.

    Allowed actions: diagnose, restart-heartbeat, restart-capture.
    Rate-limited to one execution per action per 60 seconds.
    For restart-capture: requires force=true if currently recording.
    """
    if action_name not in _ALLOWED_ACTIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown action: {action_name}. Allowed: {list(_ALLOWED_ACTIONS.keys())}",
        )

    action_def = _ALLOWED_ACTIONS[action_name]

    # Safety: block restart-capture while recording unless force=true
    if action_name == "restart-capture":
        current_state = _last_status.get("state") if _last_status else None
        if current_state == "recording" and not force:
            raise HTTPException(
                status_code=409,
                detail="Capture is currently recording. Pass force=true to restart anyway (may lose in-progress segment).",
            )

    # Check cooldown
    allowed, remaining = _check_cooldown(action_name)
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail=f"Action '{action_name}' on cooldown. Retry in {remaining}s.",
            headers={"Retry-After": str(remaining)},
        )

    log.info("User '%s' executing action: %s (force=%s)", user, action_name, force)

    # Run the command
    loop = _asyncio_mod.get_event_loop()
    result = await loop.run_in_executor(None, _run_ssh_command, action_def["cmd"])

    # Verify step (if applicable and main command succeeded)
    verify_result = None
    if result["success"] and action_def.get("verify_cmd"):
        verify_result = await loop.run_in_executor(
            None, _run_ssh_command, action_def["verify_cmd"]
        )
        result["verify_stdout"] = verify_result["stdout"].strip()
        result["verify_success"] = verify_result["success"]

    # Update cooldown
    _action_cooldowns[action_name] = _time_mod.time()

    # Log to DB
    action_status = "success" if result["success"] else "failed"
    _log_action(db, action_name, user, action_status, result, result["duration_ms"])

    return {
        "action": action_name,
        "description": action_def["description"],
        "status": action_status,
        "result": result,
    }


@router.get("/api/capture/actions/log")
async def get_action_log(
    limit: int = 20,
    db=Depends(get_db),
    _user=Depends(_verify_capture_auth),
):
    """Return recent capture management actions for audit display."""
    rows = db.execute(
        """SELECT id, action, requested_by, requested_at, completed_at,
                  status, result_summary, pi_host, duration_ms
           FROM capture_actions
           ORDER BY requested_at DESC
           LIMIT ?""",
        (min(limit, 100),),
    ).fetchall()
    return {"actions": [dict(row) for row in rows]}



# --- Alert Evaluator Background Task ---

async def alert_evaluator():
    """Background task: evaluate capture alert conditions every 30s."""
    await _asyncio_mod.sleep(60)  # Wait for first heartbeat after startup
    while True:
        await _asyncio_mod.sleep(30)
        try:
            db = get_connection()
            try:
                changes = evaluate_alerts(db, _last_status, _last_heartbeat_received_at)
                for change in changes:
                    await _broadcast(change)
            finally:
                db.close()
        except Exception:
            log.exception("Alert evaluator error")


# --- Alert API Endpoints ---

@router.get("/api/capture/alerts")
async def get_active_alerts(db=Depends(get_db), _user=Depends(_verify_capture_auth)):
    """Return currently open capture alerts."""
    alerts = get_open_alerts(db)
    return {"alerts": alerts, "count": len(alerts)}


@router.get("/api/capture/alerts/history")
async def get_alerts_history(
    limit: int = 50,
    db=Depends(get_db),
    _user=Depends(_verify_capture_auth),
):
    """Return recent alert history (open + resolved)."""
    history = get_alert_history(db, min(limit, 200))
    return {"alerts": history}
