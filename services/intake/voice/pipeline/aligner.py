"""Forced alignment — wav2vec2 via whisperx + speaker assignment.

Replaces the old overlap-based aligner with phoneme-level forced alignment
for accurate word-level timestamps, then assigns speakers at the word level
using whisperx.assign_word_speakers().
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from .transcriber import TranscriptionResult
from .diarizer import DiarizationResult

logger = logging.getLogger(__name__)

_align_model = None
_align_metadata = None


def _get_align_model():
    """Lazy-load the wav2vec2 alignment model."""
    global _align_model, _align_metadata
    if _align_model is None:
        import whisperx
        from config import ALIGNMENT_DEVICE
        logger.info(f"Loading wav2vec2 alignment model on {ALIGNMENT_DEVICE}")
        _align_model, _align_metadata = whisperx.load_align_model(
            language_code="en",
            device=ALIGNMENT_DEVICE,
        )
        logger.info("wav2vec2 alignment model loaded")
    return _align_model, _align_metadata


@dataclass
class AlignedWord:
    word: str
    start: float
    end: float
    speaker: str
    probability: float


@dataclass
class AlignedSegment:
    speaker: str
    start: float
    end: float
    text: str
    words: list[AlignedWord] = field(default_factory=list)


@dataclass
class AlignedTranscript:
    segments: list[AlignedSegment]
    speakers: list[str]
    duration: float


def _diarization_to_dataframe(diarization: DiarizationResult):
    """Convert DiarizationResult to pandas DataFrame for whisperx."""
    import pandas as pd
    rows = []
    for seg in diarization.segments:
        rows.append({"start": seg.start, "end": seg.end, "speaker": seg.speaker})
    return pd.DataFrame(rows)


def align(
    transcription: TranscriptionResult,
    diarization: DiarizationResult,
    audio_path: Path,
) -> AlignedTranscript:
    """Align transcript with forced alignment and assign speakers at word level.

    Args:
        transcription: Whisper transcription result.
        diarization: pyannote diarization result.
        audio_path: Path to preprocessed audio (16kHz mono WAV).

    Returns:
        AlignedTranscript with word-level speaker labels.
    """
    import whisperx

    model_a, metadata = _get_align_model()

    # Convert transcription to whisperx format
    transcript_segments = []
    for seg in transcription.segments:
        transcript_segments.append({
            "start": seg.start,
            "end": seg.end,
            "text": seg.text,
        })

    # Stage 1: Forced alignment (wav2vec2)
    logger.info("Running wav2vec2 forced alignment...")
    from config import ALIGNMENT_DEVICE
    audio = whisperx.load_audio(str(audio_path))
    aligned_result = whisperx.align(
        transcript_segments,
        model_a,
        metadata,
        audio,
        device=ALIGNMENT_DEVICE,
    )

    # Stage 2: Speaker assignment at word level
    logger.info("Assigning speakers to words...")
    diarize_df = _diarization_to_dataframe(diarization)
    if not diarize_df.empty:
        aligned_result = whisperx.assign_word_speakers(diarize_df, aligned_result)

    # Convert to our dataclasses
    output_segments = []
    speakers_set = set()

    for seg in aligned_result.get("segments", []):
        speaker = seg.get("speaker", "UNKNOWN")
        speakers_set.add(speaker)

        words = []
        for w in seg.get("words", []):
            w_speaker = w.get("speaker", speaker)
            words.append(AlignedWord(
                word=w.get("word", "").strip(),
                start=w.get("start", seg.get("start", 0.0)),
                end=w.get("end", seg.get("end", 0.0)),
                speaker=w_speaker,
                probability=w.get("score", 0.0),
            ))
            speakers_set.add(w_speaker)

        output_segments.append(AlignedSegment(
            speaker=speaker,
            start=seg.get("start", 0.0),
            end=seg.get("end", 0.0),
            text=seg.get("text", "").strip(),
            words=words,
        ))

    # Re-group by speaker boundaries (whisperx may have mixed speakers within a segment)
    regrouped = _regroup_by_speaker(output_segments)
    speakers = sorted(speakers_set - {"UNKNOWN"}) or sorted(speakers_set)

    logger.info(
        f"Alignment complete: {len(regrouped)} segments, "
        f"{len(speakers)} speakers"
    )

    return AlignedTranscript(
        segments=regrouped,
        speakers=speakers,
        duration=transcription.duration,
    )


def _regroup_by_speaker(segments: list[AlignedSegment]) -> list[AlignedSegment]:
    """Re-group segments so each has a single consistent speaker.

    whisperx.assign_word_speakers can assign different speakers to words
    within the same segment. This splits those into separate segments.
    """
    all_words = []
    for seg in segments:
        all_words.extend(seg.words)

    if not all_words:
        return segments

    regrouped = []
    current_speaker = all_words[0].speaker
    current_words = [all_words[0]]

    for word in all_words[1:]:
        if word.speaker == current_speaker:
            current_words.append(word)
        else:
            regrouped.append(AlignedSegment(
                speaker=current_speaker,
                start=current_words[0].start,
                end=current_words[-1].end,
                text=" ".join(w.word for w in current_words),
                words=current_words,
            ))
            current_speaker = word.speaker
            current_words = [word]

    if current_words:
        regrouped.append(AlignedSegment(
            speaker=current_speaker,
            start=current_words[0].start,
            end=current_words[-1].end,
            text=" ".join(w.word for w in current_words),
            words=current_words,
        ))

    return regrouped
