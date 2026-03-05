"""
download.py — Download audio from a video URL using yt-dlp.

Responsibility:
    Given an Instagram Reel or YouTube URL, download ONLY the best
    available audio stream to a local directory and return the absolute
    file path.  No format conversion happens here — that is handled by
    normalize.py.

How it works:
    1. Ensure the output directory (/tmp/postrabbit) exists.
    2. Shell out to ``yt-dlp -f bestaudio`` via subprocess.
    3. Parse yt-dlp's stdout to find the final downloaded file path.
    4. Return that path (e.g. /tmp/postrabbit/abcd1234.webm).

Error handling:
    If yt-dlp exits with a non-zero code the function raises a
    ``RuntimeError`` with the captured stderr.
"""

import logging
import os
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Persistent temp directory where all raw audio files are stored.
# On Railway (Linux) this maps to the container's /tmp.
OUTPUT_DIR = "/tmp/postrabbit"

# yt-dlp output template — uses the video ID and native extension so each
# download gets a unique, predictable filename.
OUTPUT_TEMPLATE = os.path.join(OUTPUT_DIR, "%(id)s.%(ext)s")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def download_audio(url: str) -> str:
    """
    Download the best audio stream from a YouTube or Instagram URL.

    Args:
        url: The full video URL (YouTube or Instagram Reel).

    Returns:
        Absolute path to the downloaded audio file
        (e.g. ``/tmp/postrabbit/abcd1234.webm``).

    Raises:
        RuntimeError: If yt-dlp exits with a non-zero status.
    """
    # ------------------------------------------------------------------
    # 1. Ensure the output directory exists
    # ------------------------------------------------------------------
    Path(OUTPUT_DIR).mkdir(parents=True, exist_ok=True)
    logger.info("download_audio — start  url=%s", url)

    # ------------------------------------------------------------------
    # 2. Build the yt-dlp command
    # ------------------------------------------------------------------
    #   -f bestaudio        → select the best audio-only stream
    #   -o OUTPUT_TEMPLATE  → save with the video ID as filename
    #   --no-playlist       → refuse to download entire playlists
    #   --print after_move:filepath
    #                       → print the final file path to stdout after
    #                         any post-processing moves (reliable way to
    #                         discover the saved filename)
    cmd = [
        "yt-dlp",
        "-f", "bestaudio",
        "-o", OUTPUT_TEMPLATE,
        "--no-playlist",
        "--print", "after_move:filepath",
        url,
    ]

    logger.info("download_audio — running: %s", " ".join(cmd))

    # ------------------------------------------------------------------
    # 3. Execute yt-dlp as a subprocess
    # ------------------------------------------------------------------
    result = subprocess.run(
        cmd,
        capture_output=True,   # capture stdout + stderr
        text=True,             # decode as UTF-8
    )

    # ------------------------------------------------------------------
    # 4. Handle failure
    # ------------------------------------------------------------------
    if result.returncode != 0:
        logger.error(
            "download_audio — yt-dlp failed (exit %d)\nstderr: %s",
            result.returncode,
            result.stderr.strip(),
        )
        raise RuntimeError(
            f"yt-dlp exited with code {result.returncode}: {result.stderr.strip()}"
        )

    # ------------------------------------------------------------------
    # 5. Extract the downloaded file path from yt-dlp output
    # ------------------------------------------------------------------
    #    ``--print after_move:filepath`` writes the absolute path as the
    #    last non-empty line of stdout.
    lines = [l.strip() for l in result.stdout.strip().splitlines() if l.strip()]
    if not lines:
        logger.error("download_audio — yt-dlp produced no output")
        raise RuntimeError("yt-dlp produced no output — cannot determine file path")

    file_path = lines[-1]

    # Sanity-check: the file should actually exist on disk.
    if not os.path.isfile(file_path):
        logger.error("download_audio — expected file not found: %s", file_path)
        raise RuntimeError(f"Downloaded file not found at {file_path}")

    logger.info("download_audio — saved  path=%s", file_path)
    return file_path
