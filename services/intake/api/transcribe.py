"""Stateless transcription endpoint for the AI service.

Receives an audio file, runs the full audio pipeline
(prep → transcribe → diarize → align), and returns the aligned
transcript as JSON. Does NOT create any intake DB records.

This endpoint exists to let the containerized AI service (port 8006)
delegate GPU-bound transcription to the native intake service (port 8005)
which has access to Whisper + pyannote on the Mac Mini's GPU.

Response shape:
{
    "segments": [
        {
            "speaker": "SPEAKER_00",
            "start": 0.0,
            "end": 5.2,
            "text": "Hello everyone.",
            "words": [
                {"word": "Hello", "start": 0.0, "end": 0.3, "probability": 0.95},
                ...
            ]
        },
        ...
    ],
    "speakers": ["SPEAKER_00", "SPEAKER_01"],
    "duration": 125.3,
    "language": "en",
    "num_speakers": 2,
    "embeddings": {
        "SPEAKER_00": "<base64-encoded float32 array>",
        "SPEAKER_01": "<base64-encoded float32 array>"
    }
}
"""
import base64
import logging
import os
import shutil
import tempfile
import time
import uuid
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from config import SUPPORTED_FORMATS

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/transcribe", tags=["transcribe"])


@router.post("")
async def transcribe_audio(
    audio: UploadFile = File(...),
    communication_id: str = Form(None),
):
    """Transcribe an audio file and return the aligned transcript.

    Stateless: no intake DB records are created.
    The AI service calls this to delegate GPU-bound transcription.

    Args:
        audio: Audio file (wav, flac, mp3, m4a, ogg, opus).
        communication_id: Optional correlation ID for logging.

    Returns:
        Aligned transcript with speaker labels, timestamps, words, embeddings.
    """
    correlation = (communication_id or "unknown")[:8]
    filename = audio.filename or "upload.wav"
    suffix = Path(filename).suffix.lower()

    # Validate format
    if suffix not in SUPPORTED_FORMATS and suffix != ".wav":
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported audio format: {suffix}. Accepted: {sorted(SUPPORTED_FORMATS)}",
        )

    # Read file content
    content = await audio.read()
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="Empty audio file")
    if len(content) > 200 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File too large (max 200MB)")

    logger.info("[%s] Transcribe request: %s (%.1f MB)", correlation, filename, len(content) / 1024 / 1024)

    # Save to temp file
    work_dir = Path(tempfile.mkdtemp(prefix="ai_transcribe_"))
    input_path = work_dir / filename

    try:
        input_path.write_bytes(content)

        # Stage 1: Audio preprocessing
        t0 = time.time()
        from voice.pipeline.audio_prep import prepare_audio
        try:
            prepared_path = prepare_audio(input_path, cache_dir=work_dir)
        except Exception as e:
            logger.warning("[%s] Audio prep failed (%s) — using original", correlation, e)
            prepared_path = input_path
        prep_time = time.time() - t0

        # Stage 2: Transcription (Whisper)
        t0 = time.time()
        from voice.pipeline.transcriber import transcribe
        transcription = transcribe(prepared_path)
        transcribe_time = time.time() - t0

        # Stage 3: Diarization (pyannote)
        t0 = time.time()
        from voice.pipeline.diarizer import diarize, DiarizationResult, SpeakerSegment
        try:
            diarization = diarize(prepared_path)
        except Exception as e:
            logger.warning("[%s] Diarization failed — single-speaker fallback: %s", correlation, e)
            duration = transcription.duration
            diarization = DiarizationResult(
                segments=[SpeakerSegment(speaker="SPEAKER_00", start=0.0, end=duration)],
                embeddings={},
                num_speakers=1,
            )
        diarize_time = time.time() - t0

        # Stage 4: Alignment
        t0 = time.time()
        from voice.pipeline.aligner import align
        aligned = align(transcription, diarization)
        align_time = time.time() - t0

        # Build response
        segments = []
        for seg in aligned.segments:
            words = []
            for w in seg.words:
                words.append({
                    "word": w.word,
                    "start": round(w.start, 3),
                    "end": round(w.end, 3),
                    "probability": round(w.probability, 4),
                })
            segments.append({
                "speaker": seg.speaker,
                "start": round(seg.start, 3),
                "end": round(seg.end, 3),
                "text": seg.text,
                "words": words,
            })

        # Encode embeddings as base64
        embeddings = {}
        for label, emb in diarization.embeddings.items():
            embeddings[label] = base64.b64encode(emb.tobytes()).decode("ascii")

        total_time = prep_time + transcribe_time + diarize_time + align_time

        logger.info(
            "[%s] Transcription complete: %d segments, %d speakers, %.1fs duration "
            "(prep=%.1fs, transcribe=%.1fs, diarize=%.1fs, align=%.1fs, total=%.1fs)",
            correlation, len(segments), len(aligned.speakers), aligned.duration,
            prep_time, transcribe_time, diarize_time, align_time, total_time,
        )

        return {
            "segments": segments,
            "speakers": aligned.speakers,
            "duration": round(aligned.duration, 2),
            "language": transcription.language,
            "num_speakers": len(aligned.speakers),
            "embeddings": embeddings,
            "timing": {
                "prep_seconds": round(prep_time, 2),
                "transcribe_seconds": round(transcribe_time, 2),
                "diarize_seconds": round(diarize_time, 2),
                "align_seconds": round(align_time, 2),
                "total_seconds": round(total_time, 2),
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("[%s] Transcription failed: %s", correlation, e)
        raise HTTPException(
            status_code=500,
            detail={
                "error_type": "transcription_error",
                "message": str(e),
                "communication_id": communication_id,
            },
        )
    finally:
        # Clean up temp files
        try:
            shutil.rmtree(work_dir, ignore_errors=True)
        except Exception:
            pass
