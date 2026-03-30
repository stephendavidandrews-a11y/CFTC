"""CFTC Intake Service -- configuration."""

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

# -- Runtime environment --
APP_ENV: str = os.environ.get("APP_ENV", "development")

# -- Paths --
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
_default_db = DATA_DIR / "cftc_voice.db"
DB_PATH: Path = Path(os.environ.get("INTAKE_DB_PATH", str(_default_db)))
_default_inbox = DATA_DIR / "inbox"
INBOX_DIR: Path = Path(os.environ.get("INTAKE_INBOX_DIR", str(_default_inbox)))
INBOX_PI = INBOX_DIR / "pi"
INBOX_PLAUD = INBOX_DIR / "plaud"
INBOX_PHONE = INBOX_DIR / "phone"
MODELS_DIR = DATA_DIR / "models"

# -- Auth --
PIPELINE_USER: str = os.environ.get("PIPELINE_USER", "")
PIPELINE_PASS: str = os.environ.get("PIPELINE_PASS", "")

# -- Service --
SERVICE_PORT: int = int(os.environ.get("INTAKE_PORT", "8005"))

# -- Audio Formats --
SUPPORTED_FORMATS = {".wav", ".flac", ".mp3", ".m4a", ".ogg", ".opus"}
MIN_AUDIO_DURATION_SECS: float = float(os.environ.get("MIN_AUDIO_DURATION_SECS", "2.0"))

# -- ASR Engine (Qwen3-ASR on MLX / Apple Silicon) --
QWEN3_ASR_MODEL: str = os.environ.get("QWEN3_ASR_MODEL", "Qwen/Qwen3-ASR-1.7B")
QWEN3_DRAFT_MODEL: str = os.environ.get("QWEN3_DRAFT_MODEL", "Qwen/Qwen3-ASR-0.6B")
ASR_CONTEXT: str = os.environ.get("ASR_CONTEXT", "")

# -- pyannote --
PYANNOTE_PIPELINE = "pyannote/speaker-diarization-community-1"

# -- Diarization --
ENABLE_DIARIZATION: bool = os.environ.get("ENABLE_DIARIZATION", "true").lower() == "true"
DIARIZATION_MIN_SPEAKERS = 2
DIARIZATION_MAX_SPEAKERS = None
DIARIZATION_CLUSTERING_THRESHOLD = 0.55

# -- Conversation Boundaries --
SILENCE_BOUNDARY_SECONDS = 30
MAX_RECORDING_SECONDS = 14400  # 4 hours

# -- Voiceprint Matching --
VOICEPRINT_AUTO_THRESHOLD = 0.85
VOICEPRINT_SUGGEST_THRESHOLD = 0.65

# -- Vocal Analysis --
ENABLE_VOCAL_ANALYSIS: bool = os.environ.get("ENABLE_VOCAL_ANALYSIS", "true").lower() == "true"
VOCAL_MIN_SEGMENT_SECONDS = 5.0
BASELINE_EMA_ALPHA = 0.1
BASELINE_WARN_THRESHOLD = 0.20
BASELINE_ALERT_THRESHOLD = 0.50

# -- Auto-Advance --
ENABLE_AUTO_ADVANCE: bool = os.environ.get("ENABLE_AUTO_ADVANCE", "false").lower() == "false"

# -- Voiceprint Quality Gate --
VP_MIN_DIARIZATION_CONFIDENCE = 0.90
VP_MIN_SEGMENT_DURATION = 3.0  # seconds
VP_MIN_SNR_DB = 15.0
VP_MIN_HNR_DB = 10.0
VP_MAX_JITTER_PCT = 0.02  # 2%
VP_MAX_SHIMMER_PCT = 0.05  # 5%
VP_MAX_ENERGY_VARIANCE_STD = 2.0
VP_MAX_F0_STDDEV_RATIO = 0.40
VP_TARGET_DURATION_MIN = 30.0  # seconds of clean audio needed
VP_TARGET_DURATION_MAX = 40.0
VP_PROVISIONAL_IF_BELOW = 30.0


def validate_config() -> None:
    """Validate config at startup. Logs warnings in dev, exits in production."""
    import shutil
    import sys

    errors = []

    if APP_ENV == "production":
        if not PIPELINE_USER or not PIPELINE_PASS:
            errors.append("PIPELINE_USER and PIPELINE_PASS must be set in production")

    if not DB_PATH.parent.exists():
        errors.append(f"DB parent directory does not exist: {DB_PATH.parent}")

    if shutil.which("ffmpeg") is None:
        errors.append("ffmpeg not found in PATH -- required for audio preprocessing")

    if errors:
        for e in errors:
            print(f"[CONFIG ERROR] {e}", file=sys.stderr)
        if APP_ENV == "production":
            sys.exit(1)
        else:
            for e in errors:
                logger.warning("Config warning: %s", e)
