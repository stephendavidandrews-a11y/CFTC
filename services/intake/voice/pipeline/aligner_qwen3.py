"""Speaker assignment and overlap detection -- pyannote-based.

Assigns speakers to Qwen3-ASR word-level timestamps using pyannote's
exclusive_speaker_diarization (one speaker per time point). Detects
overlap regions from pyannote's regular diarization segments.

Replaces the whisperx-based aligner (wav2vec2 forced alignment +
whisperx.assign_word_speakers). Since Qwen3-ASR produces word-level
timestamps natively via its built-in ForcedAligner, wav2vec2 is no
longer needed.
"""

import bisect
import logging
from dataclasses import dataclass, field

from .transcriber_qwen3 import TranscriptionResult
from .diarizer import DiarizationResult

logger = logging.getLogger(__name__)


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


def _assign_speaker_at_time(
    time_point: float,
    exclusive_segments: list,
) -> str:
    """Find which speaker owns a given time point using exclusive diarization.

    Uses bisect for O(log n) lookup on sorted segments.
    Falls back to UNKNOWN if no segment covers the point.
    """
    if not exclusive_segments:
        return "UNKNOWN"

    # bisect on segment start times to find candidate
    starts = [s.start for s in exclusive_segments]
    idx = bisect.bisect_right(starts, time_point) - 1

    if idx >= 0 and exclusive_segments[idx].start <= time_point <= exclusive_segments[idx].end:
        return exclusive_segments[idx].speaker

    # Check idx+1 in case of floating point edge
    if idx + 1 < len(exclusive_segments) and exclusive_segments[idx + 1].start <= time_point <= exclusive_segments[idx + 1].end:
        return exclusive_segments[idx + 1].speaker

    # Fallback: find nearest segment within 1s tolerance
    nearest = min(exclusive_segments, key=lambda s: abs((s.start + s.end) / 2 - time_point))
    if abs(nearest.start - time_point) < 1.0 or abs(nearest.end - time_point) < 1.0:
        return nearest.speaker

    return "UNKNOWN"


def _detect_overlap_regions(diarization: DiarizationResult) -> list[OverlapRegion]:
    """Detect time regions where 2+ speakers are active simultaneously.

    Uses the REGULAR (non-exclusive) diarization segments, which preserve
    overlapping speaker turns.
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


def _word_in_overlap(
    word_start: float, word_end: float, overlaps: list[OverlapRegion]
) -> bool:
    """Check if a word falls within any overlap region."""
    word_mid = (word_start + word_end) / 2
    for o in overlaps:
        if o.start <= word_mid <= o.end:
            return True
    return False


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


def align(
    transcription: TranscriptionResult,
    diarization: DiarizationResult,
) -> AlignedTranscript:
    """Assign speakers to transcription words and detect overlaps.

    Uses pyannote's exclusive_speaker_diarization for word->speaker
    assignment (one speaker per time point). Uses regular diarization
    for overlap detection.

    Note: audio_path is NOT needed (unlike the whisperx aligner).
    Qwen3-ASR already provides word-level timestamps.
    """
    # Use exclusive segments for speaker assignment, fall back to regular
    speaker_segments = diarization.exclusive_segments or diarization.segments

    # Detect overlaps from regular (overlapping) diarization
    overlap_regions = _detect_overlap_regions(diarization)

    # Assign speakers to each word
    speakers_set = set()
    output_segments = []

    for seg in transcription.segments:
        words = []
        for w in seg.words:
            word_mid = (w.start + w.end) / 2
            speaker = _assign_speaker_at_time(word_mid, speaker_segments)
            speakers_set.add(speaker)

            is_overlap = _word_in_overlap(w.start, w.end, overlap_regions) if overlap_regions else False

            words.append(AlignedWord(
                word=w.word,
                start=w.start,
                end=w.end,
                speaker=speaker,
                probability=w.probability,
                is_overlap=is_overlap,
            ))

        seg_speaker = words[0].speaker if words else "UNKNOWN"
        seg_has_overlap = any(w.is_overlap for w in words)

        output_segments.append(AlignedSegment(
            speaker=seg_speaker,
            start=seg.start,
            end=seg.end,
            text=seg.text,
            words=words,
            is_overlap=seg_has_overlap,
        ))

    # Regroup by speaker boundaries
    regrouped = _regroup_by_speaker(output_segments)
    speakers = sorted(speakers_set - {"UNKNOWN"}) or sorted(speakers_set)

    logger.info(
        f"Alignment complete: {len(regrouped)} segments, "
        f"{len(speakers)} speakers, "
        f"{len(overlap_regions)} overlap regions"
    )

    return AlignedTranscript(
        segments=regrouped,
        speakers=speakers,
        duration=transcription.duration,
        overlap_regions=overlap_regions,
    )
