"""CFTC Intake Service — configuration."""

from pathlib import Path

# ── Paths ──
BASE_DIR = Path("/Users/stephen/Documents/Website/cftc/services/intake")
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "cftc_voice.db"
INBOX_DIR = DATA_DIR / "inbox"
INBOX_PI = INBOX_DIR / "pi"
INBOX_PLAUD = INBOX_DIR / "plaud"
INBOX_PHONE = INBOX_DIR / "phone"
MODELS_DIR = DATA_DIR / "models"

# ── Service ──
SERVICE_PORT = 8005

# ── Audio Formats ──
SUPPORTED_FORMATS = {".wav", ".flac", ".mp3", ".m4a", ".ogg", ".opus"}

# ── Whisper ──
WHISPER_MODEL = "medium.en"

# ── pyannote ──
PYANNOTE_PIPELINE = "pyannote/speaker-diarization-3.1"

# ── Conversation Boundaries ──
SILENCE_BOUNDARY_SECONDS = 30
MAX_RECORDING_SECONDS = 14400  # 4 hours

# ── Voiceprint Matching ──
VOICEPRINT_AUTO_THRESHOLD = 0.85   # auto-assign above this
VOICEPRINT_SUGGEST_THRESHOLD = 0.65  # suggest above this
