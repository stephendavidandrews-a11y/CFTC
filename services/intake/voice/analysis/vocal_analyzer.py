"""Vocal analysis — Parselmouth + librosa feature extraction.

Extracts 25+ acoustic features per speaker segment for prosodic analysis,
voice quality metrics, stress detection, and baseline comparison.
"""

import json
import logging
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)


def extract_vocal_features(audio_path: Path, start: float, end: float) -> dict:
    """Extract vocal features from an audio segment.

    Args:
        audio_path: Path to the full audio file.
        start: Segment start time in seconds.
        end: Segment end time in seconds.

    Returns:
        Dict of extracted features. Empty dict if segment too short.
    """
    import parselmouth
    from parselmouth.praat import call
    import librosa

    y, sr = librosa.load(str(audio_path), sr=None, offset=start, duration=end - start)

    if len(y) < sr * 0.3:
        return {}

    features = {}

    # === Parselmouth features ===
    try:
        snd = parselmouth.Sound(y.astype(np.float64), sampling_frequency=sr)

        # Pitch
        pitch = call(snd, "To Pitch", 0.0, 75, 600)
        features["pitch_mean"] = call(pitch, "Get mean", 0, 0, "Hertz")
        features["pitch_std"] = call(pitch, "Get standard deviation", 0, 0, "Hertz")
        features["pitch_min"] = call(pitch, "Get minimum", 0, 0, "Hertz", "Parabolic")
        features["pitch_max"] = call(pitch, "Get maximum", 0, 0, "Hertz", "Parabolic")

        # Jitter and Shimmer
        point_process = call(snd, "To PointProcess (periodic, cc)", 75, 600)
        features["jitter"] = call(
            point_process, "Get jitter (local)", 0, 0, 0.0001, 0.02, 1.3
        )
        features["shimmer"] = call(
            [snd, point_process], "Get shimmer (local)", 0, 0, 0.0001, 0.02, 1.3, 1.6
        )

        # HNR
        harmonicity = call(snd, "To Harmonicity (cc)", 0.01, 75, 0.1, 1.0)
        features["hnr"] = call(harmonicity, "Get mean", 0, 0)

        # Intensity
        intensity = call(snd, "To Intensity", 75, 0, "yes")
        features["intensity_mean"] = call(intensity, "Get mean", 0, 0, "energy")

        # Formants F1-F3
        formant = call(snd, "To Formant (burg)", 0.0, 5, 5500, 0.025, 50)
        features["f1_mean"] = call(formant, "Get mean", 1, 0, 0, "Hertz")
        features["f2_mean"] = call(formant, "Get mean", 2, 0, 0, "Hertz")
        features["f3_mean"] = call(formant, "Get mean", 3, 0, 0, "Hertz")
    except Exception:
        logger.debug("Parselmouth extraction partially failed", exc_info=True)

    # === librosa features ===
    try:
        # MFCCs
        mfccs = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13)
        features["mfcc_means"] = json.dumps(np.mean(mfccs, axis=1).tolist())

        # RMS energy
        rms = librosa.feature.rms(y=y)
        features["rms_mean"] = float(np.mean(rms))

        # Spectral centroid
        sc = librosa.feature.spectral_centroid(y=y, sr=sr)
        features["spectral_centroid"] = float(np.mean(sc))

        # Zero-crossing rate
        zcr = librosa.feature.zero_crossing_rate(y)
        features["zcr_mean"] = float(np.mean(zcr))

        # Spectral rolloff
        rolloff = librosa.feature.spectral_rolloff(y=y, sr=sr)
        features["spectral_rolloff"] = float(np.mean(rolloff))

        # Speaking rate (approximate via onset detection)
        onsets = librosa.onset.onset_detect(y=y, sr=sr)
        duration = end - start
        if duration > 0:
            features["speaking_rate_wpm"] = len(onsets) / duration * 60
    except Exception:
        logger.debug("librosa extraction partially failed", exc_info=True)

    # Replace NaN/Inf with None
    for key, value in features.items():
        if isinstance(value, float) and (np.isnan(value) or np.isinf(value)):
            features[key] = None

    return features


def aggregate_speaker_features(
    audio_path: Path,
    segments: list[dict],
    min_segment_seconds: float = 5.0,
) -> dict:
    """Aggregate vocal features across all segments for one speaker.

    Args:
        audio_path: Path to audio file.
        segments: List of dicts with "start" and "end" keys.
        min_segment_seconds: Minimum total speech to analyze.

    Returns:
        Aggregated features dict, or empty dict if insufficient speech.
    """
    total_speech = sum(s["end"] - s["start"] for s in segments)
    if total_speech < min_segment_seconds:
        return {}

    all_features = []
    for seg in segments:
        features = extract_vocal_features(audio_path, seg["start"], seg["end"])
        if features:
            all_features.append(features)

    if not all_features:
        return {}

    # Average numeric features across segments
    aggregated = {}
    numeric_keys = [
        "pitch_mean",
        "pitch_std",
        "pitch_min",
        "pitch_max",
        "jitter",
        "shimmer",
        "hnr",
        "intensity_mean",
        "f1_mean",
        "f2_mean",
        "f3_mean",
        "rms_mean",
        "spectral_centroid",
        "zcr_mean",
        "spectral_rolloff",
        "speaking_rate_wpm",
    ]

    for key in numeric_keys:
        values = [f[key] for f in all_features if key in f and f[key] is not None]
        if values:
            aggregated[key] = sum(values) / len(values)

    # Average MFCCs
    mfcc_lists = []
    for f in all_features:
        if "mfcc_means" in f and f["mfcc_means"]:
            try:
                mfcc_lists.append(json.loads(f["mfcc_means"]))
            except (json.JSONDecodeError, TypeError):
                pass
    if mfcc_lists:
        avg_mfccs = np.mean(mfcc_lists, axis=0).tolist()
        aggregated["mfcc_means"] = json.dumps(avg_mfccs)

    return aggregated
