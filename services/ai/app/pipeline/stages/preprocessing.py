"""Audio preprocessing stage — normalize to 16kHz mono PCM WAV.

Conservative approach:
- mono, 16 kHz, 16-bit PCM WAV
- No aggressive denoise, hard noise gates, heavy compression,
  time-stretching, or anything that changes cadence/speaker characteristics
- Preserves original file; creates normalized copy for downstream processing

Adapted from services/intake/voice/pipeline/audio_prep.py for the AI service.
"""

import json
import logging
import shutil
import subprocess
from pathlib import Path

from app.config import AI_UPLOAD_DIR

logger = logging.getLogger(__name__)

# Target format for Whisper + pyannote
TARGET_SAMPLE_RATE = 16000
TARGET_CHANNELS = 1

# Accepted audio formats on ingestion
ACCEPTED_FORMATS = {
    ".wav",
    ".flac",
    ".mp3",
    ".m4a",
    ".mp4",
    ".aac",
    ".ogg",
    ".opus",
    ".wma",
    ".webm",
}

# Formats that always need conversion (not already PCM WAV)
COMPRESSED_FORMATS = {
    ".m4a",
    ".mp4",
    ".aac",
    ".mp3",
    ".ogg",
    ".opus",
    ".flac",
    ".wma",
    ".webm",
}


def _find_ffmpeg() -> str:
    """Find ffmpeg binary, checking common locations."""
    found = shutil.which("ffmpeg")
    if found:
        return found
    # Homebrew on macOS (native worker path)
    homebrew = "/opt/homebrew/bin/ffmpeg"
    if Path(homebrew).exists():
        return homebrew
    raise FileNotFoundError(
        "ffmpeg not found in PATH or /opt/homebrew/bin. "
        "Install with: apt-get install ffmpeg (container) or brew install ffmpeg (native)"
    )


def _find_ffprobe() -> str:
    """Find ffprobe binary."""
    found = shutil.which("ffprobe")
    if found:
        return found
    homebrew = "/opt/homebrew/bin/ffprobe"
    if Path(homebrew).exists():
        return homebrew
    raise FileNotFoundError("ffprobe not found")


def _is_target_format(wav_path: Path) -> bool:
    """Check if a WAV is already 16kHz mono 16-bit PCM.

    First tries Python's wave module (no external deps).
    Falls back to ffprobe if available.
    """
    # Try Python wave module first (works for standard PCM WAV)
    try:
        import wave

        with wave.open(str(wav_path), "rb") as wf:
            sr = wf.getframerate()
            ch = wf.getnchannels()
            sw = wf.getsampwidth()
            return sr == TARGET_SAMPLE_RATE and ch == TARGET_CHANNELS and sw == 2
    except Exception:
        pass

    # Fallback to ffprobe
    try:
        ffprobe = _find_ffprobe()
        cmd = [
            ffprobe,
            "-v",
            "quiet",
            "-print_format",
            "json",
            "-show_streams",
            str(wav_path),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if result.returncode != 0:
            return False
        data = json.loads(result.stdout)
        for stream in data.get("streams", []):
            if stream.get("codec_type") == "audio":
                sr = int(stream.get("sample_rate", 0))
                ch = int(stream.get("channels", 0))
                codec = stream.get("codec_name", "")
                return (
                    sr == TARGET_SAMPLE_RATE
                    and ch == TARGET_CHANNELS
                    and codec == "pcm_s16le"
                )
        return False
    except Exception:
        return False


def get_audio_metadata(audio_path: Path) -> dict:
    """Extract audio metadata. Tries Python wave module first, then ffprobe."""
    suffix = audio_path.suffix.lower()

    # For WAV files, try Python's wave module first (no external deps)
    if suffix == ".wav":
        try:
            import wave

            with wave.open(str(audio_path), "rb") as wf:
                frames = wf.getnframes()
                sr = wf.getframerate()
                ch = wf.getnchannels()
                sw = wf.getsampwidth()
                duration = frames / sr if sr > 0 else 0
                return {
                    "duration_seconds": round(duration, 2),
                    "file_size_bytes": audio_path.stat().st_size,
                    "format_name": "wav",
                    "codec": "pcm_s16le" if sw == 2 else f"pcm_s{sw * 8}le",
                    "sample_rate": sr,
                    "channels": ch,
                    "bits_per_sample": sw * 8,
                }
        except Exception:
            pass  # Fall through to ffprobe

    # Try ffprobe for non-WAV or if wave module failed
    try:
        ffprobe = _find_ffprobe()
        cmd = [
            ffprobe,
            "-v",
            "quiet",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            str(audio_path),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        if result.returncode != 0:
            return {"error": "ffprobe failed", "stderr": result.stderr[-200:]}

        data = json.loads(result.stdout)
        fmt = data.get("format", {})
        audio_stream = None
        for s in data.get("streams", []):
            if s.get("codec_type") == "audio":
                audio_stream = s
                break

        meta = {
            "duration_seconds": float(fmt.get("duration", 0)),
            "file_size_bytes": int(fmt.get("size", 0)),
            "format_name": fmt.get("format_name", "unknown"),
            "bit_rate": int(fmt.get("bit_rate", 0)),
        }
        if audio_stream:
            meta.update(
                {
                    "codec": audio_stream.get("codec_name", "unknown"),
                    "sample_rate": int(audio_stream.get("sample_rate", 0)),
                    "channels": int(audio_stream.get("channels", 0)),
                    "bits_per_sample": int(audio_stream.get("bits_per_sample", 0)),
                }
            )

        # Extract creation_time from format tags (embedded by recording devices)
        tags = fmt.get("tags", {})
        creation_time = (
            tags.get("creation_time")
            or tags.get("date")
            or tags.get("DATE")
            or tags.get("CREATION_TIME")
        )
        if creation_time:
            meta["creation_time"] = creation_time

        return meta
    except FileNotFoundError:
        # Neither wave module nor ffprobe worked — return basic file info
        return {
            "file_size_bytes": audio_path.stat().st_size if audio_path.exists() else 0,
            "format_name": suffix.lstrip("."),
            "note": "ffprobe not available; metadata is limited",
        }
    except Exception as e:
        return {"error": str(e)}


def preprocess_audio(
    original_path: Path,
    communication_id: str,
) -> tuple[Path, dict]:
    """Normalize audio to 16kHz mono PCM WAV.

    Args:
        original_path: Path to the original audio file.
        communication_id: Used for naming the output file.

    Returns:
        Tuple of (normalized_wav_path, metadata_dict).

    Raises:
        FileNotFoundError: If ffmpeg not available.
        RuntimeError: If ffmpeg conversion fails.
        ValueError: If input format not accepted.
    """
    suffix = original_path.suffix.lower()
    if suffix not in ACCEPTED_FORMATS:
        raise ValueError(
            f"Unsupported audio format: {suffix}. "
            f"Accepted: {', '.join(sorted(ACCEPTED_FORMATS))}"
        )

    # Output goes to uploads/<comm_id>/normalized.wav
    output_dir = AI_UPLOAD_DIR / communication_id
    output_dir.mkdir(parents=True, exist_ok=True)
    normalized_path = output_dir / "normalized.wav"

    # Get source metadata before conversion
    source_meta = get_audio_metadata(original_path)

    # If already target format, just copy (preserve original, create normalized copy)
    if suffix == ".wav" and _is_target_format(original_path):
        logger.info("Audio already at target format — copying: %s", original_path.name)
        shutil.copy2(str(original_path), str(normalized_path))
        return normalized_path, source_meta

    # Convert with ffmpeg — conservative settings only
    logger.info(
        "Preprocessing %s -> 16kHz mono PCM WAV: %s",
        suffix,
        original_path.name,
    )
    ffmpeg = _find_ffmpeg()
    cmd = [
        ffmpeg,
        "-y",  # overwrite output
        "-i",
        str(original_path),  # input
        "-ac",
        str(TARGET_CHANNELS),  # mono
        "-ar",
        str(TARGET_SAMPLE_RATE),  # 16 kHz
        "-sample_fmt",
        "s16",  # 16-bit PCM
        "-acodec",
        "pcm_s16le",  # explicit PCM codec
        str(normalized_path),
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,  # 5 min max
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError(
            f"ffmpeg timed out after 300s preprocessing {original_path.name}"
        )

    if result.returncode != 0:
        stderr_tail = result.stderr[-500:] if result.stderr else "no stderr"
        raise RuntimeError(
            f"ffmpeg failed (code {result.returncode}) preprocessing "
            f"{original_path.name}: {stderr_tail}"
        )

    if not normalized_path.exists():
        raise RuntimeError(f"ffmpeg produced no output file: {normalized_path}")

    output_size = normalized_path.stat().st_size
    logger.info(
        "Preprocessed: %s -> %s (%.1f MB)",
        original_path.name,
        normalized_path.name,
        output_size / 1024 / 1024,
    )

    return normalized_path, source_meta
