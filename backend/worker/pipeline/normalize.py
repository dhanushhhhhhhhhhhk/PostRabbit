"""
normalize.py — Normalize audio using ffmpeg.

Responsibility:
    Convert a raw audio file (any format yt-dlp produced) into a mono
    16 kHz WAV file optimised for speech processing and Whisper
    transcription.

Why these settings?
    - Mono (-ac 1):    Whisper expects single-channel audio.  Mixing
                       to mono also halves the data size.
    - 16 kHz (-ar 16000): The native sample rate for Whisper.
                       Resampling here avoids redundant work later.

The original file is intentionally NOT deleted — cleanup is handled by a
later pipeline stage.
"""

import logging
import os
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def normalize_audio(input_path: str) -> str:
    """
    Convert *input_path* to a normalised WAV suitable for speech processing.

    Args:
        input_path: Absolute path to the raw audio file produced by
                    ``download_audio()`` (e.g. ``/tmp/postrabbit/abcd1234.webm``).

    Returns:
        Absolute path to the normalised WAV file
        (e.g. ``/tmp/postrabbit/abcd1234_normalized.wav``).

    Raises:
        FileNotFoundError: If *input_path* does not exist.
        RuntimeError:      If ffmpeg exits with a non-zero code or the output
                           file is not created.
    """
    # ------------------------------------------------------------------
    # 1. Validate the input file
    # ------------------------------------------------------------------
    if not os.path.isfile(input_path):
        logger.error("normalize_audio — input file not found: %s", input_path)
        raise FileNotFoundError(f"Input audio file not found: {input_path}")

    logger.info("normalize_audio — start  input=%s", input_path)

    # ------------------------------------------------------------------
    # 2. Derive the output path
    #    /tmp/postrabbit/abcd1234.webm → /tmp/postrabbit/abcd1234_normalized.wav
    # ------------------------------------------------------------------
    stem = Path(input_path).stem            # e.g. "abcd1234"
    parent = str(Path(input_path).parent)   # e.g. "/tmp/postrabbit"
    output_path = os.path.join(parent, f"{stem}_normalized.wav")

    # ------------------------------------------------------------------
    # 3. Build the ffmpeg command
    # ------------------------------------------------------------------
    #   -y        → overwrite output if it already exists
    #   -i        → input file
    #   -ac 1     → mix down to mono
    #   -ar 16000 → resample to 16 kHz
    cmd = [
        "ffmpeg",
        "-y",
        "-i", input_path,
        "-ac", "1",
        "-ar", "16000",
        output_path,
    ]

    logger.info("normalize_audio — running: %s", " ".join(cmd))

    # ------------------------------------------------------------------
    # 4. Execute ffmpeg
    # ------------------------------------------------------------------
    result = subprocess.run(
        cmd,
        capture_output=True,   # capture stdout + stderr
        text=True,             # decode as UTF-8
    )

    # ------------------------------------------------------------------
    # 5. Handle failure
    # ------------------------------------------------------------------
    if result.returncode != 0:
        logger.error(
            "normalize_audio — ffmpeg failed (exit %d)\nstderr: %s",
            result.returncode,
            result.stderr.strip(),
        )
        raise RuntimeError(
            f"ffmpeg exited with code {result.returncode}: {result.stderr.strip()}"
        )

    # ------------------------------------------------------------------
    # 6. Verify the output file was created
    # ------------------------------------------------------------------
    if not os.path.isfile(output_path):
        logger.error("normalize_audio — output file not found: %s", output_path)
        raise RuntimeError(f"Normalised audio file was not created at {output_path}")

    logger.info("normalize_audio — saved  output=%s", output_path)
    return output_path
