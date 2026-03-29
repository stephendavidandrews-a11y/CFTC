"""Transcription module -- Qwen3-ASR on MLX (Apple Silicon).

Uses mlx-qwen3-asr with Qwen3-ASR-1.7B for transcription and
Qwen3-ForcedAligner-0.6B-8bit for word-level timestamps.
Handles long audio via internal 30s energy-based chunking.
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

_session = None


def _get_session():
    """Lazy-load the Qwen3-ASR session (keeps model warm across calls)."""
    global _session
    if _session is None:
        from mlx_qwen3_asr import Session
        from config import QWEN3_ASR_MODEL

        logger.info(f"Loading Qwen3-ASR session: {QWEN3_ASR_MODEL}")
        _session = Session(model=QWEN3_ASR_MODEL)
        logger.info("Qwen3-ASR session loaded")
    return _session


# -- Dataclasses (identical to old transcriber.py) --


@dataclass
class WordTimestamp:
    word: str
    start: float
    end: float
    probability: float


@dataclass
class TranscriptSegment:
    start: float
    end: float
    text: str
    words: list[WordTimestamp] = field(default_factory=list)


@dataclass
class TranscriptionResult:
    segments: list[TranscriptSegment]
    language: str
    duration: float


# Common abbreviations that end with a period but are NOT sentence endings.
# Includes regulatory, legal, and general abbreviations.
_ABBREVIATIONS = frozenset({
    "dr.", "mr.", "mrs.", "ms.", "jr.", "sr.", "st.", "ave.", "blvd.",
    "no.", "nos.", "vol.", "vs.", "etc.", "approx.", "dept.", "div.",
    "gov.", "gen.", "sgt.", "cpl.", "pvt.", "rev.", "hon.",
    "inc.", "corp.", "ltd.", "co.", "llc.", "assn.",
    "u.s.", "u.k.", "e.u.", "d.c.",
    "jan.", "feb.", "mar.", "apr.", "jun.", "jul.", "aug.", "sep.",
    "sept.", "oct.", "nov.", "dec.",
    "fig.", "eq.", "ref.", "sec.", "ch.", "pt.", "art.",
    "cfr.", "fr.", "p.l.", "pub.", "stat.",
    "a.m.", "p.m.", "e.g.", "i.e.",
})


def _is_sentence_end(word: str, next_word: str | None) -> bool:
    """Determine if a word is a true sentence-ending boundary.

    Handles abbreviations like "Dr.", "U.S.", "No.", "Corp." by requiring
    that the next word starts with a capital letter (or is end-of-text).
    Exclamation and question marks are always sentence-ending.
    """
    stripped = word.strip()
    if not stripped:
        return False

    # ! and ? are always sentence-ending
    if stripped[-1] in ("!", "?"):
        return True

    # Period: only sentence-ending if not an abbreviation
    if stripped[-1] == ".":
        # Check against abbreviation list
        if stripped.lower() in _ABBREVIATIONS:
            return False
        # Single letter + period (e.g., "A.", "B.") -- likely initial, not sentence end
        if len(stripped) == 2 and stripped[0].isalpha():
            return False
        # If next word exists and starts lowercase, probably not sentence end
        # (e.g., "...the U.S. government" -- "government" is lowercase)
        if next_word:
            first_char = next_word.strip()[0] if next_word.strip() else ""
            if first_char and first_char.islower():
                return False
        # Period at end of text, or followed by capital letter -> sentence end
        return True

    return False


def _words_to_segments(words: list[WordTimestamp], full_text: str) -> list[TranscriptSegment]:
    """Group word-level timestamps into sentence-level segments.

    Splits on sentence-ending punctuation, handling abbreviations
    like "Dr.", "U.S.", "No.", "Corp." by checking for a following
    capital letter. This matches the granularity that faster-whisper produced.
    """
    if not words:
        return []

    segments = []
    current_words = []

    for i, word in enumerate(words):
        current_words.append(word)
        next_word_text = words[i + 1].word if i + 1 < len(words) else None
        if _is_sentence_end(word.word, next_word_text):
            segments.append(TranscriptSegment(
                start=current_words[0].start,
                end=current_words[-1].end,
                text=" ".join(w.word for w in current_words),
                words=list(current_words),
            ))
            current_words = []

    # Flush remaining words as final segment
    if current_words:
        segments.append(TranscriptSegment(
            start=current_words[0].start,
            end=current_words[-1].end,
            text=" ".join(w.word for w in current_words),
            words=list(current_words),
        ))

    return segments


def transcribe(audio_path: Path, context: str = "") -> TranscriptionResult:
    """Transcribe audio file using Qwen3-ASR with word-level timestamps.

    Args:
        audio_path: Path to 16kHz mono WAV (from audio_prep).
        context: Optional domain vocabulary hint (space-separated terms).
                 Not wired up yet -- reserved for future context biasing.

    Returns:
        TranscriptionResult with sentence-level segments containing word timestamps.
    """
    session = _get_session()

    from config import QWEN3_DRAFT_MODEL

    logger.info(f"Transcribing: {audio_path.name}")
    result = session.transcribe(
        str(audio_path),
        return_timestamps=True,
        language="English",
        context=context,
        draft_model=QWEN3_DRAFT_MODEL,
    )

    # Qwen3 returns word-level segments as [{text, start, end}, ...]
    words = []
    if result.segments:
        for seg in result.segments:
            words.append(WordTimestamp(
                word=seg["text"],
                start=seg["start"],
                end=seg["end"],
                probability=1.0,  # Qwen3 does not provide confidence scores
            ))

    # Overlay punctuated text from result.text
    # Qwen3's segments have bare words but result.text has full punctuation
    punctuated_words = result.text.split() if result.text else []
    if len(punctuated_words) == len(words):
        for w, pw in zip(words, punctuated_words):
            w.word = pw
    elif punctuated_words and words:
        logger.warning(
            f"Word count mismatch: {len(punctuated_words)} punctuated vs {len(words)} segments. "
            "Using unpunctuated segment text."
        )

    # Reconstitute sentence-level segments from word timestamps
    segments = _words_to_segments(words, result.text)

    duration = words[-1].end if words else 0.0

    # Normalize language: Qwen3 returns "English", we need "en"
    language = result.language or "English"
    lang_map = {"English": "en", "Chinese": "zh", "Japanese": "ja", "Korean": "ko"}
    language = lang_map.get(language, language.lower()[:2])

    logger.info(f"Transcription complete: {len(segments)} segments, {duration:.1f}s")
    return TranscriptionResult(
        segments=segments,
        language=language,
        duration=duration,
    )
