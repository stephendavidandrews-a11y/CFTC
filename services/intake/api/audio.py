"""Audio serving API endpoints.

Serves audio files and clips for speaker review and transcript playback.
"""

import hashlib
import logging
import shutil
import subprocess
import tempfile
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from db.connection import get_connection

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/audio", tags=["audio"])

CLIP_CACHE_DIR = Path(tempfile.gettempdir()) / "cftc_voice_clips"
CLIP_CACHE_DIR.mkdir(exist_ok=True)


def _find_ffmpeg() -> str:
    path = shutil.which("ffmpeg")
    if path:
        return path
    brew_path = "/opt/homebrew/bin/ffmpeg"
    if Path(brew_path).exists():
        return brew_path
    raise FileNotFoundError("ffmpeg not found")


def _get_audio_path(conversation_id: str) -> Path:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT file_path FROM audio_files WHERE conversation_id = ?",
            (conversation_id,),
        ).fetchone()
        if not row:
            raise HTTPException(404, f"No audio file for conversation {conversation_id}")
        path = Path(row["file_path"])
        if not path.exists():
            raise HTTPException(404, f"Audio file not found on disk: {path}")
        return path
    finally:
        conn.close()


def _detect_media_type(path: Path) -> str:
    ext = path.suffix.lower()
    return {
        ".wav": "audio/wav", ".flac": "audio/flac", ".mp3": "audio/mpeg",
        ".m4a": "audio/mp4", ".ogg": "audio/ogg", ".opus": "audio/opus",
    }.get(ext, "audio/octet-stream")


@router.get("/{conversation_id}")
def serve_full_audio(conversation_id: str):
    """Serve the full audio file."""
    path = _get_audio_path(conversation_id)
    return FileResponse(path=str(path), media_type=_detect_media_type(path), filename=path.name)


@router.get("/{conversation_id}/clip")
def serve_audio_clip(conversation_id: str, start: float, end: float):
    """Serve an audio clip between start and end seconds."""
    if start < 0 or end <= start:
        raise HTTPException(400, "Invalid time range")
    if end - start > 300:
        raise HTTPException(400, "Clip too long (max 5 minutes)")

    audio_path = _get_audio_path(conversation_id)

    cache_key = hashlib.md5(f"{conversation_id}:{start}:{end}".encode()).hexdigest()
    cache_path = CLIP_CACHE_DIR / f"{cache_key}.wav"

    if cache_path.exists():
        return FileResponse(path=str(cache_path), media_type="audio/wav")

    try:
        ffmpeg = _find_ffmpeg()
        cmd = [
            ffmpeg, "-i", str(audio_path),
            "-ss", str(start), "-to", str(end),
            "-ac", "1", "-ar", "16000", "-f", "wav", "-y", str(cache_path),
        ]
        result = subprocess.run(cmd, capture_output=True, timeout=30)
        if result.returncode != 0:
            raise HTTPException(500, "Failed to extract audio clip")
        return FileResponse(path=str(cache_path), media_type="audio/wav")
    except FileNotFoundError:
        raise HTTPException(500, "ffmpeg not available")
    except subprocess.TimeoutExpired:
        raise HTTPException(500, "Audio extraction timed out")


@router.get("/{conversation_id}/speaker-sample/{speaker_label}")
def serve_speaker_sample(conversation_id: str, speaker_label: str):
    """Serve a representative audio clip for a speaker."""
    conn = get_connection()
    try:
        segments = conn.execute(
            """SELECT start_time, end_time
               FROM transcripts
               WHERE conversation_id = ? AND speaker_label = ?
                 AND (end_time - start_time) >= 3.0
               ORDER BY
                 CASE WHEN (end_time - start_time) BETWEEN 3.0 AND 15.0 THEN 0 ELSE 1 END,
                 (end_time - start_time) DESC
               LIMIT 1""",
            (conversation_id, speaker_label),
        ).fetchone()

        if not segments:
            segments = conn.execute(
                """SELECT start_time, end_time
                   FROM transcripts
                   WHERE conversation_id = ? AND speaker_label = ?
                     AND (end_time - start_time) >= 1.0
                   ORDER BY (end_time - start_time) DESC
                   LIMIT 1""",
                (conversation_id, speaker_label),
            ).fetchone()

        if not segments:
            raise HTTPException(404, f"No suitable audio segment for speaker {speaker_label}")

        start = float(segments["start_time"])
        end = float(segments["end_time"])
        if end - start > 15.0:
            end = start + 15.0
    finally:
        conn.close()

    return serve_audio_clip(conversation_id, start, end)
