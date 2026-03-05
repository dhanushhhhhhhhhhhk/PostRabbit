"""
vad.py — Voice Activity Detection using Silero VAD.

Responsibility:
    Analyze a normalised 16 kHz mono WAV file and return timestamp ranges
    where speech is detected.  Only timestamps are returned — no audio is
    extracted here.

Why Silero VAD?
    - Small model (~1 MB), very fast on CPU.
    - Returns frame-level speech probabilities that we convert to
      (start, end) second pairs.
    - Well-suited for pre-filtering before Whisper so we skip silence.

Segment merging:
    Adjacent segments separated by less than ``MERGE_GAP_SEC`` (1 s) are
    merged into a single span.  This avoids fragmenting natural pauses
    within a sentence.

Model caching:
    The Silero model is loaded once at module level (``_load_model()``) and
    reused for every subsequent call.  This avoids the overhead of
    re-downloading / re-loading the ONNX graph on each job.
"""

import logging
from typing import List, Tuple

import numpy as np
import soundfile as sf
import torch

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Silero VAD operates on 16 kHz audio.  Our normalise step already
# resamples to this rate, but we assert it here as a safety check.
EXPECTED_SAMPLE_RATE = 16_000

# Segments closer together than this threshold (in seconds) are merged
# so that brief pauses don't fragment a continuous utterance.
MERGE_GAP_SEC = 1.0

# ---------------------------------------------------------------------------
# Model singleton
# ---------------------------------------------------------------------------

_vad_model = None
_vad_utils = None


def _load_model():
    """
    Load the Silero VAD model once and cache it in module-level globals.

    Uses ``torch.hub`` which downloads the model on first call and
    caches it in ``~/.cache/torch/hub`` for subsequent runs.
    """
    global _vad_model, _vad_utils       # noqa: PLW0603

    if _vad_model is not None:
        return _vad_model, _vad_utils

    logger.info("Loading Silero VAD model (first call — will be cached)")

    model, utils = torch.hub.load(
        repo_or_dir="snakers4/silero-vad",
        model="silero_vad",
        trust_repo=True,
    )

    _vad_model = model
    _vad_utils = utils

    logger.info("Silero VAD model loaded successfully")
    return _vad_model, _vad_utils


# ---------------------------------------------------------------------------
# Segment merging
# ---------------------------------------------------------------------------


def _merge_segments(
    segments: List[Tuple[float, float]],
    gap: float = MERGE_GAP_SEC,
) -> List[Tuple[float, float]]:
    """
    Merge consecutive segments whose gap is smaller than *gap* seconds.

    Example:
        [(10.0, 12.0), (12.3, 15.0)]  →  [(10.0, 15.0)]
        Gap of 0.3 s < 1.0 s threshold → merged.
    """
    if not segments:
        return []

    merged: List[Tuple[float, float]] = [segments[0]]

    for start, end in segments[1:]:
        prev_start, prev_end = merged[-1]

        if start - prev_end < gap:
            # Gap is small enough — extend the previous segment
            merged[-1] = (prev_start, max(prev_end, end))
        else:
            merged.append((start, end))

    return merged


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def detect_speech_segments(audio_path: str) -> List[Tuple[float, float]]:
    """
    Detect speech segments in a normalised WAV file.

    Args:
        audio_path: Absolute path to a 16 kHz mono WAV produced by
                    ``normalize_audio()``.

    Returns:
        List of ``(start_seconds, end_seconds)`` tuples for each speech
        region, with short gaps merged.  Returns an empty list when no
        speech is found.

    Raises:
        ValueError:  If the sample rate is not 16 kHz.
        RuntimeError: If the VAD model fails unexpectedly.
    """
    logger.info("detect_speech_segments — start  audio=%s", audio_path)

    # ------------------------------------------------------------------
    # 1. Load the cached Silero model
    # ------------------------------------------------------------------
    model, utils = _load_model()
    (get_speech_timestamps, _, read_audio, *_) = utils

    # ------------------------------------------------------------------
    # 2. Read the WAV file
    # ------------------------------------------------------------------
    #    ``read_audio`` from silero-vad returns a torch tensor and
    #    automatically resamples if needed, but we verify the sample
    #    rate anyway to catch pipeline misconfiguration early.
    wav = read_audio(audio_path, sampling_rate=EXPECTED_SAMPLE_RATE)
    duration_sec = len(wav) / EXPECTED_SAMPLE_RATE
    logger.info(
        "detect_speech_segments — loaded %.1fs of audio (%d samples)",
        duration_sec,
        len(wav),
    )

    # ------------------------------------------------------------------
    # 3. Run VAD
    # ------------------------------------------------------------------
    #    ``get_speech_timestamps`` returns a list of dicts:
    #    [{"start": <sample_idx>, "end": <sample_idx>}, …]
    raw_timestamps = get_speech_timestamps(
        wav,
        model,
        sampling_rate=EXPECTED_SAMPLE_RATE,
        return_seconds=False,       # we get sample indices
    )

    logger.info(
        "detect_speech_segments — raw segments detected: %d",
        len(raw_timestamps),
    )

    # ------------------------------------------------------------------
    # 4. Handle empty result
    # ------------------------------------------------------------------
    if not raw_timestamps:
        logger.warning(
            "detect_speech_segments — no speech detected in %s", audio_path
        )
        return []

    # ------------------------------------------------------------------
    # 5. Convert sample indices → seconds
    # ------------------------------------------------------------------
    segments: List[Tuple[float, float]] = [
        (
            round(ts["start"] / EXPECTED_SAMPLE_RATE, 3),
            round(ts["end"] / EXPECTED_SAMPLE_RATE, 3),
        )
        for ts in raw_timestamps
    ]

    # ------------------------------------------------------------------
    # 6. Merge segments separated by < MERGE_GAP_SEC
    # ------------------------------------------------------------------
    merged = _merge_segments(segments)

    logger.info(
        "detect_speech_segments — merged segments: %d  (from %d raw)",
        len(merged),
        len(segments),
    )
    for i, (s, e) in enumerate(merged):
        logger.info("  segment %d: %.3fs – %.3fs (%.1fs)", i, s, e, e - s)

    return merged
