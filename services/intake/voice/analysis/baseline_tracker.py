"""Vocal baseline tracker — EMA-based deviation detection.

Maintains per-person vocal baselines using exponential moving average.
Flags significant (>50%) and moderate (>20%) deviations from baseline.
"""

import logging
import uuid
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

BASELINE_FIELDS = [
    "pitch_mean",
    "pitch_std",
    "jitter",
    "shimmer",
    "hnr",
    "speaking_rate_wpm",
    "spectral_centroid",
    "rms_mean",
    "f1_mean",
    "f2_mean",
    "f3_mean",
]


def update_baseline(conn, tracker_person_id: str, features: dict):
    """Update vocal baseline for a person using EMA.

    EMA: new_baseline = alpha * new + (1 - alpha) * old
    """
    from config import BASELINE_EMA_ALPHA

    alpha = BASELINE_EMA_ALPHA

    row = conn.execute(
        "SELECT * FROM vocal_baselines WHERE tracker_person_id = ?",
        (tracker_person_id,),
    ).fetchone()

    now = datetime.now(timezone.utc).isoformat()

    if row is None:
        # First sample — initialize directly
        conn.execute(
            """INSERT INTO vocal_baselines (
                id, tracker_person_id,
                pitch_mean, pitch_std, jitter, shimmer, hnr,
                speaking_rate_wpm, spectral_centroid, rms_mean,
                f1_mean, f2_mean, f3_mean,
                sample_count, last_updated
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)""",
            (
                str(uuid.uuid4()),
                tracker_person_id,
                features.get("pitch_mean"),
                features.get("pitch_std"),
                features.get("jitter"),
                features.get("shimmer"),
                features.get("hnr"),
                features.get("speaking_rate_wpm"),
                features.get("spectral_centroid"),
                features.get("rms_mean"),
                features.get("f1_mean"),
                features.get("f2_mean"),
                features.get("f3_mean"),
                now,
            ),
        )
    else:
        updates = {}
        for field in BASELINE_FIELDS:
            new_val = features.get(field)
            old_val = row[field]
            if new_val is not None and old_val is not None:
                updates[field] = alpha * new_val + (1 - alpha) * old_val
            elif new_val is not None:
                updates[field] = new_val

        if updates:
            set_clause = ", ".join(f"{k} = ?" for k in updates)
            values = list(updates.values())
            conn.execute(
                f"UPDATE vocal_baselines SET {set_clause}, "
                "sample_count = sample_count + 1, last_updated = ? "
                "WHERE tracker_person_id = ?",
                values + [now, tracker_person_id],
            )


def compare_to_baseline(conn, tracker_person_id: str, features: dict) -> dict:
    """Compare current features to baseline.

    Returns:
        Dict of field -> {"level": "SIGNIFICANT"|"MODERATE"|"normal", "pct": float}
        Empty dict if insufficient baseline data.
    """
    from config import BASELINE_WARN_THRESHOLD, BASELINE_ALERT_THRESHOLD

    row = conn.execute(
        "SELECT * FROM vocal_baselines WHERE tracker_person_id = ?",
        (tracker_person_id,),
    ).fetchone()

    if row is None or row["sample_count"] < 3:
        return {}

    comparison_fields = [
        "pitch_mean",
        "jitter",
        "shimmer",
        "hnr",
        "speaking_rate_wpm",
        "spectral_centroid",
        "rms_mean",
    ]

    deviations = {}
    for field in comparison_fields:
        new_val = features.get(field)
        baseline_val = row[field]
        if new_val is not None and baseline_val is not None and baseline_val != 0:
            pct_change = abs(new_val - baseline_val) / abs(baseline_val)
            if pct_change >= BASELINE_ALERT_THRESHOLD:
                level = "SIGNIFICANT"
            elif pct_change >= BASELINE_WARN_THRESHOLD:
                level = "MODERATE"
            else:
                level = "normal"
            deviations[field] = {"level": level, "pct": round(pct_change, 3)}

    return deviations
