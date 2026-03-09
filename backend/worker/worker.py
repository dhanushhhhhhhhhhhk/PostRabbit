"""
worker.py — Background worker entry point.

Continuously polls the ``jobs`` table for pending work and runs each job
through the processing pipeline:

    1. download_audio      — Fetch audio via yt-dlp
    2. normalize_audio     — Normalize audio with ffmpeg
    3. transcribe_segments — Transcribe full audio with Whisper
    4. generate_summary    — Generate summary & key points via OpenRouter LLM

Concurrency safety
------------------
Multiple worker instances can run in parallel.  Each worker acquires a
row-level lock on the job it picks up using PostgreSQL's
``SELECT … FOR UPDATE SKIP LOCKED``, which guarantees that no two workers
will ever process the same job simultaneously.

After the pipeline completes (or fails), the worker persists the results
in ``content_analysis`` and updates the status on both the ``jobs`` and
``content`` tables.
"""

import logging
import time
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.content import Content
from app.models.content_analysis import ContentAnalysis
from app.models.job import Job

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# How long to sleep (seconds) when the queue is empty
POLL_INTERVAL = 3

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger("worker")

# ---------------------------------------------------------------------------
# Pipeline stage imports
# ---------------------------------------------------------------------------
# Each stage is implemented in its own module under worker/pipeline/.

from worker.pipeline.download import download_audio
from worker.pipeline.normalize import normalize_audio
from worker.pipeline.transcribe import transcribe_segments
from worker.pipeline.summarize import generate_summary


# ---------------------------------------------------------------------------
# Job fetching — safe row-level locking
# ---------------------------------------------------------------------------


def fetch_next_job(db: Session) -> Optional[Job]:
    """
    Fetch the oldest pending job while acquiring a row-level lock.

    Uses ``FOR UPDATE SKIP LOCKED`` so that:
      - The selected row is locked for the duration of this transaction.
      - Any rows already locked by another worker are silently skipped,
        preventing duplicate processing.

    Returns the locked Job instance, or None if the queue is empty.
    """
    job = (
        db.query(Job)
        .filter(Job.status == "pending")
        .order_by(Job.created_at)
        .with_for_update(skip_locked=True)
        .first()
    )
    return job


# ---------------------------------------------------------------------------
# Job processing
# ---------------------------------------------------------------------------


def process_job(db: Session, job: Job) -> None:
    """
    Run the full processing pipeline for a single locked job.

    Steps:
        1. Mark the job and its parent content as *processing*.
        2. Execute each pipeline stage in order.
        3. Persist the analysis results in ``content_analysis``.
        4. Mark the job and content as *completed*.

    If any stage raises an exception the job and content are marked
    *failed* and the error is logged.
    """
    content: Optional[Content] = (
        db.query(Content).filter(Content.id == job.content_id).first()
    )

    # ------------------------------------------------------------------
    # 1. Transition to "processing"
    # ------------------------------------------------------------------
    logger.info("Marking job %s as processing (content %s)", job.id, job.content_id)
    job.status = "processing"
    job.started_at = datetime.now(timezone.utc)
    if content:
        content.status = "processing"
    db.commit()

    try:
        # --------------------------------------------------------------
        # 2. Run pipeline stages
        #    download → normalize → transcribe → summarize
        # --------------------------------------------------------------
        url = content.url if content else ""
        logger.info("Starting pipeline for job %s — url=%s", job.id, url)

        audio_path = download_audio(url)
        normalized_path = normalize_audio(audio_path)
        transcript = transcribe_segments(normalized_path)
        result = generate_summary(transcript)

        logger.info("Pipeline completed for job %s", job.id)

        # --------------------------------------------------------------
        # 3. Persist analysis results
        # --------------------------------------------------------------
        analysis = ContentAnalysis(
            content_id=job.content_id,
            transcript=transcript,
            summary=result["summary"],
            key_points=result["key_points"],
        )
        db.add(analysis)
        logger.info("Saved content_analysis for content %s", job.content_id)

        # --------------------------------------------------------------
        # 4. Mark completed
        # --------------------------------------------------------------
        job.status = "completed"
        job.finished_at = datetime.now(timezone.utc)
        if content:
            content.status = "completed"
        db.commit()
        logger.info("Job %s completed successfully", job.id)

    except Exception:
        # --------------------------------------------------------------
        # Handle failure — mark both records and log the traceback
        # --------------------------------------------------------------
        logger.exception("Job %s failed", job.id)
        db.rollback()

        job.status = "failed"
        job.finished_at = datetime.now(timezone.utc)
        if content:
            content.status = "failed"
        db.commit()


# ---------------------------------------------------------------------------
# Main worker loop
# ---------------------------------------------------------------------------


def run_worker() -> None:
    """
    Entry point for the background worker process.

    Runs an infinite loop that:
      1. Opens a new DB session.
      2. Attempts to fetch and lock a pending job.
      3. Processes the job (or sleeps if the queue is empty).
      4. Closes the session before the next iteration.

    Designed to be launched as a standalone process:
        python -m worker.worker
    """
    logger.info("Worker starting — polling every %ds", POLL_INTERVAL)

    while True:
        db = SessionLocal()
        try:
            job = fetch_next_job(db)

            if job is None:
                # Nothing to do — wait and try again
                logger.debug("No pending jobs — sleeping %ds", POLL_INTERVAL)
                db.close()
                time.sleep(POLL_INTERVAL)
                continue

            logger.info(
                "Picked up job %s for content %s", job.id, job.content_id
            )
            process_job(db, job)

        except Exception:
            # Catch-all so the worker loop never crashes
            logger.exception("Unexpected error in worker loop")
            db.rollback()
        finally:
            db.close()


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    run_worker()
