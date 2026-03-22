"""Transcription module — faster-whisper with int8 quantization + Silero VAD.

Uses faster-whisper (CTranslate2 backend) on CPU with int8 for ~2-4x speedup
over openai-whisper. Silero VAD pre-segments audio to reduce hallucination.
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

_whisper_model = None


def _get_model():
    global _whisper_model
    if _whisper_model is None:
        from faster_whisper import WhisperModel
        from config import (
            WHISPER_MODEL, WHISPER_DEVICE, WHISPER_COMPUTE_TYPE,
            WHISPER_CPU_THREADS, MODELS_DIR,
        )

        download_root = MODELS_DIR / "faster-whisper"
        download_root.mkdir(parents=True, exist_ok=True)

        logger.info(
            f"Loading faster-whisper: {WHISPER_MODEL} on {WHISPER_DEVICE} "
            f"(compute_type={WHISPER_COMPUTE_TYPE}, threads={WHISPER_CPU_THREADS})"
        )
        _whisper_model = WhisperModel(
            WHISPER_MODEL,
            device=WHISPER_DEVICE,
            compute_type=WHISPER_COMPUTE_TYPE,
            cpu_threads=WHISPER_CPU_THREADS,
            download_root=str(download_root),
        )
        logger.info("faster-whisper model loaded")
    return _whisper_model


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


def transcribe(audio_path: Path) -> TranscriptionResult:
    """Transcribe audio file using faster-whisper with Silero VAD."""
    from config import WHISPER_BEAM_SIZE, VAD_THRESHOLD, VAD_MIN_SPEECH_MS, VAD_MIN_SILENCE_MS

    model = _get_model()

    logger.info(f"Transcribing: {audio_path.name}")
    segments_gen, info = model.transcribe(
        str(audio_path),
        language="en",
        beam_size=WHISPER_BEAM_SIZE,
        word_timestamps=True,
        condition_on_previous_text=False,  # reduces hallucination
        vad_filter=True,
        vad_parameters={
            "threshold": VAD_THRESHOLD,
            "min_speech_duration_ms": VAD_MIN_SPEECH_MS,
            "min_silence_duration_ms": VAD_MIN_SILENCE_MS,
        },
    )

    # faster-whisper returns a generator — consume into list
    segments = []
    for seg in segments_gen:
        words = []
        if seg.words:
            for w in seg.words:
                words.append(WordTimestamp(
                    word=w.word.strip(),
                    start=w.start,
                    end=w.end,
                    probability=w.probability,
                ))
        segments.append(TranscriptSegment(
            start=seg.start,
            end=seg.end,
            text=seg.text.strip(),
            words=words,
        ))

    duration = segments[-1].end if segments else 0.0

    logger.info(f"Transcription complete: {len(segments)} segments, {duration:.1f}s")
    return TranscriptionResult(
        segments=segments,
        language=info.language,
        duration=duration,
    )
