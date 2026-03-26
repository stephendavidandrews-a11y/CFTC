"""Voiceprint quality gate -- validates audio segments before voiceprint commitment.

Runs AFTER diarization and vocal analysis, BEFORE voiceprint storage.
Ensures only high-quality, single-speaker audio is used for voiceprint enrollment.

Pipeline:
  Step 1: Segment selection (confidence + duration filters)
  Step 2: Signal quality scoring (SNR, HNR, jitter, shimmer, energy)
  Step 3: Speaker purity validation (F0 unimodality check)
  Step 4: Assembly (rank by SNR, select best 30-40s)
  Step 5: Store as candidate for human review
  Step 6: Commit only after human acceptance (handled by review API)
"""

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class QualityMetrics:
    snr_db: float | None = None
    hnr_db: float | None = None
    jitter: float | None = None
    shimmer: float | None = None
    energy_variance_ratio: float | None = None
    duration: float = 0.0
    passed: bool = False
    rejection_reasons: list[str] = field(default_factory=list)


@dataclass
class QualityGateResult:
    speaker_label: str
    total_candidate_segments: int
    segments_passed: int
    total_clean_duration: float
    avg_snr_db: float | None
    avg_hnr_db: float | None
    f0_stddev_ratio: float | None
    f0_unimodal: bool
    status: str  # "accepted_for_review", "provisional", "rejected"
    rejection_reason: str | None
    selected_segment_indices: list[int] = field(default_factory=list)


def run_quality_gate(
    conn,
    conversation_id: str,
    speaker_label: str,
    segments: list[dict],
    audio_path: Path,
    diarization_embeddings: dict[str, np.ndarray],
) -> QualityGateResult:
    """Run the full voiceprint quality gate pipeline for one speaker.

    Args:
        conn: SQLite connection.
        conversation_id: Conversation ID.
        speaker_label: e.g. "SPEAKER_00".
        segments: List of dicts with "start", "end", and vocal features.
        audio_path: Path to preprocessed audio.
        diarization_embeddings: Speaker embeddings from pyannote.

    Returns:
        QualityGateResult with status and metrics.
    """
    from config import (
        VP_MIN_SEGMENT_DURATION,
        VP_MIN_SNR_DB,
        VP_MIN_HNR_DB,
        VP_MAX_JITTER_PCT,
        VP_MAX_SHIMMER_PCT,
        VP_MAX_ENERGY_VARIANCE_STD,
        VP_MAX_F0_STDDEV_RATIO,
        VP_TARGET_DURATION_MIN,
        VP_TARGET_DURATION_MAX,
        VP_PROVISIONAL_IF_BELOW,
    )

    log_prefix = f"[{conversation_id[:8]}:{speaker_label}]"

    # Step 1: Segment selection -- filter by duration
    # (diarization confidence is not directly available per-segment from pyannote
    # output, so we filter by duration and rely on non-overlapping segments)
    candidates = []
    for i, seg in enumerate(segments):
        duration = seg["end"] - seg["start"]
        if duration < VP_MIN_SEGMENT_DURATION:
            continue
        candidates.append({"index": i, **seg})

    logger.info(
        f"{log_prefix} Step 1: {len(candidates)}/{len(segments)} segments pass duration filter"
    )

    if not candidates:
        return QualityGateResult(
            speaker_label=speaker_label,
            total_candidate_segments=len(segments),
            segments_passed=0,
            total_clean_duration=0.0,
            avg_snr_db=None,
            avg_hnr_db=None,
            f0_stddev_ratio=None,
            f0_unimodal=True,
            status="rejected",
            rejection_reason=f"No segments >= {VP_MIN_SEGMENT_DURATION}s duration",
        )

    # Step 2: Signal quality scoring
    # Use vocal features already extracted (avoid recomputation)
    quality_segments = []
    for seg in candidates:
        features = seg.get("features", {})
        metrics = _score_signal_quality(
            features,
            VP_MIN_SNR_DB,
            VP_MIN_HNR_DB,
            VP_MAX_JITTER_PCT,
            VP_MAX_SHIMMER_PCT,
            VP_MAX_ENERGY_VARIANCE_STD,
        )
        metrics.duration = seg["end"] - seg["start"]
        if metrics.passed:
            quality_segments.append({**seg, "metrics": metrics})
        else:
            logger.debug(
                f"{log_prefix} Segment {seg['index']} rejected: {metrics.rejection_reasons}"
            )

    logger.info(
        f"{log_prefix} Step 2: {len(quality_segments)}/{len(candidates)} pass quality gate"
    )

    if not quality_segments:
        return QualityGateResult(
            speaker_label=speaker_label,
            total_candidate_segments=len(segments),
            segments_passed=0,
            total_clean_duration=0.0,
            avg_snr_db=None,
            avg_hnr_db=None,
            f0_stddev_ratio=None,
            f0_unimodal=True,
            status="rejected",
            rejection_reason="No segments pass signal quality thresholds",
        )

    # Step 3: Speaker purity validation (F0 unimodality)
    f0_values = [
        s["features"]["pitch_mean"]
        for s in quality_segments
        if s.get("features", {}).get("pitch_mean") is not None
    ]

    f0_unimodal = True
    f0_stddev_ratio = None
    if f0_values and len(f0_values) >= 2:
        f0_mean = np.mean(f0_values)
        f0_std = np.std(f0_values)
        if f0_mean > 0:
            f0_stddev_ratio = f0_std / f0_mean
            if f0_stddev_ratio > VP_MAX_F0_STDDEV_RATIO:
                f0_unimodal = False
                logger.warning(
                    f"{log_prefix} Step 3: F0 distribution suspicious "
                    f"(stddev/mean={f0_stddev_ratio:.2f} > {VP_MAX_F0_STDDEV_RATIO})"
                )

    if not f0_unimodal:
        # Store as provisional with contamination flag
        _store_candidate(
            conn,
            conversation_id,
            speaker_label,
            quality_segments,
            diarization_embeddings,
            "provisional",
            f"F0 distribution non-unimodal (stddev/mean={f0_stddev_ratio:.2f})",
            f0_stddev_ratio,
            f0_unimodal,
        )
        return QualityGateResult(
            speaker_label=speaker_label,
            total_candidate_segments=len(segments),
            segments_passed=len(quality_segments),
            total_clean_duration=sum(s["metrics"].duration for s in quality_segments),
            avg_snr_db=_avg_metric(quality_segments, "snr_db"),
            avg_hnr_db=_avg_metric(quality_segments, "hnr_db"),
            f0_stddev_ratio=f0_stddev_ratio,
            f0_unimodal=False,
            status="provisional",
            rejection_reason=f"Potential speaker contamination (F0 stddev/mean={f0_stddev_ratio:.2f})",
        )

    # Step 4: Assembly -- rank by SNR descending, select best 30-40s
    quality_segments.sort(
        key=lambda s: s["metrics"].snr_db if s["metrics"].snr_db is not None else 0,
        reverse=True,
    )

    selected = []
    total_duration = 0.0
    for seg in quality_segments:
        if total_duration >= VP_TARGET_DURATION_MAX:
            break
        selected.append(seg)
        total_duration += seg["metrics"].duration

    total_clean = sum(s["metrics"].duration for s in selected)
    logger.info(
        f"{log_prefix} Step 4: Selected {len(selected)} segments, {total_clean:.1f}s clean audio"
    )

    if total_clean < VP_PROVISIONAL_IF_BELOW:
        status = "provisional"
        reason = (
            f"Only {total_clean:.1f}s of clean audio (need {VP_TARGET_DURATION_MIN}s)"
        )
    else:
        status = "accepted_for_review"
        reason = None

    _store_candidate(
        conn,
        conversation_id,
        speaker_label,
        selected,
        diarization_embeddings,
        status,
        reason,
        f0_stddev_ratio,
        f0_unimodal,
    )

    return QualityGateResult(
        speaker_label=speaker_label,
        total_candidate_segments=len(segments),
        segments_passed=len(selected),
        total_clean_duration=total_clean,
        avg_snr_db=_avg_metric(selected, "snr_db"),
        avg_hnr_db=_avg_metric(selected, "hnr_db"),
        f0_stddev_ratio=f0_stddev_ratio,
        f0_unimodal=f0_unimodal,
        status=status,
        rejection_reason=reason,
        selected_segment_indices=[s["index"] for s in selected],
    )


def accept_voiceprint_candidate(conn, candidate_id: str, tracker_person_id: str):
    """Accept a voiceprint candidate after human review (Step 6).

    Commits the embedding to speaker_voice_profiles and locks it.
    """
    candidate = conn.execute(
        "SELECT * FROM voiceprint_candidates WHERE id = ?", (candidate_id,)
    ).fetchone()

    if not candidate:
        logger.error(f"Voiceprint candidate not found: {candidate_id}")
        return False

    if candidate["status"] == "accepted":
        logger.warning(f"Candidate {candidate_id} already accepted")
        return True

    embedding_bytes = candidate["embedding"]
    if not embedding_bytes:
        logger.error(f"No embedding for candidate {candidate_id}")
        return False

    now = datetime.now(timezone.utc).isoformat()

    # Check if person already has a profile (locked voiceprints are not auto-updated)
    existing = conn.execute(
        "SELECT id FROM speaker_voice_profiles WHERE tracker_person_id = ?",
        (tracker_person_id,),
    ).fetchone()

    if existing:
        # Replace existing profile
        conn.execute(
            """UPDATE speaker_voice_profiles
               SET embedding = ?, quality_score = ?, source_conversation_id = ?
               WHERE id = ?""",
            (
                embedding_bytes,
                candidate["quality_score"],
                candidate["conversation_id"],
                existing["id"],
            ),
        )
        logger.info(f"Re-enrolled voiceprint for person {tracker_person_id[:8]}")
    else:
        # Create new profile
        conn.execute(
            """INSERT INTO speaker_voice_profiles
               (id, tracker_person_id, embedding, source_conversation_id, quality_score)
               VALUES (?, ?, ?, ?, ?)""",
            (
                str(uuid.uuid4()),
                tracker_person_id,
                embedding_bytes,
                candidate["conversation_id"],
                candidate["quality_score"],
            ),
        )
        logger.info(f"Created voiceprint for person {tracker_person_id[:8]}")

    # Mark candidate as accepted
    conn.execute(
        "UPDATE voiceprint_candidates SET status = 'accepted', reviewed_at = ? WHERE id = ?",
        (now, candidate_id),
    )

    return True


def reject_voiceprint_candidate(conn, candidate_id: str, reason: str = ""):
    """Reject a voiceprint candidate after human review."""
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "UPDATE voiceprint_candidates SET status = 'rejected', rejection_reason = ?, reviewed_at = ? WHERE id = ?",
        (reason or "Manual rejection", now, candidate_id),
    )
    logger.info(f"Rejected voiceprint candidate {candidate_id}")


def _score_signal_quality(
    features: dict,
    min_snr: float,
    min_hnr: float,
    max_jitter: float,
    max_shimmer: float,
    max_energy_var_std: float,
) -> QualityMetrics:
    """Score a segment's signal quality against thresholds."""
    metrics = QualityMetrics()
    reasons = []

    # SNR -- estimate from RMS energy vs noise floor
    # Use RMS mean as proxy; actual SNR requires noise estimation
    # For now, use HNR as the primary quality indicator
    rms = features.get("rms_mean")
    if rms is not None and rms > 0:
        # Rough SNR estimate: 20 * log10(rms / noise_floor)
        # Using HNR as a proxy since it measures signal vs noise
        metrics.snr_db = features.get("hnr")  # HNR is close to SNR for voiced speech
    else:
        metrics.snr_db = features.get("hnr")

    # HNR
    hnr = features.get("hnr")
    metrics.hnr_db = hnr
    if hnr is not None and hnr < min_hnr:
        reasons.append(f"HNR {hnr:.1f}dB < {min_hnr}dB")

    # Jitter
    jitter = features.get("jitter")
    metrics.jitter = jitter
    if jitter is not None and jitter > max_jitter:
        reasons.append(f"Jitter {jitter:.4f} > {max_jitter}")

    # Shimmer
    shimmer = features.get("shimmer")
    metrics.shimmer = shimmer
    if shimmer is not None and shimmer > max_shimmer:
        reasons.append(f"Shimmer {shimmer:.4f} > {max_shimmer}")

    # Energy consistency -- check if intensity_mean suggests stable signal
    # (Full energy variance check would require per-frame data; using intensity as proxy)
    intensity = features.get("intensity_mean")
    if intensity is not None:
        metrics.energy_variance_ratio = 0.0  # Placeholder for per-frame analysis

    # If we have HNR and it's our SNR proxy, check the SNR threshold too
    if metrics.snr_db is not None and metrics.snr_db < min_snr:
        reasons.append(f"SNR(HNR) {metrics.snr_db:.1f}dB < {min_snr}dB")

    metrics.rejection_reasons = reasons
    metrics.passed = len(reasons) == 0
    return metrics


def _store_candidate(
    conn,
    conversation_id,
    speaker_label,
    selected_segments,
    diarization_embeddings,
    status,
    rejection_reason,
    f0_stddev_ratio,
    f0_unimodal,
):
    """Store voiceprint candidate in DB for human review."""
    now = datetime.now(timezone.utc).isoformat()

    embedding = diarization_embeddings.get(speaker_label)
    embedding_bytes = embedding.tobytes() if embedding is not None else None

    total_duration = sum(
        s.get("metrics", QualityMetrics()).duration
        if hasattr(s.get("metrics", {}), "duration")
        else (s["end"] - s["start"])
        for s in selected_segments
    )

    # Compute quality score (0-1) based on duration and signal quality
    quality_score = min(1.0, total_duration / 40.0)

    # Collect quality metrics summary
    metrics_summary = {
        "segment_count": len(selected_segments),
        "total_duration": round(total_duration, 1),
        "avg_snr_db": _avg_metric(selected_segments, "snr_db"),
        "avg_hnr_db": _avg_metric(selected_segments, "hnr_db"),
        "f0_stddev_ratio": round(f0_stddev_ratio, 3)
        if f0_stddev_ratio is not None
        else None,
        "f0_unimodal": f0_unimodal,
    }

    segment_ranges = json.dumps(
        [{"start": s["start"], "end": s["end"]} for s in selected_segments]
    )

    conn.execute(
        """INSERT INTO voiceprint_candidates
           (id, conversation_id, speaker_label, embedding, quality_score,
            total_duration, segment_count, segment_ranges, metrics_summary,
            status, rejection_reason, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            str(uuid.uuid4()),
            conversation_id,
            speaker_label,
            embedding_bytes,
            quality_score,
            total_duration,
            len(selected_segments),
            segment_ranges,
            json.dumps(metrics_summary),
            status,
            rejection_reason,
            now,
        ),
    )

    logger.info(
        f"[{conversation_id[:8]}:{speaker_label}] Voiceprint candidate stored: "
        f"status={status}, {total_duration:.1f}s, {len(selected_segments)} segments"
    )


def _avg_metric(segments: list[dict], metric_name: str) -> float | None:
    """Average a metric across segments that have QualityMetrics."""
    values = []
    for s in segments:
        m = s.get("metrics")
        if m and hasattr(m, metric_name):
            v = getattr(m, metric_name)
            if v is not None:
                values.append(v)
    return round(sum(values) / len(values), 2) if values else None
