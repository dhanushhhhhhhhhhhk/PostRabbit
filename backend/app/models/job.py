"""
job.py — SQLAlchemy model for processing jobs.

Each Job row represents a single attempt to process a piece of content
through the pipeline (download → normalize → VAD → transcribe → summarize).

Jobs are separated from Content so that:
  - We can retry processing without duplicating the content record.
  - Job-specific timing (started_at, finished_at) stays isolated.
  - The worker only needs to query the jobs table, not the content table.

Columns:
    id          — Primary key (UUID).
    content_id  — Foreign key → content.id (which content this job processes).
    status      — Job status: pending | processing | completed | failed.
    created_at  — When the job was enqueued.
    started_at  — When the worker began processing (NULL until started).
    finished_at — When processing finished or failed (NULL until done).
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, Index, String, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


class Job(Base):
    """A processing job in the pipeline queue."""

    __tablename__ = "jobs"

    # Primary key — UUID generated on insert
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Foreign key to the content being processed
    content_id = Column(UUID(as_uuid=True), ForeignKey("content.id"), nullable=False)

    # Job status: pending | processing | completed | failed
    # Indexed so the worker can efficiently poll for pending jobs
    status = Column(String, nullable=False, default="pending", index=True)

    # When the job was created / enqueued
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # When the worker picked up the job (NULL while pending)
    started_at = Column(DateTime, nullable=True)

    # When the job finished or failed (NULL while in progress)
    finished_at = Column(DateTime, nullable=True)

    # ---------------------------------------------------------------------------
    # Relationships
    # ---------------------------------------------------------------------------

    # Many-to-one: each job belongs to a content item
    content = relationship("Content", back_populates="jobs")
