"""Speaker resolver — voiceprint matching + auto-suggest.

Matches speaker embeddings against voice profiles keyed by tracker_person_id.
Person names are resolved by the frontend via the Tracker API — this module
only deals with IDs and embeddings.
"""

import logging
import uuid

import numpy as np

from db.connection import get_connection
from config import VOICEPRINT_AUTO_THRESHOLD, VOICEPRINT_SUGGEST_THRESHOLD

logger = logging.getLogger(__name__)


def auto_suggest_speakers(
    conn,
    conversation_id: str,
    speaker_embeddings: dict[str, np.ndarray],
) -> dict[str, dict]:
    """Auto-suggest speaker identities based on voiceprint similarity.

    Called after diarization. Creates speaker_mappings entries for
    high-confidence matches. Returns dict of label -> suggestion info.
    """
    if not speaker_embeddings:
        return {}

    # Load all voice profiles (keyed by tracker_person_id)
    profiles = conn.execute(
        """SELECT id as profile_id, tracker_person_id, embedding
           FROM speaker_voice_profiles"""
    ).fetchall()

    if not profiles:
        logger.info(f"[{conversation_id[:8]}] No voice profiles — skipping auto-suggest")
        return {}

    # Build profile embeddings
    profile_data = []
    for p in profiles:
        emb = np.frombuffer(p["embedding"], dtype=np.float32)
        if np.linalg.norm(emb) > 0:
            profile_data.append({
                "profile_id": p["profile_id"],
                "tracker_person_id": p["tracker_person_id"],
                "embedding": emb,
            })

    suggestions = {}
    for label, emb in speaker_embeddings.items():
        best_match = None
        best_sim = -1.0

        for profile in profile_data:
            sim = _cosine_similarity(emb, profile["embedding"])
            if sim > best_sim:
                best_sim = sim
                best_match = profile

        if best_match and best_sim >= VOICEPRINT_SUGGEST_THRESHOLD:
            method = "auto" if best_sim >= VOICEPRINT_AUTO_THRESHOLD else "suggested"
            confirmed = best_sim >= VOICEPRINT_AUTO_THRESHOLD

            # Create mapping entry
            conn.execute(
                """INSERT INTO speaker_mappings
                   (id, conversation_id, speaker_label, tracker_person_id,
                    confidence, method, confirmed)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (str(uuid.uuid4()), conversation_id, label,
                 best_match["tracker_person_id"], best_sim, method, confirmed),
            )

            # If auto-matched, also update transcript speaker_id
            if confirmed:
                conn.execute(
                    "UPDATE transcripts SET speaker_id = ? WHERE conversation_id = ? AND speaker_label = ?",
                    (best_match["tracker_person_id"], conversation_id, label),
                )

            suggestions[label] = {
                "tracker_person_id": best_match["tracker_person_id"],
                "confidence": best_sim,
                "method": method,
            }

            logger.info(
                f"[{conversation_id[:8]}] {label} -> {best_match['tracker_person_id'][:8]} "
                f"({method}, {best_sim:.2f})"
            )

    return suggestions


def get_suggestions_for_conversation(conversation_id: str) -> dict:
    """Get speaker suggestions for a conversation.

    Returns existing mappings + fresh voiceprint comparisons for unmapped speakers.
    Keyed by speaker_label for easy frontend consumption.
    """
    conn = get_connection()
    try:
        # Get existing mappings
        mappings = conn.execute(
            """SELECT speaker_label, tracker_person_id, confidence, method, confirmed
               FROM speaker_mappings
               WHERE conversation_id = ?
               ORDER BY speaker_label""",
            (conversation_id,),
        ).fetchall()

        # Group by label
        result = {}
        for m in mappings:
            label = m["speaker_label"]
            if label not in result:
                result[label] = []
            result[label].append({
                "tracker_person_id": m["tracker_person_id"],
                "confidence": m["confidence"],
                "method": m["method"],
                "confirmed": bool(m["confirmed"]),
            })

        # For unmapped speakers, try fresh comparison
        mapped_labels = {m["speaker_label"] for m in mappings}
        samples = conn.execute(
            "SELECT speaker_label, embedding FROM voice_samples WHERE source_conversation_id = ? AND embedding IS NOT NULL",
            (conversation_id,),
        ).fetchall()

        profiles = conn.execute(
            "SELECT tracker_person_id, embedding FROM speaker_voice_profiles"
        ).fetchall()

        profile_data = []
        for p in profiles:
            emb = np.frombuffer(p["embedding"], dtype=np.float32)
            if np.linalg.norm(emb) > 0:
                profile_data.append({
                    "tracker_person_id": p["tracker_person_id"],
                    "embedding": emb,
                })

        for sample in samples:
            label = sample["speaker_label"]
            if label in mapped_labels:
                continue

            emb = np.frombuffer(sample["embedding"], dtype=np.float32)
            if np.linalg.norm(emb) == 0:
                continue

            # Find top matches
            matches = []
            for profile in profile_data:
                sim = _cosine_similarity(emb, profile["embedding"])
                if sim >= VOICEPRINT_SUGGEST_THRESHOLD:
                    matches.append({
                        "tracker_person_id": profile["tracker_person_id"],
                        "confidence": sim,
                        "method": "suggested",
                        "confirmed": False,
                    })

            matches.sort(key=lambda x: x["confidence"], reverse=True)
            if matches:
                result[label] = matches[:3]  # top 3 suggestions per unmapped speaker

        return result
    finally:
        conn.close()


def promote_voice_sample(conn, conversation_id: str, speaker_label: str, tracker_person_id: str):
    """Promote a confirmed speaker embedding into a voice profile.

    Called after speaker assignment is confirmed in the review UI.
    Creates or updates the person's voice profile.
    """
    # Get the voice sample for this speaker
    sample = conn.execute(
        """SELECT embedding FROM voice_samples
           WHERE source_conversation_id = ? AND speaker_label = ?
           ORDER BY created_at LIMIT 1""",
        (conversation_id, speaker_label),
    ).fetchone()

    if not sample or not sample["embedding"]:
        logger.warning(f"No voice sample for {speaker_label} in {conversation_id[:8]}")
        return

    embedding = np.frombuffer(sample["embedding"], dtype=np.float32)
    if np.linalg.norm(embedding) == 0:
        return

    # Quality gate: minimum speech duration
    speech_dur = conn.execute(
        """SELECT SUM(end_time - start_time) as total
           FROM transcripts
           WHERE conversation_id = ? AND speaker_label = ?""",
        (conversation_id, speaker_label),
    ).fetchone()
    total_speech = speech_dur["total"] if speech_dur and speech_dur["total"] else 0

    if total_speech < 5.0:
        logger.info(f"Skipping voice profile for {speaker_label}: only {total_speech:.1f}s speech (min 5s)")
        return

    # Check if this person already has a profile
    existing = conn.execute(
        "SELECT id, embedding FROM speaker_voice_profiles WHERE tracker_person_id = ? ORDER BY created_at DESC LIMIT 1",
        (tracker_person_id,),
    ).fetchone()

    quality_score = min(1.0, total_speech / 30.0)  # 30s = max quality

    if existing:
        # Update with running average
        old_emb = np.frombuffer(existing["embedding"], dtype=np.float32)
        if old_emb.shape == embedding.shape:
            new_emb = 0.7 * old_emb + 0.3 * embedding
            new_emb = new_emb / np.linalg.norm(new_emb)
            conn.execute(
                "UPDATE speaker_voice_profiles SET embedding = ?, quality_score = ?, source_conversation_id = ? WHERE id = ?",
                (new_emb.tobytes(), quality_score, conversation_id, existing["id"]),
            )
            logger.info(f"Updated voice profile for person {tracker_person_id[:8]}")
        else:
            conn.execute(
                "UPDATE speaker_voice_profiles SET embedding = ?, quality_score = ?, source_conversation_id = ? WHERE id = ?",
                (embedding.tobytes(), quality_score, conversation_id, existing["id"]),
            )
    else:
        # Create new profile
        conn.execute(
            """INSERT INTO speaker_voice_profiles (id, tracker_person_id, embedding, source_conversation_id, quality_score)
               VALUES (?, ?, ?, ?, ?)""",
            (str(uuid.uuid4()), tracker_person_id, embedding.tobytes(), conversation_id, quality_score),
        )
        logger.info(f"Created voice profile for person {tracker_person_id[:8]}")


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Compute cosine similarity between two vectors."""
    if a.shape != b.shape:
        return 0.0
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    result = float(np.dot(a, b) / (norm_a * norm_b))
    if np.isnan(result) or np.isinf(result):
        return 0.0
    return result
