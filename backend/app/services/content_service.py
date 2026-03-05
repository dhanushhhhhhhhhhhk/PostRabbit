"""
content_service.py — Service layer for content-related operations.

Centralizes database queries and business rules so that routes stay thin.
Each function maps to a discrete operation on the content / job / analysis
tables.  Business logic (e.g. source detection, duplicate prevention, status
transitions) lives here rather than directly inside route handlers.
"""

import logging
from uuid import UUID
from typing import Optional, Tuple

from sqlalchemy.orm import Session

from app.models.content import Content
from app.models.job import Job
from app.models.content_analysis import ContentAnalysis

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Source detection
# ---------------------------------------------------------------------------

SUPPORTED_SOURCES = {
    "youtube": ["youtube.com", "youtu.be"],
    "instagram": ["instagram.com"],
}


def detect_source(url: str) -> Optional[str]:
    """
    Determine the content platform from the URL.

    Returns:
        'youtube', 'instagram', or None if the URL doesn't match
        any supported platform.
    """
    url_lower = url.lower()
    for source, domains in SUPPORTED_SOURCES.items():
        if any(domain in url_lower for domain in domains):
            return source
    return None


# ---------------------------------------------------------------------------
# Content helpers
# ---------------------------------------------------------------------------

def get_content_by_id(db: Session, content_id: UUID) -> Optional[Content]:
    """Fetch a single content item by primary key."""
    return db.query(Content).filter(Content.id == content_id).first()


def get_existing_content(db: Session, user_id: UUID, url: str) -> Optional[Content]:
    """
    Look up an existing content record for this user + URL pair.

    Used for duplicate prevention — if the same user submits the same URL
    twice we return the original record rather than creating a new one.
    """
    return (
        db.query(Content)
        .filter(Content.user_id == user_id, Content.url == url)
        .first()
    )


def create_content(db: Session, user_id: UUID, url: str, source: str) -> Tuple[Content, bool]:
    """
    Persist a new content submission with status 'pending', or return the
    existing record if this user has already submitted the same URL.

    Also creates an initial processing Job so the worker picks it up
    (only when a new record is created).

    Returns:
        (content, created) — the Content row and a boolean indicating
        whether a new record was created (True) or an existing duplicate
        was returned (False).
    """
    # --- Duplicate check ------------------------------------------------
    existing = get_existing_content(db, user_id, url)
    if existing:
        logger.info("Duplicate URL for user %s — returning existing content %s", user_id, existing.id)
        return existing, False

    # --- Create new content + job ---------------------------------------
    content = Content(user_id=user_id, url=url, source=source)
    db.add(content)
    db.flush()  # flush to generate content.id before creating the job

    # Automatically enqueue a processing job for this content
    job = Job(content_id=content.id)
    db.add(job)

    db.commit()
    db.refresh(content)
    logger.info("Created content %s with pending job for user %s", content.id, user_id)
    return content, True


def update_content_status(db: Session, content_id: UUID, status: str) -> Optional[Content]:
    """Update the high-level processing status of a content item."""
    content = get_content_by_id(db, content_id)
    if content:
        content.status = status
        db.commit()
        db.refresh(content)
    return content


# ---------------------------------------------------------------------------
# Job helpers
# ---------------------------------------------------------------------------

def get_pending_job(db: Session) -> Optional[Job]:
    """Fetch the oldest pending job (FIFO)."""
    return (
        db.query(Job)
        .filter(Job.status == "pending")
        .order_by(Job.created_at)
        .first()
    )


# ---------------------------------------------------------------------------
# Analysis helpers
# ---------------------------------------------------------------------------

def create_analysis(
    db: Session,
    content_id: UUID,
    transcript: str,
    summary: str,
    key_points: list,
) -> ContentAnalysis:
    """Persist the AI-generated analysis for a content item."""
    analysis = ContentAnalysis(
        content_id=content_id,
        transcript=transcript,
        summary=summary,
        key_points=key_points,
    )
    db.add(analysis)
    db.commit()
    db.refresh(analysis)
    return analysis
