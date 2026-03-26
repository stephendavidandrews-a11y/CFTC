"""
Voice profile management — CRUD, quality-gated promotion, running average updates.

Design:
  - One aggregate embedding per person (for fast O(n) matching)
  - Individual confirmed samples preserved in voice_samples for audit/rebuild
  - Profile update uses 70/30 old/new running average (prevents single-sample corruption)
  - Quality gate: minimum 5 seconds of speech before promoting to profile
  - L2 normalization on storage
"""

import logging
import math
import struct
import uuid
from typing import Optional

logger = logging.getLogger(__name__)

EMBEDDING_DIM = 192
FLOAT32_SIZE = 4
EXPECTED_BLOB_SIZE = EMBEDDING_DIM * FLOAT32_SIZE

# Minimum speech duration (seconds) before a sample can update a profile
MIN_SPEECH_SECONDS = 5.0

# Running average blend factor: 70% existing + 30% new sample
BLEND_OLD = 0.7
BLEND_NEW = 0.3


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _unpack(blob: bytes) -> Optional[list[float]]:
    if not blob or len(blob) != EXPECTED_BLOB_SIZE:
        return None
    return list(struct.unpack(f"<{EMBEDDING_DIM}f", blob))


def _pack(vec: list[float]) -> bytes:
    return struct.pack(f"<{EMBEDDING_DIM}f", *vec)


def _l2_normalize(vec: list[float]) -> list[float]:
    norm = math.sqrt(sum(x * x for x in vec))
    if norm == 0.0:
        return vec
    return [x / norm for x in vec]


def _is_zero_vec(vec: list[float]) -> bool:
    return all(x == 0.0 for x in vec)


# ---------------------------------------------------------------------------
# Profile CRUD
# ---------------------------------------------------------------------------


def get_profile(db, tracker_person_id: str) -> Optional[dict]:
    """Get a voice profile by tracker person ID. Returns None if not found."""
    row = db.execute(
        """SELECT id, tracker_person_id, embedding_dimension, quality_score,
                  sample_count, total_speech_seconds, status, source_communication_id,
                  created_from, created_at, updated_at
           FROM speaker_voice_profiles
           WHERE tracker_person_id = ?
           ORDER BY updated_at DESC LIMIT 1""",
        (tracker_person_id,),
    ).fetchone()
    if not row:
        return None
    return dict(row)


def list_profiles(db, status: str = "active") -> list[dict]:
    """List all voice profiles, optionally filtered by status."""
    if status:
        rows = db.execute(
            """SELECT id, tracker_person_id, embedding_dimension, quality_score,
                      sample_count, total_speech_seconds, status,
                      source_communication_id, created_from, created_at, updated_at
               FROM speaker_voice_profiles WHERE status = ?
               ORDER BY updated_at DESC""",
            (status,),
        ).fetchall()
    else:
        rows = db.execute(
            """SELECT id, tracker_person_id, embedding_dimension, quality_score,
                      sample_count, total_speech_seconds, status,
                      source_communication_id, created_from, created_at, updated_at
               FROM speaker_voice_profiles ORDER BY updated_at DESC"""
        ).fetchall()
    return [dict(r) for r in rows]


def deactivate_profile(db, tracker_person_id: str) -> bool:
    """Set a profile to inactive (stops matching). Returns True if found."""
    result = db.execute(
        "UPDATE speaker_voice_profiles SET status = 'inactive', updated_at = datetime('now') WHERE tracker_person_id = ? AND status = 'active'",
        (tracker_person_id,),
    )
    db.commit()
    return result.rowcount > 0


def activate_profile(db, tracker_person_id: str) -> bool:
    """Re-activate an inactive profile. Returns True if found."""
    result = db.execute(
        "UPDATE speaker_voice_profiles SET status = 'active', updated_at = datetime('now') WHERE tracker_person_id = ? AND status = 'inactive'",
        (tracker_person_id,),
    )
    db.commit()
    return result.rowcount > 0


# ---------------------------------------------------------------------------
# Quality-gated profile promotion
# ---------------------------------------------------------------------------


def promote_sample_to_profile(
    db,
    communication_id: str,
    speaker_label: str,
    tracker_person_id: str,
) -> dict:
    """Promote a confirmed speaker embedding into a voice profile.

    Called after human confirms speaker identity in speaker review.

    Returns:
        {"status": "created" | "updated" | "skipped", "reason": str}
    """
    # Get the voice sample for this speaker
    sample = db.execute(
        "SELECT id, embedding FROM voice_samples WHERE communication_id = ? AND speaker_label = ? AND embedding IS NOT NULL LIMIT 1",
        (communication_id, speaker_label),
    ).fetchone()

    if not sample:
        return {"status": "skipped", "reason": "no voice sample found"}

    emb = _unpack(sample["embedding"])
    if emb is None or _is_zero_vec(emb):
        return {"status": "skipped", "reason": "invalid or zero embedding"}

    # Quality gate: check total speech duration for this speaker
    dur_row = db.execute(
        "SELECT SUM(end_time - start_time) as total FROM transcripts WHERE communication_id = ? AND speaker_label = ?",
        (communication_id, speaker_label),
    ).fetchone()
    speech_seconds = dur_row["total"] if dur_row and dur_row["total"] else 0.0

    if speech_seconds < MIN_SPEECH_SECONDS:
        logger.info(
            "[%s] Skipping profile promotion for %s: %.1fs speech (min %.1fs)",
            communication_id[:8],
            speaker_label,
            speech_seconds,
            MIN_SPEECH_SECONDS,
        )
        return {
            "status": "skipped",
            "reason": f"insufficient speech ({speech_seconds:.1f}s < {MIN_SPEECH_SECONDS}s)",
        }

    quality = min(1.0, speech_seconds / 30.0)  # 30s = max quality score

    # Check existing profile
    existing = db.execute(
        "SELECT id, embedding, sample_count, total_speech_seconds FROM speaker_voice_profiles WHERE tracker_person_id = ? AND status = 'active' ORDER BY updated_at DESC LIMIT 1",
        (tracker_person_id,),
    ).fetchone()

    if existing:
        old_emb = _unpack(existing["embedding"])
        if old_emb and len(old_emb) == len(emb):
            # Running average: 70% old + 30% new, then L2 normalize
            blended = [BLEND_OLD * o + BLEND_NEW * n for o, n in zip(old_emb, emb)]
            blended = _l2_normalize(blended)
            new_count = (existing["sample_count"] or 1) + 1
            new_total = (existing["total_speech_seconds"] or 0.0) + speech_seconds

            db.execute(
                """
                UPDATE speaker_voice_profiles
                SET embedding = ?, quality_score = ?, sample_count = ?,
                    total_speech_seconds = ?, source_communication_id = ?,
                    updated_at = datetime('now')
                WHERE id = ?
            """,
                (
                    _pack(blended),
                    quality,
                    new_count,
                    new_total,
                    communication_id,
                    existing["id"],
                ),
            )
        else:
            # Dimension mismatch — overwrite (shouldn't happen normally)
            normalized = _l2_normalize(emb)
            db.execute(
                """
                UPDATE speaker_voice_profiles
                SET embedding = ?, quality_score = ?, sample_count = 1,
                    total_speech_seconds = ?, source_communication_id = ?,
                    updated_at = datetime('now')
                WHERE id = ?
            """,
                (
                    _pack(normalized),
                    quality,
                    speech_seconds,
                    communication_id,
                    existing["id"],
                ),
            )

        result_status = "updated"
        logger.info(
            "[%s] Updated voice profile for person %s (sample #%d)",
            communication_id[:8],
            tracker_person_id[:8],
            (existing["sample_count"] or 1) + 1,
        )
    else:
        # Create new profile
        normalized = _l2_normalize(emb)
        profile_id = str(uuid.uuid4())
        db.execute(
            """
            INSERT INTO speaker_voice_profiles
                (id, tracker_person_id, embedding, embedding_dimension, quality_score,
                 sample_count, total_speech_seconds, status, source_communication_id,
                 created_from)
            VALUES (?, ?, ?, ?, ?, 1, ?, 'active', ?, 'confirmed_review')
        """,
            (
                profile_id,
                tracker_person_id,
                _pack(normalized),
                EMBEDDING_DIM,
                quality,
                speech_seconds,
                communication_id,
            ),
        )

        result_status = "created"
        logger.info(
            "[%s] Created voice profile for person %s",
            communication_id[:8],
            tracker_person_id[:8],
        )

    # Mark the voice sample as promoted
    db.execute(
        "UPDATE voice_samples SET promoted_to_profile = 1, speech_duration_seconds = ? WHERE id = ?",
        (speech_seconds, sample["id"]),
    )

    db.commit()
    return {
        "status": result_status,
        "reason": f"speech={speech_seconds:.1f}s, quality={quality:.2f}",
    }


def get_sample_history(db, tracker_person_id: str) -> list[dict]:
    """Get all voice samples that have been promoted to this person's profile."""
    rows = db.execute(
        """
        SELECT vs.id, vs.communication_id, vs.speaker_label,
               vs.speech_duration_seconds, vs.created_at,
               c.title as communication_title
        FROM voice_samples vs
        JOIN communication_participants cp
            ON cp.communication_id = vs.communication_id
            AND cp.speaker_label = vs.speaker_label
        LEFT JOIN communications c ON c.id = vs.communication_id
        WHERE cp.tracker_person_id = ?
          AND vs.promoted_to_profile = 1
        ORDER BY vs.created_at DESC
    """,
        (tracker_person_id,),
    ).fetchall()
    return [dict(r) for r in rows]
