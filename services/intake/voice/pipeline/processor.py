"""Pipeline orchestrator -- stages 0-7.

Stage 0: Audio prep (ffmpeg -> 16kHz mono WAV)
Stage 1: Transcription (faster-whisper + Silero VAD)
Stage 2: Diarization (pyannote 3.1 on MPS)
Stage 3: Forced alignment + speaker assignment (wav2vec2 via whisperx)
Stage 4: Store transcript + voice samples
Stage 5: Vocal analysis (Parselmouth + librosa, optional)
Stage 6: Voiceprint quality gate (validates before commitment)
Stage 7: Auto-advance check (confidence-gated, optional)

Sets status to awaiting_speaker_review (or speakers_confirmed if auto-advance).
"""

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

from db.connection import get_connection
from .transcriber import transcribe
from .diarizer import diarize, DiarizationResult, SpeakerSegment
from .aligner import align, AlignedTranscript, AlignedSegment, AlignedWord
from .audio_prep import prepare_audio

logger = logging.getLogger(__name__)


def process_conversation(conversation_id: str) -> bool:
    """Process a conversation through the full pipeline."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM conversations WHERE id = ?", (conversation_id,)
        ).fetchone()
        if not row:
            logger.error(f"Conversation not found: {conversation_id}")
            return False

        audio_row = conn.execute(
            "SELECT * FROM audio_files WHERE conversation_id = ?", (conversation_id,)
        ).fetchone()
        if not audio_row:
            logger.error(f"No audio file for conversation: {conversation_id}")
            return False

        audio_path = Path(audio_row["file_path"])
        if not audio_path.exists():
            logger.error(f"Audio file not found: {audio_path}")
            _update_status(conn, conversation_id, "error")
            return False

        _update_status(conn, conversation_id, "transcribing")

        # Check for existing transcripts (skip if reprocessing)
        existing_count = conn.execute(
            "SELECT COUNT(*) as cnt FROM transcripts WHERE conversation_id = ?",
            (conversation_id,),
        ).fetchone()["cnt"]

        if existing_count > 0:
            logger.info(f"[{conversation_id[:8]}] Reusing {existing_count} existing transcript segments")
            _update_status(conn, conversation_id, "awaiting_speaker_review")
            conn.commit()
            return True

        # Stage 0: Audio preprocessing
        try:
            cache_dir = audio_path.parent / ".prepared"
            prepared_path = prepare_audio(audio_path, cache_dir=cache_dir)
        except Exception as e:
            logger.warning(f"Audio prep failed ({type(e).__name__}: {e}) -- using original")
            prepared_path = audio_path

        # Stage 1: Transcription (faster-whisper + Silero VAD)
        logger.info(f"[{conversation_id[:8]}] Stage 1: Transcribing (faster-whisper)...")
        transcription = transcribe(prepared_path)

        conn.execute(
            "UPDATE conversations SET duration_seconds = ? WHERE id = ?",
            (transcription.duration, conversation_id),
        )

        # Stage 2: Diarization (pyannote 3.1 on MPS)
        logger.info(f"[{conversation_id[:8]}] Stage 2: Diarizing (pyannote 3.1)...")
        try:
            diarization = diarize(prepared_path)
        except Exception as e:
            logger.warning(f"[{conversation_id[:8]}] Diarization failed -- single-speaker fallback")
            diarization = _single_speaker_fallback(transcription.duration)

        # Stage 3: Forced alignment + speaker assignment (wav2vec2)
        logger.info(f"[{conversation_id[:8]}] Stage 3: Aligning (wav2vec2)...")
        aligned = align(transcription, diarization, prepared_path)

        # Stage 4: Store transcript + voice samples
        logger.info(f"[{conversation_id[:8]}] Stage 4: Storing {len(aligned.segments)} segments...")
        _store_transcript(conn, conversation_id, aligned)
        _store_voice_samples(conn, conversation_id, diarization)

        # Run auto-suggest from voiceprints (existing profiles only)
        suggestions = {}
        try:
            from voice.speakers.resolver import auto_suggest_speakers
            suggestions = auto_suggest_speakers(conn, conversation_id, diarization.embeddings)
        except Exception as e:
            logger.warning(f"[{conversation_id[:8]}] Auto-suggest failed (non-fatal): {e}")

        # Stage 5: Vocal analysis (optional)
        vocal_data = {}  # speaker_label -> {features, segments_with_features}
        from config import ENABLE_VOCAL_ANALYSIS
        if ENABLE_VOCAL_ANALYSIS:
            vocal_data = _run_vocal_analysis(
                conn, conversation_id, aligned, diarization, prepared_path, suggestions
            )

        # Stage 6: Voiceprint quality gate
        # For speakers WITHOUT an existing voiceprint profile, run quality gate
        _run_voiceprint_quality_gate(
            conn, conversation_id, aligned, diarization, vocal_data, prepared_path, suggestions
        )

        # Stage 7: Auto-advance check (optional)
        from config import ENABLE_AUTO_ADVANCE
        if ENABLE_AUTO_ADVANCE and _all_speakers_resolved(conn, conversation_id):
            _update_status(conn, conversation_id, "speakers_confirmed")
            conn.execute(
                "UPDATE conversations SET speakers_confirmed = 1 WHERE id = ?",
                (conversation_id,),
            )
            _log_auto_advance(conn, conversation_id)
            logger.info(f"[{conversation_id[:8]}] Auto-advanced: all speakers resolved at >=0.85")
        else:
            _update_status(conn, conversation_id, "awaiting_speaker_review")

        conn.commit()

        logger.info(
            f"[{conversation_id[:8]}] Pipeline complete: "
            f"{len(aligned.speakers)} speakers, "
            f"{len(aligned.segments)} segments, "
            f"{transcription.duration:.0f}s"
        )
        return True

    except Exception:
        conn.rollback()
        logger.exception(f"Pipeline failed for conversation {conversation_id}")
        try:
            _update_status(conn, conversation_id, "error")
            conn.commit()
        except Exception:
            pass
        return False
    finally:
        conn.close()


def process_pending():
    """Process all pending conversations."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT id FROM conversations WHERE processing_status = 'pending' ORDER BY created_at"
        ).fetchall()
    finally:
        conn.close()

    if not rows:
        logger.info("No pending conversations to process")
        return

    logger.info(f"Processing {len(rows)} pending conversations...")
    for row in rows:
        process_conversation(row["id"])


def _run_vocal_analysis(conn, conversation_id, aligned, diarization, audio_path, suggestions):
    """Stage 5: Extract vocal features for each speaker.

    Returns dict of speaker_label -> {features: dict, segments: list[dict with features]}
    """
    from config import VOCAL_MIN_SEGMENT_SECONDS

    logger.info(f"[{conversation_id[:8]}] Stage 5: Vocal analysis...")
    vocal_data = {}

    try:
        from voice.analysis.vocal_analyzer import extract_vocal_features, aggregate_speaker_features
        from voice.analysis.baseline_tracker import update_baseline, compare_to_baseline

        # Group segments by speaker
        speaker_segments = {}
        for seg in aligned.segments:
            if seg.speaker not in speaker_segments:
                speaker_segments[seg.speaker] = []
            speaker_segments[seg.speaker].append({"start": seg.start, "end": seg.end})

        for speaker_label, segs in speaker_segments.items():
            # Extract per-segment features (needed for quality gate)
            segments_with_features = []
            for seg in segs:
                features = extract_vocal_features(audio_path, seg["start"], seg["end"])
                segments_with_features.append({
                    "start": seg["start"],
                    "end": seg["end"],
                    "features": features,
                })

            # Aggregate for storage
            agg_features = aggregate_speaker_features(audio_path, segs, VOCAL_MIN_SEGMENT_SECONDS)
            if agg_features:
                _store_vocal_features(conn, conversation_id, speaker_label, agg_features)

                # Baseline update for resolved speakers
                suggestion = suggestions.get(speaker_label)
                deviations = {}
                if suggestion and suggestion.get("method") == "auto":
                    person_id = suggestion["tracker_person_id"]
                    update_baseline(conn, person_id, agg_features)
                    deviations = compare_to_baseline(conn, person_id, agg_features)

            vocal_data[speaker_label] = {
                "features": agg_features or {},
                "segments": segments_with_features,
                "deviations": {},
            }

        logger.info(f"[{conversation_id[:8]}] Vocal analysis complete: {len(vocal_data)} speakers")
    except Exception as e:
        logger.warning(f"[{conversation_id[:8]}] Vocal analysis failed (non-fatal): {e}")

    return vocal_data


def _run_voiceprint_quality_gate(
    conn, conversation_id, aligned, diarization, vocal_data, audio_path, suggestions
):
    """Stage 6: Run voiceprint quality gate for speakers without existing profiles."""
    logger.info(f"[{conversation_id[:8]}] Stage 6: Voiceprint quality gate...")

    try:
        from voice.speakers.quality_gate import run_quality_gate

        for speaker_label in aligned.speakers:
            # Skip speakers that already have a voiceprint profile
            suggestion = suggestions.get(speaker_label)
            if suggestion and suggestion.get("method") == "auto":
                continue  # Already has a profile, matched at >=0.85

            # Get segments with vocal features for this speaker
            speaker_vocal = vocal_data.get(speaker_label, {})
            segments = speaker_vocal.get("segments", [])

            if not segments:
                # Fallback: build segment list from aligned transcript
                segments = [
                    {"start": seg.start, "end": seg.end, "features": {}}
                    for seg in aligned.segments
                    if seg.speaker == speaker_label
                ]

            result = run_quality_gate(
                conn, conversation_id, speaker_label,
                segments, audio_path, diarization.embeddings,
            )

            logger.info(
                f"[{conversation_id[:8]}] Quality gate for {speaker_label}: "
                f"status={result.status}, {result.total_clean_duration:.1f}s clean, "
                f"{result.segments_passed}/{result.total_candidate_segments} segments"
            )

    except Exception as e:
        logger.warning(f"[{conversation_id[:8]}] Voiceprint quality gate failed (non-fatal): {e}")


def _all_speakers_resolved(conn, conversation_id: str) -> bool:
    """Check if all speakers are auto-resolved at >=0.85."""
    from config import VOICEPRINT_AUTO_THRESHOLD

    speaker_rows = conn.execute(
        "SELECT DISTINCT speaker_label FROM transcripts WHERE conversation_id = ?",
        (conversation_id,),
    ).fetchall()
    speaker_labels = {r["speaker_label"] for r in speaker_rows}

    if not speaker_labels:
        return False

    for label in speaker_labels:
        mapping = conn.execute(
            """SELECT confidence, method FROM speaker_mappings
               WHERE conversation_id = ? AND speaker_label = ? AND confirmed = 1
               ORDER BY confidence DESC LIMIT 1""",
            (conversation_id, label),
        ).fetchone()

        if not mapping or mapping["confidence"] < VOICEPRINT_AUTO_THRESHOLD:
            return False

    return True


def _log_auto_advance(conn, conversation_id: str):
    """Log auto-advance decisions to audit table."""
    try:
        from .audit import log_auto_advance

        mappings = conn.execute(
            """SELECT speaker_label, tracker_person_id, confidence, method
               FROM speaker_mappings
               WHERE conversation_id = ? AND confirmed = 1""",
            (conversation_id,),
        ).fetchall()

        decisions = [
            {
                "speaker_label": m["speaker_label"],
                "tracker_person_id": m["tracker_person_id"],
                "confidence": m["confidence"],
                "method": m["method"],
            }
            for m in mappings
        ]
        log_auto_advance(conn, conversation_id, decisions)
    except Exception as e:
        logger.warning(f"[{conversation_id[:8]}] Audit log failed (non-fatal): {e}")


def _update_status(conn, conversation_id: str, status: str):
    """Update conversation processing status."""
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "UPDATE conversations SET processing_status = ?, updated_at = ? WHERE id = ?",
        (status, now, conversation_id),
    )


def _store_transcript(conn, conversation_id: str, aligned: AlignedTranscript):
    """Write aligned segments to transcripts table."""
    for seg in aligned.segments:
        word_timestamps = json.dumps([
            {"word": w.word, "start": w.start, "end": w.end, "probability": w.probability}
            for w in seg.words
        ])
        conn.execute(
            """INSERT INTO transcripts (id, conversation_id, speaker_label, start_time, end_time, text, word_timestamps)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (str(uuid.uuid4()), conversation_id, seg.speaker,
             seg.start, seg.end, seg.text, word_timestamps),
        )


def _store_voice_samples(conn, conversation_id: str, diarization):
    """Write speaker embeddings to voice_samples table."""
    for speaker_label, embedding in diarization.embeddings.items():
        conn.execute(
            """INSERT INTO voice_samples (id, source_conversation_id, speaker_label, embedding)
               VALUES (?, ?, ?, ?)""",
            (str(uuid.uuid4()), conversation_id, speaker_label, embedding.tobytes()),
        )


def _store_vocal_features(conn, conversation_id: str, speaker_label: str, features: dict):
    """Store aggregated vocal features for a speaker."""
    conn.execute(
        """INSERT INTO vocal_features (
            id, conversation_id, speaker_label,
            pitch_mean, pitch_std, pitch_min, pitch_max,
            jitter, shimmer, hnr, intensity_mean,
            f1_mean, f2_mean, f3_mean,
            mfcc_means, rms_mean, spectral_centroid, zcr_mean, spectral_rolloff,
            speaking_rate_wpm
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            str(uuid.uuid4()), conversation_id, speaker_label,
            features.get("pitch_mean"), features.get("pitch_std"),
            features.get("pitch_min"), features.get("pitch_max"),
            features.get("jitter"), features.get("shimmer"),
            features.get("hnr"), features.get("intensity_mean"),
            features.get("f1_mean"), features.get("f2_mean"), features.get("f3_mean"),
            features.get("mfcc_means"), features.get("rms_mean"),
            features.get("spectral_centroid"), features.get("zcr_mean"),
            features.get("spectral_rolloff"), features.get("speaking_rate_wpm"),
        ),
    )


def _single_speaker_fallback(duration: float) -> DiarizationResult:
    """Create a minimal diarization result with a single speaker."""
    return DiarizationResult(
        segments=[SpeakerSegment(speaker="SPEAKER_00", start=0.0, end=duration)],
        embeddings={},
        num_speakers=1,
    )


def _reconstruct_from_db(conn, conversation_id: str):
    """Reconstruct AlignedTranscript from stored DB transcripts."""
    rows = conn.execute(
        """SELECT speaker_label, speaker_id, start_time, end_time, text, word_timestamps
           FROM transcripts WHERE conversation_id = ?
           ORDER BY start_time""",
        (conversation_id,),
    ).fetchall()

    if not rows:
        return None

    segments = []
    speakers_set = set()
    max_end = 0.0

    for row in rows:
        speaker = row["speaker_label"] or "SPEAKER_00"
        speakers_set.add(speaker)

        words = []
        if row["word_timestamps"]:
            try:
                word_data = json.loads(row["word_timestamps"])
                for w in word_data:
                    words.append(AlignedWord(
                        word=w["word"],
                        start=w["start"],
                        end=w["end"],
                        speaker=speaker,
                        probability=w.get("probability", 1.0),
                    ))
            except (json.JSONDecodeError, KeyError):
                pass

        start = float(row["start_time"] or 0)
        end = float(row["end_time"] or 0)
        max_end = max(max_end, end)

        segments.append(AlignedSegment(
            speaker=speaker, start=start, end=end,
            text=row["text"] or "", words=words,
        ))

    dur_row = conn.execute(
        "SELECT duration_seconds FROM conversations WHERE id = ?",
        (conversation_id,),
    ).fetchone()
    duration = float(dur_row["duration_seconds"]) if dur_row and dur_row["duration_seconds"] else max_end

    return AlignedTranscript(
        segments=segments,
        speakers=sorted(speakers_set),
        duration=duration,
    )


def _load_stored_embeddings(conn, conversation_id: str) -> dict:
    """Load speaker embeddings from voice_samples table."""
    import numpy as np
    rows = conn.execute(
        "SELECT speaker_label, embedding FROM voice_samples WHERE source_conversation_id = ? AND embedding IS NOT NULL",
        (conversation_id,),
    ).fetchall()
    embeddings = {}
    for row in rows:
        emb = np.frombuffer(row["embedding"], dtype=np.float32)
        embeddings[row["speaker_label"]] = emb
    return embeddings
