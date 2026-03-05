"""
config.py — Centralized configuration loaded from environment variables.

Uses python-dotenv to read a .env file when present, then exposes all
settings through a single `Settings` instance imported elsewhere.

Environment variables:
    DATABASE_URL        — PostgreSQL connection string
    OPENROUTER_API_KEY  — API key for the OpenRouter LLM service
    DEBUG               — Enable debug mode (default: False)
"""

import os
from dotenv import load_dotenv

# Load .env file from project root (if it exists)
load_dotenv()


class Settings:
    """Application settings populated from environment variables."""

    # PostgreSQL connection string
    # Example: postgresql://user:password@localhost:5432/postrabbit
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://localhost:5432/postrabbit")

    # OpenRouter API key used by the LLM summarization step
    OPENROUTER_API_KEY: str = os.getenv("OPENROUTER_API_KEY", "")

    # Whisper API key used by the transcription pipeline step
    WHISPER_API_KEY: str = os.getenv("WHISPER_API_KEY", "")

    # Toggle debug / development helpers
    DEBUG: bool = os.getenv("DEBUG", "false").lower() in ("true", "1", "yes")


# Singleton settings instance used throughout the app
settings = Settings()
