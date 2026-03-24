"""Phase 6.3 — Undo API: reverse tracker writebacks for a committed communication.

Spec authority: 02_PIPELINE_ARCHITECTURE.md §4D, §5I

Undo operates entirely from tracker_writebacks records — never from recomputed
extraction output. Each writeback has the exact table, record_id, write_type,
written_data, and previous_data needed to reverse the operation.

Undo flow:
  1. Validate communication is in undoable state ("complete")
  2. Load all non-reversed tracker_writebacks for the communication
  3. For each writeback (reverse dependency order):
     a. Fetch current tracker record
     b. Compare current state to written_data → detect conflicts
     c. If no conflicts: reverse the operation (delete for inserts, restore for updates)
     d. Mark writeback as reversed
  4. Reset communication status to "reviewed"
  5. Audit everything

Conflict detection:
  - For inserts: compare current record fields to written_data; if any AI-written
    field has been modified by a human, flag as conflict.
  - For updates: compare current record's updated fields to written_data;
    if they differ, the record has been modified since the AI update.
  - Conflicts block undo by default. force=True overrides (deletes/restores anyway).
"""

import json
import logging
from dataclasses import dataclass, field
from enum import Enum

import httpx

from app.config import TRACKER_BASE_URL, TRACKER_USER, TRACKER_PASS
from app.bundle_review.audit import write_audit

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════
# Typed errors
# ═══════════════════════════════════════════════════════════════════════════

class UndoErrorType(str, Enum):
    INVALID_COMMUNICATION = "invalid_communication"
    NOT_UNDOABLE_STATE = "not_undoable_state"
    NO_WRITEBACKS = "no_writebacks"
    ALREADY_REVERSED = "already_reversed"
    TRACKER_RECORD_MISSING = "tracker_record_missing"
    CONFLICT_DETECTED = "conflict_detected"
    FORCE_NOT_ALLOWED = "force_not_allowed"
    TRACKER_ERROR = "tracker_error"
    PARTIAL_FAILURE = "partial_failure"


class UndoError(Exception):
    """Typed undo failure."""
    def __init__(self, error_type: UndoErrorType, message: str,
                 details: dict | None = None):
        self.error_type = error_type
        self.message = message
        self.details = details or {}
        super().__init__(f"[{error_type.value}] {message}")


# ═══════════════════════════════════════════════════════════════════════════
# Data structures
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class ConflictInfo:
    """A single field-level conflict between written and current state."""
    writeback_id: str
    target_table: str
    target_record_id: str
    write_type: str
    field_name: str
    written_value: object
    current_value: object


@dataclass
class WritebackReversal:
    """Result of reversing a single writeback."""
    writeback_id: str
    target_table: str
    target_record_id: str
    write_type: str
    success: bool
    skipped: bool = False
    skip_reason: str | None = None
    conflicts: list[ConflictInfo] = field(default_factory=list)
    error: str | None = None


@dataclass
class UndoResult:
    """Complete undo operation result."""
    communication_id: str
    success: bool = False
    total_writebacks: int = 0
    reversed_count: int = 0
    skipped_count: int = 0
    conflict_count: int = 0
    forced: bool = False
    reversals: list[WritebackReversal] = field(default_factory=list)
    conflicts: list[ConflictInfo] = field(default_factory=list)
    error: str | None = None
    error_type: UndoErrorType | None = None


# States from which undo is allowed
UNDOABLE_STATES = {"complete"}

# Tracker interaction timeout — normalized to match tracker_client.py (30s)
TRACKER_TIMEOUT = 30.0

# Fields to ignore when detecting conflicts (system-managed, not user-editable)
SYSTEM_FIELDS = {
    "id", "created_at", "updated_at", "created_by", "updated_by",
    "source", "source_id", "ai_confidence", "automation_hold",
    "external_refs",
}


# ═══════════════════════════════════════════════════════════════════════════
# Tracker HTTP helpers
# ═══════════════════════════════════════════════════════════════════════════

def _tracker_auth():
    if TRACKER_USER and TRACKER_PASS:
        return (TRACKER_USER, TRACKER_PASS)
    return None


async def _tracker_get(table: str, record_id: str) -> dict | None:
    """GET a single tracker record. Returns None if 404."""
    url = f"{TRACKER_BASE_URL}/{table}/{record_id}"
    try:
        async with httpx.AsyncClient(timeout=TRACKER_TIMEOUT) as client:
            resp = await client.get(url, auth=_tracker_auth())
        if resp.status_code == 200:
            return resp.json()
        if resp.status_code == 404:
            return None
        logger.warning("Tracker GET %s/%s returned %d", table, record_id[:8], resp.status_code)
        return None
    except (httpx.ConnectError, httpx.TimeoutException) as e:
        logger.error("Tracker GET failed: %s", e)
        return None


async def _tracker_delete(table: str, record_id: str) -> bool:
    """DELETE a tracker record. Returns True on success or 404 (already gone)."""
    url = f"{TRACKER_BASE_URL}/{table}/{record_id}"
    try:
        async with httpx.AsyncClient(timeout=TRACKER_TIMEOUT) as client:
            resp = await client.delete(url, auth=_tracker_auth())
        if resp.status_code in (200, 204, 404):
            return True
        logger.warning("Tracker DELETE %s/%s returned %d: %s",
                       table, record_id[:8], resp.status_code, resp.text[:200])
        return False
    except (httpx.ConnectError, httpx.TimeoutException) as e:
        logger.error("Tracker DELETE failed: %s", e)
        return False


async def _tracker_update(table: str, record_id: str, data: dict) -> bool:
    """PUT/PATCH a tracker record to restore previous_data. Returns True on success."""
    url = f"{TRACKER_BASE_URL}/{table}/{record_id}"
    try:
        async with httpx.AsyncClient(timeout=TRACKER_TIMEOUT) as client:
            resp = await client.put(url, json=data, auth=_tracker_auth())
        if resp.status_code in (200, 204):
            return True
        logger.warning("Tracker PUT %s/%s returned %d: %s",
                       table, record_id[:8], resp.status_code, resp.text[:200])
        return False
    except (httpx.ConnectError, httpx.TimeoutException) as e:
        logger.error("Tracker PUT failed: %s", e)
        return False


# ═══════════════════════════════════════════════════════════════════════════
# Conflict detection
# ═══════════════════════════════════════════════════════════════════════════

def _detect_conflicts(
    writeback_id: str,
    target_table: str,
    target_record_id: str,
    write_type: str,
    written_data: dict,
    current_record: dict,
) -> list[ConflictInfo]:
    """Compare written_data to current tracker record, return field-level conflicts.

    A conflict exists when a field that the AI wrote has been subsequently
    modified by a human (current value differs from what the AI wrote).
    """
    conflicts = []

    for field_name, written_value in written_data.items():
        if field_name in SYSTEM_FIELDS:
            continue

        current_value = current_record.get(field_name)

        # Normalize JSON strings for comparison
        if isinstance(written_value, str) and isinstance(current_value, str):
            try:
                w = json.loads(written_value)
                c = json.loads(current_value)
                if w == c:
                    continue
            except (json.JSONDecodeError, TypeError):
                pass

        # Normalize None vs missing
        if written_value is None and current_value is None:
            continue
        if written_value is None and field_name not in current_record:
            continue

        # Type-coerce for comparison (tracker may return int vs str)
        if str(written_value) == str(current_value):
            continue

        if written_value != current_value:
            conflicts.append(ConflictInfo(
                writeback_id=writeback_id,
                target_table=target_table,
                target_record_id=target_record_id,
                write_type=write_type,
                field_name=field_name,
                written_value=written_value,
                current_value=current_value,
            ))

    return conflicts


# ═══════════════════════════════════════════════════════════════════════════
# Reverse dependency ordering for undo
# ═══════════════════════════════════════════════════════════════════════════

# Reverse of ITEM_TYPE_ORDER from ordering.py:
# Undo must delete in reverse order to avoid FK constraint violations
# e.g., delete meeting_participants before meetings, stakeholders before people
UNDO_TABLE_ORDER = {
    "matter_updates": 0,
    "decisions": 0,
    "tasks": 0,
    "documents": 0,
    "meeting_matters": 1,
    "meeting_participants": 1,
    "matter_people": 2,
    "matter_organizations": 2,
    "meetings": 3,
    "people": 4,
    "organizations": 5,
    "matters": 6,
}


def _undo_sort_key(wb: dict) -> int:
    """Sort writebacks for undo: leaf tables first, root tables last."""
    return UNDO_TABLE_ORDER.get(wb["target_table"], 10)


# ═══════════════════════════════════════════════════════════════════════════
# Main undo function
# ═══════════════════════════════════════════════════════════════════════════

async def undo_communication(
    db,
    communication_id: str,
    force: bool = False,
) -> UndoResult:
    """Reverse all tracker writebacks for a committed communication.

    Args:
        db: sqlite3 connection
        communication_id: the communication to undo
        force: if True, override conflicts and undo anyway

    Returns:
        UndoResult with detailed per-writeback outcomes

    Raises:
        UndoError for validation failures (invalid state, no writebacks, etc.)
    """
    result = UndoResult(communication_id=communication_id, forced=force)

    # ── Step 1: Validate communication exists and is undoable ──
    comm = db.execute(
        "SELECT id, processing_status FROM communications WHERE id = ?",
        (communication_id,),
    ).fetchone()

    if not comm:
        raise UndoError(
            UndoErrorType.INVALID_COMMUNICATION,
            f"Communication {communication_id} not found",
        )

    if comm["processing_status"] not in UNDOABLE_STATES:
        raise UndoError(
            UndoErrorType.NOT_UNDOABLE_STATE,
            f"Communication is in '{comm['processing_status']}' state, "
            f"must be one of: {', '.join(sorted(UNDOABLE_STATES))}",
            {"current_status": comm["processing_status"]},
        )

    # ── Step 2: Load non-reversed writebacks ──
    writebacks = db.execute("""
        SELECT id, communication_id, bundle_id, bundle_item_id,
               target_table, target_record_id, write_type,
               written_data, previous_data, reversed
        FROM tracker_writebacks
        WHERE communication_id = ? AND reversed = 0
        ORDER BY rowid ASC
    """, (communication_id,)).fetchall()

    result.total_writebacks = len(writebacks)

    if not writebacks:
        # Check if there are already-reversed writebacks
        any_reversed = db.execute(
            "SELECT COUNT(*) as cnt FROM tracker_writebacks WHERE communication_id = ? AND reversed = 1",
            (communication_id,),
        ).fetchone()["cnt"]

        if any_reversed > 0:
            raise UndoError(
                UndoErrorType.ALREADY_REVERSED,
                f"All {any_reversed} writebacks for this communication have already been reversed",
            )
        raise UndoError(
            UndoErrorType.NO_WRITEBACKS,
            "No committed writebacks found for this communication",
        )

    # Convert to dicts for sorting
    wb_list = [dict(wb) for wb in writebacks]

    # Sort in reverse dependency order (leaf tables first)
    wb_list.sort(key=_undo_sort_key)

    # ── Step 3: Audit undo_started ──
    write_audit(db, communication_id, None, None, "undo_started", {
        "total_writebacks": len(wb_list),
        "force": force,
    })
    db.commit()

    # ── Step 4: Conflict detection pass (unless force) ──
    all_conflicts = []

    if not force:
        for wb in wb_list:
            written_data = _parse_json(wb["written_data"])
            if not written_data:
                continue

            # Fetch current state from tracker
            current = await _tracker_get(wb["target_table"], wb["target_record_id"])

            if current is None:
                # Record missing — for inserts, this is fine (already deleted)
                # For updates, this is unexpected
                if wb["write_type"] == "update":
                    all_conflicts.append(ConflictInfo(
                        writeback_id=wb["id"],
                        target_table=wb["target_table"],
                        target_record_id=wb["target_record_id"],
                        write_type=wb["write_type"],
                        field_name="_record",
                        written_value="exists",
                        current_value="missing",
                    ))
                continue

            conflicts = _detect_conflicts(
                wb["id"], wb["target_table"], wb["target_record_id"],
                wb["write_type"], written_data, current,
            )
            all_conflicts.extend(conflicts)

    if all_conflicts and not force:
        result.success = False
        result.conflicts = all_conflicts
        result.conflict_count = len(all_conflicts)
        result.error_type = UndoErrorType.CONFLICT_DETECTED
        result.error = (
            f"{len(all_conflicts)} conflict(s) detected across "
            f"{len(set(c.writeback_id for c in all_conflicts))} writebacks. "
            f"Use force=true to override."
        )

        # Audit conflict
        write_audit(db, communication_id, None, None, "undo_conflict_detected", {
            "conflict_count": len(all_conflicts),
            "affected_tables": list(set(c.target_table for c in all_conflicts)),
            "conflicts": [
                {
                    "table": c.target_table,
                    "record_id": c.target_record_id,
                    "field": c.field_name,
                    "written": str(c.written_value)[:200],
                    "current": str(c.current_value)[:200],
                }
                for c in all_conflicts[:20]  # cap audit detail
            ],
        })
        db.commit()

        return result

    # ── Step 5: Execute reversals ──
    for wb in wb_list:
        reversal = WritebackReversal(
            writeback_id=wb["id"],
            target_table=wb["target_table"],
            target_record_id=wb["target_record_id"],
            write_type=wb["write_type"],
            success=False,
        )

        try:
            if wb["write_type"] == "insert":
                # Reverse an insert → delete the record
                ok = await _tracker_delete(wb["target_table"], wb["target_record_id"])
                if ok:
                    reversal.success = True
                    _mark_reversed(db, wb["id"])
                    result.reversed_count += 1
                else:
                    reversal.error = "Tracker delete failed"

            elif wb["write_type"] == "update":
                # Reverse an update → restore previous_data
                previous = _parse_json(wb["previous_data"])
                if previous:
                    ok = await _tracker_update(
                        wb["target_table"], wb["target_record_id"], previous,
                    )
                    if ok:
                        reversal.success = True
                        _mark_reversed(db, wb["id"])
                        result.reversed_count += 1
                    else:
                        reversal.error = "Tracker update failed"
                else:
                    # No previous_data — can't restore, skip
                    reversal.skipped = True
                    reversal.skip_reason = "No previous_data available to restore"
                    result.skipped_count += 1
                    _mark_reversed(db, wb["id"])  # Still mark reversed to prevent retry

            else:
                reversal.skipped = True
                reversal.skip_reason = f"Unknown write_type: {wb['write_type']}"
                result.skipped_count += 1

        except Exception as e:
            reversal.error = str(e)
            logger.exception("[%s] Undo reversal failed for writeback %s",
                             communication_id[:8], wb["id"][:8])

        result.reversals.append(reversal)

    db.commit()

    # ── Step 6: Determine overall success ──
    failed_reversals = [r for r in result.reversals if not r.success and not r.skipped]
    result.success = len(failed_reversals) == 0

    # ── Step 7: Update communication status ──
    if result.success:
        db.execute("""
            UPDATE communications
            SET processing_status = 'reviewed',
                error_message = NULL,
                error_stage = NULL,
                updated_at = datetime('now')
            WHERE id = ?
        """, (communication_id,))
        db.commit()

        write_audit(db, communication_id, None, None, "undo_complete", {
            "reversed_count": result.reversed_count,
            "skipped_count": result.skipped_count,
            "forced": force,
        })
        db.commit()

        logger.info(
            "[%s] Undo complete: %d reversed, %d skipped",
            communication_id[:8], result.reversed_count, result.skipped_count,
        )
    else:
        # Partial failure — leave status as-is, record the failure
        write_audit(db, communication_id, None, None, "undo_partial_failure", {
            "reversed_count": result.reversed_count,
            "failed_count": len(failed_reversals),
            "skipped_count": result.skipped_count,
            "failed_tables": [r.target_table for r in failed_reversals],
        })
        db.commit()

        result.error_type = UndoErrorType.PARTIAL_FAILURE
        result.error = (
            f"Partial undo: {result.reversed_count} reversed, "
            f"{len(failed_reversals)} failed, {result.skipped_count} skipped"
        )

        logger.warning(
            "[%s] Undo partial failure: %d reversed, %d failed",
            communication_id[:8], result.reversed_count, len(failed_reversals),
        )

    return result


# ═══════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════

def _mark_reversed(db, writeback_id: str):
    """Mark a single tracker_writebacks row as reversed."""
    db.execute("""
        UPDATE tracker_writebacks
        SET reversed = 1, reversed_at = datetime('now')
        WHERE id = ?
    """, (writeback_id,))


def _parse_json(raw: str | None) -> dict | None:
    """Parse JSON string, return None on failure."""
    if not raw or raw == "null":
        return None
    try:
        result = json.loads(raw)
        return result if isinstance(result, dict) else None
    except (json.JSONDecodeError, TypeError):
        return None
