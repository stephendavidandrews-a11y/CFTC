"""Transcription stage — orchestrates transcription, diarization, and alignment.

ARCHITECTURE DECISION: Native Worker Path
==========================================
Transcription (Whisper) and diarization (pyannote) require:
- GPU acceleration (MPS/Metal on Mac Mini, or CUDA)
- Large model files (Whisper medium.en ~1.5GB, pyannote ~500MB)
- torch, torchaudio, whisper, pyannote.audio dependencies

The AI service runs containerized (Docker, python:3.11-slim) with no GPU access.
Forcing transcription into the container would mean:
- Massive image size (~8GB+ with torch)
- CPU-only transcription (10-30x slower)
- No diarization (pyannote needs GPU for reasonable speed)

Therefore: transcription runs via a NATIVE WORKER on the Mac Mini host,
where GPU (MPS/Metal) is available. The AI service orchestrates this
by calling the native worker's HTTP API.

The native worker is the existing intake service (port 8005) which already
has Whisper + pyannote loaded. We add a thin transcription-only endpoint
to it, or use its existing pipeline.

For Phase 1, the worker abstraction allows:
- Native worker (current): HTTP call to intake service
- Future: containerized worker with GPU passthrough
- Future: cloud transcription API (Deepgram, AssemblyAI, etc.)

If the native worker is unavailable, the stage fails cleanly with a typed error.
"""
import json
import logging
import uuid
from dataclasses import dataclass, field
from pathlib import Path

import httpx

from app.config import load_policy

logger = logging.getLogger(__name__)

# Native worker endpoint — the intake service on the Mac Mini host
# In Docker: host-services:8005; locally: localhost:8005
NATIVE_WORKER_BASE = "http://localhost:8005"
NATIVE_WORKER_TIMEOUT = 4800  # 80 minutes max for long audio

# Fallback for local dev (not in Docker)
import os
if os.environ.get("APP_ENV") == "development":
    NATIVE_WORKER_BASE = os.environ.get(
        "NATIVE_WORKER_URL", "http://localhost:8005"
    )


# ── Data classes for transcription results ──

@dataclass
class WordTimestamp:
    word: str
    start: float
    end: float
    probability: float


@dataclass
class TranscriptSegment:
    speaker: str
    start: float
    end: float
    text: str
    words: list[WordTimestamp] = field(default_factory=list)


@dataclass
class TranscriptionResult:
    segments: list[TranscriptSegment]
    speakers: list[str]
    duration: float
    language: str = "en"
    num_speakers: int = 0
    embeddings: dict[str, bytes] = field(default_factory=dict)
    vocal_features: dict[str, dict] = field(default_factory=dict)
    overlap_regions: list[dict] = field(default_factory=list)


class TranscriptionError(Exception):
    """Typed error for transcription failures."""
    def __init__(self, message: str, error_type: str = "transcription_error",
                 recoverable: bool = False):
        super().__init__(message)
        self.error_type = error_type
        self.recoverable = recoverable


async def transcribe_via_native_worker(
    audio_path: Path,
    communication_id: str,
) -> TranscriptionResult:
    """Send audio to the native worker for transcription + diarization + alignment.

    The native worker runs Whisper + pyannote on the Mac Mini's GPU.
    We send the normalized WAV file path (shared volume or host path)
    and receive the aligned transcript back.

    Args:
        audio_path: Path to the normalized 16kHz mono WAV.
        communication_id: For logging and correlation.

    Returns:
        TranscriptionResult with speaker-labeled segments.

    Raises:
        TranscriptionError: On worker failure, timeout, or unavailability.
    """
    logger.info(
        "[%s] Sending to native worker for transcription: %s",
        communication_id[:8], audio_path.name,
    )

    # The native worker needs the file path as seen from the host.
    # In Docker: the AI service mounts audio at /app/uploads/<comm_id>/normalized.wav
    # The host equivalent path depends on the Docker volume mapping.
    # For now, we send the file content directly via multipart upload.
    try:
        async with httpx.AsyncClient(timeout=NATIVE_WORKER_TIMEOUT) as client:
            # Try the transcription-only endpoint first
            with open(audio_path, "rb") as f:
                response = await client.post(
                    f"{NATIVE_WORKER_BASE}/intake/api/transcribe",
                    files={"audio": (audio_path.name, f, "audio/wav")},
                    data={"communication_id": communication_id},
                )

            if response.status_code == 404:
                # Endpoint doesn't exist yet — fall back to full pipeline
                raise TranscriptionError(
                    "Native worker /transcribe endpoint not found. "
                    "The intake service needs a transcription-only endpoint.",
                    error_type="worker_endpoint_missing",
                    recoverable=False,
                )

            if response.status_code != 200:
                raise TranscriptionError(
                    f"Native worker returned {response.status_code}: "
                    f"{response.text[:500]}",
                    error_type="worker_error",
                    recoverable=response.status_code >= 500,
                )

            data = response.json()

    except httpx.ConnectError:
        raise TranscriptionError(
            f"Cannot reach native worker at {NATIVE_WORKER_BASE}. "
            "Is the intake service running on port 8005?",
            error_type="worker_unavailable",
            recoverable=True,
        )
    except httpx.TimeoutException:
        raise TranscriptionError(
            f"Native worker timed out after {NATIVE_WORKER_TIMEOUT}s",
            error_type="worker_timeout",
            recoverable=True,
        )
    except TranscriptionError:
        raise
    except Exception as e:
        raise TranscriptionError(
            f"Unexpected error calling native worker: {e}",
            error_type="worker_error",
            recoverable=False,
        )

    return _parse_worker_response(data, communication_id)


def _parse_worker_response(data: dict, communication_id: str) -> TranscriptionResult:
    """Parse the native worker's JSON response into our data model."""
    segments = []
    speakers_set = set()

    for seg in data.get("segments", []):
        speaker = seg.get("speaker", "SPEAKER_00")
        speakers_set.add(speaker)

        words = []
        for w in seg.get("words", []):
            words.append(WordTimestamp(
                word=w.get("word", ""),
                start=float(w.get("start", 0)),
                end=float(w.get("end", 0)),
                probability=float(w.get("probability", 0)),
            ))

        segments.append(TranscriptSegment(
            speaker=speaker,
            start=float(seg.get("start", 0)),
            end=float(seg.get("end", 0)),
            text=seg.get("text", ""),
            words=words,
        ))

    speakers = sorted(speakers_set)
    duration = float(data.get("duration", 0))
    if segments and duration == 0:
        duration = segments[-1].end

    # Embeddings come as base64-encoded bytes (if provided)
    embeddings = {}
    for label, emb_data in data.get("embeddings", {}).items():
        if isinstance(emb_data, str):
            import base64
            embeddings[label] = base64.b64decode(emb_data)
        elif isinstance(emb_data, bytes):
            embeddings[label] = emb_data

    logger.info(
        "[%s] Transcription result: %d segments, %d speakers, %.1fs",
        communication_id[:8], len(segments), len(speakers), duration,
    )

    # Parse vocal features and overlap regions from intake service
    vocal_features = data.get("vocal_features", {})
    overlap_regions = data.get("overlap_regions", [])

    return TranscriptionResult(
        segments=segments,
        speakers=speakers,
        duration=duration,
        language=data.get("language", "en"),
        num_speakers=len(speakers),
        embeddings=embeddings,
        vocal_features=vocal_features,
        overlap_regions=overlap_regions,
    )


def store_transcript(db, communication_id: str, result: TranscriptionResult):
    """Persist transcription results to ai.db.

    Stores:
    - Transcript segments (transcripts table)
    - Voice samples/embeddings (voice_samples table)
    - Duration on communication record
    - Communication participants (one per speaker label)
    """
    now_sql = "datetime('now')"

    # Update communication duration
    db.execute(
        "UPDATE communications SET duration_seconds = ?, updated_at = datetime('now') WHERE id = ?",
        (result.duration, communication_id),
    )

    # Store transcript segments
    for seg in result.segments:
        word_timestamps = json.dumps([
            {"word": w.word, "start": w.start, "end": w.end, "probability": w.probability}
            for w in seg.words
        ]) if seg.words else None

        db.execute("""
            INSERT INTO transcripts (id, communication_id, speaker_label,
                start_time, end_time, raw_text, word_timestamps, confidence)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            str(uuid.uuid4()), communication_id, seg.speaker,
            seg.start, seg.end, seg.text, word_timestamps,
            min(w.probability for w in seg.words) if seg.words else None,
        ))

    # Create participant records (one per unique speaker)
    for speaker in result.speakers:
        db.execute("""
            INSERT INTO communication_participants
                (id, communication_id, speaker_label, confirmed)
            VALUES (?, ?, ?, 0)
        """, (str(uuid.uuid4()), communication_id, speaker))

    # Store voice embeddings
    for label, emb_bytes in result.embeddings.items():
        db.execute("""
            INSERT INTO voice_samples (id, communication_id, speaker_label, embedding)
            VALUES (?, ?, ?, ?)
        """, (str(uuid.uuid4()), communication_id, label, emb_bytes))

    # Store vocal quality metrics on voice_samples
    for label, features in result.vocal_features.items():
        db.execute("""
            UPDATE voice_samples
            SET vocal_quality_json = ?,
                hnr_db = ?, jitter = ?, shimmer = ?,
                pitch_mean = ?, pitch_std = ?,
                speaking_rate_wpm = ?
            WHERE communication_id = ? AND speaker_label = ?
        """, (
            json.dumps(features),
            features.get("hnr"), features.get("jitter"), features.get("shimmer"),
            features.get("pitch_mean"), features.get("pitch_std"),
            features.get("speaking_rate_wpm"),
            communication_id, label,
        ))

    # Store overlap regions on communication
    if result.overlap_regions:
        db.execute(
            "UPDATE communications SET overlap_regions_json = ? WHERE id = ?",
            (json.dumps(result.overlap_regions), communication_id),
        )

    db.commit()
    logger.info(
        "[%s] Stored: %d transcript segments, %d participants, %d voice samples, %d vocal profiles",
        communication_id[:8],
        len(result.segments),
        len(result.speakers),
        len(result.embeddings),
        len(result.vocal_features),
    )


async def run_transcription_stage(
    db, communication_id: str, audio_path: Path
) -> TranscriptionResult:
    """Full transcription stage: call worker, store results.

    This is the entry point called by the orchestrator.
    """
    result = await transcribe_via_native_worker(audio_path, communication_id)
    store_transcript(db, communication_id, result)
    return result
