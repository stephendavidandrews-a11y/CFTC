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

# ── Diarization Tuning ──
# min_speakers: Default minimum expected speakers. Set to 2 because
# single-person recordings are rare (most are meetings/conversations).
# Can be overridden per-call via diarize(min_speakers=N).
DIARIZATION_MIN_SPEAKERS = 2

# max_speakers: Default maximum expected speakers. None = auto-detect.
# Set a cap if you know the typical meeting size (e.g., 6 for small meetings).
DIARIZATION_MAX_SPEAKERS = None

# clustering_threshold: Controls how aggressively pyannote merges speaker
# clusters. pyannote default is ~0.7 (aggressive merging → fewer speakers).
# Lower values = less merging = more speakers detected.
# 0.55 is a good balance for close-proximity multi-person conversations
# (e.g., Plaud Note Pro recordings at meetings/networking events).
# Range: 0.0 (never merge) to 1.0 (merge everything into one speaker).
DIARIZATION_CLUSTERING_THRESHOLD = 0.55

# ── Conversation Boundaries ──
SILENCE_BOUNDARY_SECONDS = 30
MAX_RECORDING_SECONDS = 14400  # 4 hours

# ── Voiceprint Matching ──
VOICEPRINT_AUTO_THRESHOLD = 0.85   # auto-assign above this
VOICEPRINT_SUGGEST_THRESHOLD = 0.65  # suggest above this
