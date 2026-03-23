"""Forced alignment -- wav2vec2 via whisperx + speaker assignment + overlap detection.

Replaces the old overlap-based aligner with phoneme-level forced alignment
for accurate word-level timestamps, then assigns speakers at the word level
using whisperx.assign_word_speakers().

Overlap handling: pyannote 3.1 natively detects overlapping speech (up to 2
speakers simultaneously). Words in overlap regions keep their single speaker
attribution (whoever whisperx assigned) but get flagged as overlap. The
overlap regions are stored separately for the UI to display indicators.
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path


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
    is_overlap: bool = False


@dataclass
class AlignedSegment:
    speaker: str
    start: float
    end: float
    text: str
    words: list[AlignedWord] = field(default_factory=list)
    is_overlap: bool = False


@dataclass
class OverlapRegion:
    start: float
    end: float
    speakers: list[str]


@dataclass
class AlignedTranscript:
    segments: list[AlignedSegment]
    speakers: list[str]
    duration: float
    overlap_regions: list[OverlapRegion] = field(default_factory=list)


def _diarization_to_dataframe(diarization: DiarizationResult):
    """Convert DiarizationResult to pandas DataFrame for whisperx."""
    import pandas as pd
    rows = []
    for seg in diarization.segments:
        rows.append({"start": seg.start, "end": seg.end, "speaker": seg.speaker})
    return pd.DataFrame(rows)


def _detect_overlap_regions(diarization: DiarizationResult) -> list[OverlapRegion]:
    """Detect time regions where 2+ speakers are active simultaneously.

    pyannote 3.1 outputs overlapping segments for different speakers.
    We find all time regions where segments from different speakers overlap.
    """
    if len(diarization.segments) < 2:
        return []

    sorted_segs = sorted(diarization.segments, key=lambda s: s.start)
    overlaps = []

    for i, seg_a in enumerate(sorted_segs):
        for seg_b in sorted_segs[i + 1:]:
            if seg_b.start >= seg_a.end:
                break
            if seg_a.speaker == seg_b.speaker:
                continue

            overlap_start = max(seg_a.start, seg_b.start)
            overlap_end = min(seg_a.end, seg_b.end)
            if overlap_end > overlap_start:
                overlaps.append(OverlapRegion(
                    start=overlap_start,
                    end=overlap_end,
                    speakers=sorted([seg_a.speaker, seg_b.speaker]),
                ))

    if not overlaps:
        return []

    # Merge adjacent overlap regions with same speaker pair
    overlaps.sort(key=lambda o: o.start)
    merged = [overlaps[0]]
    for o in overlaps[1:]:
        prev = merged[-1]
        if o.start <= prev.end and o.speakers == prev.speakers:
            prev.end = max(prev.end, o.end)
        else:
            merged.append(o)

    logger.info(f"Detected {len(merged)} overlap regions")
    return merged


def _word_in_overlap(word_start: float, word_end: float, overlaps: list[OverlapRegion]) -> bool:
    """Check if a word falls within any overlap region."""
    word_mid = (word_start + word_end) / 2
    for o in overlaps:
        if o.start <= word_mid <= o.end:
            return True
    return False


def align(
    transcription: TranscriptionResult,
    diarization: DiarizationResult,
    audio_path: Path,
) -> AlignedTranscript:
    """Align transcript with forced alignment and assign speakers at word level.

    Words in overlap regions keep their single speaker attribution but are
    flagged with is_overlap=True. Overlap regions are stored separately.
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

    # Stage 3: Detect overlap regions from pyannote output
    overlap_regions = _detect_overlap_regions(diarization)

    # Stage 4: Convert to our dataclasses, flagging overlaps
    output_segments = []
    speakers_set = set()
    overlap_word_count = 0

    for seg in aligned_result.get("segments", []):
        speaker = seg.get("speaker", "UNKNOWN")
        speakers_set.add(speaker)

        words = []
        seg_has_overlap = False
        for w in seg.get("words", []):
            w_speaker = w.get("speaker", speaker)
            w_start = w.get("start", seg.get("start", 0.0))
            w_end = w.get("end", seg.get("end", 0.0))
            w_overlap = _word_in_overlap(w_start, w_end, overlap_regions) if overlap_regions else False

            if w_overlap:
                overlap_word_count += 1
                seg_has_overlap = True

            words.append(AlignedWord(
                word=w.get("word", "").strip(),
                start=w_start,
                end=w_end,
                speaker=w_speaker,
                probability=w.get("score", 0.0),
                is_overlap=w_overlap,
            ))
            speakers_set.add(w_speaker)

        output_segments.append(AlignedSegment(
            speaker=speaker,
            start=seg.get("start", 0.0),
            end=seg.get("end", 0.0),
            text=seg.get("text", "").strip(),
            words=words,
            is_overlap=seg_has_overlap,
        ))

    # Re-group by speaker boundaries
    regrouped = _regroup_by_speaker(output_segments)
    speakers = sorted(speakers_set - {"UNKNOWN"}) or sorted(speakers_set)

    logger.info(
        f"Alignment complete: {len(regrouped)} segments, "
        f"{len(speakers)} speakers, "
        f"{len(overlap_regions)} overlap regions, "
        f"{overlap_word_count} words in overlap"
    )

    return AlignedTranscript(
        segments=regrouped,
        speakers=speakers,
        duration=transcription.duration,
        overlap_regions=overlap_regions,
    )


def _regroup_by_speaker(segments: list[AlignedSegment]) -> list[AlignedSegment]:
    """Re-group segments so each has a single consistent speaker."""
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
            has_overlap = any(w.is_overlap for w in current_words)
            regrouped.append(AlignedSegment(
                speaker=current_speaker,
                start=current_words[0].start,
                end=current_words[-1].end,
                text=" ".join(w.word for w in current_words),
                words=current_words,
                is_overlap=has_overlap,
            ))
            current_speaker = word.speaker
            current_words = [word]

    if current_words:
        has_overlap = any(w.is_overlap for w in current_words)
        regrouped.append(AlignedSegment(
            speaker=current_speaker,
            start=current_words[0].start,
            end=current_words[-1].end,
            text=" ".join(w.word for w in current_words),
            words=current_words,
            is_overlap=has_overlap,
        ))

    return regrouped
