"""
Voiceprint matcher — cosine similarity matching against voice profile library.

Conservative, human-in-the-loop design:
  - No auto-confirm at any threshold
  - Returns ranked candidates with confidence labels
  - Logs every match attempt for auditability

Embedding format: 192-dim float32 from pyannote speaker-diarization-3.1
Similarity metric: cosine similarity (standard for speaker embeddings)
"""
import json
import logging
import struct
import uuid
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Thresholds — conservative, precision-first
# ---------------------------------------------------------------------------
SUGGEST_THRESHOLD = 0.60       # Below this = no candidate shown
LOW_CONFIDENCE_CEIL = 0.70     # [0.60, 0.70) = low confidence
MEDIUM_CONFIDENCE_CEIL = 0.80  # [0.70, 0.80) = medium confidence
                               # >= 0.80       = high confidence

# Maximum candidates to return per speaker
MAX_CANDIDATES = 3

EMBEDDING_DIM = 192
FLOAT32_SIZE = 4
EXPECTED_BLOB_SIZE = EMBEDDING_DIM * FLOAT32_SIZE  # 768 bytes


# ---------------------------------------------------------------------------
# Pure-Python cosine similarity (no numpy dependency required)
# ---------------------------------------------------------------------------

def _unpack_embedding(blob: bytes) -> Optional[list[float]]:
    """Unpack a BLOB into a list of float32 values. Returns None if invalid."""
    if not blob or len(blob) != EXPECTED_BLOB_SIZE:
        return None
    return list(struct.unpack(f"<{EMBEDDING_DIM}f", blob))


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Cosine similarity between two float vectors. Safe against zero-norm."""
    if len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(x * x for x in b) ** 0.5
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    result = dot / (norm_a * norm_b)
    # Clamp to [-1, 1] for floating point safety
    return max(-1.0, min(1.0, result))


def _label_confidence(score: float) -> str:
    """Map similarity score to human-readable confidence label."""
    if score < SUGGEST_THRESHOLD:
        return "no_candidate"
    elif score < LOW_CONFIDENCE_CEIL:
        return "low_confidence"
    elif score < MEDIUM_CONFIDENCE_CEIL:
        return "medium_confidence"
    else:
        return "high_confidence"


# ---------------------------------------------------------------------------
# Main matching function
# ---------------------------------------------------------------------------

def match_speaker(
    db,
    communication_id: str,
    speaker_label: str,
    embedding_blob: bytes,
) -> dict:
    """Match a speaker embedding against all active voice profiles.

    Returns:
        {
            "speaker_label": "SPEAKER_00",
            "outcome": "high_confidence" | "medium_confidence" | "low_confidence" | "no_candidate" | "no_profiles",
            "candidates": [
                {"tracker_person_id": "...", "score": 0.87, "confidence_label": "high_confidence"},
                ...
            ],
            "profiles_compared": 5,
            "match_log_id": "uuid"
        }
    """
    sample_emb = _unpack_embedding(embedding_blob)
    if sample_emb is None:
        logger.warning("[%s] Invalid embedding for %s — skipping match",
                       communication_id[:8], speaker_label)
        return {
            "speaker_label": speaker_label,
            "outcome": "no_candidate",
            "candidates": [],
            "profiles_compared": 0,
            "match_log_id": None,
        }

    # Get the voice_sample id for audit logging
    sample_row = db.execute(
        "SELECT id FROM voice_samples WHERE communication_id = ? AND speaker_label = ? LIMIT 1",
        (communication_id, speaker_label),
    ).fetchone()
    sample_id = sample_row["id"] if sample_row else None

    # Load all active voice profiles
    profiles = db.execute(
        "SELECT id, tracker_person_id, embedding FROM speaker_voice_profiles WHERE status = 'active'"
    ).fetchall()

    if not profiles:
        # Log the attempt even with no profiles
        log_id = _log_match(db, communication_id, speaker_label, sample_id,
                            profiles_compared=0, candidates=[], outcome="no_profiles")
        return {
            "speaker_label": speaker_label,
            "outcome": "no_profiles",
            "candidates": [],
            "profiles_compared": 0,
            "match_log_id": log_id,
        }

    # Compare against each profile
    scored = []
    for profile in profiles:
        prof_emb = _unpack_embedding(profile["embedding"])
        if prof_emb is None:
            continue
        sim = _cosine_similarity(sample_emb, prof_emb)
        if sim >= SUGGEST_THRESHOLD:
            scored.append({
                "tracker_person_id": profile["tracker_person_id"],
                "score": round(sim, 4),
                "confidence_label": _label_confidence(sim),
            })

    # Sort by score descending, take top N
    scored.sort(key=lambda x: x["score"], reverse=True)
    candidates = scored[:MAX_CANDIDATES]

    # Determine overall outcome
    if candidates:
        outcome = candidates[0]["confidence_label"]
    else:
        outcome = "no_candidate"

    # Audit log
    log_id = _log_match(
        db, communication_id, speaker_label, sample_id,
        profiles_compared=len(profiles),
        candidates=candidates,
        outcome=outcome,
    )

    return {
        "speaker_label": speaker_label,
        "outcome": outcome,
        "candidates": candidates,
        "profiles_compared": len(profiles),
        "match_log_id": log_id,
    }


def match_all_speakers(db, communication_id: str) -> dict[str, dict]:
    """Match all speakers in a communication against the voice profile library.

    Returns dict keyed by speaker_label.
    """
    # Get all voice samples for this communication
    samples = db.execute(
        "SELECT speaker_label, embedding FROM voice_samples WHERE communication_id = ? AND embedding IS NOT NULL",
        (communication_id,),
    ).fetchall()

    results = {}
    for sample in samples:
        label = sample["speaker_label"]
        if label in results:
            continue  # one match per speaker label
        results[label] = match_speaker(
            db, communication_id, label, sample["embedding"]
        )

    return results


# ---------------------------------------------------------------------------
# Audit logging
# ---------------------------------------------------------------------------

def _log_match(
    db,
    communication_id: str,
    speaker_label: str,
    sample_embedding_id: Optional[str],
    profiles_compared: int,
    candidates: list[dict],
    outcome: str,
) -> str:
    """Write a voiceprint_match_log entry. Returns the log row id."""
    log_id = str(uuid.uuid4())
    top_person = candidates[0]["tracker_person_id"] if candidates else None
    top_score = candidates[0]["score"] if candidates else None

    db.execute("""
        INSERT INTO voiceprint_match_log
            (id, communication_id, speaker_label, sample_embedding_id,
             profiles_compared, top_candidate_person_id, top_candidate_score,
             candidate_list, threshold_used, outcome)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        log_id, communication_id, speaker_label, sample_embedding_id,
        profiles_compared, top_person, top_score,
        json.dumps(candidates) if candidates else None,
        SUGGEST_THRESHOLD, outcome,
    ))
    db.commit()
    return log_id
