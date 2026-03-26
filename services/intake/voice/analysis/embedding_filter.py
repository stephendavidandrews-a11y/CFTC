"""Quality-filtered speaker embedding extraction.

Scores each diarization segment's audio quality using vocal features,
selects the best segments (up to 40s), and computes a clean embedding
from only those segments using pyannote's wespeaker model.

This replaces pyannote's whole-recording embedding with one derived
from only high-quality audio, preventing noisy/muffled sections from
contaminating the voiceprint.
"""

import logging
from pathlib import Path

import numpy as np
import torch

logger = logging.getLogger(__name__)

_embedding_model = None
_embedding_inference = None

# Quality thresholds (same as quality_gate.py config values)
MIN_HNR_DB = 10.0
MAX_JITTER = 0.02
MAX_SHIMMER = 0.05
MIN_SEGMENT_DURATION = 3.0
TARGET_DURATION = 40.0


def _get_embedding_model():
    """Lazy-load the wespeaker embedding model."""
    global _embedding_model, _embedding_inference
    if _embedding_model is None:
        from pyannote.audio import Model, Inference

        logger.info("Loading wespeaker embedding model for quality-filtered extraction")
        _embedding_model = Model.from_pretrained(
            "pyannote/wespeaker-voxceleb-resnet34-LM", token=False
        )
        if torch.backends.mps.is_available():
            _embedding_model.to(torch.device("mps"))
        _embedding_inference = Inference(_embedding_model, window="whole")
        logger.info("wespeaker embedding model loaded")
    return _embedding_inference


def compute_filtered_embeddings(
    audio_path: Path,
    speaker_segments: dict[str, list[dict]],
    speaker_features: dict[str, list[dict]],
    raw_embeddings: dict[str, np.ndarray],
) -> dict[str, dict]:
    """Compute quality-filtered embeddings for each speaker.

    Args:
        audio_path: Path to 16kHz mono WAV.
        speaker_segments: {speaker_label: [{start, end}, ...]}
        speaker_features: {speaker_label: [{start, end, features: {...}}, ...]}
            Per-segment vocal features from the analyzer.
        raw_embeddings: {speaker_label: np.ndarray} from pyannote diarization.

    Returns:
        {speaker_label: {
            "embedding": np.ndarray (filtered, or raw fallback),
            "quality_score": float (0-1),
            "clean_duration": float (seconds of clean audio used),
            "total_duration": float (total speech duration),
            "segments_used": int,
            "segments_total": int,
            "filtered": bool (True if filtered embedding was computed),
        }}
    """
    import librosa

    results = {}
    y_full, sr = librosa.load(str(audio_path), sr=16000, mono=True)

    for speaker_label in speaker_segments:
        segs = speaker_segments[speaker_label]
        feats = speaker_features.get(speaker_label, [])

        total_duration = sum(s["end"] - s["start"] for s in segs)

        # Build scored segments: pair each segment with its vocal features
        scored = []
        for i, seg in enumerate(segs):
            duration = seg["end"] - seg["start"]
            if duration < MIN_SEGMENT_DURATION:
                continue

            # Find matching features
            seg_feats = {}
            for f in feats:
                if (
                    abs(f["start"] - seg["start"]) < 0.1
                    and abs(f["end"] - seg["end"]) < 0.1
                ):
                    seg_feats = f.get("features", {})
                    break

            # Score the segment
            score, issues = _score_segment(seg_feats)
            scored.append(
                {
                    "start": seg["start"],
                    "end": seg["end"],
                    "duration": duration,
                    "score": score,
                    "issues": issues,
                    "hnr": seg_feats.get("hnr"),
                }
            )

        # Sort by quality score descending, then select best up to TARGET_DURATION
        scored.sort(key=lambda s: s["score"], reverse=True)

        selected = []
        clean_duration = 0.0
        for seg in scored:
            if clean_duration >= TARGET_DURATION:
                break
            if seg["score"] > 0:  # Only use segments that passed at least some checks
                selected.append(seg)
                clean_duration += seg["duration"]

        if clean_duration < MIN_SEGMENT_DURATION or not selected:
            # Not enough clean audio -- fall back to raw pyannote embedding
            raw = raw_embeddings.get(speaker_label)
            results[speaker_label] = {
                "embedding": raw,
                "quality_score": 0.0,
                "clean_duration": 0.0,
                "total_duration": total_duration,
                "segments_used": 0,
                "segments_total": len(segs),
                "filtered": False,
            }
            logger.warning(
                f"[{speaker_label}] No clean audio for filtered embedding "
                f"({clean_duration:.1f}s clean / {total_duration:.1f}s total). Using raw."
            )
            continue

        # Extract audio for selected segments and compute embedding
        try:
            embedding = _compute_embedding_from_segments(y_full, sr, selected)
            quality_score = min(1.0, clean_duration / 30.0)

            results[speaker_label] = {
                "embedding": embedding,
                "quality_score": quality_score,
                "clean_duration": clean_duration,
                "total_duration": total_duration,
                "segments_used": len(selected),
                "segments_total": len(segs),
                "filtered": True,
            }
            logger.info(
                f"[{speaker_label}] Filtered embedding: "
                f"{len(selected)}/{len(segs)} segments, "
                f"{clean_duration:.1f}s clean / {total_duration:.1f}s total, "
                f"quality={quality_score:.2f}"
            )
        except Exception as e:
            # Fall back to raw embedding on any error
            raw = raw_embeddings.get(speaker_label)
            results[speaker_label] = {
                "embedding": raw,
                "quality_score": 0.0,
                "clean_duration": 0.0,
                "total_duration": total_duration,
                "segments_used": 0,
                "segments_total": len(segs),
                "filtered": False,
            }
            logger.warning(
                f"[{speaker_label}] Filtered embedding failed ({e}). Using raw."
            )

    return results


def _score_segment(features: dict) -> tuple[float, list[str]]:
    """Score a segment's audio quality. Returns (score 0-1, list of issues)."""
    if not features:
        return 0.5, ["no features"]  # Unknown quality, give benefit of doubt

    score = 1.0
    issues = []

    hnr = features.get("hnr")
    if hnr is not None:
        if hnr < MIN_HNR_DB:
            score -= 0.4
            issues.append(f"low HNR ({hnr:.1f}dB)")
        elif hnr >= 15:
            score += 0.1  # Bonus for very clean audio

    jitter = features.get("jitter")
    if jitter is not None and jitter > MAX_JITTER:
        score -= 0.3
        issues.append(f"high jitter ({jitter:.3f})")

    shimmer = features.get("shimmer")
    if shimmer is not None and shimmer > MAX_SHIMMER:
        score -= 0.3
        issues.append(f"high shimmer ({shimmer:.3f})")

    return max(0.0, min(1.0, score)), issues


def _compute_embedding_from_segments(
    y_full: np.ndarray, sr: int, segments: list[dict]
) -> np.ndarray:
    """Extract and concatenate clean segments, compute speaker embedding.

    Uses pyannote's wespeaker model with in-memory waveform (bypasses torchcodec).
    """
    inference = _get_embedding_model()

    # Concatenate selected segments
    chunks = []
    for seg in segments:
        start_sample = int(seg["start"] * sr)
        end_sample = int(seg["end"] * sr)
        chunk = y_full[start_sample:end_sample]
        if len(chunk) > 0:
            chunks.append(chunk)

    if not chunks:
        raise ValueError("No audio chunks to process")

    concatenated = np.concatenate(chunks)
    waveform = torch.from_numpy(concatenated).unsqueeze(0).float()

    # Pass as in-memory dict (bypasses torchcodec file loading)
    audio_input = {"waveform": waveform, "sample_rate": sr}
    embedding = inference(audio_input)

    # L2 normalize
    norm = np.linalg.norm(embedding)
    if norm > 0:
        embedding = embedding / norm

    return embedding.flatten()
