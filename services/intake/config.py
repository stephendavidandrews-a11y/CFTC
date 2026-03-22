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

# ── ASR Engine ──
# faster-whisper with int8 quantization (replaces openai-whisper)
WHISPER_MODEL = "medium.en"
WHISPER_DEVICE = "cpu"
WHISPER_COMPUTE_TYPE = "int8"
WHISPER_CPU_THREADS = 8
WHISPER_BEAM_SIZE = 5

# ── VAD (Silero, built into faster-whisper) ──
VAD_THRESHOLD = 0.5
VAD_MIN_SPEECH_MS = 250
VAD_MIN_SILENCE_MS = 2000

# ── Forced Alignment (wav2vec2 via whisperx) ──
ALIGNMENT_DEVICE = "cpu"

# ── pyannote ──
PYANNOTE_PIPELINE = "pyannote/speaker-diarization-3.1"

# ── Diarization Tuning ──
DIARIZATION_MIN_SPEAKERS = 2
DIARIZATION_MAX_SPEAKERS = None
DIARIZATION_CLUSTERING_THRESHOLD = 0.55

# ── Conversation Boundaries ──
SILENCE_BOUNDARY_SECONDS = 30
MAX_RECORDING_SECONDS = 14400  # 4 hours

# ── Voiceprint Matching ──
VOICEPRINT_AUTO_THRESHOLD = 0.85
VOICEPRINT_SUGGEST_THRESHOLD = 0.65

# ── Vocal Analysis ──
ENABLE_VOCAL_ANALYSIS = True
VOCAL_MIN_SEGMENT_SECONDS = 5.0
BASELINE_EMA_ALPHA = 0.1
BASELINE_WARN_THRESHOLD = 0.20
BASELINE_ALERT_THRESHOLD = 0.50

# ── Auto-Advance ──
ENABLE_AUTO_ADVANCE = False
