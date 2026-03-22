"""Stateless transcription endpoint for the AI service.

Receives an audio file, runs the full audio pipeline
(prep -> transcribe -> diarize -> align), and returns the aligned
transcript as JSON. Does NOT create any intake DB records.

This endpoint exists to let the containerized AI service (port 8006)
delegate GPU-bound transcription to the native intake service (port 8005)
which has access to faster-whisper + pyannote on the Mac Mini.

Response shape:
{
    "segments": [...],
    "speakers": ["SPEAKER_00", "SPEAKER_01"],
    "duration": 125.3,
    "language": "en",
    "num_speakers": 2,
    "embeddings": {"SPEAKER_00": "<base64>", ...},
    "timing": {...},
    "vocal_features": {...},       # optional, if ENABLE_VOCAL_ANALYSIS
    "baseline_deviations": {...}   # optional, if ENABLE_VOCAL_ANALYSIS
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
    """
    correlation = (communication_id or "unknown")[:8]
    filename = audio.filename or "upload.wav"
    suffix = Path(filename).suffix.lower()

    if suffix not in SUPPORTED_FORMATS and suffix != ".wav":
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported audio format: {suffix}. Accepted: {sorted(SUPPORTED_FORMATS)}",
        )

    content = await audio.read()
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="Empty audio file")
    if len(content) > 200 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File too large (max 200MB)")

    logger.info("[%s] Transcribe request: %s (%.1f MB)", correlation, filename, len(content) / 1024 / 1024)

    work_dir = Path(tempfile.mkdtemp(prefix="ai_transcribe_"))
    input_path = work_dir / filename

    try:
        input_path.write_bytes(content)

        # Stage 0: Audio preprocessing
        t0 = time.time()
        from voice.pipeline.audio_prep import prepare_audio
        try:
            prepared_path = prepare_audio(input_path, cache_dir=work_dir)
        except Exception as e:
            logger.warning("[%s] Audio prep failed (%s) -- using original", correlation, e)
            prepared_path = input_path
        prep_time = time.time() - t0

        # Stage 1: Transcription (faster-whisper + Silero VAD)
        t0 = time.time()
        from voice.pipeline.transcriber import transcribe
        transcription = transcribe(prepared_path)
        transcribe_time = time.time() - t0

        # Stage 2: Diarization (pyannote 3.1 on MPS)
        t0 = time.time()
        from voice.pipeline.diarizer import diarize, DiarizationResult, SpeakerSegment
        try:
            diarization = diarize(prepared_path)
        except Exception as e:
            logger.warning("[%s] Diarization failed -- single-speaker fallback: %s", correlation, e)
            duration = transcription.duration
            diarization = DiarizationResult(
                segments=[SpeakerSegment(speaker="SPEAKER_00", start=0.0, end=duration)],
                embeddings={},
                num_speakers=1,
            )
        diarize_time = time.time() - t0

        # Stage 3: Forced alignment + speaker assignment (wav2vec2)
        t0 = time.time()
        from voice.pipeline.aligner import align
        aligned = align(transcription, diarization, prepared_path)
        align_time = time.time() - t0

        # Build response segments
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
                "is_overlap": seg.is_overlap,
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

        response = {
            "segments": segments,
            "speakers": aligned.speakers,
            "duration": round(aligned.duration, 2),
            "language": transcription.language,
            "num_speakers": len(aligned.speakers),
            "overlap_regions": [
                {"start": round(o.start, 3), "end": round(o.end, 3), "speakers": o.speakers}
                for o in getattr(aligned, 'overlap_regions', [])
            ],
            "embeddings": embeddings,
            "timing": {
                "prep_seconds": round(prep_time, 2),
                "transcribe_seconds": round(transcribe_time, 2),
                "diarize_seconds": round(diarize_time, 2),
                "align_seconds": round(align_time, 2),
                "total_seconds": round(total_time, 2),
            },
        }

        # Optional: Vocal analysis
        from config import ENABLE_VOCAL_ANALYSIS
        if ENABLE_VOCAL_ANALYSIS:
            t0 = time.time()
            vocal_data = _run_vocal_analysis(aligned, prepared_path)
            vocal_time = time.time() - t0
            if vocal_data:
                response["vocal_features"] = vocal_data["features"]
                response["baseline_deviations"] = vocal_data["deviations"]
                response["timing"]["vocal_seconds"] = round(vocal_time, 2)
                response["timing"]["total_seconds"] = round(total_time + vocal_time, 2)

        logger.info(
            "[%s] Transcription complete: %d segments, %d speakers, %.1fs duration "
            "(prep=%.1fs, transcribe=%.1fs, diarize=%.1fs, align=%.1fs, total=%.1fs)",
            correlation, len(segments), len(aligned.speakers), aligned.duration,
            prep_time, transcribe_time, diarize_time, align_time,
            response["timing"]["total_seconds"],
        )

        return response

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
        try:
            shutil.rmtree(work_dir, ignore_errors=True)
        except Exception:
            pass


def _run_vocal_analysis(aligned, audio_path):
    """Run vocal analysis for the stateless endpoint."""
    try:
        from config import VOCAL_MIN_SEGMENT_SECONDS
        from voice.analysis.vocal_analyzer import aggregate_speaker_features

        speaker_segments = {}
        for seg in aligned.segments:
            if seg.speaker not in speaker_segments:
                speaker_segments[seg.speaker] = []
            speaker_segments[seg.speaker].append({"start": seg.start, "end": seg.end})

        features = {}
        deviations = {}
        for speaker_label, segs in speaker_segments.items():
            feat = aggregate_speaker_features(audio_path, segs, VOCAL_MIN_SEGMENT_SECONDS)
            if feat:
                # Remove mfcc_means from response (large JSON blob)
                feat_response = {k: v for k, v in feat.items() if k != "mfcc_means"}
                features[speaker_label] = feat_response
                deviations[speaker_label] = {}  # No baseline context in stateless mode

        if features:
            return {"features": features, "deviations": deviations}
    except Exception as e:
        logger.warning("Vocal analysis failed in stateless endpoint (non-fatal): %s", e)

    return None
