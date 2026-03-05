# PostRabbit Backend

Social-media video summarization API. Users share Instagram Reels or YouTube videos; the backend downloads the audio, transcribes speech, and generates a summary with key points.

## Architecture

```
backend/
  app/
    main.py          — FastAPI entry point
    config.py        — Environment-based settings
    database.py      — SQLAlchemy engine, session, Base
    models/
      video.py       — Video ORM model
    schemas/
      video.py       — Pydantic request/response schemas
    routes/
      health.py      — Health-check endpoint
      submissions.py — Video submission endpoints
    services/
      video_service.py — Business-logic helpers
  worker/
    worker.py        — Background polling worker
    pipeline/
      download.py    — yt-dlp audio download
      normalize.py   — ffmpeg audio normalization
      vad.py         — Silero VAD speech detection
      transcribe.py  — Whisper transcription
      summarize.py   — OpenRouter LLM summarization
  requirements.txt
  README.md
```

## Processing Pipeline

```
URL → yt-dlp → ffmpeg → Silero VAD → Whisper → OpenRouter LLM → PostgreSQL
```

## Quick Start

```bash
# 1. Create a virtual environment
python -m venv venv
source venv/bin/activate   # Linux/macOS
venv\Scripts\activate      # Windows

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment
cp .env.example .env       # then edit .env with your values

# 4. Run the API
uvicorn app.main:app --reload

# 5. Run the worker (separate terminal)
python -m worker.worker
```

## Environment Variables

| Variable             | Description                          | Default                                    |
|----------------------|--------------------------------------|--------------------------------------------|
| `DATABASE_URL`       | PostgreSQL connection string         | `postgresql://localhost:5432/postrabbit`    |
| `OPENROUTER_API_KEY` | API key for OpenRouter LLM service   | *(empty)*                                  |
| `DEBUG`              | Enable debug mode                    | `false`                                    |

## Tech Stack

- **FastAPI** — async web framework
- **PostgreSQL** — relational database
- **SQLAlchemy** — ORM / database toolkit
- **yt-dlp** — video/audio downloader
- **ffmpeg** — audio normalization
- **Silero VAD** — voice activity detection
- **Whisper** — speech-to-text
- **OpenRouter** — LLM summarization
