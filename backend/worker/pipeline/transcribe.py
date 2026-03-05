"""
transcribe.py — Transcribe speech segments using the Whisper API.

Responsibility:
    Given a normalised WAV file and a list of (start, end) speech segment
    timestamps from the VAD step, extract each segment into a temporary
    file, send it to the OpenAI Whisper API, and return a single merged
    transcript string.

Workflow:
    1. For each segment, cut a temporary WAV slice via ffmpeg.
    2. POST each slice to the Whisper ``/v1/audio/transcriptions`` endpoint.
    3. Concatenate the per-segment transcripts in chronological order.
    4. Clean up all temporary slice files.

Error handling:
    If a single segment fails (API error, network issue, etc.) it is logged
    and skipped.  The remaining segments are still transcribed so that a
    partial transcript is returned rather than nothing.
"""

import logging
import os
import subprocess
from pathlib import Path
from typing import List, Tuple

import requests

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Whisper API endpoint (OpenAI-compatible)
WHISPER_API_URL = "https://api.openai.com/v1/audio/transcriptions"

# Model identifier recognised by the endpoint
WHISPER_MODEL = "whisper-1"


def _get_api_key() -> str:
    """
    Read the Whisper API key from the environment.

    Loaded lazily (not at import time) so that worker code that doesn’t
    call this module is unaffected if the variable is missing.
    """
    key = os.getenv("WHISPER_API_KEY", "")
    if not key:
        raise RuntimeError(
            "WHISPER_API_KEY environment variable is not set.  "
            "Cannot call the Whisper transcription API."
        )
    return key


# ---------------------------------------------------------------------------
# Segment extraction
# ---------------------------------------------------------------------------


def _extract_segment(
    audio_path: str,
    start: float,
    end: float,
    index: int,
) -> str:
    """
    Cut a time-range from *audio_path* into a standalone WAV file.

    Uses ffmpeg::

        ffmpeg -y -i audio.wav -ss START -to END segment_X.wav

    Args:
        audio_path: Source normalised WAV.
        start:      Segment start in seconds.
        end:        Segment end in seconds.
        index:      Segment ordinal (used in the filename).

    Returns:
        Absolute path to the extracted segment file.

    Raises:
        RuntimeError: If ffmpeg exits with a non-zero code.
    """
    parent = str(Path(audio_path).parent)
    stem = Path(audio_path).stem
    segment_path = os.path.join(parent, f"{stem}_segment_{index}.wav")

    cmd = [
        "ffmpeg",
        "-y",
        "-i", audio_path,
        "-ss", str(start),
        "-to", str(end),
        segment_path,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        raise RuntimeError(
            f"ffmpeg segment extraction failed (exit {result.returncode}): "
            f"{result.stderr.strip()}"
        )

    return segment_path


# ---------------------------------------------------------------------------
# Single-segment transcription
# ---------------------------------------------------------------------------


def _transcribe_file(file_path: str, api_key: str) -> str:
    """
    Send a WAV file to the Whisper API and return the transcript text.

    Args:
        file_path: Absolute path to the WAV segment.
        api_key:   Bearer token for the API.

    Returns:
        The transcribed text for this segment.

    Raises:
        requests.HTTPError: If the API returns a non-2xx status.
    """
    with open(file_path, "rb") as f:
        response = requests.post(
            WHISPER_API_URL,
            headers={"Authorization": f"Bearer {api_key}"},
            files={"file": (os.path.basename(file_path), f, "audio/wav")},
            data={"model": WHISPER_MODEL},
            timeout=120,
        )

    response.raise_for_status()
    return response.json().get("text", "").strip()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def transcribe_segments(
    audio_path: str,
    segments: List[Tuple[float, float]],
) -> str:
    """
    Transcribe speech segments and return a single merged transcript.

    Args:
        audio_path: Absolute path to the normalised 16 kHz mono WAV.
        segments:   List of ``(start_seconds, end_seconds)`` tuples from
                    the VAD step.

    Returns:
        Merged transcript string (all segments concatenated in order).
        Returns ``""`` if *segments* is empty or every segment fails.
    """
    # ------------------------------------------------------------------
    # 1. Handle empty input
    # ------------------------------------------------------------------
    if not segments:
        logger.warning("transcribe_segments — no segments provided, returning empty transcript")
        return ""

    logger.info(
        "transcribe_segments — start  audio=%s  segments=%d",
        audio_path,
        len(segments),
    )

    api_key = _get_api_key()

    transcripts: List[str] = []
    temp_files: List[str] = []

    for i, (start, end) in enumerate(segments):
        duration = round(end - start, 3)
        logger.info(
            "  segment %d/%d: %.3fs – %.3fs (%.1fs)",
            i + 1,
            len(segments),
            start,
            end,
            duration,
        )

        segment_path: str | None = None
        try:
            # ----------------------------------------------------------
            # 2. Extract the segment audio via ffmpeg
            # ----------------------------------------------------------
            segment_path = _extract_segment(audio_path, start, end, i)
            temp_files.append(segment_path)

            # ----------------------------------------------------------
            # 3. Send to Whisper API
            # ----------------------------------------------------------
            text = _transcribe_file(segment_path, api_key)
            logger.info(
                "  segment %d transcript (%d chars): %.80s%s",
                i + 1,
                len(text),
                text,
                "…" if len(text) > 80 else "",
            )
            transcripts.append(text)

        except Exception:
            # Log and skip — we still process remaining segments
            logger.exception("  segment %d — failed, skipping", i + 1)

    # ------------------------------------------------------------------
    # 4. Clean up temporary segment files
    # ------------------------------------------------------------------
    for path in temp_files:
        try:
            os.remove(path)
            logger.debug("Removed temp file %s", path)
        except OSError:
            logger.warning("Could not remove temp file %s", path)

    # ------------------------------------------------------------------
    # 5. Merge and return
    # ------------------------------------------------------------------
    merged = " ".join(transcripts).strip()
    logger.info(
        "transcribe_segments — done  total_chars=%d",
        len(merged),
    )
    return merged
