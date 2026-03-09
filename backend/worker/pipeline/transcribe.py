"""
transcribe.py — Transcribe audio using the Whisper API.

Responsibility:
    Given a normalised WAV file, send it directly to the OpenAI Whisper API
    and return the full transcript string.

Workflow:
    1. POST the audio file to the Whisper ``/v1/audio/transcriptions`` endpoint.
    2. Return the transcript text.
"""

import logging
import os

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

    Loaded lazily (not at import time) so that worker code that doesn't
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
# Public API
# ---------------------------------------------------------------------------


def transcribe_segments(audio_path: str) -> str:
    """
    Transcribe the full audio file and return the transcript.

    Args:
        audio_path: Absolute path to the normalised 16 kHz mono WAV.

    Returns:
        Transcript string.  Returns ``""`` if the API returns no text.
    """
    logger.info("transcribe_segments — start  audio=%s", audio_path)

    api_key = _get_api_key()

    with open(audio_path, "rb") as f:
        response = requests.post(
            WHISPER_API_URL,
            headers={"Authorization": f"Bearer {api_key}"},
            files={"file": (os.path.basename(audio_path), f, "audio/wav")},
            data={"model": WHISPER_MODEL},
            timeout=300,
        )

    response.raise_for_status()
    transcript = response.json().get("text", "").strip()

    logger.info(
        "transcribe_segments — done  total_chars=%d",
        len(transcript),
    )
    return transcript
