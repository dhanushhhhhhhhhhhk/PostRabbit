"""
summarize.py — Generate summary and key points via OpenRouter LLM.

Responsibility:
    Send the transcript to an LLM through the OpenRouter chat-completions
    API and return a structured dict with a concise summary and a list of
    key insights.

Prompt design:
    - A *system* message sets the persona ("social-media video analyst").
    - A *user* message contains the transcript and asks for a summary
      (2–3 sentences) plus bullet-point key insights (3–6 items).

Parsing:
    The raw LLM output is split into a summary block and a key-points
    list using simple heuristics (look for numbered / bulleted lines).
    This is intentionally lightweight — we don’t need perfect parsing
    because the output is already semi-structured by the prompt.

Fallback:
    On any API or parsing error the function returns the first 200 chars
    of the transcript as a degraded summary so that downstream consumers
    always get *something*.
"""

import logging
import os
import re
from typing import Dict, List

import requests

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_MODEL = "openrouter/free"

# ---------------------------------------------------------------------------
# Prompt templates
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = "You analyze transcripts of social media videos."

USER_PROMPT_TEMPLATE = """Analyze the following transcript and produce:

1. A concise summary (2–3 sentences)
2. Key insights as bullet points (3–6 items)

Transcript:
{transcript}"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_api_key() -> str:
    """Read the OpenRouter API key from the environment (lazy)."""
    key = os.getenv("OPENROUTER_API_KEY", "")
    if not key:
        raise RuntimeError(
            "OPENROUTER_API_KEY environment variable is not set. "
            "Cannot call the OpenRouter LLM API."
        )
    return key


def _parse_response(text: str) -> Dict[str, object]:
    """
    Split the raw LLM output into *summary* and *key_points*.

    Strategy:
        - Lines that start with a bullet (•, -, *) or a digit+period are
          treated as key-point items.
        - Everything before the first key-point line is the summary.
        - The "Key insights" / "Key points" header line (if present) is
          stripped from the summary.
    """
    lines = text.strip().splitlines()

    summary_lines: List[str] = []
    key_points: List[str] = []
    in_key_points = False

    # Regex for bullet / numbered list items
    bullet_re = re.compile(r"^\s*(?:[\-\*\u2022]|\d+[\.\)])\ *(.+)")
    # Regex for a header like "Key insights:" or "Key points:"
    header_re = re.compile(r"^\s*(?:key\s*(?:insights?|points?|takeaways?))\s*:?\s*$", re.IGNORECASE)

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        # Detect transition into key-points section
        if header_re.match(stripped):
            in_key_points = True
            continue

        match = bullet_re.match(stripped)
        if match:
            in_key_points = True
            key_points.append(match.group(1).strip())
        elif not in_key_points:
            # Skip summary-section headers like "Summary:"
            if re.match(r"^\s*summary\s*:?\s*$", stripped, re.IGNORECASE):
                continue
            summary_lines.append(stripped)

    summary = " ".join(summary_lines).strip()

    return {"summary": summary, "key_points": key_points}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def generate_summary(transcript: str) -> Dict[str, object]:
    """
    Generate a summary and key insights from a transcript via OpenRouter.

    Args:
        transcript: Full text transcript from the Whisper step.

    Returns:
        ``{"summary": str, "key_points": list[str]}``.
        On failure returns a degraded fallback so callers always get a dict.
    """
    # ------------------------------------------------------------------
    # 1. Handle empty transcript
    # ------------------------------------------------------------------
    if not transcript or not transcript.strip():
        logger.warning("generate_summary — empty transcript, returning blank result")
        return {"summary": "", "key_points": []}

    logger.info(
        "generate_summary — start  transcript_length=%d",
        len(transcript),
    )

    # ------------------------------------------------------------------
    # 2. Build the API request
    # ------------------------------------------------------------------
    api_key = _get_api_key()

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": OPENROUTER_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": USER_PROMPT_TEMPLATE.format(transcript=transcript),
            },
        ],
    }

    # ------------------------------------------------------------------
    # 3. Call OpenRouter
    # ------------------------------------------------------------------
    try:
        response = requests.post(
            OPENROUTER_API_URL,
            headers=headers,
            json=payload,
            timeout=60,
        )
        response.raise_for_status()

        data = response.json()
        raw_text = (
            data.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
        )

        logger.info(
            "generate_summary — LLM response length=%d",
            len(raw_text),
        )

    except Exception:
        # --------------------------------------------------------------
        # 4. Fallback on any API / network error
        # --------------------------------------------------------------
        logger.exception("generate_summary — OpenRouter request failed, using fallback")
        return {
            "summary": transcript[:200],
            "key_points": [],
        }

    # ------------------------------------------------------------------
    # 5. Parse the LLM output
    # ------------------------------------------------------------------
    result = _parse_response(raw_text)

    # If parsing produced nothing useful, degrade gracefully
    if not result["summary"] and not result["key_points"]:
        logger.warning("generate_summary — parsing produced empty result, using raw text")
        result["summary"] = raw_text.strip()[:500]

    logger.info(
        "generate_summary — done  summary_length=%d  key_points=%d",
        len(result["summary"]),
        len(result["key_points"]),
    )

    return result
