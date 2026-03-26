"""pyannote speaker diarization module.

Uses pyannote/speaker-diarization-3.1 for speaker segmentation.
Extracts speaker embeddings for voiceprint matching.
"""

import logging
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import torch

logger = logging.getLogger(__name__)

_diarization_pipeline = None


def _get_pipeline():
    """Load and tune the pyannote diarization pipeline."""
    global _diarization_pipeline
    if _diarization_pipeline is None:
        from pyannote.audio import Pipeline
        from config import PYANNOTE_PIPELINE, DIARIZATION_CLUSTERING_THRESHOLD

        logger.info(f"Loading pyannote pipeline: {PYANNOTE_PIPELINE}")

        import os

        hf_token = os.environ.get("HF_TOKEN")
        if hf_token:
            _diarization_pipeline = Pipeline.from_pretrained(
                PYANNOTE_PIPELINE, token=hf_token
            )
        else:
            logger.info("HF_TOKEN not set — loading pyannote from local cache")
            _diarization_pipeline = Pipeline.from_pretrained(
                PYANNOTE_PIPELINE, token=False
            )

        if DIARIZATION_CLUSTERING_THRESHOLD is not None:
            try:
                params = _diarization_pipeline.parameters(instantiated=True)
                old_threshold = params["clustering"]["threshold"]
                params["clustering"]["threshold"] = DIARIZATION_CLUSTERING_THRESHOLD
                _diarization_pipeline.instantiate(params)
                logger.info(
                    f"Clustering threshold: {old_threshold:.4f} -> "
                    f"{DIARIZATION_CLUSTERING_THRESHOLD} (lower = more speakers)"
                )
            except Exception as e:
                logger.warning(
                    f"Could not set clustering threshold: {e} — using pipeline default"
                )

        if torch.backends.mps.is_available():
            _diarization_pipeline.to(torch.device("mps"))
            logger.info("pyannote using Metal (MPS) acceleration")
        else:
            logger.info("pyannote using CPU")

    return _diarization_pipeline


@dataclass
class SpeakerSegment:
    speaker: str
    start: float
    end: float


@dataclass
class SpeakerEmbedding:
    speaker: str
    embedding: np.ndarray


@dataclass
class DiarizationResult:
    segments: list[SpeakerSegment]
    embeddings: dict[str, np.ndarray]
    num_speakers: int

    def to_dataframe(self):
        """Convert to pandas DataFrame for whisperx speaker assignment."""
        import pandas as pd

        rows = [
            {"start": s.start, "end": s.end, "speaker": s.speaker}
            for s in self.segments
        ]
        return pd.DataFrame(rows)


def diarize(
    audio_path: Path,
    min_speakers: int | None = None,
    max_speakers: int | None = None,
) -> DiarizationResult:
    """Run speaker diarization on audio file."""
    from config import DIARIZATION_MIN_SPEAKERS, DIARIZATION_MAX_SPEAKERS

    pipeline = _get_pipeline()

    if min_speakers is None:
        min_speakers = DIARIZATION_MIN_SPEAKERS
    if max_speakers is None:
        max_speakers = DIARIZATION_MAX_SPEAKERS

    logger.info(
        f"Diarizing: {audio_path.name} "
        f"(min_speakers={min_speakers}, max_speakers={max_speakers})"
    )

    kwargs = {}
    if min_speakers is not None:
        kwargs["min_speakers"] = min_speakers
    if max_speakers is not None:
        kwargs["max_speakers"] = max_speakers

    result = pipeline(str(audio_path), **kwargs)

    if hasattr(result, "speaker_diarization"):
        annotation = result.speaker_diarization
    else:
        annotation = result

    segments = []
    for turn, _, speaker in annotation.itertracks(yield_label=True):
        segments.append(
            SpeakerSegment(
                speaker=speaker,
                start=turn.start,
                end=turn.end,
            )
        )

    embeddings = _extract_embeddings(result, segments)

    speakers = set(s.speaker for s in segments)
    logger.info(
        f"Diarization complete: {len(speakers)} speakers, {len(segments)} segments"
    )

    return DiarizationResult(
        segments=segments,
        embeddings=embeddings,
        num_speakers=len(speakers),
    )


def _extract_embeddings(
    result, segments: list[SpeakerSegment]
) -> dict[str, np.ndarray]:
    """Extract per-speaker embeddings from diarization result."""
    try:
        if (
            hasattr(result, "speaker_embeddings")
            and result.speaker_embeddings is not None
        ):
            emb_array = result.speaker_embeddings
            speaker_labels = sorted(set(s.speaker for s in segments))
            embeddings = {}
            for i, label in enumerate(speaker_labels):
                if i < len(emb_array):
                    embeddings[label] = emb_array[i]
            logger.info(
                f"Speaker embeddings extracted: {len(embeddings)} speakers, dim={emb_array.shape[1]}"
            )
            return embeddings
        else:
            logger.warning("No speaker embeddings available from diarization result")
            return {}
    except Exception:
        logger.exception("Failed to extract speaker embeddings")
        return {}
