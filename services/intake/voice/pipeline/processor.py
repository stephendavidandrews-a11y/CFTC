"""Pipeline orchestrator — stages 0-4 only.

audio prep -> transcribe -> diarize -> align -> store transcript + voice samples.
Sets status to awaiting_speaker_review when done.
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
    """Process a conversation through stages 0-4: audio to transcript."""
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

        # Check for existing transcripts (skip stages 0-4 if reprocessing)
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
            logger.warning(f"Audio prep failed ({type(e).__name__}: {e}) — using original")
            prepared_path = audio_path

        # Stage 1: Transcription
        logger.info(f"[{conversation_id[:8]}] Stage 1: Transcribing...")
        transcription = transcribe(audio_path)

        conn.execute(
            "UPDATE conversations SET duration_seconds = ? WHERE id = ?",
            (transcription.duration, conversation_id),
        )

        # Stage 2: Diarization
        logger.info(f"[{conversation_id[:8]}] Stage 2: Diarizing...")
        try:
            diarization = diarize(prepared_path)
        except Exception as e:
            logger.warning(f"[{conversation_id[:8]}] Diarization failed — single-speaker fallback")
            diarization = _single_speaker_fallback(transcription.duration)

        # Stage 3: Alignment
        logger.info(f"[{conversation_id[:8]}] Stage 3: Aligning...")
        aligned = align(transcription, diarization)

        # Stage 4: Store transcript + voice samples
        logger.info(f"[{conversation_id[:8]}] Storing {len(aligned.segments)} segments...")
        _store_transcript(conn, conversation_id, aligned)
        _store_voice_samples(conn, conversation_id, diarization)

        # Run auto-suggest from voiceprints
        try:
            from voice.speakers.resolver import auto_suggest_speakers
            auto_suggest_speakers(conn, conversation_id, diarization.embeddings)
        except Exception as e:
            logger.warning(f"[{conversation_id[:8]}] Auto-suggest failed (non-fatal): {e}")

        _update_status(conn, conversation_id, "awaiting_speaker_review")
        conn.commit()

        logger.info(
            f"[{conversation_id[:8]}] Pipeline complete: "
            f"{len(aligned.speakers)} speakers, "
            f"{len(aligned.segments)} segments, "
            f"{transcription.duration:.0f}s — awaiting speaker review"
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
